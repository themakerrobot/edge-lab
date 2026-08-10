# -*- coding: utf-8 -*-
"""The Maker 실행기 — themaker.exe 로 빌드되어 같은 폴더의 run.bat 을 실행한다."""
import os
import subprocess
import sys
import time


def base_dir():
    if getattr(sys, "frozen", False):                 # exe로 실행 중
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def main():
    base = base_dir()
    run = os.path.join(base, "run.bat")
    if not os.path.exists(run):
        print("[오류] run.bat 을 찾을 수 없습니다.")
        print("themaker.exe 를 프로젝트 폴더(run.bat 옆)에 두고 실행하세요.")
        print("현재 위치:", base)
        input("\n엔터를 누르면 닫힙니다. ")
        return 1
    return subprocess.call(["cmd", "/c", run], cwd=base)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
