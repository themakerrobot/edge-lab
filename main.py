# -*- coding: utf-8 -*-
# vapi-od : 단일 FastAPI 서버 (기존 circulus-vapi 5개 서버 통합, 온디바이스)
# 응답 스키마는 기존 서버와 동일: {"type": <service_name>, "result": "ok"|"fail", "data": ...}
import os
import time
import uuid
from contextlib import asynccontextmanager


import cv2
import uvicorn
from fastapi import FastAPI, File, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

import prompts as P

HOST = os.environ.get("VAPI_HOST", "0.0.0.0")
PORT = int(os.environ.get("VAPI_PORT", "57711"))
IMAGE_DIR = "image_temp/"
os.makedirs(IMAGE_DIR, exist_ok=True)

eng = None


def open_browser():
    """모델 로딩이 끝난 뒤 기본 브라우저로 화면을 연다.
    끄고 싶으면 환경변수 VAPI_NO_BROWSER=1 로 실행한다."""
    if os.environ.get("VAPI_NO_BROWSER"):
        return
    import threading
    import webbrowser

    url = f"http://localhost:{PORT}"

    def _open():
        time.sleep(1.0)  # uvicorn 소켓 바인딩 여유
        try:
            webbrowser.open(url)
        except Exception as ex:
            print("[browser] 자동 실행 실패:", ex, "→ 직접 접속:", url)

    threading.Thread(target=_open, daemon=True).start()


# 서비스 → 실행 디바이스 (HUD 표시용, engines의 배정과 동일)
DEVICE_OF = {}


def build_device_map():
    import engines as E
    vlm = {"caption", "caption_place_e", "caption_time_e", "caption_weather_e",
           "caption_question_e", "caption_tag_e", "vlm_inference_e",
           "object_cls_e", "face_attribute"}
    gan = {"cartoon", "sketch", "portrait", "sr"}
    face = {"face_detect_e", "face_analyze_e", "face_analyze", "face_emotion_e",
            "face_age_gender_e", "face_pose_e"}
    for k in vlm:
        DEVICE_OF[k] = E.DEV_VLM
    for k in gan:
        DEVICE_OF[k] = E.DEV_GAN
    for k in face:
        DEVICE_OF[k] = E.DEV_FACE
    for k in ("object_search_e", "object_search", "object_pose_e", "object_seg_e",
              "object_custom_e", "mask_detect"):
        DEVICE_OF[k] = "CPU"
    for k in ("ocr", "barcode"):
        DEVICE_OF[k] = "CPU"


@asynccontextmanager
async def lifespan(app: FastAPI):
    global eng
    import engines
    eng = engines.Engines()
    build_device_map()
    print(f"! vapi-od listening on {HOST}:{PORT}")
    open_browser()
    yield


app = FastAPI(title="vapi-od", docs_url="/docs", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])
os.makedirs("view_project/fonts", exist_ok=True)
app.mount("/fonts", StaticFiles(directory="view_project/fonts"), name="fonts")
if os.path.isdir("view_project/blockly"):
    app.mount("/blockly", StaticFiles(directory="view_project/blockly"), name="blockly")


# ---------------------------------------------------------------- 공통
def save_upload(upload: UploadFile, service_name: str) -> str:
    ext = os.path.splitext(upload.filename or "img.jpg")[1] or ".jpg"
    path = IMAGE_DIR + service_name + "-" + str(uuid.uuid4()) + ext
    with open(path, "wb") as f:
        f.write(upload.file.read())
    return path


def service(name):
    """저장→추론→삭제→{"type","result","data"} 포맷을 공통 처리.
    fn(path, **extras)의 extras(prompt/mode/lang 등)는 쿼리 파라미터로 노출된다."""
    import inspect

    def deco(fn):
        extras = list(inspect.signature(fn).parameters.values())[1:]  # 'path' 제외

        async def wrapper(request: Request, uploadFile: UploadFile = File(...), **kw):
            path = save_upload(uploadFile, name)
            t0 = time.perf_counter()
            try:
                data = fn(path, **kw)
                return {"type": name, "result": "ok", "data": data,
                        "elapsed_ms": int((time.perf_counter() - t0) * 1000),
                        "device": DEVICE_OF.get(name, "CPU")}
            except Exception as ex:
                import traceback
                traceback.print_exc()
                return {"type": name, "result": "fail", "data": "Inference error:" + str(ex),
                        "elapsed_ms": int((time.perf_counter() - t0) * 1000)}
            finally:
                if os.path.exists(path):
                    os.remove(path)

        params = [
            inspect.Parameter("request", inspect.Parameter.POSITIONAL_OR_KEYWORD,
                              annotation=Request),
            inspect.Parameter("uploadFile", inspect.Parameter.POSITIONAL_OR_KEYWORD,
                              annotation=UploadFile, default=File(...)),
        ] + [p.replace(kind=inspect.Parameter.KEYWORD_ONLY) for p in extras]
        wrapper.__signature__ = inspect.Signature(params)
        wrapper.__name__ = fn.__name__
        return wrapper
    return deco


