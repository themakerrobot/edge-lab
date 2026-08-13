# -*- coding: utf-8 -*-
"""speech_routes — 음성 인식(STT) · 음성 합성(TTS).

- POST /speech/stt   (uploadFile: wav)  -> {"text": "...", "lang": "ko"}
- POST /speech/tts   (text, voice, lang) -> WAV 파일
- GET  /speech/ready                    -> 모델이 준비됐는지
- GET  /speech/voices                   -> 쓸 수 있는 목소리 목록

모델
  STT: models/stt (OpenVINO/whisper-small-int8-ov, openvino_genai.WhisperPipeline)
  TTS: models/tts (Supertone/supertonic-3, onnx/ + voice_styles/)
       추론은 onnxruntime 만 사용한다. 절차는 공식 예제(supertone-inc/supertonic, MIT)를
       그대로 옮긴 것 — 전처리·토크나이저·마스크 계산은 원본과 결과 일치를 확인했다.

둘 다 무거우므로 처음 요청이 올 때 로딩한다(지연 로딩). 서버 시작 시간에 영향이 없다.
STT 입력은 WAV 만 받는다. 브라우저 녹음(webm)은 화면 쪽에서 WAV 로 바꿔 보낸다.
"""
import io
import json
import os
import re
import time
import unicodedata
import wave
import threading

import numpy as np
from fastapi import APIRouter, Body, File, UploadFile, Query
from fastapi.responses import Response

router = APIRouter()

ROOT = os.path.dirname(os.path.abspath(__file__))
STT_DIR = os.path.join(ROOT, "models", "stt")
TTS_DIR = os.path.join(ROOT, "models", "tts")
TARGET_SR = 16000                       # Whisper 입력 샘플레이트

_pipe = None
_dev = "CPU"
_lock = threading.Lock()
_err = ""

_tts = None
_tts_lock = threading.Lock()
_tts_err = ""
VOICES = ["F1", "F2", "F3", "F4", "F5", "M1", "M2", "M3", "M4", "M5"]


def _ok(name, data, t0, dev):
    return {"type": name, "result": "ok", "data": data,
            "elapsed_ms": int((time.perf_counter() - t0) * 1000), "device": dev}


def _fail(name, msg, t0, dev="CPU"):
    return {"type": name, "result": "fail", "data": str(msg),
            "elapsed_ms": int((time.perf_counter() - t0) * 1000), "device": dev}


def _pick_device():
    """GPU 가 있으면 GPU, 없으면 CPU. (NPU 는 Whisper 미지원 케이스가 많다)"""
    try:
        import openvino as ov
        devs = ov.Core().available_devices
        return "GPU" if any(d.startswith("GPU") for d in devs) else "CPU"
    except Exception:
        return "CPU"


def _load():
    """WhisperPipeline 지연 로딩. 실패해도 서버는 계속 돈다."""
    global _pipe, _dev, _err
    if _pipe is not None or _err:
        return _pipe
    with _lock:
        if _pipe is not None or _err:
            return _pipe
        if not os.path.isdir(STT_DIR):
            _err = "models/stt 폴더가 없어요. setup 으로 모델을 받아 주세요."
            return None
        try:
            import openvino_genai as ov_genai
            _dev = _pick_device()
            try:
                from engines import CACHE_DIR as _cache
            except Exception:
                _cache = ""
            kw = {"CACHE_DIR": _cache} if _cache else {}
            _pipe = ov_genai.WhisperPipeline(STT_DIR, _dev, **kw)
            print(f"[stt] whisper loaded ({_dev})")
        except Exception as ex:
            _err = "STT 모델을 열 수 없어요: %s" % ex
            print("[stt]", _err)
    return _pipe


