# =============================================================================
# freeze.ps1 - 지금 설치된 버전을 requirements.lock.txt 로 잠근다
#
# 언제 쓰나:
#   setup_deploy.ps1 로 설치하고 tools\bundle_check.bat 이 전부 통과한 뒤.
#   그 상태를 그대로 다른 기기에 복제하고 싶을 때.
#
# 결과물(requirements.lock.txt)을 git 에 커밋하면,
# 이후 setup_deploy.ps1 은 자동으로 그 버전 그대로 설치한다.
# =============================================================================
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

$PY = "venv\Scripts\python.exe"
if (-not (Test-Path $PY)) { throw "venv 가 없습니다. 먼저 setup_deploy.ps1 을 실행하세요." }

$stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
$pyver = & $PY -c "import sys; print(sys.version.split()[0])"

$header = @(
  "# The Maker - 검증된 패키지 버전 (setup_deploy.ps1 이 이 파일을 우선 사용한다)",
  "# frozen at $stamp",
  "# python $pyver",
  "#",
  "# 이 파일을 지우면 requirements.txt(범위 고정)로 설치된다."
)
$header | Out-File -Encoding utf8 requirements.lock.txt
& $PY -m pip freeze | Out-File -Append -Encoding utf8 requirements.lock.txt

$n = (Get-Content requirements.lock.txt | Where-Object { $_ -notmatch "^#" }).Count
Write-Host ""
Write-Host "requirements.lock.txt 생성 완료 - 패키지 $n 개" -ForegroundColor Green
Write-Host "  git add requirements.lock.txt 로 커밋하면 다른 기기도 같은 버전으로 설치됩니다." -ForegroundColor DarkGray
