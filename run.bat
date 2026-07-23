@echo off
cd /d %~dp0
call venv\Scripts\activate
set HF_HUB_OFFLINE=1
set TRANSFORMERS_OFFLINE=1
set YOLO_OFFLINE=1
python main.py
