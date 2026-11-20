# -*- coding: utf-8 -*-
"""학생 파이썬 코드 실행기 — 파이썬 화면(code_routes)이 학생 파일을 이것으로 돌린다.

    python pyrunner.py run_xxxx.py

하는 일은 그대로 실행하는 것뿐이고, 멈췄을 때만 다르다.
Traceback 을 출력에 쏟는 대신 무슨 오류인지를 파일 옆 run_xxxx.err.json 에 남긴다
  {"type": "NameError", "msg": "...", "line": 3, "text": "prnt(1)", "tm": null, "raw": "Traceback ..."}
  type  예외 종류          tm   themaker 가 낸 오류면 그 코드(TM-CAM 등 — themaker.TheMakerError.code)
  line  학생 코드의 몇 번째 줄 (라이브러리 안에서 났으면 그것을 부른 학생 코드의 줄)
  raw   원래 Traceback (이 실행기 · runpy 줄은 뺀다)
화면은 이것으로 오류 코드 · 쉬운 설명 · 줄 번호를 보여 준다 (view_project/lib/errcodes.js).
"""
import json
import os
import runpy
import sys
import traceback


def _same(a, b):
    try:
        return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))
    except Exception:
        return False


def _report(path, ex):
    info = {"type": type(ex).__name__, "msg": str(ex), "line": None, "text": "", "tm": None, "raw": ""}
    code = getattr(ex, "code", None)
    if type(ex).__name__ == "TheMakerError" and isinstance(code, str):
        info["tm"] = code
    if isinstance(ex, SyntaxError) and _same(ex.filename or "", path):
        info["line"] = ex.lineno
        info["text"] = (ex.text or "").rstrip("\n")
        info["msg"] = ex.msg
    frames = traceback.extract_tb(ex.__traceback__)
    mine = [f for f in frames if _same(f.filename, path)]
    if info["line"] is None and mine:
        info["line"] = mine[-1].lineno
        info["text"] = (mine[-1].line or "").strip()
    # 원래 Traceback — 실행기 · runpy 줄은 학생이 쓴 것이 아니라 뺀다
    keep = [f for f in frames if not (_same(f.filename, __file__) or f.filename.endswith(("runpy.py", "<frozen runpy>")))]
    raw = "Traceback (most recent call last):\n" if keep else ""
    raw += "".join(traceback.format_list(keep))
    raw += "".join(traceback.format_exception_only(type(ex), ex))
    raw = raw.replace(os.path.abspath(path), "내 코드" if os.environ.get("THEMAKER_LANG") != "en" else "my code")
    info["raw"] = raw.replace(os.path.dirname(os.path.abspath(__file__)) + os.sep, "")   # themaker.py 처럼 짧게
    try:
        with open(os.path.splitext(path)[0] + ".err.json", "w", encoding="utf-8") as f:
            json.dump(info, f, ensure_ascii=False)
    except OSError:
        sys.stderr.write(info["raw"])          # 남기지 못하면 예전처럼 출력에라도


def main():
    if len(sys.argv) < 2:
        sys.stderr.write("usage: python pyrunner.py <file.py>\n")
        return 2
    path = os.path.abspath(sys.argv[1])
    sys.argv = [path] + sys.argv[2:]
    sys.path[0] = os.path.dirname(path)        # 학생 파일을 직접 돌릴 때와 같은 import 경로
    try:
        runpy.run_path(path, run_name="__main__")
    except SystemExit:
        raise
    except KeyboardInterrupt:                  # [정지] — 오류가 아니다
        return 130
    except BaseException as ex:                # noqa: BLE001 — 무슨 오류든 남긴다
        try:
            sys.stdout.flush()
        except Exception:
            pass
        _report(path, ex)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
