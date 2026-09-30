# -*- coding: utf-8 -*-
"""읽어 주기(TTS) 모델 두 벌의 속도를 이 PC 에서 잰다 — models/tts (원래) vs models/tts-int8.

    venv\\Scripts\\python tools\\tts_bench.py
    venv\\Scripts\\python tools\\tts_bench.py tts tts-int8 --steps 8

같은 문장을 각 모델로 여러 번 합성해 문장당 걸린 시간과 RTF(합성 시간 ÷ 소리 길이, 작을수록 빠름)를 찍고,
귀로 비교하도록 bench-<모델>-<n>.wav 를 앱데이터 tmp 폴더에 남긴다. 첫 번은 준비(워밍업)라 빼고 잰다.
"""
import argparse
import os
import sys
import time
import wave

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import speech_routes as SR   # noqa: E402
import paths                 # noqa: E402

SENTS = [("ko", "안녕하세요. 오늘은 인공지능에게 소리를 가르쳐 볼 거예요."),
         ("ko", "고양이가 창가에서 졸고 있어요. 햇살이 따뜻해서 기분이 좋아요."),
         ("ko", "천이백삼십사만 오천"),
         ("en", "The robot can see my face and read my words aloud.")]


def save(path, wav, sr):
    pcm = (np.clip(wav, -1, 1) * 32767).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes(pcm.tobytes())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("models", nargs="*", default=["tts", "tts-int8"])
    ap.add_argument("--steps", type=int, default=8)
    ap.add_argument("--repeat", type=int, default=3)
    ap.add_argument("--voice", default="F1")
    a = ap.parse_args()
    out_dir = paths.TMP_DIR
    os.makedirs(out_dir, exist_ok=True)
    rows = []
    for name in a.models:
        root = os.path.join(ROOT, "models", name)
        if not os.path.isdir(root):
            print("[skip] models/%s 없음" % name)
            continue
        t0 = time.perf_counter()
        tts = SR._Supertonic(root)
        load_s = time.perf_counter() - t0
        tts.say("준비", lang="ko", voice=a.voice, steps=a.steps)          # 워밍업
        spent = audio = 0.0
        for i, (lang, text) in enumerate(SENTS):
            for r in range(a.repeat):
                t0 = time.perf_counter()
                wav = tts.say(text, lang=lang, voice=a.voice, steps=a.steps)
                spent += time.perf_counter() - t0
                audio += len(wav) / tts.sr
            save(os.path.join(out_dir, "bench-%s-%d.wav" % (name, i + 1)), wav, tts.sr)
        n = len(SENTS) * a.repeat
        rows.append((name, load_s, spent / n * 1000, spent / max(audio, 1e-6)))
        print("%-10s 여는 데 %.1fs · 문장당 %.0f ms · RTF %.3f" % rows[-1])
    if len(rows) == 2:
        print("\n%s 가 %s 보다 %.2f배 빠름 (문장당 시간 기준)" % (rows[1][0], rows[0][0], rows[0][2] / rows[1][2]))
    print("귀로 비교할 소리:", out_dir)


if __name__ == "__main__":
    main()
