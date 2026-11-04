# -*- coding: utf-8 -*-
"""손 · 얼굴 · 포즈 → 특징 벡터.

브라우저의 lib/features.js 와 **같은 계산**을 한다. 숫자가 어긋나면 학습한
분류기가 엉뚱한 답을 내므로, 아래 정규화 방법을 바꿀 때는 양쪽을 함께 고쳐야 한다.

  손   world landmarks 21점. 손목(0)을 원점으로 옮기고
       손목~중지MCP(9) 거리로 나눈다 → 63
       두 손 갈래는 왼손 63 + 오른손 63 = 126 (없는 손은 0)
  얼굴 blendshape 52개 점수 그대로 → 52
  포즈 world landmarks. 상반신은 0~24번, 양 어깨(11,12) 중점 원점 ·
       어깨 너비 스케일 → 75. 전신은 33점, 엉덩이(23,24) 중점 원점 ·
       몸통 길이 스케일 → 99

좌표는 **원본 프레임**에서 뽑는다 (좌우를 뒤집지 않는다).
뒤집으면 MediaPipe 의 왼손/오른손 판별이 반대가 되어 학습이 망가진다.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np

from .modelfile import read_model

SOURCES = ("hand", "face", "pose")

DIMS = {
    ("hand", "one"): 63,
    ("hand", "two"): 126,
    ("face", None): 52,
    ("pose", "upper"): 75,
    ("pose", "full"): 99,
}

DEFAULT_VARIANT = {"hand": "one", "face": None, "pose": "upper"}


def dim_of(source: str, variant: str | None) -> int:
    if source == "hand":
        return 126 if variant == "two" else 63
    if source == "pose":
        return 99 if variant == "full" else 75
    if source == "face":
        return 52
    raise ValueError(f"좌표를 뽑을 수 없는 소스예요: {source}")


class LandmarkExtractor:
    """MediaPipe 랜드마커를 감싼다. 한 번 만들어 두고 계속 쓴다."""

    def __init__(self, source: str, model_path: str | Path, variant: str | None = None):
        if source not in SOURCES:
            raise ValueError(f"좌표를 뽑을 수 없는 소스예요: {source}")
        try:
            import mediapipe as mp
            from mediapipe.tasks import python as mp_python
            from mediapipe.tasks.python import vision as mp_vision
        except ImportError as e:                       # pragma: no cover
            raise ImportError(
                "손·얼굴·포즈 모델을 돌리려면 MediaPipe 가 필요해요:\n"
                "    pip install \"teachlab[landmark]\""
            ) from e

        self._mp = mp
        self.source = source
        self.variant = variant or DEFAULT_VARIANT[source]
        self.model_path = Path(model_path)
        self.dim = dim_of(source, self.variant)

        # 경로가 아니라 바이트로 넘긴다 — 한글 경로에서 깨지지 않게
        base = mp_python.BaseOptions(model_asset_buffer=read_model(self.model_path))
        mode = mp_vision.RunningMode.IMAGE
        if source == "hand":
            options = mp_vision.HandLandmarkerOptions(
                base_options=base, running_mode=mode, num_hands=2)
            self._task = mp_vision.HandLandmarker.create_from_options(options)
        elif source == "face":
            options = mp_vision.FaceLandmarkerOptions(
                base_options=base, running_mode=mode, num_faces=1,
                output_face_blendshapes=True)
            self._task = mp_vision.FaceLandmarker.create_from_options(options)
        else:
            options = mp_vision.PoseLandmarkerOptions(
                base_options=base, running_mode=mode, num_poses=1)
            self._task = mp_vision.PoseLandmarker.create_from_options(options)

    # ── 뽑기 ──
    def detect(self, rgb: np.ndarray):
        image = self._mp.Image(image_format=self._mp.ImageFormat.SRGB,
                               data=np.ascontiguousarray(rgb))
        return self._task.detect(image)

    def vector(self, rgb: np.ndarray) -> np.ndarray | None:
        """RGB uint8 배열 → float32 특징 벡터. 아무것도 안 보이면 None."""
        result = self.detect(rgb)
        if self.source == "hand":
            return (_hand_two(result) if self.variant == "two" else _hand_one(result))
        if self.source == "face":
            return _face(result)
        return (_pose_full(result) if self.variant == "full" else _pose_upper(result))

    def close(self) -> None:
        try:
            self._task.close()
        except Exception:
            pass

    def __enter__(self) -> "LandmarkExtractor":
        return self

    def __exit__(self, *exc) -> None:
        self.close()


# ── 계산 (lib/features.js 와 같은 식) ──
def _dist(a, b) -> float:
    return math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2 + (a.z - b.z) ** 2)


def _mid(a, b):
    class P:
        pass
    p = P()
    p.x = (a.x + b.x) / 2
    p.y = (a.y + b.y) / 2
    p.z = (a.z + b.z) / 2
    return p


def _write_hand(lm, out: np.ndarray, off: int) -> None:
    wrist, mcp = lm[0], lm[9]
    scale = _dist(wrist, mcp) or 1e-6
    for i in range(21):
        out[off + i * 3] = (lm[i].x - wrist.x) / scale
        out[off + i * 3 + 1] = (lm[i].y - wrist.y) / scale
        out[off + i * 3 + 2] = (lm[i].z - wrist.z) / scale


def _hand_one(result) -> np.ndarray | None:
    hands = getattr(result, "hand_world_landmarks", None) or []
    if not hands or len(hands[0]) < 21:
        return None
    vec = np.zeros(63, dtype=np.float32)
    _write_hand(hands[0], vec, 0)
    return vec


def _hand_two(result) -> np.ndarray | None:
    hands = getattr(result, "hand_world_landmarks", None) or []
    if not hands:
        return None
    handedness = getattr(result, "handedness", None) or []
    vec = np.zeros(126, dtype=np.float32)
    wrote = False
    for i, lm in enumerate(hands):
        if not lm or len(lm) < 21:
            continue
        label = "Left" if i == 0 else "Right"
        if i < len(handedness) and handedness[i]:
            label = handedness[i][0].category_name
        _write_hand(lm, vec, 0 if label == "Left" else 63)
        wrote = True
    return vec if wrote else None


def _face(result) -> np.ndarray | None:
    shapes = getattr(result, "face_blendshapes", None) or []
    if not shapes or len(shapes[0]) < 52:
        return None
    return np.array([c.score for c in shapes[0][:52]], dtype=np.float32)


def _pose_upper(result) -> np.ndarray | None:
    poses = getattr(result, "pose_world_landmarks", None) or []
    if not poses or len(poses[0]) < 25:
        return None
    lm = poses[0]
    left, right = lm[11], lm[12]
    cx, cy, cz = (left.x + right.x) / 2, (left.y + right.y) / 2, (left.z + right.z) / 2
    scale = _dist(left, right) or 1e-6
    vec = np.zeros(75, dtype=np.float32)
    for i in range(25):
        vec[i * 3] = (lm[i].x - cx) / scale
        vec[i * 3 + 1] = (lm[i].y - cy) / scale
        vec[i * 3 + 2] = (lm[i].z - cz) / scale
    return vec


def _pose_full(result) -> np.ndarray | None:
    poses = getattr(result, "pose_world_landmarks", None) or []
    if not poses or len(poses[0]) < 33:
        return None
    lm = poses[0]
    shoulder = _mid(lm[11], lm[12])
    hip = _mid(lm[23], lm[24])
    scale = _dist(shoulder, hip) or 1e-6
    vec = np.zeros(99, dtype=np.float32)
    for i in range(33):
        vec[i * 3] = (lm[i].x - hip.x) / scale
        vec[i * 3 + 1] = (lm[i].y - hip.y) / scale
        vec[i * 3 + 2] = (lm[i].z - hip.z) / scale
    return vec
