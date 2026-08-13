# -*- coding: utf-8 -*-
"""folderpick — 폴더 고르기 창.

바깥 것을 아무것도 안 쓴다. PowerShell 도, .NET 컴파일도, 별도 패키지도 필요 없다.
윈도우가 원래 갖고 있는 창(IFileOpenDialog)을 ctypes 로 직접 부른다 — 파일 업로드 때
보는 그 큰 탐색기형 창이고, 거기에 "폴더를 고른다" 옵션(FOS_PICKFOLDERS)만 준 것이다.

전에는 PowerShell 로 C# 을 그 자리에서 컴파일해 불렀는데, 그러면 PowerShell 실행 정책,
.NET 컴파일러, 백신, 임시 폴더 권한 중 하나만 막혀도 창이 안 뜬다. 교실 PC 마다 다른
그 조건들을 없애려고 파이썬만으로 옮겼다.

세 단계로 물러선다:
  1) 윈도우 기본 창 (ctypes)
  2) tkinter 폴더 창 — 윈도우 외 OS 이거나 1 이 막힌 경우
  3) 실패를 알린다 — 화면은 경로를 직접 적는 방식으로 넘어간다

창은 STA 스레드에서 띄워야 해서 전용 스레드에서 돌린다(서버 스레드의 COM 상태를
건드리지 않기 위해서이기도 하다).
"""
import ctypes
import os
import threading
from ctypes import POINTER, byref, c_int, c_uint, c_void_p, c_wchar_p


class _GUID(ctypes.Structure):
    _fields_ = [("Data1", ctypes.c_ulong), ("Data2", ctypes.c_ushort),
                ("Data3", ctypes.c_ushort), ("Data4", ctypes.c_ubyte * 8)]

    def __init__(self, text):
        super().__init__()
        ctypes.oledll.ole32.CLSIDFromString(c_wchar_p(text), byref(self))


# 윈도우가 정한 값들 — 바꾸면 안 된다
CLSID_FileOpenDialog = "{DC1C5A9C-E88A-4DDE-A5A1-60F82A20AEF7}"
IID_IFileOpenDialog = "{D57C7288-D4AD-4768-BE02-9D969532D960}"

FOS_PICKFOLDERS = 0x00000020        # 파일이 아니라 폴더를 고른다
FOS_FORCEFILESYSTEM = 0x00000040    # 실제 폴더만 (라이브러리·가상 폴더 제외)
FOS_PATHMUSTEXIST = 0x00000800
SIGDN_FILESYSPATH = 0x80058000      # 결과를 진짜 경로 문자열로

CLSCTX_INPROC_SERVER = 1
COINIT_APARTMENTTHREADED = 2

# 함수 자리(vtable) 번호. IUnknown 3개가 앞에 오고 그 뒤로 순서대로다.
# 번호가 하나만 어긋나도 엉뚱한 함수가 불려 조용히 잘못 동작하므로 표로 남긴다.
V_SHOW = 3          # IModalWindow::Show
V_SETOPTIONS = 9    # IFileDialog::SetOptions
V_GETOPTIONS = 10
V_SETTITLE = 17
V_SETOKLABEL = 18
V_GETRESULT = 20
V_ITEM_GETNAME = 5  # IShellItem::GetDisplayName


def _call(obj, index, restype, *argtypes):
    """COM 객체의 index 번째 함수를 부를 수 있는 파이썬 함수로 만들어 준다."""
    vtable = ctypes.cast(obj, POINTER(POINTER(c_void_p))).contents
    proto = ctypes.WINFUNCTYPE(restype, c_void_p, *argtypes)
    return proto(vtable[index])


FOS_FILEMUSTEXIST = 0x00001000
V_SETFOLDER = 12          # IFileDialog::SetFolder
V_SETFILETYPES = 4


