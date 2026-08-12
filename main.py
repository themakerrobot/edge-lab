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
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

import prompts as P

HOST = os.environ.get("VAPI_HOST", "0.0.0.0")
PORT = int(os.environ.get("VAPI_PORT", "57711"))
from paths import TMP_DIR, APPWIN_DIR, DATA_DIR   # noqa: E402  (폴더 규칙은 paths.py 한 곳에)
IMAGE_DIR = TMP_DIR + os.sep

eng = None


# Chrome / Edge 를 앱 모드(--app)로 열기 위한 후보 경로.
# 주소창·탭·북마크가 없는 전용 창으로 떠서 프로그램처럼 보인다.
_APP_BROWSERS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]


def _find_app_browser():
    for p in _APP_BROWSERS:
        if p and os.path.exists(p):
            return p
    return None


def open_browser():
    """서버가 뜨자마자 화면을 연다 — 모델 로딩은 뒤에서 계속되고,
    화면은 부팅(로딩) 안내를 보여준다.

    Chrome/Edge 가 있으면 앱 모드(--app)로 전용 창을 띄우고, 없으면 기본 브라우저로 연다.
    끄고 싶으면 VAPI_NO_BROWSER=1, 앱 모드만 끄려면 VAPI_NO_APPMODE=1 로 실행한다."""
    if os.environ.get("VAPI_NO_BROWSER"):
        return
    import subprocess
    import threading
    import webbrowser

    url = f"http://localhost:{PORT}"

    def _open():
        time.sleep(1.0)  # uvicorn 소켓 바인딩 여유
        exe = None if os.environ.get("VAPI_NO_APPMODE") else _find_app_browser()
        if exe:
            try:
                # 전용 프로필을 쓰면 이미 열려 있는 브라우저 창과 섞이지 않는다.
                profile = APPWIN_DIR
                args = [exe, f"--app={url}",
                        f"--user-data-dir={profile}",
                        "--window-size=1400,900",
                        "--no-first-run", "--no-default-browser-check"]
                # 화면 확대: VAPI_ZOOM=1.25 처럼 지정하면 처음부터 그 배율로 뜬다.
                # (미지정 시 브라우저 기본 — Ctrl + '+' 로 맞춘 배율도 프로필에 저장되어 유지된다)
                zoom = os.environ.get("VAPI_ZOOM", "").strip()
                if zoom:
                    args.append(f"--force-device-scale-factor={zoom}")
                subprocess.Popen(args)
                print("[browser] 앱 창으로 실행:", os.path.basename(exe))
                return
            except Exception as ex:
                print("[browser] 앱 모드 실패:", ex, "→ 기본 브라우저로 엽니다")
        try:
            webbrowser.open(url)
        except Exception as ex:
            print("[browser] 자동 실행 실패:", ex, "→ 직접 접속:", url)

    threading.Thread(target=_open, daemon=True).start()


# 서비스 → 실행 디바이스 (HUD 표시용)
# 배정값(DEV_*)이 아니라 **컴파일된 모델이 보고한 실제 실행 디바이스**를 쓴다.
DEVICE_OF = {}


def exec_device(obj, fallback="CPU"):
    """OpenVINO 가 실제로 어디서 실행하는지 물어본다.
    AUTO/HETERO 나 폴백이 일어나도 정확한 값이 나온다."""
    for attr in ("compiled", "compiled_model", "model"):
        c = getattr(obj, attr, None)
        if c is None:
            continue
        try:
            v = c.get_property("EXECUTION_DEVICES")
        except Exception:
            continue
        if isinstance(v, (list, tuple)):
            v = "+".join(str(x) for x in v)
        v = str(v).strip()
        if v:
            return v.split(".")[0]        # "GPU.0" -> "GPU"
    return fallback


