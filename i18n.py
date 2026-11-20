# -*- coding: utf-8 -*-
"""서버 글의 말 — 요청마다 화면 언어(ko · en)를 기억해 두고, 오류 · 안내를 그 말로 돌려준다.

  화면(lib/embed.js)과 themaker 는 모든 요청에 X-Lang 헤더를 붙인다. main.py 의 미들웨어가
  ?lang= > X-Lang > 쿠키 vapiLang 순으로 읽어 set_lang 한다(없으면 ko).
  서버 코드는 글을 t("한글", "English") 로 쓴다 — 요청 밖(기동 중 모델 올리기 등)은 ko.
  파이보 · 파이브레인처럼 한/영을 나눠 보이기 위해서다.
"""
import contextvars

_lang = contextvars.ContextVar("vapi_lang", default="ko")


def norm(value):
    return "en" if str(value or "").strip().lower().startswith("en") else "ko"


def set_lang(value):
    return _lang.set(norm(value))


def reset(token):
    _lang.reset(token)


def lang():
    return _lang.get()


def t(ko, en):
    return en if _lang.get() == "en" else ko
