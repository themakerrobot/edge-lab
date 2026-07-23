# vapi-od

circulus-vapi 온디바이스 버전 (Intel Meteor Lake / OpenVINO).
기존 5개 서버(face/object/caption/gan/code/vlm)를 단일 FastAPI로 통합했고, 응답 스키마는 그대로 유지한다.
설치가 끝나면 **인터넷 없이 전 서비스가 동작**한다.

## 설치

### A. 변환까지 직접 (모델 만들기, 30~50분)
```
git clone https://github.com/themakerrobot/vapi-od.git
cd vapi-od
python -m venv venv && venv\Scripts\activate      # linux: source venv/bin/activate
:: 커스텀 pt 8종을 models\org\ 에 복사
powershell -ExecutionPolicy Bypass -File setup.ps1   # linux: bash setup.sh
python check.py                                       # fail = 0 이어야 함
```
변환이 모두 성공하면 `models/org/`는 자동 삭제된다.

### B. 변환본 내려받기 (배포용, 몇 분)
```
python -m venv venv && venv\Scripts\activate
pip install openvino openvino-genai fastapi "uvicorn[standard]" ultralytics ^
    opencv-python pillow numpy easyocr python-multipart huggingface_hub
hf download leeyunjai/vapi-od --local-dir models --exclude "models.7z"
python fonts_download.py     # 폰트가 repo에 커밋돼 있으면 생략
python check.py
```

## 실행
```
run.bat            # http://localhost:57711  (다른 기기: http://<PC IP>:57711)
```
오프라인 실행 시 환경변수: `HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 YOLO_OFFLINE=1` (run.bat에 포함)

## 구성
| 파일 | 역할 |
|---|---|
| `main.py` | 단일 FastAPI — 기존 엔드포인트 전부 호환, `/docs`, `/system` |
| `engines.py` | OpenVINO 추론 — VLM/변환=GPU, 얼굴=NPU, YOLO/OCR=CPU, 기동 시 워밍업 |
| `prompts.py` | VLM 프롬프트 템플릿 + 출력 파서 (caption 계열·faceAttr·cls 흡수) |
| `view_project/index.html` | 실습 프론트 (학습지 UI, 시스템 상태바, 라이브 모드, 실행 기록) |
| `setup.ps1` / `setup.sh` | 패키지 설치 + 모델 변환/다운로드 |
| `fonts_download.py` | 구글 폰트 로컬화 (`view_project/fonts/`) |
| `check.py` | 전 모델 로드 검증 (오프라인 전환 가능 여부 확인) |

## 모델
| 용도 | 모델 | 디바이스 |
|---|---|---|
| 캡션·질문·태그·장소/시간/날씨·분류·얼굴속성 | Qwen2.5-VL-3B INT4 | GPU |
| 사물/포즈/분할 | YOLO11m (+pose/seg) | CPU |
| 커스텀 7종 (fire·fall·ball·rps·number·helmet·box) | YOLO11s | CPU |
| 마스크 | YOLO11s-cls (얼굴 크롭 224 입력) | CPU |
| 얼굴 검출·나이성별·감정·방향 | OpenVINO 프리트레인 | NPU |
| 변환 (만화·감성·배경제거·화질개선) | AnimeGANv3 ×2 / U2Net / SR-1032 | GPU |
| 글자 인식 | easyocr (ko/en) | CPU |
| QR 인식 | **OpenCV QRCodeDetector** | CPU |

## QR / 바코드 (pyzbar 관련)
- **QR은 OpenCV 디코더로 동작**하므로 추가 설치가 필요 없다.
- `pyzbar`는 **1D 바코드(EAN/CODE128 등) 전용 선택 사항**이며, 없거나 로드에 실패해도 서비스는 정상 동작한다.
- Windows에서 pyzbar를 쓰려면 [Visual C++ 2013 재배포 패키지(x64)](https://www.microsoft.com/download/details.aspx?id=40784)가 필요하다.
  (미설치 시 `libzbar-64.dll` 로드 오류가 나지만 QR 인식에는 영향 없음)
- Linux는 `libzbar0` 패키지만 있으면 된다.

## 제외된 기능
이미지 생성(`txt2image`, `txt2cbimage`)은 온디바이스 버전에서 지원하지 않는다.
엔드포인트는 남아 있으며 미지원 응답을 반환한다.