def build_device_map():
    import engines as E
    vlm = {"place", "time", "weather", "tag", "look", "chat_ask"}
    gan = {"portrait", "sr"}
    face = {"face_detect", "face_analyze", "face_emotion", "face_age_gender"}
    # 실측: 각 그룹의 대표 모델에게 직접 물어본다
    dev_face = exec_device(eng.face.detect, E.DEV_FACE) if eng else E.DEV_FACE
    dev_gan = exec_device(eng.gan.bgremove, E.DEV_GAN) if eng else E.DEV_GAN
    dev_vlm = E.DEV_VLM          # GenAI 파이프라인은 속성 조회를 제공하지 않는다

    for k in vlm:
        DEVICE_OF[k] = dev_vlm
    for k in gan:
        DEVICE_OF[k] = dev_gan
    for k in face:
        DEVICE_OF[k] = dev_face
    for k in ("object_search", "object_pose", "object_seg",
              "object_custom", "mask_detect"):
        DEVICE_OF[k] = "CPU"
    for k in ("ocr", "barcode"):
        DEVICE_OF[k] = "CPU"
    for k in ("mesh", "hand", "mesh_calibrate"):     # MediaPipe
        DEVICE_OF[k] = "CPU"

    print(f"[devices] face={DEVICE_OF.get('face_analyze')} "
          f"gan={DEVICE_OF.get('portrait')} vlm={DEVICE_OF.get('place')} "
          f"yolo={DEVICE_OF.get('object_search')} code=CPU  (런타임 보고값)")


# ---------------------------------------------------------------- 준비 상태
# 모델 로딩은 오래 걸린다. 서버는 먼저 뜨고, 로딩은 뒤에서 돌린다.
# 화면(index.html)이 /ready 를 물어보며 진행바를 그린다.
READY = {"ready": False, "loaded": 0, "total": 0, "current": "", "error": ""}


def _load_engines():
    global eng
    import engines
    READY["total"] = engines.TOTAL_STEPS
    labels = {k: (ko, en) for k, ko, en in engines.LOAD_STEPS + engines.WARM_STEPS}

    def progress(key, index):
        READY["loaded"] = index
        READY["current"] = key
        READY["current_ko"], READY["current_en"] = labels.get(key, (key, key))

    try:
        eng = engines.Engines(progress=progress)
        build_device_map()
        READY["loaded"] = READY["total"]
        READY["current"] = ""
        READY["ready"] = True
        print("[engines] ready — 화면에서 시작할 수 있습니다")
    except Exception as ex:
        import traceback
        traceback.print_exc()
        READY["error"] = str(ex)


@asynccontextmanager
async def lifespan(app: FastAPI):
    import threading
    threading.Thread(target=_load_engines, daemon=True).start()
    print(f"! vapi-od listening on {HOST}:{PORT}")
    open_browser()
    yield


