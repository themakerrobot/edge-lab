# -*- coding: utf-8 -*-
"""가르치기 특징 · 분류기 — 사진 · 손 · 얼굴 · 몸을 숫자로 바꾸고, 저장한 분류기로 답을 낸다 (train_routes 가 쓴다).

  사진      mobilenet_v3_small 1024 (L2) — models/mediapipe/mobilenet_v3_small_embedder.onnx 를 OpenVINO f32 로
            Teachable Machine cropTo 와 같은 자르기 · 줄이기(브라우저 캔버스와 같은 쌍선형) → 0~1 → L2 정규화
  손        world 좌표 21점 → 손목 원점 · 손목~중지 MCP 길이로 나눔 → 63 (두 손 126)  — hand_landmarker.task
  얼굴      표정 blendshape 52                                                       — face_landmarker.task
  몸        상반신 25점 75 (어깨 원점 · 어깨 너비) / 전신 33점 99 (엉덩이 원점 · 몸통 길이) — pose_landmarker_lite.task
  분류기    classifier.json(층마다 shape · offset) + classifier.bin(float32) → Dense relu → Dense softmax (numpy)

모델 파일은 허깅페이스(brand.json 의 repo_hf) mediapipe/ 에서 받는다 → models/mediapipe/ (tools/fetch_models.py).
계산은 teach-lab(themakerrobot/teach-lab, MIT)에서 옮겨 왔다. 이 식을 바꾸면 전에 가르친 AI 가 엉뚱한 답을 낸다.
"""

from __future__ import annotations

import json
import math
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import numpy as np

from modelfile import read_model

MODEL_DIR = Path(__file__).resolve().parent / "models" / "mediapipe"
EMBEDDER_ONNX = MODEL_DIR / "mobilenet_v3_small_embedder.onnx"
LANDMARK_FILE = {
    "hand": MODEL_DIR / "hand_landmarker.task",
    "face": MODEL_DIR / "face_landmarker.task",
    "pose": MODEL_DIR / "pose_landmarker_lite.task",
}


# ---------------------------------------------------------------- 사진 자르기 · 줄이기 (브라우저와 같게)
def crop_to(rgb: np.ndarray, size: int, flip: bool = False) -> np.ndarray:
    """Teachable Machine 의 cropTo 와 같은 결과를 만든다.

    먼저 짧은 변을 size 에 맞춰 전체를 줄이고, 그다음 가운데를 잘라 낸다.
    (자르고 줄이는 게 아니라 줄이고 자르는 순서다 — 반올림까지 TM 과 맞춘다.)
    """
    h, w = rgb.shape[:2]
    if not h or not w:
        raise ValueError("빈 사진이에요.")

    scale = size / min(w, h)
    scaled_w = math.ceil(w * scale)
    scaled_h = math.ceil(h * scale)

    resized = resize_bilinear(rgb, scaled_w, scaled_h)

    left = (scaled_w - size) // 2
    top = (scaled_h - size) // 2
    out = resized[top:top + size, left:left + size]

    if flip:
        out = out[:, ::-1]
    return np.ascontiguousarray(out)


def resize_bilinear(rgb: np.ndarray, width: int, height: int) -> np.ndarray:
    """안티에일리어싱 없는 쌍선형 보간 — 브라우저 캔버스(drawImage)와 같은 방식.

    표본 위치는 픽셀 가운데를 기준으로 잡는다: src = (dst + 0.5) * 비율 - 0.5.
    (OpenCV 의 INTER_LINEAR 과 같은 격자다.)
    """
    h, w = rgb.shape[:2]
    if (width, height) == (w, h):
        return rgb

    x = (np.arange(width, dtype=np.float32) + 0.5) * (w / width) - 0.5
    y = (np.arange(height, dtype=np.float32) + 0.5) * (h / height) - 0.5
    np.clip(x, 0, w - 1, out=x)
    np.clip(y, 0, h - 1, out=y)

    x0 = np.floor(x).astype(np.int32)
    y0 = np.floor(y).astype(np.int32)
    x1 = np.minimum(x0 + 1, w - 1)
    y1 = np.minimum(y0 + 1, h - 1)
    wx = (x - x0)[None, :, None]
    wy = (y - y0)[:, None, None]

    src = rgb.astype(np.float32)
    top = src[y0[:, None], x0[None, :]] * (1 - wx) + src[y0[:, None], x1[None, :]] * wx
    bottom = src[y1[:, None], x0[None, :]] * (1 - wx) + src[y1[:, None], x1[None, :]] * wx
    out = top * (1 - wy) + bottom * wy
    return np.clip(out + 0.5, 0, 255).astype(np.uint8)


# ---------------------------------------------------------------- 사진 → 1024
INPUT_SCALE = 1.0 / 255.0


