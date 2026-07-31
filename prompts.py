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
    "caption": 128, "place": 48, "time": 16, "weather": 16,
    "question": 160, "tag": 96, "attr": 64, "cls": 96, "free": 256,
}

LANGS = ("ko", "en")


def _lang(lang):
    lang = (lang or "ko").strip().lower()[:2]
    return lang if lang in LANGS else "ko"


# ---------------------------------------------------------------- 프롬프트
_CAPTION = {
    "ko": ("이 사진을 설명하세요. 반드시 아래 JSON 형식으로만 답하세요.\n"
           '{"caption": "<한국어 한 문장>", "caption_en": "<English one sentence>"}'),
    "en": ("Describe this photo. Answer only in the JSON format below.\n"
           '{"caption": "<one English sentence>", "caption_en": "<the same English sentence>"}'),
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
    "ko": ("사진을 보고 질문에 답하세요. 반드시 아래 JSON 형식으로만 답하세요.\n"
           '{"answer": "<한국어 답변>", "answer_en": "<English answer>"}\n'
           "질문: {q}"),
    "en": ("Look at the photo and answer the question. Answer only in the JSON format below.\n"
           '{"answer": "<English answer>", "answer_en": "<the same English answer>"}\n'
           "Question: {q}"),
}

_TAG = {
    "ko": ("이 사진의 핵심 사물/개념 태그를 5~10개 뽑으세요. 반드시 JSON으로만 답하세요. "
           '{"tag": "<한국어 태그 콤마 구분>", "tag_en": "<english tags comma separated>"}'),
    "en": ("List 5 to 10 key object or concept tags for this photo. Answer only in JSON. "
           '{"tag": "<english tags comma separated>", "tag_en": "<the same english tags>"}'),
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
    "ko": ("이 이미지의 주제를 가장 잘 나타내는 카테고리 3개를 확신도 순으로 답하세요. "
           "반드시 JSON 배열로만 답하세요.\n"
           '[{"name": "<english>", "ko_name": "<한국어>", "score": <0-100>}, ...]'),
    "en": ("Give the 3 categories that best describe this image, most confident first. "
           "Answer only as a JSON array.\n"
           '[{"name": "<english>", "ko_name": "<english, same as name>", "score": <0-100>}, ...]'),
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


def parse_caption(text):
    d = _extract_json(text)
    if isinstance(d, dict) and d.get("caption"):
        cap = str(d.get("caption", ""))
        cap_en = str(d.get("caption_en", "")) or cap
        return {"caption": cap, "caption_en": cap_en, "raw": [cap_en]}
    t = (text or "").strip()
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
        ans = str(d.get("answer", ""))
        return {"answer": ans,
                "answer_en": str(d.get("answer_en", "")) or ans,
                "prompt_en": prompt}
    t = (text or "").strip()
    return {"answer": t, "answer_en": t, "prompt_en": prompt}


def parse_tag(text):
    d = _extract_json(text)
    if isinstance(d, dict):
        tag, tag_en = d.get("tag", ""), d.get("tag_en", "")
        if isinstance(tag, list):
            tag = ", ".join(map(str, tag))
        if isinstance(tag_en, list):
            tag_en = ", ".join(map(str, tag_en))
        tag, tag_en = str(tag), str(tag_en)
        return {"tag": tag, "tag_en": tag_en or tag}
    t = (text or "").strip()
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
                out.append({"name": str(item["name"]),
                            "ko_name": str(item.get("ko_name", "")),
                            "score": max(0, min(100, score))})
    if not out:
        out = [{"name": (text or "unknown").strip()[:50], "ko_name": "", "score": 0}]
    return out
