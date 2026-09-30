# -*- coding: utf-8 -*-
"""appwin — 앱 창(Chrome/Edge 전용 창, 기본은 키오스크)을 띄운다.

main.py 의 open_browser 가 서버가 대답할 수 있게 된 뒤 바탕화면("/")으로 바로 띄운다.
켜는 화면·준비 화면을 거치지 않는다 — 화면이 바뀔 때마다 깜빡였다. 모델 준비는 바탕화면 상단바가 보여 준다.

환경변수
  VAPI_NO_BROWSER=1   창을 띄우지 않는다
  VAPI_NO_APPMODE=1   전용 창 대신 기본 브라우저로 연다 (그때는 서버가 뜬 뒤에 연다)
  VAPI_NO_KIOSK=1     키오스크(전체 화면) 대신 보통 창
  VAPI_ZOOM=1.25      화면 배율
"""
import os
import subprocess

from paths import APPWIN_DIR

# Chrome / Edge 후보 경로 — 주소창·탭이 없는 전용 창으로 떠서 프로그램처럼 보인다.
BROWSERS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]

PROC = None        # 앱 창 프로세스 — [끄기] 때 같이 닫는다


def find():
    if os.environ.get("VAPI_NO_APPMODE"):
        return None
    for p in BROWSERS:
        if p and os.path.exists(p):
            return p
    return None


def launch(url):
    """전용 창을 띄운다. 띄웠으면 True — 브라우저가 없으면 False (호출한 쪽이 기본 브라우저로 연다)."""
    global PROC
    if PROC is not None and PROC.poll() is None:
        return True                              # 이미 떠 있다
    exe = find()
    if not exe:
        return False
    # 지난번에 띄운 창이 남아 있으면(까만 창만 닫았을 때 등) 새 창이 그 위에 겹쳐 뜬다 — 먼저 닫는다
    _kill_profile()
    # 전용 프로필을 쓰면 이미 열려 있는 브라우저 창과 섞이지 않는다.
    args = [exe, "--app=" + url, "--user-data-dir=" + APPWIN_DIR,
            "--window-size=1400,900", "--no-first-run", "--no-default-browser-check"]
    zoom = os.environ.get("VAPI_ZOOM", "").strip()
    if zoom:
        args.append("--force-device-scale-factor=" + zoom)
    # 키오스크(기본): 주소줄·창 틀 없이 화면 전체. 셸의 [끄기] 가 빠져나가는 길이다.
    # Chrome 은 --kiosk. Edge 의 --kiosk 는 InPrivate 로 돌아(Microsoft 문서의 키오스크 모드)
    # 끌 때 localStorage(언어·블록 임시 저장·바탕화면 설정)가 지워질 수 있어서,
    # Edge 에서는 --start-fullscreen 으로 대신한다 (F11 로 빠져나갈 수 있다). 둘 다 실기기 확인 필요.
    if not os.environ.get("VAPI_NO_KIOSK"):
        edge = os.path.basename(exe).lower() == "msedge.exe"
        args.append("--start-fullscreen" if edge else "--kiosk")
    # [끄기] 가 창을 강제로 닫으므로 다음 실행 때 "복원할까요" 풍선이 뜨지 않게
    args.append("--hide-crash-restore-bubble")
    try:
        PROC = subprocess.Popen(args)
    except Exception as ex:
        print("[browser] 앱 창 실패:", ex)
        return False
    print("[browser] 앱 창으로 실행:", os.path.basename(exe))
    return True


def _kill_profile():
    """우리 프로필(APPWIN_DIR)로 뜬 Chrome/Edge 를 전부 닫는다 (윈도우). 다른 브라우저 창은 건드리지 않는다."""
    if os.name != "nt":
        return
    flags = 0x08000000                         # CREATE_NO_WINDOW — 까만 창이 번쩍이지 않게
    prof = APPWIN_DIR.replace("'", "''").replace("[", "`[").replace("]", "`]")
    # 큰따옴표를 쓰지 않는다 — 명령줄로 넘길 때 따옴표 이스케이프가 꼬이지 않게
    ps = ("Get-CimInstance Win32_Process | "
          "Where-Object { ($_.Name -eq 'chrome.exe' -or $_.Name -eq 'msedge.exe') -and $_.CommandLine -like '*%s*' } | "
          "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" % prof)
    try:
        subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
                       capture_output=True, timeout=15, creationflags=flags)
    except Exception as ex:
        print("[browser] 앱 창 닫기 실패:", ex)


def close():
    """[끄기] 때 앱 창을 닫는다.

    띄운 프로세스(PROC)만 끝내면 안 닫힐 때가 있다: 같은 프로필로 이미 떠 있는 창이 있으면 새로 띄운
    chrome.exe 는 그 창에 일을 넘기고 바로 끝나 버린다. 그래서 윈도우에서는 프로필로 찾아 닫는다."""
    p = PROC
    if os.name == "nt":
        if p is not None and p.poll() is None:
            subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True, creationflags=0x08000000)
        _kill_profile()
    elif p is not None and p.poll() is None:
        try:
            p.terminate()
        except Exception:
            pass