def _shell_item(path):
    """경로를 창이 알아듣는 형태로 — 창을 그 폴더에서 열기 위해서."""
    item = c_void_p()
    ctypes.oledll.shell32.SHCreateItemFromParsingName(
        c_wchar_p(path), None, byref(_GUID("{43826D1E-E718-42EE-BC55-A1E261C37BFE}")),
        byref(item))
    return item


def _pick_windows_file(title, start_dir):
    """파일 고르기 창. 폴더 고르기와 같은 창이고 옵션만 다르다."""
    ole32 = ctypes.oledll.ole32
    ole32.CoInitializeEx(None, COINIT_APARTMENTTHREADED)
    dlg = c_void_p()
    try:
        ole32.CoCreateInstance(byref(_GUID(CLSID_FileOpenDialog)), None,
                               CLSCTX_INPROC_SERVER,
                               byref(_GUID(IID_IFileOpenDialog)), byref(dlg))
        opts = c_uint()
        _call(dlg, V_GETOPTIONS, ctypes.HRESULT, POINTER(c_uint))(dlg, byref(opts))
        _call(dlg, V_SETOPTIONS, ctypes.HRESULT, c_uint)(
            dlg, opts.value | FOS_FORCEFILESYSTEM | FOS_FILEMUSTEXIST)
        if title:
            _call(dlg, V_SETTITLE, ctypes.HRESULT, c_wchar_p)(dlg, title)

        # 그 폴더에서 열리게 — 아이가 폴더를 찾아 헤매지 않도록
        if start_dir and os.path.isdir(start_dir):
            try:
                item = _shell_item(start_dir)
                _call(dlg, V_SETFOLDER, ctypes.HRESULT, c_void_p)(dlg, item)
                _call(item, 2, ctypes.c_ulong)(item)
            except Exception:
                pass

        owner = ctypes.windll.user32.GetForegroundWindow()
        show = ctypes.WINFUNCTYPE(c_int, c_void_p, c_void_p)(
            ctypes.cast(dlg, POINTER(POINTER(c_void_p))).contents[V_SHOW])
        if show(dlg, owner) != 0:
            return ""                                   # 취소
        item = c_void_p()
        _call(dlg, V_GETRESULT, ctypes.HRESULT, POINTER(c_void_p))(dlg, byref(item))
        try:
            name = c_wchar_p()
            _call(item, V_ITEM_GETNAME, ctypes.HRESULT, c_uint, POINTER(c_wchar_p))(
                item, SIGDN_FILESYSPATH, byref(name))
            path = name.value or ""
            ctypes.windll.ole32.CoTaskMemFree(name)
            return path
        finally:
            _call(item, 2, ctypes.c_ulong)(item)
    finally:
        if dlg:
            _call(dlg, 2, ctypes.c_ulong)(dlg)
        ole32.CoUninitialize()


def _pick_tk_file(title, start_dir):
    import tkinter
    from tkinter import filedialog
    root = tkinter.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        return filedialog.askopenfilename(title=title, initialdir=start_dir or None) or ""
    finally:
        root.destroy()


def choose_file(title="파일을 고르세요", start_dir=""):
    """파일 하나를 고르게 하고 경로를 돌려준다 — choose() 와 같은 규약."""
    box = {}

    def run():
        if os.name == "nt":
            try:
                box["path"] = _pick_windows_file(title, start_dir)
                box["how"] = "windows"
                return
            except Exception as ex:
                box["why1"] = "%s: %s" % (type(ex).__name__, ex)
        try:
            box["path"] = _pick_tk_file(title, start_dir)
            box["how"] = "tk"
        except Exception as ex:
            box["why2"] = "%s: %s" % (type(ex).__name__, ex)

    t = threading.Thread(target=run, daemon=True)
    t.start()
    t.join(600)
    if "path" in box:
        return box["path"], box.get("how", ""), ""
    why = " / ".join(x for x in (box.get("why1"), box.get("why2")) if x)
    return "", "", why or "창이 응답하지 않았어요"


