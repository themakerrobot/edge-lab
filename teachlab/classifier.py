# -*- coding: utf-8 -*-
"""분류기 — Teach Lab 이 내보낸 가중치를 numpy 로 그대로 돌린다.

저장 형식 (파일 두 개)
  classifier.json  층마다 kernel/bias 의 shape 과 offset(float32 개수)
  classifier.bin   float32 little-endian 을 순서대로 이어 붙인 것

딥러닝 라이브러리가 필요 없다. 행렬 곱 두 번이면 끝난다.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import numpy as np

CLF_FORMAT = "teachlab-classifier"
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
            raise ValueError("Teach Lab 분류기 파일이 아니에요.")
        if int(spec.get("version", 1)) > CLF_VERSION:
            raise ValueError("더 새로운 버전에서 만든 파일이에요. teachlab 을 올려 주세요.")

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
