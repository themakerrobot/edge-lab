# -*- coding: utf-8 -*-
"""내가 준 자료에서 찾아 답하기 (RAG).

  POST /chat/db        자료 만들기 (제목 + 글, 또는 txt 파일)
  GET  /chat/db        자료 목록
  GET  /chat/db/{slug} 자료 하나 (조각 미리보기)
  DEL  /chat/db/{slug} 자료 지우기
  POST /chat/find      질문과 가까운 조각만 찾기 (답은 안 만든다 — 수업용)
  POST /chat/rag       자료에서 찾아 답하기

저장 자리는 data/db/<slug>.json — 아이가 만든 것이므로 models/ 가 아니라 data/ 다.
전체 초기화(data 삭제)에 함께 지워진다.

왜 "찾기"와 "답하기" 를 나눴나 — 아이에게 RAG 는 두 단계다.
① 질문과 비슷한 문장을 찾는다 ② 그 문장을 보고 답을 만든다.
①만 따로 볼 수 있어야 "AI 가 어디서 가져왔는지" 를 가르칠 수 있다.
"""
import base64
import json
import os
import re
import time
import uuid

import numpy as np
from fastapi import APIRouter, File, Form, Query, Request, UploadFile

import hub
from paths import DB_DIR

router = APIRouter()

MAX_TEXT = 400_000          # 자료 한 개의 글자 수 상한 (약 200쪽)
CHUNK = 350                 # 조각 하나의 길이(글자)
OVERLAP = 60                # 조각끼리 겹치는 길이 — 문장이 잘려도 뜻이 이어지게
TOP_K = 4                   # 기본으로 가져올 조각 수
# 가장 닮은 조각조차 이 점수 아래면 자료와 상관없는 질문으로 보고 모델을 부르지 않는다.
# 처음 0.72 로 잡았다가 실기에서 맞는 질문(시간표)까지 걸러냈다 — e5-small INT8 의
# 한국어 점수는 생각보다 낮게 나온다. 그래서 0.60 으로 내리고, 문턱에 걸리면 점수를
# 콘솔에 찍어 눈으로 맞출 수 있게 했다. 화면 "찾은 곳"에도 점수가 보인다.
MIN_SCORE = float(os.environ.get("VAPI_RAG_MIN", "0.60"))
# 이 점수 이상으로 닮은 조각이 있는데 모델이 "찾지 못했어요"라고 하면 말이 안 맞는 것 —
# 빠져나갈 문구가 없는 프롬프트로 한 번 더 시킨다. (실기: 규칙 질문이 0.88인데도 못 찾았다고 함)
SURE_SCORE = float(os.environ.get("VAPI_RAG_SURE", "0.80"))


def _eng():
    return hub.engines()          # import main 은 금물 — main.py 가 통째로 다시 실행된다


def _ok(data, t0=None, device=None):
    out = {"type": "db", "result": "ok", "data": data,
           "elapsed_ms": int((time.perf_counter() - t0) * 1000) if t0 else 0}
    if device:
        out["device"] = device                # 화면 상태바·점검 도구가 장치를 보여 준다
    return out


def _fail(msg, t0=None):
    return {"type": "db", "result": "fail", "data": msg,
            "elapsed_ms": int((time.perf_counter() - t0) * 1000) if t0 else 0}


def _slugify(text):
    s = re.sub(r"[^0-9a-zA-Z가-힣]+", "-", (text or "").strip()).strip("-").lower()
    return s[:40] or ("db-" + uuid.uuid4().hex[:6])


def _uniq(base):
    s, k = base, 2
    while os.path.exists(os.path.join(DB_DIR, s + ".json")):
        s = "%s-%d" % (base, k)
        k += 1
    return s


def split_text(text):
    """긴 글을 조각으로 나눈다.

    먼저 빈 줄(문단)로 끊고, 문단이 길면 문장 부호에서 자른다.
    조각이 너무 짧으면 앞 조각에 붙인다 — 한 문장짜리 조각은 검색에 도움이 안 된다.
    """
    text = re.sub(r"\r\n?", "\n", str(text)).strip()
    parts = []
    for para in re.split(r"\n\s*\n", text):
        para = para.strip()
        if not para:
            continue
        if len(para) <= CHUNK:
            parts.append(para)
            continue
        sents = re.split(r"(?<=[.!?。？！])\s+|\n", para)
        buf = ""
        for sent in sents:
            if len(buf) + len(sent) + 1 <= CHUNK:
                buf = (buf + " " + sent).strip()
            else:
                if buf:
                    parts.append(buf)
                # 한 문장이 CHUNK 보다 길면 통째로 잘라 넣는다
                while len(sent) > CHUNK:
                    parts.append(sent[:CHUNK])
                    sent = sent[CHUNK - OVERLAP:]
                buf = sent
        if buf:
            parts.append(buf)

    out = []
    for p in parts:
        if out and len(p) < 40:                 # 너무 짧은 조각은 앞에 붙인다
            out[-1] = (out[-1] + " " + p)[:CHUNK * 2]
        else:
            out.append(p)
    # 맨 앞이 짧으면(글 제목 같은 것) 붙일 앞이 없다 — 뒤에 붙인다
    while len(out) > 1 and len(out[0]) < 40:
        out[1] = (out[0] + " " + out[1])[:CHUNK * 2]
        out.pop(0)
    return out


