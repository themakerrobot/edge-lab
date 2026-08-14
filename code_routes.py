# -*- coding: utf-8 -*-
"""code_routes — 파이썬 IDE 백엔드.

- POST /pycode/run        {code}      -> {sid}   학생 코드를 로컬 프로세스로 실행
- POST /pycode/stop       {sid}                  실행 중지
- GET  /pycode/output     ?sid&pos    -> {text, done, exit}  출력 폴링
- POST /pycode/save       {name, code}
- GET  /pycode/works                  -> 저장 목록
- GET  /pycode/work       ?name       -> {name, code}
- POST /pycode/delete     {name}

학생 코드는 이 PC 의 파이썬(서버와 같은 인터프리터)으로 돌리고,
프로젝트 루트를 PYTHONPATH 에 넣어 `from themaker import *` 가 되게 한다.
cv2.imshow 창도 로컬이라 그대로 뜬다. input() 은 지원하지 않는다.
"""
import os
import sys
import time
import uuid
import signal
import threading
import subprocess
from pathlib import Path

from fastapi import APIRouter, Body, File, Query, UploadFile
from fastapi.responses import Response

router = APIRouter()

ROOT = Path(__file__).resolve().parent
from paths import PYCODE_DIR, BLOCKS_DIR       # noqa: E402
WORK_DIR = Path(PYCODE_DIR)                    # 저장한 작품
RUN_DIR = WORK_DIR / ".run"                    # 실행용 임시 파일
MAX_OUTPUT = 200_000                           # 세션당 출력 버퍼 상한(문자)
MAX_SESSIONS = 4

_sessions = {}                                 # sid -> dict(proc, buf, done, exit)
_lock = threading.Lock()


def _ok(data):
    return {"result": "ok", "data": data}


def _fail(msg):
    return {"result": "fail", "data": str(msg)}


def _reader(sid, proc):
    """자식 프로세스 stdout 을 세션 버퍼로 옮긴다."""
    try:
        for line in iter(proc.stdout.readline, b""):
            text = line.decode("utf-8", errors="replace")
            with _lock:
                s = _sessions.get(sid)
                if s is None:
                    break
                s["buf"] += text
                if len(s["buf"]) > MAX_OUTPUT:
                    s["buf"] = s["buf"][-MAX_OUTPUT:]
    except Exception:
        pass
    finally:
        code = proc.wait()
        with _lock:
            s = _sessions.get(sid)
            if s is not None:
                s["done"] = True
                s["exit"] = code


def _cleanup():
    """끝난 지 오래된 세션 정리."""
    now = time.time()
    with _lock:
        dead = [k for k, s in _sessions.items()
                if s["done"] and now - s["t0"] > 600]
        for k in dead:
            _sessions.pop(k, None)


@router.post("/pycode/run", tags=["pycode"], summary="파이썬 코드 실행")
def pycode_run(code: str = Body(..., embed=True), lang: str = "ko"):
    _cleanup()
    with _lock:
        running = sum(1 for s in _sessions.values() if not s["done"])
    if running >= MAX_SESSIONS:
        return _fail("실행 중인 코드가 너무 많아요. 먼저 정지해 주세요.")

    RUN_DIR.mkdir(parents=True, exist_ok=True)
    sid = uuid.uuid4().hex[:12]
    path = RUN_DIR / ("run_%s.py" % sid)
    path.write_text(code, encoding="utf-8")

    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUNBUFFERED"] = "1"
    env["THEMAKER_SID"] = sid          # show() 가 결과를 화면으로 보내는 통로
    env["THEMAKER_LANG"] = "en" if str(lang).startswith("en") else "ko"   # 화면 언어 = AI 이름 언어

    kw = {}
    if os.name == "nt":
        kw["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kw["preexec_fn"] = os.setsid

    proc = subprocess.Popen(
        [sys.executable, str(path)],
        cwd=str(WORK_DIR), env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL, **kw)

    with _lock:
        _sessions[sid] = {"proc": proc, "buf": "", "done": False, "exit": None,
                          "stopped": False, "t0": time.time(), "file": str(path),
                          "frame": None, "seq": 0, "caption": ""}
    threading.Thread(target=_reader, args=(sid, proc), daemon=True).start()
    return _ok({"sid": sid})


@router.post("/pycode/stop", tags=["pycode"], summary="실행 중지")
def pycode_stop(sid: str = Body(..., embed=True)):
    with _lock:
        s = _sessions.get(sid)
    if s is None:
        return _fail("no such session")
    proc = s["proc"]
    if proc.poll() is None:
        try:
            if os.name == "nt":
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                               capture_output=True, timeout=10)
            else:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except Exception:
            pass
        if proc.poll() is None:
            try:
                proc.kill()
            except Exception:
                pass
    with _lock:
        s["stopped"] = True                      # 화면에 "정지"로 표시하기 위한 표시
    return _ok({"stopped": True})