def read_bgr(path):
    img = cv2.imread(path)
    if img is None:
        raise ValueError("invalid image")
    return img


# ---------------------------------------------------------------- object
@app.post("/object/object_search_e", tags=["object"], summary="사물 인식")
@service("object_search_e")
def object_search_e(path):
    o_ko, o_en, p_ko, p_en = eng.object.search(path)
    return {"person": p_ko, "person_en": p_en, "object": o_ko, "object_en": o_en}


@app.post("/object/object_search", tags=["object"], summary="(로봇용)사물 인식")
@service("object_search")
def object_search(path):
    o_ko, o_en, p_ko, p_en = eng.object.search(path)
    return {"person": p_ko, "person_en": p_en, "object": o_ko, "object_en": o_en,
            "keypoint": eng.object.points(path)}


@app.post("/object/object_pose_e", tags=["object"], summary="포즈 인식")
@service("object_pose_e")
def object_pose_e(path):
    return eng.object.points(path)


@app.post("/object/object_seg_e", tags=["object"], summary="사물 영역 인식")
@service("object_seg_e")
def object_seg_e(path):
    return eng.object.segment(path)


@app.post("/object/object_custom_e", tags=["object"],
          summary="Custom Yolo (fire|fall|ball|rps|number|helmet|box)")
async def object_custom_e(request: Request, uploadFile: UploadFile = File(...),
                          detect_mode: str = "fire"):
    name = "object_custom_e"
    path = save_upload(uploadFile, name)
    try:
        data = eng.custom.predict(detect_mode, path)
        return {"type": name, "result": "ok", "detect_mode": detect_mode,
                "data": {"object": data}}
    except Exception as ex:
        return {"type": name, "result": "fail", "detect_mode": detect_mode,
                "data": "Inference error:" + str(ex)}
    finally:
        os.path.exists(path) and os.remove(path)


@app.post("/object/object_cls_e", tags=["object"], summary="이미지 분류 (VLM)")
@service("object_cls_e")
def object_cls_e(path):
    text = eng.vlm.generate(read_bgr(path), P.P_CLS, P.MAX_TOKENS["cls"])
    return P.parse_cls(text)


# ---------------------------------------------------------------- face
def _faces(path):
    image = read_bgr(path)
    return image, eng.face.detect.predict(image)


@app.post("/face/face_detect_e", tags=["face"], summary="얼굴 찾기")
@service("face_detect_e")
def face_detect_e(path):
    _, items = _faces(path)
    return items


@app.post("/face/face_analyze_e", tags=["face"], summary="얼굴 분석")
@service("face_analyze_e")
def face_analyze_e(path):
    image, items = _faces(path)
    faces = []
    for item in items:
        x1, y1, x2, y2 = item["box"]
        crop = image[y1:y2, x1:x2]
        _a, (_g_ko, _g_en) = eng.face.age_gender.predict(crop)
        _e_ko, _e_en = eng.face.emotion.predict(crop)
        _p = eng.face.head_pose.predict(crop)
        faces.append(dict(item, **{"age": _a, "gender": _g_ko, "gender_en": _g_en,
                                   "emotion": _e_ko, "emotion_en": _e_en, "pos": _p}))
    return faces


@app.post("/face/face_analyze", tags=["face"], summary="(로봇용)얼굴 분석")
async def face_analyze(request: Request, uploadFile: UploadFile = File(...), mode: str = "all"):
    name = "face_analyze"
    path = save_upload(uploadFile, name)
    try:
        image = read_bgr(path)
        _a, (_g_ko, _g_en), _e_ko, _e_en, _p = "", ("", ""), "", "", {"direction": ""}
        if mode in ("all", "age_gender"):
            _a, (_g_ko, _g_en) = eng.face.age_gender.predict(image)
        if mode in ("all", "emotion"):
            _e_ko, _e_en = eng.face.emotion.predict(image)
        if mode in ("all", "pose"):
            _p = eng.face.head_pose.predict(image)
        return {"type": name, "result": "ok", "age": _a, "gender": _g_ko,
                "gender_en": _g_en, "emotion": _e_ko, "emotion_en": _e_en,
                "pos": _p["direction"]}
    except Exception as ex:
        return {"type": name, "result": "fail", "data": "Inference error:" + str(ex)}
    finally:
        os.path.exists(path) and os.remove(path)


