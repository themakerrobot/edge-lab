# -*- coding: utf-8 -*-
"""lab — 코딩 실습: JupyterLab 을 이 PC 에서 띄우고 Chrome/Edge 전용 창으로 연다. 창을 닫으면 JupyterLab 도 끈다.

    python lab.py [노트북 폴더]        (보통은 lab.bat / lab.sh 를 실행)

- 노트북: 프로그램 폴더의 notebooks/ 는 원본(교재)이다. 켤 때 작업폴더(paths.NOTEBOOK_DIR,
  기본 문서/Edge Lab/notebooks)에 맞춰 넣고, 학습자는 그 폴더에서 작업한다 (sync_notebooks):
  없는 것은 복사, 안 고친 것은 바뀐 원본으로 바꾸고, 고친 것은 그대로 두고 새 원본을 "(새 버전)" 으로 옆에 둔다.
  원본으로 되돌리려면 그 노트북을 지우고 다시 켠다.
- 노트북에 알려 주는 환경변수: EDGE_ROOT(프로그램 폴더), EDGE_MODELS(프로그램 폴더의 models/).
- 주소는 127.0.0.1 만 연다(같은 교실 망의 다른 PC 에서 못 들어온다). 토큰은 켤 때마다 새로 만든다.
- 끌 때는 JupyterLab 에 "끄기" 를 요청한다(/api/shutdown) — 커널까지 정리되어 NPU·GPU 메모리가 남지 않는다.
- 배포 번들(python/ + pylib/)에서는 JupyterLab 의 화면 파일이 pylib/share/jupyter 에 깔린다.
  sys.prefix 가 python/ 이라 그대로 두면 "application assets not found" 로 빈 화면이 된다 — 경로를 알려 준다.
- 브라우저를 직접 고르려면 환경변수 LAB_BROWSER 에 chrome / msedge 실행 파일 경로를 넣는다.
- 윈도우 · 우분투 둘 다 돈다.
"""
import os
import sys
import time
import shutil
import socket
import secrets
import subprocess
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
HOST = "127.0.0.1"

# Chrome / Edge 후보 — 주소창 없는 전용 창(--app)으로 띄운다 (appwin.py 와 같은 순서)
WIN_BROWSERS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]
LINUX_BROWSERS = ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "microsoft-edge"]


def find_browser():
    want = os.environ.get("LAB_BROWSER", "")
    if want and os.path.exists(want):
        return want
    if os.name == "nt":
        for p in WIN_BROWSERS:
            if os.path.exists(p):
                return p
        return None
    for name in LINUX_BROWSERS:
        p = shutil.which(name)
        if p:
            return p
    return None


def work_folders():
    """(노트북 작업폴더, 창 프로필 폴더) — paths.py 의 규칙을 따른다."""
    try:
        sys.path.insert(0, str(ROOT))
        import paths
        return Path(paths.NOTEBOOK_DIR), Path(paths.LABWIN_DIR)
    except Exception as ex:                       # paths 를 못 읽어도 실습은 되게
        print("[lab] 작업폴더 규칙(paths.py)을 읽지 못해 프로그램 폴더 옆을 씁니다:", ex)
        return ROOT / "notebooks-work", ROOT / ".labwin"


MANIFEST = ".originals.json"       # 작업폴더에 둔다 — 노트북마다 "마지막으로 넣어 준 원본" 의 지문(sha256)


def _sha(path):
    import hashlib
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sync_notebooks(src, dst):
    """원본(교재) 노트북을 작업폴더에 맞춘다. 돌려주는 값: (새로 넣음, 새 버전으로 바꿈, 옆에 새 버전을 둠)

    - 작업폴더에 없으면 복사한다.
    - 있고, 학습자가 안 고쳤으면(지난번에 넣어 준 원본과 같으면) 바뀐 원본으로 바꾼다.
    - 학습자가 고쳤으면(셀을 실행해 결과가 저장된 것도 고친 것이다) 지우지 않고,
      새 원본을 "이름 (새 버전).ipynb" 로 옆에 한 번만 넣는다.
    지문 기록이 없는 노트북(이 기능 전에 복사된 것)은 원본과 다르면 고친 것으로 본다 — 지우지 않는 쪽이 안전하다.
    """
    import json
    added = updated = side = 0
    if not src.is_dir():
        return added, updated, side
    man_path = dst / MANIFEST
    try:
        man = json.loads(man_path.read_text(encoding="utf-8"))
    except Exception:
        man = {}
    for f in sorted(src.rglob("*")):
        if f.is_dir() or ".ipynb_checkpoints" in f.parts:
            continue
        rel = f.relative_to(src).as_posix()
        to = dst / rel
        new = _sha(f)
        to.parent.mkdir(parents=True, exist_ok=True)
        if not to.exists():
            shutil.copy2(f, to)
            added += 1
        else:
            have = _sha(to)
            if have != new:
                if man.get(rel) == have:                       # 안 고친 옛 원본 → 새 원본으로
                    shutil.copy2(f, to)
                    updated += 1
                elif man.get(rel) != new:                      # 고친 것 → 새 원본은 옆에 (한 번만)
                    shutil.copy2(f, to.with_name(f"{to.stem} (새 버전){to.suffix}"))
                    side += 1
        man[rel] = new
    try:
        man_path.write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
    except Exception as ex:
        print("[lab] 원본 기록을 쓰지 못했어요:", ex)
    return added, updated, side


