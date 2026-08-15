# -*- coding: utf-8 -*-
# vapi-od : on-device inference engines (Intel Meteor Lake / OpenVINO)
# 디바이스 배정: VLM/YOLO/gan=GPU, 얼굴 스위트=NPU(없으면 GPU→CPU), ocr/qr=CPU
import base64
import os
import threading
from math import cos, sin, pi
from pathlib import Path

import cv2
import numpy as np
import openvino as ov

MODELS = Path("models")
core = ov.Core()

# 컴파일 캐시 — GPU/NPU 모델 컴파일 산출물을 디스크에 저장한다.
# iGPU 는 전용 메모리가 없어 컴파일 순간 피크가 시스템 RAM 을 그대로 먹는데
# (가중치의 2배 가까이), 16GB PC 는 여기서 넘어져 모델이 안 올라간다.
# 캐시가 있으면 두 번째 기동부터 컴파일을 건너뛰어 피크 메모리·부팅 시간이
# 함께 준다. 자리는 앱데이터(그 PC 의 것 — 작업폴더로 옮길 이유가 없다).
try:
    from paths import APPDATA_DIR as _APPDATA
    CACHE_DIR = os.path.join(_APPDATA, "ov-cache")
    os.makedirs(CACHE_DIR, exist_ok=True)
    core.set_property({"CACHE_DIR": CACHE_DIR})
except Exception as _ex:
    CACHE_DIR = ""
    print("[engines] 컴파일 캐시를 켜지 못했어요 (없어도 동작):", _ex)


def pick(*prefer):
    avail = core.available_devices
    for d in prefer:
        if d in avail:
            return d
    return "CPU"

DEV_FACE = pick("NPU", "GPU")
DEV_GAN = pick("GPU")
VERBOSE = bool(os.environ.get("VAPI_VERBOSE"))   # 자세한 로그 (기본은 조용히)
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
    'train', 'truck', 'boat', 'traffic-light', 'fire-hydrant', 'stop-sign',
    'parking-meter', 'bench', 'bird', 'cat', 'dog', 'horse', 'sheep', 'cow',
    'elephant', 'bear', 'zebra', 'giraffe', 'backpack', 'umbrella',
    'handbag', 'tie', 'suitcase', 'frisbee', 'skis', 'snowboard', 'sports-ball',
    'kite', 'baseball-bat', 'baseball-glove', 'skateboard', 'surfboard', 'tennis-racket',
    'bottle', 'wine-glass', 'cup', 'fork', 'knife', 'spoon', 'bowl',
    'banana', 'apple', 'sandwich', 'orange', 'broccoli', 'carrot', 'hot-dog', 'pizza',
    'donut', 'cake', 'chair', 'sofa', 'potted-plant', 'bed', 'dining-table',
    'toilet', 'tvmonitor', 'laptop', 'mouse', 'remote', 'keyboard', 'cell-phone',
    'microwave', 'oven', 'toaster', 'sink', 'refrigerator', 'book',
    'clock', 'vase', 'scissors', 'teddy-bear', 'hair-drier', 'toothbrush'
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
        self.det = Yolo(MODELS / "object/yolo11m_openvino_model", task="detect")
        self.pose = Yolo(MODELS / "object/yolo11m-pose_openvino_model", task="pose")
        self.seg = Yolo(MODELS / "object/yolo11m-seg_openvino_model", task="segment")
        self.image_size = 800

    @staticmethod
    def _pos(cx, cy):
        p = "L" if cx < 300 else ("R" if cx > 500 else "C")
        p += "T" if cy < 300 else ("B" if cy > 500 else "C")
        return p

    def search(self, image_path, lang="ko"):
        """사람과 사물을 한 목록으로 돌려준다.

        예전에는 person 과 object 를 따로 담았는데, 사람도 COCO 80종 중 하나라
        나눌 이유가 없었다. 사람만 세고 싶으면 name_en == "person" 으로 거른다."""
        image = cv2.imread(image_path)
        h, w = image.shape[:2]
        r = self.det(image, conf=0.7)[0]
        names = COCO_KO if str(lang).startswith("ko") else COCO_EN
        found = []
        for box in (r.boxes or []):
            if len(found) >= 15:
                break
            cls_id = int(box.cls[0])
            conf = float(box.conf[0])
            x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
            nx1, ny1 = x1 * self.image_size / w, y1 * self.image_size / h
            nx2, ny2 = x2 * self.image_size / w, y2 * self.image_size / h
            found.append({
                "name": names[cls_id], "name_en": COCO_EN[cls_id],
                "score": int(conf * 100), "percent": int(conf * 100),
                "pos": self._pos(int(nx1 + (nx2 - nx1) / 2), int(ny1 + (ny2 - ny1) / 2)),
                "box": [int(x1), int(y1), int(x2), int(y2)],
            })
        return found

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

    def segment(self, image_path, lang="ko"):
        """영역을 칠한 그림 + 무엇을 칠했는지 이름·박스.

        seg 모델은 박스·이름·점수를 다 내므로 그림만 돌려주면 아까웠다.
        화면의 "풀이" 문장도 이 이름 목록으로 만든다."""
        r = self.seg(image_path)[0]
        names = COCO_KO if str(lang).startswith("ko") else COCO_EN
        found = []
        for box in (r.boxes or []):
            score = float(box.conf[0])
            if score < 0.3:
                continue
            x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
            cls_id = int(box.cls[0])
            found.append({"name": names[cls_id], "name_en": COCO_EN[cls_id],
                          "score": int(score * 100),
                          "box": [int(x1), int(y1), int(x2), int(y2)]})
        # 라벨·박스는 그리지 않는다 — Ultralytics 가 새기는 글씨는 영문 클래스 이름이라
        # 화면 언어와 어긋난다. 색칠만 받고, 이름은 화면·라이브러리가 그린다.
        return {"image": to_b64_jpg(r.plot(labels=False, boxes=False)), "object": found}


