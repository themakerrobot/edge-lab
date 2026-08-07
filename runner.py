# -*- coding: utf-8 -*-
"""runner — 배포한 파이썬 작품 실행기 (themaker-run.exe 로 빌드된다).

같은 폴더의 code.py 를 The Maker 의 파이썬으로 실행한다.
The Maker 가 설치된 PC 에서만 동작한다 (AI 서버와 라이브러리를 함께 쓰기 때문).

찾는 순서:
  1) 환경변수 THEMAKER_HOME
  2) 이 파일이 들어 있는 폴더에 함께 있는 themaker_home.txt
  3) 흔한 설치 위치들
"""
import os
import subprocess
import sys

CANDIDATES = [
    r"C:\vapi-od",
    r"C:\The Maker",
    os.path.expanduser(r"~\vapi-od"),
    os.path.expanduser(r"~\Desktop\vapi-od"),
    os.path.expanduser(r"~\Documents\vapi-od"),
]


def base_dir():
    """exe 로 묶였을 때도 '파일이 놓인 폴더'를 얻는다."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def find_home():
    here = base_dir()
    env = os.environ.get("THEMAKER_HOME", "").strip()
    if env and os.path.isdir(env):
        return env
    memo = os.path.join(here, "themaker_home.txt")
    if os.path.exists(memo):
        with open(memo, encoding="utf-8") as f:
            p = f.read().strip()
        if p and os.path.isdir(p):
            return p
    for p in CANDIDATES:
        if os.path.isfile(os.path.join(p, "themaker.py")):
            return p
    return ""


def python_of(home):
    """The Maker 의 파이썬 — 설치본(venv) 또는 포터블 번들(python/)."""
    for rel in (r"venv\Scripts\python.exe", r"python\python.exe",
                "venv/bin/python", "python/bin/python"):
        p = os.path.join(home, rel)
        if os.path.exists(p):
            return p
    return sys.executable


def main():
    here = base_dir()
    code = os.path.join(here, "code.py")
    if not os.path.exists(code):
        print("code.py 를 찾을 수 없어요. 이 파일과 같은 폴더에 두세요.")
        input("엔터를 누르면 닫혀요...")
        return 1

    home = find_home()
    if not home:
        print("The Maker 가 설치된 폴더를 찾지 못했어요.")
        print("themaker_home.txt 에 설치 폴더 경로를 한 줄로 적어 주세요.")
        print("  예) C:\\Users\\내이름\\vapi-od")
        input("엔터를 누르면 닫혀요...")
        return 1

    env = dict(os.environ)
    env["PYTHONPATH"] = home + os.pathsep + env.get("PYTHONPATH", "")
    env["PYTHONIOENCODING"] = "utf-8"

    print("The Maker:", home)
    print("-" * 50)
    rc = subprocess.call([python_of(home), code], cwd=here, env=env)
    print("-" * 50)
    print("끝났어요. (코드 %d)" % rc)
    input("엔터를 누르면 닫혀요...")
    return rc


if __name__ == "__main__":
    sys.exit(main())