@router.get("/pycode/output", tags=["pycode"], summary="출력 가져오기 (폴링)")
def pycode_output(sid: str = Query(...), pos: int = Query(0)):
    with _lock:
        s = _sessions.get(sid)
        if s is None:
            return _fail("no such session")
        buf = s["buf"]
        done, code, stopped = s["done"], s["exit"], s.get("stopped", False)
    pos = max(0, min(pos, len(buf)))
    with _lock:
        s2 = _sessions.get(sid) or {}
        seq, cap = s2.get("seq", 0), s2.get("caption", "")
    return _ok({"text": buf[pos:], "pos": len(buf), "done": done, "exit": code,
                "stopped": stopped, "seq": seq, "caption": cap})


# ---------------------------------------------------------------- 화면(그림) 보기
@router.post("/pycode/frame", tags=["pycode"], summary="show() 결과를 화면으로 보내기")
def pycode_frame(sid: str = Query(...), caption: str = Query(""),
                 uploadFile: UploadFile = File(...)):
    """학생 코드의 show() 가 그린 그림을 받아 둔다. 화면은 폴링하며 가져간다."""
    raw = uploadFile.file.read()
    if len(raw) > 8_000_000:
        return _fail("그림이 너무 커요.")
    with _lock:
        s = _sessions.get(sid)
        if s is None:
            return _fail("no such session")
        s["frame"] = raw
        s["seq"] += 1
        s["caption"] = caption[:60]
        seq = s["seq"]
    return _ok({"seq": seq})


@router.get("/pycode/frame", tags=["pycode"], summary="화면 그림 가져오기")
def pycode_frame_get(sid: str = Query(...)):
    with _lock:
        s = _sessions.get(sid)
        raw = s.get("frame") if s else None
    if not raw:
        return _fail("no frame")
    return Response(content=raw, media_type="image/jpeg",
                    headers={"Cache-Control": "no-store"})


# ---------------------------------------------------------------- 작품 저장
def _safe(name):
    name = "".join(c for c in str(name) if c.isalnum() or c in "-_ 가-힣").strip()
    return name[:40] or "이름없음"


@router.post("/pycode/save", tags=["pycode"], summary="작품 저장")
def pycode_save(name: str = Body(...), code: str = Body(...)):
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    (WORK_DIR / (_safe(name) + ".py")).write_text(code, encoding="utf-8")
    return _ok({"saved": _safe(name)})


# ── 블록 작품 ──────────────────────────────────────────────────────────
# 파이썬 작품과 같은 규약(save/works/work)으로 맞춘다 — 두 화면이 같게 동작해야
# 아이가 헷갈리지 않는다. 다른 점은 확장자(.json)와 폴더(blocks)뿐이다.
BLOCK_DIR = Path(BLOCKS_DIR)


@router.post("/blocks/save", tags=["blocks"], summary="블록 작품 저장")
def blocks_save(name: str = Body(...), state: str = Body(...)):
    BLOCK_DIR.mkdir(parents=True, exist_ok=True)
    (BLOCK_DIR / (_safe(name) + ".json")).write_text(state, encoding="utf-8")
    return _ok({"saved": _safe(name)})


@router.get("/blocks/works", tags=["blocks"], summary="블록 작품 목록")
def blocks_works():
    if not BLOCK_DIR.exists():
        return _ok([])
    return _ok([{"name": p.stem, "mtime": int(p.stat().st_mtime)}
                for p in sorted(BLOCK_DIR.glob("*.json"))])


@router.get("/blocks/work", tags=["blocks"], summary="블록 작품 불러오기")
def blocks_work(name: str = Query(...)):
    p = BLOCK_DIR / (_safe(name) + ".json")
    if not p.exists():
        return _fail("no such work")
    return _ok({"name": p.stem, "state": p.read_text(encoding="utf-8")})


@router.delete("/blocks/work", tags=["blocks"], summary="블록 작품 지우기")
def blocks_delete(name: str = Query(...)):
    p = BLOCK_DIR / (_safe(name) + ".json")
    if p.exists():
        p.unlink()
    return _ok({"deleted": _safe(name)})


@router.get("/pycode/works", tags=["pycode"], summary="저장 목록")
def pycode_works():
    if not WORK_DIR.exists():
        return _ok([])
    items = []
    for p in sorted(WORK_DIR.glob("*.py")):
        items.append({"name": p.stem,
                      "mtime": int(p.stat().st_mtime)})
    return _ok(items)


@router.get("/pycode/work", tags=["pycode"], summary="작품 불러오기")
def pycode_work(name: str = Query(...)):
    p = WORK_DIR / (_safe(name) + ".py")
    if not p.exists():
        return _fail("no such work")
    return _ok({"name": p.stem, "code": p.read_text(encoding="utf-8")})


@router.post("/pycode/delete", tags=["pycode"], summary="작품 삭제")
def pycode_delete(name: str = Body(..., embed=True)):
    p = WORK_DIR / (_safe(name) + ".py")
    if p.exists():
        p.unlink()
    return _ok({"deleted": _safe(name)})