# 개별 인식 모델이 내는 영문 클래스 이름 -> 한국어. 없으면 영문을 그대로 쓴다
# (숫자 모델의 "0"~"9", "+" 같은 것은 번역할 게 없다)
class UserYolo:
    """사람이 가져다 둔 YOLO 모델 파일(.pt)로 인식한다.

    프로그램이 들고 오는 모델과 다른 점 둘:
      - 기동 때 안 올린다. 처음 쓸 때 올리고 그대로 들고 있는다(_cache).
      - 이름은 파일 이름 그대로 — 번역표가 없으므로 name 과 name_en 이 같다.
    파일은 작업폴더의 models 칸(paths.YOLO_DIR)에서만 찾는다. 바깥 경로를
    받지 않는 것은 화면에서 고른 이름이 그대로 파일 경로가 되기 때문이다.
    """

    EXTS = (".pt", ".onnx")

    def __init__(self):
        self._cache = {}
        self.lock = threading.Lock()

    @staticmethod
    def folder():
        import paths as _p
        os.makedirs(_p.YOLO_DIR, exist_ok=True)
        return _p.YOLO_DIR

    @classmethod
    def files(cls):
        """쓸 수 있는 모델 이름 목록 (확장자 포함, 이름순)."""
        d = cls.folder()
        out = []
        try:
            for n in sorted(os.listdir(d)):
                full = os.path.join(d, n)
                if os.path.isfile(full) and n.lower().endswith(cls.EXTS):
                    out.append(n)
                elif os.path.isdir(full) and n.endswith("_openvino_model"):
                    out.append(n)
        except Exception as ex:
            print("[user-yolo] 폴더를 읽지 못했어요:", ex)
        return out

    def _resolve(self, name):
        """이름 하나를 실제 경로로. 폴더 밖으로는 못 나간다."""
        base = os.path.basename(str(name or "").strip())
        if not base:
            raise ValueError("모델 이름이 비었어요.")
        d = self.folder()
        cand = [base] if (base.lower().endswith(self.EXTS)
                          or base.endswith("_openvino_model")) else \
               [base + e for e in self.EXTS] + [base + "_openvino_model"]
        for c in cand:
            full = os.path.join(d, c)
            if os.path.exists(full):
                return full
        have = ", ".join(self.files()) or "(아직 없어요)"
        raise FileNotFoundError(
            "모델 파일이 없어요: %s\n모델 폴더: %s\n지금 있는 것: %s" % (base, d, have))

    def _model(self, name):
        full = self._resolve(name)
        with self.lock:
            m = self._cache.get(full)
            if m is None:
                m = Yolo(full)                 # 처음 쓸 때만 올린다
                self._cache[full] = m
            return m

    def predict(self, name, image_path, conf=0.3):
        r = self._model(name)(image_path)[0]
        out = []
        for box in (r.boxes or []):
            score = float(box.conf[0])
            if score < conf:
                continue
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            names = r.names
            raw = names.get(int(box.cls[0]), "?") if isinstance(names, dict) \
                else names[int(box.cls[0])]
            en = str(raw).strip()
            out.append({"name": en, "name_en": en,
                        "percent": int(score * 100), "score": int(score * 100),
                        "box": (x1, y1, x2, y2)})
        return out

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


