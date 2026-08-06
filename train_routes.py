# -*- coding: utf-8 -*-
# vapi-od : "나만의 AI 만들기" 라우터 (브라우저 학습 결과를 서버 OpenVINO로 추론)
# 기존 파일을 건드리지 않는 독립 모듈 — main.py에 두 줄만 추가해 연결한다:
#   import train_routes
#   app.include_router(train_routes.router)
#
# 모델 파일:
#   models/backbone/mobilenetv2_feat.xml / .bin / .json   (HF에서 배포)
#   models/user/<slug>/model.zip + meta.json               (학생이 만든 AI)
#   models/project/<slug>.zip                              (작업 중인 작품 — 사진 포함)
#
# 특징(feature) 두 가지를 지원한다:
#   kind="image" : MobileNetV2 1280차원 (OpenVINO)
#   kind="pose"  : MediaPipe 손 랜드마크 21점 정규화 63차원 (mp_routes 재사용)
#
# 이미지 전처리는 브라우저(TF.js)와 반드시 동일해야 한다:
#   fromPixels(RGB) -> resizeNearestNeighbor([224,224]) -> toFloat() -> div(255)
import io
import json
import os
import re
import shutil
import threading
import time
import uuid
import zipfile
from typing import List

import cv2
import numpy as np
from fastapi import APIRouter, Body, File, Form, Query, Request, UploadFile
from fastapi.responses import FileResponse

router = APIRouter()

BACKBONE_XML = "models/backbone/mobilenetv2_feat.xml"
USER_DIR = "models/user"
PROJECT_DIR = "models/project"
REPORTS_PATH = "models/stats/reports.json"
IMAGE_DIR = "image_temp/"
IMAGE_DIM = 1280
POSE_DIM = 63                       # 21점 × (x,y,z)
SIZE = 224
MAX_ZIP = 128 * 1024 * 1024         # 업로드 zip 상한
MAX_IMAGES = 600                    # zip 1회 처리 상한
MAX_BATCH = 64                      # 배치 임베딩 1회 장수
DEVICE_ORDER = ["NPU", "GPU", "CPU"]  # 가벼운 모델이라 NPU 우선

_lock = threading.Lock()
_core = None
_compiled = None
_out = None
_device = "CPU"
_meta = {}
_heads = {}                         # slug -> Head (캐시)

_DT = {"float32": np.float32, "int32": np.int32, "uint8": np.uint8, "bool": np.bool_}
DIM_OF = {"image": IMAGE_DIM, "pose": POSE_DIM}


class SoftError(ValueError):
    """사용자에게 그대로 보여줄 예상된 실패 (손 없음 등) — 트레이스백을 찍지 않는다."""


# ---------------------------------------------------------------- 백본
def _load():
    """첫 호출 때 백본 IR 로딩 (NPU > GPU > CPU, 실패하면 다음 디바이스로)."""
    global _core, _compiled, _out, _device, _meta
    if _compiled is not None:
        return
    import openvino as ov
    if not os.path.exists(BACKBONE_XML):
        raise RuntimeError(f"백본 모델이 없습니다: {BACKBONE_XML} (hf download 단계를 실행하세요)")
    _core = ov.Core()
    model = _core.read_model(BACKBONE_XML)
    avail = _core.available_devices
    last = None
    for dev in DEVICE_ORDER:
        if dev not in avail:
            continue
        try:
            cfg = {"INFERENCE_PRECISION_HINT": "f16"} if dev in ("NPU", "GPU") else {}
            _compiled = _core.compile_model(model, dev, cfg)
            _device = dev
            break
        except Exception as ex:                 # NPU 미지원 레이어 등 → 다음 디바이스
            last = ex
            print(f"[custom] {dev} compile failed: {ex}")
    if _compiled is None:
        raise RuntimeError(f"백본을 컴파일할 수 없습니다: {last}")
    _out = _compiled.output(0)
    mp_ = os.path.splitext(BACKBONE_XML)[0] + ".json"
    if os.path.exists(mp_):
        with open(mp_, encoding="utf-8") as f:
            _meta = json.load(f)
    print(f"[custom] mobilenetv2_feat loaded ({_device}, dim={IMAGE_DIM})")


