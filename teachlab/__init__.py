# -*- coding: utf-8 -*-
"""Teach Lab 런타임 — 가르치기의 특징 계산을 로봇(파이보·PiBrain)과 같게 한다.

로봇 리포 openpibo-os.pibo 의 openpibo/modules/teachlab/ 을 가져왔다
(themakerrobot/teach-lab python/teachlab, MIT). **같은 계산**이어야 PC 에서 가르친 AI 가
로봇에서 같은 답을 낸다. 고칠 때는 로봇 쪽과 같이 고친다.

  classifier.py  분류기 가중치(classifier.json/.bin) → numpy 로 추론        (로봇과 같은 파일)
  landmarks.py   손·얼굴·포즈 → 좌표·표정 점수 (MediaPipe)                  (로봇과 같은 파일)
  preprocess.py  브라우저 캔버스와 같은 자르기·줄이기                        (로봇과 같은 파일)
  modelfile.py   모델 파일을 바이트로 읽기                                  (로봇과 같은 파일)
  embedder.py    이미지 → 1024 (mobilenet_v3_small) — 로봇은 onnxruntime, 여기는 같은 ONNX 를 OpenVINO(f32)로

models/ 의 파일도 로봇과 같은 파일이다(sha256 이 같아야 한다):
  mobilenet_v3_small_embedder.onnx   로봇 openpibo/modules/teachlab/ (tflite 를 tf2onnx 로 바꾼 것)
  hand_landmarker.task · face_landmarker.task · pose_landmarker_lite.task   로봇 classifier/static/models/
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(HERE, 'models')
EMBEDDER_ONNX = os.path.join(MODEL_DIR, 'mobilenet_v3_small_embedder.onnx')
LANDMARK_FILE = {
    'hand': os.path.join(MODEL_DIR, 'hand_landmarker.task'),
    'face': os.path.join(MODEL_DIR, 'face_landmarker.task'),
    'pose': os.path.join(MODEL_DIR, 'pose_landmarker_lite.task'),
}
