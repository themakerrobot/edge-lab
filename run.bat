@echo off
cd /d %~dp0
call venv\Scripts\activate
set HF_HUB_OFFLINE=1
set TRANSFORMERS_OFFLINE=1
set YOLO_OFFLINE=1
echo vapi-od 시작 중... 모델 로딩이 끝나면 브라우저가 자동으로 열립니다 (1~2분).
python main.py
pause