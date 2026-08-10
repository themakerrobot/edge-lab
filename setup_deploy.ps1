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
# requirements.lock.txt 가 있으면 그 버전 그대로 설치한다 (배포 기기 전부 동일한 환경).
# 없으면 requirements.txt(범위 고정)로 설치한 뒤, 검증이 끝나면 tools\freeze.ps1 로 잠근다.
if (Test-Path "requirements.lock.txt") {
  Write-Host "  requirements.lock.txt 사용 (버전 고정)" -ForegroundColor DarkGray
  & $PY -m pip install -r requirements.lock.txt
} else {
  Write-Host "  requirements.txt 사용 — 검증 후 tools\freeze.ps1 로 잠그세요" -ForegroundColor Yellow
  & $PY -m pip install -r requirements.txt
}
if ($LASTEXITCODE -ne 0) { throw "package install failed" }
# pyinstaller: 배포용 exe 빌드(tools\make_bundle.bat)에만 필요 — 실패해도 무방
& $PY -m pip install pyinstaller 2>$null | Out-Null
$global:LASTEXITCODE = 0

# 설치된 패키지 버전을 남긴다 — 나중에 "언제부터 안 되기 시작했는지" 를 찾는 근거가 된다
New-Item -ItemType Directory -Force -Path data | Out-Null
$stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
"# installed by setup_deploy.ps1 at $stamp" | Out-File -Encoding utf8 data\installed-packages.txt
& $PY -c "import sys; print('# python ' + sys.version.split()[0])" | Out-File -Append -Encoding utf8 data\installed-packages.txt
& $PY -m pip freeze | Out-File -Append -Encoding utf8 data\installed-packages.txt
Write-Host "  package versions -> data\installed-packages.txt" -ForegroundColor DarkGray

Write-Host "=== [3/5] models from HF ===" -ForegroundColor Cyan
& "venv\Scripts\hf.exe" download leeyunjai/vapi-od --local-dir models --exclude "models.7z"
if ($LASTEXITCODE -ne 0) { throw "model download failed (check token / network)" }

Write-Host "=== [4/5] fonts ===" -ForegroundColor Cyan
if (Test-Path "view_project\fonts\fonts.css") {
  Write-Host "  fonts already in repo - skip"
} else {
  & $PY tools\fonts_download.py
  if ($LASTEXITCODE -ne 0) { throw "font download failed" }
}

Write-Host "=== [5/5] verify ===" -ForegroundColor Cyan
& $PY tools\check.py
if ($LASTEXITCODE -ne 0) { throw "model verification failed" }

Write-Host ""
Write-Host "DONE. start with:  run.bat" -ForegroundColor Green