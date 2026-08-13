# -*- coding: utf-8 -*-
"""paths — 폴더 규칙 한 곳에 모으기.

프로그램 폴더는 깨끗하게 둔다. 새 버전으로 덮어써도 아이들 작품이 함께
사라지면 안 되고, Program Files 처럼 쓰기가 막힌 곳에 설치돼도 돌아야 한다.

  프로그램 폴더
      models/      허깅페이스에서 받은 AI 모델. 지워도 다시 받으면 된다.

  작업폴더 — 사람이 만든 것. 사용자가 위치를 고른다.
      user/        내가 가르친 AI
      project/     블록 코딩 작품
      pycode/      파이썬 작품 (파이썬을 실행할 때 이 폴더가 작업 위치)
      db/          아이가 올린 자료
      기본값: 문서\\The Maker  (문서 폴더가 없으면 홈\\The Maker)

  앱데이터 — 프로그램이 혼자 쓰는 것. 사용자가 열어볼 일이 없다.
      stats/  사용 통계·성적표   tmp/  업로드된 사진(자동 정리)
      .appwin/  앱 창 프로필     settings.json  작업폴더 위치
      기본값: 윈도우 %LOCALAPPDATA%\\TheMaker / 리눅스 ~/.local/share/themaker

정하는 순서 (앞이 이김)
  1) 환경변수 VAPI_WORK / VAPI_APPDATA
  2) 프로그램 폴더의 portable.txt — USB 로 들고 다닐 때. 옆에 data/ 를 만든다
  3) 앱데이터의 settings.json (설정 화면에서 바꾼 값)
  4) 기본값

예전 설치본(프로그램 폴더 안 data/, 더 예전엔 models/ 안)은 처음 뜰 때 옮겨 준다.
"""
import json
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(ROOT, "models")

WORK_NAME = "The Maker"
PORTABLE_MARK = os.path.join(ROOT, "portable.txt")


def _home():
    return os.path.expanduser("~")


def _documents():
    """윈도우 '문서' 폴더. 원드라이브로 옮겨져 있어도 레지스트리가 알고 있다."""
    if sys.platform.startswith("win"):
        try:
            import winreg
            key = r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key) as k:
                val, _ = winreg.QueryValueEx(k, "Personal")
                val = os.path.expandvars(val)
                if os.path.isdir(val):
                    return val
        except Exception:
            pass
    d = os.path.join(_home(), "Documents")
    return d if os.path.isdir(d) else _home()


def _default_appdata():
    if sys.platform.startswith("win"):
        base = os.environ.get("LOCALAPPDATA") or os.path.join(_home(), "AppData", "Local")
        return os.path.join(base, "TheMaker")
    if sys.platform == "darwin":
        return os.path.join(_home(), "Library", "Application Support", "TheMaker")
    base = os.environ.get("XDG_DATA_HOME") or os.path.join(_home(), ".local", "share")
    return os.path.join(base, "themaker")


def _portable():
    return os.path.isfile(PORTABLE_MARK)


# ── 앱데이터 위치 ────────────────────────────────────────────────────────
if os.environ.get("VAPI_APPDATA"):
    APPDATA_DIR = os.path.abspath(os.environ["VAPI_APPDATA"])
elif _portable():
    APPDATA_DIR = os.path.join(ROOT, "data")
else:
    APPDATA_DIR = _default_appdata()

SETTINGS_PATH = os.path.join(APPDATA_DIR, "settings.json")


def read_settings():
    try:
        with open(SETTINGS_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def write_settings(data):
    os.makedirs(APPDATA_DIR, exist_ok=True)
    tmp = SETTINGS_PATH + ".new"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, SETTINGS_PATH)          # 쓰다 만 파일이 남지 않게


def default_work():
    if _portable():
        return os.path.join(ROOT, "data", "work")
    return os.path.join(_documents(), WORK_NAME)


