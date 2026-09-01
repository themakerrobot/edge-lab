# ==========================================================================
#  edge-lab : one-shot deploy (clone the repo, then run this)
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

# 설치된 패키지 버전을 남긴다 — 나중에 "언제부터 안 되기 시작했는지" 를 찾는 근거가 된다.
# 자리는 paths.py 의 앱데이터(기본 %LOCALAPPDATA%\TheMaker) — 프로그램 폴더에 data\ 를 만들지 않는다
$appdata = & $PY -c "import paths; print(paths.DATA_DIR)"
New-Item -ItemType Directory -Force -Path $appdata | Out-Null
$snap = Join-Path $appdata "installed-packages.txt"
$stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
"# installed by setup_deploy.ps1 at $stamp" | Out-File -Encoding utf8 $snap
& $PY -c "import sys; print('# python ' + sys.version.split()[0])" | Out-File -Append -Encoding utf8 $snap
& $PY -m pip freeze | Out-File -Append -Encoding utf8 $snap
Write-Host "  package versions -> $snap" -ForegroundColor DarkGray

Write-Host "=== [3/5] models from HF ===" -ForegroundColor Cyan
# org/ 는 모델 변환용 원본(.pt) 이라 교실 PC 에는 필요 없다 — 서버는 IR 만 읽는다
# --exclude 는 한 번에 값 하나만 받는다. 예전처럼 두 개를 이어 쓰면 뒤엣것이
# "받을 파일 이름"으로 먹혀 org/* 를 파일로 받으려다 죽는다(WinError 123).
& "venv\Scripts\hf.exe" download leeyunjai/vapi-od --local-dir models --exclude "models.7z" --exclude "org/*"
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