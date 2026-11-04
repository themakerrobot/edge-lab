# -*- coding: utf-8 -*-
# edge-lab : "나만의 AI 만들기" 라우터 — 특징은 서버가 뽑고, 머리(분류기)는 브라우저 TF.js 가 학습한다
#
# 261104 부터 **로봇(파이보·PiBrain)과 같은 계산·같은 파일 형식**이다(로봇 연동 일원화).
#   특징  teachlab/ (로봇 openpibo/modules/teachlab 과 같은 코드·같은 모델 파일)
#         image   mobilenet_v3_small 1024 (L2)            — teachlab/models/mobilenet_v3_small_embedder.onnx, OpenVINO f32
#         pose    손 21점 world 좌표 63 (손목 원점·중지 MCP 길이)   — MediaPipe hand_landmarker
#         hand2   두 손 126 (왼손 63 + 오른손 63, 없는 손은 0)
#         face    표정 blendshape 52                       — MediaPipe face_landmarker
#         body_up 상반신 25점 world 좌표 75 (어깨 원점·어깨 너비) — MediaPipe pose_landmarker_lite
#         body    전신 33점 world 좌표 99 (엉덩이 원점·몸통 길이)
#         사진은 로봇처럼 짧은 변 240 으로 줄인 뒤 뽑는다(_stream_rgb — 로봇 vision_classify._as_stream_rgb 와 같다)
#   저장  data/user/<slug>/model.zip 안에 로봇 형식 그대로:
#         project.json · classifier.json · classifier.bin · labels.txt · samples.json (+ report.json)
#         → [로봇으로 보내기] 가 이 파일들을 로봇 분류기(50010) POST /api/models 로 보낸다
#
# 예전 모델(TF.js zip: model.json · weightsSpecs.json · weights.bin · kind.txt)도 계속 읽는다 —
# 그 모델은 예전 특징(MobileNetV2 1280 · 화면 좌표 손 63 · easydetect 몸 22/34)으로 추론한다(_legacy_*).
#
# 모델 파일:
#   teachlab/models/*                                       (리포에 들어 있다 — 로봇과 같은 파일)
#   models/backbone/mobilenetv2_feat.xml / .bin / .json     (예전 모델을 쓸 때만, HF 에서 배포)
#   data/user/<slug>/model.zip + meta.json                  (학생이 만든 AI)
#   data/project/<slug>.zip                                 (작업 중인 작품 — 사진 포함)
import io
import ipaddress
import json
import os
import re
import shutil
import socket
import threading
import time
import sysinfo                    # 이 컴퓨터 상태 (메모리·CPU)
import urllib.error
import urllib.request
import uuid
import zipfile
from typing import List

import cv2
import numpy as np

import hub
import teachlab
from fastapi import APIRouter, Body, File, Form, Query, Request, UploadFile
from fastapi.responses import FileResponse

router = APIRouter()

BACKBONE_XML = "models/backbone/mobilenetv2_feat.xml"     # 예전 모델 전용
from paths import (USER_DIR, PROJECT_DIR, PYCODE_DIR, REPORTS_PATH,   # noqa: E402
                   TMP_DIR)
import trash                                                        # noqa: E402  (지운 AI·작품은 휴지통으로)
IMAGE_DIR = TMP_DIR + os.sep

# 가르치기 종류(화면의 kind) → teach-lab (source, variant). 로봇 project.json 의 source/variant 와 같은 값
KINDS = {
    "image": ("image", None),
    "pose": ("hand", "one"),
    "hand2": ("hand", "two"),
    "face": ("face", None),
    "body_up": ("pose", "upper"),
    "body": ("pose", "full"),
}
KIND_OF = {v: k for k, v in KINDS.items()}
DIM_OF = {"image": 1024, "pose": 63, "hand2": 126, "face": 52, "body_up": 75, "body": 99}
STREAM_SHORT_SIDE = 240             # 로봇 분류기가 추론 전에 줄이는 짧은 변(vision_classify.STREAM_SHORT_SIDE)

# 예전 모델(TF.js zip)의 특징 차원
LEGACY_DIM = {"image": 1280, "pose": 63, "face": 52, "body_up": 22, "body": 34}
KP_CONF = 0.3                       # 예전 몸 특징: 이 값보다 흐린 관절은 "안 보임"
SIZE = 224
MAX_ZIP = 128 * 1024 * 1024         # 업로드 zip 상한
MAX_IMAGES = 600                    # zip 1회 처리 상한
MAX_BATCH = 64                      # 배치 임베딩 1회 장수
DEVICE_ORDER = ["NPU", "GPU", "CPU"]  # 예전 백본: 가벼운 모델이라 NPU 우선
ROBOT_PORT = 50010                  # 로봇 분류기 서비스(파이보·PiBrain 같음)

