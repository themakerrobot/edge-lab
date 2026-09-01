# -*- coding: utf-8 -*-
# edge-lab : MediaPipe 확장 라우터 (얼굴 메시=거리/방향, 손동작)
# 기존 파일을 건드리지 않는 독립 모듈 — main.py에 두 줄만 추가해 연결한다:
#   import mp_routes
#   app.include_router(mp_routes.router)
#
# 모델 파일(셋업 시 1회 다운로드, 이후 오프라인):
#   models/mediapipe/face_landmarker.task
#   models/mediapipe/gesture_recognizer.task
import json
import os
import threading
import time
import uuid

import cv2
from fastapi import APIRouter, File, Request, UploadFile

import hub

router = APIRouter()

MP_DIR = "models/mediapipe"
CALIB_PATH = os.path.join(MP_DIR, "calib.json")
from paths import TMP_DIR  # noqa: E402
IMAGE_DIR = TMP_DIR + os.sep
IRIS_MM = 11.7                      # 사람 홍채 실지름(거의 일정)
PROC_W = 640                        # 처리 해상도 고정 (f_px 일관성)

_lock = threading.Lock()
_face = None
_hand = None

GESTURE_KO = {
    "Thumb_Up": "엄지척", "Thumb_Down": "엄지아래", "Victory": "브이",
    "Open_Palm": "손바닥", "Closed_Fist": "주먹", "Pointing_Up": "검지위",
    "ILoveYou": "사랑해", "None": "없음",
}


def _load():
    """첫 호출 때 MediaPipe 태스크 로딩 (CPU)."""
    global _face, _hand
    if _face is not None:
        return
    import mediapipe as mp
    from mediapipe.tasks import python as mp_python
    from mediapipe.tasks.python import vision

    fpath = os.path.join(MP_DIR, "face_landmarker.task")
    hpath = os.path.join(MP_DIR, "gesture_recognizer.task")
    for p in (fpath, hpath):
        if not os.path.exists(p):
            raise RuntimeError(f"MediaPipe 모델이 없습니다: {p} (setup의 mediapipe 단계를 실행하세요)")
    _face = vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(
        base_options=mp_python.BaseOptions(model_asset_path=fpath), num_faces=2))
    _hand = vision.GestureRecognizer.create_from_options(vision.GestureRecognizerOptions(
        base_options=mp_python.BaseOptions(model_asset_path=hpath), num_hands=2))
    print("[mp] face_landmarker / gesture_recognizer loaded (CPU)")


def _mp_image(bgr):
    import mediapipe as mp
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    return mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)


def _read_640(path):
    """추론용 640폭 이미지와, 원본 좌표 복원을 위한 배율을 함께 반환."""
    img = cv2.imread(path)
    if img is None:
        raise ValueError("invalid image")
    h, w = img.shape[:2]
    if w != PROC_W:                                   # 처리 해상도 고정 (f_px 일관성)
        img = cv2.resize(img, (PROC_W, int(h * PROC_W / w)))
    return img, w / img.shape[1]                      # scale: 추론좌표 → 원본좌표


def _rescale(data, scale):
    """box/points 좌표를 추론(640) 기준에서 원본 이미지 기준으로 되돌린다."""
    if scale == 1 or not isinstance(data, list):
        return data
    for item in data:
        if isinstance(item, dict):
            if "box" in item:
                item["box"] = [int(v * scale) for v in item["box"]]
            if "points" in item:
                item["points"] = [(int(x * scale), int(y * scale))
                                  for x, y in item["points"]]
    return data


def _f_px(width):
    """models/mediapipe/calib.json 이 있으면 그 f_px 를 쓰고, 없으면 일반 웹캠
    화각(약 70°) 기본값. 화면에서 캘리브레이션하는 경로는 쓰는 곳이 없어 뺐다 —
    필요하면 {"f_px": 값} 파일을 손으로 두면 그대로 읽는다."""
    try:
        with open(CALIB_PATH, encoding="utf-8") as f:
            return float(json.load(f)["f_px"])
    except Exception:
        return 0.714 * width


def _iris_px(lms, w, h):
    """양쪽 홍채 링(468~472 / 473~477)의 지름 픽셀 — 평균으로 노이즈 완화."""
    def diameter(idxs):
        xs = [lms[i].x * w for i in idxs]
        ys = [lms[i].y * h for i in idxs]
        return max(max(xs) - min(xs), max(ys) - min(ys))
    d1 = diameter([469, 470, 471, 472])
    d2 = diameter([474, 475, 476, 477])
    vals = [d for d in (d1, d2) if d > 0]
    return sum(vals) / len(vals) if vals else 0


