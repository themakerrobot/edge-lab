# -*- coding: utf-8 -*-
"""보드(MCU) 시리얼 — /board/*. 연결은 board.BOARD 하나가 쥔다.

  GET  /board/ports                       연결된 USB 시리얼 포트 목록
  GET  /board/status                      연결 상태 · 마지막 번호(seq)
  POST /board/connect  {port, baud, eol}  열기 (eol: lf · crlf · cr)
  POST /board/disconnect                  닫기
  POST /board/send     {text}             한 줄 보내기
  POST /board/ask      {text, timeout, prefix}   보내고 답 한 줄 기다리기 — 없으면 reply: null
  POST /board/read     {after, timeout, prefix}  after 다음에 받은 줄 하나 (after 가 -1 이면 지금부터)
  GET  /board/lines?after=N               주고받은 기록 (보드 앱의 화면)

AI 를 쓰지 않으므로 모델을 올리는 동안에도 된다(main.py 의 ALLOW_WHILE_LOADING).
ask·read 는 기다리는 동안 스레드 하나를 쓴다 — 그래서 async 가 아닌 def 로 둔다(FastAPI 가 스레드 풀에서 돌린다).
"""
from fastapi import APIRouter, Body

from board import BOARD, BoardError

router = APIRouter()


def _ok(data):
    return {"result": "ok", "data": data}


def _fail(msg):
    return {"result": "fail", "data": str(msg)}


@router.get("/board/ports", tags=["board"], summary="시리얼 포트 목록")
def board_ports():
    try:
        return _ok(BOARD.ports())
    except BoardError as ex:
        return _fail(ex)


@router.get("/board/status", tags=["board"], summary="보드 연결 상태")
def board_status():
    return _ok(BOARD.status())


@router.post("/board/connect", tags=["board"], summary="보드 연결")
def board_connect(port: str = Body(..., embed=True), baud: int = Body(115200, embed=True),
                  eol: str = Body("lf", embed=True)):
    try:
        return _ok(BOARD.connect(port, baud, eol))
    except BoardError as ex:
        return _fail(ex)


@router.post("/board/disconnect", tags=["board"], summary="보드 연결 끊기")
def board_disconnect():
    return _ok(BOARD.disconnect())


@router.post("/board/send", tags=["board"], summary="한 줄 보내기")
def board_send(text: str = Body(..., embed=True)):
    try:
        return _ok({"seq": BOARD.send(text)})
    except BoardError as ex:
        return _fail(ex)


@router.post("/board/ask", tags=["board"], summary="보내고 답 한 줄 받기 (없으면 null)")
def board_ask(text: str = Body(..., embed=True), timeout: float = Body(1.0, embed=True),
              prefix: str = Body("", embed=True)):
    try:
        return _ok(BOARD.ask(text, timeout, prefix))
    except BoardError as ex:
        return _fail(ex)


@router.post("/board/read", tags=["board"], summary="받은 줄 하나 읽기")
def board_read(after: int = Body(-1, embed=True), timeout: float = Body(1.0, embed=True),
               prefix: str = Body("", embed=True)):
    if not BOARD.connected:
        return _fail("보드가 연결되어 있지 않아요. 보드 앱에서 먼저 연결해 주세요.")
    return _ok(BOARD.read(after, timeout, prefix))


@router.get("/board/lines", tags=["board"], summary="주고받은 기록")
def board_lines(after: int = 0):
    return _ok(BOARD.lines(after))
