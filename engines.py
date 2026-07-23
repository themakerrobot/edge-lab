# -*- coding: utf-8 -*-
# vapi-od : on-device inference engines (Intel Meteor Lake / OpenVINO)
# 디바이스 배정: VLM/YOLO/gan=GPU, 얼굴 스위트=NPU(없으면 GPU→CPU), ocr/qr=CPU
import base64
import threading
from math import cos, sin, pi
from pathlib import Path

import cv2
import numpy as np
import openvino as ov

MODELS = Path("models")
core = ov.Core()


def pick(*prefer):
    avail = core.available_devices
    for d in prefer:
        if d in avail:
            return d
    return "CPU"

DEV_FACE = pick("NPU", "GPU")
DEV_GAN = pick("GPU")
DEV_VLM = pick("GPU")


def _out(req, *names):
    """이름 후보로 출력 텐서 찾기 (모델별 명칭 차이 방어)."""
    for n in names:
        try:
            return req.get_tensor(n).data
        except Exception:
            continue
    return None


def to_b64_jpg(bgr):
    ok, buf = cv2.imencode(".jpg", bgr, [cv2.IMWRITE_JPEG_QUALITY, 92])
    return base64.b64encode(buf).decode()


# ---------------------------------------------------------------- YOLO 계열
class Yolo:
    """ultralytics + OpenVINO export 디렉토리 공용 래퍼."""

    def __init__(self, ov_dir, task=None):
        from ultralytics import YOLO
        self.model = YOLO(str(ov_dir), task=task)
        self.lock = threading.Lock()

    def __call__(self, image, **kw):
        with self.lock:
            return self.model(image, verbose=False, **kw)


COCO_EN = [
    'person', 'bicycle', 'car', 'motorbike', 'aeroplane', 'bus',
    'train', 'truck', 'boat', 'traffic light', 'fire hydrant', 'stop sign',
    'parking meter', 'bench', 'bird', 'cat', 'dog', 'horse', 'sheep', 'cow',
    'elephant', 'bear', 'zebra', 'giraffe', 'backpack', 'umbrella',
    'handbag', 'tie', 'suitcase', 'frisbee', 'skis', 'snowboard', 'sports ball',
    'kite', 'baseball bat', 'baseball glove', 'skateboard', 'surfboard', 'tennis racket',
    'bottle', 'wine glass', 'cup', 'fork', 'knife', 'spoon', 'bowl',
    'banana', 'apple', 'sandwich', 'orange', 'broccoli', 'carrot', 'hot dog', 'pizza',
    'donut', 'cake', 'chair', 'sofa', 'potted plant', 'bed', 'dining table',
    'toilet', 'tvmonitor', 'laptop', 'mouse', 'remote', 'keyboard', 'cell phone',
    'microwave', 'oven', 'toaster', 'sink', 'refrigerator', 'book',
    'clock', 'vase', 'scissors', 'teddy bear', 'hair drier', 'toothbrush'
]
COCO_KO = [
    '사람', '자전거', '자동차', '오토바이', '비행기', '버스',
    '기차', '트럭', '보트', '신호등', '소화전', '정지신호',
    '주차료징수기', '벤치', '새', '고양이', '개', '말', '양', '소',
    '코끼리', '곰', '얼룩말', '기린', '배낭', '우산',
    '핸드백', '넥타이', '여행가방', '프리스비', '스키', '스노우보드', '스포츠공',
    '연', '야구방망이', '야구글러브', '스케이트보드', '서핑보드', '테니스라켓',
    '병', '와인잔', '컵', '포크', '칼', '숟가락', '그릇',
    '바나나', '사과', '샌드위치', '오렌지', '브로콜리', '당근', '핫도그', '피자',
    '도넛', '케이크', '의자', '소파', '화분', '침대', '식탁',
    '화장실', 'TV', '노트북', '마우스', '리모컨', '키보드', '휴대폰',
    '전자레인지', '오븐', '토스터', '싱크대', '냉장고', '책',
    '시계', '꽃병', '가위', '테디베어', '헤어드라이어', '칫솔'
]