def _pick_windows(title):
    ole32 = ctypes.oledll.ole32
    ole32.CoInitializeEx(None, COINIT_APARTMENTTHREADED)
    dlg = c_void_p()
    try:
        ole32.CoCreateInstance(byref(_GUID(CLSID_FileOpenDialog)), None,
                               CLSCTX_INPROC_SERVER,
                               byref(_GUID(IID_IFileOpenDialog)), byref(dlg))

        opts = c_uint()
        _call(dlg, V_GETOPTIONS, ctypes.HRESULT, POINTER(c_uint))(dlg, byref(opts))
        _call(dlg, V_SETOPTIONS, ctypes.HRESULT, c_uint)(
            dlg, opts.value | FOS_PICKFOLDERS | FOS_FORCEFILESYSTEM | FOS_PATHMUSTEXIST)

        if title:
            _call(dlg, V_SETTITLE, ctypes.HRESULT, c_wchar_p)(dlg, title)
        _call(dlg, V_SETOKLABEL, ctypes.HRESULT, c_wchar_p)(dlg, "이 폴더 쓰기")

        # 지금 맨 앞에 있는 창(브라우저)의 자식으로 띄운다.
        # 부모 없이 띄우면 활성 창이 아니라서 흐리게 보이고 뒤로 숨는다.
        owner = ctypes.windll.user32.GetForegroundWindow()
        show = ctypes.WINFUNCTYPE(c_int, c_void_p, c_void_p)(
            ctypes.cast(dlg, POINTER(POINTER(c_void_p))).contents[V_SHOW])
        hr = show(dlg, owner)
        if hr != 0:
            return ""                                  # 취소(HRESULT 가 0 이 아님)

        item = c_void_p()
        _call(dlg, V_GETRESULT, ctypes.HRESULT, POINTER(c_void_p))(dlg, byref(item))
        try:
            name = c_wchar_p()
            _call(item, V_ITEM_GETNAME, ctypes.HRESULT, c_uint, POINTER(c_wchar_p))(
                item, SIGDN_FILESYSPATH, byref(name))
            path = name.value or ""
            ctypes.windll.ole32.CoTaskMemFree(name)
            return path
        finally:
            _call(item, 2, ctypes.c_ulong)(item)        # IUnknown::Release
    finally:
        if dlg:
            _call(dlg, 2, ctypes.c_ulong)(dlg)          # IUnknown::Release
        ole32.CoUninitialize()


def _pick_tk(title):
    """윈도우가 아니거나 위가 막힌 경우. 파이썬에 딸려 오는 tkinter 를 쓴다."""
    import tkinter
    from tkinter import filedialog
    root = tkinter.Tk()
    root.withdraw()
    root.attributes("-topmost", True)                   # 뒤에 숨지 않게
    try:
        return filedialog.askdirectory(title=title, mustexist=False) or ""
    finally:
        root.destroy()


def choose(title="작업 폴더를 고르세요"):
    """폴더를 고르게 하고 경로를 돌려준다.

    돌려주는 값: (경로, 어떻게 띄웠는지, 실패 이유)
      경로가 "" 이고 이유가 "" 이면 사용자가 취소한 것이다.
    """
    box = {}

    def run():
        if os.name == "nt":
            try:
                box["path"] = _pick_windows(title)
                box["how"] = "windows"
                return
            except Exception as ex:
                box["why1"] = "%s: %s" % (type(ex).__name__, ex)
        try:
            box["path"] = _pick_tk(title)
            box["how"] = "tk"
        except Exception as ex:
            box["why2"] = "%s: %s" % (type(ex).__name__, ex)

    t = threading.Thread(target=run, daemon=True)        # 창은 전용 스레드에서
    t.start()
    t.join(600)                                          # 10분이면 충분히 기다린 것

    if "path" in box:
        return box["path"], box.get("how", ""), ""
    why = " / ".join(x for x in (box.get("why1"), box.get("why2")) if x)
    return "", "", why or "창이 응답하지 않았어요"
