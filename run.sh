#!/usr/bin/env bash
# 실행 (우분투) — 윈도우의 run.bat 과 같다. 설치는 bash setup_deploy.sh
cd "$(dirname "$0")"
if [ -x venv/bin/python ]; then PY=venv/bin/python; else echo "[WARN] venv 가 없어요 — 먼저 bash setup_deploy.sh"; PY=python3; fi

# 인터넷 없이 — 모델을 받으러 나가지 않게
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1

# 실행 기록(요청 한 줄씩)을 보려면:            export VAPI_VERBOSE=1
# 화면을 처음부터 확대하려면(예: 125%):        export VAPI_ZOOM=1.25
# 기본은 전체 화면(키오스크) — 보통 창으로:    export VAPI_NO_KIOSK=1

echo "Starting ... the browser opens right away and shows loading progress."
exec "$PY" main.py "$@"