def _b64(vecs):
    return base64.b64encode(np.asarray(vecs, np.float32).tobytes()).decode("ascii")


def _unb64(s, dim):
    raw = np.frombuffer(base64.b64decode(s), np.float32)
    return raw.reshape(-1, dim)


def _load(slug):
    p = os.path.join(DB_DIR, _slugify(slug) + ".json")
    if not os.path.exists(p):
        raise ValueError("자료를 찾을 수 없어요: %s" % slug)
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def _search(slug, question, top_k=TOP_K):
    """질문과 가까운 조각을 고른다 — 벡터가 정규화돼 있어 내적이 곧 닮은 정도다."""
    db = _load(slug)
    vecs = _unb64(db["vectors"], db.get("dim", 384))
    q = _eng().embed.encode([question], kind="query")[0]
    score = vecs @ np.asarray(q, np.float32)
    order = np.argsort(-score)[:max(1, int(top_k))]
    return db, [{"text": db["chunks"][i], "score": round(float(score[i]), 3),
                 "no": int(i) + 1} for i in order]


def _is_not_found(answer):
    """답이 "찾지 못했어요" 문구뿐인지 (구두점만 다른 것 포함)."""
    import prompts as P
    core = re.sub(r"[\s\.\!\?,·…\"']+", "", answer or "")
    return any(re.sub(r"[\s\.\!\?,·…\"']+", "", ph) == core
               for ph in P.NOT_FOUND.values())


def _tidy_answer(answer, lang="ko"):
    """작은 모델이 답을 해 놓고도 "자료에서 찾지 못했어요"를 뒤에 붙이는 버릇을 걷어낸다.

    문구만 온 답(진짜 못 찾음)은 그대로 두고, 실제 답과 섞여 온 경우에만 문구를 뺀다."""
    import prompts as P
    text = (answer or "").strip()
    for phrase in P.NOT_FOUND.values():
        if phrase not in text:
            continue
        rest = text.replace(phrase, " ")
        rest = re.sub(r"[\s\.\!\?,·…\"'()\[\]]+", " ", rest).strip()
        if len(rest) >= 8:                     # 문구 말고도 답이 있다 -> 문구를 뺀다
            text = re.sub(r"[\s\.\!]*" + re.escape(phrase) + r"[\s\.\!]*", " ", text)
            text = re.sub(r"\s{2,}", " ", text).strip()
    return text