@app.post("/face/face_emotion_e", tags=["face"], summary="얼굴 감정")
@service("face_emotion_e")
def face_emotion_e(path):
    image, items = _faces(path)
    faces = []
    for item in items:
        x1, y1, x2, y2 = item["box"]
        _e_ko, _e_en = eng.face.emotion.predict(image[y1:y2, x1:x2])
        faces.append(dict(item, **{"emotion": _e_ko, "emotion_en": _e_en}))
    return faces


@app.post("/face/face_age_gender_e", tags=["face"], summary="얼굴 나이 성별")
@service("face_age_gender_e")
def face_age_gender_e(path):
    image, items = _faces(path)
    faces = []
    for item in items:
        x1, y1, x2, y2 = item["box"]
        _a, (_g_ko, _g_en) = eng.face.age_gender.predict(image[y1:y2, x1:x2])
        faces.append(dict(item, **{"age": _a, "gender": _g_ko, "gender_en": _g_en}))
    return faces


@app.post("/face/face_pose_e", tags=["face"], summary="얼굴 방향")
@service("face_pose_e")
def face_pose_e(path):
    image, items = _faces(path)
    faces = []
    for item in items:
        x1, y1, x2, y2 = item["box"]
        faces.append(dict(item, **{"pos": eng.face.head_pose.predict(image[y1:y2, x1:x2])}))
    return faces


@app.post("/face/mask_detect", tags=["face"], summary="마스크 인식")
@service("mask_detect")
def mask_detect(path):
    image, items = _faces(path)
    out = []
    for item in items:
        x1, y1, x2, y2 = item["box"]
        out.append(dict(item, **eng.face.mask.predict(image[y1:y2, x1:x2])))
    return out


@app.post("/face/face_attribute", tags=["face"], summary="얼굴 속성 (VLM)")
@service("face_attribute")
def face_attribute(path):
    image, items = _faces(path)
    out = []
    for item in items[:2]:  # VLM 호출 비용 고려 상위 2명
        x1, y1, x2, y2 = item["box"]
        text = eng.vlm.generate(image[y1:y2, x1:x2], P.P_ATTR, P.MAX_TOKENS["attr"])
        out.append(dict(P.parse_attr(text), **item))
    return out


# ---------------------------------------------------------------- caption (VLM 통합)
@app.post("/caption/caption", tags=["caption"], summary="이미지 캡션")
@service("caption")
def caption(path, mode: str = "enko"):
    text = eng.vlm.generate(read_bgr(path), P.P_CAPTION, P.MAX_TOKENS["caption"])
    return P.parse_caption(text)


@app.post("/caption/caption_place_e", tags=["caption"], summary="이미지 장소 인식")
@service("caption_place_e")
def caption_place_e(path):
    text = eng.vlm.generate(read_bgr(path), P.P_PLACE, P.MAX_TOKENS["place"])
    return P.parse_place(text)


@app.post("/caption/caption_time_e", tags=["caption"], summary="이미지 시간 인식")
@service("caption_time_e")
def caption_time_e(path):
    text = eng.vlm.generate(read_bgr(path), P.P_TIME, P.MAX_TOKENS["time"])
    return {"time": P.parse_choice(text, P.TIME_CHOICES)}


@app.post("/caption/caption_weather_e", tags=["caption"], summary="이미지 날씨 인식")
@service("caption_weather_e")
def caption_weather_e(path):
    text = eng.vlm.generate(read_bgr(path), P.P_WEATHER, P.MAX_TOKENS["weather"])
    return {"weather": P.parse_choice(text, P.WEATHER_CHOICES)}


@app.post("/caption/caption_question_e", tags=["caption"], summary="이미지 질문")
@service("caption_question_e")
def caption_question_e(path, prompt: str = ""):
    text = eng.vlm.generate(read_bgr(path), P.P_QUESTION.replace("{q}", prompt),
                            P.MAX_TOKENS["question"])
    return P.parse_question(text, prompt)


