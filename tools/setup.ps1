# =============================================================================
# vapi-ondevice setup - Windows (PowerShell) - always full install, no skip
# Usage: put mask-11s-cls.pt in models\org\ then run:
#   powershell -ExecutionPolicy Bypass -File .\tools\setup.ps1
# Existing outputs are overwritten. ASCII-only for PowerShell 5.1 safety.
# =============================================================================
$ErrorActionPreference = "Stop"
$BASE   = Split-Path $PSScriptRoot -Parent   # 프로젝트 루트 (이 스크립트는 tools\ 안에 있다)
Set-Location $BASE
$MODELS = Join-Path $BASE "models"
foreach ($d in "org","vlm","object","face","gan","code","stt","tts") {
  New-Item -ItemType Directory -Force -Path (Join-Path $MODELS $d) | Out-Null
}

Write-Host "=== [1/9] python packages ===" -ForegroundColor Cyan
pip install -r requirements.txt        # 실행에 필요한 것 (루트의 목록)
pip install "optimum[openvino]" nncf torchvision
pip install mediapipe
pip install pyinstaller   # make_bundle.bat 의 런처 exe 빌드용 (개발 PC 전용)
$global:LASTEXITCODE = 0

Write-Host "=== [2/9] VLM ===" -ForegroundColor Cyan
# VLM 은 요구하는 transformers 버전이 달라 전용 가상환경에서 따로 변환한다.
# (자세한 절차는 README 의 "VLM 모델 바꾸기")
if (Get-ChildItem (Join-Path $MODELS "vlm") -Directory -ErrorAction SilentlyContinue) {
  Write-Host "  이미 있음 - 건너뜁니다" -ForegroundColor DarkGray
} else {
  Write-Host "  아직 없습니다. README 의 'VLM 모델 바꾸기' 를 보고 먼저 변환하세요." -ForegroundColor Yellow
}

Write-Host "=== [3/9] YOLO standard x3 export (auto-downloaded by ultralytics) ===" -ForegroundColor Cyan
Push-Location (Join-Path $MODELS "object")
@'
import shutil
from pathlib import Path
from ultralytics import YOLO

# 이 셋은 HF 에 두지 않는다 - ultralytics 가 GitHub 에서 받아온다(인터넷 필요).
for name in ["yolo11m.pt", "yolo11m-pose.pt", "yolo11m-seg.pt"]:
    out = Path(name.replace(".pt", "_openvino_model"))
    if out.exists():
        shutil.rmtree(out)  # overwrite: convert fresh every run
    YOLO(name).export(format="openvino", half=True)
    print("OK  ", out)
'@ | python -
if ($LASTEXITCODE -ne 0) { throw "step 3 failed" }
Pop-Location

Write-Host "=== [4/9] mask classifier export (models\org -> models\object) ===" -ForegroundColor Cyan
Push-Location $MODELS
@'
import shutil, sys
from pathlib import Path
from ultralytics import YOLO

ORG, OBJ = Path("org"), Path("object")
EXPECTED = ["mask-11s-cls.pt"]
# mask-11s-cls: classifier (224), input = face crop

missing, failed = [], []
for name in EXPECTED:
    src = ORG / name
    if not src.exists():
        missing.append(name); print("MISSING:", name); continue
    out = OBJ / name.replace(".pt", "_openvino_model")
    if out.exists():
        shutil.rmtree(out)  # overwrite: convert fresh every run
    try:
        imgsz = 224 if "cls" in name else 640
        YOLO(str(src)).export(format="openvino", half=True, imgsz=imgsz)
        shutil.move(str(src.with_name(out.name)), str(out))  # export lands next to pt
        print("OK  ", out)
    except Exception as e:
        failed.append(name); print("FAIL", name, e)

if missing or failed:
    print("keeping models/org (missing=%s failed=%s)" % (missing, failed))
    sys.exit(1)

shutil.rmtree(ORG)  # converted -> remove source pt folder (원본은 HF org/ 에 있다)
print("mask classifier done, models/org removed")
'@ | python -
if ($LASTEXITCODE -ne 0) { throw "step 4 failed" }
Pop-Location