def _mesh_boxes(bgr):
    """MediaPipe 얼굴 메시로 홍채 지름을 잰다 — 거리 계산에만 쓴다.
    돌려주는 것: [(박스, 홍채픽셀), ...]"""
    h, w = bgr.shape[:2]
    with _lock:
        res = _face.detect(_mp_image(bgr))
    out = []
    if not (res and res.face_landmarks):
        return out
    for lms in res.face_landmarks:
        xs = [p.x * w for p in lms]
        ys = [p.y * h for p in lms]
        box = [int(max(0, min(xs))), int(max(0, min(ys))),
               int(min(w, max(xs))), int(min(h, max(ys)))]
        out.append((box, _iris_px(lms, w, h)))
    return out


def _center_in(box, outer):
    """box 의 가운데가 outer 안에 있으면 같은 얼굴로 본다."""
    cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    return outer[0] <= cx <= outer[2] and outer[1] <= cy <= outer[3]


def _face_items(bgr, lang="ko"):
    """얼굴 하나에 대해 거리와 방향을 함께 낸다.

    얼굴 찾기와 방향은 OpenVINO 얼굴 스위트(NPU)를 쓴다 — 각도를 직접 내는
    모델이라 코끝 위치로 어림하던 것보다 정확하다.
    MediaPipe 는 홍채 지름(거리)만 맡는다. 박스는 OpenVINO 것으로 통일해
    거리·방향·박스가 늘 같은 얼굴을 가리키게 한다."""
    eng = hub.engines()                           # 엔진은 main 이 들고 있다

    h, w = bgr.shape[:2]
    f_px = _f_px(w)
    meshes = _mesh_boxes(bgr)                     # 거리용 (전체 이미지 기준 — f_px 일관성)

    items = []
    for face in eng.face.detect.predict(bgr):
        box = face["box"]
        x1, y1, x2, y2 = box
        pose = eng.face.head_pose.predict(bgr[y1:y2, x1:x2], lang)

        iris = 0
        for mbox, m_iris in meshes:               # 가운데가 겹치는 메시를 짝지어 준다
            if _center_in(mbox, box):
                iris = m_iris
                break
        distance_cm = int(f_px * IRIS_MM / iris / 10) if iris > 0 else 0

        items.append({"box": box, "distance": distance_cm,
                      "direction": pose["direction"],
                      "direction_en": pose["direction_en"],
                      "iris_px": round(iris, 1)})
    return items


def _hand_items(bgr, lang="ko"):
    h, w = bgr.shape[:2]
    with _lock:
        res = _hand.recognize(_mp_image(bgr))
    items = []
    if not res or not res.hand_landmarks:
        return items
    for i, lms in enumerate(res.hand_landmarks):
        xs = [p.x * w for p in lms]
        ys = [p.y * h for p in lms]
        box = [int(max(0, min(xs))), int(max(0, min(ys))),
               int(min(w, max(xs))), int(min(h, max(ys)))]
        gesture, score = "None", 0
        if res.gestures and i < len(res.gestures) and res.gestures[i]:
            g = res.gestures[i][0]
            gesture, score = g.category_name, int(g.score * 100)
        handed = ""
        if res.handedness and i < len(res.handedness) and res.handedness[i]:
            handed = res.handedness[i][0].category_name  # Left / Right
        items.append({
            "gesture": (GESTURE_KO.get(gesture, gesture)
                        if str(lang).startswith("ko") else gesture),
            "gesture_en": gesture,          # MediaPipe 코드 — 값 비교용 (Thumb_Up 등)
            "score": score, "hand": handed, "box": box,
            "points": [(int(p.x * w), int(p.y * h)) for p in lms],
        })
    return items


def _run(name: str, upload: UploadFile, fn):
    """기존 서버와 동일한 {type,result,data,elapsed_ms,device} 응답 포맷."""
    path = IMAGE_DIR + name + "-" + str(uuid.uuid4()) + ".jpg"
    os.makedirs(IMAGE_DIR, exist_ok=True)
    with open(path, "wb") as f:
        f.write(upload.file.read())
    t0 = time.perf_counter()
    try:
        _load()
        img, scale = _read_640(path)
        data = _rescale(fn(img), scale)
        return {"type": name, "result": "ok", "data": data,
                "elapsed_ms": int((time.perf_counter() - t0) * 1000), "device": "CPU"}
    except Exception as ex:
        import traceback
        traceback.print_exc()
        return {"type": name, "result": "fail", "data": "Inference error:" + str(ex),
                "elapsed_ms": int((time.perf_counter() - t0) * 1000)}
    finally:
        if os.path.exists(path):
            os.remove(path)


@router.post("/face/mesh", tags=["face"], summary="얼굴 거리/방향 (MediaPipe)")
async def face_mesh(request: Request, uploadFile: UploadFile = File(...),
                    lang: str = "ko"):
    return _run("mesh", uploadFile, lambda img: _face_items(img, lang))


@router.post("/object/hand", tags=["object"], summary="손동작 인식 (MediaPipe)")
async def object_hand(request: Request, uploadFile: UploadFile = File(...),
                      lang: str = "ko"):
    return _run("hand", uploadFile, lambda img: _hand_items(img, lang))


