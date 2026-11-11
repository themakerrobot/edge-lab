# -*- coding: utf-8 -*-
"""모델 파일 읽기 — 경로를 C++ 런타임에 넘기지 않는다."""

from __future__ import annotations

from pathlib import Path


def read_model(path: Path) -> bytes:
    """모델 파일을 바이트로 읽는다.

    경로 문자열을 C++ 런타임에 그대로 넘기지 않기 위해서다. 윈도우에서
    `C:\\Users\\...\\바탕 화면\\...` 처럼 한글이 든 경로는 넘기는 순간 깨져서
    "Could not open ... The model allocation is null/empty" 가 난다.
    파이썬의 open() 은 유니코드 경로를 제대로 다룬다.

    OneDrive 처럼 "요청 시 다운로드" 로 비워 둔 파일도 여기서 실제로 받아 온다.
    """
    if not path.exists():
        raise FileNotFoundError(f"모델 파일을 찾지 못했어요: {path}")
    data = path.read_bytes()
    if not data:
        raise ValueError(
            f"모델 파일이 비어 있어요: {path}\n"
            "OneDrive·구글 드라이브의 '요청 시 다운로드' 상태일 수 있어요. "
            "파일을 오른쪽 클릭해 '이 장치에 항상 유지' 로 바꾼 뒤 다시 해 보세요."
        )
    return data