# ---------------------------------------------------------------- 자료 만들기
@router.post("/chat/db", tags=["chat"], summary="자료 만들기 (글 또는 txt 파일)")
async def db_create(request: Request, title: str = Form(...), text: str = Form(""),
                    uploadFile: UploadFile = File(None)):
    t0 = time.perf_counter()
    body = text or ""
    if uploadFile is not None:
        try:
            body = (body + "\n" + uploadFile.file.read().decode("utf-8", "replace")).strip()
        except Exception as ex:
            return _fail("파일을 읽지 못했어요: %s" % ex, t0)
    body = body.strip()
    if not body:
        return _fail("자료로 쓸 글을 넣어 주세요.", t0)
    if len(body) > MAX_TEXT:
        return _fail("글이 너무 길어요 (%d자). %d자 아래로 줄여 주세요."
                     % (len(body), MAX_TEXT), t0)

    chunks = split_text(body)
    if not chunks:
        return _fail("나눌 만한 글이 없어요.", t0)
    try:
        vecs = _eng().embed.encode(chunks, kind="passage")
    except Exception as ex:
        return _fail(str(ex), t0)

    os.makedirs(DB_DIR, exist_ok=True)
    slug = _uniq(_slugify(title))
    meta = {"slug": slug, "title": title.strip(), "chunks": chunks,
            "dim": len(vecs[0]), "vectors": _b64(vecs),
            "chars": len(body), "count": len(chunks),
            "saved": time.strftime("%Y-%m-%d %H:%M:%S")}
    with open(os.path.join(DB_DIR, slug + ".json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False)
    return _ok({k: meta[k] for k in ("slug", "title", "count", "chars", "saved")}, t0)


@router.get("/chat/db", tags=["chat"], summary="자료 목록")
async def db_list(request: Request):
    os.makedirs(DB_DIR, exist_ok=True)
    items = []
    for n in sorted(os.listdir(DB_DIR)):
        if not n.endswith(".json"):
            continue
        try:
            with open(os.path.join(DB_DIR, n), encoding="utf-8") as f:
                d = json.load(f)
            items.append({k: d.get(k) for k in ("slug", "title", "count", "chars", "saved")})
        except Exception:
            pass
    return _ok(items)


@router.get("/chat/db/{slug}", tags=["chat"], summary="자료 하나 (조각 미리보기)")
async def db_get(request: Request, slug: str, limit: int = 20):
    try:
        d = _load(slug)
    except ValueError as ex:
        return _fail(str(ex))
    return _ok({"slug": d["slug"], "title": d["title"], "count": d["count"],
                "chars": d["chars"], "saved": d["saved"],
                "chunks": d["chunks"][:max(1, int(limit))]})


@router.delete("/chat/db/{slug}", tags=["chat"], summary="자료 지우기")
async def db_delete(request: Request, slug: str):
    p = os.path.join(DB_DIR, _slugify(slug) + ".json")
    if not os.path.exists(p):
        return _fail("자료를 찾을 수 없어요: %s" % slug)
    os.remove(p)
    return _ok({"slug": _slugify(slug), "deleted": True})


# ---------------------------------------------------------------- 찾기 / 답하기
@router.post("/chat/find", tags=["chat"], summary="자료에서 비슷한 곳 찾기 (답은 안 만듦)")
async def db_find(request: Request, db: str = Query(...), prompt: str = Query(...),
                  top_k: int = TOP_K):
    t0 = time.perf_counter()
    if not prompt.strip():
        return _fail("물어볼 말을 적어 주세요.", t0)
    try:
        meta, hits = _search(db, prompt, top_k)
    except Exception as ex:
        return _fail(str(ex), t0)
    return _ok({"db": meta["title"], "found": hits}, t0)


@router.post("/chat/rag", tags=["chat"], summary="내가 준 자료에서 찾아 답하기")
async def db_rag(request: Request, db: str = Query(...), prompt: str = Query(...),
                 lang: str = "ko", top_k: int = TOP_K):
    """찾은 조각을 그대로 붙여 AI 에게 준다 — 무엇을 보고 답했는지 함께 돌려준다."""
    import prompts as P
    t0 = time.perf_counter()
    if not prompt.strip():
        return _fail("물어볼 말을 적어 주세요.", t0)
    try:
        meta, hits = _search(db, prompt, top_k)
        lg = P.lang_of(prompt, lang)
        if hits and hits[0]["score"] < MIN_SCORE:      # 자료와 상관없는 질문
            print("[rag] 최고 점수 %.3f < 문턱 %.2f — 모델을 부르지 않고 못 찾음 처리"
                  " (질문: %s)" % (hits[0]["score"], MIN_SCORE, prompt[:30]))
            return _ok({"answer": P.NOT_FOUND[lg if lg in P.NOT_FOUND else "ko"],
                        "db": meta["title"], "found": hits}, t0)
        context = "\n".join("(%d) %s" % (h["no"], h["text"]) for h in hits)
        answer = _tidy_answer(_eng().vlm.generate_text(
            P.p_rag(prompt, context, lg), P.MAX_TOKENS["chat"]), lg)
        if _is_not_found(answer) and hits and hits[0]["score"] >= SURE_SCORE:
            # 잘 닮은 조각이 있는데 못 찾았다니 — 모델이 조건 문구에 쏠린 것. 다시 시킨다.
            print("[rag] 점수 %.2f인데 못 찾음이라 답함 — 강제 프롬프트로 재시도"
                  % hits[0]["score"])
            answer = _tidy_answer(_eng().vlm.generate_text(
                P.p_rag_force(prompt, context, lg), P.MAX_TOKENS["chat"]), lg)
    except Exception as ex:
        import traceback
        traceback.print_exc()
        return _fail(str(ex), t0)
    return _ok({"answer": answer, "db": meta["title"], "found": hits}, t0,
               device=hub.device_of("chat_ask", "GPU"))
