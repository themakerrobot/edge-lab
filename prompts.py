# -*- coding: utf-8 -*-
# vapi-od : VLM prompt templates + output parsers
# 모든 caption/* 계열과 face_attribute, object_cls_e 를 VLM 하나로 처리한다.
#
# lang 파라미터 (기본 "ko")
#   - 응답 스키마는 그대로 유지한다. lang="en" 이면 주 필드(caption/answer/tag/category)에
#     영어가 들어간다. 기존 클라이언트는 lang 을 보내지 않으므로 동작이 바뀌지 않는다.
#   - time/weather/attr 은 원래 언어 중립(영문 코드값)이라 프롬프트만 영어로 바꾼다.
import json, re

MAX_TOKENS = {
    "caption": 64, "place": 32, "time": 12, "weather": 12,
    "question": 80, "tag": 56, "attr": 48, "cls": 64, "free": 128,
}

LANGS = ("ko", "en")


def _lang(lang):
    lang = (lang or "ko").strip().lower()[:2]
    return lang if lang in LANGS else "ko"


# ---------------------------------------------------------------- 프롬프트
_CAPTION = {
    "ko": ("이 사진을 한국어 한 문장으로 설명하세요. 한국어로만 쓰고, "
           "발음 표기나 영어 번역은 넣지 마세요.\n"
           '반드시 이 JSON 으로만 답하세요. {"caption": "<한 문장>"}'),
    "en": ("Describe this photo in one English sentence.\n"
           'Answer only in this JSON. {"caption": "<one sentence>"}'),
}

_PLACE = {
    "ko": ("이 사진의 장소를 판단하세요. environment는 '실내' 또는 '실외' 중 하나, "
           "category는 장소 종류(예: 교실, 공원, 주방)를 한국어 한 단어로. "
           '반드시 JSON으로만 답하세요. {"environment": "...", "category": "..."}'),
    "en": ("Decide where this photo was taken. environment must be either 'indoor' or 'outdoor'. "
           "category is the kind of place in one English word (e.g. classroom, park, kitchen). "
           'Answer only in JSON. {"environment": "...", "category": "..."}'),
}

_TIME = {
    "ko": ("이 사진이 찍힌 시간대를 다음 중 하나의 단어로만 답하세요: "
           "morning, afternoon, evening, night, unknown"),
    "en": ("Answer with exactly one of these words for the time of day in this photo: "
           "morning, afternoon, evening, night, unknown"),
}
TIME_CHOICES = ["morning", "afternoon", "evening", "night", "unknown"]

_WEATHER = {
    "ko": ("이 사진의 날씨를 다음 중 하나의 단어로만 답하세요: "
           "sunny, cloudy, rainy, snow, unknown"),
    "en": ("Answer with exactly one of these words for the weather in this photo: "
           "sunny, cloudy, rainy, snow, unknown"),
}
WEATHER_CHOICES = ["sunny", "cloudy", "rainy", "snow", "unknown"]

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

_ATTR = {
    "ko": ("이 얼굴 사진에서 각 항목의 여부를 0~100 정수 확신도로 답하세요. "
           "반드시 JSON으로만 답하세요.\n"
           '{"Eyeglasses": 0, "Mustache": 0, "Beard": 0, "Hat": 0}'),
    "en": ("For this face photo, give a 0-100 integer confidence for each item. "
           "Answer only in JSON.\n"
           '{"Eyeglasses": 0, "Mustache": 0, "Beard": 0, "Hat": 0}'),
}
ATTR_KEYS = ["Eyeglasses", "Mustache", "Beard", "Hat"]

_CLS = {
    "ko": ("이 이미지의 주제를 나타내는 낱말 3개를 확신도 순으로 답하세요. "
           "이름은 한국어 한 낱말로, 설명은 넣지 마세요.\n"
           '반드시 이 JSON 배열로만 답하세요. [{"name": "낱말", "score": 90}, ...]'),
    "en": ("Give 3 words describing this image, most confident first. "
           "One English word each, no explanation.\n"
           'Answer only as this JSON array. [{"name": "word", "score": 90}, ...]'),
}

_FREE = {
    "ko": "이 이미지를 설명하세요.",
    "en": "Describe this image.",
}