def _preprocess(bgr):
    """BGR ndarray -> (1,224,224,3) float32.  TF.js resizeNearestNeighbor 동일 구현.

    float32 연산이어야 TF / tfjs(WebGL 셰이더)와 픽셀 단위로 일치한다.
    """
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    h, w = rgb.shape[:2]
    ar = np.arange(SIZE, dtype=np.float32)
    yi = np.floor(ar * (np.float32(h) / np.float32(SIZE))).astype(np.int32).clip(0, h - 1)
    xi = np.floor(ar * (np.float32(w) / np.float32(SIZE))).astype(np.int32).clip(0, w - 1)
    return (rgb[yi][:, xi].astype(np.float32) / 255.0)[None, ...]


def _embed_image(bgr):
    _load()
    x = _preprocess(bgr)
    with _lock:
        return _compiled(x)[_out].reshape(-1)          # (1280,)


# ---------------------------------------------------------------- 포즈(손) 특징
def _hand_landmarks(bgr):
    """손 랜드마크 21점. 없으면 None. (norm=0~1 화면좌표, px=픽셀좌표, handed=Left/Right)"""
    import mp_routes                                    # MediaPipe 로딩은 mp_routes 재사용
    mp_routes._load()
    h, w = bgr.shape[:2]
    with mp_routes._lock:
        res = mp_routes._hand.recognize(mp_routes._mp_image(bgr))
    if not res or not res.hand_landmarks:
        return None
    lms = res.hand_landmarks[0]
    handed = ""
    if res.handedness and res.handedness[0]:
        handed = res.handedness[0][0].category_name
    gesture = ""
    if res.gestures and res.gestures[0]:
        gesture = res.gestures[0][0].category_name
    norm = [[round(float(p.x), 4), round(float(p.y), 4)] for p in lms]
    px = np.array([[p.x * w, p.y * h, p.z * w] for p in lms], dtype=np.float32)
    return {"norm": norm, "px": px, "handed": handed, "gesture": gesture}


def _embed_pose(bgr):
    """손 랜드마크 21점을 손목 기준·크기 정규화해 63차원으로 만든다.

    카메라와의 거리·화면 위치가 달라도 같은 손모양이면 비슷한 값이 나오도록 한다.
    """
    hand = _hand_landmarks(bgr)
    if hand is None:
        raise SoftError("손이 보이지 않아요. 손을 화면 안에 보여 주세요.")
    pts = hand["px"].copy()
    pts -= pts[0]                                       # 손목을 원점으로
    scale = float(np.linalg.norm(pts, axis=1).max())
    if scale > 0:
        pts /= scale                                    # 손 크기로 정규화
    return pts.reshape(-1)                              # (63,)


def _embed(bgr, kind="image"):
    return _embed_pose(bgr) if kind == "pose" else _embed_image(bgr)


def _imread(path):
    img = cv2.imread(path)
    if img is None:
        raise ValueError("invalid image")
    return img


def _decode(raw):
    img = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("invalid image")
    return img


