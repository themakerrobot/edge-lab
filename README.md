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

딱 하나 걸러 내는 것이 있다 — 브라우저가 먼저 끊었을 때 나는
`ConnectionResetError: [WinError 10054]` + `_ProactorBasePipeTransport._call_connection_lost`
잡음. 사진 스트림을 보다가 새로고침하거나 페이지를 옮기면 서버가 아직 쓰는 중인 연결을
브라우저가 끊어서 생긴다. 우리 쪽 잘못이 아니고 이미 끝난 연결이라 할 일도 없지만, 교실
콘솔에서는 빨간 Traceback 이 고장처럼 보인다. `main._quiet_disconnects()` 가 이 한 가지만
넘기고 나머지 오류는 그대로 보여 준다. `VAPI_VERBOSE=1` 이면 이것도 다 나온다.

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
| 대화 | `/chat/ask` | `{"answer": "..."}` — **사진 없이** 묻는다. 같은 VLM 을 글만 넣어 부르므로 모델이 늘지 않는다. 서버는 앞말을 들고 있지 않는다 — 필요하면 화면이 본문에 `history` 로 함께 보낸다(대화 화면의 **앞말 기억** 드롭다운 — 안 함·1·2·3·5·모두, 기본 **안 함**). **말투**(성격)도 같은 본문의 `persona` 로 보낸다 — 고른 값이나 직접 적은 한두 문장이며, 매번 같은 크기로 한 번 붙으므로 대화가 길어져도 늘지 않는다. 한글은 주소에 넣으면 글자당 9바이트로 부풀어 몇 턴만 담아도 주소 길이 한계를 넘기므로 본문으로 받는다 |
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

프로그램 폴더는 깨끗하게 둔다 — 새 버전으로 덮어써도 아이들 작품이 사라지면 안 되고,
`Program Files` 처럼 쓰기가 막힌 곳에 설치돼도 돌아야 하기 때문이다.

| 자리 | 내용 | 기본 위치 |
|---|---|---|
| 프로그램 폴더 | 코드 + `models/`(AI 모델) | 설치한 곳 |
| **작업폴더** | 사람이 만든 것 — 가르친 AI(`user`), 블록 작품(`project`), 파이썬 작품(`pycode`), 자료(`db`), 사용 기록·성적표(`stats`) | 윈도우 `문서\The Maker` |
| 앱데이터 | 그 PC 의 것 — 임시 사진(`tmp`), 앱 창 프로필(`.appwin`), `settings.json` | 윈도우 `%LOCALAPPDATA%\TheMaker` |

`stats` 는 작업폴더에 둔다 — 1 PC : 1 학생 구조라 "이 PC 의 통계"가 곧 "이 사람의 기록"이고,
작업폴더를 옮기면 성적표도 따라가야 하기 때문. 여러 학생을 한데 모아 보는 교사용 집계는
이 파일을 합치는 게 아니라, 필요한 값만 교사용 서버로 보내는 별도 구현으로 한다.

작업폴더 안 `work.json` 에는 **쓰는 사람 이름**이 들어간다(설정·점검 화면의 "이름" 줄,
`POST /system/username`). 비우면 윈도우 로그인 이름을 쓴다. 폴더를 옮기면 이름도 따라간다 —
나중에 교사용 서버로 기록을 보낼 때 누구 것인지 가리는 값으로 쓸 자리다.

USB 를 작업폴더로 쓰다가 **뽑았거나 드라이브 문자가 바뀌면**(E: → F:) 그 자리를 못 찾는다.
이때는 기본 자리(문서\The Maker)로 물러서서 저장이 되게 하고, 설정은 지우지 않는다 —
다시 꽂고 켜면 원래 폴더로 돌아간다. 설정 화면에는 빨간 글씨로 "못 찾은 자리" 를 함께 보여 준다
(`summary()["unreachable"]`). 이 확인이 없으면 서버는 멀쩡히 뜨는데 저장만 전부 실패한다.

설정·점검에는 **소리 시험**과 **마이크 시험**이 나란히 있다. 마이크 시험은 3초 녹음해서
그대로 되들려준다 — 파형이나 숫자 막대는 아이가 판단하기 어렵고, "방금 내가 한 말이 들리는가"
가 유일하게 확실한 기준이다. 이 한 번으로 마이크와 소리 출력이 함께 확인된다.
옆 단추는 윈도우 설정을 연다(`POST /system/sound_settings`, `/system/mic_settings`) —
앱에서 장치를 고르게 하면 브라우저 소리와 파이썬 소리가 갈라지므로 제대로 된 자리를 열어 준다.

**웹캠은 필수가 아니다.** 카메라가 없거나 막혀 있어도 화면은 그대로 돌아간다. 가르치기는
카메라 자리에 이유(없음·막힘·다른 프로그램이 사용 중)와 함께 "사진 넣기로도 학습할 수 있다"를
적어 준다 — 예전에는 켤 때마다 경고창이 떠서 카메라 없는 PC 에서는 매번 눌러 없애야 했다.
검사는 `tools/e2e/nocam.js`·`camtext.js`.

**작품 저장·불러오기는 워드와 같은 결이다.** 저장하면 이름을 묻고, 머리줄에 그 이름이 뜨고,
다시 저장하면 묻지 않고 덮어쓴다. [새로 만들기] 를 누르면 다시 새 작품이 된다.
불러오기는 **탐색기 창**이 작품 폴더(`pycode`/`blocks`)에서 열린다(`POST /system/pick_file`) —
창을 못 띄우는 PC 에서는 저장 목록에서 고르는 방식으로 물러선다.

왼쪽 파일 목록 패널은 **없앴다**. 칸이 하나 늘면 배치가 틀어질 여지가 생기는 데 비해,
아이가 얻는 것은 적었다. 파일을 지우거나 이름을 바꾸는 일은 설정의 `[폴더 열기]` 로
탐색기에서 하면 된다.