Write-Host "=== [5/9] face suite + SR + transform models ===" -ForegroundColor Cyan
$OMZ = "https://storage.openvinotoolkit.org/repositories/open_model_zoo/2023.0/models_bin/1"
function Get-Omz([string]$name, [string]$dest) {
  foreach ($ext in "xml","bin") {
    Invoke-WebRequest -Uri "$OMZ/$name/FP16/$name.$ext" -OutFile (Join-Path $dest "$name.$ext")
  }
}
$faceDir = Join-Path $MODELS "face"
$ganDir  = Join-Path $MODELS "gan"
Get-Omz "face-detection-retail-0005"         $faceDir
Get-Omz "age-gender-recognition-retail-0013" $faceDir
Get-Omz "emotions-recognition-retail-0003"   $faceDir   # 5 classes
Get-Omz "head-pose-estimation-adas-0001"     $faceDir
Get-Omz "single-image-super-resolution-1032" $ganDir    # 4x SR

# AnimeGANv3 는 비상업 라이선스라 제외했다 (배경제거 U2Net · 화질개선 SR 만 사용)
Invoke-WebRequest -Uri "https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2net.onnx" `
  -OutFile (Join-Path $ganDir "u2net.onnx")

Write-Host "=== [6/9] local fonts ===" -ForegroundColor Cyan
python tools\fonts_download.py
if ($LASTEXITCODE -ne 0) { throw "font download failed" }

Write-Host "=== [7/9] mediapipe models ===" -ForegroundColor Cyan
$mpDir = Join-Path $MODELS "mediapipe"
New-Item -ItemType Directory -Force -Path $mpDir | Out-Null
Invoke-WebRequest -Uri "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task" -OutFile (Join-Path $mpDir "face_landmarker.task")
Invoke-WebRequest -Uri "https://storage.googleapis.com/mediapipe-models/gesture_recognizer/gesture_recognizer/float16/latest/gesture_recognizer.task" -OutFile (Join-Path $mpDir "gesture_recognizer.task")

Write-Host "=== [8/9] speech models (STT / TTS) ===" -ForegroundColor Cyan
# 이미 변환된 것을 그대로 쓴다 (직접 변환할 필요 없음)
& hf download OpenVINO/whisper-small-int8-ov --local-dir (Join-Path $MODELS "stt")
if ($LASTEXITCODE -ne 0) { throw "STT download failed" }
& hf download Supertone/supertonic-3 --local-dir (Join-Path $MODELS "tts")
if ($LASTEXITCODE -ne 0) { throw "TTS download failed" }

Write-Host "=== [9/9] easyocr + offline check ===" -ForegroundColor Cyan
@'
import easyocr
# store weights in models/code/easyocr (server must use the same paths)
easyocr.Reader(["ko", "en"], gpu=False,
               model_storage_directory="models/code/easyocr",
               user_network_directory="models/code/easyocr")
print("easyocr OK -> models/code/easyocr")
'@ | python -
if ($LASTEXITCODE -ne 0) { throw "easyocr download failed" }

@'
from pathlib import Path
import openvino as ov
import openvino_tokenizers  # registers tokenizer custom ops (required for vlm xml)
core = ov.Core()
print("devices:", core.available_devices)  # expect CPU / GPU / NPU
models = Path("models")
targets = list(models.rglob("*.xml")) + list(models.glob("gan/*.onnx"))
fails = 0
for name in ["duration_predictor.onnx", "text_encoder.onnx",
             "vector_estimator.onnx", "vocoder.onnx",
             "tts.json", "unicode_indexer.json"]:
    if not (models / "tts/onnx" / name).exists():
        fails += 1; print("FAIL models/tts/onnx/" + name, "| missing")
for m in targets:
    try:
        core.read_model(m); print("OK ", m)
    except Exception as e:
        fails += 1; print("FAIL", m, e)
raise SystemExit(1 if fails else 0)
'@ | python -
if ($LASTEXITCODE -ne 0) { throw "model verification failed" }

Write-Host ""
Write-Host "DONE. For offline run set:" -ForegroundColor Green
Write-Host '  $env:HF_HUB_OFFLINE=1; $env:TRANSFORMERS_OFFLINE=1; $env:YOLO_OFFLINE=1'
Write-Host ""
Write-Host "HF 에 올리려면:" -ForegroundColor Green
Write-Host "  hf upload leeyunjai/vapi-od models ."
Write-Host "  (models\org\mask-11s-cls.pt 도 함께 올려 두면 이 저장소만으로 전부 다시 만들 수 있다)" -ForegroundColor DarkGray
