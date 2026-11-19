# -*- coding: utf-8 -*-
"""얼굴 등록 명단 — 파이보 · 파이브레인(openpibo vision_face)과 같은 파일 형식 · 같은 판정.

파일은 작업폴더의 face/facedb.json 하나(이 PC 의 얼굴 AI 앱 · 블록 · 파이썬이 같이 쓴다).
  {"format": "openpibo-facedb", "model": "face-reidentification-retail-0095",
   "names": [이름, ...], "vectors": [[숫자 256개], ...]}
파이보의 Face.save_db() 가 쓰는 파일과 같아서, 여기서 받은 파일을 파이보 load_db() 로 바로 열고 그 반대도 된다.
사진은 저장하지 않는다 — 얼굴에서 뽑은 숫자(L2 정규화 256개)만 둔다. 같은 이름을 여러 번 등록하면 줄이 여러 개가 된다.

판정(파이보와 같다): 오차도 = (1 - 코사인) x 2/3. 가장 낮은 오차도가 0.4 보다 낮으면 그 사람.
코사인 0.6 이 오차도 0.4 다(예전 dlib 기준과 크기를 맞춘 것). 교실 아이 얼굴에서의 정확도는 확인 필요.
"""
import json
import os
import threading

import numpy as np

DB_FORMAT = "openpibo-facedb"
DB_MODEL = "face-reidentification-retail-0095"
THRESHOLD = 0.4
SCORE_SCALE = 0.4 / 0.6
GUEST = "Guest"                     # 등록 안 된 얼굴 — 파이보 recognize 와 같은 값
MAX_NAME = 30
MAX_ROWS = 2000                     # 한 반이 여러 번 등록해도 넉넉한 상한(파일 약 3MB)


class FaceDBError(ValueError):
    pass


def _clean_name(name):
    n = " ".join(str(name or "").split())[:MAX_NAME]
    if not n:
        raise FaceDBError("이름을 적어 주세요 / Please type a name")
    if n == GUEST:
        raise FaceDBError(f'"{GUEST}" 는 등록할 수 없는 이름이에요 (모르는 사람 표시용)')
    return n


def parse(raw):
    """파일 내용(bytes · str · dict) → (names, vectors). 형식이 다르면 FaceDBError."""
    if isinstance(raw, (bytes, bytearray)):
        try:
            raw = raw.decode("utf-8")
        except UnicodeDecodeError:
            raise FaceDBError("얼굴 정보 파일이 아니에요 (예전 pickle 파일은 열지 않아요 — 다시 등록해 주세요)")
    data = raw
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
        except ValueError:
            raise FaceDBError("얼굴 정보 파일이 아니에요")
    if not isinstance(data, dict) or data.get("format") != DB_FORMAT:
        raise FaceDBError("얼굴 정보 파일이 아니에요 (format: openpibo-facedb 가 아님)")
    if data.get("model") != DB_MODEL:
        raise FaceDBError(f"다른 모델로 만든 얼굴 파일이에요 ({data.get('model')}) — 다시 등록해 주세요")
    names, vectors = data.get("names", []), data.get("vectors", [])
    if not isinstance(names, list) or not isinstance(vectors, list) or len(names) != len(vectors):
        raise FaceDBError("얼굴 정보 파일이 깨졌어요")
    if len(names) > MAX_ROWS:
        raise FaceDBError(f"얼굴이 너무 많아요 ({len(names)}개, {MAX_ROWS}개까지)")
    out_n, out_v = [], []
    for n, v in zip(names, vectors):
        a = np.asarray(v, np.float32).reshape(-1)
        if a.shape[0] != 256 or not np.all(np.isfinite(a)):
            raise FaceDBError("얼굴 정보 파일이 깨졌어요 (숫자 256개가 아님)")
        out_n.append(str(n)[:MAX_NAME])
        out_v.append(a / (float(np.linalg.norm(a)) or 1.0))
    return out_n, out_v


class FaceDB:
    """명단 하나. 모든 바꾸기는 바로 파일에 쓴다(잠그고)."""

    def __init__(self, path_fn):
        self._path_fn = path_fn                # 작업폴더를 옮길 수 있어 부를 때마다 경로를 묻는다
        self._lock = threading.Lock()

    @property
    def path(self):
        return self._path_fn()

    def _read(self):
        p = self.path
        if not os.path.isfile(p):
            return [], []
        with open(p, "rb") as f:
            return parse(f.read())

    def _write(self, names, vectors):
        p = self.path
        os.makedirs(os.path.dirname(p), exist_ok=True)
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(names, vectors), f, ensure_ascii=False)
        os.replace(tmp, p)

    @staticmethod
    def to_dict(names, vectors):
        return {"format": DB_FORMAT, "model": DB_MODEL, "names": list(names),
                "vectors": [[round(float(x), 6) for x in v] for v in vectors]}

    def summary(self):
        names, _ = self._read()
        counts = {}
        for n in names:
            counts[n] = counts.get(n, 0) + 1
        return {"names": [{"name": n, "count": c} for n, c in counts.items()],
                "total": len(names), "people": len(counts), "model": DB_MODEL, "threshold": THRESHOLD}

    def add(self, name, vec):
        name = _clean_name(name)
        with self._lock:
            names, vectors = self._read()
            if len(names) >= MAX_ROWS:
                raise FaceDBError(f"더 등록할 수 없어요 ({MAX_ROWS}개까지) — 안 쓰는 이름을 지워 주세요")
            v = np.asarray(vec, np.float32).reshape(-1)
            names.append(name)
            vectors.append(v / (float(np.linalg.norm(v)) or 1.0))
            self._write(names, vectors)
            return {"name": name, "count": names.count(name), "total": len(names)}

    def delete(self, name):
        with self._lock:
            names, vectors = self._read()
            keep = [(n, v) for n, v in zip(names, vectors) if n != name]
            found = len(keep) != len(names)
            if found:
                self._write([k[0] for k in keep], [k[1] for k in keep])
            return found

    def clear(self):
        with self._lock:
            self._write([], [])

    def replace(self, raw):
        names, vectors = parse(raw)
        with self._lock:
            self._write(names, vectors)
        return len(names)

    def export(self):
        names, vectors = self._read()
        return self.to_dict(names, vectors)

    def match(self, vec):
        """{"name": 이름 또는 Guest, "match": 오차도, "max": 가장 가까운 이름, "known": bool} — 파이보 recognize 와 같은 계산."""
        names, vectors = self._read()
        if not names:
            return {"name": GUEST, "match": 0.0, "max": "", "known": False}
        v = np.asarray(vec, np.float32).reshape(-1)
        v = v / (float(np.linalg.norm(v)) or 1.0)
        dist = (1.0 - np.stack(vectors) @ v) * SCORE_SCALE
        best = int(np.argmin(dist))
        known = bool(dist[best] < THRESHOLD)
        return {"name": names[best] if known else GUEST, "match": round(float(dist[best]), 2),
                "max": names[best], "known": known}
