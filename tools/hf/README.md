---
license: other
license_name: per-folder
license_link: https://github.com/themakerrobot/edge-lab/blob/main/NOTICE
tags:
  - openvino
  - education
---

# edge-lab — 모델 저장소

인터넷 없이 내 컴퓨터에서 하는 AI 실습 [edge-lab](https://github.com/themakerrobot/edge-lab) 이 쓰는 모델입니다.
대부분 OpenVINO IR · ONNX 로 변환해 두었습니다. 설치(`setup_deploy.ps1`)와 배포판 만들기는 `tools/fetch_models.py` 로 여기서 받습니다.

모델마다 라이선스가 다릅니다 — 폴더별로 아래 표를 보세요.
사물 찾기 · 자세 · 영역은 [leeyunjai/easydetect](https://huggingface.co/leeyunjai/easydetect)(Apache-2.0)에서 따로 받습니다.

| 폴더 | 무엇 | 라이선스 |
|---|---|---|
| `face/` | 얼굴 검출 · 나이/성별 · 표정 · 머리 방향 · 얼굴 구분(reidentification-0095) (open_model_zoo) | Apache-2.0 |
| `mask/` | 마스크 판별 (`mask.onnx` — MediaPipe mobilenet_v3_small 임베더 + 분류기) | Apache-2.0 |
| `mediapipe/` | 얼굴 메시(거리 · 방향) · 손동작, 가르치기 특징(손 · 자세 점, mobilenet_v3_small 사진 임베더) | Apache-2.0 |
| `gan/` | 배경 지우기(U2Net) · 화질 개선(SR-1032) · 깊이(Depth Anything V2 Small) | Apache-2.0 |
| `vlm/` | 사진 보고 답하기 (Gemma 3 4B, INT4) | Gemma Terms of Use |
| `embed/` | 문장 임베딩 — 자료에서 찾아 답하기 (multilingual-e5-small, INT8) | MIT |
| `backbone/` | 특징 추출기(MobileNetV2) — 코딩 실습 노트북 07 · 예전 방식으로 가르친 AI | Apache-2.0 |
| `code/` | 글자 인식 (easyocr) | Apache-2.0 |
| `stt-sv/` | 음성 인식 (SenseVoiceSmall INT8, sherpa-onnx) + 말 구간 찾기(silero VAD) | FunASR Model License 1.1 (폴더 안 `LICENSE-SenseVoice.txt`) · silero VAD MIT |
| `tts-int8/` | 음성 합성 (Supertonic 3, INT8) | OpenRAIL-M (사용 제한 — 폴더 안 `LICENSE-OpenRAIL-M.txt`, 바꾼 곳 `MODIFICATIONS.md`) |
| `tts/` | 음성 합성 원본 (Supertonic 3) — 보관용, 설치본에는 안 들어감 | OpenRAIL-M |
| `release/` | 배포판 zip (압축을 풀고 바로 실행) · `latest.json` — 설치할 때는 받지 않음 | 위 모델들의 라이선스를 따름 |

설치하면 `tts/` · `release/` 를 뺀 나머지를 받아 갑니다.
