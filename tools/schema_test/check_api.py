# -*- coding: utf-8 -*-
"""살아 있는 서버에 실제로 요청을 보내 응답 모양을 확인한다."""
import json
import urllib.error
import urllib.parse
import urllib.request

import cv2
import numpy as np

_img = np.full((480, 640, 3), 220, np.uint8)
cv2.rectangle(_img, (200, 150), (320, 300), (60, 120, 200), -1)
JPG = cv2.imencode(".jpg", _img)[1].tobytes()


def _post(host, path, params=None):
    q = ("?" + "&".join("%s=%s" % kv for kv in (params or {}).items())) if params else ""
    b = "----schematest"
    body = (("--%s\r\nContent-Disposition: form-data; name=\"uploadFile\"; "
             "filename=\"a.jpg\"\r\nContent-Type: image/jpeg\r\n\r\n" % b).encode()
            + JPG + ("\r\n--%s--\r\n" % b).encode())
    req = urllib.request.Request(host + path + q, data=body,
                                 headers={"Content-Type":
                                          "multipart/form-data; boundary=" + b})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


# (이름, 경로, 파라미터, 검사)
CASES = [
    ("사물 인식", "/object/object_search", None,
     lambda d: isinstance(d["object"], list) and "name_en" in d["object"][0]
     and "person" not in d),
    ("사물 인식(en)", "/object/object_search", {"lang": "en"},
     lambda d: d["object"][0]["name"] == "person"),
    ("포즈", "/object/object_pose", None, lambda d: "points" in d[0]),
    ("분할", "/object/object_seg", None,
     lambda d: "image" in d and "name_en" in d["object"][0]),
    ("분할(en)", "/object/object_seg", {"lang": "en"},
     lambda d: d["object"][0]["name"] == "chair"),
    ("개별인식(불)", "/object/object_custom", {"detect_mode": "fire"},
     lambda d: d["object"][0]["name"] == "불" and d["object"][0]["name_en"] == "fire"),
    ("개별인식(가위바위보)", "/object/object_custom", {"detect_mode": "rps"},
     lambda d: d["object"][0]["name"] == "바위" and d["object"][0]["name_en"] == "rock"),
    ("개별인식(en)", "/object/object_custom", {"detect_mode": "rps", "lang": "en"},
     lambda d: d["object"][0]["name"] == "rock"),
    ("얼굴 찾기", "/face/face_detect", None,
     lambda d: d[0]["name"] == "얼굴" and d[0]["name_en"] == "face"),
    ("얼굴 찾기(en)", "/face/face_detect", {"lang": "en"}, lambda d: d[0]["name"] == "face"),
    ("얼굴 분석", "/face/face_analyze", None,
     lambda d: d[0]["gender"] == "남성" and d[0]["gender_en"] == "man"
     and d[0]["emotion_en"] == "happy" and d[0]["pos"]["direction"] == "왼쪽 위"
     and d[0]["pos"]["direction_en"] == "LT"),
    ("얼굴 분석(en)", "/face/face_analyze", {"lang": "en"},
     lambda d: d[0]["gender"] == "man" and d[0]["pos"]["direction"] == "left up"),
    ("얼굴 감정", "/face/face_emotion", None,
     lambda d: d[0]["emotion"] == "행복한 표정" and d[0]["emotion_en"] == "happy"),
    ("나이·성별", "/face/face_age_gender", None,
     lambda d: d[0]["age"] == 34 and d[0]["gender_en"] == "man"),
    ("마스크", "/face/mask_detect", None,
     lambda d: d[0]["name"] == "마스크 씀" and d[0]["name_en"] == "mask"),
    ("장소", "/vlm/place", None,
     lambda d: d["place"] == "거실" and d["place_en"] == "living-room"),
    ("장소(en)", "/vlm/place", {"lang": "en"},
     lambda d: d["place"] == "living-room"),
    ("시간", "/vlm/time", None,
     lambda d: d["time"] == "저녁" and d["time_en"] == "evening"),
    ("날씨", "/vlm/weather", None,
     lambda d: d["weather"] == "실내" and d["weather_en"] == "indoor"),
    ("질문(프롬프트 전달)", "/vlm/look", {"prompt": "PROBE_XYZ"},
     lambda d: "PROBE_XYZ" in d["answer"] and "answer_en" not in d),
    ("태그", "/vlm/tag", None, lambda d: "tag" in d and "tag_en" not in d),
    ("배경 제거", "/gan/portrait", None, lambda d: isinstance(d, str) and len(d) > 100),
    ("화질 개선", "/gan/sr", None, lambda d: isinstance(d, str)),
    ("글자 인식", "/code/ocr", None, lambda d: d[0]["text"] == "안녕"),
    ("QR", "/code/barcode", None, lambda d: d[0]["data"].startswith("http")),
]

# 없어진 경로 — 되살아나면 안 된다
CHAT = "/chat/ask"

GONE = ["/caption/caption", "/object/object_cls", "/face/face_attribute", "/caption/caption_place",
        "/caption/caption_question", "/vlm/vlm_inference", "/vlm/ask", "/face/face_pose", "/vlm/place_e", "/object/object_search_e",
        "/face/face_analyze_e", "/gan/txt2image", "/speech/wav_to_text"]

PAGES = ["/", "/blocks", "/code", "/train", "/options", "/talk", "/ready"]

# 있어야 하는 GET 경로 (없으면 화면에서 기능이 통째로 막힌다)
NEEDED_GET = ["/custom/models", "/custom/projects", "/system/files"]