@app.post("/caption/caption_tag_e", tags=["caption"], summary="이미지 태그")
@service("caption_tag_e")
def caption_tag_e(path):
    text = eng.vlm.generate(read_bgr(path), P.P_TAG, P.MAX_TOKENS["tag"])
    return P.parse_tag(text)


@app.post("/vlm/vlm_inference_e", tags=["vlm"], summary="이미지 설명 (자유 프롬프트)")
@service("vlm_inference_e")
def vlm_inference_e(path, prompt: str = ""):
    answer = eng.vlm.generate(read_bgr(path), prompt or "이 이미지를 설명하세요.",
                              P.MAX_TOKENS["free"])
    return {"answer": answer}


# ---------------------------------------------------------------- gan (변환 계열)
@app.post("/gan/cartoon", tags=["gan"], summary="카툰화 (AnimeGANv3 Hayao)")
@service("cartoon")
def gan_cartoon(path):
    from engines import to_b64_jpg
    return to_b64_jpg(eng.gan.cartoon.predict(read_bgr(path)))


@app.post("/gan/sketch", tags=["gan"], summary="스타일 변환 (AnimeGANv3 Shinkai)")
@service("sketch")
def gan_sketch(path):
    from engines import to_b64_jpg
    return to_b64_jpg(eng.gan.style.predict(read_bgr(path)))


@app.post("/gan/portrait", tags=["gan"], summary="배경 제거 (U2Net)")
@service("portrait")
def gan_portrait(path):
    from engines import to_b64_jpg
    return to_b64_jpg(eng.gan.bgremove.predict(read_bgr(path)))


@app.post("/gan/sr", tags=["gan"], summary="화질 개선 4x (SR-1032)")
@service("sr")
def gan_sr(path):
    from engines import to_b64_jpg
    return to_b64_jpg(eng.gan.sr.predict(read_bgr(path)))


@app.post("/gan/txt2image", tags=["gan"], summary="(미지원) 이미지 생성")
@app.post("/gan/txt2cbimage", tags=["gan"], summary="(미지원) 스토리북 생성")
async def gan_txt2image(request: Request):
    name = request.url.path.rsplit("/", 1)[-1]
    return {"type": name, "result": "fail",
            "data": "on-device 버전에서는 이미지 생성을 지원하지 않습니다."}


# ---------------------------------------------------------------- code
@app.post("/code/ocr", tags=["code"], summary="문자 인식")
@service("ocr")
def code_ocr(path, lang: str = "all"):
    import re
    data = []
    for item in eng.code.ocr(path):
        x1, y1 = int(item[0][0][0]), int(item[0][0][1])
        x2, y2 = int(item[0][2][0]), int(item[0][2][1])
        has_ko = bool(re.search(r"[가-힣]", item[1]))
        has_en = bool(re.search(r"[A-Za-z]", item[1]))
        if (lang == "ko" and has_en) or (lang == "en" and has_ko):
            continue
        data.append({"box": [x1, y1, x2, y2], "text": item[1],
                     "score": int(100 * item[2])})
    return data


@app.post("/code/barcode", tags=["code"], summary="QR코드 인식")
@service("barcode")
def code_barcode(path):
    return eng.code.barcode(path)


# ---------------------------------------------------------------- view
@app.get("/", response_class=HTMLResponse)
async def index():
    with open("view_project/index.html", encoding="utf-8") as f:
        return f.read()


@app.get("/blocks", response_class=HTMLResponse)
async def blocks():
    with open("view_project/blocks.html", encoding="utf-8") as f:
        return f.read()


@app.get("/monitor")
async def monitor():
    from engines import core
    return {"devices": core.available_devices}


@app.get("/system")
async def system():
    """온디바이스 상태 요약 (프론트 상단 HUD용)."""
    import engines as E
    import openvino as ov
    return {
        "ready": eng is not None,
        "devices": E.core.available_devices,
        "assign": {"vlm": E.DEV_VLM, "vision": E.DEV_GAN, "face": E.DEV_FACE, "code": "CPU"},
        "models": {
            "vlm": "Qwen2.5-VL-3B INT4",
            "detect": "YOLO11m (+pose/seg)",
            "custom": len(eng.custom.models) if eng else 0,
            "face": 5, "transform": 4, "ocr": "easyocr ko/en",
        },
        "runtime": {"openvino": ov.get_version().split("-")[0], "port": PORT},
        "offline": True,
    }


if __name__ == "__main__":
    uvicorn.run("main:app", host=HOST, port=PORT)
