# -*- coding: utf-8 -*-
"""paths — 폴더 규칙 한 곳에 모으기.

  models/   AI 모델만 (허깅페이스에서 받은 것). 사람이 만든 게 아니므로 지우면 다시 받으면 된다.
  data/     실행하면서 생기는 것 전부. "전체 초기화"는 이 폴더만 지운다.
              data/user     내가 가르친 AI
              data/project  블록 코딩 작품
              data/pycode   파이썬 작품
              data/stats    사용 통계·학습 성적표
              data/tmp      업로드된 사진 (자동 정리)
              data/.appwin  앱 창 프로필 (웹캠 권한 등)

예전 설치본은 이것들이 models/ 안에 있었다 — 서버가 처음 뜰 때 옮겨 준다.
"""
import os
import shutil

ROOT = os.path.dirname(os.path.abspath(__file__))

MODELS_DIR = os.path.join(ROOT, "models")
DATA_DIR = os.path.join(ROOT, "data")

USER_DIR = os.path.join(DATA_DIR, "user")
PROJECT_DIR = os.path.join(DATA_DIR, "project")
PYCODE_DIR = os.path.join(DATA_DIR, "pycode")
STATS_DIR = os.path.join(DATA_DIR, "stats")
TMP_DIR = os.path.join(DATA_DIR, "tmp")
APPWIN_DIR = os.path.join(DATA_DIR, ".appwin")

REPORTS_PATH = os.path.join(STATS_DIR, "reports.json")
USAGE_PATH = os.path.join(STATS_DIR, "usage.json")

# 전체 초기화 대상 (모델은 건드리지 않는다)
RESET_DIRS = [USER_DIR, PROJECT_DIR, PYCODE_DIR, STATS_DIR, TMP_DIR]


def ensure():
    for d in (DATA_DIR, USER_DIR, PROJECT_DIR, PYCODE_DIR, STATS_DIR, TMP_DIR):
        os.makedirs(d, exist_ok=True)


def migrate_old():
    """예전 위치(models/…, image_temp/)에 있던 작업 파일을 data/ 로 옮긴다."""
    moves = [
        (os.path.join(MODELS_DIR, "user"), USER_DIR),
        (os.path.join(MODELS_DIR, "project"), PROJECT_DIR),
        (os.path.join(MODELS_DIR, "pycode"), PYCODE_DIR),
        (os.path.join(MODELS_DIR, "stats"), STATS_DIR),
        (os.path.join(MODELS_DIR, ".appwin"), APPWIN_DIR),
        (os.path.join(ROOT, "image_temp"), TMP_DIR),
    ]
    for src, dst in moves:
        if not os.path.isdir(src):
            continue
        try:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            if not os.path.exists(dst):
                shutil.move(src, dst)
            else:                                   # 이미 있으면 안쪽만 옮긴다
                for name in os.listdir(src):
                    tgt = os.path.join(dst, name)
                    if not os.path.exists(tgt):
                        shutil.move(os.path.join(src, name), tgt)
                shutil.rmtree(src, ignore_errors=True)
            print("[paths] moved", os.path.basename(src), "->", os.path.relpath(dst, ROOT))
        except Exception as ex:
            print("[paths] move failed:", src, ex)


ensure()
migrate_old()
