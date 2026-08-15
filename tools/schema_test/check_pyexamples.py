# -*- coding: utf-8 -*-
"""code.html 의 파이썬 예제를 진짜로 실행해 본다 (가짜 서버 상대).

왜 필요한가 — 예제를 눈으로만 훑으면 인자 "순서"가 바뀐 것을 못 잡는다.
자료와 질문 자리를 바꿔 쓴 예제가 회귀 99 PASS 를
통과한 채 실기에서 터졌다. 개수 대조로는 안 걸리므로 실행이 답이다.

카메라·마이크·소리가 필요한 줄은 가짜로 바꿔 끼운다(아래 STUB).
"""
import ast
import io
import os
import re
import sys
import traceback

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 사람이 손을 대야 도는 예제는 뺀다 — 이유를 함께 적는다
SKIP = {
    "wav_to_text": "wav 파일이 있어야 한다",
    "load": "사진 파일이 있어야 한다",
    "input": "사람이 입력해야 한다",
}


def _examples():
    """code.html 예제 모달의 코드만 뽑는다.

    도움말의 예시(x:)는 일부러 뺀다 — img 가 이미 있다고 가정한 조각글이라
    통째로 돌리면 NameError 만 잔뜩 난다. 여기서 보려는 것은 "완결된 예제가
    처음부터 끝까지 도는가" 다.
    """
    html = io.open(os.path.join(ROOT, "view_project/code.html"), encoding="utf-8").read()
    return [(m.group(1), m.group(2)) for m in re.finditer(
        r'\{ ko: \["([^"]+)",[^\]]*\],\s*\n\s*en: \[[^\]]*\],\s*\n\s*code: `(.*?)`', html, re.S)]


def _skip_reason(src):
    # 주석에 적어 둔 안내문에 걸리지 않게 주석을 걷어내고 본다
    live = "\n".join(re.sub(r"#.*$", "", ln) for ln in src.split("\n"))
    if re.search(r'vision\(\s*["\']my:', live) or "여기에-모델이름" in live:
        return "가르치기에서 학습한 모델이 있어야 한다"
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return None
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in SKIP:
            return SKIP[node.func.id]
    return None


def run(host):
    os.environ["THEMAKER_SERVER"] = host
    import themaker as T

    img = np.full((480, 640, 3), 210, np.uint8)

    # 사람 손이 필요한 것만 바꿔 끼운다 — 나머지는 진짜 함수를 그대로 쓴다
    T.camera = lambda *a, **k: img.copy()
    T.show = lambda *a, **k: None
    T.save = lambda *a, **k: "saved.jpg"
    T.sleep = lambda *a, **k: None
    # 소리·마이크는 조용히 넘긴다(예제를 통째로 건너뛰지 않기 위해)
    T.speak = lambda *a, **k: None
    T.beep = lambda *a, **k: None
    T.play_note = lambda *a, **k: None
    T.play_melody = lambda *a, **k: None
    T.play_hz = lambda *a, **k: None
    T.listen = lambda *a, **k: "안녕"
    # 목록만 보는 것은 빈 목록으로 — 전체 점검 예제가 이것 하나 때문에 통째로
    # 빠지면 그 안의 자료·인식 부분을 못 본다
    T.my_models = lambda *a, **k: []
    T.models = lambda *a, **k: []
    T.models_folder = lambda *a, **k: None        # 탐색기 창을 띄우지 않는다
    T.speaker = lambda *a, **k: []                # 출력 장치 목록은 기기마다 다르다

    def _no_model(*a, **k):
        raise AssertionError("이 예제는 가져다 둔 .pt 파일이 있어야 합니다")
    T.detect = _no_model

    ok = fail = skip = 0
    for name, src in _examples():
        why = _skip_reason(src)
        if why:
            skip += 1
            continue
        env = {k: getattr(T, k) for k in dir(T) if not k.startswith("_")}
        env["__name__"] = "__main__"
        try:
            exec(compile(src, "<%s>" % name, "exec"), env)
            print("  PASS  예제 실행  %s" % name[:40])
            ok += 1
        except AssertionError as ex:      # 준비물이 없어 못 도는 예제
            print("  [skip] %s — %s" % (name[:40], ex))
            skip += 1
        except Exception as ex:
            line = traceback.extract_tb(sys.exc_info()[2])[-1].lineno
            print("  FAIL  예제 실행  %s | %d번째 줄 %s: %s"
                  % (name[:40], line, type(ex).__name__, ex))
            fail += 1
    print("  (사람 손이 필요해 건너뛴 예제 %d개)" % skip)
    return ok, fail
