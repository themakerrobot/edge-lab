import os
import pathlib
import sys
import openvino as ov
import openvino_tokenizers  # registers tokenizer custom ops (required for vlm xml)

core = ov.Core()
print("devices:", core.available_devices)

targets = list(pathlib.Path("models").rglob("*.xml")) + \
          list(pathlib.Path("models").glob("gan/*.onnx")) + \
          list(pathlib.Path("models").glob("mask/*.onnx"))

# 있는 파일만 열어 보면 "모델이 통째로 빠진" 경우를 놓친다(그때도 fail=0).
# 서버가 반드시 읽는 것들은 이름을 적어 두고 존재부터 확인한다.
# YOLO 계열은 폴더째 넘긴다(안의 xml 이름은 ultralytics 가 정한다) — 폴더에
# xml 이 하나라도 있으면 정상으로 본다. 이름을 박아 두면 내보내기 방식이
# 바뀔 때마다 헛되이 FAIL 이 난다.
NEED_DIRS = []

NEED = [
    "face/face-detection-retail-0005.xml",
    "face/age-gender-recognition-retail-0013.xml",
    "face/emotions-recognition-retail-0003.xml",
    "face/head-pose-estimation-adas-0001.xml",
    "face/face-reidentification-retail-0095.xml",   # 얼굴 구분(얼굴 AI · 파이보와 같은 파일)
    "gan/u2net.onnx",
    "gan/single-image-super-resolution-1032.xml",
    "gan/depth-v2s.xml",          # 깊이 지도 (상대 깊이 — 보여 주는 용도)
    "mask/mask.onnx",                  # 마스크 분류 (임베더 + 분류기가 한 파일 — 아래에서 연다)
    "mediapipe/face_landmarker.task",  # 얼굴 거리·방향
    "mediapipe/gesture_recognizer.task",  # 손동작
]

# 코딩 실습(노트북)이 쓰는 모델 — 위 NEED 에 없는 것만. 없으면 그 노트북이 첫 칸에서 멈춘다
# (tools/release_check.py 가 노트북을 읽어 여기 · 00_start 점검 목록과 맞는지 본다)
NB_NEED = [
    "backbone/mobilenetv2_feat.xml",                    # 07 내 분류기 (예전 가르치기 모델도 이것을 쓴다)
    "code/easyocr/craft_mlt_25k.pth",                   # 05 글자 찾기
    "code/easyocr/korean_g2.pth",                       # 05 글자 읽기
    "embed/e5-small-int8/openvino_model.xml",           # 08 (대화 자료 찾기와 같은 파일)
    "embed/e5-small-int8/openvino_tokenizer.xml",
    "vlm/gemma3-4b-int4/openvino_language_model.xml",   # 08 · 09
]

fails = 0
for rel in NEED_DIRS:
    d = pathlib.Path("models") / rel
    if not d.is_dir():
        fails += 1
        print("FAIL models/" + rel, "| 폴더 없음")
    elif not list(d.glob("*.xml")):
        fails += 1
        print("FAIL models/" + rel, "| 폴더 안에 .xml 이 없음")

for rel in NEED:
    if not (pathlib.Path("models") / rel).exists():
        fails += 1
        print("FAIL models/" + rel, "| 파일 없음")

for rel in NB_NEED:
    if not (pathlib.Path("models") / rel).exists():
        fails += 1
        print("FAIL models/" + rel, "| 파일 없음 — 코딩 실습 노트북이 씁니다")

for m in targets:
    size = m.stat().st_size
    try:
        core.read_model(m)
    except Exception as e:
        fails += 1
        print("FAIL", m, f"({size} bytes)", "|", str(e)[:200])

# 얼굴 구분(retail-0095) — 파이보와 같은 파일이어야 명단(facedb.json)을 주고받는다. 모양까지 본다
_reid = pathlib.Path("models/face/face-reidentification-retail-0095.xml")
if _reid.exists():
    try:
        _m = core.read_model(_reid)
        _ins, _out = list(_m.inputs[0].get_partial_shape()), _m.outputs[0].get_partial_shape()
        _n = 1
        for _d in _out:
            _n *= _d.get_length()
        # 출력 모양은 [1, 256, 1, 1] — 값이 256 개면 된다 (engines.FaceReid 가 한 줄로 편다)
        if [d.get_length() for d in _ins] != [1, 3, 128, 128] or _n != 256:
            fails += 1
            print("FAIL", _reid, "| 입력 1x3x128x128 · 출력 256 이 아님 — 다른 모델 파일", _ins, _out)
    except Exception as e:
        fails += 1
        print("FAIL", _reid, "|", str(e)[:200])

