# -*- coding: utf-8 -*-
"""themaker 를 살아 있는 서버에 물려 실제로 돌려 본다 (학생이 쓰는 그대로)."""
import os

import cv2
import numpy as np


def run(host):
    os.environ["THEMAKER_SERVER"] = host
    import themaker as T

    img = np.full((480, 640, 3), 210, np.uint8)
    cv2.rectangle(img, (200, 150), (320, 300), (60, 120, 200), -1)

    state = {"ok": 0, "fail": 0}

    def case(name, fn, check):
        try:
            r = fn()
            assert check(r), "결과가 예상과 다름: %r" % (r,)
            print("  PASS  %-24s %s" % (name, str(r)[:60].replace("\n", " ")))
            state["ok"] += 1
        except Exception as ex:
            print("  FAIL  %-24s %s" % (name, ex))
            state["fail"] += 1

    # 기능 이름 (영문·한글 별칭)
    case("vision('object')", lambda: T.vision("object", img),
         lambda r: r["object"][0]["name"] == "사람" and r["object"][0]["name_en"] == "person")
    case("vision('사물')", lambda: T.vision("사물", img), lambda r: "object" in r)
    case("vision('place')", lambda: T.vision("place", img),
         lambda r: r["place"] == "거실" and r["place_en"] == "living-room")
    case("vision('장소')", lambda: T.vision("장소", img), lambda r: "place" in r)
    case("vision('time')", lambda: T.vision("time", img), lambda r: r["time"] == "저녁")
    case("vision('weather')", lambda: T.vision("weather", img),
         lambda r: r["weather"] == "실내")
    case("vision('look') 설명", lambda: T.vision("look", img), lambda r: "answer" in r)
    case("vision('look') 질문", lambda: T.vision("look", img, prompt="몇 명이야?"),
         lambda r: "몇 명이야?" in r["answer"])          # 프롬프트가 서버까지 가는지
    case("vision('tag')", lambda: T.vision("tag", img), lambda r: "tag" in r)
    case("vision('face_attr')", lambda: T.vision("face_attr", img),
         lambda r: r[0]["gender"] == "남성" and r[0]["pos"]["direction"] == "왼쪽 위")
    case("vision('face')", lambda: T.vision("face", img), lambda r: r[0]["name"] == "얼굴")
    case("vision('ocr')", lambda: T.vision("ocr", img), lambda r: r[0]["text"] == "안녕")
    case("vision('qr')", lambda: T.vision("qr", img),
         lambda r: r[0]["data"].startswith("http"))
    case("vision('rps')", lambda: T.vision("rps", img),
         lambda r: r["object"][0]["name"] == "바위")     # detect_mode 가 가는지
    case("vision('bg_remove')", lambda: T.vision("bg_remove", img),
         lambda r: isinstance(r, np.ndarray))
    case("vision('seg') 그림+이름", lambda: T.vision("seg", img),
         lambda r: isinstance(r["image"], np.ndarray) and r["object"][0]["name"] == "의자")

    case("chat() 사진 없이", lambda: T.chat("삼국지가 뭐야?"),
         lambda r: isinstance(r, str) and len(r) > 0)

    def _db():
        T.db_add("시험자료", "무지개는 빛이 물방울에 꺾여서 생긴다.\n\n달은 지구를 도는 위성이다.")
        found = T.db_find("무지개는 왜 생겨?", "시험자료", 1)
        answer = T.chat("무지개는 왜 생겨?", db="시험자료")
        titles = [k["title"] for k in T.db_list()]
        gone = [T.db_delete(k["slug"])["deleted"]        # db_delete 도 함께 확인
                for k in T.db_list() if k["title"] == "시험자료"]
        return ("무지개" in found[0]["text"], bool(answer),
                "시험자료" in titles, all(gone) and bool(gone))
    case("db_add/find/chat/delete", _db, lambda r: all(r))

    # 언어
    case("language('en')", lambda: (T.language("en"), T.vision("object", img))[1],
         lambda r: r["object"][0]["name"] == "person")
    case("language('ko')", lambda: (T.language("ko"), T.vision("object", img))[1],
         lambda r: r["object"][0]["name"] == "사람")
    case("lang= 한 번만", lambda: T.vision("object", img, lang="en"),
         lambda r: r["object"][0]["name"] == "person")

    # 그리기 (한글 라벨이 실제로 찍히는지 = 픽셀이 바뀌는지)
    def _draw():
        out = T.draw(img, T.vision("object", img))
        return int(np.abs(out.astype(int) - img.astype(int)).sum())
    case("draw() 한글 라벨", _draw, lambda n: n > 10000)

    def _draw_seg():
        r = T.vision("seg", img)
        out = T.draw(r["image"], r["object"])
        return int(np.abs(out.astype(int) - r["image"].astype(int)).sum())
    case("draw() 분할 결과", _draw_seg, lambda n: n > 1000)

    # 오류 안내
    def _unknown():
        try:
            T.vision("없는기능", img)
        except T.TheMakerError as ex:
            return str(ex)
    case("모르는 기능 안내", _unknown, lambda s: "모르는 기능" in s)

    def _404():
        old = T._API["object"]
        T._API["object"] = ("/object/no_such_route", {})
        try:
            T.vision("object", img)
        except T.TheMakerError as ex:
            return str(ex)
        finally:
            T._API["object"] = old
    case("404 안내 문구", _404, lambda s: "서버에 없어요" in s)

    # 이미지 편집 (예제가 쓰는 것들)
    case("resize/rotate/flip", lambda: T.flip(T.rotate(T.resize(img, 0.5), 90), "h"),
         lambda r: isinstance(r, np.ndarray))
    case("draw_text 한글", lambda: T.draw_text(img, "안녕하세요", "tc", 30, "red"),
         lambda r: int(np.abs(r.astype(int) - img.astype(int)).sum()) > 1000)
    case("attach/put_on", lambda: T.put_on(T.attach(img, img, "h"), img, "mc"),
         lambda r: isinstance(r, np.ndarray))
    case("size_of/main_color",
         lambda: (T.size_of(img, "w"), T.size_of(img, "h"), T.main_color(img)),
         lambda r: r[0] == 640 and r[1] == 480 and isinstance(r[2], str))

    return state["ok"], state["fail"]