# ---------------------------------------------------------------- 헤드
class Head:
    """브라우저(TF.js)에서 내보낸 zip -> numpy 행렬곱 2회.

    zip 구조: model.json / weightsSpecs.json / weights.bin / labels.txt [+ kind.txt]
    구조    : Dense(D->128, relu) -> Dropout(추론시 항등) -> Dense(128->N, softmax)
    """

    def __init__(self, zip_bytes):
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
        names = set(zf.namelist())
        for req in ("model.json", "weightsSpecs.json", "weights.bin", "labels.txt"):
            if req not in names:
                raise ValueError(f"zip에 {req} 이(가) 없습니다")

        specs = json.loads(zf.read("weightsSpecs.json").decode("utf-8"))
        buf = zf.read("weights.bin")
        self.labels = [s.strip() for s in
                       zf.read("labels.txt").decode("utf-8").splitlines() if s.strip()]
        self.report = None
        if "report.json" in names:
            try:
                self.report = json.loads(zf.read("report.json").decode("utf-8"))
            except Exception:
                self.report = None
        self.kind = "image"
        if "kind.txt" in names:
            k = zf.read("kind.txt").decode("utf-8").strip()
            if k in DIM_OF:
                self.kind = k

        tensors, off = [], 0
        for s in specs:
            shape = tuple(s["shape"])
            dt = _DT[s["dtype"]]
            n = int(np.prod(shape)) if shape else 1
            arr = np.frombuffer(buf, dtype=dt, count=n, offset=off).reshape(shape)
            tensors.append(np.array(arr, dtype=np.float32))
            off += n * np.dtype(dt).itemsize

        mats = [t for t in tensors if t.ndim == 2]
        vecs = [t for t in tensors if t.ndim == 1]
        if len(mats) != 2 or len(vecs) != 2:
            raise ValueError("예상과 다른 가중치 구성입니다 (Dense 2단이 아님)")
        self.W1, self.W2 = mats
        self.b1, self.b2 = vecs
        self.dim = int(self.W1.shape[0])
        if self.dim != DIM_OF[self.kind]:
            raise ValueError(f"입력 차원 불일치: {self.dim} (기대 {DIM_OF[self.kind]})")
        if self.W2.shape[1] != len(self.labels):
            raise ValueError(f"클래스 수 불일치: 가중치 {self.W2.shape[1]} / labels {len(self.labels)}")

    def predict(self, feat):
        h = feat @ self.W1 + self.b1
        np.maximum(h, 0, out=h)
        z = h @ self.W2 + self.b2
        z = z - z.max()
        e = np.exp(z)
        return e / e.sum()


def _slugify(text):
    s = re.sub(r"[^0-9a-zA-Z가-힣]+", "-", (text or "").strip()).strip("-").lower()
    return s[:40] or ("model-" + uuid.uuid4().hex[:6])


def _uniq_slug(root, base):
    """같은 이름이 있으면 -2, -3 으로 늘려 학생 결과물을 덮어쓰지 않는다."""
    s, k = base, 2
    while os.path.exists(os.path.join(root, s)) or os.path.exists(os.path.join(root, s + ".zip")):
        s = f"{base}-{k}"
        k += 1
    return s


def _head(slug):
    with _lock:
        h = _heads.get(slug)
    if h is not None:
        return h
    p = os.path.join(USER_DIR, slug, "model.zip")
    if not os.path.exists(p):
        raise ValueError(f"모델을 찾을 수 없습니다: {slug}")
    with open(p, "rb") as f:
        h = Head(f.read())
    with _lock:
        _heads[slug] = h
    return h


def _zip_images(raw):
    """업로드된 zip 에서 이미지 파일 이름 목록과 zipfile 객체를 돌려준다."""
    if len(raw) > MAX_ZIP:
        raise ValueError(f"압축파일이 너무 큽니다 ({len(raw) // 1048576}MB)")
    zf = zipfile.ZipFile(io.BytesIO(raw))
    exts = (".png", ".jpg", ".jpeg", ".bmp", ".webp")
    names = [n for n in sorted(zf.namelist())
             if n.lower().endswith(exts) and not n.startswith("__MACOSX")]
    if not names:
        raise ValueError("압축파일에 이미지가 없습니다")
    if len(names) > MAX_IMAGES:
        raise ValueError(f"이미지가 너무 많습니다 ({len(names)} / 최대 {MAX_IMAGES})")
    return zf, names


# ---------------------------------------------------------------- 공통 응답
def _run(name, fn):
    """기존 서버와 동일한 {type,result,data,elapsed_ms,device} 응답 포맷."""
    t0 = time.perf_counter()
    try:
        data = fn()
        return {"type": name, "result": "ok", "data": data,
                "elapsed_ms": int((time.perf_counter() - t0) * 1000), "device": _device}
    except SoftError as ex:
        return {"type": name, "result": "fail", "data": str(ex),
                "elapsed_ms": int((time.perf_counter() - t0) * 1000)}
    except Exception as ex:
        import traceback
        traceback.print_exc()
        return {"type": name, "result": "fail", "data": "Inference error:" + str(ex),
                "elapsed_ms": int((time.perf_counter() - t0) * 1000)}