# 사물 찾기 · 자세 · 영역 — easydetect .onnx. 없으면 그 기능이 안 된다. 열리는지도 본다
for rel in ["easydetect/ed-m/ed-m.onnx", "easydetect/pose/pose-m.onnx",
            "easydetect/mobile_sam/encoder.onnx", "easydetect/mobile_sam/decoder.onnx"]:
    f = pathlib.Path("models") / rel
    if not f.exists():
        fails += 1
        print("FAIL models/" + rel, "| 파일 없음 (setup 을 다시 돌려 주세요)")
        continue
    try:
        core.read_model(f)
    except Exception as e:
        fails += 1
        print("FAIL models/" + rel, "|", str(e)[:200])

# 가르치기 특징 — models/mediapipe (train_features.py 가 읽는다). 임베더는 OpenVINO 로 열리는지까지 본다
for rel in ["mediapipe/mobilenet_v3_small_embedder.onnx", "mediapipe/hand_landmarker.task",
            "mediapipe/face_landmarker.task", "mediapipe/pose_landmarker_lite.task"]:
    f = pathlib.Path("models") / rel
    if not f.exists():
        fails += 1
        print("FAIL models/" + rel, "| 파일 없음 — 가르치기를 쓸 수 없습니다. tools\\fetch_models.py 로 받으세요")
        continue
    if f.suffix == ".onnx":
        try:
            core.read_model(f)
        except Exception as e:
            fails += 1
            print("FAIL models/" + rel, "|", str(e)[:200])

# 읽어 주기(Supertonic int8)는 OpenVINO 로 읽는 모델이 아니라 파일이 다 있는지만 본다
tts_need = ["duration_predictor.onnx", "text_encoder.onnx", "vector_estimator.onnx",
            "vocoder.onnx", "tts.json", "unicode_indexer.json"]
q = pathlib.Path("models/tts-int8")
qd = q / "onnx" if (q / "onnx" / "vector_estimator.onnx").exists() else q
for name in tts_need:
    if not (qd / name).exists():
        fails += 1
        print("FAIL", (qd / name).as_posix(), "| 파일 없음 — 읽어 주기(TTS)를 쓸 수 없습니다")
vs = list((q / "voice_styles").glob("*.json"))
if len(vs) < 10:
    fails += 1
    print("FAIL models/tts-int8/voice_styles | 목소리 파일이", len(vs), "개 (10개 기대)")
if (qd / "vocoder.onnx").exists() and len(vs) >= 10:
    print("OK   읽어 주기는 models/tts-int8 을 씁니다")

sv = pathlib.Path("models/stt-sv")
sv_miss = [n for n in ("model.int8.onnx", "tokens.txt", "silero_vad.onnx") if not (sv / n).is_file()]
if not sv_miss:
    print("OK   음성 인식은 models/stt-sv (SenseVoice) 를 씁니다")
    try:
        import sherpa_onnx  # noqa: F401
    except Exception as ex:
        fails += 1
        print("FAIL sherpa-onnx | 불러오지 못함:", ex)
else:
    fails += 1
    print("FAIL models/stt-sv 에", ", ".join(sv_miss), "없음 — 음성 인식(STT)을 쓸 수 없습니다. tools\\fetch_models.py 로 받으세요")

# opencv 는 세 벌(python·contrib·headless)이 서로 다른 패키지의 의존성으로 함께 깔리고
# 같은 cv2 를 덮어쓴다. headless 가 이기면 창을 못 띄워 파이썬 show(window=True) 가 죽는다.
# 배포 번들은 venv 를 통째로 굳혀 나가므로 무관하고, 여기서 clone 후 새로 설치한 PC 만 걸린다.
# 리눅스에서 화면(DISPLAY)이 없으면 창을 열다 Qt 가 프로그램째 멈춰 버리므로(예외가 아니다) 이 점검만 건너뛴다.
if sys.platform.startswith("linux") and not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
    print("SKIP opencv GUI | 화면이 없는 곳에서 실행 — 바탕화면에서 다시 돌리면 점검합니다")
else:
    try:
        import cv2
        cv2.namedWindow("_check")
        cv2.destroyAllWindows()
    except Exception as e:
        fails += 1
        print("FAIL opencv GUI |", str(e)[:120])
        print("     고침: pip install --force-reinstall opencv-python  (GUI 있는 것을 마지막에 덮어쓴다)")

# 코딩 실습(lab.bat → JupyterLab) — 없으면 실습만 못 하고 서버는 그대로 돈다
try:
    import jupyterlab
    import ipykernel  # noqa: F401  (노트북 실행기)
    print("OK   jupyterlab", jupyterlab.__version__)
except Exception as e:
    fails += 1
    print("FAIL jupyterlab |", str(e)[:120])
    print("     고침: pip install -r requirements.lock.txt  (코딩 실습 lab.bat 에 필요)")

# 가져온 모델 중 easydetect(easydetect-lab 에서 학습한 .onnx) — 없으면 그 모델만 못 쓴다
try:
    import easydetect
    print("OK   easydetect", easydetect.__version__)
except Exception as e:
    fails += 1
    print("FAIL easydetect |", str(e)[:120])
    print("     고침: pip install -r requirements.lock.txt  (easydetect-lab 모델을 쓰려면 필요)")

print("done. fail =", fails)