def _reachable(path):
    """지금 이 자리에 진짜 쓸 수 있는지. 만들어 보고 써 본다.

    USB 를 뽑았거나 드라이브 문자가 바뀌면(E: → F:) 경로만 남고 자리는 없다.
    그대로 두면 서버는 멀쩡히 뜨는데 저장이 전부 실패한다 — 아이는 콘솔을
    안 보니 원인을 알 수 없다. 그래서 켤 때 한 번 확인한다.
    """
    try:
        os.makedirs(path, exist_ok=True)
        probe = os.path.join(path, ".write-test")
        with open(probe, "w", encoding="utf-8") as f:
            f.write("ok")
        os.remove(probe)
        return True
    except Exception:
        return False


def _pick_work():
    """쓸 작업폴더를 정한다. 돌려주는 값: (실제로 쓸 자리, 못 쓴 자리 or None)

    정해진 자리를 못 쓰면 기본 자리로 물러선다. 설정은 지우지 않는다 —
    USB 를 다시 꽂으면 그대로 이어서 쓰게.
    """
    if os.environ.get("VAPI_WORK"):
        return os.path.abspath(os.environ["VAPI_WORK"]), None
    saved = read_settings().get("work_dir")
    if saved and str(saved).strip():
        want = os.path.abspath(str(saved))
        if _reachable(want):
            return want, None
        fallback = default_work()
        print("[paths] 작업폴더를 찾을 수 없어요:", want)
        print("[paths] 이번에는 여기를 씁니다:", fallback,
              "(USB 라면 다시 꽂고 프로그램을 다시 켜세요)")
        return fallback, want
    return default_work(), None


WORK_ROOT, WORK_UNREACHABLE = _pick_work()

USER_DIR = os.path.join(WORK_ROOT, "user")
PROJECT_DIR = os.path.join(WORK_ROOT, "project")
PYCODE_DIR = os.path.join(WORK_ROOT, "pycode")
DB_DIR = os.path.join(WORK_ROOT, "db")

# 통계·성적표는 그 사람이 만든 기록이다 — 작업폴더에 둔다.
# (1 PC : 1 학생 구조라 "이 PC 의 통계"와 "이 사람의 기록"이 같다. 작업폴더를
#  USB 로 옮기면 성적표도 따라간다. 교사용 집계는 나중에 별도 서버로 보내는
#  방식이라, 여기서 파일을 나눠 둘 이유가 없다.)
STATS_DIR = os.path.join(WORK_ROOT, "stats")

# 블록으로 만든 작품(.json). 파이썬 작품(pycode)과 같은 급이라 나란히 둔다.
BLOCKS_DIR = os.path.join(WORK_ROOT, "blocks")

# 작업폴더에 딸린 칸 이름 — 옮길 때·비었는지 볼 때 모두 이 목록을 쓴다.
# 예전에는 같은 목록이 두 군데 적혀 있어서, 칸을 하나 늘리면 한쪽만 고쳐질 수 있었다.
WORK_PARTS = ("user", "project", "pycode", "blocks", "db", "stats")

# 임시 사진과 앱 창 프로필은 그 PC 의 것 — 옮겨 봐야 쓸모없으므로 앱데이터에 둔다.
TMP_DIR = os.path.join(APPDATA_DIR, "tmp")
APPWIN_DIR = os.path.join(APPDATA_DIR, ".appwin")

DATA_DIR = APPDATA_DIR          # 예전 이름 — 설치 목록 파일이 쓴다

REPORTS_PATH = os.path.join(STATS_DIR, "reports.json")
USAGE_PATH = os.path.join(STATS_DIR, "usage.json")

RESET_DIRS = [USER_DIR, PROJECT_DIR, PYCODE_DIR, DB_DIR, STATS_DIR, TMP_DIR]
# 위 WORK_PARTS 에서 뽑는다 — 목록을 두 벌 적어 두면 칸을 늘릴 때 한쪽만 고쳐진다
WORK_SUBDIRS = [os.path.join(WORK_ROOT, n) for n in WORK_PARTS]


