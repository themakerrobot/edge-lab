# -*- coding: utf-8 -*-
"""모델 없이 서버를 띄우기 위한 가짜 엔진.

진짜 engines.py 에서 **표와 순수 계산**(COCO 이름, DIRECTION, direction_words)은
그대로 읽어 쓴다 — 스키마 검증이 목적이라 이 부분을
흉내 내면 시험이 무의미해진다. 추론하는 부분만 그럴듯한 값으로 대신한다.
"""
import ast
import base64
import os

import cv2
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ---- 진짜 표 읽어 오기 (import 하면 openvino 가 필요하므로 필요한 줄만 실행한다)
_ns = {}
for _node in ast.parse(open(os.path.join(ROOT, "engines.py"), encoding="utf-8").read()).body:
    if isinstance(_node, (ast.Assign, ast.FunctionDef)):
        try:
            exec(compile(ast.Module([_node], []), "engines", "exec"), _ns)
        except Exception:
            pass                                  # 모델을 건드리는 줄은 그냥 넘어간다

COCO_EN = _ns["COCO_EN"]
COCO_KO = _ns["COCO_KO"]
DIRECTION = _ns["DIRECTION"]
direction_words = _ns["direction_words"]

DEV_VLM, DEV_GAN, DEV_FACE = "GPU", "GPU", "NPU"
TOTAL_STEPS = 3
LOAD_STEPS = [("fake", "가짜 엔진", "fake engine")]
WARM_STEPS = []


class core:
    available_devices = ["CPU", "GPU", "NPU"]


def to_b64_jpg(img):
    return base64.b64encode(cv2.imencode(".jpg", img)[1]).decode("ascii")


class _Object:
    image_size = 640

    @staticmethod
    def _pos(cx, cy):
        p = "L" if cx < 300 else ("R" if cx > 500 else "C")
        return p + ("T" if cy < 300 else ("B" if cy > 500 else "C"))

    def search(self, path, lang="ko"):
        names = COCO_KO if str(lang).startswith("ko") else COCO_EN
        out = []
        for cls_id, box in ((0, [10, 20, 120, 200]), (56, [200, 150, 320, 300])):
            out.append({"name": names[cls_id], "name_en": COCO_EN[cls_id],
                        "score": 88, "percent": 88,
                        "pos": self._pos(100, 100), "box": box})
        return out

    def points(self, path):
        return [{"score": 90, "box": [10, 20, 120, 200],
                 "points": [(i, i) for i in range(17)]}]

    def segment(self, path, lang="ko"):
        names = COCO_KO if str(lang).startswith("ko") else COCO_EN
        return {"image": to_b64_jpg(cv2.imread(path)),
                "object": [{"name": names[56], "name_en": COCO_EN[56],
                            "score": 77, "box": [200, 150, 320, 300]}]}


class UserYolo:
    """가져온 모델 파일 — 진짜와 같은 규칙(폴더 안에서만 찾기)으로 흉내 낸다."""

    EXTS = (".pt", ".onnx")

    @staticmethod
    def folder():
        import paths as _p
        os.makedirs(_p.YOLO_DIR, exist_ok=True)
        return _p.YOLO_DIR

    @classmethod
    def files(cls):
        d = cls.folder()
        try:
            return sorted(n for n in os.listdir(d)
                          if n.lower().endswith(cls.EXTS)
                          or n.endswith("_openvino_model"))
        except Exception:
            return []

    def predict(self, name, path, conf=0.3):
        base = os.path.basename(str(name or "").strip())
        if not base:
            raise ValueError("모델 이름이 비었어요.")
        if base not in self.files():
            raise FileNotFoundError("모델 파일이 없어요: %s\n지금 있는 것: %s"
                                    % (base, ", ".join(self.files()) or "(아직 없어요)"))
        return [{"name": "cat", "name_en": "cat", "percent": 88,
                 "score": 88, "box": (5, 5, 60, 60)}]


class _Detect:
    def predict(self, image):
        return [{"box": [10, 20, 120, 140], "score": 95}]


class _AgeGender:
    def predict(self, crop):
        return 34, ("남성", "man")


class _Emotion:
    def predict(self, crop):
        return "행복한 표정", "happy"


class _HeadPose:
    def predict(self, crop, lang="ko"):
        return dict(direction_words("LT", lang), pitch=0.1, yaw=-0.2, roll=0.0)


class _Mask:
    def predict(self, crop, lang="ko"):
        return {"mask": 1, "name": "마스크 씀" if str(lang).startswith("ko") else "mask",
                "name_en": "mask", "score": 91.0}


class _Face:
    def __init__(self):
        self.detect = _Detect()
        self.age_gender = _AgeGender()
        self.emotion = _Emotion()
        self.head_pose = _HeadPose()
        self.mask = _Mask()


class _VLM:
    """프롬프트를 보고 그럴듯한 답을 만든다 — 진짜 파서를 그대로 태우기 위해서다.
    질문은 되돌려 준다(프롬프트가 서버까지 오는지 확인용)."""

    def generate(self, image, prompt, max_tokens):
        import json
        p = str(prompt)
        if "answer" in p:
            q = p.split("질문:")[-1].split("Question:")[-1].strip()
            return json.dumps({"answer": q or "(질문 없음)"}, ensure_ascii=False)
        if "caption" in p:
            return '{"caption": "남자가 방에 앉아 있어요"}'
        if "score" in p and "name" in p:
            return '[{"name": "실내", "score": 90}, {"name": "사람", "score": 70}]'
        if "Eyeglasses" in p:
            return '{"Eyeglasses": 80, "Mustache": 5, "Beard": 3, "Hat": 1}'
        return "이 사진에는 사람이 있어요."


    def generate_text(self, prompt, max_new_tokens=256):
        q = prompt.split("질문:")[-1].split("Question:")[-1].strip()
        return "그건 %s 에 대한 이야기예요." % (q or "무엇")


class _Gan:
    class _M:
        def predict(self, img):
            return img
    bgremove = _M()
    sr = _M()


class _Code:
    def ocr(self, path):
        return [([[10, 10], [90, 10], [90, 40], [10, 40]], "안녕", 0.93)]

    def barcode(self, path):
        return [{"box": [5, 5, 50, 50], "data": "https://themaker"}]


class _Embed:
    """가짜 임베딩 — 글자 빈도로 384차원을 만든다.

    진짜 뜻은 모르지만 **같은 글은 같은 벡터, 겹치는 낱말이 많으면 가까운 벡터**가
    되므로 저장·검색·정렬 경로를 그대로 시험할 수 있다."""

    DIM = 384

    def ready(self):
        return True

    def load(self):
        pass

    def encode(self, texts, kind="passage"):
        out = []
        for t in texts:
            v = np.zeros(self.DIM, np.float32)
            for ch in str(t):
                v[ord(ch) % self.DIM] += 1.0
            n = float(np.linalg.norm(v))
            out.append(v / n if n else v)
        return out


class Engines:
    def __init__(self, progress=None):
        if progress:
            progress("fake", 1)
        self.object = _Object()
        self.user = UserYolo()
        self.face = _Face()
        self.vlm = _VLM()
        self.gan = _Gan()
        self.code = _Code()
        self.embed = _Embed()