def free_port(start=8888):
    for port in range(start, start + 20):
        with socket.socket() as s:
            if s.connect_ex((HOST, port)) != 0:
                return port
    raise SystemExit("[lab] 8888~8907 포트가 모두 쓰이고 있어요")


def wait_port(port, server, timeout=120):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if server.poll() is not None:            # JupyterLab 이 켜지다 멈췄다 — 위의 오류를 본다
            return False
        with socket.socket() as s:
            if s.connect_ex((HOST, port)) == 0:
                return True
        time.sleep(0.3)
    return False


def shutdown(server, port, token):
    """JupyterLab 에 끄기를 요청하고, 10초 안에 안 꺼지면 강제로 끈다."""
    if server.poll() is not None:
        return
    try:
        req = urllib.request.Request(f"http://{HOST}:{port}/api/shutdown", method="POST",
                                     headers={"Authorization": f"token {token}"})
        urllib.request.urlopen(req, timeout=5).close()
    except Exception:
        pass
    try:
        server.wait(timeout=10)
    except subprocess.TimeoutExpired:
        server.kill()


def lab_env():
    env = dict(os.environ)
    env["EDGE_ROOT"] = str(ROOT)
    if (ROOT / "models").is_dir():
        env.setdefault("EDGE_MODELS", str(ROOT / "models"))
    share = ROOT / "pylib" / "share" / "jupyter"             # 배포 번들
    if (share / "lab").is_dir():
        env.setdefault("JUPYTERLAB_DIR", str(share / "lab"))
        env["JUPYTER_PATH"] = os.pathsep.join(p for p in (str(share), env.get("JUPYTER_PATH", "")) if p)
    return env


def main():
    try:
        import jupyterlab  # noqa: F401
    except ImportError:
        print("[lab] JupyterLab 이 설치돼 있지 않아요.")
        print(f'      "{sys.executable}" -m pip install -r requirements.lock.txt')
        return 1

    nb, prof = work_folders()
    if len(sys.argv) > 1:
        nb = Path(sys.argv[1]).resolve()
    nb.mkdir(parents=True, exist_ok=True)
    added, updated, side = sync_notebooks(ROOT / "notebooks", nb)
    if added:
        print(f"[lab] 새 노트북 {added}개를 작업폴더에 넣었어요.")
    if updated:
        print(f"[lab] 교재가 바뀐 노트북 {updated}개를 새 버전으로 바꿨어요.")
    if side:
        print(f"[lab] 고친 노트북 {side}개는 그대로 두고, 새 버전을 '(새 버전)' 이름으로 옆에 넣었어요.")

    port, token = free_port(), secrets.token_hex(16)
    cmd = [sys.executable, "-m", "jupyterlab", "--no-browser",
           f"--ServerApp.ip={HOST}", f"--ServerApp.port={port}", "--ServerApp.port_retries=0",
           f"--IdentityProvider.token={token}", f"--ServerApp.root_dir={nb}"]
    if hasattr(os, "geteuid") and os.geteuid() == 0:   # 리눅스에서 root 로 돌릴 때만(윈도우에는 없다)
        cmd.append("--allow-root")
    print(f"[lab] JupyterLab 을 켜는 중 ... (노트북 폴더: {nb})")
    server = subprocess.Popen(cmd, env=lab_env())
    try:
        if not wait_port(port, server):
            print("[lab] JupyterLab 이 켜지지 않았어요 — 위의 메시지를 확인하세요.")
            shutdown(server, port, token)
            return 1

        url = f"http://{HOST}:{port}/lab?token={token}"
        exe = find_browser()
        if exe:
            t0 = time.time()
            win = subprocess.Popen([exe, f"--app={url}", f"--user-data-dir={prof}", "--window-size=1400,900",
                                    "--no-first-run", "--no-default-browser-check"])
            print("[lab] 창을 닫으면 JupyterLab 도 꺼져요.")
            win.wait()
            # 같은 전용 프로필 창이 이미 떠 있으면 새 브라우저 프로세스는 그 창에 일을 넘기고 바로 끝난다 —
            # 그때는 창 닫힘을 알 수 없으니 이 창(까만 창 · 터미널)에서 끝낸다
            if time.time() - t0 < 5:
                print("[lab] 이미 열린 창에 넘겼어요. 끝내려면 이 창에서 Ctrl+C 를 누르세요.")
                server.wait()
        else:
            print(f"[lab] Chrome/Edge 를 못 찾아 기본 브라우저로 엽니다: {url}")
            print("[lab] 끝내려면 이 창에서 Ctrl+C 를 누르세요.")
            webbrowser.open(url)
            server.wait()
    except KeyboardInterrupt:
        pass
    finally:
        print("[lab] JupyterLab 을 끄는 중 ...")
        shutdown(server, port, token)
    return 0


if __name__ == "__main__":
    sys.exit(main())
