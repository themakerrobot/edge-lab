# 스키마 시험 (모델 없이)

```
tools\schema_test\run.bat          (더블클릭해도 된다)
python tools\schema_test\run.py    (직접 부를 때)
```

가짜 엔진(`fake_engines.py`)을 물려 서버를 띄우고, **모든 엔드포인트와
`themaker` 를 실제로 호출**해 응답 모양을 확인한다. 모델·웹캠·스피커가 없어도
몇 초면 끝나므로, 응답 스키마나 경로를 건드린 뒤 회귀 확인용으로 쓴다.

- 포트는 **57799** — 진짜 서버(57711)가 켜져 있어도 상관없다.
- 실패하면 종료 코드 1 을 돌려준다.

## 무엇을 보는가
| 항목 | 내용 |
|---|---|
| 엔드포인트 | 인식 계열 전부 + 한/영 두 언어 + `prompt`·`detect_mode` 가 서버까지 가는지 |
| 삭제한 경로 | `face_pose`·`_e` 접미사·`txt2image` 등이 되살아나지 않았는지(404) |
| 화면 | `/`·`/blocks`·`/code`·`/train`·`/options` 가 열리는지 |
| themaker | 기능 이름·한글 별칭·언어 전환·`draw()` 한글 라벨·오류 안내·이미지 편집 |

## 무엇을 못 보는가
실제 인식 정확도, 블록 페이지 실행(Blockly), 소리·마이크. 이건 개발기에서 확인한다.

## 손볼 때
`fake_engines.py` 는 진짜 `engines.py` 에서 **표와 순수 계산**(COCO 이름,
`DIRECTION`, `direction_words`, `CUSTOM_KO`)을 그대로 읽어 쓴다 — 이 부분을
흉내 내면 시험이 무의미해지므로 그대로 두고, 추론하는 부분만 대신한다.
기능을 더하면 `check_api.py` 의 `CASES`, `check_themaker.py` 에 한 줄씩 넣는다.