app = FastAPI(title="vapi-od", docs_url="/docs", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

# 로딩 중에도 열어 두는 경로 (페이지·정적파일·상태). 나머지 AI 호출은 503 으로 막는다.
ALLOW_WHILE_LOADING = ("/ready", "/system", "/lib", "/assets", "/fonts", "/blockly",
                       "/docs", "/openapi.json", "/favicon", "/stats", "/custom", "/pycode",
                       "/speech")


@app.middleware("http")
async def _loading_guard(request: Request, call_next):
    path = request.url.path
    if (not READY["ready"] and request.method != "OPTIONS"
            and path not in ("/", "/blocks", "/train", "/options", "/code", "/talk")
            and not path.startswith(ALLOW_WHILE_LOADING)):
        return JSONResponse(status_code=503, content={
            "type": "loading", "result": "fail",
            "data": "AI를 준비하는 중이에요. 조금만 기다려 주세요.", "elapsed_ms": 0})
    return await call_next(request)


@app.get("/ready", tags=["system"], summary="모델 준비 상태 (로딩 화면용)")
async def ready():
    return dict(READY)
os.makedirs("view_project/fonts", exist_ok=True)
if os.path.isdir("view_project/assets"):
    app.mount("/assets", StaticFiles(directory="view_project/assets"), name="assets")
app.mount("/fonts", StaticFiles(directory="view_project/fonts"), name="fonts")
if os.path.isdir("view_project/blockly"):
    app.mount("/blockly", StaticFiles(directory="view_project/blockly"), name="blockly")
if os.path.isdir("view_project/lib"):
    app.mount("/lib", StaticFiles(directory="view_project/lib"), name="lib")

import mp_routes  # noqa: E402  (MediaPipe 확장: /face/mesh, /object/hand, /face/mesh_calibrate)
app.include_router(mp_routes.router)

import train_routes  # noqa: E402  (나만의 AI: /custom/predict, /custom/upload, /custom/models ...)
app.include_router(train_routes.router)

import stats_routes  # noqa: E402  (사용 통계: 미들웨어 자동집계 + /stats/*)
stats_routes.install(app)

import code_routes  # noqa: E402  (파이썬 IDE: /pycode/run·stop·output·save ...)
app.include_router(code_routes.router)

import db_routes  # noqa: E402  (자료에서 찾아 답하기: /chat/db, /chat/find, /chat/rag)
app.include_router(db_routes.router)

import speech_routes  # noqa: E402  (음성 인식: /speech/stt — 첫 요청 때 지연 로딩)
app.include_router(speech_routes.router)


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
@app.post("/object/object_search", tags=["object"], summary="사물 인식")
@service("object_search")
def object_search(path, lang: str = "ko"):
    # 사람도 사물 목록 안에 함께 온다 (name_en == "person")
    return {"object": eng.object.search(path, lang)}


@app.post("/object/object_pose", tags=["object"], summary="포즈 인식")
@service("object_pose")
def object_pose(path):
    return eng.object.points(path)


@app.post("/object/object_seg", tags=["object"], summary="사물 영역 인식")
@service("object_seg")
def object_seg(path, lang: str = "ko"):
    return eng.object.segment(path, lang)


@app.post("/object/object_custom", tags=["object"],
          summary="Custom Yolo (fire|fall|ball|rps|number|helmet|box)")
async def object_custom(request: Request, uploadFile: UploadFile = File(...),
                          detect_mode: str = "fire", lang: str = "ko"):
    name = "object_custom"
    path = save_upload(uploadFile, name)
    dev = DEVICE_OF.get(name, "CPU")
    t0 = time.perf_counter()
    try:
        data = eng.custom.predict(detect_mode, path, lang)
        return {"type": name, "result": "ok", "detect_mode": detect_mode,
                "data": {"object": data},
                "elapsed_ms": int((time.perf_counter() - t0) * 1000), "device": dev}
    except Exception as ex:
        return {"type": name, "result": "fail", "detect_mode": detect_mode,
                "data": "Inference error:" + str(ex),
                "elapsed_ms": int((time.perf_counter() - t0) * 1000), "device": dev}
    finally:
        os.path.exists(path) and os.remove(path)


# ---------------------------------------------------------------- face
def _faces(path):
    image = read_bgr(path)
    return image, eng.face.detect.predict(image)


@app.post("/face/face_detect", tags=["face"], summary="얼굴 찾기")
@service("face_detect")
def face_detect(path, lang: str = "ko"):
    _, items = _faces(path)
    name = "얼굴" if (lang or "ko").startswith("ko") else "face"
    return [dict(it, name=name, name_en="face") for it in items]


@app.post("/face/face_analyze", tags=["face"], summary="얼굴 분석")
@service("face_analyze")
def face_analyze(path, lang: str = "ko"):
    image, items = _faces(path)
    i = 0 if (lang or "ko").startswith("ko") else 1
    faces = []
    for item in items:
        x1, y1, x2, y2 = item["box"]
        crop = image[y1:y2, x1:x2]
        age, gender = eng.face.age_gender.predict(crop)
        emotion = eng.face.emotion.predict(crop)
        faces.append(dict(item, **{"age": age,
                                   "gender": gender[i], "gender_en": gender[1],
                                   "emotion": emotion[i], "emotion_en": emotion[1],
                                   "pos": eng.face.head_pose.predict(crop, lang)}))
    return faces


@app.post("/face/face_emotion", tags=["face"], summary="얼굴 감정")
@service("face_emotion")
def face_emotion(path, lang: str = "ko"):
    image, items = _faces(path)
    i = 0 if (lang or "ko").startswith("ko") else 1
    faces = []
    for item in items:
        x1, y1, x2, y2 = item["box"]
        emotion = eng.face.emotion.predict(image[y1:y2, x1:x2])
        faces.append(dict(item, **{"emotion": emotion[i], "emotion_en": emotion[1]}))
    return faces


@app.post("/face/face_age_gender", tags=["face"], summary="얼굴 나이 성별")
@service("face_age_gender")
def face_age_gender(path, lang: str = "ko"):
    image, items = _faces(path)
    i = 0 if (lang or "ko").startswith("ko") else 1
    faces = []
    for item in items:
        x1, y1, x2, y2 = item["box"]
        age, gender = eng.face.age_gender.predict(image[y1:y2, x1:x2])
        faces.append(dict(item, **{"age": age, "gender": gender[i],
                                   "gender_en": gender[1]}))
    return faces


@app.post("/face/mask_detect", tags=["face"], summary="마스크 인식")
@service("mask_detect")
def mask_detect(path, lang: str = "ko"):
    image, items = _faces(path)
    out = []
    for item in items:
        x1, y1, x2, y2 = item["box"]
        out.append(dict(item, **eng.face.mask.predict(image[y1:y2, x1:x2], lang)))
    return out


# ---------------------------------------------------------------- vlm (사진을 보고 답한다)
# 접두사 규칙: /<묶음>/<기능>. 같은 이름을 두 번 쓰지 않는다(caption_place → place).
@app.post("/vlm/place", tags=["vlm"], summary="장소 맞히기")
@service("place")
def vlm_place(path, lang: str = "ko"):
    text = eng.vlm.generate(read_bgr(path), P.p_place(lang), P.MAX_TOKENS["place"])
    return P.parse_place(text, lang)


@app.post("/vlm/time", tags=["vlm"], summary="시간대 맞히기")
@service("time")
def vlm_time(path, lang: str = "ko"):
    text = eng.vlm.generate(read_bgr(path), P.p_time(lang), P.MAX_TOKENS["time"])
    return P.parse_time(text, lang)


@app.post("/vlm/weather", tags=["vlm"], summary="날씨 맞히기")
@service("weather")
def vlm_weather(path, lang: str = "ko"):
    text = eng.vlm.generate(read_bgr(path), P.p_weather(lang), P.MAX_TOKENS["weather"])
    return P.parse_weather(text, lang)


@app.post("/vlm/tag", tags=["vlm"], summary="핵심 낱말 뽑기")
@service("tag")
def vlm_tag(path, lang: str = "ko"):
    text = eng.vlm.generate(read_bgr(path), P.p_tag(lang), P.MAX_TOKENS["tag"])
    return P.parse_tag(text)


@app.post("/vlm/look", tags=["vlm"], summary="사진 보고 답하기 (질문을 비우면 설명)")
@service("look")
def vlm_look(path, prompt: str = "", lang: str = "ko"):
    """질문을 주면 그 질문에, 비우면 사진 설명을 답한다.

    답하는 언어는 질문을 따라간다 — 한글로 물으면 한국어, 영어로 물으면 영어.
    (질문이 비면 화면 언어를 따른다)"""
    lang = P.lang_of(prompt, lang)
    q = (prompt or "").strip() or P.p_free(lang)     # 비우면 "이 사진을 설명하세요"
    text = eng.vlm.generate(read_bgr(path), P.p_question(q, lang),
                            P.MAX_TOKENS["question"])
    return P.parse_question(text)


# ---------------------------------------------------------------- chat (사진 없이 대화)
@app.post("/chat/ask", tags=["chat"], summary="사진 없이 물어보기")
async def chat_ask(request: Request, prompt: str = "", lang: str = "ko"):
    """같은 VLM 에게 사진 없이 묻는다 — 모델을 더 올리지 않는다.

    앞말은 기억하지 않는다(한 번 묻고 한 번 답한다). 교실에서 학생마다 대화가
    섞이지 않게 하려면 기록은 화면 쪽이 들고 있어야 한다."""
    name = "chat_ask"
    t0 = time.perf_counter()
    q = (prompt or "").strip()
    if not q:
        return {"type": name, "result": "fail", "data": "물어볼 말을 적어 주세요.",
                "elapsed_ms": 0}
    try:
        answer = eng.vlm.generate_text(P.p_chat(q, P.lang_of(q, lang)),
                                       P.MAX_TOKENS["chat"])
        return {"type": name, "result": "ok", "data": {"answer": answer},
                "elapsed_ms": int((time.perf_counter() - t0) * 1000),
                "device": DEVICE_OF.get("place", "GPU")}
    except Exception as ex:
        import traceback
        traceback.print_exc()
        return {"type": name, "result": "fail", "data": "Inference error:" + str(ex),
                "elapsed_ms": int((time.perf_counter() - t0) * 1000)}


# ---------------------------------------------------------------- gan (변환 계열)
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


@app.get("/train", response_class=HTMLResponse)
async def train():
    with open("view_project/train.html", encoding="utf-8") as f:
        return f.read()


@app.get("/options", response_class=HTMLResponse)
async def options_page():
    with open("view_project/options.html", encoding="utf-8") as f:
        return f.read()


@app.get("/talk", response_class=HTMLResponse)
async def talk_page():
    with open("view_project/talk.html", encoding="utf-8") as f:
        return f.read()


@app.get("/code", response_class=HTMLResponse)
async def code_page():
    with open("view_project/code.html", encoding="utf-8") as f:
        return f.read()


@app.get("/monitor")
async def monitor():
    from engines import core
    return {"devices": core.available_devices}


# 어떤 버전으로 돌고 있는지 — 문제 생겼을 때 "언제부터" 를 찾는 근거
KEY_PACKAGES = ["openvino", "openvino-genai", "onnxruntime", "ultralytics",
                "mediapipe", "opencv-python", "numpy", "easyocr", "fastapi",
                "sounddevice", "huggingface-hub"]


@app.get("/system/packages", tags=["system"], summary="설치된 패키지 버전")
async def system_packages():
    import platform
    try:
        from importlib.metadata import version, PackageNotFoundError
    except ImportError:                       # 아주 오래된 파이썬 대비
        return {"result": "fail", "data": "버전을 읽을 수 없어요."}

    pkgs = {}
    for name in KEY_PACKAGES:
        try:
            pkgs[name] = version(name)
        except PackageNotFoundError:
            pkgs[name] = None                 # 안 깔림
        except Exception:
            pkgs[name] = "?"

    snap = os.path.join(DATA_DIR, "installed-packages.txt")
    saved = ""
    if os.path.exists(snap):
        try:
            with open(snap, encoding="utf-8", errors="replace") as f:
                saved = f.readline().strip()  # 설치 시각이 적힌 첫 줄
        except Exception:
            pass
    return {"result": "ok",
            "data": {"python": platform.python_version(), "packages": pkgs,
                     "installed_at": saved, "snapshot": os.path.exists(snap)}}


@app.post("/system/sound_settings", tags=["system"], summary="윈도우 소리 설정 열기")
async def open_sound_settings():
    """소리가 안 들릴 때 쓰는 길잡이.

    소리는 윈도우 기본 출력 장치로 나간다 — 노트북 기본이 모니터(HDMI)로 잡혀
    있으면 블록 코딩·파이썬·TTS 가 전부 조용해 보인다. 이 앱에서 장치를 따로
    고르게 하면 브라우저 소리와 파이썬 소리가 서로 다른 데로 갈라지므로,
    제대로 된 자리인 윈도우 설정을 열어 준다."""
    import subprocess
    if os.name != "nt":
        return {"result": "fail",
                "data": "윈도우에서만 열 수 있어요. 시스템 소리 설정을 직접 열어 주세요."}
    try:
        subprocess.Popen(["cmd", "/c", "start", "", "ms-settings:sound"],
                         creationflags=0x08000000)     # 창 안 띄우기
        return {"result": "ok", "data": "윈도우 소리 설정을 열었어요."}
    except Exception as ex:
        return {"result": "fail", "data": "열지 못했어요: %s" % ex}


@app.get("/system")
async def system():
    """온디바이스 상태 요약 (프론트 상단 HUD용)."""
    import engines as E
    import openvino as ov
    return {
        "ready": eng is not None,
        "devices": E.core.available_devices,
        "assign": {"vlm": DEVICE_OF.get("place", E.DEV_VLM),
                   "vision": DEVICE_OF.get("portrait", E.DEV_GAN),
                   "face": DEVICE_OF.get("face_analyze", E.DEV_FACE),
                   "code": "CPU"},
        "assign_requested": {"vlm": E.DEV_VLM, "vision": E.DEV_GAN, "face": E.DEV_FACE},
        "device_of": DEVICE_OF,          # 서비스명 -> 실행 디바이스 (프론트 HUD용)
        "models": {
            "vlm": "Gemma 3 4B INT4",
            "detect": "YOLO11m (+pose/seg)",
            "custom": len(eng.custom.models) if eng else 0,
            "face": 5, "transform": 4, "ocr": "easyocr ko/en",
        },
        "runtime": {"openvino": ov.get_version().split("-")[0], "port": PORT},
        "offline": True,
    }


if __name__ == "__main__":
    # 교실에서는 요청 한 줄 한 줄이 콘솔을 가득 채운다 — 기본은 조용히 띄우고,
    # 문제를 볼 때만 VAPI_VERBOSE=1 로 실행 기록을 켠다. (오류·경고는 항상 나온다)
    verbose = bool(os.environ.get("VAPI_VERBOSE"))
    # app 을 문자열("main:app")로 주면 uvicorn 이 이 파일을 한 번 더 import 한다
    # (__main__ 과 main, 두 벌이 됨 → 시작 안내가 두 줄씩 찍히고 준비도 두 번 한다).
    # 자동 재시작을 쓰지 않으므로 객체를 그대로 넘긴다.
    uvicorn.run(app, host=HOST, port=PORT,
                log_level="info" if verbose else "warning",
                access_log=verbose)