# =============================================================================
# vapi-ondevice setup - Windows (PowerShell) - always full install, no skip
# Usage: put 8 custom pt files in models\org\ then run:
#   powershell -ExecutionPolicy Bypass -File .\setup.ps1
# Existing outputs are overwritten. ASCII-only for PowerShell 5.1 safety.
# =============================================================================
$ErrorActionPreference = "Stop"
$BASE   = $PSScriptRoot
$MODELS = Join-Path $BASE "models"
foreach ($d in "org","vlm","object","face","gan","code") {
  New-Item -ItemType Directory -Force -Path (Join-Path $MODELS $d) | Out-Null
}

Write-Host "=== [1/6] python packages ===" -ForegroundColor Cyan
pip install openvino openvino-genai fastapi "uvicorn[standard]" `
    ultralytics opencv-python pillow numpy easyocr python-multipart
pip install "optimum[openvino]" nncf torchvision
# pyzbar: 1D 바코드 전용(선택). QR은 OpenCV 디코더로 동작하므로 실패해도 무방.
# Windows에서 pyzbar를 쓰려면 VC++ 2013 재배포 패키지(x64)가 필요하다.
pip install pyzbar
if ($LASTEXITCODE -ne 0) { Write-Host "pyzbar skipped (QR은 OpenCV로 동작)" -ForegroundColor Yellow }
$global:LASTEXITCODE = 0

Write-Host "=== [2/6] VLM: Qwen2.5-VL-3B INT4 export ===" -ForegroundColor Cyan
$vlmDir = Join-Path $MODELS "vlm\qwen2.5-vl-3b-int4"
if (Test-Path $vlmDir) { Remove-Item -Recurse -Force $vlmDir }
optimum-cli export openvino -m Qwen/Qwen2.5-VL-3B-Instruct --weight-format int4 $vlmDir
if ($LASTEXITCODE -ne 0) { throw "VLM export failed" }

Write-Host "=== [3/6] YOLO standard x3 export ===" -ForegroundColor Cyan
Push-Location (Join-Path $MODELS "object")
@'
import shutil
from pathlib import Path
from ultralytics import YOLO

for name in ["yolo11m.pt", "yolo11m-pose.pt", "yolo11m-seg.pt"]:
    out = Path(name.replace(".pt", "_openvino_model"))
    if out.exists():
        shutil.rmtree(out)  # overwrite: convert fresh every run
    YOLO(name).export(format="openvino", half=True)
    print("OK  ", out)
'@ | python -
if ($LASTEXITCODE -ne 0) { throw "step 3 failed" }
Pop-Location

Write-Host "=== [4/6] custom x8 export (models\org -> models\object) ===" -ForegroundColor Cyan
Push-Location $MODELS
@'
import shutil, sys
from pathlib import Path
from ultralytics import YOLO

ORG, OBJ = Path("org"), Path("object")
EXPECTED = ["ball-11s.pt", "box-11s.pt", "fall-11s.pt", "fire-11s.pt",
            "helmet-11s.pt", "mask-11s-cls.pt", "number-11s.pt", "rps-11s.pt"]
# box-11s: seg model used as detect (read boxes only) - export is the same
# helmet-11s: 2 classes (face/helmet) / mask-11s-cls: classifier (224), input = face crop

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

shutil.rmtree(ORG)  # all 8 converted -> remove source pt folder
print("custom x8 done, models/org removed")
'@ | python -
if ($LASTEXITCODE -ne 0) { throw "step 4 failed" }
Pop-Location

Write-Host "=== [5/6] face suite + SR + transform models ===" -ForegroundColor Cyan
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

$AGV3 = "https://github.com/TachibanaYoshino/AnimeGANv3/releases/download/v1.1.0"
foreach ($f in "AnimeGANv3_Hayao_36.onnx","AnimeGANv3_Shinkai_37.onnx") {
  Invoke-WebRequest -Uri "$AGV3/$f" -OutFile (Join-Path $ganDir $f)
}
Invoke-WebRequest -Uri "https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2net.onnx" `
  -OutFile (Join-Path $ganDir "u2net.onnx")

Write-Host "=== [5.5/6] local fonts ===" -ForegroundColor Cyan
python fonts_download.py
if ($LASTEXITCODE -ne 0) { throw "font download failed" }

Write-Host "=== [6/6] easyocr + offline check ===" -ForegroundColor Cyan
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