def ensure():
    for d in [APPDATA_DIR, TMP_DIR, WORK_ROOT] + WORK_SUBDIRS:
        try:
            os.makedirs(d, exist_ok=True)
        except Exception as ex:
            print("[paths] 폴더를 만들 수 없어요:", d, ex)


# ── 쓰는 사람 이름 ───────────────────────────────────────────────────────
# 작업폴더 안(work.json)에 둔다 — PC 설정이 아니라 그 사람의 것이므로, USB 로
# 옮기면 이름도 따라가야 한다. 나중에 교사용 서버로 기록을 보낼 때 누구 것인지
# 가리는 값으로 쓴다. 지금은 이 컴퓨터 안에만 있다.
WORK_META = "work.json"


def _meta_path():
    return os.path.join(WORK_ROOT, WORK_META)


def default_user_name():
    """윈도우/리눅스 로그인 이름 — 아이가 따로 안 적어도 뭔가는 있게."""
    try:
        import getpass
        return getpass.getuser()
    except Exception:
        return os.environ.get("USERNAME") or os.environ.get("USER") or ""


def read_work_meta():
    try:
        with open(_meta_path(), encoding="utf-8") as f:
            d = json.load(f)
            return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def write_work_meta(data):
    os.makedirs(WORK_ROOT, exist_ok=True)
    tmp = _meta_path() + ".new"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, _meta_path())


def user_name():
    name = str(read_work_meta().get("name") or "").strip()
    return name or default_user_name()


def set_user_name(name):
    name = str(name or "").strip()[:40]
    meta = read_work_meta()
    if name:
        meta["name"] = name
    else:
        meta.pop("name", None)          # 비우면 로그인 이름으로 돌아간다
    write_work_meta(meta)
    return user_name()


def can_write(path):
    """그 폴더에 진짜 쓸 수 있는지 — 만들어 보고 지운다."""
    try:
        os.makedirs(path, exist_ok=True)
        probe = os.path.join(path, ".write-test")
        with open(probe, "w", encoding="utf-8") as f:
            f.write("ok")
        os.remove(probe)
        return True, ""
    except Exception as ex:
        return False, str(ex)


def _merge(src, dst):
    """src 안의 것을 dst 로 옮긴다. 이미 있는 이름은 건드리지 않는다."""
    try:
        os.makedirs(dst, exist_ok=True)
        for name in os.listdir(src):
            tgt = os.path.join(dst, name)
            if not os.path.exists(tgt):
                shutil.move(os.path.join(src, name), tgt)
        if not os.listdir(src):
            os.rmdir(src)
    except Exception as ex:
        print("[paths] 옮기지 못했어요:", src, ex)


def has_work(path):
    """그 폴더에 이미 작업이 들어 있는지 — 작품·자료·이름 중 하나라도 있으면 참."""
    if os.path.isfile(os.path.join(path, WORK_META)):
        return True
    for name in WORK_PARTS:
        d = os.path.join(path, name)
        try:
            if os.path.isdir(d) and any(True for _ in os.scandir(d)):
                return True
        except Exception:
            pass
    return False