def run(host):
    ok = fail = 0
    for name, path, params, check in CASES:
        try:
            r = _post(host, path, params)
            assert r.get("result") == "ok", r.get("data")
            assert check(r["data"]), \
                "스키마 불일치: " + json.dumps(r["data"], ensure_ascii=False)[:150]
            print("  PASS  %-20s %s" % (name, path)); ok += 1
        except Exception as ex:
            print("  FAIL  %-20s %s\n        %s" % (name, path, ex)); fail += 1

    # 사진 없이 묻기 (업로드 없음)
    try:
        req = urllib.request.Request(host + CHAT + "?prompt=" +
                                     urllib.parse.quote("삼국지가 뭐야?"),
                                     data=b"", method="POST")
        with urllib.request.urlopen(req, timeout=30) as r:
            d = json.loads(r.read().decode())
        assert d.get("result") == "ok" and "answer" in d["data"], d
        print("  PASS  %-20s %s" % ("사진 없이 묻기", CHAT)); ok += 1
    except Exception as ex:
        print("  FAIL  %-20s %s" % ("사진 없이 묻기", ex)); fail += 1

    # 자료 만들기 → 찾기 → 답하기 → 지우기 (한 흐름)
    try:
        b = "----kbtest"
        fields = {"title": "시험자료",
                  "text": "무지개는 빛이 물방울에 꺾여서 생긴다. 비가 온 뒤 햇빛이 나면 "
                          "하늘에 반원 모양으로 나타난다. 빨강부터 보라까지 일곱 빛깔이다.\n\n"
                          "달은 지구를 도는 위성이다. 밤하늘에서 가장 밝게 보이며 "
                          "한 달에 한 번씩 모양이 둥글게 찼다가 다시 줄어든다."}
        body = b"".join(
            ('--%s\r\nContent-Disposition: form-data; name="%s"\r\n\r\n%s\r\n'
             % (b, k, v)).encode() for k, v in fields.items()) + ("--%s--\r\n" % b).encode()
        req = urllib.request.Request(host + "/chat/db", data=body,
                                     headers={"Content-Type":
                                              "multipart/form-data; boundary=" + b})
        d = json.loads(urllib.request.urlopen(req, timeout=30).read().decode())
        assert d["result"] == "ok" and d["data"]["count"] >= 2, d
        slug = d["data"]["slug"]
        print("  PASS  %-20s %s" % ("자료 만들기", "/chat/db")); ok += 1

        with urllib.request.urlopen(host + "/chat/db", timeout=10) as r:
            lst = json.loads(r.read().decode())
        assert any(x["slug"] == slug for x in lst["data"]), lst
        print("  PASS  %-20s %s" % ("자료 목록", "/chat/db")); ok += 1

        q = urllib.parse.urlencode({"db": slug, "prompt": "무지개는 왜 생겨?", "top_k": 2})
        req = urllib.request.Request(host + "/chat/find?" + q, data=b"", method="POST")
        d = json.loads(urllib.request.urlopen(req, timeout=30).read().decode())
        assert d["result"] == "ok" and "무지개" in d["data"]["found"][0]["text"], d
        print("  PASS  %-20s %s" % ("자료에서 찾기", "/chat/find")); ok += 1

        req = urllib.request.Request(host + "/chat/rag?" + q, data=b"", method="POST")
        d = json.loads(urllib.request.urlopen(req, timeout=30).read().decode())
        assert d["result"] == "ok" and "answer" in d["data"] and d["data"]["found"], d
        print("  PASS  %-20s %s" % ("자료에서 답하기", "/chat/rag")); ok += 1

        req = urllib.request.Request(host + "/chat/db/" + urllib.parse.quote(slug),
                                     method="DELETE")
        d = json.loads(urllib.request.urlopen(req, timeout=10).read().decode())
        assert d["result"] == "ok", d
        print("  PASS  %-20s %s" % ("자료 지우기", "/chat/db/{slug}")); ok += 1
    except Exception as ex:
        print("  FAIL  %-20s %s" % ("자료(RAG) 흐름", ex)); fail += 1

    for path in GONE:
        try:
            _post(host, path)
            print("  FAIL  삭제된 경로가 살아 있음  %s" % path); fail += 1
        except urllib.error.HTTPError as e:
            if e.code == 404:
                print("  PASS  삭제 확인(404)      %s" % path); ok += 1
            else:
                print("  FAIL  %s -> %s" % (path, e.code)); fail += 1

    for path in NEEDED_GET:
        try:
            with urllib.request.urlopen(host + path, timeout=10) as r:
                assert json.loads(r.read().decode())["result"] == "ok"
            print("  PASS  목록 경로 살아 있음    %s" % path); ok += 1
        except Exception as ex:
            print("  FAIL  %s  %s" % (path, ex)); fail += 1

    # 작업폴더 파일 브라우저 — 폴더 밖으로 나가려는 시도는 막혀야 한다
    for bad in ["..", "../secret.txt", "a/../../b"]:
        try:
            u = host + "/system/files?path=" + urllib.parse.quote(bad)
            with urllib.request.urlopen(u, timeout=10) as r:
                print("  FAIL  작업폴더 밖이 열림    %s -> %s" % (bad, r.status)); fail += 1
        except urllib.error.HTTPError as e:
            if e.code == 400:
                print("  PASS  작업폴더 밖 막음      %s" % bad); ok += 1
            else:
                print("  FAIL  %s -> %s" % (bad, e.code)); fail += 1
        except Exception as ex:
            print("  FAIL  %s  %s" % (bad, ex)); fail += 1

    for path in PAGES:
        try:
            with urllib.request.urlopen(host + path, timeout=10) as r:
                assert r.status == 200
            print("  PASS  화면·상태 열림        %s" % path); ok += 1
        except Exception as ex:
            print("  FAIL  %s  %s" % (path, ex)); fail += 1
    return ok, fail