def _run_image(name, upload, fn):
    """웹캠 캡쳐 1장 업로드 — mp_routes 와 동일한 임시파일 방식."""
    os.makedirs(IMAGE_DIR, exist_ok=True)
    path = IMAGE_DIR + name + "-" + str(uuid.uuid4()) + ".jpg"
    with open(path, "wb") as f:
        f.write(upload.file.read())
    try:
        return _run(name, lambda: fn(_imread(path)))
    finally:
        if os.path.exists(path):
            os.remove(path)


# ---------------------------------------------------------------- 특징 추출
@router.post("/custom/embed", tags=["custom"], summary="특징 추출 (캡쳐 1장)")
async def custom_embed(request: Request, uploadFile: UploadFile = File(...),
                       kind: str = Query("image", description="image | pose")):
    def fn(bgr):
        v = _embed(bgr, kind)
        return {"kind": kind, "dim": len(v),
                "feature": [round(float(x), 6) for x in v]}
    return _run_image("custom_embed", uploadFile, fn)


@router.post("/custom/pose", tags=["custom"], summary="손 랜드마크 (화면 표시용)")
async def custom_pose(request: Request, uploadFile: UploadFile = File(...)):
    """손이 없어도 실패로 보지 않는다 — 학습 화면에서 초당 수십 번 호출되는 용도.

    디스크 임시파일을 쓰지 않고 메모리에서 바로 디코드한다.
    """
    raw = uploadFile.file.read()

    def fn():
        hand = _hand_landmarks(_decode(raw))
        if hand is None:
            return {"found": False, "points": []}
        return {"found": True, "points": hand["norm"],
                "hand": hand["handed"], "gesture": hand["gesture"]}
    return _run("custom_pose", fn)


@router.post("/custom/embed_batch", tags=["custom"], summary="특징 추출 (여러 장 한 번에)")
async def custom_embed_batch(request: Request, uploadFiles: List[UploadFile] = File(...),
                             kind: str = Query("image", description="image | pose")):
    """연속 촬영한 프레임을 모아 한 번에 보낸다 — 요청 수를 줄여 훨씬 빠르다."""
    raws = [f.file.read() for f in uploadFiles[:MAX_BATCH]]

    def fn():
        feats, failed = [], []
        for i, raw in enumerate(raws):
            try:
                feats.append([round(float(x), 6) for x in _embed(_decode(raw), kind)])
            except SoftError as ex:
                failed.append({"index": i, "reason": str(ex)})
            except Exception as ex:
                failed.append({"index": i, "reason": str(ex)})
        return {"kind": kind, "dim": DIM_OF.get(kind, 0),
                "count": len(feats), "failed": failed, "features": feats}
    return _run("custom_embed_batch", fn)


@router.post("/custom/embed_zip", tags=["custom"], summary="특징 추출 (클래스 압축파일 통째로)")
async def custom_embed_zip(request: Request, uploadFile: UploadFile = File(...),
                           label: str = Form(""),
                           kind: str = Query("image", description="image | pose")):
    raw = uploadFile.file.read()

    def fn():
        zf, names = _zip_images(raw)
        feats, failed = [], []
        for n in names:
            try:
                feats.append([round(float(x), 6) for x in _embed(_decode(zf.read(n)), kind)])
            except Exception:
                failed.append(n)
        return {"label": label, "kind": kind, "dim": DIM_OF.get(kind, 0),
                "count": len(feats), "failed": failed, "features": feats}
    return _run("custom_embed_zip", fn)