# 얼굴이 보는 쪽: 코드(CC·LT…)는 값 비교용으로 그대로 두고, 사람이 읽을 낱말을 함께 준다
DIRECTION = {
    "CC": ("정면", "front"),
    "LC": ("왼쪽", "left"), "RC": ("오른쪽", "right"),
    "CT": ("위", "up"), "CB": ("아래", "down"),
    "LT": ("왼쪽 위", "left up"), "LB": ("왼쪽 아래", "left down"),
    "RT": ("오른쪽 위", "right up"), "RB": ("오른쪽 아래", "right down"),
}


def direction_words(code, lang="ko"):
    """{"direction": 낱말, "direction_en": 코드} — 코드는 언어를 바꿔도 안 변한다."""
    ko, en = DIRECTION.get(code, (code, code))
    return {"direction": ko if str(lang).startswith("ko") else en,
            "direction_en": code}


class HeadPose(OVModel):
    """head-pose-estimation-adas-0001 — 입력 [1,3,60,60] BGR, yaw/pitch/roll(도)."""

    def __init__(self, device):
        super().__init__(MODELS / "face/head-pose-estimation-adas-0001.xml", device)

    def predict(self, face_bgr, lang="ko"):
        blob = cv2.resize(face_bgr, (60, 60)).transpose(2, 0, 1)[None].astype(np.float32)
        with self.lock:
            req = self.compiled.create_infer_request()
            req.infer({self.input.any_name: blob})
            yaw = float(np.squeeze(_out(req, "angle_y_fc")))
            pitch = float(np.squeeze(_out(req, "angle_p_fc")))
            roll = float(np.squeeze(_out(req, "angle_r_fc")))
        # 기존 headpose_inference 와 동일한 방향 판정/라디안 응답 유지
        pitch_r, yaw_r, roll_r = pitch * pi / 180, -(yaw * pi / 180), roll * pi / 180
        # adas-0001은 pitch 부호가 기존 모델과 반대 → 위를 보면 T가 되도록 부호 반전
        x3 = sin(yaw_r)
        y3 = cos(yaw_r) * sin(pitch_r)
        res = ("R" if x3 > 0.15 else ("L" if x3 < -0.15 else "C"))
        res += ("B" if y3 > 0.15 else ("T" if y3 < -0.15 else "C"))
        return dict(direction_words(res, lang),
                    pitch=pitch_r, yaw=yaw_r, roll=roll_r)


