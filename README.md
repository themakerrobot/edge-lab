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
| `hub.py` | 실행 중인 main 모듈·엔진 찾기 (`import main` 은 금물 — main.py 가 다시 실행된다) |
| `db_routes.py` | 내가 준 자료에서 찾아 답하기(RAG) — 자료 저장·검색·답변 |
| `themaker.py` | 학생 코드용 라이브러리 — `vision()`·`camera()`·`speak()` 등 |
| `view_project/` | 프론트 6페이지 (`index` 써보기 · `blocks` 블록 코딩 · `code` 파이썬 · `train` 가르치기 · `talk` 대화 · `options` 설정) |
| `paths.py` | 폴더 규칙 — `models/`(AI 모델) / `data/`(작업 파일) 분리·자동 이전 |
| `run.bat` | 실행 |
| `setup_deploy.ps1` | 설치 — 패키지 + 모델 다운로드 |
| `requirements.txt` | 패키지 목록 (lock 파일이 있으면 그쪽 우선) |
| `tools/schema_test/` | 모델 없이 응답 스키마 회귀 시험 — `tools\schema_test\run.bat` (가짜 엔진으로 서버를 띄워 엔드포인트·themaker 를 실제 호출) |
| `tools/` | 개발·점검용 — 모델 변환(`setup.ps1`·`setup.sh`), 번들 생성(`make_bundle.bat`), 점검(`check.py`·`smoke_test.py`·`bundle_check.bat`), 버전 잠금(`freeze.ps1`)·업그레이드 시험(`upgrade_check.ps1`), 폰트, 런처 소스 |

## 로그
기본은 조용히 뜬다 — 교실에서는 요청 한 줄 한 줄이 콘솔을 가득 채우기 때문이다.
문제를 볼 때는 `set VAPI_VERBOSE=1` 로 실행하면 uvicorn 실행 기록과 워밍업 상세가 나온다.
오류·경고는 설정과 무관하게 항상 출력된다.

## 경로 규칙
`/<묶음>/<기능>` — 묶음은 **무엇으로 푸는가**로 나눈다.

| 묶음 | 뜻 |
|---|---|
| `/object/` `/face/` | YOLO · 얼굴 스위트 (빠름) |
| `/vlm/` | 사진을 보고 답하는 VLM (몇 초 걸림) |
| `/chat/` | 사진 없이 글로만 (같은 VLM) + 내가 준 자료에서 찾아 답하기 |
| `/gan/` `/code/` | 이미지 변환 · 글자 읽기 |
| `/custom/` `/pycode/` `/speech/` `/stats/` `/system/` | 나만의 AI · 파이썬 IDE · 음성 · 통계 · 시스템 |

묶음 이름을 기능에 또 쓰지 않는다 — `caption_place` 가 아니라 `/vlm/place`.

## API 응답 규칙
모든 추론 API 는 `{"type", "result", "data", "elapsed_ms", "device"}` 형태로 답한다.
엔드포인트 이름에 붙던 `_e` 접미사와, 한/영을 함께 담던 `_en` 필드는 없앴다.

- **질문한 언어로 답한다** — `/vlm/look` 와 `/chat/ask` 는
  프롬프트에 한글이 있으면 한국어로, 로마자만 있으면 영어로 답한다(`prompts.lang_of`).
  질문이 비어 있을 때만 `lang` 을 따른다.
- **언어는 `lang` 하나로** — `?lang=ko`(기본) 또는 `?lang=en`. 이름·감정·성별·손모양·
  VLM 답변 모두 요청한 언어로 **한 벌만** 온다. 예전처럼 `answer` 와 `answer_en` 이
  같이 오지 않는다 (출력 토큰이 두 배라 느렸고, 화면에도 같은 말이 두 번 나왔다).
- **표에서 꺼내는 값은 `X` 와 `X_en` 둘 다** — 장소·시간·날씨·사물 이름·얼굴 감정·성별·
  손 모양·개별 인식 클래스처럼 코드가 표에서 꺼내는 값은 영어를 함께 줘도 추론 비용이 0이다. 화면 표시는 `X`, **값 비교는
  `X_en`** 을 쓴다 — 화면 언어를 바꿔도 안 변한다. 모델이 만드는 문장(설명·질문·태그)만
  한 언어로 한 벌 온다.
- **영어 값의 띄어쓰기는 하이픈** — `living-room`, `cell-phone`, `traffic-light`.
  비교 키로 쓰는 값이라 공백을 남기지 않는다(모델에게 보여 주는 프롬프트에서는 공백으로 편다).
- **장소·시간·날씨는 정해진 낱말 중 하나** — 아이가 사진만 보고 맞았는지 스스로
  판단할 수 있어야 수업이 된다. 낱말 목록은 `prompts.py` 의 `PLACE`/`TIME`/`WEATHER`
  표 한 곳에서 관리하고, 파서가 별칭까지 흡수해 그 낱말로 맞춰 준다.

