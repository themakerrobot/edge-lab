# 실제로 열어 보는 시험 (e2e)

회귀 시험(`tools/schema_test`)은 서버 응답만 본다. 이쪽은 **페이지를 진짜로 열어**
화면 스크립트가 끝까지 도는지, 단추를 눌렀을 때 실제로 저장이 되는지까지 본다.
정적 검사로는 안 잡히는 것들(선언 순서 오류, 없는 칸에 값 쓰기)이 여기서 잡힌다.

## 쓰는 법

    npm install jsdom          # 한 번만
    python3 tools/e2e/serve.py &      # 가짜 엔진으로 서버 기동 (57900)
    node tools/e2e/pages.js          # 여섯 페이지가 오류 없이 뜨는지
    node tools/e2e/actions.js        # 저장 단추를 눌러 실제 저장까지
    node tools/e2e/drag.js           # 손잡이를 끌었을 때 크기가 유지되는지
    node tools/e2e/nocam.js          # 웹캠이 없거나 막혀도 화면이 계속 도는지
    node tools/e2e/camtext.js        # 그때 이유와 대안이 화면에 뜨는지
    node tools/e2e/mic.js            # 마이크 시험(녹음→되들려주기)과 없을 때 안내
    node tools/e2e/dragdir.js        # 좌·우 양쪽으로 끌었을 때 크기가 유지되는지

## jsdom 이 못 하는 것

브라우저에는 있지만 jsdom 에 없는 것은 시험 코드가 채워 준다 —
`fetch`, `Range.getBoundingClientRect`, `canvas.getContext`, `matchMedia`.
이것들이 없어서 나는 오류는 우리 코드 문제가 아니므로 걸러야 한다.
Blockly 가 내는 SVG 관련 경고도 같은 이유로 거른다.
