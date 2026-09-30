#!/usr/bin/env bash
# 코딩 실습 (우분투) — JupyterLab 을 전용 창으로 연다. 창을 닫으면 JupyterLab 도 꺼진다 (lab.py)
# 노트북 원본은 notebooks/ , 실제로 쓰는 곳은 작업폴더(~/Documents/Edge Lab/notebooks)
cd "$(dirname "$0")"
if [ -x venv/bin/python ]; then PY=venv/bin/python; else PY=python3; fi

# 인터넷 없이 — 모델을 받으러 나가지 않게
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 YOLO_OFFLINE=1
export YOLO_CONFIG_DIR="$PWD/.ultralytics"
mkdir -p "$YOLO_CONFIG_DIR"

exec "$PY" lab.py "$@"
