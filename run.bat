@echo off
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

rem 화면을 처음부터 확대해서 띄우려면 아래 줄의 rem 을 지우고 배율을 조절한다 (예: 1.25 = 125%%)
rem set VAPI_ZOOM=1.25

echo Starting vapi-od ... the browser opens right away and shows loading progress.
"%PY%" main.py
pause