_lock = threading.Lock()
_compiled = None                    # 사진 임베더(teachlab.embedder.ImageEmbedder) — main.py 상태표가 본다
_device = "CPU"                     # 임베더는 f32 로 맞추려고 CPU 에서 돈다
_extractors = {}                    # (source, variant) -> LandmarkExtractor
_ext_lock = threading.Lock()
_heads = {}                         # slug -> Head (캐시)

_legacy = {"core": None, "compiled": None, "out": None, "device": "CPU", "meta": {}}
_DT = {"float32": np.float32, "int32": np.int32, "uint8": np.uint8, "bool": np.bool_}


class SoftError(ValueError):
    """사용자에게 그대로 보여줄 예상된 실패 (손 없음 등) — 트레이스백을 찍지 않는다."""


# ---------------------------------------------------------------- 특징 (로봇과 같은 계산)
def _stream_rgb(bgr):
    """BGR → RGB, 짧은 변 240 으로 줄인다(작으면 그대로). 로봇 vision_classify._as_stream_rgb 와 같은 식이다."""
    if bgr.ndim == 2:
        bgr = cv2.cvtColor(bgr, cv2.COLOR_GRAY2BGR)
    elif bgr.shape[2] == 4:
        bgr = cv2.cvtColor(bgr, cv2.COLOR_BGRA2BGR)
    h, w = bgr.shape[:2]
    s = STREAM_SHORT_SIDE / min(h, w)
    if s < 1:
        bgr = cv2.resize(bgr, (int(round(w * s)), int(round(h * s))))
    return np.ascontiguousarray(bgr[:, :, ::-1])


def _load():
    """사진 임베더를 처음 쓸 때 올린다(mobilenet_v3_small ONNX, OpenVINO f32 CPU)."""
    global _compiled
    if _compiled is not None:
        return
    with _lock:
        if _compiled is None:
            from teachlab.embedder import ImageEmbedder
            _compiled = ImageEmbedder(teachlab.EMBEDDER_ONNX)
            print(f"[custom] mobilenet_v3_small embedder loaded (CPU f32, dim={_compiled.dim})")


def _extractor(kind):
    source, variant = KINDS[kind]
    key = (source, variant)
    with _ext_lock:
        ex = _extractors.get(key)
        if ex is None:
            from teachlab.landmarks import LandmarkExtractor
            ex = LandmarkExtractor(source, teachlab.LANDMARK_FILE[source], variant)
            _extractors[key] = ex
            print(f"[custom] {source} landmarker loaded ({variant or '-'})")
        return ex


def _detect(kind, rgb):
    """MediaPipe 결과(화면 표시용). LandmarkExtractor 하나를 특징 뽑기와 같이 쓴다."""
    ex = _extractor(kind)
    with _ext_lock:
        return ex.detect(rgb)


NOT_SEEN = {
    "pose": "손이 보이지 않아요. 손을 화면 안에 보여 주세요.",
    "hand2": "손이 보이지 않아요. 손을 화면 안에 보여 주세요.",
    "face": "얼굴이 보이지 않아요. 얼굴을 화면 안에 보여 주세요.",
    "body_up": "사람이 보이지 않아요. 몸을 화면 안에 보여 주세요.",
    "body": "사람이 보이지 않아요. 온몸이 보이게 뒤로 물러서 주세요.",
}


def _embed(bgr, kind="image"):
    """사진 한 장 → 특징(float32). 로봇 CustomClassifier 와 같은 숫자를 만든다."""
    kind = kind if kind in KINDS else "image"
    rgb = _stream_rgb(bgr)
    if kind == "image":
        _load()
        return _compiled.embed_rgb(rgb)
    ex = _extractor(kind)
    with _ext_lock:
        vec = ex.vector(rgb)
    if vec is None:
        raise SoftError(NOT_SEEN[kind])
    return vec


# ---------------------------------------------------------------- 예전 모델(TF.js zip) 전용 특징
def _legacy_load():
    """예전 백본 IR 로딩 (NPU > GPU > CPU, 실패하면 다음 디바이스로)."""
    L = _legacy
    if L["compiled"] is not None:
        return
    import openvino as ov
    if not os.path.exists(BACKBONE_XML):
        raise RuntimeError(f"예전 모델용 백본이 없습니다: {BACKBONE_XML} (예전 모델은 다시 가르쳐 주세요)")
    L["core"] = ov.Core()
    model = L["core"].read_model(BACKBONE_XML)
    avail = L["core"].available_devices
    last = None
    for dev in DEVICE_ORDER:
        if dev not in avail:
            continue
        try:
            cfg = {"INFERENCE_PRECISION_HINT": "f16"} if dev in ("NPU", "GPU") else {}
            L["compiled"] = L["core"].compile_model(model, dev, cfg)
            L["device"] = dev
            break
        except Exception as ex:                 # NPU 미지원 레이어 등 → 다음 디바이스
            last = ex
            print(f"[custom] {dev} compile failed: {ex}")
    if L["compiled"] is None:
        raise RuntimeError(f"백본을 컴파일할 수 없습니다: {last}")
    L["out"] = L["compiled"].output(0)
    print(f"[custom] (legacy) mobilenetv2_feat loaded ({L['device']}, dim=1280)")


