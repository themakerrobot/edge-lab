# -*- coding: utf-8 -*-
# vapi-od : VLM prompt templates + output parsers
# 모든 caption/* 계열과 face_attribute, object_cls_e 를 VLM 하나로 처리한다.
import json, re

MAX_TOKENS = {
    "caption": 128, "place": 48, "time": 16, "weather": 16,
    "question": 160, "tag": 96, "attr": 64, "cls": 96, "free": 256,
}

P_CAPTION = (
    "이 사진을 설명하세요. 반드시 아래 JSON 형식으로만 답하세요.\n"
    '{"caption": "<한국어 한 문장>", "caption_en": "<English one sentence>"}'
)

P_PLACE = (
    "이 사진의 장소를 판단하세요. environment는 '실내' 또는 '실외' 중 하나, "
    "category는 장소 종류(예: 교실, 공원, 주방)를 한국어 한 단어로. "
    '반드시 JSON으로만 답하세요. {"environment": "...", "category": "..."}'
)

P_TIME = (
    "이 사진이 찍힌 시간대를 다음 중 하나의 단어로만 답하세요: "
    "morning, afternoon, evening, night, unknown"
)
TIME_CHOICES = ["morning", "afternoon", "evening", "night", "unknown"]

P_WEATHER = (
    "이 사진의 날씨를 다음 중 하나의 단어로만 답하세요: "
    "sunny, cloudy, rainy, snow, unknown"
)
WEATHER_CHOICES = ["sunny", "cloudy", "rainy", "snow", "unknown"]

P_QUESTION = (
    "사진을 보고 질문에 답하세요. 반드시 아래 JSON 형식으로만 답하세요.\n"
    '{"answer": "<한국어 답변>", "answer_en": "<English answer>"}\n'
    "질문: {q}"
)

P_TAG = (
    "이 사진의 핵심 사물/개념 태그를 5~10개 뽑으세요. "
    '반드시 JSON으로만 답하세요. {"tag": "<한국어 태그 콤마 구분>", "tag_en": "<english tags comma separated>"}'
)

P_ATTR = (
    "이 얼굴 사진에서 각 항목의 여부를 0~100 정수 확신도로 답하세요. "
    "반드시 JSON으로만 답하세요.\n"
    '{"Eyeglasses": 0, "Mustache": 0, "Beard": 0, "Hat": 0}'
)
ATTR_KEYS = ["Eyeglasses", "Mustache", "Beard", "Hat"]

P_CLS = (
    "이 이미지의 주제를 가장 잘 나타내는 카테고리 3개를 확신도 순으로 답하세요. "
    "반드시 JSON 배열로만 답하세요.\n"
    '[{"name": "<english>", "ko_name": "<한국어>", "score": <0-100>}, ...]'
)


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
        return {"caption": str(d.get("caption", "")),
                "caption_en": str(d.get("caption_en", "")),
                "raw": [str(d.get("caption_en", ""))]}
    t = (text or "").strip()
    return {"caption": t, "caption_en": t, "raw": [t]}


def parse_place(text):
    d = _extract_json(text)
    if isinstance(d, dict):
        env = str(d.get("environment", "")).strip()
        env = "실내" if "실내" in env or "indoor" in env.lower() else \
              ("실외" if "실외" in env or "outdoor" in env.lower() else "unknown")
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
        return {"answer": str(d.get("answer", "")),
                "answer_en": str(d.get("answer_en", "")),
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
        return {"tag": str(tag), "tag_en": str(tag_en)}
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
