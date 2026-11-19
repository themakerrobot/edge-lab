# -*- coding: utf-8 -*-
"""제품 이름 — brand.json 하나에서 읽는다.

이름을 바꿀 때는 brand.json 만 고치고 `python tools/brand.py` 를 한 번 돌린다
(문서 · 노트북 · 화면용 lib/brand.js 를 맞춰 준다). 코드에 이름을 직접 쓰지 않는다 —
tools/release_check.py 가 잡는다.

  name            화면 · 영어 문장 속 이름 (타이틀바, 창 제목 앞, 콘솔)
  name_ko         한국어 문장 속 이름 ("~을 켜는 중이에요")
  tagline(_en)    부제 — 타이틀바 로고에 마우스를 올리면 보인다
  slug            파일 이름 (번들 zip · exe · ico)
  work_folder     작업 폴더 이름 (문서\\<이것>)
  appdata_folder  앱데이터 폴더 이름 (%LOCALAPPDATA%\\<이것>, 리눅스는 소문자)
  repo_github · repo_hf   저장소 주소 (설치 문서 · 모델 받기)
"""
import json
import os

_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "brand.json")
KEYS = ("name", "name_ko", "tagline", "tagline_en", "slug", "work_folder", "appdata_folder",
        "repo_github", "repo_hf")


def load(path=_PATH):
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    missing = [k for k in KEYS if not str(d.get(k, "")).strip()]
    if missing:
        raise ValueError("brand.json 에 빠진 값: " + ", ".join(missing))
    return {k: str(d[k]).strip() for k in KEYS}


B = load()
NAME, NAME_KO, SLUG = B["name"], B["name_ko"], B["slug"]
TAGLINE, TAGLINE_EN = B["tagline"], B["tagline_en"]
WORK_FOLDER, APPDATA_FOLDER = B["work_folder"], B["appdata_folder"]
REPO_GITHUB, REPO_HF = B["repo_github"], B["repo_hf"]


def _has_batchim(word):
    """마지막 글자에 받침이 있나. 한글이 아니면 영어 끝소리로 대강 본다(…lab → '랩' → 있음)."""
    w = word.rstrip()
    if not w:
        return False
    c = w[-1]
    if "가" <= c <= "힣":
        return (ord(c) - 0xAC00) % 28 != 0
    return c.lower() in "bklmnpt"          # 영어 끝소리가 받침처럼 들리는 것 (lab, AI 는 아님)


def ko(particle="을"):
    """한국어 이름 + 조사 — ko("을") → '… lab 을' / '… 실습실을'. 한글로 끝나면 붙여 쓴다."""
    pairs = {"을": ("을", "를"), "를": ("을", "를"), "은": ("은", "는"), "는": ("은", "는"),
             "이": ("이", "가"), "가": ("이", "가"), "과": ("과", "와"), "와": ("과", "와")}
    a, b = pairs.get(particle, (particle, particle))
    p = a if _has_batchim(NAME_KO) else b
    sep = "" if "가" <= NAME_KO[-1] <= "힣" else " "
    return NAME_KO + sep + p