def _legacy_preprocess(bgr):
    """BGR ndarray -> (1,224,224,3) float32.  TF.js resizeNearestNeighbor 동일 구현."""
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    h, w = rgb.shape[:2]
    ar = np.arange(SIZE, dtype=np.float32)
    yi = np.floor(ar * (np.float32(h) / np.float32(SIZE))).astype(np.int32).clip(0, h - 1)
    xi = np.floor(ar * (np.float32(w) / np.float32(SIZE))).astype(np.int32).clip(0, w - 1)
    return (rgb[yi][:, xi].astype(np.float32) / 255.0)[None, ...]


def _legacy_embed_image(bgr):
    _legacy_load()
    L = _legacy
    x = _legacy_preprocess(bgr)
    with _lock:
        return L["compiled"](x)[L["out"]].reshape(-1)          # (1280,)


def _hand_landmarks(bgr):
    """손 랜드마크 21점(화면 표시·예전 모델용). 없으면 None. (norm=0~1 화면좌표, px=픽셀좌표)"""
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
    hands = [[[round(float(p.x), 4), round(float(p.y), 4)] for p in hl] for hl in res.hand_landmarks]
    return {"norm": norm, "px": px, "handed": handed, "gesture": gesture, "hands": hands}


def _legacy_embed_pose(bgr):
    """예전 손 특징 — 화면 좌표 21점, 손목 원점·최대 거리로 나눔(63)."""
    hand = _hand_landmarks(bgr)
    if hand is None:
        raise SoftError(NOT_SEEN["pose"])
    pts = hand["px"].copy()
    pts -= pts[0]
    scale = float(np.linalg.norm(pts, axis=1).max())
    if scale > 0:
        pts /= scale
    return pts.reshape(-1)


# 예전 몸 특징: easydetect COCO 17점
LEGACY_UPPER_N = 11


def _body_keypoints(bgr):
    """가장 크게 잡힌 사람 한 명의 관절 17개 [(x, y, conf)]. 없으면 None (예전 모델용)."""
    eng = hub.engines(required=False)
    if eng is None:
        raise SoftError("AI를 준비하는 중이에요. 조금만 기다려 주세요.")
    r = eng.object.pose(bgr)[0]
    if r.keypoints is None or r.boxes is None or len(r.boxes) == 0:
        return None
    b = np.asarray(r.boxes.xyxy)
    i = int(np.argmax((b[:, 2] - b[:, 0]) * (b[:, 3] - b[:, 1])))
    xy = np.asarray(r.keypoints.xy[i])
    cf = np.asarray(r.keypoints.conf[i]) if r.keypoints.conf is not None else np.ones(len(xy), dtype=np.float32)
    return [(float(p[0]), float(p[1]), float(c)) for p, c in zip(xy, cf)]


def _legacy_embed_body(bgr, full):
    kp = _body_keypoints(bgr)
    if kp is None:
        raise SoftError(NOT_SEEN["body" if full else "body_up"])
    need = [5, 6, 11, 12] if full else [5, 6]
    if any(kp[i][2] < KP_CONF for i in need):
        raise SoftError("전신이 다 보이지 않아요. 뒤로 조금 물러서 주세요." if full
                        else "어깨가 보이지 않아요. 몸을 화면 안에 보여 주세요.")
    mid = lambda a, b: ((kp[a][0] + kp[b][0]) / 2, (kp[a][1] + kp[b][1]) / 2)
    sh = mid(5, 6)
    if full:
        hip = mid(11, 12)
        origin = hip
        scale = float(np.hypot(sh[0] - hip[0], sh[1] - hip[1]))
        idx = range(17)
    else:
        origin = sh
        scale = float(np.hypot(kp[5][0] - kp[6][0], kp[5][1] - kp[6][1]))
        idx = range(LEGACY_UPPER_N)
    if scale < 1e-3:
        raise SoftError("사람이 너무 작게 보여요. 조금 앞으로 와 주세요.")
    out = []
    for i in idx:
        x, y, c = kp[i]
        if c < KP_CONF:
            out += [0.0, 0.0]
        else:
            out += [(x - origin[0]) / scale, (y - origin[1]) / scale]
    return np.array(out, dtype=np.float32)


