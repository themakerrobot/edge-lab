# -*- coding: utf-8 -*-
# vapi-od : VLM prompt templates + output parsers
# 장소·시간·날씨·태그·질문(사진)과 사진 없는 대화를 VLM 하나로 처리한다.
#
# lang 파라미터 (기본 "ko")
#   - 답은 요청한 언어 하나만 만든다. 한/영을 함께 만들던 예전 방식은 없앴다
#     (출력 토큰이 두 배라 느리고, 화면에도 같은 말이 두 번 나왔다).
#   - 장소/시간/날씨는 정해진 낱말 중에서만 고르게 한다 — 아이가 사진만 보고
#     맞았는지 틀렸는지 스스로 판단할 수 있어야 수업이 된다.
import json, re

MAX_TOKENS = {
    "place": 12, "time": 8, "weather": 8,
    "question": 80, "tag": 56, "free": 128, "chat": 256,
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


# ---------------------------------------------------------------- 선택지
# (한국어, 영어, 별칭...) — 별칭은 모델이 다른 말로 답했을 때 끌어오기 위한 것
PLACE = [
    ("교실", "classroom", "school", "lecture room"),
    ("도서관", "library", "book"),
    ("식당", "restaurant", "cafeteria", "dining", "cafe", "diner"),
    ("부엌", "kitchen", "주방"),
    ("거실", "living-room", "living room", "livingroom", "lounge"),
    ("침실", "bedroom", "방", "room"),
    ("사무실", "office", "연구실", "실험실", "laboratory", "lab", "desk", "study"),
    ("운동장", "playground", "gym", "체육관", "sports field", "stadium", "court"),
    ("공원", "park", "garden", "정원"),
    ("길거리", "street", "road", "sidewalk", "거리", "도로"),
    ("가게", "shop", "store", "market", "상점", "마트"),
    ("자연", "nature", "mountain", "beach", "sea", "forest", "field", "산", "바다", "숲"),
    ("기타", "other", "unknown"),
]

TIME = [
    ("아침", "morning", "dawn", "새벽"),
    ("낮", "afternoon", "daytime", "noon", "day", "오후"),
    ("저녁", "evening", "sunset", "dusk"),
    ("밤", "night", "midnight", "새벽녘"),
]

WEATHER = [
    ("맑음", "sunny", "clear", "맑은", "화창"),
    ("흐림", "cloudy", "overcast", "흐린", "구름"),
    ("비", "rainy", "rain", "비오는"),
    ("눈", "snowy", "snow", "눈오는"),
    ("바람", "windy", "wind", "바람부는"),
    ("실내", "indoor", "indoors", "inside", "안"),
]


def choices(table, lang):
    """프롬프트에 넣을 낱말 목록 (기타/unknown 은 빼고 보여준다).
    모델에게는 하이픈을 뺀 자연스러운 낱말로 보여 준다."""
    i = 0 if _lang(lang) == "ko" else 1
    return [row[i].replace("-", " ") for row in table if row[0] != "기타"]


def _pick(text, table, lang, key, fallback_index=-1):
    """모델 출력에서 표의 한 줄을 찾아 {key: 요청 언어, key_en: 영어} 로 돌려준다.

    영어 값은 표에서 꺼내는 것이라 공짜다. 화면 언어를 바꿔도 안 변하므로
    블록·파이썬에서 값을 비교할 때는 _en 쪽을 쓴다."""
    i = 0 if _lang(lang) == "ko" else 1
    t = (text or "").strip().lower()
    row = table[fallback_index]
    if t:
        # 긴 낱말부터 확인 — '맑음'이 '맑'보다, 'living room'이 'room'보다 먼저
        cand = []
        for r in table:
            for word in r:
                cand.append((len(word), word.lower(), r))
        for _, word, r in sorted(cand, key=lambda x: -x[0]):
            if word in t:
                row = r
                break
    return {key: row[i], key + "_en": row[1]}


# ---------------------------------------------------------------- 프롬프트
_PLACE = {
    "ko": "이 사진 속 장소를 다음 중 하나의 낱말로만 답하세요: {c}",
    "en": "Answer with exactly one of these words for the place in this photo: {c}",
}

_TIME = {
    "ko": "이 사진을 찍은 시간대를 다음 중 하나의 낱말로만 답하세요: {c}",
    "en": "Answer with exactly one of these words for the time of day in this photo: {c}",
}

_WEATHER = {
    "ko": ("이 사진의 날씨를 다음 중 하나의 낱말로만 답하세요: {c}\n"
           "바깥이 보이지 않으면 '실내'라고 답하세요."),
    "en": ("Answer with exactly one of these words for the weather in this photo: {c}\n"
           "If the outdoors is not visible, answer 'indoor'."),
}

_QUESTION = {
    "ko": ("사진을 보고 질문에 한국어로 짧게 답하세요. 한국어로만 쓰고, "
           "발음 표기나 영어 번역은 넣지 마세요.\n"
           '반드시 이 JSON 으로만 답하세요. {"answer": "<짧은 답>"}\n'
           "질문: {q}"),
    "en": ("Look at the photo and answer briefly in English.\n"
           'Answer only in this JSON. {"answer": "<short answer>"}\n'
           "Question: {q}"),
}

_TAG = {
    "ko": ("이 사진의 핵심 낱말을 5개까지 한국어로 뽑으세요. 낱말만 콤마로 잇고 "
           "설명은 넣지 마세요.\n"
           '반드시 이 JSON 으로만 답하세요. {"tag": "낱말, 낱말, 낱말"}'),
    "en": ("List up to 5 key words for this photo in English, comma separated, no explanation.\n"
           'Answer only in this JSON. {"tag": "word, word, word"}'),
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


def p_place(lang="ko"):
    return _PLACE[_lang(lang)].replace("{c}", ", ".join(choices(PLACE, lang)))


def p_time(lang="ko"):
    return _TIME[_lang(lang)].replace("{c}", ", ".join(choices(TIME, lang)))


def p_weather(lang="ko"):
    return _WEATHER[_lang(lang)].replace("{c}", ", ".join(choices(WEATHER, lang)))


def p_question(q, lang="ko"):
    return _QUESTION[_lang(lang)].replace("{q}", q or "")


def p_tag(lang="ko"):
    return _TAG[_lang(lang)]


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


def p_chat(q, lang="ko"):
    """사진 없이 묻는 말 — 같은 VLM 에게 글만 준다."""
    return _CHAT[_lang(lang)].replace("{q}", q or "")


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


def parse_place(text, lang="ko"):
    """정해진 장소 낱말 하나로 정리한다. 못 고르면 기타/other."""
    return _pick(text, PLACE, lang, "place")


def parse_time(text, lang="ko"):
    """모르겠으면 낮/afternoon 으로 둔다 — 사진에서 가장 흔한 답이다."""
    return _pick(text, TIME, lang, "time", fallback_index=1)


def parse_weather(text, lang="ko"):
    """바깥이 안 보이면 실내/indoor."""
    return _pick(text, WEATHER, lang, "weather", fallback_index=5)


def parse_question(text):
    d = _extract_json(text)
    if isinstance(d, dict) and d.get("answer"):
        return {"answer": _clean(d.get("answer"))}
    return {"answer": _clean(text)}


def parse_tag(text):
    d = _extract_json(text)
    if isinstance(d, dict):
        tag = d.get("tag", "")
        if isinstance(tag, list):
            tag = ", ".join(map(str, tag))
        return {"tag": _clean(tag)}
    return {"tag": _clean(text)}
