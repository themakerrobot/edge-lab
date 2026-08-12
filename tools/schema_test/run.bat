@echo off
chcp 65001 >nul
REM ==========================================================================
REM  The Maker : 스키마 시험 — 모델 없이 응답 모양을 확인한다 (몇 초면 끝난다).
REM  가짜 엔진으로 서버(포트 57799)를 띄우고 엔드포인트와 themaker 를 실제로 부른다.
REM  진짜 서버(57711)가 켜져 있어도 상관없다.
REM ==========================================================================
setlocal
cd /d "%~dp0"
cd ..\..
if not exist main.py (echo [FAIL] main.py 를 찾을 수 없습니다 & pause & exit /b 1)

if exist "python\python.exe" (
  rem 배포 번들 — 동봉된 파이썬
  set "PY=python\python.exe"
  set "PYTHONPATH=%CD%\pylib"
) else if exist "venv\Scripts\python.exe" (
  rem 개발 설치 — setup_deploy.ps1 이 만든 venv
  set "PY=venv\Scripts\python.exe"
) else (
  echo [WARN] venv 가 없어 시스템 파이썬을 씁니다
  set "PY=python"
)

set HF_HUB_OFFLINE=1
set TRANSFORMERS_OFFLINE=1
set YOLO_OFFLINE=1
set "YOLO_CONFIG_DIR=%CD%\.ultralytics"
if not exist ".ultralytics" mkdir ".ultralytics"

"%PY%" tools\schema_test\run.py
set RC=%ERRORLEVEL%
echo.
if "%RC%"=="0" (echo [OK] 모두 통과했습니다.) else (echo [FAIL] 실패한 항목이 있습니다. 위 목록을 확인하세요.)
pause
exit /b %RC%
