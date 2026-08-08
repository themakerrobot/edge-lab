# The Maker

**Intel AI PC 기반 온디바이스 AI 체험·코딩·학습 도구.**
사물·얼굴·손·자세 인식, 그림 변환, 글자 읽기, VLM(그림 보고 말하기)까지 CPU/GPU/NPU에 나눠 실행하며,
블록 코딩과 나만의 AI 학습(티처블 머신)을 포함한다. 설치가 끝나면 **인터넷 없이 전부 동작**한다.

## 메뉴
| 메뉴 | 내용 |
|---|---|
| 써보기 (Use) | AI 12가지를 눌러 보는 체험 실습 — 라이브 모드, 시스템 상태바 |
| 파이썬 (Python) | 파이썬 코딩 — themaker 라이브러리로 AI 호출, 실행·정지, 배포 zip |
| 만들기 (Code) | 블록 코딩 — 인식·사진 편집·소리·이벤트 블록, 예제 6종, 무대 |
| 가르치기 (Train) | 나만의 AI 학습 — 사진/손모양/표정/상반신/전신 5개 모드, 학습 곡선·특징 지도 |
| 설정 · 점검 (⚙) | 수업 전 점검, 결과물 관리, 학습 결과 도표, 사용 통계, 전체 초기화 |

## 설치
변환 완료된 모델을 허깅페이스에서 내려받는다 (private repo — Read 권한 토큰 필요).
```
git clone https://github.com/themakerrobot/vapi-od.git
cd vapi-od
powershell -ExecutionPolicy Bypass -File setup_deploy.ps1 -Token hf_xxxx
```
토큰은 `-Token` 인자 또는 `HF_TOKEN` 환경변수로 전달한다 (스크립트에 토큰을 심지 않는다).
미리 `hf auth login`을 해둔 기기라면 토큰 없이 실행해도 된다.

## 실행
`run.bat` 또는 `themaker.exe` (같은 동작).

- 서버가 뜨면 **브라우저 창이 자동으로 열리고**, 모델을 올리는 동안 로딩 안내가 표시된다.
- Chrome/Edge가 있으면 주소창 없는 **앱 창**으로 뜬다 (첫 실행 시 웹캠 권한을 한 번 허용).
- 주소: `http://localhost:57711` (다른 기기에서: `http://<PC IP>:57711`)
- 오프라인 환경변수(`HF_HUB_OFFLINE=1` 등)는 run.bat에 포함되어 있다.

## 파일 구성
| 파일 | 역할 |
|---|---|
| `main.py` | FastAPI 서버 — 전 엔드포인트, `/docs`, `/system`, `/ready`, 앱 창 실행 |
| `engines.py` | OpenVINO 추론 엔진 + 백그라운드 로딩 |
| `prompts.py` | VLM 프롬프트 템플릿·파서 |
| `mp_routes.py` | MediaPipe — 얼굴 거리·방향, 손 제스처 |
| `train_routes.py` | 나만의 AI 학습 API — 특징 추출(5모드)·모델 저장·작품·성적표 |
| `stats_routes.py` | 사용 통계 수집 |
| `code_routes.py` | 파이썬 IDE API — 실행·정지·출력·작품 저장·배포 zip |
| `speech_routes.py` | 음성 인식(STT)·음성 합성(TTS) API |
| `themaker.py` | 학생 코드용 라이브러리 — `vision()`·`camera()`·`speak()` 등 |
| `runner.py` | 배포한 작품 실행기 (themaker-run.exe 로 빌드) |
| `view_project/` | 프론트 5페이지 (`index` 써보기 · `blocks` 블록 코딩 · `code` 파이썬 · `train` 가르치기 · `options` 설정) |
| `run.bat` / `launcher.py` | 실행 (launcher는 themaker.exe 빌드용) |
| `paths.py` | 폴더 규칙 — `models/`(AI 모델) / `data/`(작업 파일) 분리·자동 이전 |
| `setup_deploy.ps1` | 설치 — 패키지 + 모델 다운로드 |
| `make_bundle.bat` / `bundle_check.bat` | 포터블 zip 번들 생성·점검 |
| `check.py` / `smoke_test.py` | 모델 로드·API 검증 |

## 폴더
| 폴더 | 내용 | 지워도 되나 |
|---|---|---|
| `models/` | 허깅페이스에서 받은 AI 모델만 | 다시 받으면 됨 |
| `data/` | 실행하면서 생기는 것 — 학습한 AI(`user`), 작품(`project`·`pycode`), 통계(`stats`), 임시(`tmp`) | **지우면 복구 불가** |