def set_work_dir(path, mode="auto"):
    """작업폴더를 바꾼다. 새 위치를 돌려준다.

    두 가지 일을 갈라 놓는다 — 섞이면 남의 작업을 덮어쓴다.

      옮기기(move)   빈 폴더로 간다. 지금 작업을 그쪽으로 가져간다.
      이어서 쓰기(open)  이미 작업이 든 폴더를 그대로 쓴다. **아무것도 옮기지 않는다.**
                     (지난 학기 폴더나 USB 를 다시 여는 경우)

    mode="auto" 면 폴더 상태를 보고 정한다 — 비어 있으면 옮기기, 들어 있으면 이어서 쓰기.
    전에는 늘 옮기기여서, 지난 학기 폴더를 고르면 이번 학기 파일이 그 안으로 쏟아져
    들어가고 원래 폴더는 비었다. 아이 작품이 뒤섞이는 사고라 이렇게 갈랐다.
    """
    new = os.path.abspath(str(path).strip())
    ok, why = can_write(new)
    if not ok:
        raise OSError("이 폴더에는 쓸 수 없어요: " + why)

    old = WORK_ROOT
    same = os.path.normcase(new) == os.path.normcase(old)
    if mode == "auto":
        mode = "open" if has_work(new) else "move"

    if not same and mode == "move":
        for name in WORK_PARTS:
            src = os.path.join(old, name)
            if os.path.isdir(src):
                _merge(src, os.path.join(new, name))
        meta = os.path.join(old, WORK_META)          # 쓰는 사람 이름도 함께
        if os.path.isfile(meta) and not os.path.exists(os.path.join(new, WORK_META)):
            try:
                shutil.move(meta, os.path.join(new, WORK_META))
            except Exception as ex:
                print("[paths] 이름 파일을 옮기지 못했어요:", ex)

    cfg = read_settings()
    cfg["work_dir"] = new
    write_settings(cfg)
    return new


def migrate_old():
    """예전 위치에 있던 것을 새 자리로. 두 세대를 함께 본다."""
    old_data = os.path.join(ROOT, "data")
    pairs = [
        (os.path.join(MODELS_DIR, "user"), USER_DIR),
        (os.path.join(MODELS_DIR, "project"), PROJECT_DIR),
        (os.path.join(MODELS_DIR, "pycode"), PYCODE_DIR),
        (os.path.join(MODELS_DIR, "stats"), STATS_DIR),
        (os.path.join(MODELS_DIR, ".appwin"), APPWIN_DIR),
        (os.path.join(ROOT, "image_temp"), TMP_DIR),
        # 통계를 앱데이터에 두던 판(2026-08 이전)에서 쓰던 자리 — 작업폴더로 데려온다
        (os.path.join(APPDATA_DIR, "stats"), STATS_DIR),
    ]
    if os.path.normcase(old_data) != os.path.normcase(APPDATA_DIR):
        pairs += [
            (os.path.join(old_data, "user"), USER_DIR),
            (os.path.join(old_data, "project"), PROJECT_DIR),
            (os.path.join(old_data, "pycode"), PYCODE_DIR),
            (os.path.join(old_data, "db"), DB_DIR),
            (os.path.join(old_data, "stats"), STATS_DIR),
            (os.path.join(old_data, "tmp"), TMP_DIR),
            (os.path.join(old_data, ".appwin"), APPWIN_DIR),
        ]
    moved = []
    for src, dst in pairs:
        if not os.path.isdir(src) or os.path.normcase(src) == os.path.normcase(dst):
            continue
        try:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            if not os.path.exists(dst):
                shutil.move(src, dst)
            else:
                _merge(src, dst)
            moved.append(os.path.basename(src))
        except Exception as ex:
            print("[paths] 옮기지 못했어요:", src, ex)
    if moved:
        print("[paths] 예전 자료를 옮겼어요:", ", ".join(moved))
    try:
        if os.path.isdir(old_data) and os.path.normcase(old_data) != os.path.normcase(APPDATA_DIR) \
           and not os.listdir(old_data):
            os.rmdir(old_data)
    except Exception:
        pass


def summary():
    """설정 화면에 보여 줄 지금 상태."""
    return {
        "name": user_name(),
        "unreachable": WORK_UNREACHABLE,      # 못 찾은 자리(USB 뺐을 때). 없으면 None
        "name_is_default": not str(read_work_meta().get("name") or "").strip(),
        "work_dir": WORK_ROOT,
        "app_dir": APPDATA_DIR,
        "default_work": default_work(),
        "portable": _portable(),
        "fixed_by_env": bool(os.environ.get("VAPI_WORK")),
    }


ensure()
migrate_old()
