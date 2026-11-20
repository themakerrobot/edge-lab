# -*- coding: utf-8 -*-
"""얼굴 AI — 누구인지 알아보기(얼굴 등록 · 구분) + 나이 · 성별 · 감정 · 방향 · 거리 · 마스크를 한 번에.

  POST /face/who        사진 → 얼굴마다 {box, name(등록한 이름 또는 모르는 사람), known, match(오차도) ...
                        + 고른 정보(info=age,gender,emotion,dir,dist,mask)}
  POST /face/register   사진 + name → 가장 큰 얼굴을 그 이름으로 등록 (같은 사람을 여러 번 등록하면 더 잘 알아본다)
  GET  /face/db         등록한 이름 · 횟수 (숫자는 안 보낸다)
  POST /face/db/delete  {name} 그 이름을 모두 지운다
  POST /face/db/clear   모두 지운다
  GET  /face/db/file    명단 파일 받기 — 파이보 · 파이브레인 Face.load_db() 로 바로 연다
  POST /face/db/file    명단 파일 열기(파이보 Face.save_db() 가 쓴 파일) — 지금 명단을 바꾼다

얼굴 구분은 파이보와 같은 모델(face-reidentification-retail-0095) · 같은 정렬 · 같은 판정(facedb.py).
명단은 작업폴더 face/facedb.json — 사진은 저장하지 않는다(숫자 256개만). 인터넷으로 나가지 않는다.
"""
import os
import time
import uuid

import cv2
from fastapi import APIRouter, Body, File, Request, UploadFile
from fastapi.responses import JSONResponse

import facedb as FDB
import hub
import paths
from paths import TMP_DIR
from i18n import t as _t                        # noqa: E402  서버 글 한/영 (i18n.py)

router = APIRouter()
INFO_ALL = ("age", "gender", "emotion", "dir", "dist", "mask")
NO_MODEL = ("얼굴 구분 모델이 없어요 — 설치를 다시 돌려 주세요 (models/face/face-reidentification-retail-0095.xml)",
            "The face ID model is missing — run the setup again (models/face/face-reidentification-retail-0095.xml)")


def db_path():
    """작업폴더를 옮길 수 있어 부를 때마다 묻는다."""
    return os.path.join(paths.WORK_ROOT, "face", "facedb.json")


DB = FDB.FaceDB(db_path)


def _ok(data, t0=None, name="face"):
    out = {"type": name, "result": "ok", "data": data}
    if t0 is not None:
        out["elapsed_ms"] = int((time.perf_counter() - t0) * 1000)
        out["device"] = hub.device_of("face_analyze", "CPU")
    return out


def _fail(msg, t0=None, name="face"):
    out = {"type": name, "result": "fail", "data": str(msg)}
    if t0 is not None:
        out["elapsed_ms"] = int((time.perf_counter() - t0) * 1000)
    return out


def _read_upload(upload):
    path = os.path.join(TMP_DIR, "face-" + str(uuid.uuid4()) + ".jpg")
    os.makedirs(TMP_DIR, exist_ok=True)
    with open(path, "wb") as f:
        f.write(upload.file.read())
    try:
        img = cv2.imread(path)
    finally:
        if os.path.exists(path):
            os.remove(path)
    if img is None:
        raise ValueError(_t("사진을 읽을 수 없어요", "Can't read the photo"))
    return img


def _embed(eng, bgr, box):
    import mp_routes
    return eng.face.reid.embed(bgr, box, mp_routes.face_points(bgr, box))