# 기존 코드 호환용 상수 (한국어 기본값)
P_CAPTION = _CAPTION["ko"]
P_PLACE = _PLACE["ko"]
P_TIME = _TIME["ko"]
P_WEATHER = _WEATHER["ko"]
P_QUESTION = _QUESTION["ko"]
P_TAG = _TAG["ko"]
P_ATTR = _ATTR["ko"]
P_CLS = _CLS["ko"]


def p_caption(lang="ko"):
    return _CAPTION[_lang(lang)]


def p_place(lang="ko"):
    return _PLACE[_lang(lang)]


def p_time(lang="ko"):
    return _TIME[_lang(lang)]


def p_weather(lang="ko"):
    return _WEATHER[_lang(lang)]


def p_question(q, lang="ko"):
    return _QUESTION[_lang(lang)].replace("{q}", q or "")


def p_tag(lang="ko"):
    return _TAG[_lang(lang)]


def p_attr(lang="ko"):
    return _ATTR[_lang(lang)]


def p_cls(lang="ko"):
    return _CLS[_lang(lang)]


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


def parse_caption(text):
    d = _extract_json(text)
    if isinstance(d, dict) and d.get("caption"):
        cap = _clean(d.get("caption"))
        cap_en = _clean(d.get("caption_en")) or cap
        return {"caption": cap, "caption_en": cap_en, "raw": [cap_en]}
    t = _clean(text)
    return {"caption": t, "caption_en": t, "raw": [t]}


def parse_place(text, lang="ko"):
    """environment 는 요청 언어에 맞춰 돌려준다 (실내/실외 또는 indoor/outdoor)."""
    lang = _lang(lang)
    inside = ("실내", "indoor") if lang == "ko" else ("indoor", "indoor")
    outside = ("실외", "outdoor") if lang == "ko" else ("outdoor", "outdoor")

    d = _extract_json(text)
    if isinstance(d, dict):
        raw = str(d.get("environment", "")).strip().lower()
        if "실내" in raw or "indoor" in raw:
            env = inside[0]
        elif "실외" in raw or "outdoor" in raw:
            env = outside[0]
        else:
            env = "unknown"
        return {"environment": env, "category": str(d.get("category", "unknown"))}
    return {"environment": "unknown", "category": "unknown"}


def parse_choice(text, choices):
    t = (text or "").strip().lower()
    for c in choices:
        if c in t:
            return c
    return "unknown"


def parse_question(text, prompt):
    d = _extract_json(text)
    if isinstance(d, dict) and d.get("answer"):
        ans = _clean(d.get("answer"))
        return {"answer": ans,
                "answer_en": _clean(d.get("answer_en")) or ans,
                "prompt_en": prompt}
    t = _clean(text)
    return {"answer": t, "answer_en": t, "prompt_en": prompt}


def parse_tag(text):
    d = _extract_json(text)
    if isinstance(d, dict):
        tag, tag_en = d.get("tag", ""), d.get("tag_en", "")
        if isinstance(tag, list):
            tag = ", ".join(map(str, tag))
        if isinstance(tag_en, list):
            tag_en = ", ".join(map(str, tag_en))
        tag, tag_en = _clean(tag), _clean(tag_en)
        return {"tag": tag, "tag_en": tag_en or tag}
    t = _clean(text)
    return {"tag": t, "tag_en": t}


def parse_attr(text):
    d = _extract_json(text)
    out = {}
    for k in ATTR_KEYS:
        try:
            out[k] = int(d.get(k, 0)) if isinstance(d, dict) else 0
        except Exception:
            out[k] = 0
        out[k] = max(0, min(100, out[k]))
    return out


def parse_cls(text):
    d = _extract_json(text)
    out = []
    if isinstance(d, list):
        for item in d[:3]:
            if isinstance(item, dict) and item.get("name"):
                try:
                    score = int(item.get("score", 0))
                except Exception:
                    score = 0
                name = str(item["name"])
                # 이제 한 언어만 만들게 하므로 ko_name 이 없을 수 있다 — 화면이
                # ko_name 을 먼저 보므로 비어 있으면 name 을 넣어 준다.
                out.append({"name": name,
                            "ko_name": str(item.get("ko_name", "")) or name,
                            "score": max(0, min(100, score))})
    if not out:
        one = (text or "unknown").strip()[:50]
        out = [{"name": one, "ko_name": one, "score": 0}]
    return out