def _legacy_embed(bgr, kind="image"):
    if kind == "body_up":
        return _legacy_embed_body(bgr, False)
    if kind == "body":
        return _legacy_embed_body(bgr, True)
    if kind == "pose":
        return _legacy_embed_pose(bgr)
    if kind == "face":
        return _embed(bgr, "face")          # 표정은 예전·지금 모두 blendshape 52 — 같은 계산
    return _legacy_embed_image(bgr)


# ---------------------------------------------------------------- 화면 표시용 묶음
# 얼굴선(MediaPipe 표준 인덱스)
FACE_CONTOURS = {
    "oval": [10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288, 397, 365,
             379, 378, 400, 377, 152, 148, 176, 149, 150, 136, 172, 58, 132, 93,
             234, 127, 162, 21, 54, 103, 67, 109, 10],
    "eyeL": [33, 246, 161, 160, 159, 158, 157, 173, 133, 155, 154, 153, 145, 144, 163, 7, 33],
    "eyeR": [263, 466, 388, 387, 386, 385, 384, 398, 362, 382, 381, 380, 374, 373, 390, 249, 263],
    "browL": [70, 63, 105, 66, 107],
    "browR": [300, 293, 334, 296, 336],
    "lips": [61, 185, 40, 39, 37, 0, 267, 269, 270, 409, 291, 375, 321, 405, 314,
             17, 84, 181, 91, 146, 61],
}
# MediaPipe 자세 33점 뼈대 (로봇 vision_classify.POSE_EDGES 와 같다). 상반신은 0~24번만
POSE_EDGES = [(0, 1), (1, 2), (2, 3), (3, 7), (0, 4), (4, 5), (5, 6), (6, 8), (9, 10), (11, 12), (11, 13), (13, 15),
              (15, 17), (15, 19), (15, 21), (17, 19), (12, 14), (14, 16), (16, 18), (16, 20), (16, 22), (18, 20),
              (11, 23), (12, 24), (23, 24), (23, 25), (24, 26), (25, 27), (26, 28), (27, 29), (28, 30), (29, 31),
              (30, 32), (27, 31), (28, 32)]
UPPER_N = 25


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
class TeachHead:
    """로봇 형식 zip — project.json · classifier.json · classifier.bin · labels.txt (+ samples.json · report.json).

    분류기는 로봇과 같은 teachlab.classifier.Classifier (Dense relu → Dense softmax, numpy).
    """
    legacy = False

    def __init__(self, zf, names):
        from teachlab.classifier import Classifier
        for req in ("project.json", "classifier.json", "classifier.bin"):
            if req not in names:
                raise ValueError(f"zip에 {req} 이(가) 없습니다")
        self.project = json.loads(zf.read("project.json").decode("utf-8"))
        spec = json.loads(zf.read("classifier.json").decode("utf-8"))
        self.clf = Classifier(spec, zf.read("classifier.bin"))
        self.labels = list(self.clf.classes)
        src = self.project.get("source") or "image"
        var = self.project.get("variant")
        self.kind = KIND_OF.get((src, var if src != "image" else None))
        if self.kind is None:
            raise ValueError(f"이 특징은 아직 쓸 수 없어요: {src}/{var}")
        self.dim = self.clf.input_dim
        if self.dim != DIM_OF[self.kind]:
            raise ValueError(f"입력 차원 불일치: {self.dim} (기대 {DIM_OF[self.kind]})")
        self.report = None
        if "report.json" in names:
            try:
                self.report = json.loads(zf.read("report.json").decode("utf-8"))
            except Exception:
                self.report = None
        self.has_samples = "samples.json" in names

    def features(self, bgr):
        return _embed(bgr, self.kind)

    def predict(self, feat):
        return self.clf.predict_proba(feat)


class LegacyHead:
    """예전(261104 전) 브라우저 TF.js zip -> numpy 행렬곱 2회. 예전 특징으로 추론한다.

    zip 구조: model.json / weightsSpecs.json / weights.bin / labels.txt [+ kind.txt]
    구조    : Dense(D->128, relu) -> Dropout(추론시 항등) -> Dense(128->N, softmax)
    """
    legacy = True
    project = None
    has_samples = False

    def __init__(self, zf, names):
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
            if k in LEGACY_DIM:
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
        if self.dim != LEGACY_DIM[self.kind]:
            raise ValueError(f"입력 차원 불일치: {self.dim} (기대 {LEGACY_DIM[self.kind]})")
        if self.W2.shape[1] != len(self.labels):
            raise ValueError(f"클래스 수 불일치: 가중치 {self.W2.shape[1]} / labels {len(self.labels)}")

    def features(self, bgr):
        return _legacy_embed(bgr, self.kind)

    def predict(self, feat):
        h = feat @ self.W1 + self.b1
        np.maximum(h, 0, out=h)
        z = h @ self.W2 + self.b2
        z = z - z.max()
        e = np.exp(z)
        return e / e.sum()