class ObjectEngine:
    def __init__(self):
        self.det = Yolo(MODELS / "object/yolo11m_openvino_model")
        self.pose = Yolo(MODELS / "object/yolo11m-pose_openvino_model")
        self.seg = Yolo(MODELS / "object/yolo11m-seg_openvino_model")
        self.image_size = 800

    @staticmethod
    def _pos(cx, cy):
        p = "L" if cx < 300 else ("R" if cx > 500 else "C")
        p += "T" if cy < 300 else ("B" if cy > 500 else "C")
        return p

    def search(self, image_path):
        image = cv2.imread(image_path)
        h, w = image.shape[:2]
        r = self.det(image, conf=0.7)[0]
        o_ko, o_en, p_ko, p_en = [], [], [], []
        for box in (r.boxes or []):
            cls_id = int(box.cls[0])
            conf = float(box.conf[0])
            x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
            nx1, ny1 = x1 * self.image_size / w, y1 * self.image_size / h
            nx2, ny2 = x2 * self.image_size / w, y2 * self.image_size / h
            pos = self._pos(int(nx1 + (nx2 - nx1) / 2), int(ny1 + (ny2 - ny1) / 2))
            item = {"score": int(conf * 100), "percent": int(conf * 100),
                    "pos": pos, "box": [int(x1), int(y1), int(x2), int(y2)]}
            if COCO_EN[cls_id] == "person" and len(p_en) < 5:
                p_en.append(dict(item, name=COCO_EN[cls_id]))
                p_ko.append(dict(item, name=COCO_KO[cls_id]))
            elif COCO_EN[cls_id] != "person" and len(o_en) < 10:
                o_en.append(dict(item, name=COCO_EN[cls_id]))
                o_ko.append(dict(item, name=COCO_KO[cls_id]))
        return o_ko, o_en, p_ko, p_en

    def points(self, image_path):
        frame = cv2.imread(image_path)
        h, w = frame.shape[:2]
        r = self.pose(frame)[0]
        out = []
        if r.keypoints is not None and r.boxes is not None:
            for i in range(len(r.boxes)):
                score = float(r.boxes.conf[i])
                if score < 0.7 or len(out) >= 5:
                    continue
                x1, y1, x2, y2 = r.boxes.xyxy[i].cpu().numpy()
                kpts = r.keypoints.xy[i].cpu().numpy()
                out.append({
                    "score": int(score * 100), "percent": int(score * 100),
                    "box": [int(max(0, x1 + .5)), int(max(0, y1 + .5)),
                            int(min(w, x2 + .5)), int(min(h, y2 + .5))],
                    "points": [(int(k[0]), int(k[1])) for k in kpts],
                })
        return out

    def segment(self, image_path):
        r = self.seg(image_path)[0]
        return to_b64_jpg(r.plot())


class CustomEngine:
    MODES = ["fire", "fall", "ball", "rps", "number", "helmet", "box"]

    def __init__(self):
        self.models = {}
        for m in self.MODES:
            # box-11s는 seg 모델이지만 detect처럼 boxes만 사용
            self.models[m] = Yolo(MODELS / f"object/{m}-11s_openvino_model")

    def predict(self, mode, image_path):
        if mode not in self.models:
            return []
        r = self.models[mode](image_path)[0]
        data = []
        for box in (r.boxes or []):
            score = float(box.conf[0])
            if score < 0.3:
                continue
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            names = r.names
            name = names.get(int(box.cls[0]), "Unknown") if isinstance(names, dict) \
                else names[int(box.cls[0])]
            data.append({"name": name, "percent": int(score * 100),
                         "score": int(score * 100), "box": (x1, y1, x2, y2)})
        return data


# ---------------------------------------------------------------- 얼굴 스위트 (OV 프리트레인 + YOLO mask cls)
class OVModel:
    def __init__(self, xml_path, device):
        model = core.read_model(xml_path)
        self.compiled = core.compile_model(model, device)
        self.input = self.compiled.input(0)
        self.lock = threading.Lock()

    def infer(self, blob):
        with self.lock:
            return self.compiled({self.input.any_name: blob})


class FaceDetector(OVModel):
    """face-detection-retail-0005 — 입력 [1,3,300,300] BGR, 출력 [1,1,N,7]."""

    def __init__(self, device):
        super().__init__(MODELS / "face/face-detection-retail-0005.xml", device)

    def predict(self, bgr, conf=0.5, margin=0.3, limit=5):
        h, w = bgr.shape[:2]
        blob = cv2.resize(bgr, (300, 300)).transpose(2, 0, 1)[None].astype(np.float32)
        res = list(self.infer(blob).values())[0].reshape(-1, 7)
        items = []
        for det in res:
            score = float(det[2])
            if score < conf or len(items) >= limit:
                continue
            x1, y1, x2, y2 = det[3] * w, det[4] * h, det[5] * w, det[6] * h
            mx, my = (x2 - x1) * margin, (y2 - y1) * margin  # MTCNN 시절과 동일한 30% 마진
            items.append({
                "box": [int(max(0, x1 - mx)), int(max(0, y1 - my)),
                        int(min(w, x2 + mx)), int(min(h, y2 + my))],
                "score": int(score * 100),
            })
        return items


