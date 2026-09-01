# -*- coding: utf-8 -*-
# edge-lab : 사용 통계 (오프라인, 이 PC 안에서만)
# 기존 파일을 건드리지 않는 독립 모듈 — main.py에 두 줄만 추가해 연결한다:
#   import stats_routes
#   stats_routes.install(app)
#
# 수집 항목
#   - API 호출 수/시간/실패 : 미들웨어가 자동 집계 (페이지가 뭘 하든 빠짐없이 잡힌다)
#   - 페이지 열람/체류시간   : 브라우저가 보낸다 (활동 중일 때만 센다)
#   - 이벤트                : 블록 실행, 학습 실행, 모델 저장 등
#
# 개인정보는 담지 않는다. 누가 썼는지는 기록하지 않고 횟수와 시간만 센다.
import json
import os
import threading
import time

from fastapi import APIRouter, Body, Query, Request

router = APIRouter()

from paths import STATS_DIR  # noqa: E402
STATS_PATH = os.path.join(STATS_DIR, "usage.json")
FLUSH_EVERY = 20          # 이만큼 쌓이면 저장
FLUSH_SECONDS = 15        # 또는 이만큼 지나면 저장
PAGES = ("index", "blocks", "code", "train", "talk", "options")
SKIP_PREFIX = ("/stats", "/assets", "/fonts", "/lib", "/blockly", "/docs", "/openapi",
               "/favicon",
               # 아래는 화면이 배경에서 계속 부르는 내부 호출이다 — 아이가 "쓴" 것이
               # 아니므로 리포트에서 빼야 한다. 전에는 /ready 가 1등으로 찍혔다.
               "/ready", "/system", "/pycode/out", "/pycode/frame", "/custom/reports")

_lock = threading.Lock()
_dirty = 0
_last_flush = 0.0
_S = None


def _empty():
    return {
        "since": time.strftime("%Y-%m-%d %H:%M:%S"),
        "pages": {},        # page -> {opens, seconds}
        "api": {},          # path -> {n, ms, fail}
        "events": {},       # name -> n
        "daily": {},        # YYYY-MM-DD -> {opens, api, seconds}
    }


def _load():
    global _S, _last_flush
    if _S is not None:
        return _S
    try:
        with open(STATS_PATH, encoding="utf-8") as f:
            _S = json.load(f)
        for k in ("pages", "api", "events", "daily"):
            _S.setdefault(k, {})
        _S.setdefault("since", time.strftime("%Y-%m-%d %H:%M:%S"))
    except Exception:
        _S = _empty()
    _last_flush = time.time()
    return _S


def _flush(force=False):
    global _dirty, _last_flush
    if _S is None:
        return
    if not force and _dirty < FLUSH_EVERY and (time.time() - _last_flush) < FLUSH_SECONDS:
        return
    try:
        os.makedirs(STATS_DIR, exist_ok=True)
        tmp = STATS_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(_S, f, ensure_ascii=False, indent=1)
        os.replace(tmp, STATS_PATH)
        _dirty = 0
        _last_flush = time.time()
    except Exception as ex:
        print("[stats] save failed:", ex)


def _today(s):
    d = time.strftime("%Y-%m-%d")
    return s["daily"].setdefault(d, {"opens": 0, "api": 0, "seconds": 0})


def _norm(path):
    """/custom/models/가위바위보 -> /custom/models/*  (경로 변수는 뭉뚱그린다)"""
    parts = [p for p in path.split("/") if p]
    if len(parts) >= 3:
        parts = parts[:2] + ["*"]
    return "/" + "/".join(parts) if parts else "/"


def install(app):
    """미들웨어 + 라우터를 한 번에 붙인다."""
    @app.middleware("http")
    async def _count(request: Request, call_next):
        path = request.url.path
        if path.startswith(SKIP_PREFIX) or request.method == "OPTIONS":
            return await call_next(request)
        t0 = time.perf_counter()
        resp = await call_next(request)
        ms = int((time.perf_counter() - t0) * 1000)
        try:
            global _dirty
            with _lock:
                s = _load()
                key = _norm(path)
                e = s["api"].setdefault(key, {"n": 0, "ms": 0, "fail": 0})
                e["n"] += 1
                e["ms"] += ms
                if resp.status_code >= 400:
                    e["fail"] += 1
                _today(s)["api"] += 1
                _dirty += 1
                _flush()
        except Exception:
            pass
        return resp

    app.include_router(router)
    print("[stats] usage tracking on ->", STATS_PATH)


# ---------------------------------------------------------------- 수집
@router.post("/stats/event", tags=["stats"], summary="페이지 체류/이벤트 기록")
async def stats_event(request: Request, body: dict = Body(...)):
    """{page, seconds, open, events:{name:n}} — 브라우저가 30초마다 보낸다."""
    global _dirty
    page = str(body.get("page", ""))[:16]
    if page not in PAGES:
        page = "etc"
    seconds = int(min(max(body.get("seconds", 0), 0), 600))
    opened = bool(body.get("open"))
    events = body.get("events") or {}
    with _lock:
        s = _load()
        p = s["pages"].setdefault(page, {"opens": 0, "seconds": 0})
        if opened:
            p["opens"] += 1
            _today(s)["opens"] += 1
        p["seconds"] += seconds
        _today(s)["seconds"] += seconds
        if isinstance(events, dict):
            for k, v in list(events.items())[:20]:
                try:
                    n = int(v)
                except Exception:
                    continue
                if 0 < n < 10000:
                    s["events"][str(k)[:32]] = s["events"].get(str(k)[:32], 0) + n
        _dirty += 1
        _flush()
    return {"type": "stats_event", "result": "ok", "data": {"page": page}}


# ---------------------------------------------------------------- 조회 / 초기화
@router.get("/stats/summary", tags=["stats"], summary="사용 통계 요약")
async def stats_summary(request: Request):
    with _lock:
        s = _load()
        api = sorted(
            ({"path": k, "n": v["n"], "fail": v["fail"],
              "avg_ms": int(v["ms"] / v["n"]) if v["n"] else 0}
             for k, v in s["api"].items()), key=lambda x: -x["n"])
        pages = [{"page": k, "opens": v["opens"], "seconds": v["seconds"]}
                 for k, v in sorted(s["pages"].items())]
        daily = [{"date": k, **v} for k, v in sorted(s["daily"].items())][-14:]
        data = {
            "since": s["since"],
            "pages": pages,
            "api": api[:30],
            "api_total": sum(v["n"] for v in s["api"].values()),
            "events": dict(sorted(s["events"].items(), key=lambda x: -x[1])),
            "daily": daily,
            "seconds_total": sum(p["seconds"] for p in pages),
        }
    return {"type": "stats_summary", "result": "ok", "data": data}


@router.delete("/stats", tags=["stats"], summary="통계 초기화 (다음 반 시작 전)")
async def stats_reset(request: Request, confirm: str = Query("")):
    global _S
    if confirm != "yes":
        return {"type": "stats_reset", "result": "fail", "data": "confirm=yes 가 필요합니다"}
    with _lock:
        _S = _empty()
        _flush(force=True)
    return {"type": "stats_reset", "result": "ok", "data": {"reset": True}}


def snapshot_path():
    """다른 모듈(export)에서 현재 통계 파일 경로를 얻을 때 사용."""
    with _lock:
        _flush(force=True)
    return STATS_PATH
