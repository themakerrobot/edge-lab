# -*- coding: utf-8 -*-
"""speech_routes — 음성 인식(STT) · 음성 합성(TTS).

- POST /speech/stt   (uploadFile: wav)  -> {"text": "...", "lang": "ko", "engine": "sensevoice"}
- POST /speech/tts   (text, voice, lang) -> WAV 파일
- GET  /speech/ready                    -> 모델이 준비됐는지
- GET  /speech/voices                   -> 쓸 수 있는 목소리 목록

모델
  STT: models/stt-sv (SenseVoiceSmall int8 + silero VAD, sherpa-onnx). 파이보 · 파이브레인과 같은 파일·같은 계산
       (openpibo SpeechToText.transcribe: DC 빼기 · 작은 소리 키우기(최대 20배) · 25초 넘으면 VAD 로 말 단위로 잘라 받아 적기).
       언어는 모델이 스스로 알아낸다(한·영·중·일·광둥어). lang 은 응답에 그대로 돌려준다.
       실측(x86 4스레드, 문장 14개): 116ms · 최고 메모리 421MB, 글자 오류율 2.7% (예전 Whisper-small 은 492ms · 831MB · 2.3% — 뺐다)
  TTS: models/tts-int8 (Supertone/supertonic-3 의 int8 양자화판, onnx/ + voice_styles/ — 바꾼 곳은 MODIFICATIONS.md)
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
# 음성 인식 — SenseVoice(models/stt-sv) 하나. 읽어 주기 — Supertonic int8(models/tts-int8) 하나.
SV_DIR = os.path.join(ROOT, "models", "stt-sv")
SV_FILES = ("model.int8.onnx", "tokens.txt", "silero_vad.onnx")
STT_ENGINE = "sensevoice"               # 응답 · /speech/ready 에 그대로 알린다
TTS_DIR = os.path.join(ROOT, "models", "tts-int8")
TARGET_SR = 16000                       # 음성 인식 입력 샘플레이트

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


class _SenseVoice:
    """SenseVoiceSmall int8 + silero VAD (sherpa-onnx). openpibo SpeechToText.transcribe 와 같은 계산이다 —
    한쪽을 고치면 다른 쪽도 같이 고칠 것(파이보 · 파이브레인 openpibo/speech.py)."""

    def __init__(self, d, threads=4):
        import sherpa_onnx
        self._sherpa = sherpa_onnx
        self._rec = sherpa_onnx.OfflineRecognizer.from_sense_voice(
            model=os.path.join(d, "model.int8.onnx"), tokens=os.path.join(d, "tokens.txt"),
            num_threads=threads, use_itn=True)
        self._vad_cfg = sherpa_onnx.VadModelConfig()
        self._vad_cfg.silero_vad.model = os.path.join(d, "silero_vad.onnx")
        self._vad_cfg.silero_vad.min_silence_duration = 0.3
        self._vad_cfg.sample_rate = TARGET_SR

    def _decode(self, audio):
        st = self._rec.create_stream()
        st.accept_waveform(TARGET_SR, audio)
        self._rec.decode_stream(st)
        return st.result.text.strip()

    def transcribe(self, audio):
        audio = np.asarray(audio, dtype=np.float32)
        if len(audio) == 0:
            return ""
        audio = audio - audio.mean()                 # DC 가 있으면 아래 크기 맞추기가 틀어진다
        peak = float(np.abs(audio).max())
        if 0 < peak < 0.5:                           # 소리가 작으면 키운다(최대 20배)
            audio = audio * min(0.5 / peak, 20.0)
        audio = np.ascontiguousarray(audio, dtype=np.float32)
        # 말 구간을 먼저 찾는다. 하나도 없으면(조용한 녹음) 빈 글자 — 모델에 그냥 넣으면 '그.' 같은 글자를 지어낸다.
        # (로봇은 listen() 이 VAD 로 말이 있을 때만 받아 적어 같은 결과다. transcribe() 에는 이 검사가 없다)
        vad = self._sherpa.VoiceActivityDetector(self._vad_cfg,
                                                 buffer_size_in_seconds=max(30, len(audio) / TARGET_SR + 5))
        w = self._vad_cfg.silero_vad.window_size
        for i in range(0, len(audio), w):
            vad.accept_waveform(audio[i:i + w])
        vad.flush()
        segs = []
        while not vad.empty():
            segs.append(np.asarray(vad.front.samples, dtype=np.float32))
            vad.pop()
        if not segs:
            return ""
        if len(audio) <= 25 * TARGET_SR:            # 짧으면 통째로(로봇과 같은 글자)
            return self._decode(audio)
        # 25초보다 길면 말 단위로 잘라 받아 적는다(통째로 넣으면 글자가 뒤섞인다)
        texts = [self._decode(x) for x in segs]
        return " ".join(t for t in texts if t)


def _load():
    """음성 인식 모델 지연 로딩. 실패해도 서버는 계속 돈다."""
    global _pipe, _dev, _err
    if _pipe is not None or _err:
        return _pipe
    with _lock:
        if _pipe is not None or _err:
            return _pipe
        miss = [f for f in SV_FILES if not os.path.isfile(os.path.join(SV_DIR, f))]
        if miss:
            _err = "models/stt-sv 에 %s 이(가) 없어요. setup 으로 모델을 받아 주세요." % ", ".join(miss)
            return None
        try:
            _dev = "CPU"
            _pipe = _SenseVoice(SV_DIR)
            print("[stt] sensevoice loaded (CPU)")
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
            "data": {"loaded": _pipe is not None, "error": _err, "device": _dev, "engine": STT_ENGINE,
                     "tts_loaded": _tts is not None, "tts_error": _tts_err}}


@router.post("/speech/stt", tags=["speech"], summary="음성 인식 (WAV -> 글자)")
def speech_stt(uploadFile: UploadFile = File(...),
               lang: str = Query("ko", description="ko | en | auto — SenseVoice 는 언어를 스스로 알아내고, 이 값은 응답에 그대로 돌려준다")):
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
        text = pipe.transcribe(audio)
        return _ok("stt", {"text": text, "lang": lang, "engine": STT_ENGINE}, t0, _dev)
    except Exception as ex:
        return _fail("stt", "음성 인식 실패: %s" % ex, t0, _dev)


# ================================================================= TTS
# Supertonic 3 (ONNX) — 공식 예제(supertone-inc/supertonic, MIT)의 파이썬 추론 절차를
# onnxruntime 만으로 옮긴 것. 별도 SDK 없이 models/tts-int8/onnx 를 직접 돌린다.
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
        # onnx/ 아래에 두는 것이 원래 구성이다. 폴더 바로 아래에 .onnx 가 있어도 연다
        d = os.path.join(root, "onnx")
        if not os.path.isfile(os.path.join(d, "vector_estimator.onnx")):
            d = root
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
    """models/tts-int8 을 직접 연다. 실패해도 서버는 계속 돈다."""
    global _tts, _tts_err
    if _tts is not None or _tts_err:
        return _tts
    with _tts_lock:
        if _tts is not None or _tts_err:
            return _tts
        if not (os.path.isdir(os.path.join(TTS_DIR, "onnx"))
                or os.path.isfile(os.path.join(TTS_DIR, "vector_estimator.onnx"))):
            _tts_err = "%s 에 TTS 모델이 없어요. setup 으로 모델을 받아 주세요." % TTS_DIR
            return None
        try:
            _tts = _Supertonic(TTS_DIR)
            print("[tts] supertonic loaded (%s, CPU, %dHz)" % (os.path.basename(TTS_DIR), _tts.sr))
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
