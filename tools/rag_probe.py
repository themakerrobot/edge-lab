# -*- coding: utf-8 -*-
r"""RAG 근본 진단 — 서버를 거치지 않고 진짜 모델에 직접 물어 어디가 문제인지 가른다.

    venv\Scripts\python tools\rag_probe.py "우리 반 규칙은 뭐지?"
    venv\Scripts\python tools\rag_probe.py "질문" 자료이름

하는 일:
  1. data/db 의 자료를 읽어 점수 순으로 조각을 보여 준다  (검색이 문제인가?)
  2. 모델에게 세 가지 프롬프트를 그대로 던져 원문 그대로 답을 보여 준다
       [A] 지금 서비스가 쓰는 프롬프트 (p_rag)
       [B] 빠져나갈 문구가 없는 프롬프트 (p_rag_force)
       [C] 자료 없이 그냥 질문 (p_chat)                    (모델이 문제인가?)
  3. 프롬프트 전문도 찍는다                                  (내용이 문제인가?)

서버 상태와 무관하게 디스크의 prompts.py 최신본으로 시험한다 — 서버가 옛
코드를 물고 있으면 여기 결과와 화면 결과가 다르게 나오고, 그러면 원인은
코드가 아니라 "서버 재시작 안 함"이다.
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

import paths  # noqa: E402
import prompts as P  # noqa: E402


def main():
    question = sys.argv[1] if len(sys.argv) > 1 else "우리 반 규칙은 뭐지?"
    files = sorted(Path(paths.DB_DIR).glob("*.json"))
    if not files:
        print("data/db 에 자료가 없어요 — 대화 페이지에서 먼저 자료를 만드세요.")
        return 1
    if len(sys.argv) > 2:
        pick = [f for f in files if sys.argv[2] in f.stem]
        if not pick:
            print("그 이름의 자료가 없어요. 있는 것:", ", ".join(f.stem for f in files))
            return 1
        path = pick[0]
    else:
        path = files[0]
    db = json.loads(path.read_text(encoding="utf-8"))
    print("자료:", path.stem, "—", len(db["chunks"]), "조각")

    # ---- 1) 검색 ----------------------------------------------------------
    import engines
    import db_routes                          # 저장 형식 해석은 서비스 코드 그대로 쓴다
    emb = engines.Embed()
    q = np.asarray(emb.encode([question], kind="query")[0], np.float32)
    vecs = db_routes._unb64(db["vectors"], db.get("dim", 384))
    score = vecs @ q
    order = np.argsort(-score)[:4]
    print("\n== 1. 검색 (질문: %s)" % question)
    for i in order:
        print("  %.3f  %s" % (score[i], db["chunks"][i][:56].replace("\n", " ")))
    hits = [db["chunks"][i] for i in order]
    context = "\n".join("(%d) %s" % (n + 1, t) for n, t in enumerate(hits))

    # ---- 2) 모델 ----------------------------------------------------------
    print("\n[모델 올리는 중 — 30초쯤 걸립니다]")
    vlm = engines.VlmEngine()
    lg = P.lang_of(question, "ko")
    trials = [
        ("A. 서비스 프롬프트(p_rag)", P.p_rag(question, context, lg)),
        ("B. 강제 프롬프트(p_rag_force)", P.p_rag_force(question, context, lg)),
        ("C. 자료 없이(p_chat)", P.p_chat(question, lg)),
    ]
    for name, prompt in trials:
        t0 = time.perf_counter()
        out = vlm.generate_text(prompt, P.MAX_TOKENS["chat"])
        ms = (time.perf_counter() - t0) * 1000
        print("\n== 2. %s  (%.0fms)" % (name, ms))
        print("  답 원문: %r" % out)

    print("\n== 3. A 프롬프트 전문")
    print(trials[0][1])
    print("\n해석:")
    print("  - 1의 1등 점수가 낮다(0.6 아래) -> 검색·임베딩 문제")
    print("  - A 가 '찾지 못했어요'인데 B 는 제대로 답함 -> 프롬프트 조건 문구에 쏠린 것")
    print("  - A 도 B 도 이상함 -> 모델·파이프라인 문제 (원문을 그대로 알려 주세요)")
    print("  - 여기선 다 정상인데 화면만 이상함 -> 서버가 옛 코드 (run.bat 재시작)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