class ImageEmbedder:
    """OpenVINO 로 임베더 하나를 돌린다. 한 번 만들어 두고 계속 쓴다."""

    def __init__(self, model_path=None, input_size: int = 224,
                 l2_normalize: bool = True, device: str = "CPU"):
        import openvino as ov
        self.model_path = Path(model_path or EMBEDDER_ONNX)
        self.input_size = int(input_size)
        self.l2_normalize = bool(l2_normalize)
        core = ov.Core()
        model = core.read_model(str(self.model_path))
        self.device = device
        self._compiled = core.compile_model(model, device, {"INFERENCE_PRECISION_HINT": "f32"})
        self._out = self._compiled.output(0)
        self.dim = int(self._out.get_partial_shape()[-1].get_length())
        self._lock = threading.Lock()

    def embed_rgb(self, rgb: np.ndarray, flip: bool = False) -> np.ndarray:
        """RGB uint8 배열 → float32 임베딩. 자르기·줄이기·거울은 여기서 한다."""
        square = crop_to(rgb, self.input_size, flip)
        x = (square.astype(np.float32) * INPUT_SCALE).reshape(1, self.input_size, self.input_size, 3)
        with self._lock:
            vec = np.asarray(self._compiled(x)[self._out], np.float32).reshape(-1)
        if self.l2_normalize:
            vec = vec / (float(np.linalg.norm(vec)) or 1.0)
        return vec


# ---------------------------------------------------------------- 손 · 얼굴 · 몸 → 좌표 특징
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
                "    pip install -r requirements.lock.txt"
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


# ---------------------------------------------------------------- 분류기
CLF_FORMAT = "teachlab-classifier"         # 저장 파일 형식 이름 — 화면(train.html) · 소리 가르치기(lib/sound/classifier.js)와 같은 값
CLF_VERSION = 1


@dataclass
class Prediction:
    """한 장에 대한 답."""

    label: str
    score: float
    probs: dict[str, float]

    def ranked(self) -> list[tuple[str, float]]:
        """확률이 높은 순서로 [(이름, 확률), ...]"""
        return sorted(self.probs.items(), key=lambda kv: kv[1], reverse=True)

    def __str__(self) -> str:                         # print() 할 때 보기 좋게
        return f"{self.label} ({self.score * 100:.1f}%)"


@dataclass
class _Layer:
    weight: np.ndarray                                # (in, out)
    bias: np.ndarray                                  # (out,)
    activation: str


class Classifier:
    """평범한 다층 퍼셉트론 (Dense relu → Dense softmax)."""

    def __init__(self, spec: dict, weights: bytes):
        if spec.get("format") != CLF_FORMAT:
            raise ValueError("가르치기 분류기 파일이 아니에요.")
        if int(spec.get("version", 1)) > CLF_VERSION:
            raise ValueError("더 새로운 버전에서 만든 파일이에요. 프로그램을 새 버전으로 바꿔 주세요.")

        flat = np.frombuffer(weights, dtype="<f4")
        total = int(spec.get("totalCount", flat.size))
        if flat.size < total:
            raise ValueError("가중치 파일이 잘렸어요.")

        self.input_dim = int(spec["inputDim"])
        self.classes: list[str] = list(spec["classes"])
        self.layers: list[_Layer] = []
        for layer in spec["layers"]:
            k, b = layer["kernel"], layer["bias"]
            weight = flat[k["offset"]:k["offset"] + k["count"]].reshape(tuple(k["shape"]))
            bias = flat[b["offset"]:b["offset"] + b["count"]].reshape(tuple(b["shape"]))
            self.layers.append(_Layer(weight, bias, layer.get("activation", "relu")))

    # ── 만들기 ──
    @classmethod
    def from_dir(cls, folder: str | Path) -> "Classifier":
        folder = Path(folder)
        spec = json.loads((folder / "classifier.json").read_text(encoding="utf-8"))
        name = spec.get("weightsFile", "classifier.bin")
        return cls(spec, (folder / name).read_bytes())

    # ── 계산 ──
    def predict_proba(self, vec: Sequence[float] | np.ndarray) -> np.ndarray:
        x = np.asarray(vec, dtype=np.float32).reshape(-1)
        if x.size != self.input_dim:
            raise ValueError(f"입력이 {self.input_dim} 개여야 하는데 {x.size} 개가 왔어요.")
        for layer in self.layers:
            x = x @ layer.weight + layer.bias
            if layer.activation == "relu":
                x = np.maximum(x, 0.0)
            elif layer.activation == "softmax":
                e = np.exp(x - x.max())
                x = e / (e.sum() or 1.0)
        return x.astype(np.float32)

    def predict(self, vec: Sequence[float] | np.ndarray) -> Prediction:
        probs = self.predict_proba(vec)
        best = int(np.argmax(probs))
        return Prediction(
            label=self.classes[best],
            score=float(probs[best]),
            probs={name: float(p) for name, p in zip(self.classes, probs)},
        )
