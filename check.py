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

print("done. fail =", fails)