class MaskCls:
    """mask-11s-cls (YOLO classification, 입력=얼굴 크롭 224)."""

    def __init__(self):
        self.model = Yolo(MODELS / "object/mask-11s-cls_openvino_model", task="classify")

    def predict(self, face_bgr, lang="ko"):
        r = self.model(face_bgr, imgsz=224)[0]
        idx = int(r.probs.top1)
        name = r.names[idx] if not isinstance(r.names, dict) else r.names.get(idx, "")
        on = 1 if name == "with_mask" else 0
        ko, en = ("마스크 씀", "mask") if on else ("맨얼굴", "no-mask")
        return {"mask": on, "name": ko if str(lang).startswith("ko") else en,
                "name_en": en,
                "score": round(float(r.probs.top1conf) * 100, 2)}


class FaceEngine:
    def __init__(self):
        self.detect = FaceDetector(DEV_FACE)
        self.age_gender = AgeGender(DEV_FACE)
        self.emotion = Emotion(DEV_FACE)
        self.head_pose = HeadPose(DEV_FACE)
        self.mask = MaskCls()


# ---------------------------------------------------------------- 변환 계열 (gan)
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
        """모델 입력이 480x270 고정이므로 비율 유지 letterbox 후, 출력에서 패딩을 잘라낸다."""
        h, w = bgr.shape[:2]
        scale = min(480 / w, 270 / h)
        nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
        resized = cv2.resize(bgr, (nw, nh))
        canvas = cv2.copyMakeBorder(resized, 0, 270 - nh, 0, 480 - nw,
                                    cv2.BORDER_REPLICATE)
        small = canvas.transpose(2, 0, 1)[None].astype(np.float32)
        cubic = cv2.resize(canvas, (1920, 1080), interpolation=cv2.INTER_CUBIC)
        cubic = cubic.transpose(2, 0, 1)[None].astype(np.float32)
        feed = {self.inputs[0].any_name: small, self.inputs[1].any_name: cubic}
        with self.lock:
            out = list(self.compiled(feed).values())[0]
        out = np.squeeze(out).transpose(1, 2, 0)
        out = (out * 255).clip(0, 255).astype(np.uint8)
        out = out[: nh * 4, : nw * 4]                 # 패딩 제거 → 원본 비율 복원
        return cv2.resize(out, (w * 4, h * 4))        # 정확히 4x 크기로 정합


class DepthMetric:
    """Depth Anything V2 Metric Small — 출력이 **미터**다(상대 깊이가 아니다).

    실내(Hypersim)·실외(Virtual KITTI) 모델이 따로 있고 서로 바꿔 쓰면 크게 틀린다.
    교실이 기본이라 indoor 를 먼저 쓰고, 바깥 사진은 outdoor 를 고르게 한다.
    둘 다 기동 때 올리지 않는다 — 처음 쓸 때 올려 캐시한다(상주 메모리 절약).
    """

    MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
    STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)
    SIDE = 518
    PLACES = ("indoor", "outdoor")

    def __init__(self, device):
        self.device = device
        self._cache = {}
        self.lock = threading.Lock()

    def _model(self, place):
        if place not in self.PLACES:
            raise ValueError("place 는 indoor 또는 outdoor")
        if place not in self._cache:
            self._cache[place] = core.compile_model(
                core.read_model(MODELS / f"gan/depth-{place}.xml"), self.device)
        return self._cache[place]

    def meters(self, bgr, place="indoor"):
        """원본 크기의 거리 지도(미터). 값이 작을수록 가깝다."""
        h, w = bgr.shape[:2]
        rgb = cv2.cvtColor(cv2.resize(bgr, (self.SIDE, self.SIDE)), cv2.COLOR_BGR2RGB).astype(np.float32)
        rgb = ((rgb / 255.0) - self.MEAN) / self.STD
        blob = rgb.transpose(2, 0, 1)[None]
        compiled = self._model(place)
        with self.lock:
            out = list(compiled({0: blob}).values())[0]
        return cv2.resize(np.squeeze(out).astype(np.float32), (w, h))

    @staticmethod
    def colorize(m):
        """거리 지도를 색지도로. 가까울수록 밝게 보이도록 뒤집어 칠한다."""
        near = 1.0 - (m - m.min()) / (m.max() - m.min() + 1e-8)
        return cv2.applyColorMap((near * 255).astype(np.uint8), cv2.COLORMAP_INFERNO)

    def at(self, bgr, x, y, place="indoor"):
        """한 점까지의 거리(m). 흔들림을 줄이려 그 자리 5x5 를 중앙값으로 본다."""
        m = self.meters(bgr, place)
        h, w = m.shape[:2]
        x = int(max(0, min(w - 1, x)))
        y = int(max(0, min(h - 1, y)))
        patch = m[max(0, y - 2):y + 3, max(0, x - 2):x + 3]
        return round(float(np.median(patch)), 2)