def Head(zip_bytes):
    """zip 을 열어 형식에 맞는 머리를 돌려준다 — classifier.json 이 있으면 로봇 형식, 아니면 예전 TF.js"""
    zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    names = set(zf.namelist())
    if "classifier.json" in names:
        return TeachHead(zf, names)
    return LegacyHead(zf, names)


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
def _dev_for(kind, legacy=False):
    """그 작업을 실제로 처리한 장치(화면 상태바의 exec 표시).

    로봇과 같은 계산(지금)은 전부 CPU 다 — 사진 임베더도 숫자를 맞추려고 f32 CPU 로 돈다.
    예전 모델만 백본이 NPU/GPU, 몸은 easydetect 장치다.
    """
    if not legacy:
        return "CPU"
    if kind in ("body", "body_up"):
        return hub.device_of("object_pose", "CPU")
    if kind == "image":
        return _legacy["device"]
    return "CPU"


def _run(name, fn, device=None):
    """기존 서버와 동일한 {type,result,data,elapsed_ms,device} 응답 포맷."""
    t0 = time.perf_counter()
    try:
        data = fn()
        return {"type": name, "result": "ok", "data": data,
                "elapsed_ms": int((time.perf_counter() - t0) * 1000),
                "device": device or _device}
    except SoftError as ex:
        return {"type": name, "result": "fail", "data": str(ex),
                "elapsed_ms": int((time.perf_counter() - t0) * 1000),
                "device": device or _device}
    except Exception as ex:
        import traceback
        traceback.print_exc()
        return {"type": name, "result": "fail", "data": "Inference error:" + str(ex),
                "elapsed_ms": int((time.perf_counter() - t0) * 1000),
                "device": device or _device}


def _run_image(name, upload, fn, device=None):
    """웹캠 캡쳐 1장 업로드 — mp_routes 와 동일한 임시파일 방식."""
    os.makedirs(IMAGE_DIR, exist_ok=True)
    path = IMAGE_DIR + name + "-" + str(uuid.uuid4()) + ".jpg"
    with open(path, "wb") as f:
        f.write(upload.file.read())
    try:
        return _run(name, lambda: fn(_imread(path)), device=device)
    finally:
        if os.path.exists(path):
            os.remove(path)


# ---------------------------------------------------------------- 특징 추출
@router.post("/custom/embed", tags=["custom"], summary="특징 추출 (캡쳐 1장)")
async def custom_embed(request: Request, uploadFile: UploadFile = File(...),
                       kind: str = Query("image", description="image | pose | face | body_up | body")):
    def fn(bgr):
        v = _embed(bgr, kind)
        return {"kind": kind, "dim": len(v),
                "feature": [round(float(x), 6) for x in v]}
    return _run_image("custom_embed", uploadFile, fn, device=_dev_for(kind))


@router.post("/custom/pose", tags=["custom"], summary="손 랜드마크 (화면 표시용)")
async def custom_pose(request: Request, uploadFile: UploadFile = File(...)):
    """손이 없어도 실패로 보지 않는다 — 학습 화면에서 초당 수십 번 호출되는 용도.

    디스크 임시파일을 쓰지 않고 메모리에서 바로 디코드한다.
    """
    raw = uploadFile.file.read()

    def fn():
        hand = _hand_landmarks(_decode(raw))
        if hand is None:
            return {"found": False, "points": [], "hands": []}
        return {"found": True, "points": hand["norm"], "hands": hand["hands"],
                "hand": hand["handed"], "gesture": hand["gesture"]}
    return _run("custom_pose", fn, device="CPU")


@router.post("/custom/face", tags=["custom"], summary="얼굴선 + 표정 값 (화면 표시용)")
async def custom_face(request: Request, uploadFile: UploadFile = File(...)):
    """얼굴이 없어도 실패로 보지 않는다 — 학습 화면에서 계속 호출하는 용도."""
    raw = uploadFile.file.read()

    def fn():
        res = _detect("face", _stream_rgb(_decode(raw)))
        if not res or not res.face_blendshapes or not res.face_landmarks:
            return {"found": False, "lines": [], "top": []}
        lm = res.face_landmarks[0]
        lines = [[[round(lm[i].x, 4), round(lm[i].y, 4)] for i in idx if i < len(lm)]
                 for idx in FACE_CONTOURS.values()]
        bs = sorted(res.face_blendshapes[0], key=lambda c: -c.score)[:3]
        top = [{"name": c.category_name, "score": round(float(c.score), 3)}
               for c in bs if c.score > 0.15]
        return {"found": True, "lines": lines, "top": top}
    return _run("custom_face", fn, device="CPU")