| 기능 | 경로 | data |
|---|---|---|
| 장소 | `/vlm/place` | `{"place": "교실", "place_en": "classroom"}` — 교실·도서관·식당·부엌·거실·침실·사무실·운동장·공원·길거리·가게·자연·기타 |
| 시간 | `/vlm/time` | `{"time": "낮", "time_en": "afternoon"}` — 아침·낮·저녁·밤 |
| 날씨 | `/vlm/weather` | `{"weather": "맑음", "weather_en": "sunny"}` — 맑음·흐림·비·눈·바람, 바깥이 안 보이면 실내 |
| 사물 | `/object/object_search` | `{"object": [{"name","name_en","score","box","pos"}]}` — **사람도 한 목록에 함께**, `name_en == "person"` 으로 거른다 |
| 개별 인식 | `/object/object_custom` | `{"object": [{"name","name_en","score","box"}]}` — `name_en` 은 rock·paper·scissors·fire 처럼 소문자 |
| 얼굴 분석 | `/face/face_analyze` | `[{"age","gender","gender_en","emotion","emotion_en","pos","box"}]` |
| 손 모양 | `/object/hand` | `[{"gesture","gesture_en","score","hand","box","points"}]` — `gesture_en` 은 MediaPipe 코드(`Thumb_Up`) |
| 얼굴 거리·방향 | `/face/mesh` | `[{"box","distance","direction","direction_en"}]` — 얼굴 찾기·방향은 OpenVINO 얼굴 스위트(NPU), 거리는 MediaPipe 홍채(CPU) |
| 마스크 | `/face/mask_detect` | `{"mask": 0\|1, "name": "마스크 씀", "name_en": "mask", "score"}` |
| 사진 보고 답하기 | `/vlm/look` | `{"answer": "..."}` — 설명은 물음을 미리 넣은 질문일 뿐이라 따로 두지 않는다 |
| 태그 | `/vlm/tag` | `{"tag": "낱말, 낱말"}` |
| 자료 만들기 | `/chat/db` (POST) · 목록/미리보기(GET) · 삭제(DELETE) | 아이가 준 글을 조각으로 나눠 임베딩까지 저장 — `data/db/<slug>.json` |
| 자료에서 찾기 | `/chat/find` | 답은 안 만들고 닮은 조각만 — "어디서 가져왔나" 를 보여 주는 수업용 |
| 자료에서 답하기 | `/chat/rag` | 찾은 조각만 보고 답한다. 없으면 "자료에서 찾지 못했어요" |
| 대화 | `/chat/ask` | `{"answer": "..."}` — **사진 없이** 묻는다. 같은 VLM 을 글만 넣어 부르므로 모델이 늘지 않는다. 앞말은 기억하지 않는다 |
| 분할 | `/object/object_seg` | `{"image": "<b64 jpg>", "object": [{"name","name_en","score","box"}]}` — 칠한 그림과 무엇을 칠했는지 |

소리는 윈도우 **기본 출력 장치**로 나간다 — 노트북 기본이 모니터(HDMI)로 잡혀 있으면
블록 코딩·파이썬·TTS 가 전부 조용해 보인다. 점검 페이지의 `소리 시험`(브라우저로 삐 소리)
과 `윈도우 소리 설정 열기`(`ms-settings:sound`) 로 확인·수정한다. 앱 안에서 장치를 따로
고르게 하지 않는 이유는, 브라우저 소리와 파이썬 소리가 서로 다른 장치로 갈라지기 때문이다.

파이썬 쪽 소리는 `sounddevice` 로 낸다. PortAudio 의 기본 장치(MME)는 윈도우 기본 장치와
다를 때가 많아 — 모니터 HDMI 오디오가 잡히면 소리가 모니터로 나가 조용해 보인다 —
`themaker` 는 **WASAPI 기본 출력**(= 윈도우 기본 장치)을 우선 고른다.
그래도 안 들리면 `speaker()` 로 목록을 보고 `speaker(번호)`, 또는 환경변수
`THEMAKER_AUDIO=4` 로 못박는다.

파이썬 라이브러리(`themaker`)는 이 언어를 환경변수 `THEMAKER_LANG` 으로 받는다 —
파이썬 페이지에서 실행하면 화면 언어가 그대로 넘어가고, 코드에서 `language("en")` 으로
바꿀 수도 있다. 배포한 프로그램은 한국어가 기본이다.

낱말을 더하거나 빼려면 `prompts.py` 의 표만 고치면 된다 — 프롬프트·파서·프론트가
모두 그 표를 따라간다.