class GanEngine:
    def __init__(self):
        self.bgremove = U2Net(DEV_GAN)
        self.sr = SuperRes(DEV_GAN)
        self.depth = DepthMetric(DEV_GAN)      # 지연 로딩 — 처음 쓸 때 올라온다


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
        # easyocr의 경로(str) 입력 분기가 일부 Windows 환경에서 grey를 3채널로
        # 만들어 "too many values to unpack (expected 2)" 를 유발함 →
        # 직접 2D 그레이스케일 ndarray로 변환해 전달하면 해당 분기를 우회함
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError("invalid image")
        grey = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        with self.lock:
            return self.reader.readtext(grey)

    @staticmethod
    def barcode(image_path):
        """QR 인식 — OpenCV QRCodeDetector 만 사용한다 (외부 DLL 없음).

        1D 바코드는 지원하지 않는다. 필요해지면 pyzbar 를 추가하면 되지만,
        Windows 에서 VC++ 2013 재배포 패키지를 요구해 기본에서는 제외했다.
        """
        image = cv2.imread(image_path)
        if image is None:
            raise ValueError("invalid image")
        res = []
        try:
            det = cv2.QRCodeDetector()
            ok, texts, pts, _ = det.detectAndDecodeMulti(image)
            if ok and pts is not None:
                for text, quad in zip(texts, pts):
                    if not text:
                        continue
                    xs, ys = quad[:, 0], quad[:, 1]
                    res.append({"type": "QRCODE", "data": text,
                                "box": [int(xs.min()), int(ys.min()),
                                        int(xs.max()), int(ys.max())]})
        except Exception as ex:
            print("[barcode] qr decoder failed:", ex)
        return res


# ---------------------------------------------------------------- VLM
# 쓰는 VLM. 다른 모델을 시험할 때는 VAPI_VLM 환경변수로 폴더 이름을 준다.
#   set VAPI_VLM=다른모델-int4
# 모델을 바꾸려면 새 IR 을 models/vlm 에 두고 이 이름만 고친다 (README 참고).
VLM_NAME = "gemma3-4b-int4"


def find_vlm():
    """쓸 VLM 폴더를 고른다."""
    root = MODELS / "vlm"
    want = os.environ.get("VAPI_VLM", "").strip() or VLM_NAME
    path = root / want
    if path.is_dir():
        return path
    have = [d.name for d in sorted(root.iterdir()) if d.is_dir()] if root.is_dir() else []
    if not have:
        raise FileNotFoundError("models/vlm 에 모델이 없습니다.")
    print("[engines] %s 가 없어 %s 를 씁니다 (있는 것: %s)"
          % (want, have[0], ", ".join(have)))
    return root / have[0]


