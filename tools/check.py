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

print("done. fail =", fails)
