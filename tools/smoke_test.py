# -*- coding: utf-8 -*-
"""vapi-od 배포 점검: 서버에 실제 요청을 보내 전 서비스가 응답하는지 확인한다.
   사용법: python smoke_test.py [host]     기본값 http://localhost:57711
   표준 라이브러리 + cv2/numpy 만 사용 (requests 불필요)."""
import io
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

import cv2
import numpy as np

HOST = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:57711"


def make_images():
    """합성 테스트 이미지 3종 (일반 / 글자 / QR)."""
    plain = np.full((480, 640, 3), 200, np.uint8)
    cv2.rectangle(plain, (120, 140), (380, 400), (60, 90, 200), -1)
    cv2.circle(plain, (470, 220), 90, (80, 170, 90), -1)

    text = np.full((240, 720, 3), 255, np.uint8)
    cv2.putText(text, "VAPI-OD 2026", (30, 150), cv2.FONT_HERSHEY_SIMPLEX, 2.2, (0, 0, 0), 5)

    try:
        qr = cv2.QRCodeEncoder.create().encode("https://circul.us")
        if qr.max() <= 1:
            qr = qr * 255
        qr = cv2.cvtColor(cv2.resize(qr, (420, 420), interpolation=cv2.INTER_NEAREST),
                          cv2.COLOR_GRAY2BGR)
    except Exception:
        qr = plain
    return {"plain": plain, "text": text, "qr": qr}