class VlmEngine:
    def __init__(self):
        import openvino_genai as og
        path = find_vlm()
        print("[engines] VLM:", path.name)
        # VLMPipeline 은 자기 Core 를 쓰므로 캐시를 인자로 직접 준다 —
        # 가장 큰 모델(3.5GB)이라 캐시 효과도 가장 크다
        kw = {"CACHE_DIR": CACHE_DIR} if CACHE_DIR else {}
        self.pipe = og.VLMPipeline(str(path), DEV_VLM, **kw)
        self.lock = threading.Lock()

    @staticmethod
    def _tensor(bgr, max_side=640):
        """640 이 적정선. 실측상 896 은 느리기만 하고 답이 더 낫지 않으며,
        640 아래로 내려도 더 빨라지지 않는다."""
        h, w = bgr.shape[:2]
        scale = min(1.0, max_side / max(h, w))
        if scale < 1.0:
            bgr = cv2.resize(bgr, (int(w * scale), int(h * scale)))
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        return ov.Tensor(rgb[None].astype(np.uint8))

    def generate(self, bgr, prompt, max_new_tokens=128):
        import openvino_genai as og
        cfg = og.GenerationConfig()
        cfg.max_new_tokens = max_new_tokens
        cfg.repetition_penalty = 1.15  # 3B 소형 모델의 문장 반복 루프 억제
        cfg.do_sample = False
        with self.lock:
            out = self.pipe.generate(prompt, image=self._tensor(bgr),
                                     generation_config=cfg)
        return str(out).strip()

    def generate_text(self, prompt, max_new_tokens=256):
        """사진 없이 글만 준다 — 같은 파이프라인을 쓰므로 모델이 늘지 않는다."""
        import openvino_genai as og
        cfg = og.GenerationConfig()
        cfg.max_new_tokens = max_new_tokens
        cfg.repetition_penalty = 1.15
        cfg.do_sample = False
        with self.lock:
            out = self.pipe.generate(prompt, generation_config=cfg)
        return str(out).strip()


# ---------------------------------------------------------------- 임베딩 (자료 찾기용)
class Embed:
    """multilingual-e5-small(INT8) — 글을 숫자 목록(384개)으로 바꾼다.

    무거운 편은 아니지만 쓰는 수업에서만 필요하므로 **첫 요청 때 올린다**.
    CPU 로 돌린다 — GPU 는 VLM 이 쓰고 있고, 이 모델은 CPU 로도 충분히 빠르다.

    e5 계열은 접두사를 붙여야 성능이 나온다 — 자료는 "passage: ", 질문은 "query: ".
    """

    DIM = 384

    def __init__(self):
        self.lock = threading.Lock()
        self.model = None
        self.tok = None
        self.err = ""

    def ready(self):
        return self.model is not None

    def load(self):
        if self.model is not None or self.err:
            return
        with self.lock:
            if self.model is not None or self.err:
                return
            try:
                d = MODELS / "embed/e5-small-int8"
                if not (d / "openvino_model.xml").exists():
                    raise RuntimeError("models/embed/e5-small-int8 가 없어요 "
                                       "(setup_deploy.ps1 로 모델을 받으세요)")
                # 토크나이저 IR 은 openvino-tokenizers 확장이 있어야 열린다.
                # (없으면 "Cannot create SpecialTokensSplit layer ... unsupported opset")
                # 확장은 import 뒤에 만든 Core 에만 붙으므로 여기서 새로 만든다.
                try:
                    import openvino_tokenizers  # noqa: F401
                except ImportError:
                    raise RuntimeError(
                        "openvino-tokenizers 가 설치돼 있지 않아요. "
                        "venv 에서 pip install \"openvino-tokenizers==2026.2.*\" 를 하세요")
                tcore = ov.Core()                 # 확장이 붙은 새 Core
                try:                              # 먼저 만들어 둔 core 에도 붙여 둔다
                    core.add_extension(str(openvino_tokenizers._ext_path))
                except Exception:
                    pass
                self.tok = tcore.compile_model(str(d / "openvino_tokenizer.xml"), "CPU")
                self.model = tcore.compile_model(str(d / "openvino_model.xml"), "CPU")
                print("[embed] multilingual-e5-small loaded (CPU)")
            except Exception as ex:
                self.err = str(ex)
                print("[embed]", ex)

    def encode(self, texts, kind="passage"):
        """글 목록 -> 벡터 목록(정규화됨). kind: passage(자료) / query(질문)"""
        self.load()
        if self.model is None:                      # 긴 OpenVINO 오류를 그대로 띄우면 못 읽는다
            first = (self.err or "models/embed").split("\n")[0].strip()
            raise RuntimeError("자료 찾기 모델을 열지 못했어요 — %s" % first[:140])
        items = [("%s: %s" % (kind, str(t).strip())) for t in texts]
        out = []
        with self.lock:
            for i in range(0, len(items), 16):                # 16개씩 나눠 넣는다
                batch = items[i:i + 16]
                tk = self.tok(batch)
                ids = tk["input_ids"]
                mask = tk["attention_mask"]
                feed = {"input_ids": ids, "attention_mask": mask}
                names = {p.any_name for p in self.model.inputs}
                if "token_type_ids" in names:                 # 이 모델은 셋을 요구한다
                    feed["token_type_ids"] = np.zeros_like(ids)
                res = self.model(feed)[self.model.output(0)]   # [배치, 토큰, 384]
                m = np.asarray(mask, dtype=np.float32)[..., None]
                vec = (res * m).sum(1) / np.maximum(m.sum(1), 1e-9)   # 마스크 평균 풀링
                vec /= np.maximum(np.linalg.norm(vec, axis=1, keepdims=True), 1e-9)
                out.extend(vec.astype(np.float32))
        return out