class AgeGender(OVModel):
    """age-gender-recognition-retail-0013 — 입력 [1,3,62,62] BGR."""

    def __init__(self, device):
        super().__init__(MODELS / "face/age-gender-recognition-retail-0013.xml", device)

    def predict(self, face_bgr):
        blob = cv2.resize(face_bgr, (62, 62)).transpose(2, 0, 1)[None].astype(np.float32)
        with self.lock:
            req = self.compiled.create_infer_request()
            req.infer({self.input.any_name: blob})
            age = _out(req, "age_conv3", "fc3_a")
            prob = _out(req, "prob", "fc3_g")
        _a = int(float(np.squeeze(age)) * 100)
        p = np.squeeze(prob)  # [female, male]
        _g = ("여성", "woman") if p[0] > 0.5 else ("남성", "man")
        return _a, _g


EMO_EN = ["neutral", "happy", "sad", "surprised", "angry"]
EMO_KO = ["무표정", "행복한 표정", "슬픈 표정", "놀란 표정", "화난 표정"]


class Emotion(OVModel):
    """emotions-recognition-retail-0003 — 입력 [1,3,64,64] BGR, 5클래스."""

    def __init__(self, device):
        super().__init__(MODELS / "face/emotions-recognition-retail-0003.xml", device)

    def predict(self, face_bgr):
        blob = cv2.resize(face_bgr, (64, 64)).transpose(2, 0, 1)[None].astype(np.float32)
        res = np.squeeze(list(self.infer(blob).values())[0])
        idx = int(np.argmax(res))
        return EMO_KO[idx], EMO_EN[idx]


class HeadPose(OVModel):
    """head-pose-estimation-adas-0001 — 입력 [1,3,60,60] BGR, yaw/pitch/roll(도)."""

    def __init__(self, device):
        super().__init__(MODELS / "face/head-pose-estimation-adas-0001.xml", device)

    def predict(self, face_bgr):
        blob = cv2.resize(face_bgr, (60, 60)).transpose(2, 0, 1)[None].astype(np.float32)
        with self.lock:
            req = self.compiled.create_infer_request()
            req.infer({self.input.any_name: blob})
            yaw = float(np.squeeze(_out(req, "angle_y_fc")))
            pitch = float(np.squeeze(_out(req, "angle_p_fc")))
            roll = float(np.squeeze(_out(req, "angle_r_fc")))
        # 기존 headpose_inference 와 동일한 방향 판정/라디안 응답 유지
        pitch_r, yaw_r, roll_r = pitch * pi / 180, -(yaw * pi / 180), roll * pi / 180
        x3 = sin(yaw_r)
        y3 = -cos(yaw_r) * sin(pitch_r)
        res = ("R" if x3 > 0.15 else ("L" if x3 < -0.15 else "C"))
        res += ("B" if y3 > 0.15 else ("T" if y3 < -0.15 else "C"))
        return {"direction": res, "pitch": pitch_r, "yaw": yaw_r, "roll": roll_r}


class MaskCls:
    """mask-11s-cls (YOLO classification, 입력=얼굴 크롭 224)."""

    def __init__(self):
        self.model = Yolo(MODELS / "object/mask-11s-cls_openvino_model", task="classify")

    def predict(self, face_bgr):
        r = self.model(face_bgr, imgsz=224)[0]
        idx = int(r.probs.top1)
        name = r.names[idx] if not isinstance(r.names, dict) else r.names.get(idx, "")
        return {"mask": 1 if name == "with_mask" else 0,
                "score": round(float(r.probs.top1conf) * 100, 2)}


class FaceEngine:
    def __init__(self):
        self.detect = FaceDetector(DEV_FACE)
        self.age_gender = AgeGender(DEV_FACE)
        self.emotion = Emotion(DEV_FACE)
        self.head_pose = HeadPose(DEV_FACE)
        self.mask = MaskCls()


