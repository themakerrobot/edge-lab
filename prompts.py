# -*- coding: utf-8 -*-
# vapi-od : VLM prompt templates + output parsers
# 사진 질문과 사진 없는 대화를 VLM 하나로 처리한다.
#
# lang 파라미터 (기본 "ko")
#   - 답은 요청한 언어 하나만 만든다. 한/영을 함께 만들던 예전 방식은 없앴다
#     (출력 토큰이 두 배라 느리고, 화면에도 같은 말이 두 번 나왔다).
import json, re

MAX_TOKENS = {
    "question": 80, "free": 128, "chat": 256,
}

LANGS = ("ko", "en")


def _lang(lang):
    lang = (lang or "ko").strip().lower()[:2]
    return lang if lang in LANGS else "ko"


def lang_of(text, fallback="ko"):
    """질문에 쓰인 언어를 알아낸다 — 한글이 하나라도 있으면 한국어, 로마자만
    있으면 영어. 글자가 없으면(질문이 비었으면) 화면 언어를 그대로 쓴다."""
    t = str(text or "")
    if re.search(r"[가-힣]", t):
        return "ko"
    if re.search(r"[A-Za-z]", t):
        return "en"
    return _lang(fallback)


# ---------------------------------------------------------------- 프롬프트
_QUESTION = {
    "ko": ("사진을 보고 질문에 한국어로 짧게 답하세요. 한국어로만 쓰고, "
           "발음 표기나 영어 번역은 넣지 마세요.\n"
           '반드시 이 JSON 으로만 답하세요. {"answer": "<짧은 답>"}\n'
           "질문: {q}"),
    "en": ("Look at the photo and answer briefly in English.\n"
           'Answer only in this JSON. {"answer": "<short answer>"}\n'
           "Question: {q}"),
}

_CHAT = {
    "ko": ("아이에게 이야기하듯 한국어로 쉽고 짧게 답하세요. 세 문장을 넘기지 마세요.\n"
           "질문: {q}"),
    "en": ("Answer in easy, short English as if talking to a child. "
           "Keep it under three sentences.\n"
           "Question: {q}"),
}

# 작은 모델은 "없으면 X 라고 답하세요" 같은 조건 문구를 답 뒤에 그대로 붙이는 버릇이
# 있다(답을 해 놓고 "자료에서 찾지 못했어요"까지 이어 씀). 그래서 두 경우를 문장으로
# 갈라 말하고, 그래도 붙여 오면 db_routes 가 걷어낸다.
NOT_FOUND = {"ko": "자료에서 찾지 못했어요", "en": "I could not find it in the material"}

# 지시 순서가 중요하다 — "없으면 X라고 쓰세요" 를 마지막 지시로 두면 작은 모델이
# 자료에 답이 있어도 그쪽으로 쏠린다(실기에서 규칙 질문에 "찾지 못했어요"로 답함).
# 그래서 자료·질문을 먼저 주고, "자료 내용으로 답하라" 를 마지막에 둔다.
_RAG = {
    "ko": ("아래 자료에서 질문의 답을 찾아 아이에게 이야기하듯 한국어로 쉽고 짧게 "
           "답하세요. 세 문장을 넘기지 마세요.\n"
           "--- 자료 ---\n{c}\n--- 끝 ---\n"
           "질문: {q}\n"
           "자료에 관련 내용이 있으면 그 내용으로 답하세요. "
           "정말 없을 때만 \"자료에서 찾지 못했어요\" 라고 하세요.\n답:"),
    "en": ("Find the answer in the material below and answer in easy, short English. "
           "Keep it under three sentences.\n"
           "--- material ---\n{c}\n--- end ---\n"
           "Question: {q}\n"
           "If the material has related content, answer from it. "
           "Only when it truly does not, say \"I could not find it in the material\".\nAnswer:"),
}

_FREE = {
    "ko": "이 이미지를 설명하세요.",
    "en": "Describe this image.",
}