# ---------------------------------------------------------------- 로딩
# 로딩 단계 정의 — 화면(진행바)과 순서를 맞추기 위해 여기에 모아 둔다.
LOAD_STEPS = [
    ("object", "사물 찾기", "Object detection"),
    ("face", "얼굴 분석", "Face analysis"),
    ("gan", "그림 바꾸기", "Image transform"),
    ("code", "글자 · 코드 읽기", "Text & code"),
    ("vlm", "그림 보고 말하기", "Vision language"),
]
WARM_STEPS = [
    ("w_yolo", "사물 찾기 준비", "Warming up detection"),
    ("w_face", "얼굴 분석 준비", "Warming up face"),
    ("w_gan", "그림 바꾸기 준비", "Warming up transform"),
    ("w_vlm", "그림 보고 말하기 준비", "Warming up vision language"),
]
TOTAL_STEPS = len(LOAD_STEPS) + len(WARM_STEPS)


class Engines:
    def __init__(self, warmup=True, progress=None):
        """progress(key, index) — 단계가 시작될 때마다 호출한다 (로딩 화면용)."""
        self._progress = progress or (lambda *a: None)
        self._n = 0
        print(f"[engines] devices={core.available_devices} face={DEV_FACE} gan={DEV_GAN} vlm={DEV_VLM}")
        builders = [("object", ObjectEngine), ("face", FaceEngine),
                    ("gan", GanEngine), ("code", CodeEngine), ("vlm", VlmEngine)]
        for key, cls in builders:
            self._step(key)
            setattr(self, key, cls())
        self.embed = Embed()          # 지연 로딩 — 자료 찾기 수업에서만 올라온다
        self.user = UserYolo()        # 지연 로딩 — 가져온 모델을 처음 쓸 때만 올린다
        print("[engines] all models loaded")
        if warmup:
            self.warmup()

    def _step(self, key):
        self._progress(key, self._n)
        self._n += 1

    def warmup(self):
        """첫 클릭 지연 제거: 각 모델을 더미 이미지로 1회 실행해 미리 컴파일한다."""
        dummy = np.full((640, 640, 3), 127, np.uint8)
        face = np.full((224, 224, 3), 127, np.uint8)
        steps = [
            ("yolo", lambda: (self.object.det(dummy), self.object.pose(dummy),
                              self.object.seg(dummy))),
            ("face", lambda: (self.face.detect.predict(dummy),
                              self.face.age_gender.predict(face),
                              self.face.emotion.predict(face),
                              self.face.head_pose.predict(face),
                              self.face.mask.predict(face))),
            ("gan", lambda: (self.gan.bgremove.predict(face), self.gan.sr.predict(face))),
            ("vlm", lambda: self.vlm.generate(face, "hi", 1)),
        ]
        for name, fn in steps:
            self._step("w_" + name)
            try:
                fn()
                if VERBOSE:
                    print(f"[warmup] {name} ready")
            except Exception as ex:
                print(f"[warmup] {name} skipped: {ex}")
        print("[engines] warmup done")