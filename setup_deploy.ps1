# ==========================================================================
#  vapi-od : one-shot deploy (clone the repo, then run this)
#  Installs packages + downloads converted models from HF + verifies.
#  usage:
#    powershell -ExecutionPolicy Bypass -File setup_deploy.ps1
#    powershell -ExecutionPolicy Bypass -File setup_deploy.ps1 -Token hf_xxxx
#  token lookup order: -Token arg > HF_TOKEN env
# ==========================================================================
param([string]$Token = "")

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if ($Token) { $env:HF_TOKEN = $Token }
if (-not $env:HF_TOKEN) {
  Write-Host "[WARN] no HF token given (arg/env) - download will fail if repo is private" -ForegroundColor Yellow
}

Write-Host "=== [1/5] venv ===" -ForegroundColor Cyan
if (-not (Test-Path "venv\Scripts\python.exe")) { python -m venv venv }
$PY = "venv\Scripts\python.exe"
# pip bootstrap via cmd (avoids PS5.1 stderr-to-error promotion); fast no-op if pip exists
cmd /c "venv\Scripts\python.exe -m ensurepip --upgrade >nul 2>&1"
cmd /c "venv\Scripts\python.exe -m pip --version >nul 2>&1"
if ($LASTEXITCODE -ne 0) { throw "venv has no pip - delete venv folder and retry" }
& $PY -m pip install --upgrade pip --quiet

Write-Host "=== [2/5] packages ===" -ForegroundColor Cyan
& $PY -m pip install openvino openvino-genai fastapi "uvicorn[standard]" `
    ultralytics opencv-python pillow numpy easyocr python-multipart huggingface_hub mediapipe
if ($LASTEXITCODE -ne 0) { throw "package install failed" }
& $PY -m pip install pyzbar 2>$null | Out-Null   # optional (1D barcodes)
$global:LASTEXITCODE = 0

Write-Host "=== [3/5] models from HF ===" -ForegroundColor Cyan
& "venv\Scripts\hf.exe" download leeyunjai/vapi-od --local-dir models --exclude "models.7z"
if ($LASTEXITCODE -ne 0) { throw "model download failed (check token / network)" }

Write-Host "=== [4/5] fonts ===" -ForegroundColor Cyan
if (Test-Path "view_project\fonts\fonts.css") {
  Write-Host "  fonts already in repo - skip"
} else {
  & $PY fonts_download.py
  if ($LASTEXITCODE -ne 0) { throw "font download failed" }
}

Write-Host "=== [5/5] verify ===" -ForegroundColor Cyan
& $PY check.py
if ($LASTEXITCODE -ne 0) { throw "model verification failed" }

Write-Host ""
Write-Host "DONE. start with:  run.bat" -ForegroundColor Green