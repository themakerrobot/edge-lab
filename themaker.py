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

# 기능명(영문 기본) -> (엔드포인트, 기본 파라미터)
_API = {
    "object":     ("/object/object_search_e", {}),
    "pose":       ("/object/object_pose_e", {}),
    "seg":        ("/object/object_seg_e", {}),
    "hand":       ("/object/hand_e", {}),
    "face":       ("/face/face_detect_e", {}),
    "face_attr":  ("/face/face_analyze_e", {}),
    "distance":   ("/face/mesh_e", {}),
    "caption":    ("/caption/caption", {}),
    "question":   ("/caption/caption_question_e", {}),
    "tag":        ("/caption/caption_tag_e", {}),
    "classify":   ("/vlm/vlm_inference_e", {}),
    "ocr":        ("/code/ocr", {}),
    "qr":         ("/code/barcode", {}),
    "bg_remove":  ("/gan/portrait", {}),
    "sr":         ("/gan/sr", {}),
    "mask":       ("/face/mask_detect", {}),
    # 특별 훈련된 YOLO 7종 (detect_mode 로 구분)
    "fire":       ("/object/object_custom_e", {"detect_mode": "fire"}),
    "fall":       ("/object/object_custom_e", {"detect_mode": "fall"}),
    "ball":       ("/object/object_custom_e", {"detect_mode": "ball"}),
    "rps":        ("/object/object_custom_e", {"detect_mode": "rps"}),
    "number":     ("/object/object_custom_e", {"detect_mode": "number"}),
    "helmet":     ("/object/object_custom_e", {"detect_mode": "helmet"}),
    "box":        ("/object/object_custom_e", {"detect_mode": "box"}),
}

