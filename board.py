# -*- coding: utf-8 -*-
"""board — 보드(MCU)와 시리얼로 글자 한 줄씩 주고받는다.

포트는 서버가 연다. 블록(브라우저에서 돈다)과 파이썬(서버에서 돈다)이 같은 연결을 쓰려면
연결의 주인이 하나여야 해서다. 브라우저 Web Serial 은 쓰지 않는다.

펌웨어와의 약속은 "글자 한 줄 = 명령 하나"뿐이다. 명령에 답이 올 수도, 안 올 수도 있다.
그래서 세 가지만 한다.

    send(글)              보내기만 한다
    ask(글, 기다릴 초)     보내고, 그 뒤에 처음 들어오는 줄을 답으로 돌려준다 — 없으면 None
    read(after, 기다릴 초) 보드가 스스로 보낸 줄(센서 값 등)을 차례로 읽는다

명령 이름(LED 켜기 등)은 여기서 정하지 않는다 — 펌웨어가 정한다.

주의
  * ask 는 "보낸 뒤 처음 들어온 줄"을 답으로 본다. 보드가 센서 값을 계속 흘려보내는 중이면
    그 줄이 답으로 잡힐 수 있다. 펌웨어가 답 앞에 머리말(예: "OK", 명령 이름)을 붙이면
    prefix 로 골라 받을 수 있다.
  * 보낸 명령을 그대로 되돌려 보내는(echo) 펌웨어도 있다. 보낸 글과 똑같은 줄은 답으로 치지 않는다.
  * 줄 끝 없이 멈춘 글(예: "> " 같은 입력 안내)은 0.3초 동안 더 오는 게 없으면 한 줄로 친다.
  * 여는 순간 DTR/RTS 를 내려 둔다 — USB-UART 칩(CP210x·CH340) 보드는 이 두 선으로 리셋되기도 한다.
    ESP32-S3 의 내장 USB(USB-Serial-JTAG)에서 이것으로 리셋이 막히는지는 실기기 확인 필요.
"""
import collections
import threading
import time

try:
    import serial                      # pyserial
    import serial.tools.list_ports
except ImportError:                    # 설치가 빠져도 서버는 떠야 한다 — 보드 기능만 안내를 낸다
    serial = None

MAX_LOG = 2000        # 기억해 두는 줄 수 (보낸 것 · 받은 것 · 알림 모두)
MAX_WAIT = 10.0       # ask/read 가 기다리는 가장 긴 시간(초)
IDLE_FLUSH = 0.3      # 줄 끝 없이 멈춘 글을 한 줄로 치기까지(초)
BAUDS = (9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600)
EOLS = {"lf": "\n", "crlf": "\r\n", "cr": "\r", "none": ""}   # none: 명령 끝을 펌웨어가 정한 글자(예: "!")로 알아듣는 경우

# USB 칩 제조사(VID) → 보드 앱에서 보여 줄 짧은 설명. 확실한 것만 적는다.
VID_HINT = {
    0x303A: "Espressif (ESP32 내장 USB)",
    0x10C4: "Silicon Labs CP210x",
    0x1A86: "WCH CH340",
    0x0403: "FTDI",
    0x2E8A: "Raspberry Pi (RP2040)",
}


class BoardError(RuntimeError):
    pass


