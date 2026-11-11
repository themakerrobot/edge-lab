# -*- coding: utf-8 -*-
"""사진 전처리 — 브라우저와 똑같이 자르고 줄인다.

Teachable Machine 의 cropTo (@teachablemachine/image, src/utils/canvas.ts) 를
그대로 옮긴 것이다. Teach Lab 브라우저 쪽(lib/embedder.js)도 같은 순서를 쓴다.

  1. 짧은 변이 size 가 되도록 전체를 같은 비율로 줄인다 (찌그러뜨리지 않는다)
  2. 가운데 size×size 만 남긴다
  3. 웹캠 프레임이면 좌우를 뒤집는다 (거울)

거울은 웹캠에만 건다. 사진 파일은 뒤집지 않는다 — TM 도 마찬가지로
Webcam(w, h, flip=True) 이 찍을 때 한 번만 걸고, predict(image) 의 기본값은
flipped=False 다.

줄이기는 numpy 로 직접 한다. OpenCV·Pillow 의 축소 필터는 저마다 달라서
브라우저 캔버스와 어긋나는데, 캔버스(drawImage)의 기본 축소는 안티에일리어싱
없는 평범한 **쌍선형 보간**이라 몇 줄이면 그대로 맞출 수 있다. 덕분에 무거운
이미지 라이브러리에 기대지 않아도 된다.
"""

from __future__ import annotations

import io
import math
from pathlib import Path
from typing import Any

import numpy as np

try:                                  # 파일을 읽을 때만 쓴다 (jpg·png 디코딩)
    from PIL import Image as _PILImage
except ImportError:
    _PILImage = None

try:                                  # 있으면 쓰고, 없어도 된다
    import cv2
except ImportError:
    cv2 = None


def load_rgb(source: Any, bgr: bool | None = None) -> np.ndarray:
    """어떤 입력이 와도 RGB uint8 (H, W, 3) 배열로 만든다.

    source 로 받을 수 있는 것:
      · 파일 경로 (str / Path)
      · numpy 배열 — OpenCV 로 읽은 BGR 이라고 보고 뒤집는다 (bgr=False 로 끄기)
      · PIL.Image
      · bytes (파일 내용 그대로)
    """
    if isinstance(source, (str, Path)):
        return _decode(Path(source).read_bytes(), Path(source))

    if isinstance(source, (bytes, bytearray)):
        return _decode(bytes(source), None)

    if _PILImage is not None and isinstance(source, _PILImage.Image):
        return np.asarray(source.convert("RGB"), dtype=np.uint8)

    if isinstance(source, np.ndarray):
        arr = source
        if arr.dtype != np.uint8:
            arr = np.clip(arr, 0, 255).astype(np.uint8)
        if arr.ndim == 2:
            arr = np.stack([arr] * 3, axis=-1)
        if arr.ndim != 3 or arr.shape[2] not in (3, 4):
            raise ValueError(f"지원하지 않는 배열 모양입니다: {source.shape}")
        if arr.shape[2] == 4:
            arr = arr[:, :, :3]
        # OpenCV 로 읽은 그림은 BGR 이다. 기본값은 BGR 로 본다.
        if bgr is None or bgr:
            arr = arr[:, :, ::-1]
        return np.ascontiguousarray(arr)

    raise TypeError(f"사진으로 쓸 수 없는 값입니다: {type(source)!r}")


def _decode(data: bytes, path: Path | None) -> np.ndarray:
    if _PILImage is not None:
        with _PILImage.open(io.BytesIO(data)) as im:
            return np.asarray(im.convert("RGB"), dtype=np.uint8)
    if cv2 is not None:
        img = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError(f"사진을 읽지 못했어요: {path or '(메모리)'}")
        return np.ascontiguousarray(img[:, :, ::-1])
    raise RuntimeError("사진 파일을 읽으려면 Pillow 가 필요해요:  pip install pillow")


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
