import pathlib
import openvino as ov
import openvino_tokenizers  # registers tokenizer custom ops (required for vlm xml)

core = ov.Core()
print("devices:", core.available_devices)

targets = list(pathlib.Path("models").rglob("*.xml")) + \
          list(pathlib.Path("models").glob("gan/*.onnx"))

# 있는 파일만 열어 보면 "모델이 통째로 빠진" 경우를 놓친다(그때도 fail=0).
# 서버가 반드시 읽는 것들은 이름을 적어 두고 존재부터 확인한다.
# YOLO 계열은 폴더째 넘긴다(안의 xml 이름은 ultralytics 가 정한다) — 폴더에
# xml 이 하나라도 있으면 정상으로 본다. 이름을 박아 두면 내보내기 방식이
# 바뀔 때마다 헛되이 FAIL 이 난다.
NEED_DIRS = [
    "object/yolo11m_openvino_model",
    "object/yolo11m-pose_openvino_model",
    "object/yolo11m-seg_openvino_model",
    "object/mask-11s-cls_openvino_model",
]

NEED = [
    "face/face-detection-retail-0005.xml",
    "face/age-gender-recognition-retail-0013.xml",
    "face/emotions-recognition-retail-0003.xml",
    "face/head-pose-estimation-adas-0001.xml",
    "gan/u2net.onnx",
    "gan/single-image-super-resolution-1032.xml",
    "gan/depth-v2s.xml",          # 깊이 지도 (상대 깊이 — 보여 주는 용도)
    "backbone/mobilenetv2_feat.xml",   # 가르치기 — 이게 없으면 학습 자체가 안 된다
    "mediapipe/face_landmarker.task",  # 얼굴 거리·방향
    "mediapipe/gesture_recognizer.task",  # 손동작
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

for m in targets:
    size = m.stat().st_size
    try:
        core.read_model(m)
    except Exception as e:
        fails += 1
        print("FAIL", m, f"({size} bytes)", "|", str(e)[:200])

# TTS(Supertonic)는 OpenVINO 로 읽는 모델이 아니라 파일 존재만 확인한다
tts_need = ["duration_predictor.onnx", "text_encoder.onnx", "vector_estimator.onnx",
            "vocoder.onnx", "tts.json", "unicode_indexer.json"]
tts_dir = pathlib.Path("models/tts/onnx")
if tts_dir.is_dir():
    for name in tts_need:
        if not (tts_dir / name).exists():
            fails += 1
            print("FAIL models/tts/onnx/" + name, "| 파일 없음")
    styles = list(pathlib.Path("models/tts/voice_styles").glob("*.json"))
    if len(styles) < 10:
        print("WARN 목소리 파일이", len(styles), "개 (10개 기대)")
else:
    print("WARN models/tts 없음 — 음성 합성(TTS)을 쓸 수 없습니다")

if not pathlib.Path("models/stt").is_dir():
    print("WARN models/stt 없음 — 음성 인식(STT)을 쓸 수 없습니다")

# opencv 는 세 벌(python·contrib·headless)이 서로 다른 패키지의 의존성으로 함께 깔리고
# 같은 cv2 를 덮어쓴다. headless 가 이기면 창을 못 띄워 파이썬 show(window=True) 가 죽는다.
# 배포 번들은 venv 를 통째로 굳혀 나가므로 무관하고, 여기서 clone 후 새로 설치한 PC 만 걸린다.
try:
    import cv2
    cv2.namedWindow("_check")
    cv2.destroyAllWindows()
except Exception as e:
    fails += 1
    print("FAIL opencv GUI |", str(e)[:120])
    print("     고침: pip install --force-reinstall opencv-python  (GUI 있는 것을 마지막에 덮어쓴다)")

print("done. fail =", fails)
