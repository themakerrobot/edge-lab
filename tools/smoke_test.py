# -*- coding: utf-8 -*-
"""vapi-od 배포 점검: 서버에 실제 요청을 보내 전 서비스가 응답하는지 확인한다.
   사용법: python smoke_test.py [host]     기본값 http://localhost:57711
   표준 라이브러리 + cv2/numpy 만 사용 (requests 불필요)."""
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
    ("사물 인식",        "/object/object_search_e", "plain", None),
    ("사람 포즈",        "/object/object_pose_e",   "plain", None),
    ("사물 분할",        "/object/object_seg_e",    "plain", None),
    ("커스텀(가위바위보)", "/object/object_custom_e", "plain", {"detect_mode": "rps"}),
    ("커스텀(안전모)",    "/object/object_custom_e", "plain", {"detect_mode": "helmet"}),
    ("커스텀(박스)",      "/object/object_custom_e", "plain", {"detect_mode": "box"}),
    ("얼굴 찾기",        "/face/face_detect_e",     "plain", None),
    ("얼굴 분석",        "/face/face_analyze_e",    "plain", None),
    ("마스크",           "/face/mask_detect",       "plain", None),
    ("글자 인식",        "/code/ocr",               "text",  None),
    ("QR 인식",          "/code/barcode",           "qr",    None),
    ("배경 제거",        "/gan/portrait",           "plain", None),
    ("화질 개선",        "/gan/sr",                 "plain", None),
    ("VLM 설명",         "/vlm/vlm_inference_e",    "plain", {"prompt": "무엇이 보이나요?"}),
    ("VLM 시간",         "/caption/caption_time_e", "plain", None),
    ("VLM 태그",         "/caption/caption_tag_e",  "plain", None),
    ("이미지 분류",       "/object/object_cls_e",    "plain", None),
    ("얼굴 속성",        "/face/face_attribute",    "plain", None),
    ("얼굴 거리·방향(MP)", "/face/mesh_e",            "plain", None),
    ("손동작(MP)",        "/object/hand_e",          "plain", None),
]

# 음성은 모델이 없을 수도 있으므로 따로 확인한다 (없으면 건너뜀)
def check_speech():
    try:
        with urllib.request.urlopen(HOST + "/speech/voices", timeout=5) as r:
            j = json.loads(r.read().decode())
    except Exception:
        return
    err = (j.get("data") or {}).get("error") or ""
    body = json.dumps({"text": "안녕하세요", "voice": "F1", "lang": "ko"}).encode()
    req = urllib.request.Request(HOST + "/speech/tts", data=body,
                                 headers={"Content-Type": "application/json"})
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            ok = "audio" in r.headers.get("Content-Type", "") and len(r.read()) > 1000
        ms = int((time.perf_counter() - t0) * 1000)
        print(f"  {'PASS' if ok else 'FAIL'}  {'음성 합성(TTS)':<16} {ms:>6} ms")
    except Exception as ex:
        print(f"  SKIP  {'음성 합성(TTS)':<16} {str(err or ex)[:40]}")


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

    check_speech()
    print("-" * 62)
    print(f"결과: {passed} PASS / {failed} FAIL  (총 {passed + failed})")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