# ---------------------------------------------------------------- 추론
@router.post("/custom/predict", tags=["custom"], summary="내가 만든 AI로 분류 (캡쳐 1장)")
async def custom_predict(request: Request, uploadFile: UploadFile = File(...),
                         model: str = Query(..., description="모델 slug"),
                         top: int = Query(0, description="상위 N개만 (0=전체)")):
    def fn(bgr):
        head = _head(model)
        try:
            probs = head.predict(_embed(bgr, head.kind))
        except SoftError:
            return []            # 손이 안 보이면 "없음" — 블록 코딩이 멈추지 않게 한다
        order = np.argsort(-probs)
        out = [{"name": head.labels[i], "score": round(float(probs[i]), 4)} for i in order]
        return out[:top] if top > 0 else out
    return _run_image("custom", uploadFile, fn)


@router.post("/custom/predict_zip", tags=["custom"],
             summary="내가 만든 AI로 분류 (압축파일 통째로)")
async def custom_predict_zip(request: Request, uploadFile: UploadFile = File(...),
                             model: str = Query(..., description="모델 slug")):
    raw = uploadFile.file.read()

    def fn():
        head = _head(model)
        zf, names = _zip_images(raw)
        items = []
        for n in names:
            try:
                probs = head.predict(_embed(_decode(zf.read(n)), head.kind))
            except Exception:
                continue
            k = int(np.argmax(probs))
            items.append({"file": n, "name": head.labels[k],
                          "score": round(float(probs[k]), 4)})
        return items
    return _run("custom_predict_zip", fn)