def post(path, image, params=None, timeout=180):
    url = HOST + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    ok, buf = cv2.imencode(".jpg", image)
    boundary = "----vapi" + uuid.uuid4().hex
    body = (f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="uploadFile"; filename="t.jpg"\r\n'
            "Content-Type: image/jpeg\r\n\r\n").encode() + buf.tobytes() + \
           f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(url, data=body, method="POST",
                                 headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


CASES = [
    ("사물 인식",        "/object/object_search", "plain", None),
    ("사람 포즈",        "/object/object_pose",   "plain", None),
    ("사물 분할",        "/object/object_seg",    "plain", None),
    ("얼굴 찾기",        "/face/face_detect",     "plain", None),
    ("얼굴 분석",        "/face/face_analyze",    "plain", None),
    ("얼굴 감정",        "/face/face_emotion",    "plain", None),
    ("얼굴 나이·성별",     "/face/face_age_gender", "plain", None),
    ("마스크",           "/face/mask_detect",       "plain", None),
    ("글자 인식",        "/code/ocr",               "text",  None),
    ("QR 인식",          "/code/barcode",           "qr",    None),
    ("배경 제거",        "/gan/portrait",           "plain", None),
    ("화질 개선",        "/gan/sr",                 "plain", None),
    ("VLM 자유 프롬프트",  "/vlm/look",    "plain", {"prompt": "무엇이 보이나요?"}),
    ("VLM 질문",         "/vlm/look", "plain", {"prompt": "무엇이 있어?"}),
    ("얼굴 거리·방향",     "/face/mesh",            "plain", None),
    ("손동작(MP)",        "/object/hand",          "plain", None),
]

# 음성은 모델이 없을 수도 있으므로 따로 확인한다 (없으면 건너뜀)
def _wav(seconds=1.0, sr=16000, hz=440):
    """시험용 WAV 한 토막 (말은 아니지만 인식 경로가 도는지는 확인된다)."""
    import struct
    import wave
    n = int(sr * seconds)
    pcm = b"".join(struct.pack("<h", int(3000 * np.sin(2 * np.pi * hz * i / sr)))
                   for i in range(n))
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes(pcm)
    return buf.getvalue()


def check_chat():
    """사진 없이 묻기 — 업로드가 없어 CASES 와 형태가 달라 따로 확인한다."""
    url = HOST + "/chat/ask?" + urllib.parse.urlencode({"prompt": "무지개는 왜 생겨?"})
    t0 = time.perf_counter()
    try:
        req = urllib.request.Request(url, data=b"", method="POST")
        with urllib.request.urlopen(req, timeout=180) as r:
            j = json.loads(r.read().decode())
        ms = int((time.perf_counter() - t0) * 1000)
        state = "PASS" if j.get("result") == "ok" else "FAIL"
        dev = j.get("device", "-")
        print(f"  {state}  {'대화(사진 없이)':<16} {ms:>6} ms  [{dev}]")
        return (1, 0) if j.get("result") == "ok" else (0, 1)
    except Exception as ex:
        print(f"  FAIL  {'대화(사진 없이)':<16} {str(ex)[:50]}")
        return (0, 1)


def check_db():
    """자료 만들기 → 찾기 → 답하기 → 지우기. 임베딩 모델은 첫 요청 때 올라온다."""
    text = ("무지개는 빛이 물방울에 꺾여서 생긴다. 비가 온 뒤 햇빛이 나면 하늘에 "
            "반원 모양으로 나타난다. 빨강부터 보라까지 일곱 빛깔이다.\n\n"
            "달은 지구를 도는 위성이다. 밤하늘에서 가장 밝게 보이며 한 달에 한 번씩 "
            "모양이 둥글게 찼다가 다시 줄어든다.")
    b = "----vapikb"
    body = b"".join(
        ('--%s\r\nContent-Disposition: form-data; name="%s"\r\n\r\n%s\r\n'
         % (b, k, v)).encode() for k, v in (("title", "점검자료"), ("text", text)))
    body += ("--%s--\r\n" % b).encode()
    t0 = time.perf_counter()
    try:
        req = urllib.request.Request(HOST + "/chat/db", data=body,
                                     headers={"Content-Type":
                                              "multipart/form-data; boundary=" + b})
        with urllib.request.urlopen(req, timeout=180) as r:
            j = json.loads(r.read().decode())
        assert j.get("result") == "ok", j.get("data")
        slug = j["data"]["slug"]
        ms = int((time.perf_counter() - t0) * 1000)
        print(f"  PASS  {'자료 만들기':<16} {ms:>6} ms  [{j['data']['count']}조각]")

        q = urllib.parse.urlencode({"db": slug, "prompt": "무지개는 왜 생겨?", "top_k": 2})
        t1 = time.perf_counter()
        req = urllib.request.Request(HOST + "/chat/rag?" + q, data=b"", method="POST")
        with urllib.request.urlopen(req, timeout=180) as r:
            j = json.loads(r.read().decode())
        ms = int((time.perf_counter() - t1) * 1000)
        ok2 = j.get("result") == "ok"
        print(f"  {'PASS' if ok2 else 'FAIL'}  {'자료에서 답하기':<16} {ms:>6} ms "
              f" [{j.get('device', '-')}]")

        req = urllib.request.Request(HOST + "/chat/db/" + urllib.parse.quote(slug),
                                     method="DELETE")
        urllib.request.urlopen(req, timeout=10).read()
        return (1 + (1 if ok2 else 0), 0 if ok2 else 1)
    except Exception as ex:
        print(f"  FAIL  {'자료(RAG)':<16} {str(ex)[:50]}")
        return (0, 1)


def check_speech():
    """TTS(소리 만들기)와 STT(음성 인식). 둘 다 지연 로딩이라 첫 호출이 느리다."""
    p_n = f_n = 0
    err = tts_err = ""
    dev_stt = dev_tts = "CPU"                     # TTS 는 onnxruntime CPU 고정
    try:
        with urllib.request.urlopen(HOST + "/speech/ready", timeout=5) as r:
            d = (json.loads(r.read().decode()).get("data") or {})
        err, tts_err = d.get("error") or "", d.get("tts_error") or ""
        dev_stt = d.get("device") or "CPU"
    except Exception:
        pass

    # --- TTS
    body = json.dumps({"text": "안녕하세요", "voice": "F1", "lang": "ko"}).encode()
    req = urllib.request.Request(HOST + "/speech/tts", data=body,
                                 headers={"Content-Type": "application/json"})
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            ok = "audio" in r.headers.get("Content-Type", "") and len(r.read()) > 1000
        ms = int((time.perf_counter() - t0) * 1000)
        print(f"  {'PASS' if ok else 'FAIL'}  {'음성 합성(TTS)':<16} {ms:>6} ms  [{dev_tts}]")
        p_n, f_n = (p_n + 1, f_n) if ok else (p_n, f_n + 1)
    except Exception as ex:
        print(f"  SKIP  {'음성 합성(TTS)':<16} {str(tts_err or ex)[:40]}")

    # --- STT (모델이 없으면 건너뛴다)
    boundary = "----vapi" + uuid.uuid4().hex
    raw = _wav()
    data = (f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="uploadFile"; filename="a.wav"\r\n'
            "Content-Type: audio/wav\r\n\r\n").encode() + raw + \
           f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(HOST + "/speech/stt?lang=ko", data=data,
                                 headers={"Content-Type":
                                          f"multipart/form-data; boundary={boundary}"})
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            j = json.loads(r.read().decode())
        ms = int((time.perf_counter() - t0) * 1000)
        state = "PASS" if j.get("result") == "ok" else "FAIL"
        print(f"  {state}  {'음성 인식(STT)':<16} {ms:>6} ms  [{dev_stt}]")
        p_n, f_n = (p_n + 1, f_n) if state == "PASS" else (p_n, f_n + 1)
    except Exception as ex:
        print(f"  SKIP  {'음성 인식(STT)':<16} {str(err or ex)[:40]}")
    return (p_n, f_n)


def wait_ready(limit=300):
    """모델은 백그라운드로 올라온다 — 준비될 때까지 기다린다.

    서버 소켓은 즉시 열리므로 /system 응답만 보고 시작하면
    아직 로딩 중인 기능이 전부 503 으로 실패한다.
    """
    t0 = time.perf_counter()
    shown = False
    while time.perf_counter() - t0 < limit:
        try:
            with urllib.request.urlopen(HOST + "/ready", timeout=5) as r:
                j = json.loads(r.read().decode())
            if j.get("ready"):
                if shown:
                    print(f"  준비 완료 ({int(time.perf_counter() - t0)}s)")
                return True
            if not shown:
                print("  모델을 올리는 중입니다 (1~2분)...")
                shown = True
        except Exception:
            pass
        time.sleep(3)
    print(f"[FAIL] {limit}초 안에 준비되지 않았습니다")
    return False


def main():
    print(f"\nvapi-od smoke test  ->  {HOST}\n" + "-" * 62)
    if not wait_ready():
        return 1
    try:
        with urllib.request.urlopen(HOST + "/system", timeout=10) as r:
            info = json.loads(r.read().decode())
        print(f"devices : {', '.join(info.get('devices', []))}")
        print(f"assign  : {info.get('assign')}")
    except Exception as ex:
        print(f"[FAIL] 서버에 연결할 수 없습니다: {ex}")
        return 1
    print("-" * 62)

    images = make_images()
    passed = failed = 0
    for label, path, img_key, params in CASES:
        t0 = time.perf_counter()
        try:
            res = post(path, images[img_key], params)
            ms = int((time.perf_counter() - t0) * 1000)
            if res.get("result") == "ok":
                dev = res.get("device", "-")
                print(f"  PASS  {label:<16} {ms:>6} ms  [{dev}]")
                passed += 1
            else:
                print(f"  FAIL  {label:<16} {str(res.get('data'))[:60]}")
                failed += 1
        except Exception as ex:
            print(f"  FAIL  {label:<16} {str(ex)[:60]}")
            failed += 1

    for p_i, f_i in (check_chat(), check_db(), check_speech()):
        passed += p_i
        failed += f_i
    print("-" * 62)
    print(f"결과: {passed} PASS / {failed} FAIL  (총 {passed + failed})")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