@router.post("/custom/body", tags=["custom"], summary="몸 관절 (화면 표시용)")
async def custom_body(request: Request, uploadFile: UploadFile = File(...),
                      kind: str = Query("body", description="body | body_up")):
    """사람이 없어도 실패로 보지 않는다 — 학습 화면에서 계속 호출하는 용도."""
    raw = uploadFile.file.read()

    def fn():
        k = "body" if kind == "body" else "body_up"
        res = _detect(k, _stream_rgb(_decode(raw)))          # MediaPipe 자세 33점 — 특징 뽑기와 같은 모델
        poses = getattr(res, "pose_landmarks", None) or []
        if not poses:
            return {"found": False, "points": [], "edges": []}
        n = 33 if k == "body" else UPPER_N
        pts = [[round(p.x, 4), round(p.y, 4), round(float(getattr(p, "visibility", 1.0) or 0.0), 2)]
               for p in poses[0][:n]]
        edges = [e for e in POSE_EDGES if e[0] < n and e[1] < n]
        return {"found": True, "points": pts, "edges": edges}
    return _run("custom_body", fn, device="CPU")


@router.post("/custom/embed_batch", tags=["custom"], summary="특징 추출 (여러 장 한 번에)")
async def custom_embed_batch(request: Request, uploadFiles: List[UploadFile] = File(...),
                             kind: str = Query("image", description="image | pose | face | body_up | body")):
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
    return _run("custom_embed_batch", fn, device=_dev_for(kind))


@router.post("/custom/embed_zip", tags=["custom"], summary="특징 추출 (클래스 압축파일 통째로)")
async def custom_embed_zip(request: Request, uploadFile: UploadFile = File(...),
                           label: str = Form(""),
                           kind: str = Query("image", description="image | pose | face | body_up | body")):
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
    return _run("custom_embed_zip", fn, device=_dev_for(kind))


# ---------------------------------------------------------------- 추론
@router.post("/custom/predict", tags=["custom"], summary="내가 만든 AI로 분류 (캡쳐 1장)")
async def custom_predict(request: Request, uploadFile: UploadFile = File(...),
                         model: str = Query(..., description="모델 slug"),
                         top: int = Query(0, description="상위 N개만 (0=전체)")):
    try:
        h0 = _head(model)                           # 캐시되어 있어 비용이 없다
        kind, legacy = h0.kind, h0.legacy
    except Exception:
        kind, legacy = "image", False

    def fn(bgr):
        head = _head(model)
        try:
            probs = head.predict(head.features(bgr))
        except SoftError:
            return []            # 손이 안 보이면 "없음" — 블록 코딩이 멈추지 않게 한다
        order = np.argsort(-probs)
        out = [{"name": head.labels[i], "score": round(float(probs[i]), 4)} for i in order]
        return out[:top] if top > 0 else out
    return _run_image("custom", uploadFile, fn, device=_dev_for(kind, legacy))


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
                "format": "legacy" if head.legacy else "teachlab",   # teachlab = 로봇으로 보낼 수 있다
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


@router.get("/custom/models/{slug}/file", tags=["custom"], summary="내가 만든 AI 내려받기")
async def custom_model_file(request: Request, slug: str):
    """저장한 모델 zip 을 그대로 돌려준다 (가르치기에서 다시 불러올 때 쓴다)."""
    p = os.path.join(USER_DIR, _slugify(slug), "model.zip")
    if not os.path.exists(p):
        return {"type": "custom_model_file", "result": "fail",
                "data": f"모델을 찾을 수 없습니다: {slug}", "elapsed_ms": 0}
    return FileResponse(p, media_type="application/zip",
                        filename=_slugify(slug) + ".zip")