# ---------------------------------------------------------------- 변환 계열 (gan)
class AnimeGAN:
    """AnimeGANv3 onnx — NHWC float32 [-1,1], HW는 8의 배수."""

    def __init__(self, onnx_path, device):
        self.compiled = core.compile_model(core.read_model(onnx_path), device)
        self.lock = threading.Lock()

    def predict(self, bgr, max_side=960):
        h, w = bgr.shape[:2]
        scale = min(1.0, max_side / max(h, w))
        nh, nw = max(8, int(h * scale) // 8 * 8), max(8, int(w * scale) // 8 * 8)
        rgb = cv2.cvtColor(cv2.resize(bgr, (nw, nh)), cv2.COLOR_BGR2RGB)
        blob = (rgb.astype(np.float32) / 127.5 - 1.0)[None]
        with self.lock:
            out = list(self.compiled({0: blob}).values())[0]
        out = np.squeeze(out)
        if out.ndim == 3 and out.shape[0] == 3:  # NCHW 방어
            out = out.transpose(1, 2, 0)
        out = ((out + 1.0) * 127.5).clip(0, 255).astype(np.uint8)
        out = cv2.cvtColor(out, cv2.COLOR_RGB2BGR)
        return cv2.resize(out, (w, h))


class U2Net:
    """u2net onnx — 배경 제거. 입력 [1,3,320,320] RGB normalize."""

    MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
    STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)

    def __init__(self, device):
        self.compiled = core.compile_model(core.read_model(MODELS / "gan/u2net.onnx"), device)
        self.lock = threading.Lock()

    def predict(self, bgr):
        h, w = bgr.shape[:2]
        rgb = cv2.cvtColor(cv2.resize(bgr, (320, 320)), cv2.COLOR_BGR2RGB).astype(np.float32)
        rgb = ((rgb / 255.0) - self.MEAN) / self.STD
        blob = rgb.transpose(2, 0, 1)[None]
        with self.lock:
            out = list(self.compiled({0: blob}).values())[0]
        mask = np.squeeze(out).astype(np.float32)
        mask = (mask - mask.min()) / (mask.max() - mask.min() + 1e-8)
        mask = cv2.resize(mask, (w, h))[..., None]
        white = np.full_like(bgr, 255)
        return (bgr * mask + white * (1 - mask)).astype(np.uint8)


class SuperRes:
    """single-image-super-resolution-1032 — 480x270 → 1920x1080 (4x)."""

    def __init__(self, device):
        model = core.read_model(MODELS / "gan/single-image-super-resolution-1032.xml")
        self.compiled = core.compile_model(model, device)
        self.inputs = self.compiled.inputs
        self.lock = threading.Lock()

    def predict(self, bgr):
        small = cv2.resize(bgr, (480, 270)).transpose(2, 0, 1)[None].astype(np.float32)
        cubic = cv2.resize(bgr, (1920, 1080), interpolation=cv2.INTER_CUBIC)
        cubic = cubic.transpose(2, 0, 1)[None].astype(np.float32)
        feed = {self.inputs[0].any_name: small, self.inputs[1].any_name: cubic}
        with self.lock:
            out = list(self.compiled(feed).values())[0]
        out = np.squeeze(out).transpose(1, 2, 0)
        return (out * 255).clip(0, 255).astype(np.uint8)


class GanEngine:
    def __init__(self):
        self.cartoon = AnimeGAN(MODELS / "gan/AnimeGANv3_Hayao_36.onnx", DEV_GAN)
        self.style = AnimeGAN(MODELS / "gan/AnimeGANv3_Shinkai_37.onnx", DEV_GAN)
        self.bgremove = U2Net(DEV_GAN)
        self.sr = SuperRes(DEV_GAN)


# ---------------------------------------------------------------- code (ocr / qr)
class CodeEngine:
    def __init__(self):
        import easyocr
        self.reader = easyocr.Reader(
            ["ko", "en"], gpu=False,
            model_storage_directory=str(MODELS / "code/easyocr"),
            user_network_directory=str(MODELS / "code/easyocr"),
            download_enabled=False)
        self.lock = threading.Lock()

    def ocr(self, image_path):
        with self.lock:
            return self.reader.readtext(image_path)

    @staticmethod
    def barcode(image_path):
        from pyzbar import pyzbar
        image = cv2.imread(image_path)
        res = []
        for code in pyzbar.decode(image):
            x, y, bw, bh = code.rect
            res.append({"type": code.type, "data": code.data.decode("utf-8", "ignore"),
                        "box": [int(x), int(y), int(x + bw), int(y + bh)]})
        return res


# ---------------------------------------------------------------- VLM
class VlmEngine:
    def __init__(self):
        import openvino_genai as og
        self.pipe = og.VLMPipeline(str(MODELS / "vlm/qwen2.5-vl-3b-int4"), DEV_VLM)
        self.lock = threading.Lock()

    @staticmethod
    def _tensor(bgr, max_side=896):
        h, w = bgr.shape[:2]
        scale = min(1.0, max_side / max(h, w))
        if scale < 1.0:
            bgr = cv2.resize(bgr, (int(w * scale), int(h * scale)))
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        return ov.Tensor(rgb[None].astype(np.uint8))

    def generate(self, bgr, prompt, max_new_tokens=128):
        with self.lock:
            out = self.pipe.generate(prompt, image=self._tensor(bgr),
                                     max_new_tokens=max_new_tokens)
        return str(out).strip()


# ---------------------------------------------------------------- 로딩
class Engines:
    def __init__(self):
        print(f"[engines] devices={core.available_devices} face={DEV_FACE} gan={DEV_GAN} vlm={DEV_VLM}")
        self.object = ObjectEngine()
        self.custom = CustomEngine()
        self.face = FaceEngine()
        self.gan = GanEngine()
        self.code = CodeEngine()
        self.vlm = VlmEngine()
        print("[engines] all models loaded")
