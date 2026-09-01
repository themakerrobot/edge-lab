# 설치 · 모델 만들기

**The Maker 를 쓰는 사람은 이 문서를 볼 일이 없다.** 설치가 끝난 뒤의 사용법은
[README.md](README.md) 에 있다. 여기에는 처음 깔 때와 모델을 새로 만들 때 필요한 것만 모았다.

| 하려는 일 | 볼 곳 |
|---|---|
| PC 에 깔기 (교실·개발 공통) | [설치](#설치) |
| 패키지 버전을 맞추거나 올리기 | [패키지 버전](#패키지-버전) |
| VLM(그림 보고 말하기) 모델 바꾸기 | [VLM 모델 바꾸기](#vlm-모델-바꾸기-개발-pc-전용) |
| 깊이 모델 다시 만들기 | [깊이 모델](#깊이-모델-다시-만들기) |
| HF 저장소를 통째로 다시 만들기 | [HF 모델 저장소](#hf-모델-저장소-다시-만들기) |

---

## 설치
변환 완료된 모델을 허깅페이스에서 내려받는다 (private repo — Read 권한 토큰 필요).
```
git clone https://github.com/themakerrobot/edge-lab.git
cd edge-lab
powershell -ExecutionPolicy Bypass -File setup_deploy.ps1 -Token hf_xxxx
```
토큰은 `-Token` 인자 또는 `HF_TOKEN` 환경변수로 전달한다 (스크립트에 토큰을 심지 않는다).
미리 `hf auth login`을 해둔 기기라면 토큰 없이 실행해도 된다.

끝나면 `run.bat` 으로 실행한다 — 이후 사용법은 README.

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

> **모델 변환용 패키지를 실행 환경에 깔지 않는다.** `transformers`·`optimum` 같은 것을
> 메인 환경에 넣으면 잠가 둔 조합이 깨진다. 아래 변환 절차는 모두 전용 `venv-convert`
> 에서 하고, 끝나면 지운다. (변환이 끝난 뒤 메인 환경이 흔들렸다면
> `pip install -r requirements.lock.txt` 로 되돌린다.)

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
venv\Scripts\python -c "from huggingface_hub import HfApi; HfApi().upload_folder(repo_id='leeyunjai/edge-lab', folder_path='models/vlm/gemma3-4b-int4', path_in_repo='vlm/gemma3-4b-int4', delete_patterns='*', ignore_patterns=['.cache/**'], commit_message='VLM: gemma3-4b')"
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

## 깊이 모델 다시 만들기
평소에는 쓸 일이 없다 — HF 에 올려 둔 IR 을 `setup` 이 받아 쓴다.

쓰는 것은 `gan/depth-v2s.xml` · `.bin` 한 벌이다.

`optimum-intel` 이 `depth_anything` 을 아직 모르므로(custom or unsupported
architecture) `openvino.convert_model` 로 직접 만든다.

```
python -m venv venv-convert
venv-convert\Scripts\activate
pip install torch transformers openvino huggingface_hub
hf auth login                                    # private repo 이므로 write 토큰
```

아래를 `conv.py` 로 저장해 `python conv.py` 로 돌린다. 입력 518 은
`engines.DepthAnything.SIDE` 와 같아야 한다. 출력이 dict(ModelOutput) 이면 변환기가
헷갈리므로 깊이 텐서 하나만 내보내게 감싼다.

```python
import numpy as np, openvino as ov, torch
from transformers import AutoModelForDepthEstimation

SIDE = 518
REPO = "depth-anything/Depth-Anything-V2-Small-hf"    # Small 만 Apache-2.0
OUT  = "depth-v2s.xml"

class DepthOnly(torch.nn.Module):
    def __init__(s, m): super().__init__(); s.m = m
    def forward(s, pixel_values):
        return s.m(pixel_values=pixel_values).predicted_depth

m = AutoModelForDepthEstimation.from_pretrained(REPO).eval()
with torch.no_grad():
    ov_model = ov.convert_model(DepthOnly(m), example_input=torch.zeros(1, 3, SIDE, SIDE))
ov.save_model(ov_model, OUT, compress_to_fp16=True)

r = np.squeeze(list(ov.Core().compile_model(ov_model, "CPU")(
    {0: np.zeros((1, 3, SIDE, SIDE), np.float32)}).values())[0])
print(OUT, r.shape, "값", round(float(r.min()), 3), "~", round(float(r.max()), 3))
```

출력은 **값이 클수록 가깝다**. `engines.DepthAnything.colorize()` 가 그 전제로
칠한다. Base/Large/Giant 는 CC-BY-NC 라 쓰지 않는다.

```
hf upload leeyunjai/edge-lab depth-v2s.xml gan/depth-v2s.xml
hf upload leeyunjai/edge-lab depth-v2s.bin gan/depth-v2s.bin
```

끝나면 정리한다(PowerShell).

```
deactivate
Remove-Item -Recurse -Force venv-convert
Remove-Item conv.py, depth-v2s.xml, depth-v2s.bin
```

## HF 모델 저장소 다시 만들기
배포·개발 PC 는 모두 HF 에서 받아 쓴다. 이 절은 **모델을 새로 만들어 HF 에 올릴 때만** 쓴다 (30~50분).
`models/org/mask-11s-cls.pt` 하나만 있으면 나머지는 전부 원본 저장소에서 받아 오므로,
HF 저장소가 비어도 다시 만들 수 있다 — 다만 **변환 PC 는 인터넷이 필요하다**.
VLM(gemma3)·깊이 지도는 요구 버전이 달라 전용 venv 에서 따로 변환한다 (위 두 절).
```
git clone https://github.com/themakerrobot/edge-lab.git
cd edge-lab
python -m venv venv && venv\Scripts\activate      # linux: source venv/bin/activate
:: mask-11s-cls.pt 를 models\org\ 에 복사 (표준 YOLO11m 3종은 자동으로 받아온다)
powershell -ExecutionPolicy Bypass -File tools\setup.ps1   # linux: bash tools/setup.sh
python tools\check.py                                 # fail = 0 이어야 함
```
변환이 끝나면 결과를 올린다 — `hf upload leeyunjai/edge-lab models .`
`models/org/mask-11s-cls.pt` 도 함께 올려 두어야 이 저장소만으로 전부 다시 만들 수 있다.
이후 기기는 `setup_deploy.ps1` 로 내려받기만 하면 된다.

### 저장소 구성
| 폴더 | 설치본에 | 무엇 |
|---|---|---|
| `object/` `face/` `mediapipe/` `gan/` `vlm/` `embed/` `backbone/` `code/` `stt/` `tts/` | 들어감 | 서버가 읽는 IR·모델 |
| `org/` | 빠짐 | 변환용 원본(.pt) |
| `yolo/` | 빠짐 | 골라 쓰는 사물 찾기 모델 — 쓸 사람이 직접 받아 `문서\The Maker\models` 에 넣는다 |
| `*.md` | 빠짐 | 저장소 설명 |

빼는 것은 `setup_deploy.ps1` 의 `--exclude` 로 정한다. 값을 이어 쓰지 말고
**플래그를 여러 번** 써야 한다 — 이어 쓰면 뒤엣것이 받을 파일 이름으로 먹힌다.