@router.delete("/custom/models/{slug}", tags=["custom"], summary="내가 만든 AI 삭제")
async def custom_delete(request: Request, slug: str):
    def fn():
        s = _slugify(slug)
        d = os.path.join(USER_DIR, s)
        if not os.path.isdir(d):
            raise ValueError(f"모델을 찾을 수 없습니다: {slug}")
        title = s
        try:
            with open(os.path.join(d, "meta.json"), encoding="utf-8") as f:
                title = json.load(f).get("title") or s
        except Exception:
            pass
        trash.put("model", title, [d])        # 바로 없애지 않는다 — 내 작품의 휴지통에서 되살린다
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
        files = [os.path.join(PROJECT_DIR, s + ext) for ext in (".zip", ".json")]
        if not any(os.path.exists(p) for p in files):
            raise ValueError(f"작품을 찾을 수 없습니다: {slug}")
        title = s
        try:
            with open(files[1], encoding="utf-8") as f:
                title = json.load(f).get("title") or s
        except Exception:
            pass
        trash.put("project", title, files)    # 바로 없애지 않는다 — 내 작품의 휴지통에서 되살린다
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
        # data/ 안의 작업 파일만 지운다 — models/(AI 모델)은 건드리지 않는다
        n = 0
        for root in (USER_DIR, PROJECT_DIR, PYCODE_DIR):
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
@router.get("/custom/backbone", tags=["custom"], summary="특징 모델 정보 (전처리 규약 확인용)")
async def custom_backbone(request: Request):
    def fn():
        _load()
        return {"dim": _compiled.dim, "input": [1, SIZE, SIZE, 3], "device": _device,
                "model": "mediapipe/mobilenet_v3_small (teachlab, ONNX)",
                "preprocess": {"stream_short_side": STREAM_SHORT_SIDE, "crop": "tm-crop-to",
                               "scale": "1/255", "l2_normalize": True, "mirror": False},
                "dims": DIM_OF}
    return _run("custom_backbone", fn)


# ---------------------------------------------------------------- 로봇으로 보내기
def _robot_host(host):
    """로봇 주소 검사 — 같은 망(사설 IP·링크 로컬·.local)만 받는다. 'IP' 또는 'IP:포트'."""
    host = (host or "").strip().replace("http://", "").replace("https://", "").strip("/")
    if not host or not re.fullmatch(r"[0-9A-Za-z.\-]+(:\d{1,5})?", host):
        raise SoftError("로봇 주소를 확인해 주세요 (예: 192.168.0.12)")
    name, _, port = host.partition(":")
    try:
        addr = ipaddress.ip_address(socket.gethostbyname(name))
    except (OSError, ValueError):
        raise SoftError(f"로봇을 찾지 못했어요: {name}")
    if not (addr.is_private or addr.is_link_local) or addr.is_loopback:
        raise SoftError("같은 공유기(학교 망) 안의 로봇에만 보낼 수 있어요.")
    return f"{addr}:{int(port) if port else ROBOT_PORT}"


def _multipart(fields, files):
    """urllib 로 보낼 multipart/form-data 본문(fields: {이름: 글}, files: {이름: (파일 이름, 바이트, 형식)})"""
    b = "----edgelab" + uuid.uuid4().hex
    out = io.BytesIO()
    for k, v in fields.items():
        out.write(f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode("utf-8"))
    for k, (fname, data, ctype) in files.items():
        out.write(f'--{b}\r\nContent-Disposition: form-data; name="{k}"; filename="{fname}"\r\n'
                  f'Content-Type: {ctype}\r\n\r\n'.encode("utf-8"))
        out.write(data)
        out.write(b"\r\n")
    out.write(f"--{b}--\r\n".encode("utf-8"))
    return out.getvalue(), "multipart/form-data; boundary=" + b


@router.get("/custom/robot/ping", tags=["custom"], summary="로봇 분류기가 켜져 있는지")
async def robot_ping(request: Request, host: str = Query(...)):
    """로봇 분류기 서비스(50010)의 모델 목록을 물어본다. 로봇 IDE 에서 [분류기] 를 켜 두어야 답한다."""
    def fn():
        h = _robot_host(host)
        try:
            with urllib.request.urlopen(f"http://{h}/api/models", timeout=4) as r:
                j = json.loads(r.read().decode("utf-8"))
        except (urllib.error.URLError, OSError, ValueError):
            raise SoftError("로봇이 답하지 않아요. 로봇 IDE 에서 [분류기] 를 켜 두었는지 확인해 주세요.")
        return {"host": h, "models": [m.get("name") for m in j.get("models", [])]}
    return _run("custom_robot_ping", fn, device="CPU")


