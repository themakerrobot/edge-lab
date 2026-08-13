# -*- coding: utf-8 -*-
"""sysinfo — 이 컴퓨터 상태(메모리·CPU 사용률).

바깥 패키지 없이 운영체제가 주는 값만 쓴다(psutil 불필요) — 교실 PC 마다 설치
상태가 달라도 같게 동작해야 하기 때문. 화면 오른쪽 위 상태 판과 수업 전 점검이
같은 값을 쓰도록 여기 한 곳에 둔다(양쪽에 베껴 두면 나중에 한쪽만 고쳐진다).
"""
import os

_CPU_PREV = {}


def _cpu_percent():
    """CPU 사용률 — 어느 윈도우 PC에서나 되는 방법만 쓴다(psutil·성능 카운터 없이).
    윈도우는 GetSystemTimes, 리눅스는 /proc/stat 을 두 번 읽어 그 차이로 구한다.
    GPU·NPU 사용률은 넣지 않는다 — 드라이버·모델마다 성능 카운터가 있기도 없기도 해서
    어떤 PC에서는 빈칸이 되고, 그게 "고장 났나?"로 읽힌다. 대신 칩 점멸로 보여 준다."""
    try:
        if os.name == "nt":
            import ctypes
            from ctypes import wintypes
            idle, kern, user = wintypes.FILETIME(), wintypes.FILETIME(), wintypes.FILETIME()
            ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kern),
                                                  ctypes.byref(user))
            def q(ft):
                return (ft.dwHighDateTime << 32) | ft.dwLowDateTime
            idle_t, total_t = q(idle), q(kern) + q(user)   # kern 에 idle 이 포함돼 있다
        else:
            parts = open("/proc/stat").readline().split()[1:]
            nums = [int(x) for x in parts]
            idle_t, total_t = nums[3] + nums[4], sum(nums)
        prev_i, prev_t = _CPU_PREV.get("idle"), _CPU_PREV.get("total")
        _CPU_PREV["idle"], _CPU_PREV["total"] = idle_t, total_t
        if prev_t is None or total_t <= prev_t:
            return None                                   # 첫 호출은 견줄 값이 없다
        busy = (total_t - prev_t) - (idle_t - prev_i)
        return max(0, min(100, int(busy * 100 / (total_t - prev_t))))
    except Exception:
        return None


def _mem_info():
    """메모리 사용률 — psutil 없이. 윈도우는 ctypes, 리눅스는 /proc/meminfo."""
    try:
        if os.name == "nt":
            import ctypes
            class MEM(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
            m = MEM(); m.dwLength = ctypes.sizeof(MEM)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
            total, avail = m.ullTotalPhys, m.ullAvailPhys
        else:
            info = {}
            for line in open("/proc/meminfo"):
                k, v = line.split(":", 1)
                info[k] = int(v.strip().split()[0]) * 1024
            total, avail = info["MemTotal"], info.get("MemAvailable", info["MemFree"])
        used = total - avail
        return {"total_gb": round(total / 2**30, 1), "used_gb": round(used / 2**30, 1),
                "percent": int(used * 100 / total)}
    except Exception:
        return None
