# -*- coding: utf-8 -*-
"""themaker — The Maker 파이썬 라이브러리.

서버(The Maker)가 켜져 있으면, 파이썬에서 AI를 함수 한 줄로 쓸 수 있다.

    from themaker import *

    img = camera()                  # 웹캠 한 장
    r = vision("사물", img)         # AI 실행
    print(r)
    show(img, r)                    # 결과를 그려서 창으로 보기

의존성: opencv-python, numpy (The Maker 설치에 이미 포함).
서버 호출은 표준 라이브러리(urllib)만 쓴다.
"""
import json
import os
import time
import urllib.request
import urllib.error
import urllib.parse

import cv2
import numpy as np

SERVER = os.environ.get("THEMAKER_SERVER", "http://127.0.0.1:57711")

# AI 가 돌려주는 이름의 언어. 파이썬 페이지에서 실행하면 화면 언어를 따라오고,
# 배포한 프로그램에서는 한국어가 기본이다. language("en") 으로 바꿀 수 있다.
LANG = (os.environ.get("THEMAKER_LANG") or "ko").strip().lower()[:2]


def language(code=None):
    """AI 가 돌려주는 이름의 언어를 정한다. language("en") / language("ko").

    >>> language("en")
    >>> vision("object", img)      # name 이 영어로 온다
    """
    global LANG
    if code:
        LANG = str(code).strip().lower()[:2]
    return LANG

# 기능명(영문 기본) -> (엔드포인트, 기본 파라미터)
_API = {
    "object":     ("/object/object_search", {}),
    "pose":       ("/object/object_pose", {}),
    "seg":        ("/object/object_seg", {}),
    "hand":       ("/object/hand", {}),
    "face":       ("/face/face_detect", {}),
    "face_attr":  ("/face/face_analyze", {}),
    "distance":   ("/face/mesh", {}),
    # 사진을 보고 답한다 — 물으면 그 질문에, 안 물으면 사진 설명
    "look":       ("/vlm/look", {}),
    "ocr":        ("/code/ocr", {}),
    "qr":         ("/code/barcode", {}),
    "bg_remove":  ("/gan/portrait", {}),
    "sr":         ("/gan/sr", {}),
    "depth":      ("/gan/depth", {}),
    "mask":       ("/face/mask_detect", {}),
}

# 한글 이름도 그대로 쓸 수 있다
_ALIAS_KO = {
    "사물": "object", "자세": "pose", "분할": "seg", "손": "hand",
    "얼굴": "face", "얼굴분석": "face_attr", "얼굴거리": "distance",
    "보기": "look", "설명": "look", "질문": "look",
    "글자": "ocr", "큐알": "qr", "배경제거": "bg_remove", "화질개선": "sr", "깊이지도": "depth", "깊이": "depth",
    "마스크": "mask",
}


class TheMakerError(RuntimeError):
    pass


def _post(url, data=None, files=None, timeout=120):
    """multipart/form-data POST (표준 라이브러리만 사용)."""
    boundary = "----themaker%d" % int(time.time() * 1000)
    body = b""
    for k, v in (data or {}).items():
        body += ("--%s\r\nContent-Disposition: form-data; name=\"%s\"\r\n\r\n%s\r\n"
                 % (boundary, k, v)).encode("utf-8")
    for k, (name, blob, mime) in (files or {}).items():
        body += ("--%s\r\nContent-Disposition: form-data; name=\"%s\"; filename=\"%s\"\r\n"
                 "Content-Type: %s\r\n\r\n" % (boundary, k, name, mime)).encode("utf-8")
        body += blob + b"\r\n"
    body += ("--%s--\r\n" % boundary).encode("utf-8")
    req = urllib.request.Request(
        SERVER + url, data=body,
        headers={"Content-Type": "multipart/form-data; boundary=" + boundary})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.URLError as ex:
        code = getattr(ex, "code", None)
        if code == 404:
            raise TheMakerError(
                "그런 기능이 서버에 없어요: %s\n"
                "The Maker 를 최신으로 올렸는지 확인해 주세요." % url)
        if code == 503:
            raise TheMakerError("AI 를 준비하는 중이에요. 조금만 기다렸다 다시 실행해 주세요.")
        if code:
            raise TheMakerError("서버가 오류를 냈어요 (%s): %s" % (code, url))
        raise TheMakerError(
            "The Maker 서버에 연결할 수 없어요. run.bat 이 켜져 있는지 확인하세요. (%s)" % ex)