@router.post("/custom/robot/send", tags=["custom"], summary="저장한 AI 를 로봇으로 보내기")
async def robot_send(request: Request, body: dict = Body(...)):
    """저장한 모델(로봇 형식)을 로봇 분류기 POST /api/models 로 그대로 보낸다.

    본문: {"slug": 저장한 AI, "host": "192.168.0.12", "name": 로봇에 저장할 이름(없으면 제목), "overwrite": false}
    로봇에 같은 이름이 있으면 data.exists = true 로 돌려준다(화면이 덮어쓸지 묻는다).
    """
    def fn():
        s = _slugify(body.get("slug", ""))
        d = os.path.join(USER_DIR, s)
        p = os.path.join(d, "model.zip")
        if not os.path.exists(p):
            raise SoftError(f"모델을 찾을 수 없습니다: {s}")
        with open(p, "rb") as f:
            zf = zipfile.ZipFile(io.BytesIO(f.read()))
        names = set(zf.namelist())
        if "classifier.json" not in names:
            raise SoftError("예전 방식으로 만든 AI 라 로봇으로 보낼 수 없어요. 다시 가르쳐 저장해 주세요.")
        title = s
        try:
            with open(os.path.join(d, "meta.json"), encoding="utf-8") as f:
                title = json.load(f).get("title") or s
        except Exception:
            pass
        name = (str(body.get("name") or title)).strip()[:40]
        h = _robot_host(body.get("host", ""))
        files = {
            "project": ("project.json", zf.read("project.json"), "application/json"),
            "classifier_json": ("classifier.json", zf.read("classifier.json"), "application/json"),
            "classifier_bin": ("classifier.bin", zf.read("classifier.bin"), "application/octet-stream"),
        }
        if "samples.json" in names:
            files["samples"] = ("samples.json", zf.read("samples.json"), "application/json")
        data, ctype = _multipart({"name": name, "overwrite": "1" if body.get("overwrite") else "0"}, files)
        req = urllib.request.Request(f"http://{h}/api/models", data=data, method="POST",
                                     headers={"Content-Type": ctype})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                j = json.loads(r.read().decode("utf-8") or "{}")
        except urllib.error.HTTPError as ex:
            if ex.code == 409:
                return {"host": h, "name": name, "exists": True}
            try:
                why = json.loads(ex.read().decode("utf-8")).get("error", "")
            except Exception:
                why = ""
            raise SoftError(f"로봇이 받지 않았어요 ({ex.code} {why}).")
        except (urllib.error.URLError, OSError):
            raise SoftError("로봇이 답하지 않아요. 로봇 IDE 에서 [분류기] 를 켜 두었는지 확인해 주세요.")
        saved = (j.get("model") or {}).get("name") or name
        return {"host": h, "name": saved, "exists": False}
    return _run("custom_robot_send", fn, device="CPU")


@router.get("/custom/selftest", tags=["custom"], summary="수업 전 점검")
async def custom_selftest(request: Request):
    """수업 시작 전에 준비 상태를 한 번에 확인한다 (특징 모델·손/얼굴/자세·메모리·저장 폴더)."""
    def fn():
        checks = []

        def add(key, ok, detail=""):
            checks.append({"key": key, "ok": bool(ok), "detail": str(detail)})

        # 1. 사진 특징 (mobilenet_v3_small)
        try:
            _load()
            probe = np.zeros((240, 320, 3), dtype=np.uint8)
            t0 = time.perf_counter()
            v = _embed(probe, "image")
            ms = int((time.perf_counter() - t0) * 1000)
            add("backbone", len(v) == DIM_OF["image"], f"{_device} · {ms}ms · {len(v)}d")
        except Exception as ex:
            add("backbone", False, ex)

        # 2. 손·자세(MediaPipe)
        try:
            _extractor("pose")
            _extractor("body_up")
            add("pose", True, "hand · pose landmarker ready")
        except Exception as ex:
            add("pose", False, ex)

        # 2-2. 표정(블렌드셰이프)
        try:
            _extractor("face")
            add("face", True, "blendshapes ready")
        except Exception as ex:
            add("face", False, ex)

        # 3. 이 컴퓨터 형편 (메모리) — RAM 16GB 를 기준으로 만들었다
        mem = sysinfo._mem_info()
        if mem:
            add("memory", mem["total_gb"] >= 15.0,
                "%s / %s GB 씀 (%s%%)" % (mem["used_gb"], mem["total_gb"], mem["percent"]))
        sysinfo._cpu_percent()                      # 첫 호출은 견줄 값이 없다(차분으로 구함)
        time.sleep(0.2)
        cpu = sysinfo._cpu_percent()
        if cpu is not None:
            add("cpu", cpu < 80, "%s%% 사용 중" % cpu)

        # 4. 저장된 결과물
        n_models = len(os.listdir(USER_DIR)) if os.path.isdir(USER_DIR) else 0
        n_proj = len([f for f in os.listdir(PROJECT_DIR)
                      if f.endswith(".zip")]) if os.path.isdir(PROJECT_DIR) else 0
        add("storage", True, f"models={n_models} projects={n_proj}")

        return {"ok": all(c["ok"] for c in checks), "checks": checks, "device": _device}
    return _run("custom_selftest", fn)
