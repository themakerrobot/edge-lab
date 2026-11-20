# -*- coding: utf-8 -*-
"""음성 인식(SenseVoice) 모델 받기 → models/stt-sv/

파이보 · 파이브레인과 같은 파일을 쓴다(허깅페이스 leeyunjai/themaker 의 .model/stt/).
  model.int8.onnx  SenseVoiceSmall int8 (sherpa-onnx 변환본)  — FunASR Model License 1.1
  tokens.txt       글자표
  silero_vad.onnx  말 구간 찾기(긴 녹음을 자를 때)              — MIT
FunASR 모델 라이선스는 '출처·저작자 표시와 모델 이름 유지' 를 요구한다 — 원문(tools/licenses)을 같은 폴더에 둔다.

쓰는 법:  venv\\Scripts\\python tools\\fetch_stt.py      (변환 setup.ps1 이 부르고, fetch_models.py 는 저장소에 stt-sv 가 없을 때만 부른다)
"""
import os
import shutil
import sys

from huggingface_hub import hf_hub_download

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DST = os.path.join(ROOT, "models", "stt-sv")
FILES = ("model.int8.onnx", "tokens.txt", "silero_vad.onnx")


def main():
    os.makedirs(DST, exist_ok=True)
    for name in FILES:
        src = hf_hub_download("leeyunjai/themaker", ".model/stt/" + name)
        shutil.copyfile(src, os.path.join(DST, name))
        print("  stt-sv/%s  %.1f MB" % (name, os.path.getsize(os.path.join(DST, name)) / 1e6))
    shutil.copyfile(os.path.join(ROOT, "tools", "licenses", "FunASR-MODEL_LICENSE.txt"),
                    os.path.join(DST, "LICENSE-SenseVoice.txt"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
