@echo off
chcp 65001 >nul
cd /d "%~dp0"

REM use venv python directly (no activation needed; works even if activate.bat is missing)
if exist "%~dp0venv\Scripts\python.exe" (
  set "PY=%~dp0venv\Scripts\python.exe"
) else if exist "%~dp0python\python.exe" (
  set "PY=%~dp0python\python.exe"
  set "PYTHONPATH=%~dp0pylib"
) else (
  echo [WARN] venv not found - using system python
  set "PY=python"
)

set HF_HUB_OFFLINE=1
set TRANSFORMERS_OFFLINE=1
set YOLO_OFFLINE=1
set "YOLO_CONFIG_DIR=%~dp0.ultralytics"
if not exist "%~dp0.ultralytics" mkdir "%~dp0.ultralytics"

rem 실행 기록(요청 한 줄씩)을 보려면 아래 줄의 rem 을 지운다 — 기본은 조용히 뜬다
rem set VAPI_VERBOSE=1

rem 화면을 처음부터 확대해서 띄우려면 아래 줄의 rem 을 지우고 배율을 조절한다 (예: 1.25 = 125%%)
rem set VAPI_ZOOM=1.25

rem 기본은 전체 화면(키오스크)이다 — 빠져나갈 때는 오른쪽 위 전원 단추의 [끄기].
rem 보통 창으로 띄우려면(개발·선생님 PC) 아래 줄의 rem 을 지운다
rem set VAPI_NO_KIOSK=1

echo Starting edge-lab ... the browser opens right away and shows loading progress.
"%PY%" main.py
rem [끄기] 로 정상 종료하면 창을 바로 닫는다. 오류로 멈췄을 때만 메시지를 읽을 수 있게 멈춘다.
if errorlevel 1 pause