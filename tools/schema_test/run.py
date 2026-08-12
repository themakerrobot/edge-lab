# -*- coding: utf-8 -*-
"""모델 없이 응답 스키마를 검증한다 (몇 초면 끝난다).

    python tools\\schema_test\\run.py

가짜 엔진을 물려 서버를 띄우고, 모든 엔드포인트와 themaker 를 실제로 호출한다.
모델·웹캠·스피커가 필요 없으므로 스키마를 건드린 뒤 회귀 확인용으로 쓴다.
확인하지 못하는 것: 실제 인식 정확도, 블록 페이지 실행, 소리·마이크.

포트는 57799 를 쓴다 — 진짜 서버(57711)가 켜져 있어도 상관없다.
"""
import os
import sys
import threading
import time
import types
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
PORT = int(os.environ.get("SCHEMA_TEST_PORT", "57799"))
HOST = "http://127.0.0.1:%d" % PORT

sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)
os.chdir(ROOT)                                   # view_project/ 를 찾을 수 있게
os.environ["VAPI_NO_BROWSER"] = "1"


def boot():
    import fake_engines
    sys.modules["engines"] = fake_engines         # main 이 import engines 하면 이것을 받는다

    # 무거운 라우터는 시험 범위 밖이면 빈 것으로 대신한다 (없어도 나머지는 다 돈다)
    for name in ("train_routes", "speech_routes"):
        try:
            __import__(name)
        except Exception as ex:
            print("[skip] %s: %s" % (name, ex))
            from fastapi import APIRouter
            mod = types.ModuleType(name)
            mod.router = APIRouter()
            sys.modules[name] = mod

    import main
    main.eng = fake_engines.Engines()
    main.build_device_map()
    main.READY.update({"ready": True, "loaded": 3, "total": 3})

    import uvicorn
    cfg = uvicorn.Config(main.app, host="127.0.0.1", port=PORT, log_level="error")
    threading.Thread(target=uvicorn.Server(cfg).run, daemon=True).start()

    for _ in range(60):                           # 뜰 때까지 기다린다
        try:
            with urllib.request.urlopen(HOST + "/ready", timeout=1):
                return
        except Exception:
            time.sleep(0.25)
    raise RuntimeError("시험 서버가 뜨지 않았습니다")


def main_():
    print("가짜 엔진으로 서버를 띄웁니다 ... (%s)" % HOST)
    boot()

    import check_api
    import check_asmain
    import check_themaker

    print("\n[1] 엔드포인트 응답")
    a_ok, a_fail = check_api.run(HOST)
    print("\n[2] themaker 라이브러리")
    t_ok, t_fail = check_themaker.run(HOST)
    print("\n[3] python main.py 로 띄운 상태 (__main__)")
    m_ok, m_fail = check_asmain.run()

    ok, fail = a_ok + t_ok + m_ok, a_fail + t_fail + m_fail
    print("\n" + "=" * 46)
    print("  엔드포인트  %2d PASS / %d FAIL" % (a_ok, a_fail))
    print("  themaker   %2d PASS / %d FAIL" % (t_ok, t_fail))
    print("  직접 기동   %2d PASS / %d FAIL" % (m_ok, m_fail))
    print("  합계       %2d PASS / %d FAIL" % (ok, fail))
    print("=" * 46)
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main_())