def p_question(q, lang="ko"):
    return _QUESTION[_lang(lang)].replace("{q}", q or "")


# 점수가 높은데도 모델이 "찾지 못했어요"라고 우길 때 쓰는 재시도 프롬프트 —
# 빠져나갈 문구를 아예 주지 않아 자료 내용으로 답할 수밖에 없게 한다.
_RAG_FORCE = {
    "ko": ("아래 자료의 내용을 바탕으로 질문에 답하세요. "
           "아이에게 이야기하듯 한국어로 쉽고 짧게, 세 문장을 넘기지 마세요.\n"
           "--- 자료 ---\n{c}\n--- 끝 ---\n질문: {q}\n답:"),
    "en": ("Answer the question using the material below. "
           "Keep it easy and short, under three sentences.\n"
           "--- material ---\n{c}\n--- end ---\nQuestion: {q}\nAnswer:"),
}


def p_rag_force(q, context, lang="ko"):
    return _RAG_FORCE[_lang(lang)].replace("{c}", context or "").replace("{q}", q or "")


def p_rag(q, context, lang="ko"):
    """내가 준 자료에서만 찾아 답하게 한다 — 지어내지 않는 것이 수업의 핵심이다."""
    return _RAG[_lang(lang)].replace("{c}", context or "").replace("{q}", q or "")


def p_chat(q, lang="ko", history="", persona=""):
    """사진 없이 묻는 말 — 같은 VLM 에게 글만 준다.

    history 는 화면이 모아 보낸 앞말(주고받은 몇 턴). 있으면 질문 앞에 붙인다.
    없으면 예전과 똑같다 — 기본은 안 보내는 쪽이다.
    """
    body = _CHAT[_lang(lang)].replace("{q}", q or "")

    # 성격 — 화면에서 고르거나 직접 적은 한두 문장. 기본 규칙(쉽게·세 문장) 앞에
    # 붙인다. 매번 같은 크기로 한 번만 붙으므로 대화가 길어져도 늘지 않는다.
    style = (persona or "").strip()
    if style:
        head = "말투: " if _lang(lang) == "ko" else "Style: "
        body = head + style + "\n" + body

    past = (history or "").strip()
    if not past:
        return body
    head = "지금까지 나눈 이야기:\n" if _lang(lang) == "ko" else "What we talked about so far:\n"
    return head + past + "\n\n" + body


def p_free(lang="ko"):
    return _FREE[_lang(lang)]


# ---------------------------------------------------------------- 파서
def _extract_json(text):
    """모델 출력에서 첫 JSON 객체/배열을 뽑아 파싱. 실패 시 None."""
    if not text:
        return None
    text = re.sub(r"```(?:json)?", "", text).strip()
    i_obj, i_arr = text.find("{"), text.find("[")
    patterns = [r"\{.*\}", r"\[.*\]"]
    if i_arr != -1 and (i_obj == -1 or i_arr < i_obj):
        patterns.reverse()  # 배열이 먼저 시작하면 배열 우선 매칭
    for pattern in patterns:
        m = re.search(pattern, text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                continue
    return None


_PLACE_HOLDER = re.compile(
    r"^\s*<[^<>]{0,40}>\s*|\s*<[^<>]{0,40}>\s*$")


def _clean(v):
    """모델이 프롬프트의 자리표시자(<한국어 답변> 등)를 베껴 붙인 경우 떼어낸다."""
    t = str(v or "").strip()
    for _ in range(3):                       # 앞뒤로 여러 개 붙는 경우까지
        t2 = _PLACE_HOLDER.sub("", t).strip()
        if t2 == t:
            break
        t = t2
    return t


def parse_question(text):
    d = _extract_json(text)
    if isinstance(d, dict) and d.get("answer"):
        return {"answer": _clean(d.get("answer"))}
    return {"answer": _clean(text)}