# 한글 이름도 그대로 쓸 수 있다
_ALIAS_KO = {
    "사물": "object", "자세": "pose", "분할": "seg", "손": "hand",
    "얼굴": "face", "얼굴분석": "face_attr", "얼굴거리": "distance",
    "설명": "caption", "질문": "question", "태그": "tag", "분류": "classify",
    "글자": "ocr", "큐알": "qr", "배경제거": "bg_remove", "화질개선": "sr",
    "마스크": "mask",
    "불": "fire", "화재": "fire", "쓰러짐": "fall", "공": "ball",
    "가위바위보": "rps", "숫자": "number", "안전모": "helmet", "상자": "box",
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


def vision(kind, image, prompt=None, raw=False, **params):
    """AI 실행. kind: "object","face","caption","question","ocr","bg_remove" 등 (한글도 가능).

    >>> r = vision("object", img)
    >>> r = vision("question", img, prompt="사람이 몇 명이야?")
    >>> r = vision("caption", img, lang="en")    # 영어로 답 받기
    >>> r = vision("caption", img, raw=True)     # 서버가 준 것 그대로 (사전)
    >>> r = vision("my:my-ai", img)              # 가르치기에서 저장한 모델

    설명·질문·태그는 읽기 쉽게 글자 하나로 돌려준다.
    영어판 등 다른 값까지 보고 싶으면 raw=True 를 준다.
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
    data.update({k: str(v) for k, v in params.items()})

    j = _post(url, data=data,
              files={"uploadFile": ("input.jpg", _to_jpg(image), "image/jpeg")})
    if j.get("result") != "ok":
        raise TheMakerError("AI 실행 실패: %s" % j.get("data"))
    data = j.get("data")
    if raw:
        return data                              # 서버가 준 것 그대로 (사전·목록)
    # 배경제거·화질개선은 base64 글자로 오는데, 학생이 다루기 어렵다 —
    # 여기서 풀어서 곧바로 이미지로 돌려준다 (save·show 에 그대로 넣을 수 있게).
    if kind in ("bg_remove", "sr") and isinstance(data, str):
        return _b64_to_image(data)
    # 글로 답하는 기능은 사전 대신 글자 하나로 준다 —
    # r["answer"] 같은 걸 몰라도 print(r) 로 바로 읽히게.
    _TEXT_OF = {"caption": "caption", "question": "answer", "tag": "tag"}
    if kind in _TEXT_OF and isinstance(data, dict):
        return str(data.get(_TEXT_OF[kind], "")).strip()
    # QR 은 보통 하나만 찍으니 내용만 준다 (없으면 빈 글자)
    if kind == "qr" and isinstance(data, list):
        return str(data[0].get("data", "")) if data else ""
    # 사물 인식은 {person:[], object:[]} 로 오므로 하나의 리스트로 합쳐 준다.
    if kind == "object" and isinstance(data, dict):
        data = (data.get("object") or []) + (data.get("person") or [])
    # 특별 훈련 YOLO 는 {"object": [...]} 로 온다
    elif isinstance(data, dict) and set(data) == {"object"}:
        data = data.get("object") or []
    return data


_KIND_KO = {"image": "사진", "pose": "손모양", "face": "표정",
            "body_up": "상반신", "body": "전신"}


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


def draw(image, result):
    """인식 결과(박스/이름)를 이미지에 그려서 돌려준다."""
    img = _flatten(image).copy()
    items = result if isinstance(result, list) else [result]
    for it in items:
        if not isinstance(it, dict):
            continue
        box = it.get("box") or it.get("bbox")
        name = it.get("name") or it.get("label") or it.get("class") or ""
        score = it.get("score") or it.get("conf")
        if box and len(box) == 4:
            x1, y1, x2, y2 = [int(v) for v in box]
            cv2.rectangle(img, (x1, y1), (x2, y2), (255, 176, 46), 2)
            if isinstance(score, (int, float)):
                pct = score * 100 if score <= 1 else score      # 0~1 또는 0~100 둘 다 지원
                tag = "%s %.0f%%" % (name, pct)
            else:
                tag = str(name)
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
    return stt(_wav_bytes(rec.reshape(-1), sr), lang=lang)


def stt(wav, lang="ko"):
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
    sd.play(a, sr)
    if wait:
        sd.wait()


_yolo_cache = {}


def detect(model_path, image, conf=0.3):
    """내가 학습한 YOLO 모델 파일로 인식한다 (경로로 지정).

    >>> r = detect("my_model.pt", camera())
    >>> r = detect(r"C:\\models\\cat.pt", load("cat.jpg"))
    >>> show(camera(), r)

    model_path : .pt 파일, 또는 OpenVINO 로 변환한 폴더(*_openvino_model)
                 상대경로는 실행 폴더(data/pycode) 기준이다.
    conf       : 이 확신도보다 낮은 결과는 버린다 (0~1).
    돌려주는 것: [{"name": 이름, "score": 0~1, "box": [x1,y1,x2,y2]}, ...]
    """
    path = os.path.abspath(str(model_path))
    if not os.path.exists(path):
        raise TheMakerError("모델 파일이 없어요: %s\n경로를 확인하세요." % path)

    model = _yolo_cache.get(path)
    if model is None:
        try:
            from ultralytics import YOLO
        except ImportError:
            raise TheMakerError("ultralytics 가 없어서 내 YOLO 모델을 쓸 수 없어요.")
        model = YOLO(path)
        _yolo_cache[path] = model              # 한 번 읽으면 캐시 (반복 실행이 빨라진다)

    img = image
    if isinstance(image, str):
        img = load(image)
    out = []
    for box in (model(img, verbose=False)[0].boxes or []):
        score = float(box.conf[0])
        if score < conf:
            continue
        x1, y1, x2, y2 = [int(v) for v in box.xyxy[0]]
        out.append({"name": model.names[int(box.cls[0])],
                    "score": round(score, 4), "box": [x1, y1, x2, y2]})
    return out


__all__ = ["vision", "detect", "camera", "load", "save", "draw", "show",
           "listen", "stt", "speak", "my_models", "SERVER", "TheMakerError"]