def _get(url, timeout=30):
    """GET 요청 (목록 같은 것)."""
    try:
        with urllib.request.urlopen(SERVER + url, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.URLError as ex:
        raise TheMakerError(
            "The Maker 서버에 연결할 수 없어요. run.bat 이 켜져 있는지 확인하세요. (%s)" % ex)


def _delete(url, timeout=30):
    """DELETE 요청 (지우기)."""
    req = urllib.request.Request(SERVER + url, method="DELETE")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.URLError as ex:
        raise TheMakerError(
            "The Maker 서버에 연결할 수 없어요. run.bat 이 켜져 있는지 확인하세요. (%s)" % ex)


def _b64_to_image(b64):
    """base64 글자 -> 이미지(numpy). 투명(알파) 정보가 있으면 살린다."""
    import base64
    raw = b64.split(",", 1)[-1]                  # data:image/png;base64,... 형태도 허용
    try:
        buf = np.frombuffer(base64.b64decode(raw), np.uint8)
    except Exception:
        raise TheMakerError("이미지를 읽을 수 없어요.")
    img = cv2.imdecode(buf, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise TheMakerError("이미지를 읽을 수 없어요.")
    return img


def _flatten(image):
    """투명한 이미지는 흰 바탕 위에 올려 준다 (jpg 로 보낼 때 필요)."""
    if isinstance(image, np.ndarray) and image.ndim == 3 and image.shape[2] == 4:
        bgr = image[:, :, :3].astype(np.float32)
        a = (image[:, :, 3:4].astype(np.float32)) / 255.0
        return (bgr * a + 255.0 * (1 - a)).astype(np.uint8)
    return image


def _to_jpg(image):
    """경로 문자열 / numpy 배열 -> jpg bytes."""
    if isinstance(image, str):
        img = cv2.imread(image)
        if img is None:
            raise TheMakerError("이미지를 읽을 수 없어요: %s" % image)
    elif isinstance(image, np.ndarray):
        img = image
    else:
        raise TheMakerError("image 는 파일 경로나 camera() 결과여야 해요.")
    ok, buf = cv2.imencode(".jpg", _flatten(img))
    if not ok:
        raise TheMakerError("이미지 인코딩 실패")
    return buf.tobytes()


_model_map = {}


def _resolve_model(name):
    """가르치기에서 입력한 이름(제목)으로도 찾을 수 있게 해 준다.

    저장 이름은 공백이 "-" 로 바뀌고 소문자가 되므로("우리 반 얼굴" -> "우리-반-얼굴"),
    학생이 제목 그대로 써도 동작하도록 한 번 대조한다.
    """
    if not _model_map:
        for m in my_models():
            _model_map[m["name"].lower()] = m["name"]
            _model_map[str(m.get("title", "")).strip().lower()] = m["name"]
    hit = _model_map.get(name.strip().lower())
    if hit:
        return hit
    if _model_map:
        raise TheMakerError(
            "그런 이름의 모델이 없어요: %s\n가지고 있는 모델: %s"
            % (name, ", ".join(sorted(set(_model_map.values())))))
    return name                    # 목록을 못 받아온 경우엔 그대로 시도


def vision(kind, image, prompt=None, **params):
    """AI 실행. kind: "object","face","look","tag","ocr","bg_remove" 등 (한글도 가능).

    >>> r = vision("object", img)
    >>> r = vision("look", img, prompt="사람이 몇 명이야?")
    >>> r = vision("look", img)                  # 안 물으면 사진 설명 {"answer": "..."}
    >>> r = vision("my:my-ai", img)              # 가르치기에서 저장한 모델

    서버가 준 값을 그대로 돌려준다 (사전 또는 목록).
    무엇이 왔는지 모를 땐 print(r) 로 확인하면 된다.
    그림으로 오는 기능(배경제거·화질개선)은 바로 쓸 수 있게 이미지로 풀어 준다.
    분할은 {"image": 칠한 그림, "object": [찾은 것들]} 로 온다 — show(r["image"]).
    """
    kind = str(kind).strip()
    kind = _ALIAS_KO.get(kind, kind)

    if kind.startswith("my:") or kind.startswith("내모델:") or kind.startswith("custom:"):
        slug = _resolve_model(kind.split(":", 1)[1].strip())
        url, data = "/custom/predict?model=" + urllib.parse.quote(slug), {}
    elif kind in _API:
        url, base = _API[kind]
        data = dict(base)
    else:
        raise TheMakerError("모르는 기능이에요: %s\n가능한 기능: %s"
                            % (kind, ", ".join(sorted(_API))))
    if prompt is not None:
        data["prompt"] = prompt
    data.setdefault("lang", LANG)             # 화면·라이브러리 언어를 서버에 함께 알린다
    data.update({k: str(v) for k, v in params.items()})

    # 서버는 이 값들을 주소(쿼리)로 받는다 — 본문에 넣으면 조용히 무시된다.
    # (prompt·lang 이 안 먹던 원인)
    if data:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(data)
    j = _post(url, files={"uploadFile": ("input.jpg", _to_jpg(image), "image/jpeg")})
    if j.get("result") != "ok":
        raise TheMakerError("AI 실행 실패: %s" % j.get("data"))
    data = j.get("data")
    # 그림으로 오는 기능은 base64 글자 대신 이미지로 풀어 준다 (show·save 에 바로 넣게)
    if kind in ("bg_remove", "sr", "depth") and isinstance(data, str):
        return _b64_to_image(data)
    # 분할은 칠한 그림과 찾은 이름을 함께 준다 — 그림만 이미지로 풀어 준다
    if kind == "seg" and isinstance(data, dict) and isinstance(data.get("image"), str):
        return dict(data, image=_b64_to_image(data["image"]))
    return data                                  # 그 밖에는 서버가 준 그대로


def chat(text, db=None, lang=None):
    """사진 없이 물어보기 — 같은 AI 에게 글로만 묻는다.

    >>> print(chat("무지개는 왜 생겨?"))
    >>> print(chat("제갈량은 누구야?", db="삼국지"))   # 내가 만든 자료에서 찾아 답하기
    앞에 한 말은 기억하지 않는다 (한 번 묻고 한 번 답한다).
    """
    q = str(text).strip()
    if not q:
        raise TheMakerError("물어볼 말을 적어 주세요.")
    args = {"prompt": q, "lang": lang or LANG}
    if db:
        args["db"] = str(db)
    url = ("/chat/rag?" if db else "/chat/ask?") + urllib.parse.urlencode(args)
    j = _post(url)
    if j.get("result") != "ok":
        raise TheMakerError("AI 실행 실패: %s" % j.get("data"))
    return j["data"]["answer"]


def db_add(title, text):
    """자료 만들기 — 이 글에서 찾아 답하게 한다.

    >>> db_add("삼국지", open("삼국지.txt", encoding="utf-8").read())
    """
    body = str(text).strip()
    if not body:
        raise TheMakerError("자료로 쓸 글을 넣어 주세요.")
    j = _post("/chat/db", data={"title": str(title), "text": body})
    if j.get("result") != "ok":
        raise TheMakerError("자료를 만들지 못했어요: %s" % j.get("data"))
    return j["data"]


def db_list():
    """만들어 둔 자료 목록."""
    j = _get("/chat/db")
    return j.get("data") if j.get("result") == "ok" else []


def db_delete(db):
    """자료 지우기.

    >>> db_delete("삼국지")
    """
    name = str(db).strip()
    if not name:
        raise TheMakerError("지울 자료 이름을 적어 주세요.")
    j = _delete("/chat/db/" + urllib.parse.quote(name))
    if j.get("result") != "ok":
        raise TheMakerError("지우지 못했어요: %s" % j.get("data"))
    return j["data"]


def db_find(question, db, top_k=4):
    """답을 만들지 않고, 자료에서 비슷한 곳만 찾아 본다 (어디서 가져오는지 보기)."""
    url = "/chat/find?" + urllib.parse.urlencode(
        {"db": str(db), "prompt": str(question), "top_k": int(top_k)})
    j = _post(url)
    if j.get("result") != "ok":
        raise TheMakerError("찾지 못했어요: %s" % j.get("data"))
    return j["data"]["found"]


def models():
    """가져다 둔 YOLO 모델 파일 목록 — detect() 에 그대로 넣으면 된다.

    >>> models()
    ['cat.pt', 'my-best.pt']
    >>> r = detect(models()[0], camera())

    파일은 [설정·점검]의 [모델 폴더 열기]로 열리는 폴더에 넣는다
    (문서\\The Maker\\models). 넣자마자 이 목록에 나온다.
    """
    try:
        j = _get("/object/model_files")
        return list((j.get("data") or {}).get("files") or [])
    except Exception:
        return []


def models_folder():
    """모델 파일을 넣는 폴더의 경로 — 아이에게 어디에 넣는지 알려줄 때."""
    try:
        j = _get("/object/model_files")
        return (j.get("data") or {}).get("folder", "")
    except Exception:
        return ""


def my_models():
    """가르치기에서 저장한 내 모델 목록 — 이름·종류·클래스까지.

    >>> my_models()
    [{'name': '가위바위보', 'kind': '손모양', 'classes': ['가위', '바위', '보']}, ...]
    이름을 그대로 vision("my:이름", img) 에 넣으면 된다.
    """
    try:
        with urllib.request.urlopen(SERVER + "/custom/models", timeout=10) as r:
            j = json.loads(r.read().decode("utf-8"))
        return [{"name": m.get("slug"), "title": m.get("title") or m.get("slug"),
                 "kind": _KIND_KO.get(m.get("kind"), m.get("kind")),
                 "classes": m.get("labels") or []}
                for m in (j.get("data") or [])]
    except Exception:
        return []


def camera(index=0):
    """웹캠에서 한 장 찍기 -> 이미지(numpy)."""
    cap = cv2.VideoCapture(index, cv2.CAP_DSHOW if os.name == "nt" else 0)
    if not cap.isOpened():
        raise TheMakerError("웹캠을 열 수 없어요. 다른 프로그램이 쓰고 있지 않은지 확인하세요.")
    for _ in range(3):                      # 워밍업 프레임
        cap.read()
    ok, frame = cap.read()
    cap.release()
    if not ok:
        raise TheMakerError("웹캠에서 사진을 가져오지 못했어요.")
    return frame


def load(path):
    """이미지 파일 열기 -> 이미지(numpy)."""
    img = cv2.imread(path)
    if img is None:
        raise TheMakerError("이미지를 읽을 수 없어요: %s" % path)
    return img


def save(image, path="result.jpg"):
    """이미지를 파일로 저장. png 로 저장하면 투명 배경도 그대로 남는다."""
    img = image if str(path).lower().endswith(".png") else _flatten(image)
    cv2.imwrite(path, img)
    return path


def _boxes_of(result):
    """어떤 모양으로 와도 박스가 든 항목들을 찾아낸다.

    목록 [{box...}, ...] 도 되고,
    사전 {"object": [...]} 처럼 안에 목록이 든 것도 된다.
    """
    if isinstance(result, dict):
        out = []
        for key, val in result.items():
            if isinstance(val, list):
                out += [v for v in val if isinstance(v, dict)]
        if out:
            return out
        return [result]                           # 항목 하나짜리 사전
    if isinstance(result, list):
        return [v for v in result if isinstance(v, dict)]
    return []


def draw(image, result):
    """인식 결과(박스/이름)를 이미지에 그려서 돌려준다.

    vision() 이 준 값을 그대로 넣으면 된다 — 목록이든 사전이든 알아서 찾는다.
    """
    img = _flatten(image).copy()
    items = _boxes_of(result)
    for it in items:
        if not isinstance(it, dict):
            continue
        box = it.get("box") or it.get("bbox")
        name = (it.get("name") or it.get("label") or it.get("class")
                or it.get("gesture") or it.get("text") or it.get("emotion") or "")
        score = it.get("score") or it.get("conf")
        if box and len(box) == 4:
            x1, y1, x2, y2 = [int(v) for v in box]
            cv2.rectangle(img, (x1, y1), (x2, y2), (255, 176, 46), 2)
            if isinstance(score, (int, float)):
                pct = score * 100 if score <= 1 else score      # 0~1 또는 0~100 둘 다 지원
                tag = "%s %.0f%%" % (name, pct)
            else:
                tag = str(name)
            # 한글이 섞이면 PIL 로 그린다 — cv2.putText 는 한글을 네모로 그린다
            if any("\uac00" <= ch <= "\ud7a3" for ch in tag):
                img = _put_text(img, tag, x1, max(0, y1 - 24), 20, "orange", 0, center=False)
            else:
                cv2.putText(img, tag, (x1, max(18, y1 - 6)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 176, 46), 2)
    return img


def show(image, result=None, title="The Maker", wait=True, window=False):
    """결과를 보여준다. result 를 주면 박스를 그려서 보여준다.

    파이썬 페이지에서 실행하면 화면(결과 칸)에 바로 나온다.
    배포한 프로그램(exe)으로 실행하면 따로 창이 떠서 보여준다.
    window=True 를 주면 어디서든 창으로 띄운다.
    """
    img = draw(image, result) if result is not None else image
    sid = os.environ.get("THEMAKER_SID", "")
    if sid and not window:
        try:
            _post("/pycode/frame?sid=" + urllib.parse.quote(sid)
                  + "&caption=" + urllib.parse.quote(str(title)),
                  files={"uploadFile": ("f.jpg", _to_jpg(img), "image/jpeg")},
                  timeout=20)
            return img
        except Exception:
            pass                      # 화면으로 못 보내면 창으로 대신 띄운다
    cv2.imshow(title, _flatten(img))
    if wait:
        cv2.waitKey(0)
        cv2.destroyAllWindows()
    else:
        cv2.waitKey(1)
    return img


def _wav_bytes(samples, sr=16000):
    """float32 [-1,1] -> 16bit WAV bytes."""
    import io
    import wave
    buf = io.BytesIO()
    pcm = np.clip(np.asarray(samples, dtype=np.float32), -1, 1)
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((pcm * 32767).astype(np.int16).tobytes())
    return buf.getvalue()


def listen(seconds=4, lang="ko"):
    """마이크로 녹음해서 글자로 바꿔 준다 (음성 인식).

    >>> text = listen(4)          # 4초 동안 듣기
    >>> print(text)
    처음 한 번은 모델을 여느라 시간이 걸린다.
    """
    try:
        import sounddevice as sd
    except ImportError:
        raise TheMakerError(
            "마이크를 쓰려면 sounddevice 가 필요해요.\n"
            "설치: pip install sounddevice")
    sr = 16000
    print("듣는 중... (%d초)" % seconds)
    rec = sd.rec(int(seconds * sr), samplerate=sr, channels=1, dtype="float32")
    sd.wait()
    return wav_to_text(_wav_bytes(rec.reshape(-1), sr), lang=lang)


def wav_to_text(wav, lang="ko"):
    """소리를 글자로 바꾼다. wav 는 .wav 파일 경로 또는 WAV 바이트."""
    if isinstance(wav, str):
        with open(wav, "rb") as f:
            raw = f.read()
    elif isinstance(wav, (bytes, bytearray)):
        raw = bytes(wav)
    else:
        raise TheMakerError("wav 는 .wav 파일 경로이거나 WAV 데이터여야 해요.")
    j = _post("/speech/stt?lang=" + urllib.parse.quote(lang),
              files={"uploadFile": ("a.wav", raw, "audio/wav")}, timeout=180)
    if j.get("result") != "ok":
        raise TheMakerError("음성 인식 실패: %s" % j.get("data"))
    return (j.get("data") or {}).get("text", "")


def speak(text, voice="F1", lang="ko", speed=1.0, wait=True, save_as=None):
    """글자를 소리로 읽어 준다 (음성 합성).

    >>> speak("안녕하세요, 저는 인공지능이에요")
    >>> speak("Hello there", lang="en", voice="M1")
    >>> speak("안녕", save_as="hello.wav")     # 파일로 저장만
    voice : F1~F5(여자), M1~M5(남자)
    """
    if not str(text).strip():
        return None                          # 할 말이 없으면 그냥 넘어간다
    req = json.dumps({"text": str(text), "voice": voice,
                      "lang": lang, "speed": float(speed)}).encode("utf-8")
    r = urllib.request.Request(SERVER + "/speech/tts", data=req,
                               headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(r, timeout=180) as resp:
            raw = resp.read()
            ctype = resp.headers.get("Content-Type", "")
    except urllib.error.URLError as ex:
        raise TheMakerError("The Maker 서버에 연결할 수 없어요. (%s)" % ex)
    if "audio" not in ctype:                       # 실패는 JSON 으로 온다
        try:
            msg = json.loads(raw.decode("utf-8")).get("data")
        except Exception:
            msg = raw[:200]
        raise TheMakerError("소리를 만들지 못했어요: %s" % msg)

    if save_as:
        with open(save_as, "wb") as f:
            f.write(raw)
        return save_as
    _play_wav(raw, wait=wait)
    return None


def _play_wav(raw, wait=True):
    """WAV 를 스피커로 재생."""
    import io
    import wave
    try:
        import sounddevice as sd
    except ImportError:
        raise TheMakerError("소리를 내려면 sounddevice 가 필요해요.\n"
                            "설치: pip install sounddevice")
    with wave.open(io.BytesIO(raw), "rb") as w:
        sr, ch = w.getframerate(), w.getnchannels()
        a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    a = a.astype(np.float32) / 32768.0
    if ch > 1:
        a = a.reshape(-1, ch)
    try:
        sd.play(a, sr, device=_out_device())
    except Exception:
        _audio["dev"] = None
        sd.play(a, sr)
    if wait:
        sd.wait()


def detect(model_path, image, conf=0.3):
    """가져다 둔 YOLO 모델 파일로 인식한다.

    >>> r = detect("cat.pt", camera())          # 모델 폴더에 있는 이름
    >>> r = detect(models()[0], camera())       # 목록에서 골라서
    >>> show(camera(), r)

    model_path : 모델 폴더의 파일 이름. models() 로 목록을 볼 수 있다.
                 파일은 [설정·점검]의 [모델 폴더 열기]로 열리는 곳에 넣는다.
    conf       : 이 확신도보다 낮은 결과는 버린다 (0~1).
    돌려주는 것: [{"name": 이름, "score": 0~100, "box": [x1,y1,x2,y2]}, ...]

    블록의 "모델 파일로 찾기" 와 같은 것을 부른다 — 서버가 모델을 한 번만
    올려 두고 함께 쓰므로, 학생 코드가 모델을 또 읽지 않는다.
    """
    name = os.path.basename(str(model_path).strip())
    url = "/object/detect_file?" + urllib.parse.urlencode(
        {"model": name, "conf": conf, "lang": LANG})
    j = _post(url, files={"uploadFile": ("input.jpg", _to_jpg(image), "image/jpeg")})
    if j.get("result") != "ok":
        raise TheMakerError(str(j.get("data")))
    return (j.get("data") or {}).get("object", [])


__all__ = [
    # 기본
    "camera", "load", "save", "show", "draw", "my_models", "models", "models_folder",
    # AI
    "vision", "detect",
    # 소리 (말)
    "listen", "wav_to_text", "speak",
    # 이미지 편집 — 크기·방향·자르기·합치기
    "resize", "rotate", "flip", "crop", "crop_xy", "crop_found",
    "attach", "put_on", "put_on_xy", "put_sticker",
    # 이미지 편집 — 색·그리기
    "adjust", "img_filter", "draw_text", "draw_text_xy",
    "draw_rect", "draw_rect_xy", "draw_circle", "draw_circle_xy",
    "draw_line", "draw_line_xy",
    # 이미지 살펴보기
    "size_of", "color_at", "color_at_xy", "main_color",
    # 소리 만들기
    "play_note", "beep", "play_melody", "play_hz", "speaker",
    # 사진 없이 대화 · 내 자료에서 찾아 답하기
    "chat", "db_add", "db_list", "db_find", "db_delete",
    # 설정
    "language",
    "SERVER", "TheMakerError",
]


# ================================================================= 이미지 편집
# 블록 코딩의 "이미지 편집" 블록과 1:1 로 대응한다.
# 아홉 칸(tl tc tr / ml mc mr / bl bc br) 을 쓰는 것과, 좌표(_xy) 를 쓰는 것이 짝을 이룬다.

# 아홉 칸 -> 비율 좌표 (0~1)
_P9 = {"tl": (.12, .12), "tc": (.5, .12), "tr": (.88, .12),
       "ml": (.12, .5),  "mc": (.5, .5),  "mr": (.88, .5),
       "bl": (.12, .88), "bc": (.5, .88), "br": (.88, .88)}
_P9_KO = {"왼위": "tl", "가운데위": "tc", "오른위": "tr",
          "왼쪽": "ml", "가운데": "mc", "오른쪽": "mr",
          "왼아래": "bl", "가운데아래": "bc", "오른아래": "br"}

# 색 이름 -> BGR
_COLORS = {
    "black": (0, 0, 0), "white": (255, 255, 255), "gray": (128, 128, 128),
    "red": (0, 0, 255), "orange": (0, 140, 255), "yellow": (0, 215, 255),
    "green": (60, 175, 60), "blue": (200, 80, 40), "navy": (100, 60, 30),
    "purple": (180, 60, 130), "pink": (170, 150, 255), "brown": (40, 70, 120),
}
_COLORS_KO = {"검정": "black", "하양": "white", "회색": "gray", "빨강": "red",
              "주황": "orange", "노랑": "yellow", "초록": "green", "파랑": "blue",
              "남색": "navy", "보라": "purple", "분홍": "pink", "갈색": "brown"}

_MAX_PX = 2400          # 확대를 반복해도 폭주하지 않게


def _bgr(color):
    """색 이름 또는 (B,G,R) 을 BGR 로. '#ff0000' 도 받는다."""
    if isinstance(color, (tuple, list)) and len(color) >= 3:
        return tuple(int(c) for c in color[:3])
    name = str(color).strip().lower()
    name = _COLORS_KO.get(str(color).strip(), name)
    if name.startswith("#") and len(name) == 7:
        return (int(name[5:7], 16), int(name[3:5], 16), int(name[1:3], 16))
    if name in _COLORS:
        return _COLORS[name]
    raise TheMakerError("모르는 색이에요: %s (쓸 수 있는 색: %s)"
                        % (color, ", ".join(_COLORS)))


def _spot(img, where):
    """아홉 칸 이름 -> 실제 좌표 (x, y)."""
    key = _P9_KO.get(str(where).strip(), str(where).strip().lower())
    if key not in _P9:
        raise TheMakerError("모르는 자리예요: %s (tl tc tr ml mc mr bl bc br)" % where)
    h, w = img.shape[:2]
    fx, fy = _P9[key]
    return int(w * fx), int(h * fy)


def _img(image):
    """이미지가 맞는지 확인하고 복사본을 준다 (원본을 건드리지 않게)."""
    if not isinstance(image, np.ndarray) or image.ndim < 2:
        raise TheMakerError("사진이 아니에요. camera() 나 load() 로 만든 사진을 넣어 주세요.")
    return _flatten(image).copy()


# ---------------------------------------------------------------- 크기 · 방향
def resize(image, factor=1):
    """크기 바꾸기. factor 가 1보다 크면 가운데를 잘라 확대한다(디지털 줌).

    >>> big = resize(img, 2)      # 2배로 가까이
    >>> small = resize(img, 0.5)  # 절반 크기
    """
    img = _img(image)
    f = max(0.1, min(8.0, float(factor)))
    h, w = img.shape[:2]
    if f > 1:
        cw, ch = int(w / f), int(h / f)
        x, y = (w - cw) // 2, (h - ch) // 2
        img = img[y:y + ch, x:x + cw]
        return cv2.resize(img, (w, h), interpolation=cv2.INTER_LINEAR)
    nw, nh = max(1, int(w * f)), max(1, int(h * f))
    return cv2.resize(img, (nw, nh), interpolation=cv2.INTER_AREA)


def rotate(image, degree=90):
    """돌리기. 90 / 180 / 270 은 깔끔하게, 그 외 각도는 검은 여백이 생긴다."""
    img = _img(image)
    d = int(degree) % 360
    if d == 0:
        return img
    if d == 90:
        return cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
    if d == 180:
        return cv2.rotate(img, cv2.ROTATE_180)
    if d == 270:
        return cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
    h, w = img.shape[:2]
    m = cv2.getRotationMatrix2D((w / 2, h / 2), -d, 1.0)
    return cv2.warpAffine(img, m, (w, h), borderValue=(255, 255, 255))


def flip(image, direction="h"):
    """뒤집기. h = 좌우(거울), v = 위아래."""
    img = _img(image)
    d = str(direction).lower()
    if d in ("h", "가로", "좌우"):
        return cv2.flip(img, 1)
    if d in ("v", "세로", "위아래"):
        return cv2.flip(img, 0)
    raise TheMakerError('h(좌우) 또는 v(위아래) 를 넣어 주세요.')


# ---------------------------------------------------------------- 자르기
def crop(image, where="mc"):
    """아홉 칸 중 한 칸만 오려내기 (원본의 절반 크기)."""
    img = _img(image)
    h, w = img.shape[:2]
    cx, cy = _spot(img, where)
    cw, ch = w // 2, h // 2
    x = max(0, min(w - cw, cx - cw // 2))
    y = max(0, min(h - ch, cy - ch // 2))
    return img[y:y + ch, x:x + cw].copy()


def crop_xy(image, x, y, width, height):
    """좌표로 오려내기."""
    img = _img(image)
    h, w = img.shape[:2]
    x, y = max(0, int(x)), max(0, int(y))
    x2, y2 = min(w, x + max(1, int(width))), min(h, y + max(1, int(height)))
    if x2 <= x or y2 <= y:
        raise TheMakerError("자를 수 없는 자리예요. 사진 크기는 %d x %d 예요." % (w, h))
    return img[y:y2, x:x2].copy()


def crop_found(image, result, index=0):
    """인식 결과에서 찾은 것만 오려내기.

    >>> faces = vision("face", img)
    >>> face = crop_found(img, faces)      # 첫 번째 얼굴만
    """
    items = _boxes_of(result)
    boxes = [it["box"] for it in items if it.get("box")]
    if not boxes:
        raise TheMakerError("찾은 것이 없어요.")
    if index >= len(boxes):
        raise TheMakerError("%d 번째는 없어요. %d 개 찾았어요." % (index + 1, len(boxes)))
    x1, y1, x2, y2 = [int(v) for v in boxes[index][:4]]
    return crop_xy(image, x1, y1, x2 - x1, y2 - y1)


# ---------------------------------------------------------------- 합치기
def attach(image_a, image_b, direction="h"):
    """두 사진을 나란히 붙이기. h = 가로로, v = 세로로.

    >>> both = attach(img, flip(img, "h"), "h")     # 원본 옆에 거울 사진
    """
    a, b = _img(image_a), _img(image_b)
    d = str(direction).lower()
    if d in ("h", "가로"):
        h = min(a.shape[0], b.shape[0], _MAX_PX)
        a = cv2.resize(a, (int(a.shape[1] * h / a.shape[0]), h))
        b = cv2.resize(b, (int(b.shape[1] * h / b.shape[0]), h))
        return np.hstack([a, b])
    if d in ("v", "세로"):
        w = min(a.shape[1], b.shape[1], _MAX_PX)
        a = cv2.resize(a, (w, int(a.shape[0] * w / a.shape[1])))
        b = cv2.resize(b, (w, int(b.shape[0] * w / b.shape[1])))
        return np.vstack([a, b])
    raise TheMakerError('h(가로) 또는 v(세로) 를 넣어 주세요.')


_SIZES = {"tiny": .15, "small": .25, "half": .5, "big": .75, "full": 1.0,
          "아주작게": .15, "작게": .25, "반": .5, "크게": .75, "가득": 1.0}


def put_on(image_a, image_b, size="half", where="br"):
    """사진 위에 사진 얹기. size = tiny small half big full, where = 아홉 칸.

    >>> r = put_on(배경, 얼굴, "small", "br")        # 오른쪽 아래에 작게
    """
    a = _img(image_a)
    b = _img(image_b)
    f = _SIZES.get(str(size).strip().lower(), _SIZES.get(str(size).strip(), .5))
    bw = max(1, int(a.shape[1] * f))
    bh = max(1, int(b.shape[0] * bw / b.shape[1]))
    cx, cy = _spot(a, where)
    return put_on_xy(a, b, cx - bw // 2, cy - bh // 2, bw / b.shape[1])


def put_on_xy(image_a, image_b, x, y, scale=1.0):
    """a 위 (x, y) 자리에 b 를 얹기. scale 로 크기 조절."""
    a = _img(image_a)
    b = _flatten(image_b)
    s = max(0.02, float(scale))
    bw, bh = max(1, int(b.shape[1] * s)), max(1, int(b.shape[0] * s))
    b = cv2.resize(b, (bw, bh))
    x, y = int(x), int(y)
    H, W = a.shape[:2]
    x1, y1 = max(0, x), max(0, y)
    x2, y2 = min(W, x + bw), min(H, y + bh)
    if x2 <= x1 or y2 <= y1:
        return a                                   # 화면 밖이면 그대로
    a[y1:y2, x1:x2] = b[y1 - y:y2 - y, x1 - x:x2 - x]
    return a


def put_sticker(image, sticker_image, scale=1.0):
    """찾은 얼굴마다 스티커를 붙인다."""
    img = _img(image)
    faces = vision("face", img)
    boxes = [it["box"] for it in _boxes_of(faces) if it.get("box")]
    if not boxes:
        return img
    for x1, y1, x2, y2 in [[int(v) for v in b[:4]] for b in boxes]:
        w = max(1, int((x2 - x1) * float(scale)))
        img = put_on_xy(img, sticker_image, x1 + (x2 - x1 - w) // 2, y1,
                         w / max(1, _flatten(sticker_image).shape[1]))
    return img


# ---------------------------------------------------------------- 색
def adjust(image, what="bright", value=0):
    """밝기·대비·채도 바꾸기. value 는 -100 ~ 100.

    what : "bright"(밝기) / "contrast"(대비) / "saturate"(채도)
    >>> 밝게 = adjust(img, "bright", 40)
    """
    img = _img(image)
    v = max(-100, min(100, float(value)))
    w = str(what).strip().lower()
    if w in ("bright", "밝기"):
        return cv2.convertScaleAbs(img, alpha=1.0, beta=v * 1.27)
    if w in ("contrast", "대비"):
        return cv2.convertScaleAbs(img, alpha=1.0 + v / 100.0, beta=0)
    if w in ("saturate", "채도"):
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV).astype(np.float32)
        hsv[:, :, 1] = np.clip(hsv[:, :, 1] * (1.0 + v / 100.0), 0, 255)
        return cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)
    raise TheMakerError("bright(밝기) / contrast(대비) / saturate(채도) 중에서 골라 주세요.")


def img_filter(image, kind="gray"):
    """사진 효과. gray sepia blur sharpen invert edge

    (파이썬에 filter 라는 기본 기능이 이미 있어서 img_filter 로 이름 지었어요)
    """
    img = _img(image)
    k = str(kind).strip().lower()
    if k in ("gray", "흑백"):
        return cv2.cvtColor(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), cv2.COLOR_GRAY2BGR)
    if k in ("sepia", "세피아"):
        m = np.array([[.272, .534, .131], [.349, .686, .168], [.393, .769, .189]])
        return np.clip(img[:, :, ::-1] @ m.T, 0, 255).astype(np.uint8)[:, :, ::-1]
    if k in ("blur", "흐리게"):
        return cv2.GaussianBlur(img, (0, 0), 6)
    if k in ("sharpen", "선명하게"):
        kern = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]], np.float32)
        return cv2.filter2D(img, -1, kern)
    if k in ("invert", "반전"):
        return 255 - img
    if k in ("edge", "윤곽"):
        e = cv2.Canny(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), 80, 180)
        return cv2.cvtColor(255 - e, cv2.COLOR_GRAY2BGR)
    raise TheMakerError("gray sepia blur sharpen invert edge 중에서 골라 주세요.")


# ---------------------------------------------------------------- 그리기
_font_cache = {}


def _font(size):
    """한글이 나오는 글꼴을 찾는다 (윈도우 맑은고딕 등)."""
    from PIL import ImageFont
    size = int(size)
    if size in _font_cache:
        return _font_cache[size]
    here = os.path.dirname(os.path.abspath(__file__))
    spots = [os.path.join(here, "view_project", "fonts", "NanumGothic.ttf"),
             r"C:\Windows\Fonts\malgun.ttf", r"C:\Windows\Fonts\gulim.ttc",
             "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
             "/System/Library/Fonts/AppleSDGothicNeo.ttc"]
    for p in spots:
        if os.path.exists(p):
            try:
                f = ImageFont.truetype(p, size)
                _font_cache[size] = f
                return f
            except Exception:
                pass
    f = ImageFont.load_default()                   # 없으면 기본 글꼴(한글은 깨질 수 있다)
    _font_cache[size] = f
    return f


def draw_text(image, text, where="tc", size=40, color="black", degree=0):
    """사진에 글자 쓰기 (아홉 칸 자리).

    (파이썬에서 text 는 흔한 변수 이름이라 draw_text 로 이름 지었어요)
    """
    img = _img(image)
    cx, cy = _spot(img, where)
    return _put_text(img, text, cx, cy, size, color, degree, center=True)


def draw_text_xy(image, text, x, y, size=40, color="black", degree=0):
    """좌표를 정해서 글자 쓰기."""
    return _put_text(_img(image), text, int(x), int(y), size, color, degree, center=False)


def _put_text(img, text, x, y, size, color, degree, center):
    from PIL import Image, ImageDraw
    b, g, r = _bgr(color)
    pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    font = _font(size)
    s = str(text)

    if int(degree) % 360 == 0:
        d = ImageDraw.Draw(pil)
        if center:
            box = d.textbbox((0, 0), s, font=font)
            x -= (box[2] - box[0]) // 2
            y -= (box[3] - box[1]) // 2
        d.text((x, y), s, font=font, fill=(r, g, b))
    else:
        tmp = Image.new("RGBA", pil.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(tmp)
        box = d.textbbox((0, 0), s, font=font)
        tw, th = box[2] - box[0], box[3] - box[1]
        lay = Image.new("RGBA", (tw + 20, th + 20), (0, 0, 0, 0))
        ImageDraw.Draw(lay).text((10, 10), s, font=font, fill=(r, g, b, 255))
        lay = lay.rotate(float(degree), expand=True, resample=Image.BICUBIC)
        px = x - lay.width // 2 if center else x
        py = y - lay.height // 2 if center else y
        tmp.paste(lay, (int(px), int(py)), lay)
        pil = Image.alpha_composite(pil.convert("RGBA"), tmp).convert("RGB")
    return cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)


def draw_rect(image, where="mc", fill="line", color="red"):
    """네모 그리기 (아홉 칸 자리). fill = fill(채우기) / line(선만)."""
    img = _img(image)
    h, w = img.shape[:2]
    cx, cy = _spot(img, where)
    bw, bh = w // 4, h // 4
    return draw_rect_xy(img, cx - bw // 2, cy - bh // 2, bw, bh, fill, color)


def draw_rect_xy(image, x, y, width, height, fill="line", color="red"):
    """좌표로 네모 그리기."""
    img = _img(image)
    thick = -1 if str(fill).lower() in ("fill", "채우기") else max(2, img.shape[1] // 250)
    cv2.rectangle(img, (int(x), int(y)), (int(x) + int(width), int(y) + int(height)),
                  _bgr(color), thick)
    return img


def draw_circle(image, where="mc", fill="line", color="red"):
    """동그라미 그리기 (아홉 칸 자리)."""
    img = _img(image)
    cx, cy = _spot(img, where)
    return draw_circle_xy(img, cx, cy, min(img.shape[:2]) // 6, fill, color)


def draw_circle_xy(image, x, y, radius=50, fill="line", color="red"):
    """좌표로 동그라미 그리기."""
    img = _img(image)
    thick = -1 if str(fill).lower() in ("fill", "채우기") else max(2, img.shape[1] // 250)
    cv2.circle(img, (int(x), int(y)), max(1, int(radius)), _bgr(color), thick)
    return img


def draw_line(image, start="tl", end="br", color="red"):
    """선 긋기 (아홉 칸 자리에서 자리로)."""
    img = _img(image)
    x1, y1 = _spot(img, start)
    x2, y2 = _spot(img, end)
    return draw_line_xy(img, x1, y1, x2, y2, color)


def draw_line_xy(image, x1, y1, x2, y2, color="red"):
    """좌표로 선 긋기."""
    img = _img(image)
    cv2.line(img, (int(x1), int(y1)), (int(x2), int(y2)), _bgr(color),
             max(2, img.shape[1] // 250))
    return img


# ---------------------------------------------------------------- 살펴보기
def size_of(image, what="w"):
    """사진 크기 알아보기. w = 너비, h = 높이."""
    img = _flatten(image)
    w = str(what).strip().lower()
    if w in ("w", "너비", "가로"):
        return int(img.shape[1])
    if w in ("h", "높이", "세로"):
        return int(img.shape[0])
    raise TheMakerError("w(너비) 또는 h(높이) 를 넣어 주세요.")


def color_at(image, where="mc"):
    """그 자리의 색 이름 알아보기."""
    img = _flatten(image)
    x, y = _spot(img, where)
    return color_at_xy(img, x, y)


def color_at_xy(image, x, y):
    """좌표의 색 이름 알아보기. 둘레를 평균 내서 정한다."""
    img = _flatten(image)
    h, w = img.shape[:2]
    x, y = max(0, min(w - 1, int(x))), max(0, min(h - 1, int(y)))
    patch = img[max(0, y - 4):y + 5, max(0, x - 4):x + 5]
    return _name_of(patch.reshape(-1, 3).mean(axis=0))


def main_color(image):
    """사진에서 가장 많은 색 이름."""
    img = _flatten(image)
    small = cv2.resize(img, (64, 64), interpolation=cv2.INTER_AREA)
    names = {}
    for px in small.reshape(-1, 3):
        n = _name_of(px)
        names[n] = names.get(n, 0) + 1
    return max(names.items(), key=lambda kv: kv[1])[0]


def _name_of(bgr):
    """BGR 값에 가장 가까운 색 이름 (한국어)."""
    b, g, r = [float(v) for v in bgr[:3]]
    best, dist = "black", 1e9
    for name, (cb, cg, cr) in _COLORS.items():
        d = (b - cb) ** 2 + (g - cg) ** 2 + (r - cr) ** 2
        if d < dist:
            best, dist = name, d
    for ko, en in _COLORS_KO.items():
        if en == best:
            return ko
    return best


# ================================================================= 소리 만들기
_NOTES = {"도": 261.63, "레": 293.66, "미": 329.63, "파": 349.23,
          "솔": 392.00, "라": 440.00, "시": 493.88,
          "높은도": 523.25, "도2": 523.25, "c2": 523.25,   # 한 옥타브 위
          "레2": 587.33, "미2": 659.26, "d2": 587.33, "e2": 659.26,
          "c": 261.63, "d": 293.66, "e": 329.63, "f": 349.23,
          "g": 392.00, "a": 440.00, "b": 493.88,
          "쉼": 0.0, "-": 0.0}                              # 0 = 소리 없이 쉬기
_SR = 22050


_audio = {"dev": "?"}          # 한 번 고르면 기억해 둔다


def _out_device():
    """소리를 낼 장치를 고른다.

    PortAudio 의 기본값(MME)은 윈도우 기본 장치와 다를 때가 많다 — 모니터
    HDMI 오디오가 잡히면 소리가 모니터로 나가 조용해 보인다. 그래서 윈도우
    기본 장치를 그대로 따르는 WASAPI 쪽 기본 출력을 우선 쓴다.
    THEMAKER_AUDIO 로 번호나 이름을 직접 줄 수도 있다."""
    if _audio["dev"] != "?":
        return _audio["dev"]
    dev = None
    try:
        import sounddevice as sd
        forced = (os.environ.get("THEMAKER_AUDIO") or "").strip()
        if forced:
            dev = int(forced) if forced.isdigit() else forced
        else:
            for api in sd.query_hostapis():                 # 윈도우: WASAPI = 기본 장치
                if "WASAPI" in str(api.get("name", "")).upper():
                    i = api.get("default_output_device", -1)
                    if i is not None and i >= 0:
                        dev = i
                    break
            if dev is None:                                 # 그 밖의 OS·구형 윈도우
                i = sd.default.device[1] if isinstance(sd.default.device, (list, tuple)) \
                    else sd.default.device
                dev = i if isinstance(i, int) and i >= 0 else None
    except Exception:
        dev = None
    _audio["dev"] = dev
    return dev


def speaker(which=None):
    """소리가 안 들릴 때 스피커를 직접 고른다.

    >>> speaker()        # 쓸 수 있는 스피커 목록을 보여줘요
    >>> speaker(4)       # 4번으로 정해요
    >>> speaker("Realtek")   # 이름 일부로도 돼요
    """
    try:
        import sounddevice as sd
    except ImportError:
        raise TheMakerError("소리를 내려면 sounddevice 가 필요해요.\n"
                            "설치: pip install sounddevice")
    if which is None:
        print("[스피커] 지금 쓰는 것:", _out_device())
        for i, d in enumerate(sd.query_devices()):
            if d.get("max_output_channels", 0) > 0:
                print("  %2d  %s" % (i, d.get("name", "")))
        print("speaker(번호) 로 골라요.")
        return _out_device()
    _audio["dev"] = int(which) if str(which).isdigit() else which
    return _audio["dev"]


def _play(wave_f32, wait=True):
    try:
        import sounddevice as sd
    except ImportError:
        raise TheMakerError("소리를 내려면 sounddevice 가 필요해요.\n"
                            "설치: pip install sounddevice")
    try:
        sd.play(wave_f32, _SR, device=_out_device())
    except Exception as ex:                     # 고른 장치가 안 되면 기본값으로 한 번 더
        _audio["dev"] = None
        try:
            sd.play(wave_f32, _SR)
        except Exception:
            raise TheMakerError(
                "스피커로 소리를 낼 수 없어요 (%s)\n"
                "speaker() 로 목록을 보고 speaker(번호) 로 골라 보세요." % ex)
    if wait:
        sd.wait()


def _wave(freq, seconds, kind="sine"):
    """파형 만들기. 앞뒤를 부드럽게 해서 '툭' 소리를 없앤다. freq 0 이면 쉼표."""
    n = max(1, int(_SR * float(seconds)))
    if float(freq) <= 0:
        return np.zeros(n, dtype=np.float32)
    t = np.arange(n) / _SR
    if kind == "square":
        a = np.sign(np.sin(2 * np.pi * freq * t))
    elif kind == "saw":
        a = 2 * (t * freq - np.floor(0.5 + t * freq))
    else:
        a = np.sin(2 * np.pi * freq * t)
    fade = min(n // 8, int(_SR * 0.01))
    if fade > 0:
        a[:fade] *= np.linspace(0, 1, fade)
        a[-fade:] *= np.linspace(1, 0, fade)
    return (a * 0.3).astype(np.float32)


def play_note(name="도", beats=1, tempo=120):
    """계이름 하나를 소리 내기.

    >>> play_note("도")
    >>> play_note("솔", 2)          # 2박자
    계이름 : 도 레 미 파 솔 라 시 도2(한 옥타브 위)
    """
    key = str(name).strip().lower()
    key = key if key in _NOTES else str(name).strip()
    if key not in _NOTES:
        raise TheMakerError("모르는 계이름이에요: %s (도 레 미 파 솔 라 시 높은도)" % name)
    sec = float(beats) * 60.0 / max(20.0, float(tempo))
    _play(_wave(_NOTES[key], sec))
    return None


def beep(kind="ok"):
    """짧은 알림 소리. ok / error / ding / buzz"""
    k = str(kind).strip().lower()
    if k in ("ok", "성공"):
        w = np.concatenate([_wave(660, .09), _wave(880, .12)])
    elif k in ("error", "실패"):
        w = np.concatenate([_wave(300, .12, "square"), _wave(200, .18, "square")])
    elif k in ("ding", "딩"):
        w = _wave(1200, .25)
    elif k in ("buzz", "삐"):
        w = _wave(150, .3, "saw")
    else:
        raise TheMakerError("ok error ding buzz 중에서 골라 주세요.")
    _play(w)
    return None


def play_melody(notes="도레미파솔", tempo=120):
    """계이름을 이어서 연주하기. 띄어쓰기로 나눠도 되고 붙여 써도 돼요.

    >>> play_melody("도레미파솔라시높은도")
    >>> play_melody("솔 솔 라 라 솔 솔 미", 100)
    """
    # 띄어쓰기는 쉼표로 친다 — 블록 코딩과 같은 규칙 ("도미솔 솔 도2")
    keys = sorted(_NOTES, key=len, reverse=True)
    parts, skipped = [], []
    for group in str(notes).replace(",", " ").split(" "):
        if not group:
            continue
        if parts:
            parts.append("쉼")                     # 덩어리 사이는 한 박 쉬기
        i = 0
        while i < len(group):
            for k in keys:
                if group[i:i + len(k)] == k:
                    parts.append(k); i += len(k); break
            else:
                skipped.append(group[i]); i += 1
    while parts and parts[-1] == "쉼":
        parts.pop()
    if skipped:
        print("[play_melody] 모르는 글자는 건너뛰었어요:", "".join(skipped))
    if not parts:
        raise TheMakerError("계이름을 찾을 수 없어요. (도 레 미 파 솔 라 시 도2)")
    sec = 60.0 / max(20.0, float(tempo))
    _play(np.concatenate([_wave(_NOTES[p], sec) for p in parts]))
    return None


def play_hz(freq=440, seconds=0.5):
    """주파수(Hz)로 소리 내기. 440 = 라"""
    _play(_wave(max(20.0, float(freq)), max(0.02, float(seconds))))
    return None
