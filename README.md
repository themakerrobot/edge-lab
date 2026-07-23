# vapi-od

circulus-vapi 온디바이스 버전 (Intel Meteor Lake / OpenVINO / Windows).
기존 5개 서버(face/object/caption/gan/code/vlm)를 단일 FastAPI로 통합, 응답 스키마 호환.

## 설치 (최초 1회, 인터넷 필요)
```
git clone https://github.com/themakerrobot/vapi-od.git
cd vapi-od
python -m venv venv && venv\Scripts\activate
powershell -ExecutionPolicy Bypass -File setup.ps1   # 변환 포함 전체 셋업
python check.py                                       # fail = 0 확인
```
또는 변환 없이 모델만 받기:
```
hf download leeyunjai/vapi-od --local-dir models --exclude "models.7z"
```

## 실행 (오프라인 가능)
```
run.bat        # http://localhost:57711
```

## 구성
- main.py     : 단일 FastAPI (기존 엔드포인트 전부 호환, /docs)
- engines.py  : OpenVINO 추론 (VLM/YOLO=GPU, 얼굴=NPU, ocr/qr=CPU)
- prompts.py  : VLM 프롬프트 템플릿 + 파서 (caption 계열/faceAttr/cls 흡수)
- view_project/index.html : 실습 프론트 (local 모드 = same-origin)
