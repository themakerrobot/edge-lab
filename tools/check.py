import pathlib
import openvino as ov
import openvino_tokenizers  # registers tokenizer custom ops (required for vlm xml)

core = ov.Core()
print("devices:", core.available_devices)

targets = list(pathlib.Path("models").rglob("*.xml")) + \
          list(pathlib.Path("models").glob("gan/*.onnx"))

fails = 0
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
