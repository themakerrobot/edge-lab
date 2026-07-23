# -*- coding: utf-8 -*-
# OCR 격리 테스트: python test_ocr.py  (서버와 동일한 조건으로 easyocr만 실행)
import traceback

import cv2
import numpy as np

img = np.full((200, 600, 3), 255, np.uint8)
cv2.putText(img, "HELLO 123", (30, 120), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 0), 4)
cv2.imwrite("ocr_test.jpg", img)

import easyocr

print("reader init...")
reader = easyocr.Reader(["ko", "en"], gpu=False,
                        model_storage_directory="models/code/easyocr",
                        user_network_directory="models/code/easyocr",
                        download_enabled=False, verbose=False)
print("readtext...")
try:
    out = reader.readtext("ocr_test.jpg")
    print("OK:", out)
except Exception:
    traceback.print_exc()