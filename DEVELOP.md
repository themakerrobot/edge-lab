# 개발 메모

**엣지 랩을 쓰는 사람은 이 문서를 볼 일이 없다.** 사용법은 [README.md](README.md),
설치와 모델 만들기는 [INSTALL.md](INSTALL.md) 에 있다.
여기에는 코드를 고칠 때 알아야 할 규칙만 모았다.

## 파일 구성
| 파일 | 역할 |
|---|---|
| `main.py` | FastAPI 서버 — 전 엔드포인트, `/docs`, `/system`, `/ready`, 앱 창 실행 |
| `engines.py` | OpenVINO 추론 엔진 + 백그라운드 로딩 |
| `prompts.py` | VLM 프롬프트 템플릿·파서 |
| `mp_routes.py` | MediaPipe — 얼굴 거리·방향, 손 제스처 |
| `train_routes.py` | 나만의 AI 학습 API — 특징 추출(5모드)·모델 저장·작품·성적표 |
| `stats_routes.py` | 사용 통계 수집 |
| `code_routes.py` | 파이썬 IDE API — 실행·정지·출력·작품 저장 |
| `speech_routes.py` | 음성 인식(STT)·음성 합성(TTS) API |
| `hub.py` | 실행 중인 main 모듈·엔진 찾기 (`import main` 은 금물 — main.py 가 다시 실행된다) |
| `db_routes.py` | 내가 준 자료에서 찾아 답하기(RAG) — 자료 저장·검색·답변 |
| `themaker.py` | 학생 코드용 라이브러리 — `vision()`·`camera()`·`speak()` 등 |
| `view_project/` | 프론트 6페이지 (`index` 체험하기 · `blocks` 블록 코딩 · `code` 파이썬 · `train` 가르치기 · `talk` 대화 · `options` 설정) |
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

묶음 이름을 기능에 또 쓰지 않는다 — `caption_question` 이 아니라 `/vlm/look`.

## API 응답 규칙
모든 추론 API 는 `{"type", "result", "data", "elapsed_ms", "device"}` 형태로 답한다.
엔드포인트 이름에 붙던 `_e` 접미사와, 한/영을 함께 담던 `_en` 필드는 없앴다.

- **질문한 언어로 답한다** — `/vlm/look` 와 `/chat/ask` 는
  프롬프트에 한글이 있으면 한국어로, 로마자만 있으면 영어로 답한다(`prompts.lang_of`).
  질문이 비어 있을 때만 `lang` 을 따른다.
- **언어는 `lang` 하나로** — `?lang=ko`(기본) 또는 `?lang=en`. 이름·감정·성별·손모양·
  VLM 답변 모두 요청한 언어로 **한 벌만** 온다. 예전처럼 `answer` 와 `answer_en` 이
  같이 오지 않는다 (출력 토큰이 두 배라 느렸고, 화면에도 같은 말이 두 번 나왔다).
- **표에서 꺼내는 값은 `X` 와 `X_en` 둘 다** — 사물 이름·얼굴 감정·성별·
  손 모양처럼 코드가 표에서 꺼내는 값은 영어를 함께 줘도 추론 비용이 0이다. 화면 표시는 `X`, **값 비교는
  `X_en`** 을 쓴다 — 화면 언어를 바꿔도 안 변한다. 모델이 만드는 문장(설명·질문)만
  한 언어로 한 벌 온다.
- **영어 값의 띄어쓰기는 하이픈** — `living-room`, `cell-phone`, `traffic-light`.
  비교 키로 쓰는 값이라 공백을 남기지 않는다(모델에게 보여 주는 프롬프트에서는 공백으로 편다).

| 기능 | 경로 | data |
|---|---|---|
| 사물 | `/object/object_search` | `{"object": [{"name","name_en","score","box","pos"}]}` — **사람도 한 목록에 함께**, `name_en == "person"` 으로 거른다 |
| 얼굴 분석 | `/face/face_analyze` | `[{"age","gender","gender_en","emotion","emotion_en","pos","box"}]` |
| 손 모양 | `/object/hand` | `[{"gesture","gesture_en","score","hand","box","points"}]` — `gesture_en` 은 MediaPipe 코드(`Thumb_Up`) |
| 얼굴 거리·방향 | `/face/mesh` | `[{"box","distance","direction","direction_en"}]` — 얼굴 찾기·방향은 OpenVINO 얼굴 스위트(NPU), 거리는 MediaPipe 홍채(CPU) |
| 마스크 | `/face/mask_detect` | `{"mask": 0\|1, "name": "마스크 씀", "name_en": "mask", "score"}` |
| 사진 보고 답하기 | `/vlm/look` | `{"answer": "..."}` — 설명은 물음을 미리 넣은 질문일 뿐이라 따로 두지 않는다 |
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