# ---------------------------------------------------------------- 모델 관리
@router.post("/custom/upload", tags=["custom"], summary="학습한 모델 서버에 저장")
async def custom_upload(request: Request, uploadFile: UploadFile = File(...),
                        title: str = Form(...), slug: str = Form(""),
                        overwrite: bool = Form(False)):
    raw = uploadFile.file.read()

    def fn():
        if len(raw) > MAX_ZIP:
            raise ValueError("모델 파일이 너무 큽니다")
        head = Head(raw)                                  # 검증 겸 파싱
        base = _slugify(slug or title)
        os.makedirs(USER_DIR, exist_ok=True)
        s = base if overwrite else _uniq_slug(USER_DIR, base)
        d = os.path.join(USER_DIR, s)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "model.zip"), "wb") as f:
            f.write(raw)
        meta = {"slug": s, "title": title.strip(), "labels": head.labels,
                "classes": len(head.labels), "kind": head.kind, "dim": head.dim,
                "size": len(raw), "created": time.strftime("%Y-%m-%d %H:%M:%S"),
                "report": head.report}
        with open(os.path.join(d, "meta.json"), "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        with _lock:
            _heads[s] = head
        return meta
    return _run("custom_upload", fn)


@router.get("/custom/models", tags=["custom"], summary="내가 만든 AI 목록")
async def custom_models(request: Request):
    def fn():
        os.makedirs(USER_DIR, exist_ok=True)
        items = []
        for s in sorted(os.listdir(USER_DIR)):
            p = os.path.join(USER_DIR, s, "meta.json")
            if os.path.exists(p):
                try:
                    with open(p, encoding="utf-8") as f:
                        items.append(json.load(f))
                except Exception:
                    pass
        return items
    return _run("custom_models", fn)


@router.delete("/custom/models/{slug}", tags=["custom"], summary="내가 만든 AI 삭제")
async def custom_delete(request: Request, slug: str):
    def fn():
        s = _slugify(slug)
        d = os.path.join(USER_DIR, s)
        if not os.path.isdir(d):
            raise ValueError(f"모델을 찾을 수 없습니다: {slug}")
        shutil.rmtree(d)
        with _lock:
            _heads.pop(s, None)
        return {"slug": s, "deleted": True}
    return _run("custom_delete", fn)


# ---------------------------------------------------------------- 작품(작업 중인 내용)
@router.post("/custom/project/save", tags=["custom"], summary="작품 저장 (사진 포함)")
async def project_save(request: Request, uploadFile: UploadFile = File(...),
                       title: str = Form(...), slug: str = Form("")):
    """클래스·사진·특징을 담은 zip 을 그대로 보관한다 (다음 시간에 이어서 하기)."""
    raw = uploadFile.file.read()

    def fn():
        if len(raw) > MAX_ZIP:
            raise ValueError("작품 파일이 너무 큽니다")
        zipfile.ZipFile(io.BytesIO(raw))                  # 열리는지만 확인
        os.makedirs(PROJECT_DIR, exist_ok=True)
        base = _slugify(slug or title)
        s = base if slug else _uniq_slug(PROJECT_DIR, base)
        with open(os.path.join(PROJECT_DIR, s + ".zip"), "wb") as f:
            f.write(raw)
        meta = {"slug": s, "title": title.strip(), "size": len(raw),
                "saved": time.strftime("%Y-%m-%d %H:%M:%S")}
        with open(os.path.join(PROJECT_DIR, s + ".json"), "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        return meta
    return _run("project_save", fn)


@router.get("/custom/projects", tags=["custom"], summary="작품 목록")
async def project_list(request: Request):
    def fn():
        os.makedirs(PROJECT_DIR, exist_ok=True)
        items = []
        for n in sorted(os.listdir(PROJECT_DIR)):
            if not n.endswith(".json"):
                continue
            try:
                with open(os.path.join(PROJECT_DIR, n), encoding="utf-8") as f:
                    items.append(json.load(f))
            except Exception:
                pass
        return items
    return _run("project_list", fn)


@router.get("/custom/project/{slug}", tags=["custom"], summary="작품 내려받기")
async def project_get(request: Request, slug: str):
    p = os.path.join(PROJECT_DIR, _slugify(slug) + ".zip")
    if not os.path.exists(p):
        return {"type": "project_get", "result": "fail",
                "data": f"작품을 찾을 수 없습니다: {slug}", "elapsed_ms": 0}
    return FileResponse(p, media_type="application/zip",
                        filename=_slugify(slug) + ".zip")


@router.delete("/custom/project/{slug}", tags=["custom"], summary="작품 삭제")
async def project_delete(request: Request, slug: str):
    def fn():
        s = _slugify(slug)
        hit = False
        for ext in (".zip", ".json"):
            p = os.path.join(PROJECT_DIR, s + ext)
            if os.path.exists(p):
                os.remove(p)
                hit = True
        if not hit:
            raise ValueError(f"작품을 찾을 수 없습니다: {slug}")
        return {"slug": s, "deleted": True}
    return _run("project_delete", fn)


# ---------------------------------------------------------------- 학습 기록 (성적표)
@router.post("/custom/report", tags=["custom"], summary="학습 성적표 기록 (학습 직후 자동)")
async def report_add(request: Request, body: dict = Body(...)):
    """train.html 이 학습을 마칠 때마다 보낸다 — 모델을 저장하지 않아도 도표에 남는다."""
    def fn():
        rep = body.get("report") or {}
        if not isinstance(rep.get("classes"), list):
            raise ValueError("report.classes 가 필요합니다")
        item = {"title": str(body.get("title", ""))[:60], "report": rep,
                "at": time.strftime("%Y-%m-%d %H:%M:%S")}
        os.makedirs(os.path.dirname(REPORTS_PATH), exist_ok=True)
        with _lock:
            try:
                with open(REPORTS_PATH, encoding="utf-8") as f:
                    items = json.load(f)
            except Exception:
                items = []
            items.append(item)
            items = items[-100:]                       # 최근 100회만 보관
            with open(REPORTS_PATH, "w", encoding="utf-8") as f:
                json.dump(items, f, ensure_ascii=False, indent=1)
        return {"count": len(items)}
    return _run("custom_report", fn)


@router.get("/custom/reports", tags=["custom"], summary="학습 성적표 목록")
async def report_list(request: Request):
    def fn():
        try:
            with open(REPORTS_PATH, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return _run("custom_reports", fn)


# ---------------------------------------------------------------- 교사용
@router.delete("/custom/models", tags=["custom"], summary="[교사] 학생 결과물 전체 삭제")
async def custom_clear_all(request: Request,
                           confirm: str = Query("", description="'yes' 를 보내야 실행")):
    def fn():
        if confirm != "yes":
            raise ValueError("confirm=yes 가 필요합니다")
        n = 0
        for root in (USER_DIR, PROJECT_DIR):
            if os.path.isdir(root):
                n += len(os.listdir(root))
                shutil.rmtree(root)
            os.makedirs(root, exist_ok=True)
        if os.path.exists(REPORTS_PATH):
            os.remove(REPORTS_PATH)
        with _lock:
            _heads.clear()
        return {"cleared": n}
    return _run("custom_clear_all", fn)


@router.get("/custom/export", tags=["custom"], summary="[교사] 학생 결과물 전체 내려받기")
async def custom_export(request: Request):
    os.makedirs(IMAGE_DIR, exist_ok=True)
    out = os.path.join(IMAGE_DIR, "vapi-class-" + time.strftime("%Y%m%d-%H%M%S") + ".zip")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for root in (USER_DIR, PROJECT_DIR):
            for dirpath, _, files in os.walk(root):
                for fn_ in files:
                    p = os.path.join(dirpath, fn_)
                    z.write(p, os.path.relpath(p, "models"))
        try:                                       # 사용 통계도 함께 (초기화 전 보관용)
            import stats_routes
            sp = stats_routes.snapshot_path()
            if os.path.exists(sp):
                z.write(sp, os.path.relpath(sp, "models"))
        except Exception:
            pass
    return FileResponse(out, media_type="application/zip", filename=os.path.basename(out))


# ---------------------------------------------------------------- 점검 / 정보
@router.get("/custom/backbone", tags=["custom"], summary="백본 정보 (전처리 규약 확인용)")
async def custom_backbone(request: Request):
    def fn():
        _load()
        return {"dim": IMAGE_DIM, "input": [1, SIZE, SIZE, 3], "device": _device,
                "preprocess": _meta.get("preprocess", {}),
                "feature_layer": _meta.get("feature_layer", "global_average_pooling2d_1")}
    return _run("custom_backbone", fn)


@router.get("/custom/selftest", tags=["custom"], summary="수업 전 점검")
async def custom_selftest(request: Request):
    """수업 시작 전에 준비 상태를 한 번에 확인한다 (모델·디바이스·저장 폴더·포즈)."""
    def fn():
        checks = []

        def add(key, ok, detail=""):
            checks.append({"key": key, "ok": bool(ok), "detail": str(detail)})

        # 1. 백본
        try:
            _load()
            probe = np.zeros((240, 320, 3), dtype=np.uint8)
            t0 = time.perf_counter()
            v = _embed_image(probe)
            ms = int((time.perf_counter() - t0) * 1000)
            add("backbone", len(v) == IMAGE_DIM, f"{_device} · {ms}ms · {len(v)}d")
        except Exception as ex:
            add("backbone", False, ex)

        # 2. 포즈(MediaPipe)
        try:
            import mp_routes
            mp_routes._load()
            add("pose", True, "gesture_recognizer ready")
        except Exception as ex:
            add("pose", False, ex)

        # 3. 저장 폴더 쓰기 권한
        for root in (USER_DIR, PROJECT_DIR, IMAGE_DIR):
            try:
                os.makedirs(root, exist_ok=True)
                p = os.path.join(root, ".write_test")
                with open(p, "w") as f:
                    f.write("ok")
                os.remove(p)
                add("write:" + root, True, "")
            except Exception as ex:
                add("write:" + root, False, ex)

        # 4. 저장된 결과물
        n_models = len(os.listdir(USER_DIR)) if os.path.isdir(USER_DIR) else 0
        n_proj = len([f for f in os.listdir(PROJECT_DIR)
                      if f.endswith(".zip")]) if os.path.isdir(PROJECT_DIR) else 0
        add("storage", True, f"models={n_models} projects={n_proj}")

        return {"ok": all(c["ok"] for c in checks), "checks": checks, "device": _device}
    return _run("custom_selftest", fn)
