# =============================================================================
# upgrade_check.ps1 - 패키지 최신 버전으로 올려서 시험해 본다 (개선용)
#
#   본 설치(setup_deploy.ps1)는 requirements 로 고정된 버전을 쓴다.
#   이 스크립트는 그것과 별개로 "최신으로 올리면 문제가 없나"를 확인하는 용도다.
#
# 쓰는 순서
#   1) tools\upgrade_check.ps1          <- 최신으로 올린다 (이전 상태를 백업해 둔다)
#   2) run.bat 을 띄운 뒤 tools\bundle_check.bat  <- 전 기능 확인
#   3) 이상 없으면  tools\freeze.ps1     <- requirements.lock.txt 갱신 후 커밋
#      문제가 있으면 tools\upgrade_check.ps1 -Rollback  <- 원래대로 되돌린다
#
# 주의: 이 스크립트는 개발 PC 에서만 쓴다. 교실 PC 에서는 실행하지 말 것.
# =============================================================================
param(
  [switch]$Rollback,          # 되돌리기
  [switch]$Runtime            # openvino / onnxruntime 까지 올린다 (기본은 제외)
)
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

$PY = "venv\Scripts\python.exe"
if (-not (Test-Path $PY)) { throw "venv 가 없습니다. 먼저 setup_deploy.ps1 을 실행하세요." }
New-Item -ItemType Directory -Force -Path data | Out-Null
$backup = "data\requirements.before-upgrade.txt"

# ---------------------------------------------------------------- 되돌리기
if ($Rollback) {
  if (-not (Test-Path $backup)) { throw "백업이 없습니다: $backup" }
  Write-Host "=== 되돌리는 중 ($backup) ===" -ForegroundColor Cyan
  & $PY -m pip install -r $backup
  if ($LASTEXITCODE -ne 0) { throw "rollback failed" }
  Write-Host "되돌렸습니다. run.bat 으로 확인하세요." -ForegroundColor Green
  exit 0
}

# ---------------------------------------------------------------- 올리기
Write-Host "=== [1/3] 지금 상태 백업 ===" -ForegroundColor Cyan
& $PY -m pip freeze | Out-File -Encoding utf8 $backup
Write-Host "  $backup"

Write-Host ""
Write-Host "=== [2/3] 최신 버전으로 올리기 ===" -ForegroundColor Cyan
# 추론 런타임은 사고 이력이 있어 기본으로 제외한다 (-Runtime 을 줘야 올라간다)
$pkgs = @("ultralytics", "mediapipe", "easyocr", "fastapi", "uvicorn[standard]",
          "python-multipart", "huggingface_hub", "opencv-python", "pillow",
          "numpy", "sounddevice")
if ($Runtime) {
  Write-Host "  추론 런타임(openvino/openvino-genai/onnxruntime)도 함께 올립니다" -ForegroundColor Yellow
  $pkgs += @("openvino", "openvino-genai", "onnxruntime")
} else {
  Write-Host "  추론 런타임은 제외합니다 (-Runtime 을 주면 함께 올립니다)" -ForegroundColor DarkGray
}
& $PY -m pip install --upgrade @pkgs
if ($LASTEXITCODE -ne 0) { throw "upgrade failed" }

Write-Host ""
Write-Host "=== [3/3] 바뀐 것 ===" -ForegroundColor Cyan
$before = @{}
Get-Content $backup | ForEach-Object {
  if ($_ -match "^([^=<>~ ]+)==(.+)$") { $before[$Matches[1].ToLower()] = $Matches[2] }
}
$changed = 0
& $PY -m pip freeze | ForEach-Object {
  if ($_ -match "^([^=<>~ ]+)==(.+)$") {
    $name = $Matches[1]; $now = $Matches[2]; $old = $before[$name.ToLower()]
    if ($old -and $old -ne $now) { Write-Host ("  {0,-24} {1}  ->  {2}" -f $name, $old, $now); $changed++ }
    elseif (-not $old)           { Write-Host ("  {0,-24} (새로 설치) {1}" -f $name, $now) -ForegroundColor DarkGray }
  }
}
if ($changed -eq 0) { Write-Host "  바뀐 것이 없습니다 (이미 최신)" -ForegroundColor DarkGray }

Write-Host ""
Write-Host "다음 순서:" -ForegroundColor Green
Write-Host "  1) run.bat 실행 -> tools\bundle_check.bat 으로 전 기능 확인"
Write-Host "  2) 이상 없으면  tools\freeze.ps1        (requirements.lock.txt 갱신)"
Write-Host "     문제가 있으면 tools\upgrade_check.ps1 -Rollback"