def _read_wav(raw):
    """WAV bytes -> 16kHz mono float32 [-1,1]."""
    with wave.open(io.BytesIO(raw), "rb") as w:
        ch, width, sr = w.getnchannels(), w.getsampwidth(), w.getframerate()
        frames = w.readframes(w.getnframes())
    if width == 2:
        a = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
    elif width == 4:
        a = np.frombuffer(frames, dtype=np.int32).astype(np.float32) / 2147483648.0
    elif width == 1:
        a = (np.frombuffer(frames, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
    else:
        raise ValueError("지원하지 않는 WAV 형식이에요 (%d bit)" % (width * 8))
    if ch > 1:
        a = a.reshape(-1, ch).mean(axis=1)          # 모노로 합친다
    if sr != TARGET_SR and len(a) > 1:              # 선형 보간 리샘플
        n = int(round(len(a) * TARGET_SR / float(sr)))
        a = np.interp(np.linspace(0, len(a) - 1, n),
                      np.arange(len(a)), a).astype(np.float32)
    return np.ascontiguousarray(a, dtype=np.float32)


@router.get("/speech/ready", tags=["speech"], summary="STT 준비 상태")
def speech_ready():
    return {"result": "ok",
            "data": {"loaded": _pipe is not None, "error": _err, "device": _dev,
                     "tts_loaded": _tts is not None, "tts_error": _tts_err}}


@router.post("/speech/stt", tags=["speech"], summary="음성 인식 (WAV -> 글자)")
def speech_stt(uploadFile: UploadFile = File(...),
               lang: str = Query("ko", description="ko | en | auto")):
    t0 = time.perf_counter()
    pipe = _load()
    if pipe is None:
        return _fail("stt", _err or "STT 를 쓸 수 없어요.", t0)
    try:
        audio = _read_wav(uploadFile.file.read())
    except Exception as ex:
        return _fail("stt", "소리 파일을 읽을 수 없어요 (WAV 만 됩니다): %s" % ex, t0, _dev)
    if audio.size < TARGET_SR // 5:
        return _fail("stt", "녹음이 너무 짧아요.", t0, _dev)
    try:
        kw = {}
        if lang in ("ko", "en"):
            kw = {"language": "<|%s|>" % lang, "task": "transcribe"}
        try:
            res = pipe.generate(audio, **kw)
        except TypeError:                    # 옵션 미지원 버전 대비
            res = pipe.generate(audio)
        text = str(res).strip()
        return _ok("stt", {"text": text, "lang": lang}, t0, _dev)
    except Exception as ex:
        return _fail("stt", "음성 인식 실패: %s" % ex, t0, _dev)


# ================================================================= TTS
# Supertonic 3 (ONNX) — 공식 예제(supertone-inc/supertonic, MIT)의 파이썬 추론 절차를
# onnxruntime 만으로 옮긴 것. 별도 SDK 없이 models/tts/onnx 를 직접 돌린다.
TTS_LANGS = ("en", "ko", "ja", "ar", "bg", "cs", "da", "de", "el", "es", "et", "fi",
             "fr", "hi", "hr", "hu", "id", "it", "lt", "lv", "nl", "pl", "pt", "ro",
             "ru", "sk", "sl", "sv", "tr", "uk", "vi", "na")

_EMOJI = re.compile(
    "[\U0001f600-\U0001f64f\U0001f300-\U0001f5ff\U0001f680-\U0001f6ff"
    "\U0001f700-\U0001f77f\U0001f780-\U0001f7ff\U0001f800-\U0001f8ff"
    "\U0001f900-\U0001f9ff\U0001fa00-\U0001fa6f\U0001fa70-\U0001faff"
    "\u2600-\u26ff\u2700-\u27bf\U0001f1e6-\U0001f1ff]+", flags=re.UNICODE)

_REPL = {"–": "-", "‑": "-", "—": "-", "_": " ", "\u201c": '"', "\u201d": '"',
         "\u2018": "'", "\u2019": "'", "´": "'", "`": "'",
         "[": " ", "]": " ", "|": " ", "/": " ", "#": " ", "→": " ", "←": " "}
_EXPR = {"@": " at ", "e.g.,": "for example, ", "i.e.,": "that is, "}


def _prep_text(text, lang):
    """공식 전처리와 동일: NFKD → 이모지·기호 정리 → 문장부호 보정 → <lang> 태그."""
    text = unicodedata.normalize("NFKD", text)
    text = _EMOJI.sub("", text)
    for k, v in _REPL.items():
        text = text.replace(k, v)
    text = re.sub(r"[♥☆♡©\\]", "", text)
    for k, v in _EXPR.items():
        text = text.replace(k, v)
    for mark in (",", r"\.", "!", r"\?", ";", ":", "'"):
        text = re.sub(" " + mark, mark.replace("\\", ""), text)
    for dup in ('""', "''", "``"):
        while dup in text:
            text = text.replace(dup, dup[0])
    text = re.sub(r"\s+", " ", text).strip()
    if not re.search(r"[.!?;:,'\"')\]}…。」』】〉》›»]$", text):
        text += "."
    return "<%s>%s</%s>" % (lang, text, lang)


def _chunk(text, max_len):
    """긴 글은 문장 단위로 나눠 합성한다(모델 입력 길이 제한)."""
    out, cur = [], ""
    for sent in re.split(r"(?<=[.!?])\s+", text.strip()):
        if len(cur) + len(sent) + 1 <= max_len:
            cur += (" " if cur else "") + sent
        else:
            if cur:
                out.append(cur.strip())
            cur = sent
    if cur:
        out.append(cur.strip())
    return out or [text]


class _Supertonic:
    """4단계 ONNX: 길이예측 → 텍스트인코딩 → 잡음제거 반복 → 보코더."""

    def __init__(self, root):
        import onnxruntime as ort
        d = os.path.join(root, "onnx")
        opt = ort.SessionOptions()
        prov = ["CPUExecutionProvider"]
        load = lambda n: ort.InferenceSession(os.path.join(d, n), sess_options=opt,
                                              providers=prov)
        self.dp = load("duration_predictor.onnx")
        self.enc = load("text_encoder.onnx")
        self.est = load("vector_estimator.onnx")
        self.voc = load("vocoder.onnx")
        with open(os.path.join(d, "tts.json"), encoding="utf-8") as f:
            cfg = json.load(f)
        with open(os.path.join(d, "unicode_indexer.json"), encoding="utf-8") as f:
            self.indexer = json.load(f)
        self.sr = int(cfg["ae"]["sample_rate"])
        self.base_chunk = int(cfg["ae"]["base_chunk_size"])
        self.compress = int(cfg["ttl"]["chunk_compress_factor"])
        self.ldim = int(cfg["ttl"]["latent_dim"])
        self.styles = {}
        self.style_dir = os.path.join(root, "voice_styles")

    # ---- 목소리 ----
    def style(self, name):
        if name in self.styles:
            return self.styles[name]
        with open(os.path.join(self.style_dir, name + ".json"), encoding="utf-8") as f:
            js = json.load(f)
        def arr(key):
            dims = js[key]["dims"]
            return np.array(js[key]["data"], dtype=np.float32).reshape(
                1, dims[1], dims[2])
        st = (arr("style_ttl"), arr("style_dp"))
        self.styles[name] = st
        return st

    # ---- 토크나이저 ----
    def _ids(self, text):
        idx = self.indexer
        vals = [ord(c) for c in text]
        if isinstance(idx, dict):
            ids = [int(idx.get(str(v), 0)) for v in vals]
        else:
            ids = [int(idx[v]) if v < len(idx) else 0 for v in vals]
        return (np.array([ids], dtype=np.int64),
                np.ones((1, 1, len(ids)), dtype=np.float32))

    def _latent(self, dur):
        wav_len = (dur * self.sr).astype(np.int64)
        size = self.base_chunk * self.compress
        n = int((wav_len.max() + size - 1) // size)
        mask = (np.arange(n) < ((wav_len + size - 1) // size)[:, None]
                ).astype(np.float32).reshape(1, 1, n)
        x = np.random.randn(1, self.ldim * self.compress, n).astype(np.float32)
        return x * mask, mask

    def _one(self, text, lang, style, steps, speed):
        ids, tmask = self._ids(_prep_text(text, lang))
        ttl, dp = style
        dur = self.dp.run(None, {"text_ids": ids, "style_dp": dp,
                                 "text_mask": tmask})[0] / float(speed)
        emb = self.enc.run(None, {"text_ids": ids, "style_ttl": ttl,
                                  "text_mask": tmask})[0]
        x, lmask = self._latent(dur)
        total = np.array([steps], dtype=np.float32)
        for k in range(steps):
            x = self.est.run(None, {"noisy_latent": x, "text_emb": emb,
                                    "style_ttl": ttl, "text_mask": tmask,
                                    "latent_mask": lmask,
                                    "current_step": np.array([k], dtype=np.float32),
                                    "total_step": total})[0]
        wav = self.voc.run(None, {"latent": x})[0]
        return wav[0][:int(self.sr * float(dur[0]))]

    def say(self, text, lang="ko", voice="F1", steps=8, speed=1.05, gap=0.3):
        style = self.style(voice)
        max_len = 120 if lang in ("ko", "ja") else 300
        parts = []
        for piece in _chunk(text, max_len):
            parts.append(self._one(piece, lang, style, steps, speed))
        if len(parts) > 1:
            sil = np.zeros(int(gap * self.sr), dtype=np.float32)
            joined = parts[0]
            for w in parts[1:]:
                joined = np.concatenate([joined, sil, w])
            return joined
        return parts[0]


def _load_tts():
    """models/tts 를 직접 연다. 실패해도 서버는 계속 돈다."""
    global _tts, _tts_err
    if _tts is not None or _tts_err:
        return _tts
    with _tts_lock:
        if _tts is not None or _tts_err:
            return _tts
        if not os.path.isdir(os.path.join(TTS_DIR, "onnx")):
            _tts_err = "models/tts/onnx 폴더가 없어요. setup 으로 모델을 받아 주세요."
            return None
        try:
            _tts = _Supertonic(TTS_DIR)
            print("[tts] supertonic loaded (CPU, %dHz)" % _tts.sr)
        except ImportError as ex:
            _tts_err = "onnxruntime 이 필요해요: %s" % ex
        except Exception as ex:
            _tts_err = "TTS 모델을 열 수 없어요: %s" % ex
        if _tts_err:
            print("[tts]", _tts_err)
    return _tts


def _wav_bytes(a, sr):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(int(sr))
        w.writeframes((np.clip(a, -1, 1) * 32767).astype(np.int16).tobytes())
    return buf.getvalue()


@router.get("/speech/voices", tags=["speech"], summary="쓸 수 있는 목소리")
def speech_voices():
    return {"result": "ok", "data": {"voices": VOICES, "default": "F1",
                                     "langs": list(TTS_LANGS), "error": _tts_err}}


@router.post("/speech/tts", tags=["speech"], summary="음성 합성 (글자 -> 소리)")
def speech_tts(text: str = Body(..., embed=True),
               voice: str = Body("F1", embed=True),
               lang: str = Body("ko", embed=True),
               speed: float = Body(1.05, embed=True),
               steps: int = Body(8, embed=True)):
    text = (text or "").strip()
    if not text:
        return {"result": "fail", "data": "읽을 글이 없어요."}
    if len(text) > 1000:
        text = text[:1000]
    if voice not in VOICES:
        voice = "F1"
    if lang not in TTS_LANGS:
        lang = "ko"
    speed = min(max(float(speed), 0.5), 2.0)
    steps = min(max(int(steps), 1), 32)

    tts = _load_tts()
    if tts is None:
        return {"result": "fail", "data": _tts_err or "TTS 를 쓸 수 없어요."}
    try:
        wav = tts.say(text, lang=lang, voice=voice, steps=steps, speed=speed)
    except Exception as ex:
        return {"result": "fail", "data": "소리를 만들지 못했어요: %s" % ex}
    return Response(content=_wav_bytes(np.asarray(wav, dtype=np.float32).reshape(-1),
                                       tts.sr),
                    media_type="audio/wav",
                    headers={"X-Sample-Rate": str(tts.sr)})
