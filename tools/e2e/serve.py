import os, sys, types, threading
# 이 파일 위치에서 프로젝트 뿌리를 잡는다 — 절대경로를 박으면 다른 PC 에서 안 돈다
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tools", "schema_test"))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ["VAPI_NO_BROWSER"] = "1"

import fake_engines
sys.modules["engines"] = fake_engines
for name in ("train_routes", "speech_routes"):
    try:
        __import__(name)
    except Exception as ex:
        print("[skip]", name, ex)
        from fastapi import APIRouter
        mod = types.ModuleType(name); mod.router = APIRouter()
        sys.modules[name] = mod

import main
main.eng = fake_engines.Engines()
main.build_device_map()
main.READY.update({"ready": True, "loaded": 3, "total": 3})

import uvicorn
uvicorn.run(main.app, host="127.0.0.1", port=57900, log_level="error")