"전체 초기화"는 `data/` 안만 지운다. 예전 설치본에서 `models/user` 처럼 섞여 있던 파일은
서버가 처음 뜰 때 `data/` 로 자동으로 옮긴다.

## 모델
| 용도 | 모델 | 디바이스 |
|---|---|---|
| 캡션·질문·태그·분류·얼굴속성 | Qwen2.5-VL-3B INT4 | GPU |
| 사물/자세/분할 | YOLO11m (+pose/seg) | CPU |
| 커스텀 7종 (fire·fall·ball·rps·number·helmet·box) | YOLO11s | CPU |
| 마스크 | YOLO11s-cls | CPU |
| 얼굴 검출·나이성별·감정·방향 | OpenVINO 프리트레인 | NPU |
| 얼굴 거리·방향 / 손 제스처 / 표정 학습 | MediaPipe | CPU |
| 변환 (배경제거·화질개선) | U2Net / SR-1032 | GPU |
| 글자 인식 | easyocr (ko/en) | CPU |
| QR 인식 | OpenCV QRCodeDetector | CPU |
| 나만의 AI 특징 추출 | MobileNetV2 1280d | NPU |
| 음성 인식 (STT) | Whisper small INT8 (OpenVINO) | GPU/CPU |
| 음성 합성 (TTS) | Supertonic 3 (ONNX 4단계, 31개 언어, onnxruntime) | CPU |

## 라이선스
이 프로젝트는 **AGPL-3.0** 으로 배포한다 (`LICENSE`). YOLO(ultralytics, AGPL-3.0)를 포함하므로
전체를 같은 조건으로 공개하며, 소스·모델을 받아 사용/수정/재배포할 수 있다.

포함된 구성 요소:
| 구성 요소 | 라이선스 |
|---|---|
| Qwen2.5-VL | Apache-2.0 |
| YOLO11 (ultralytics) | AGPL-3.0 |
| OpenVINO / open_model_zoo 얼굴 모델 | Apache-2.0 |
| MediaPipe | Apache-2.0 |
| U2Net | Apache-2.0 |
| easyocr | Apache-2.0 |
| Whisper (OpenVINO 변환본) | Apache-2.0 |
| Supertonic 3 (모델 가중치) | OpenRAIL-M (BigScience Open RAIL-M) |
| Supertonic 추론 절차 (speech_routes.py) | 공식 예제(supertone-inc/supertonic) MIT 기반 이식 |
| Blockly / TensorFlow.js / JSZip | Apache-2.0 / Apache-2.0 / MIT |

### TTS 모델(OpenRAIL-M) 재배포 시 지켜야 할 것
상업 사용·재배포·서비스 호스팅은 허용된다. 다만 모델(또는 그 파생물)을 남에게 넘길 때:
1. 라이선스 사본(`models/tts/LICENSE`)을 함께 준다.
2. 이용 약관·계약서에 **Attachment A의 사용 제한**을 그대로 넣고, 받는 쪽에 그 적용을 알린다.
3. 모델 파일을 고쳤다면 고쳤다는 표시를 남긴다.

주요 제한(발췌): 미성년자 착취·가해, 허위정보 유포, 동의 없는 인물 사칭(딥페이크),
기계 생성물임을 밝히지 않은 배포, 의료 조언·판독, 법집행·출입국 자동판정 등.
이 제한은 AGPL 코드가 아니라 **TTS 모델 가중치에만** 적용된다 (코드와 모델은 별개 저작물).

## 개발용: 모델 직접 변환
pt 원본에서 처음부터 변환할 때만 필요하다 (30~50분). 배포 기기에서는 위 설치만으로 충분하다.
```
git clone https://github.com/themakerrobot/vapi-od.git
cd vapi-od
python -m venv venv && venv\Scripts\activate      # linux: source venv/bin/activate
:: 커스텀 pt 8종을 models\org\ 에 복사
powershell -ExecutionPolicy Bypass -File setup.ps1   # linux: bash setup.sh
python check.py                                       # fail = 0 이어야 함
```
변환이 모두 성공하면 `models/org/`는 자동 삭제되고, 결과를 HF repo에 업로드해 두면 이후 기기는 내려받기만 하면 된다.
