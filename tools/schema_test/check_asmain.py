# -*- coding: utf-8 -*-
"""`python main.py` 로 띄운 상태(__main__)를 그대로 재현해 확인한다.

왜 따로 두나 — 다른 시험은 main 을 **모듈로 import** 해서 띄운다. 그러면
sys.modules["main"] 이 있어서, 라우터가 `import main` 으로 엔진을 찾아도 잘 된다.
그런데 실제 배포는 `python main.py` 라 그 파일이 **__main__** 으로 올라간다.
이때 `import main` 을 하면 main.py 가 통째로 다시 실행되고(통계·라우터가 두 벌),
그 사본의 eng 는 비어 있어서 "AI 준비가 끝나지 않았어요" 가 난다.
실제로 그렇게 터진 적이 있어 시험으로 남긴다.

    python tools\\schema_test\\check_asmain.py
"""
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
import urllib.request

PORT = int(os.environ.get("ASMAIN_TEST_PORT", "57798"))
HOST = "http://127.0.0.1:%d" % PORT

SERVER = '''
import os, sys
sys.path.insert(0, "tools/schema_test"); sys.path.insert(0, ".")
os.environ["VAPI_NO_BROWSER"] = "1"
os.environ["VAPI_PORT"] = "%d"
import fake_engines
class _Echo:
    def generate(self, bgr, prompt, max_new_tokens=128): return '{"answer":"ok"}'
    def generate_text(self, prompt, max_new_tokens=256): return "ok"
fake_engines._VLM = _Echo
sys.modules["engines"] = fake_engines
import runpy
runpy.run_path("main.py", run_name="__main__")
''' % PORT


def _form(path, fields):
    b = "----asmain"
    body = b"".join(('--%s\r\nContent-Disposition: form-data; name="%s"\r\n\r\n%s\r\n'
                     % (b, k, v)).encode() for k, v in fields.items())
    body += ("--%s--\r\n" % b).encode()
    req = urllib.request.Request(HOST + path, data=body,
                                 headers={"Content-Type":
                                          "multipart/form-data; boundary=" + b})
    return json.loads(urllib.request.urlopen(req, timeout=30).read().decode())


def _post(path, params):
    req = urllib.request.Request(HOST + path + "?" + urllib.parse.urlencode(params),
                                 data=b"", method="POST")
    return json.loads(urllib.request.urlopen(req, timeout=30).read().decode())


def run():
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    os.chdir(root)
    tmp = os.path.join(tempfile.gettempdir(), "vapi_asmain_server.py")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(SERVER)

    # -u : 자식의 출력을 버퍼에 담아 두지 않고 바로 내보낸다.
    #      윈도우의 terminate() 는 프로세스를 즉시 죽여서(TerminateProcess) 버퍼가
    #      비워지지 않는다 — 버퍼링을 두면 로그가 통째로 사라진다.
    env = dict(os.environ, PYTHONUNBUFFERED="1", PYTHONIOENCODING="utf-8")
    proc = subprocess.Popen([sys.executable, "-u", tmp], cwd=root, text=True, env=env,
                            encoding="utf-8", errors="replace",
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    # 죽인 뒤에 읽으면 늦다(윈도우에서 파이프가 이미 끊긴다) — 도는 동안 모아 둔다.
    lines = []
    reader = threading.Thread(target=lambda: [lines.append(x) for x in proc.stdout],
                              daemon=True)
    reader.start()
    ok = fail = 0
    try:
        for _ in range(80):
            try:
                with urllib.request.urlopen(HOST + "/ready", timeout=1) as r:
                    if json.loads(r.read().decode()).get("ready"):
                        break
            except Exception:
                time.sleep(0.5)
        else:
            print("  FAIL  서버가 뜨지 않음")
            return 0, 1

        cases = [
            ("자료 만들기", lambda: _form("/chat/db", {
                "title": "asmain시험",
                "text": ("무지개는 빛이 물방울에 꺾여서 생겨요. 비가 온 뒤 해가 나면 "
                         "하늘에 반원으로 보여요. 일곱 빛깔이에요.\n\n"
                         "달은 지구를 도는 위성이에요. 한 달에 한 번 모양이 바뀌어요.")})),
            ("자료에서 답하기", lambda: _post("/chat/rag",
                                        {"db": "asmain시험", "prompt": "무지개는 왜 생겨?"})),
            ("사진 없이 묻기", lambda: _post("/chat/ask", {"prompt": "안녕?"})),
        ]
        for label, call in cases:
            try:
                d = call()
                assert d.get("result") == "ok", d.get("data")
                print("  PASS  %-16s" % label); ok += 1
            except Exception as ex:
                print("  FAIL  %-16s %s" % (label, str(ex)[:70])); fail += 1
        try:
            urllib.request.urlopen(urllib.request.Request(
                HOST + "/chat/db/" + urllib.parse.quote("asmain시험"), method="DELETE")).read()
        except Exception:
            pass
    finally:
        # 여기까지 찍힌 것이 "서버가 도는 동안의 로그" 다. 죽이면서 나는 잡음은
        # 아래 Traceback 검사에서 세면 안 되므로, 죽이기 전에 먼저 잘라 둔다.
        time.sleep(0.3)                      # 마지막 줄이 도착할 틈을 준다
        log = "".join(lines)
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()
        reader.join(timeout=2)

    # 로그를 아예 못 읽은 것과 "두 번 실행됨" 은 완전히 다른 문제다.
    # 둘 다 0 으로 나와서 헷갈린 적이 있어 따로 알려 준다.
    if not log.strip():
        print("  FAIL  서버 로그를 읽지 못함 (아래 세 가지를 판정할 수 없음)")
        return ok, fail + 1

    # main.py 가 두 번 실행되면 시작 안내가 두 줄씩 찍힌다
    for label, needle in (("main.py 한 번만 실행", "[stats] usage tracking"),
                          ("서버 한 번만 기동", "listening on")):
        n = log.count(needle)
        if n == 1:
            print("  PASS  %-16s" % label); ok += 1
        else:
            print("  FAIL  %-16s %d 번 (1 이어야 함)" % (label, n)); fail += 1
    if "Traceback" in log:
        print("  FAIL  서버 로그에 오류 흔적"); fail += 1
        for ln in log.splitlines():
            if "Error" in ln or "Traceback" in ln:
                print("        | " + ln.strip()[:90])
    else:
        print("  PASS  서버 로그 깨끗함"); ok += 1
    return ok, fail


if __name__ == "__main__":
    o, f = run()
    print("\n결과: %d PASS / %d FAIL" % (o, f))
    sys.exit(1 if f else 0)