칸 크기가 바뀌면 `resize` 를 흘려 준다 — Blockly·CodeMirror 는 그때만 다시 그리기 때문에,
안 알리면 캔버스가 예전 폭 그대로 남아 칸과 캔버스 사이에 흰 빈칸이 생긴다. 처음 배치할 때,
손잡이를 끌 때, 파일 목록을 접었다 펼 때 모두 알린다.

크기를 정한 칸은 `flex-shrink` 도 0 으로 둔다. 기본값 1 이면 칸을 넓혔을 때 남는 자리가
모자라면 브라우저가 그만큼 도로 줄인다 — "오른쪽으로 끌어 편집기를 넓히면 놓는 순간
되돌아가는" 증상이 이것이었다(왼쪽으로 끌 때는 줄이는 쪽이라 증상이 안 보인다).

패널 크기는 **비율(%)로 저장한다**(`lib/split.js`). px 로 적어 두면 그때의 창 폭에서만 맞아서,
파일 목록을 접었다 펴거나 다른 화면을 들렀다 오면 한쪽에 빈칸이 남았다. 저장 규격이 바뀌었으므로
`vapi-split-v4` 표시로 옛 값을 한 번 지운다.

작업폴더 안의 칸은 `paths.WORK_PARTS` 한 곳에서 정한다 — user·project·pycode·blocks·db·stats.
폴더를 만들 때도, 옮길 때도, 비었는지 볼 때도 모두 이 목록을 쓴다(예전에는 같은 목록이 세 군데
적혀 있어서 칸을 하나 늘리면 한쪽만 고쳐졌다).

**블록 작품은 `blocks/` 에 .json 으로 저장한다** — 파이썬 작품(`pycode/*.py`)과 같은 규약
(`/blocks/save`·`/blocks/works`·`/blocks/work`). 예전에는 내려받기 폴더로 파일을 떨어뜨려서
아이가 어디 갔는지 못 찾았고, 작업 폴더를 USB 로 옮겨도 블록 작품은 따라가지 않았다.
두 화면 모두 지금 고치는 작품 이름을 머리줄에 보여 주고, 저장은 그 이름에 덮어쓴다
(다른 이름으로 두려면 [새로 만들기] 로 시작한다).

작업폴더는 **설정·점검 화면의 "작업 폴더" 줄**에서 다룬다 — 지금 위치를 보여 주고
`[폴더 열기]`(탐색기)·`[바꾸기]`. `VAPI_WORK` 로 못박힌 PC 에서는 [바꾸기] 가 꺼진다.
바뀐 위치는 다음에 켤 때부터 쓰인다 — 돌고 있는 서버는 이미 예전 폴더를 열어 둔 상태라
도중에 갈아 끼우면 반쯤 옮겨진 채로 저장될 수 있다.

[바꾸기] 는 **서버가 윈도우 폴더 고르기 창을 띄운다**(`POST /system/pick_folder`) —
브라우저는 폴더의 실제 경로를 알려 주지 않기 때문이고, 서버가 같은 PC 에 있으니 가능하다.
창은 파일 업로드 때 보는 **탐색기형 큰 창**이다 — `folderpick.py` 가 파이썬 표준 `ctypes` 만으로
윈도우 기본 창(IFileOpenDialog)에 FOS_PICKFOLDERS 를 주어 부른다. **바깥 것을 아무것도 쓰지
않는다**: PowerShell·.NET 컴파일·별도 패키지가 필요 없어 교실 PC 마다 다른 조건(실행 정책,
백신, 임시 폴더 권한)에 걸리지 않는다. 처음엔 PowerShell 로 C# 을 컴파일해 불렀는데 그 조건들
때문에 안 뜨는 PC 가 있어 옮겼다.

물러서는 순서: 윈도우 기본 창 → `tkinter` 폴더 창(윈도우 외 OS·앞이 막힌 경우) → 경로 직접 입력.
창은 STA 전용 스레드에서 띄우고 서버는 `run_in_threadpool` 로 넘겨, 창이 떠 있는 동안에도
다른 요청이 그대로 처리된다(안 그러면 화면 전체가 굳는다).

고른 폴더가 **비어 있으면 옮기기**(지금 작업을 그리로), **작업이 들어 있으면 이어서 쓰기**
(아무것도 옮기지 않는다 — 지난 학기 폴더나 USB 를 다시 여는 경우). 무엇이 일어날지 누르기
전에 확인 창으로 알려 준다. 전에는 늘 옮기기여서, 지난 학기 폴더를 고르면 이번 학기 파일이
그 안으로 쏟아져 들어가고 원래 폴더는 비었다 — 아이 작품이 뒤섞이는 사고라 갈랐다.
판별은 `GET /system/workdir/peek`, 실행은 `POST /system/workdir` 에 `mode`(move/open).

USB 로 들고 다니기: `[폴더 열기]` 로 작업 폴더를 열어 통째로 복사 → 다른 PC 에서 그 폴더를
`[바꾸기]` 로 고르면 이어서 쓴다(이름·통계·작품 전부). 압축은 필요하면 하되 필수가 아니다.

정하는 순서(앞이 이김): 환경변수 `VAPI_WORK`·`VAPI_APPDATA` → 프로그램 폴더의
`portable.txt`(USB 로 들고 다닐 때 옆에 `data/` 를 만든다) → `settings.json` → 기본값.

"전체 초기화"는 작업폴더 안(작품·자료·통계)과 임시만 지운다(모델은 그대로).
예전 설치본에서 프로그램 폴더 안 `data/` 나 `models/user` 에 있던 것은 서버가 처음 뜰 때
새 자리로 옮긴다.

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
