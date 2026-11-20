# -*- coding: utf-8 -*-
"""모델 받기 — 설치(setup_deploy.ps1)와 배포판 자동 만들기(.github/workflows/bundle.yml)가 같이 쓴다.

    python tools/fetch_models.py

받는 것 (모두 공개 저장소 — 토큰 없이 받는다. HF_TOKEN 이 있으면 그걸로 받는다)
  1) brand.json 의 repo_hf (leeyunjai/edge-lab)  → models/        서버가 읽는 IR · 모델
  2) leeyunjai/themaker .model/stt               → models/stt-sv  음성 인식 SenseVoice int8 (tools/fetch_stt.py)
  3) leeyunjai/easydetect                         → models/easydetect  사물 찾기 · 자세 · 영역 (.onnx)

1) 에서 받지 않는 것 (IGNORE) — 교실 PC 는 서버가 읽는 IR 만 있으면 된다.
  models.7z · org/ (변환 전 원본) · yolo/ · object/ (예전 YOLO · 마스크, ultralytics AGPL — 지금은 easydetect · mask.onnx)
  tts/ (읽어 주기 원본 — tts-int8 을 쓴다) · stt/ (예전 Whisper — stt-sv 를 쓴다)
  release/ (배포판 zip — tools/upload_release.py 가 올린다. 설치할 때 받지 않는다)
  README.md (tts-int8/MODIFICATIONS.md 는 OpenRAIL-M 의 "바꾼 곳 알림" 이라 함께 받는다)

hf.exe CLI 대신 파이썬 API 를 쓴다 — PowerShell 을 거치며 --exclude 가 사라져 README.md 하나만 받은 적이 있다.
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import brand  # noqa: E402

IGNORE = ["models.7z", "org/*", "yolo/*", "tts/*", "stt/*", "object/*", "release/*", "README.md", "*/README.md"]
EASYDETECT = ["ed-m/ed-m.onnx", "ed-m/ed-m.names.json", "ed-m/labels.txt", "pose/pose-m.onnx", "mobile_sam/*"]


def main():
    from huggingface_hub import snapshot_download
    models = os.path.join(ROOT, "models")
    print("[1/3] %s → models/" % brand.REPO_HF, flush=True)
    snapshot_download(repo_id=brand.REPO_HF, local_dir=models, ignore_patterns=IGNORE)
    print("[2/3] 음성 인식 (SenseVoice) → models/stt-sv", flush=True)
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "fetch_stt.py")], cwd=ROOT)
    if r.returncode:
        print("음성 인식 모델을 받지 못했어요 (네트워크 확인)")
        return 1
    print("[3/3] leeyunjai/easydetect → models/easydetect", flush=True)
    snapshot_download(repo_id="leeyunjai/easydetect", local_dir=os.path.join(models, "easydetect"),
                      allow_patterns=EASYDETECT)
    print("모델 받기 끝", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