class Board:
    def __init__(self):
        self._ser = None
        self._reader = None
        self._stop = threading.Event()
        self._cv = threading.Condition()
        self._log = collections.deque(maxlen=MAX_LOG)
        self._seq = 0
        self._wlock = threading.Lock()
        self.port = ""
        self.baud = 115200
        self.eol = "lf"
        self.error = ""
        self.lost = False            # 쓰다가 끊겼는지 (케이블이 빠짐 등) — 사용자가 끊은 것과 구분

    # ── 기록 ──
    def _add(self, kind, text):
        with self._cv:
            self._seq += 1
            self._log.append({"seq": self._seq, "t": time.time(), "dir": kind, "text": text})
            self._cv.notify_all()
            return self._seq

    @property
    def connected(self):
        return self._ser is not None

    def status(self):
        return {"connected": self.connected, "port": self.port, "baud": self.baud, "eol": self.eol,
                "seq": self._seq, "error": self.error, "lost": self.lost, "pyserial": serial is not None}

    # ── 포트 ──
    @staticmethod
    def ports():
        if serial is None:
            raise BoardError("pyserial 이 설치되어 있지 않아요 (pip install pyserial).")
        out = []
        for p in serial.tools.list_ports.comports():
            out.append({"device": p.device, "description": p.description or "",
                        "vid": p.vid, "pid": p.pid, "hint": VID_HINT.get(p.vid or -1, "")})
        return sorted(out, key=lambda x: (not x["hint"], x["device"]))

    def connect(self, port, baud=115200, eol="lf"):
        if serial is None:
            raise BoardError("pyserial 이 설치되어 있지 않아요 (pip install pyserial).")
        port = str(port or "").strip()
        if not port:
            raise BoardError("포트를 골라 주세요.")
        baud = int(baud)
        if baud not in BAUDS:
            raise BoardError("속도는 %s 중에서 골라 주세요." % ", ".join(map(str, BAUDS)))
        if eol not in EOLS:
            raise BoardError("줄 끝은 lf · crlf · cr · none 중 하나예요.")
        self.disconnect(quiet=True)
        try:
            # serial_for_url: "COM3" 같은 포트 이름도, 시험용 "loop://" 도 연다
            ser = serial.serial_for_url(port, do_not_open=True, baudrate=baud, timeout=0.05, write_timeout=1.0)
            try:
                ser.dtr = False
                ser.rts = False
            except Exception:
                pass
            ser.open()
        except Exception as ex:
            self.error = "열 수 없어요: %s" % ex
            raise BoardError("%s 을(를) 열 수 없어요. 다른 프로그램(Arduino IDE 의 시리얼 모니터 등)이 "
                             "쓰고 있지 않은지 확인해 주세요. (%s)" % (port, ex))
        self._ser, self.port, self.baud, self.eol = ser, port, baud, eol
        self.error, self.lost = "", False
        self._stop.clear()
        self._reader = threading.Thread(target=self._read_loop, args=(ser,), daemon=True)
        self._reader.start()
        self._add("sys", "연결: %s · %d" % (port, baud))
        return self.status()

    def disconnect(self, quiet=False):
        ser, self._ser = self._ser, None
        self._stop.set()
        if ser is not None:
            try:
                ser.close()
            except Exception:
                pass
            if self._reader is not None and self._reader is not threading.current_thread():
                self._reader.join(timeout=1.0)
            if not quiet:
                self._add("sys", "연결 끊음")
        self._reader = None
        return self.status()

    # ── 받기 ──
    def _read_loop(self, ser):
        buf = b""
        last = time.time()
        while not self._stop.is_set():
            try:
                data = ser.read(ser.in_waiting or 1)
            except Exception as ex:                          # 케이블이 빠지면 여기로 온다
                if not self._stop.is_set():
                    self._lose(ser, ex)
                return
            now = time.time()
            if data:
                buf += data
                last = now
                while True:
                    i = min([k for k in (buf.find(b"\n"), buf.find(b"\r")) if k >= 0], default=-1)
                    if i < 0:
                        break
                    line, buf = buf[:i], buf[i + 1:]
                    if not line:                          # \r\n 사이의 빈 조각(과 빈 줄)은 버린다
                        continue
                    text = line.decode("utf-8", "replace").rstrip()   # 끝 공백은 뗀다 — "OK " 와 "OK" 가 달라지지 않게
                    if text:
                        self._add("rx", text)
            elif buf and now - last >= IDLE_FLUSH:
                text = buf.decode("utf-8", "replace").rstrip()
                buf = b""
                if text:
                    self._add("rx", text)

    def _lose(self, ser, ex):
        """쓰다가 끊겼다 — 사용자가 끊은 것과 달리 lost 로 표시해 셸이 알림을 띄운다."""
        if self._ser is not ser:
            return
        self.error, self.lost = "연결이 끊겼어요: %s" % ex, True
        self._ser = None
        self._stop.set()
        try:
            ser.close()
        except Exception:
            pass
        self._add("sys", "연결이 끊겼어요")

    # ── 보내기 ──
    def send(self, text):
        ser = self._ser
        if ser is None:
            raise BoardError("보드가 연결되어 있지 않아요. 보드 앱에서 먼저 연결해 주세요.")
        text = " ".join(str(text).splitlines()).strip()     # 한 번에 한 줄 — 줄바꿈은 명령을 둘로 나눈다
        if not text:
            raise BoardError("보낼 글이 없어요.")
        with self._wlock:
            try:
                ser.write((text + EOLS[self.eol]).encode("utf-8"))
                ser.flush()
            except Exception as ex:
                self._lose(ser, ex)
                raise BoardError("보내지 못했어요 — 보드 연결이 끊긴 것 같아요. (%s)" % ex)
        return self._add("tx", text)

    def _next_rx(self, after, timeout, prefix="", skip=None):
        """after 다음에 들어온 받은 줄 하나. timeout 안에 없으면 None."""
        end = time.time() + max(0.0, min(float(timeout), MAX_WAIT))
        with self._cv:
            while True:
                for e in self._log:
                    if e["seq"] <= after or e["dir"] != "rx":
                        continue
                    if skip is not None and e["text"].strip() == skip:
                        continue
                    if prefix and not e["text"].startswith(prefix):
                        continue
                    return e
                left = end - time.time()
                if left <= 0 or self._ser is None:
                    return None
                self._cv.wait(left)

    def ask(self, text, timeout=1.0, prefix=""):
        t0 = time.time()
        seq = self.send(text)
        e = self._next_rx(seq, timeout, prefix, skip=" ".join(str(text).splitlines()).strip())
        return {"reply": e["text"] if e else None, "seq": e["seq"] if e else seq,
                "ms": int((time.time() - t0) * 1000)}

    def read(self, after, timeout=1.0, prefix=""):
        after = self._seq if after is None or int(after) < 0 else int(after)
        e = self._next_rx(after, timeout, prefix)
        return {"line": e["text"] if e else None, "seq": e["seq"] if e else after}

    def lines(self, after=0, limit=500):
        with self._cv:
            out = [e for e in self._log if e["seq"] > int(after)]
        return {"lines": out[-limit:], "seq": self._seq}


BOARD = Board()
