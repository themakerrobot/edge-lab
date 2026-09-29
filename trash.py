# -*- coding: utf-8 -*-
"""trash — 지운 작품을 바로 없애지 않고 작업폴더의 .trash 로 옮긴다.

아이들은 [지우기] 를 잘못 누른다. 블록·파이썬·가르치기 작품·내가 가르친 AI·대화 자료를
지우면 여기로 오고, 내 작품(/works)의 휴지통에서 되살린다. 30일이 지나면 저절로 비운다.

  작업폴더/.trash/<id>/trash.json   {id, kind, label, at, items:[{orig, name}]}
  작업폴더/.trash/<id>/<원래 파일·폴더>

점(.)으로 시작하는 폴더라 작업폴더 목록(/system/files)에는 나오지 않는다.
선생님의 "학생 결과물 전체 삭제" 는 여기를 거치지 않는다 — 다음 반을 위해 비우는 일이라서.
"""
import json
import os
import re
import shutil
import time
import uuid

import paths

KEEP_DAYS = 30
_ID = re.compile(r"^\d{8}-\d{6}-[0-9a-f]{6}$")


def _root():
    return os.path.join(paths.WORK_ROOT, ".trash")


def put(kind, label, items):
    """items(파일·폴더 경로)를 휴지통 한 칸으로 옮긴다. 옮긴 것이 없으면 None."""
    items = [p for p in items if p and os.path.exists(p)]
    if not items:
        return None
    tid = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
    d = os.path.join(_root(), tid)
    os.makedirs(d, exist_ok=True)
    moved = []
    for p in items:
        name = os.path.basename(os.path.normpath(p))
        shutil.move(p, os.path.join(d, name))
        moved.append({"orig": os.path.relpath(os.path.normpath(p), paths.WORK_ROOT), "name": name})
    with open(os.path.join(d, "trash.json"), "w", encoding="utf-8") as f:
        json.dump({"id": tid, "kind": kind, "label": str(label or ""), "at": time.time(), "items": moved},
                  f, ensure_ascii=False, indent=2)
    return tid


def _read(tid):
    try:
        with open(os.path.join(_root(), tid, "trash.json"), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def purge():
    """KEEP_DAYS 가 지난 것을 비운다."""
    root = _root()
    if not os.path.isdir(root):
        return
    cut = time.time() - KEEP_DAYS * 86400
    for tid in os.listdir(root):
        m = _read(tid) if _ID.match(tid) else None
        if m is None or m.get("at", 0) < cut:
            shutil.rmtree(os.path.join(root, tid), ignore_errors=True)


def listing():
    purge()
    root = _root()
    if not os.path.isdir(root):
        return []
    out = [m for m in (_read(t) for t in os.listdir(root) if _ID.match(t)) if m]
    return sorted(out, key=lambda m: -m.get("at", 0))


def _free(target):
    """되살릴 자리에 같은 이름이 있으면 "-되살림" 을 붙인다 — 새로 만든 것을 덮지 않게.
    괄호·빈칸은 쓰지 않는다: 블록·파이썬은 이름에서 괄호를 걸러 내고(code_routes._safe),
    가르치기·자료는 빈칸을 "-" 로 바꿔(_slugify) 찾으므로 되살린 것을 못 연다."""
    if not os.path.exists(target):
        return target
    base, ext = os.path.splitext(target) if os.path.isfile(target) else (target, "")
    k = 1
    while True:
        cand = "%s-되살림%s%s" % (base, "" if k == 1 else str(k), ext)
        if not os.path.exists(cand):
            return cand
        k += 1


def _reslug(path):
    """이름이 바뀌어 되살아난 가르치기 작품·자료·내 AI 는 안에 적힌 slug 도 새 이름으로.
    목록은 파일 안의 slug 로 여는데, 그대로 두면 같은 이름의 다른(새) 것을 연다."""
    meta = os.path.join(path, "meta.json") if os.path.isdir(path) else path
    if not meta.endswith(".json") or not os.path.isfile(meta):
        return
    try:
        with open(meta, encoding="utf-8") as f:
            d = json.load(f)
        if isinstance(d, dict) and "slug" in d:
            d["slug"] = os.path.splitext(os.path.basename(path))[0] if not os.path.isdir(path) else os.path.basename(path)
            with open(meta, "w", encoding="utf-8") as f:
                json.dump(d, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def restore(tid):
    if not _ID.match(str(tid)):
        raise ValueError("휴지통 번호가 이상해요")
    m = _read(tid)
    if m is None:
        raise ValueError("휴지통에 없어요")
    work = os.path.normpath(paths.WORK_ROOT)
    back = []
    for it in m.get("items", []):
        target = os.path.normpath(os.path.join(work, it["orig"]))
        if os.path.commonpath([work, target]) != work:       # 작업폴더 밖으로는 되살리지 않는다
            continue
        src = os.path.join(_root(), tid, it["name"])
        if not os.path.exists(src):
            continue
        os.makedirs(os.path.dirname(target), exist_ok=True)
        want = target
        target = _free(target)
        shutil.move(src, target)
        if target != want:
            _reslug(target)
        back.append(os.path.relpath(target, work))
    shutil.rmtree(os.path.join(_root(), tid), ignore_errors=True)
    return {"id": tid, "kind": m.get("kind"), "label": m.get("label"), "restored": back}


def empty():
    shutil.rmtree(_root(), ignore_errors=True)
    return True
