"""깊이 모델(depth-v2s) 점검 — 서버를 띄우지 않고 모델만 직접 확인한다.

engines.Depth 를 그대로 불러 쓰므로, 여기서 통과하면 /gan/depth 도 돈다.
확인하는 것은 셋이다.

  1) 모델이 열리는가            — 파일·IR 버전·장치
  2) 입력 크기를 제대로 읽었는가 — 고정([1,3,518,518])인지 동적(-1)인지
  3) 값의 방향이 맞는가          — 가까울수록 값이 큰가

3번이 핵심이다. Depth Anything 계열은 보통 "가까울수록 큰 값(inverse depth)"
이지만 변환 방식에 따라 뒤집혀 나올 수 있고, 뒤집히면 화면에서 먼 곳이 밝게
보인다. 사람 눈으로 판단하기 어려우니 여기서 숫자로 가른다.

쓰는 법 (프로젝트 뿌리에서):
    venv\\Scripts\\python tools\\depth_check.py
    venv\\Scripts\\python tools\\depth_check.py 사진.jpg     # 내 사진으로

사진을 주지 않으면 시험용 그림을 만들어 쓴다 — 아래쪽이 가깝고(바닥),
위쪽이 먼(하늘) 실내 장면을 흉내 낸 것이다.
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)          # engines.MODELS 가 상대경로("models")라 뿌리에서 돌아야 한다

import cv2
import numpy as np


def make_test_image():
    """바닥이 가깝고 위가 먼 장면을 흉내 낸 그림.

    아래쪽에 큰 상자를 두어 '가까운 물체'를 만든다. 원근 단서가 있어야
    모델이 방향을 제대로 내놓는지 볼 수 있다.
    """
    h, w = 480, 640
    img = np.zeros((h, w, 3), np.uint8)
    # 위쪽(먼 곳)은 밝은 회색, 아래로 갈수록 어두운 바닥
    for y in range(h):
        v = int(210 - 110 * (y / h))
        img[y, :] = (v, v, v)
    # 아래 가운데에 가까운 상자
    cv2.rectangle(img, (w // 2 - 110, h - 210), (w // 2 + 110, h - 20), (40, 90, 190), -1)
    cv2.rectangle(img, (w // 2 - 110, h - 210), (w // 2 + 110, h - 20), (20, 40, 90), 3)
    # 멀리 있는 작은 상자
    cv2.rectangle(img, (70, 150), (150, 215), (150, 150, 150), -1)
    return img


def main():
    print("=" * 60)
    print("  깊이 모델 점검")
    print("=" * 60)

    # ---- 1) 모델 파일 ----
    # engines 를 올리면 openvino 와 다른 모델까지 딸려 와 느리다.
    # 파일이 없으면 거기까지 갈 필요가 없으므로 경로만 먼저 본다.
    # (engines.MODELS 는 상대경로 "models" — 위에서 뿌리로 chdir 해 두었다.
    #  paths 에는 MODELS_DIR 이라는 다른 이름만 있다.)
    from pathlib import Path
    xml = Path("models") / "gan" / "depth-v2s.xml"
    binf = Path("models") / "gan" / "depth-v2s.bin"
    print("\n[1] 모델 파일")
    for p in (xml, binf):
        if p.exists():
            print("    있음  %s  (%.1f MB)" % (p.name, p.stat().st_size / 1e6))
        else:
            print("    없음! %s" % p)
            print("\n    → hf download leeyunjai/edge-lab --local-dir models "
                  "--include \"gan/depth-v2s.*\"")
            return 1

    # ---- 2) 엔진 올리기 ----
    print("\n[2] 모델 올리기  (openvino 를 불러오느라 조금 걸려요)")
    import engines as E
    try:
        eng = E.Depth(E.DEV_GAN)
    except Exception as ex:
        print("    실패: %s: %s" % (type(ex).__name__, ex))
        print("    → 장치를 CPU 로 바꿔 다시 해 봅니다")
        try:
            eng = E.Depth("CPU")
        except Exception as ex2:
            print("    CPU 로도 실패: %s" % ex2)
            return 1
        print("    CPU 로는 올라감 — GPU 드라이버 문제일 수 있습니다")
    print("    장치      : %s" % E.DEV_GAN)
    print("    넣는 크기 : %d x %d  (고정. DINOv2 패치가 14 라 14 의 배수여야 함)"
          % (eng.SIDE, eng.SIDE))
    # 이 IR 은 입력이 동적이라 .shape 를 만지면 openvino 가 죽는다.
    # 크기를 물어볼 필요 자체가 없어서 partial_shape 만 참고로 찍는다.
    try:
        print("    모델 입력 : %s" % eng.compiled.inputs[0].partial_shape)
    except Exception as ex:
        print("    모델 입력 : 읽지 못함 (%s)" % ex)

    # ---- 3) 추론 ----
    if len(sys.argv) > 1:
        img = cv2.imread(sys.argv[1])
        if img is None:
            print("\n사진을 못 읽었어요: %s" % sys.argv[1])
            return 1
        src = sys.argv[1]
    else:
        img = make_test_image()
        src = "(시험용 그림)"

    print("\n[3] 추론 — %s  %dx%d" % (src, img.shape[1], img.shape[0]))
    import time
    t0 = time.perf_counter()
    d = eng.raw(img)
    ms = (time.perf_counter() - t0) * 1000
    print("    걸린 시간 : %.0f ms" % ms)
    print("    결과 크기 : %s  (원본과 같아야 함: %s)"
          % (d.shape, img.shape[:2]))
    print("    값 범위   : %.3f ~ %.3f" % (float(d.min()), float(d.max())))

    if d.shape != img.shape[:2]:
        print("    크기가 다릅니다 — raw() 의 resize 를 확인하세요")
        return 1
    if not np.isfinite(d).all():
        print("    NaN/Inf 가 있습니다 — 모델 변환을 의심하세요")
        return 1

    # ---- 4) 방향 판정 ----
    print("\n[4] 방향 — 가까울수록 값이 큰가?")
    h, w = d.shape
    bottom = float(np.median(d[int(h * 0.75):, :]))       # 바닥 = 가까움
    top = float(np.median(d[: int(h * 0.25), :]))          # 위 = 멂
    print("    아래쪽(가까움) 중앙값 : %.3f" % bottom)
    print("    위쪽(멂)      중앙값 : %.3f" % top)

    # 문서(INSTALL.md 「깊이 모델 다시 만들기」)에 "값이 클수록 가깝다" 고 적혀 있다.
    # 여기서는 그 전제가 실제로 맞는지를 사진으로 확인한다.
    if abs(bottom - top) < 1e-4:
        print("    두 값이 거의 같습니다 — 사진에 원근 단서가 없을 수 있어요.")
        print("    실제 방 사진으로 다시 해 보세요:  python tools/depth_check.py 사진.jpg")
        verdict = None
    elif bottom > top:
        print("    OK — 가까운 쪽이 큽니다. colorize() 그대로 두면 됩니다.")
        verdict = True
    else:
        print("    뒤집혔습니다 — 먼 쪽이 큽니다.")
        print("    → engines.py 의 Depth.colorize() 에서 near 를 뒤집으세요:")
        print("        near = 1.0 - (m - m.min()) / (m.max() - m.min() + 1e-8)")
        verdict = False

    # ---- 5) 눈으로 보기 ----
    out = eng.colorize(d)
    side = np.hstack([cv2.resize(img, (w, h)), out])
    path = os.path.abspath("depth_check.jpg")
    cv2.imwrite(path, side)
    print("\n[5] 결과 그림 : %s" % path)
    print("    왼쪽이 원본, 오른쪽이 깊이입니다.")
    print("    가까운 것이 밝게(노랑·하양) 나오면 맞습니다.")

    print("\n" + "=" * 60)
    if verdict is False:
        print("  방향을 뒤집어야 합니다 (위 [4] 참고)")
        return 1
    print("  점검 끝 — 그림을 눈으로도 확인해 주세요")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
