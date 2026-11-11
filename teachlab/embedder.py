# -*- coding: utf-8 -*-
"""이미지 임베더 — 사진을 1024개의 숫자로 바꾼다.

로봇(openpibo/modules/teachlab/embedder.py)과 같은 계산이다. 다른 곳은 실행기 하나뿐 —
로봇은 onnxruntime, 여기는 **같은 ONNX 파일**을 OpenVINO 로 돌린다. 정밀도는 f32 로 고정한다
(CPU 가 bfloat16 으로 계산하면 숫자가 어긋난다 — engines.py MaskCls 와 같은 이유).

MediaPipe ImageEmbedder 가 하는 일을 그대로 따라 한다.
  1. Teachable Machine cropTo 로 224×224 (preprocess.crop_to)
  2. 입력을 0~1 로 나눈다 (x / 255), 1×224×224×3 float32
  3. 나온 1024개 값을 L2 정규화한다
"""

from __future__ import annotations

import threading
from pathlib import Path

import numpy as np

from . import EMBEDDER_ONNX
from .preprocess import crop_to

INPUT_SCALE = 1.0 / 255.0
KNOWN = {'mobilenet_v3_small_embedder': EMBEDDER_ONNX}


def resolve(model_path) -> Path:
    """`.onnx` 면 그대로, 브라우저용 `.tflite` 이름이면 같은 모델의 ONNX 로 바꾼다."""
    p = Path(model_path)
    if p.suffix.lower() == '.onnx':
        return p
    if p.stem in KNOWN:
        return Path(KNOWN[p.stem])
    raise ValueError(f"이 임베더는 쓸 수 없어요: {p.name} (mobilenet_v3_small_embedder 만)")


class ImageEmbedder:
    """OpenVINO 로 임베더 하나를 돌린다. 한 번 만들어 두고 계속 쓴다."""

    def __init__(self, model_path=EMBEDDER_ONNX, input_size: int = 224,
                 l2_normalize: bool = True, device: str = "CPU"):
        import openvino as ov
        self.model_path = resolve(model_path)
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