## 패키지 버전
| 파일 | 내용 |
|---|---|
| `requirements.txt` | 동작이 확인된 범위. 추론 런타임(openvino·onnxruntime)은 반드시 고정 |
| `requirements.lock.txt` | 검증된 PC 에서 뽑은 완전 고정본. 있으면 설치가 이것을 우선 사용 |

배포 기기를 전부 같은 환경으로 맞추려면, 설치·점검이 끝난 PC 에서
`powershell -File tools\freeze.ps1` 을 돌려 lock 파일을 만들고 커밋한다.

버전을 올려 보고 싶을 때(개발 PC 전용):
```
powershell -File tools\upgrade_check.ps1     # 최신으로 올린다 (이전 상태 자동 백업)
run.bat  →  tools\bundle_check.bat           # 전 기능 확인
powershell -File tools\freeze.ps1            # 이상 없으면 lock 갱신 후 커밋
powershell -File tools\upgrade_check.ps1 -Rollback   # 문제가 있으면 되돌리기
```
추론 런타임(openvino·onnxruntime)은 사고 이력이 있어 기본으로 제외한다 — 함께 올리려면 `-Runtime`.

## VLM 모델 바꾸기 (개발 PC 전용)
쓰는 모델은 `engines.py` 의 `VLM_NAME` 하나다(현재 `gemma3-4b-int4`).
여러 개 두고 시험할 때는 코드를 고치지 말고 `VAPI_VLM=폴더이름` 을 준다.

변환은 **전용 가상환경**에서 한다 — 모델마다 요구하는 `transformers` 버전이 달라
메인 `venv` 와 섞으면 깨진다. `openvino` 는 **실행 쪽과 같은 버전**으로 맞춘다
(다르면 모델이 열려도 답을 못 만드는 수가 있다).

```
python -m venv venv-convert
venv-convert\Scripts\python -m pip install "transformers>=4.50,<5" "optimum-intel[openvino]" nncf accelerate openvino-tokenizers "openvino==2026.3.*"

venv-convert\Scripts\python -m optimum.commands.optimum_cli export openvino -m google/gemma-3-4b-it --task image-text-to-text --weight-format int4 --trust-remote-code models\vlm\gemma3-4b-int4
```

`--task image-text-to-text` 를 빼면 안 된다. 자동 추론에 맡기면 모델에 따라
비전 부분이 어긋나게 나와, 나중에 답을 만들 때 모양 불일치 오류가 난다.

변환이 끝나면 `venv-convert` 는 지워도 된다 — 교실 PC 는 IR 만 읽는다.

허깅페이스에 올려야 다른 PC 도 `setup_deploy.ps1` 만으로 받는다.

```
venv\Scripts\python -c "from huggingface_hub import HfApi; HfApi().upload_folder(repo_id='leeyunjai/vapi-od', folder_path='models/vlm/gemma3-4b-int4', path_in_repo='vlm/gemma3-4b-int4', delete_patterns='*', ignore_patterns=['.cache/**'], commit_message='VLM: gemma3-4b')"
```

**예전 VLM 폴더는 허깅페이스 웹에서 지운다.** 안 지우면 설치할 때 둘 다 받아 용량만 먹는다.

### 토크나이저 IR 이 "unsupported opset: extension" 으로 안 열릴 때
`Cannot create SpecialTokensSplit layer ... from unsupported opset: extension` 는
**openvino-tokenizers 확장이 그 Core 에 안 붙어 있다**는 뜻이다. 패키지를 깔아도
확장은 `import openvino_tokenizers` **뒤에 만든 Core** 에만 붙는다(그 import 가
`Core.__init__` 을 갈아 끼우는 방식이라서). 모듈 맨 위에서 만들어 둔 Core 로 열면
설치가 돼 있어도 이 오류가 난다. engines.Embed 는 import 뒤에 Core 를 새로 만들고,
기존 core 에도 확장을 붙여 둔다.

### 모델이 열리는데 답을 못 만들 때
`Check '...get_shape() == ...' failed` 같은 오류가 나면 **런타임이 그 구조를 모르는 것**이다.
아주 새로운 구조는 정식 릴리스에 아직 안 들어와 있고, 모델 카드가 nightly 빌드를 권하기도 한다.
**교실에 배포하는 제품이므로 nightly 는 쓰지 않는다** — 정식 릴리스에 들어올 때까지 기다린다.

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
| 캡션·질문·태그·분류·얼굴속성 | Gemma 3 4B INT4 (`engines.py` 의 `VLM_NAME`) | GPU |
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
| Gemma 3 | Gemma Terms of Use |
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
powershell -ExecutionPolicy Bypass -File tools\setup.ps1   # linux: bash tools/setup.sh
python tools\check.py                                 # fail = 0 이어야 함
```
변환이 모두 성공하면 `models/org/`는 자동 삭제되고, 결과를 HF repo에 업로드해 두면 이후 기기는 내려받기만 하면 된다.
