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

# 런타임에 안 쓰는 것이 섞여 잠기면 교실 PC 가 헛되이 내려받는다 — 이름만 확인해 알려준다.
# (pyinstaller 계열은 배포용 exe 빌드에만, optimum 계열은 모델 변환에만 쓴다)
$junk = Get-Content requirements.lock.txt |
        Select-String -Pattern "^(pyinstaller|altgraph|pefile|pywin32-ctypes|optimum|nncf|transformers)" |
        ForEach-Object { $_.Line }
if ($junk) {
  Write-Host ""
  Write-Host "  [주의] 런타임에 필요 없는 패키지가 잠겼습니다:" -ForegroundColor Yellow
  $junk | ForEach-Object { Write-Host "    $_" -ForegroundColor Yellow }
  Write-Host "    venv 에서 지운 뒤 다시 freeze 하세요 (교실 PC 가 이것까지 받습니다)" -ForegroundColor Yellow
}
Write-Host ""
Write-Host "requirements.lock.txt 생성 완료 - 패키지 $n 개" -ForegroundColor Green
Write-Host "  git add requirements.lock.txt 로 커밋하면 다른 기기도 같은 버전으로 설치됩니다." -ForegroundColor DarkGray
