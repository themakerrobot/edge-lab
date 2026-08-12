# -*- coding: utf-8 -*-
"""실행 중인 main 모듈을 찾아 준다.

왜 필요한가 — `python main.py` 로 띄우면 그 파일은 **__main__** 이라는 이름으로 올라간다.
이때 다른 모듈에서 `import main` 을 하면 파이썬은 "main" 이라는 **새 모듈**을 만들며
main.py 를 처음부터 다시 실행한다(라우터 등록·통계 설치가 두 벌이 되고, 그 사본의
eng 는 비어 있어서 "AI 준비가 끝나지 않았어요" 가 난다).

그래서 import 하지 않고, 이미 올라와 있는 모듈만 찾아 쓴다.
"""
import sys


def main_module():
    """이미 올라와 있는 main 모듈 (없으면 None)."""
    for name in ("main", "__main__"):
        m = sys.modules.get(name)
        if m is not None and hasattr(m, "app"):     # 진짜 서버 모듈인지 확인
            return m
    return None


def engines(required=True):
    """로딩이 끝난 엔진 모음. 아직이면 None 이거나(required=False) 오류."""
    m = main_module()
    eng = getattr(m, "eng", None) if m else None
    if eng is None and required:
        raise RuntimeError("AI 준비가 끝나지 않았어요. 잠시 뒤에 다시 해 보세요.")
    return eng


def device_of(key, default="CPU"):
    """그 기능이 어느 장치에서 도는지 (화면 표시용)."""
    m = main_module()
    table = getattr(m, "DEVICE_OF", None) if m else None
    try:
        return table.get(key, default) if table else default
    except Exception:
        return default