@router.post("/face/who", tags=["face"], summary="누구인지 알아보기 + 얼굴 정보 (나이 · 성별 · 감정 · 방향 · 거리 · 마스크)")
async def face_who(request: Request, uploadFile: UploadFile = File(...), lang: str = "ko",
                   info: str = ",".join(INFO_ALL)):
    t0 = time.perf_counter()
    try:
        eng = hub.engines()
        bgr = _read_upload(uploadFile)
        want = {w.strip() for w in str(info).split(",") if w.strip()}
        ko = str(lang or "ko").startswith("ko")
        faces = eng.face.detect.predict(bgr)
        dists = []
        if "dist" in want and faces:
            import mp_routes
            dists = mp_routes.face_distances(bgr, [f["box"] for f in faces])
        has_db = eng.face.reid is not None and DB.summary()["total"] > 0
        out = []
        for i, f in enumerate(faces):
            x1, y1, x2, y2 = f["box"]
            crop = bgr[y1:y2, x1:x2]
            it = dict(f)
            if eng.face.reid is None:
                m = {"name": FDB.GUEST, "match": 0.0, "max": "", "known": False}
            elif has_db:
                m = DB.match(_embed(eng, bgr, f["box"]))
            else:
                m = {"name": FDB.GUEST, "match": 0.0, "max": "", "known": False}
            it["known"] = m["known"]
            it["match"] = m["match"]
            it["max"] = m["max"]
            it["name_en"] = m["name"]                         # 비교용 — 모르는 사람은 Guest (파이보와 같다)
            it["name"] = m["name"] if m["known"] else ("모르는 사람" if ko else "Unknown")
            if crop.size == 0:
                out.append(it)
                continue
            if "age" in want or "gender" in want:
                age, gender = eng.face.age_gender.predict(crop)
                if "age" in want:
                    it["age"] = age
                if "gender" in want:
                    it["gender"], it["gender_en"] = (gender[0] if ko else gender[1]), gender[1]
            if "emotion" in want:
                emo = eng.face.emotion.predict(crop)
                it["emotion"], it["emotion_en"] = (emo[0] if ko else emo[1]), emo[1]
            if "dir" in want:
                pose = eng.face.head_pose.predict(crop, lang)
                it["direction"], it["direction_en"] = pose["direction"], pose["direction_en"]
            if "dist" in want:
                it["distance"] = dists[i] if i < len(dists) else 0
            if "mask" in want:
                mk = eng.face.mask.predict(crop, lang)
                it["mask"], it["mask_name"] = bool(mk.get("mask")), mk.get("name", "")
            out.append(it)
        return _ok(out, t0, "face_who")
    except Exception as ex:
        import traceback
        traceback.print_exc()
        return _fail("Inference error:" + str(ex), t0, "face_who")


@router.post("/face/register", tags=["face"], summary="얼굴 등록 — 사진에서 가장 큰 얼굴을 그 이름으로")
async def face_register(request: Request, uploadFile: UploadFile = File(...), name: str = "",
                        lang: str = "ko"):
    t0 = time.perf_counter()
    try:
        eng = hub.engines()
        if eng.face.reid is None:
            return _fail(_t(*NO_MODEL), t0, "face_register")
        bgr = _read_upload(uploadFile)
        faces = eng.face.detect.predict(bgr)
        if not faces:
            return _fail(_t("얼굴을 찾지 못했어요 — 얼굴이 잘 보이게 해 주세요", "No face found — make the face clearly visible"), t0, "face_register")
        f = max(faces, key=lambda it: (it["box"][2] - it["box"][0]) * (it["box"][3] - it["box"][1]))
        res = DB.add(name, _embed(eng, bgr, f["box"]))
        res["box"] = f["box"]
        res["faces"] = len(faces)
        return _ok(res, t0, "face_register")
    except FDB.FaceDBError as ex:
        return _fail(str(ex), t0, "face_register")
    except Exception as ex:
        import traceback
        traceback.print_exc()
        return _fail("Inference error:" + str(ex), t0, "face_register")


@router.get("/face/db", tags=["face"], summary="등록한 얼굴 — 이름과 횟수")
def face_db():
    try:
        s = DB.summary()
        eng = hub.engines(required=False)
        s["ready"] = bool(eng is not None and getattr(getattr(eng, "face", None), "reid", None) is not None)
        s["file"] = db_path()
        return _ok(s)
    except FDB.FaceDBError as ex:
        return _fail(str(ex))


@router.post("/face/db/delete", tags=["face"], summary="등록한 얼굴 지우기 (그 이름 모두)")
def face_db_delete(name: str = Body(..., embed=True)):
    try:
        return _ok({"deleted": DB.delete(str(name)), **DB.summary()})
    except FDB.FaceDBError as ex:
        return _fail(str(ex))


@router.post("/face/db/clear", tags=["face"], summary="등록한 얼굴 모두 지우기")
def face_db_clear():
    DB.clear()
    return _ok(DB.summary())


@router.get("/face/db/file", tags=["face"], summary="명단 파일 받기 (파이보 Face.load_db 로 연다)")
def face_db_file():
    try:
        return JSONResponse(DB.export(), headers={"Content-Disposition": 'attachment; filename="facedb.json"'})
    except FDB.FaceDBError as ex:
        return JSONResponse(_fail(str(ex)))


@router.post("/face/db/file", tags=["face"], summary="명단 파일 열기 (파이보 Face.save_db 가 쓴 파일) — 지금 명단을 바꾼다")
async def face_db_file_load(uploadFile: UploadFile = File(...)):
    try:
        raw = uploadFile.file.read(5 * 1024 * 1024 + 1)
        if len(raw) > 5 * 1024 * 1024:
            return _fail(_t("파일이 너무 커요 (5MB 까지)", "The file is too big (up to 5MB)"))
        DB.replace(raw)
        return _ok(DB.summary())
    except FDB.FaceDBError as ex:
        return _fail(str(ex))
