#!/usr/bin/env bash
# =============================================================================
# vapi-ondevice setup - Ubuntu - always full install, no skip
# Usage: put mask-11s-cls.pt in models/org/ then:  bash setup.sh
# Existing outputs are overwritten.
# =============================================================================
set -e
BASE="$(cd "$(dirname "$0")/.." && pwd)"   # 프로젝트 루트 (이 스크립트는 tools/ 안에 있다)
cd "$BASE"
MODELS="$BASE/models"
mkdir -p "$MODELS"/{org,vlm,object,face,gan,code}

echo "=== [1/9] packages ==="
sudo apt-get update -qq && sudo apt-get install -y -qq wget
pip install -r requirements.txt        # 실행에 필요한 것 (루트의 목록)
pip install "optimum[openvino]" nncf torchvision
pip install mediapipe

echo "=== [2/9] VLM ==="
echo "  VLM 은 따로 변환합니다 (README 참고)"

echo "=== [3/9] YOLO standard x3 export (auto-downloaded by ultralytics) ==="
cd "$MODELS/object"
python - <<'PY'
import shutil
from pathlib import Path
from ultralytics import YOLO

# 이 셋은 HF 에 두지 않는다 — ultralytics 가 GitHub 에서 받아온다(인터넷 필요).
for name in ["yolo11m.pt", "yolo11m-pose.pt", "yolo11m-seg.pt"]:
    out = Path(name.replace(".pt", "_openvino_model"))
    if out.exists():
        shutil.rmtree(out)
    YOLO(name).export(format="openvino", half=True)
    print("OK  ", out)
PY

echo "=== [4/9] mask classifier export (models/org -> models/object) ==="
cd "$MODELS"
python - <<'PY'
import shutil, sys
from pathlib import Path
from ultralytics import YOLO

ORG, OBJ = Path("org"), Path("object")
EXPECTED = ["mask-11s-cls.pt"]
# mask-11s-cls: 224 classifier, input = face crop

missing, failed = [], []
for name in EXPECTED:
    src = ORG / name
    if not src.exists():
        missing.append(name); print("MISSING:", name); continue
    out = OBJ / name.replace(".pt", "_openvino_model")
    if out.exists():
        shutil.rmtree(out)
    try:
        imgsz = 224 if "cls" in name else 640
        YOLO(str(src)).export(format="openvino", half=True, imgsz=imgsz)
        shutil.move(str(src.with_name(out.name)), str(out))
        print("OK  ", out)
    except Exception as e:
        failed.append(name); print("FAIL", name, e)

if missing or failed:
    print("keeping models/org (missing=%s failed=%s)" % (missing, failed))
    sys.exit(1)

shutil.rmtree(ORG)  # 원본은 HF org/ 에 있다
print("mask classifier done, models/org removed")
PY
cd "$BASE"

echo "=== [5/9] face suite + SR + transform models ==="
OMZ="https://storage.openvinotoolkit.org/repositories/open_model_zoo/2023.0/models_bin/1"
dl_omz () {
  for ext in xml bin; do
    wget -q --show-progress -O "$2/$1.$ext" "$OMZ/$1/FP16/$1.$ext"
  done
}
dl_omz face-detection-retail-0005         "$MODELS/face"
dl_omz age-gender-recognition-retail-0013 "$MODELS/face"
dl_omz emotions-recognition-retail-0003   "$MODELS/face"
dl_omz head-pose-estimation-adas-0001     "$MODELS/face"
dl_omz single-image-super-resolution-1032 "$MODELS/gan"

# AnimeGANv3 는 비상업 라이선스라 제외했다 (배경제거 U2Net · 화질개선 SR 만 사용)
wget -q --show-progress -O "$MODELS/gan/u2net.onnx" \
  "https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2net.onnx"

# 깊이 지도 — Depth Anything V2 Small (Apache-2.0)
# 미리 변환해 HF(leeyunjai/vapi-od)에 올려둔 IR을 그대로 받는다 (변환은 tools/convert_depth.py)
hf download leeyunjai/vapi-od --include "gan/depth-v2s/*" --local-dir "$MODELS"

echo "=== [6/9] local fonts ==="
python tools/fonts_download.py

echo "=== [7/9] mediapipe models ==="
mkdir -p models/mediapipe
wget -q -O models/mediapipe/face_landmarker.task "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task"
wget -q -O models/mediapipe/gesture_recognizer.task "https://storage.googleapis.com/mediapipe-models/gesture_recognizer/gesture_recognizer/float16/latest/gesture_recognizer.task"

echo "=== [8/9] speech models (STT / TTS) ==="
hf download OpenVINO/whisper-small-int8-ov --local-dir "$MODELS/stt"
hf download Supertone/supertonic-3 --local-dir "$MODELS/tts"

echo "=== [9/9] easyocr + offline check ==="
python - <<'PY'
import easyocr
easyocr.Reader(['ko', 'en'], gpu=False,
               model_storage_directory='models/code/easyocr',
               user_network_directory='models/code/easyocr')
print("easyocr OK -> models/code/easyocr")
PY

python - <<'PY'
from pathlib import Path
import openvino as ov
import openvino_tokenizers
core = ov.Core()
print("devices:", core.available_devices)
models = Path("models")
fails = 0
for name in ["duration_predictor.onnx", "text_encoder.onnx",
             "vector_estimator.onnx", "vocoder.onnx",
             "tts.json", "unicode_indexer.json"]:
    if not (models / "tts/onnx" / name).exists():
        fails += 1; print("FAIL models/tts/onnx/" + name, "| missing")
for m in list(models.rglob("*.xml")) + list(models.glob("gan/*.onnx")):
    try:
        core.read_model(m); print("OK ", m)
    except Exception as e:
        fails += 1; print("FAIL", m, e)
raise SystemExit(1 if fails else 0)
PY

echo ""
echo "DONE. offline run:  export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 YOLO_OFFLINE=1"
echo ""
echo "HF 에 올리려면:  hf upload leeyunjai/vapi-od models ."
echo "  (models/org/mask-11s-cls.pt 도 함께 올려 두면 이 저장소만으로 전부 다시 만들 수 있다)"
