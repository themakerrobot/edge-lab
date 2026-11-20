#!/usr/bin/env bash
# ==========================================================================
#  우분투 설치 — 저장소를 받은 뒤 이것 하나로 끝난다 (윈도우는 setup_deploy.ps1 · setup.bat)
#    venv → 패키지 → 허깅페이스에서 모델 → 글꼴 → 점검
#  쓰는 법:
#    git clone <저장소 주소(brand.json 의 repo_github)> && cd <그 폴더>
#    bash setup_deploy.sh            (private 저장소면 HF_TOKEN=hf_xxx bash setup_deploy.sh)
#    ./run.sh                        실행 · 코딩 실습은 ./lab.sh
#  배포판(압축 풀고 바로 실행)은 윈도우만 만든다 — 우분투는 이 명령으로 깐다.
# ==========================================================================
set -euo pipefail
cd "$(dirname "$0")"

echo "=== [0/5] 시스템 패키지 확인 ==="
# 파이썬 venv · 소리(sounddevice → libportaudio2) — 없으면 설치 명령을 알려 주고 멈춘다
need=()
python3 -c "import venv, ensurepip" 2>/dev/null || need+=("python3-venv")
ldconfig -p 2>/dev/null | grep -q libportaudio.so.2 || need+=("libportaudio2")
if [ ${#need[@]} -gt 0 ]; then
  echo "  먼저 설치해 주세요:  sudo apt install -y ${need[*]}"
  exit 1
fi

echo "=== [1/5] venv ==="
[ -x venv/bin/python ] || python3 -m venv venv
PY=venv/bin/python
"$PY" -m pip install --upgrade pip --quiet

echo "=== [2/5] 패키지 ==="
# requirements.lock.txt(윈도우 · 파이썬 3.13 에서 고정한 버전)를 그대로 쓰되 윈도우 전용(pywinpty · pywin32)은 뺀다.
# 우분투 파이썬 버전에 맞는 휠이 없어 실패하면 requirements.txt(범위)로 다시 깐다.
lock=$(mktemp)
grep -viE '^(pywinpty|pywin32|pywin32-ctypes|winpty)==' requirements.lock.txt > "$lock"
if ! "$PY" -m pip install -r "$lock"; then
  echo "  고정 버전으로 깔지 못했어요 — requirements.txt(범위)로 다시 깝니다"
  "$PY" -m pip install -r requirements.txt
fi
rm -f "$lock"
appdata=$("$PY" -c "import paths; print(paths.APPDATA_DIR)")
mkdir -p "$appdata"
{ echo "# installed by setup_deploy.sh at $(date '+%F %T')"; "$PY" -c "import sys; print('# python ' + sys.version.split()[0])"; "$PY" -m pip freeze; } > "$appdata/installed-packages.txt"
echo "  패키지 버전 → $appdata/installed-packages.txt"

echo "=== [3/5] 허깅페이스에서 모델 ==="
"$PY" tools/fetch_models.py

echo "=== [4/5] 글꼴 ==="
if [ -f view_project/fonts/fonts.css ]; then echo "  저장소에 있음 — 건너뜀"; else "$PY" tools/fonts_download.py; fi

echo "=== [5/5] 점검 ==="
"$PY" tools/check.py

chmod +x run.sh lab.sh 2>/dev/null || true
echo
echo "끝났어요. 실행:  ./run.sh     코딩 실습:  ./lab.sh"
