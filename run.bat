@echo off
cd /d "%~dp0"

if exist "%~dp0venv\Scripts\activate.bat" (
  call "%~dp0venv\Scripts\activate.bat"
) else (
  echo [WARN] venv not found - using system python
)

set HF_HUB_OFFLINE=1
set TRANSFORMERS_OFFLINE=1
set YOLO_OFFLINE=1

echo Starting vapi-od ... browser opens automatically when models are ready (1-2 min).
python main.py
pause
