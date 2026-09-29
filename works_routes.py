# -*- coding: utf-8 -*-
"""내 작품(/works) — 이름 바꾸기 · 휴지통.

목록·열기·지우기는 각 앱의 API 를 그대로 쓴다(블록 /blocks/*, 파이썬 /pycode/*,
가르치기 /custom/*, 대화 자료 /chat/db). 지우기는 이제 바로 없애지 않고 휴지통으로
간다(trash.py). 여기에는 앱마다 따로 두기 애매한 둘만 둔다.

  POST   /works/rename          {kind, id, to}   이름 바꾸기
  GET    /works/trash                            휴지통 목록
  POST   /works/trash/restore   {id}             되살리기
  DELETE /works/trash                            비우기
"""
import json
import os

from fastapi import APIRouter, Body

import trash
from code_routes import BLOCK_DIR, WORK_DIR, _safe
from paths import USER_DIR, PROJECT_DIR, DB_DIR

router = APIRouter()


def _ok(data):
    return {"result": "ok", "data": data}


def _fail(msg):
    return {"result": "fail", "data": str(msg)}


def _retitle(path, to):
    """JSON 파일의 title 만 바꾼다 — 가르치기 작품·내 AI·대화 자료는 슬러그(파일 이름)를
    다른 곳이 참조하므로(블록의 AI 블록 등) 파일 이름은 그대로 두고 보이는 이름만 바꾼다."""
    if not os.path.isfile(path):
        raise ValueError("그 작품을 찾을 수 없어요")
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    d["title"] = to
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


@router.post("/works/rename", tags=["works"], summary="작품 이름 바꾸기")
def works_rename(kind: str = Body(...), id: str = Body(...), to: str = Body(...)):
    to = str(to).strip()[:40]
    if not to:
        return _fail("새 이름을 적어 주세요")
    try:
        if kind in ("blocks", "code"):
            folder, ext = (BLOCK_DIR, ".json") if kind == "blocks" else (WORK_DIR, ".py")
            src = folder / (_safe(id) + ext)
            dst = folder / (_safe(to) + ext)
            if not src.exists():
                return _fail("그 작품을 찾을 수 없어요")
            if dst.exists() and dst != src:
                return _fail("같은 이름의 작품이 있어요")
            os.replace(src, dst)
            return _ok({"kind": kind, "name": dst.stem})
        if kind == "project":
            _retitle(os.path.join(PROJECT_DIR, os.path.basename(id) + ".json"), to)
        elif kind == "model":
            _retitle(os.path.join(USER_DIR, os.path.basename(id), "meta.json"), to)
        elif kind == "db":
            _retitle(os.path.join(DB_DIR, os.path.basename(id) + ".json"), to)
        else:
            return _fail("모르는 종류예요: %s" % kind)
        return _ok({"kind": kind, "id": id, "title": to})
    except Exception as ex:
        return _fail(ex)


@router.get("/works/trash", tags=["works"], summary="휴지통 목록 (30일 지나면 비워짐)")
def works_trash():
    return _ok(trash.listing())


@router.post("/works/trash/restore", tags=["works"], summary="휴지통에서 되살리기")
def works_trash_restore(id: str = Body(..., embed=True)):
    try:
        return _ok(trash.restore(id))
    except Exception as ex:
        return _fail(ex)


@router.delete("/works/trash", tags=["works"], summary="휴지통 비우기")
def works_trash_empty():
    return _ok({"emptied": trash.empty()})
