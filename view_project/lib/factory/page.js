/* 로봇 공장(/factory) — 화면 스크립트.
 *
 * themakerrobot/factory-lab index.html (커밋 7a67b5f) 에서 옮김 — 같은 저작자.
 * 로봇팔·컨베이어 조종, 동작 타임라인, 자세 저장, 순서 프로그램, 영점 보정, 멈춤(ESC), 로봇과 대화하기를
 * 그대로 가져왔다. 바뀐 것은 셋이다.
 *   1) 연결: Web Serial → 서버 시리얼(/board/*, lib/factory/link.js). 연결은 보드 앱이 한다.
 *   2) 흘려보내기: 50ms 직접 쓰기 → 0.1초에 한 번, 최신 값만 (HTTP 요청이 쌓이지 않게).
 *   3) 로봇이 없으면 "시뮬레이션" — 같은 명령이 3D 에만 간다. 로봇 없는 교실에서도 다 해 볼 수 있다.
 * 3D 는 lib/factory/scene.js. 치수·각도 변환(FLIP·보정·펄스폭)은 실물에 맞춘 값이라 그대로 두었다.
 */
(() => {
  "use strict";

  /* ===================== 설정 ===================== */
  const DEFAULT_JOINT_NAMES = ["joint1_yaw", "joint2_shoulder", "joint3_elbow", "gripper_joint"]; // pose.json 호환
  const SLOW_DPS = 30;               // 안전 시작 · 천천히 가운데로 에서 쓰는 느린 속도 (deg/s)
  // 서보별 안전 상한 (deg/s) — ch2·ch3 = MG996R, 나머지 = MG90S. 이보다 크게 지령하면 실물이 뒤처진다
  const MAX_DPS = { 1: 500, 2: 300, 3: 300, 4: 500 };
  const FW_DPS = [60, 60, 60, 120];  // 펌웨어 기본 속도 (재생 뒤 복원용)
  const FW_BAUD = 115200;            // factory-lab 기본값 — 펌웨어가 이 속도로 연다
  const CAL_KEY = "el-factory-cal", PKEY = "el-factory-poses";
  const US_MIN = 544, US_MAX = 2400; // 펌웨어 ServoJoint 와 같은 펄스폭 범위
  const BELT_MIN = 15, BELT_MAX = 40;

  const $ = id => document.getElementById(id);
  const clamp = (v, a, b) => v < a ? a : v > b ? b : v;
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const angToUs = a => Math.round(US_MIN + (a / 180) * (US_MAX - US_MIN));
  // factory-lab 에는 이 두 줄이 빠져 있어 #raw: 가 오류로 멈췄다 — 채워 둔다
  const usToAng = us => (us - US_MIN) / (US_MAX - US_MIN) * 180;

  let seqRunning = false, seqAbort = false, busy = false, slowHoming = false;
  let beltDir = 0;                   // 벨트 방향 (+1 앞 / -1 뒤 / 0 정지)

  /* ===================== 한/영 ===================== */
  let LANG = "ko";
  try { LANG = localStorage.getItem("vapiLang") === "en" ? "en" : "ko"; } catch (e) {}
  document.documentElement.lang = LANG;
  const I18N = {
    ko: {
      title: "edge-lab — 로봇 공장", lang: "EN",
      "hdr.sim": "시뮬레이션 — 로봇 없이 3D 로 움직여요", "hdr.on": "로봇 연결됨 · {port} · {baud}", "hdr.lost": "로봇 연결이 끊겼어요",
      "hdr.simHint": "진짜 로봇은 [보드 열기] 에서 속도 115200 · 줄 끝 \"없음\" 으로 연결해요.",
      "hdr.onHint": "움직이는 명령이 3D 와 진짜 로봇에 함께 가요.",
      "hdr.eolWarn": "줄 끝이 \"{eol}\" 이에요 — 이 로봇은 \"없음\" 이어야 해요",
      "hdr.baudWarn": "속도가 {baud} 이에요 — 이 로봇은 {want} 이에요",
      "hdr.board": "보드 열기", "hdr.stop": "멈춰! (ESC)",
      "hdr.idle": "쉬는 중", "hdr.working": "일하는 중", "hdr.released": "힘 뺀 상태", "hdr.playing": "동작 재생 중",
      "hdr.safe": "안전 시작", "hdr.safeTitle": "로봇이 연결되면 바로 힘을 빼고 속도를 느리게 해요",
      "sim.tag": "시뮬레이션", "sim.live": "진짜 로봇과 함께",
      "arm.title": "로봇팔 (ch1-4)", "arm.live": "실시간", "arm.liveTitle": "켜면 슬라이더를 움직이는 동안 로봇도 따라 움직여요",
      j1: "회전", j2: "어깨", j3: "팔꿈치", j4: "집게",
      "arm.note": "−/+ 는 1°씩, 꾹 누르면 계속 움직여요 · 집게 0=활짝(45mm) 180=꽉(약 22mm)",
      "arm.move": "이 자세로 가기", "arm.home": "집으로", "arm.reset": "처음 자세", "arm.resetTitle": "ch1-3=90, 집게=0",
      "arm.slowHome": "천천히 가운데로", "arm.slowHomeTitle": "집게 → 팔꿈치 → 어깨 → 회전 순서로 한 축씩 천천히 가운데(90°)로 가요",
      "arm.off": "힘 빼기", "arm.on": "힘 주기",
      "pose.title": "자세 저장", "pose.ph": "자세 이름", "pose.save": "저장",
      "pose.note": "누르면 그 자세로 가요 · Shift+클릭 = 지우기 · 순서 프로그램에서 \"pose 이름\" 으로 불러요",
      "pose.fileSave": "pose.json 저장", "pose.fileLoad": "불러오기", "pose.del": "(Shift+클릭: 지우기)",
      "cal.btn": "영점 맞추기", "cal.reset": "보정값 지우기", "cal.txt": "보정",
      "cal.help": "영점 모드: −/+ 가 ch1-3 보정값을 1°씩 바꿔요 (진짜 로봇에 보내는 값에만, 이 컴퓨터에 저장). 로봇이 똑바로 설 때까지 맞춰요.",
      "spd.label": "속도", "spd.unit": "도/초", "spd.send": "적용", "spd.ease": "부드럽게 출발·정지",
      "view.title": "3D 공장", "view.echo": "명령대로 움직이는 그림이에요 (진짜 위치는 아니에요)",
      "view.hud": "끌기: 돌리기 · 오른쪽/Shift: 옮기기 · 휠: 확대 · 클릭: 부품",
      "view.all": "전체", "view.arm": "로봇팔", "view.belt": "벨트", "view.flag": "차단봉", "view.top": "위에서",
      "view.grid": "바닥선", "view.wire": "뼈대", "view.axes": "회전축", "view.shot": "사진", "view.zoom": "확대",
      "view.no3d": "이 컴퓨터에서는 3D 그림을 그릴 수 없어요. 로봇 조종은 그대로 돼요.",
      "tl.title": "동작 타임라인 (ch1-4)", "tl.kf": "장면 {n}개", "tl.toStart": "처음으로", "tl.play": "재생 / 잠깐 멈춤", "tl.stop": "정지",
      "tl.add": "장면 추가", "tl.del": "지우기", "tl.len": "길이", "tl.speed": "빠르기", "tl.loop": "반복", "tl.save": "motion.txt", "tl.load": "불러오기",
      "tl.hint": "자세를 만들고 [장면 추가] — 시간 막대를 옮겨 다음 자세를 넣어요. 장면은 끌어서 옮기고, 두 번 누르면 거기에 추가돼요.",
      "row.cut": "꺼짐",
      "side.title": "컨베이어 · 순서 · 대화",
      "conv.title": "컨베이어 (ch5-6)", "conv.roll": "벨트", "conv.fwd": "앞으로", "conv.back": "뒤로", "conv.stop": "멈춤",
      "conv.flag": "차단봉", "conv.flagNote": "빠르기는 15~40 · 차단봉 0 = 막기, 90 = 열기",
      "conv.rollNote": "벨트 빠르기는 15~40 사이만 돼요 (그 아래는 모터가 안 돌아요)",
      "seq.title": "순서대로 시키기", "seq.example": "예제", "seq.run": "실행", "seq.stop": "멈춤", "seq.loop": "반복",
      "seq.help": "pose 이름 · wait 밀리초 · waitdone · #명령! · loop",
      "seq.helpTitle": "한 줄에 하나씩: pose 이름 = 저장한 자세로 · wait 500 = 0.5초 쉬기 · waitdone = 다 갈 때까지 기다리기 · #명령! = 로봇에 그대로 · loop = 처음으로",
      "term.title": "로봇과 대화하기", "term.pos": "어디니?", "term.clear": "지우기", "term.send": "보내기",
      "lbl.arm": "로봇팔 ch1-4", "lbl.belt": "벨트 ch5", "lbl.flag": "차단봉 ch6",
      "log.sim": "(시뮬레이션)", "log.preCal": "(보정 전 {cmd})",
      "log.ready": "준비 완료! 로봇이 없어도 3D 로 미리 볼 수 있어요.",
      "log.connected": "로봇 연결됨 · {port} · {baud}", "log.disconnected": "로봇 연결이 끊겼어요 — 이제 시뮬레이션이에요",
      "log.safeStart": "안전 시작: 힘을 빼고 속도를 느리게 했어요. 손으로 자세를 잡은 뒤 움직이세요.",
      "log.slowHomeRun": "천천히 가운데로 — 한 축씩 움직여요", "log.slowHomeDone": "가운데 자세 완료", "log.slowHomeBusy": "이미 움직이는 중이에요",
      "log.txFail": "보내기 실패: {msg}", "log.stopped": "멈췄어요",
      "log.seqEmpty": "순서가 비어 있어요", "log.seqStart": "순서 시작!", "log.seqStopped": "순서 멈춤", "log.seqDone": "순서 끝! 잘했어요",
      "log.poseMissing": "그런 자세가 없어요: {name}", "log.parseFail": "이해 못 했어요: {line}",
      "log.needKf": "먼저 장면을 추가하세요", "log.motionSaved": "motion.txt 저장 (장면 {n}개)", "log.motionLoaded": "{name} 불러옴 (장면 {n}개, {dur}s)", "log.motionErr": "동작 파일 해석 실패: {msg}",
      "log.poseName": "자세 이름을 적어 주세요", "log.poseLoaded": "{name} 불러옴: {v}", "log.poseErr": "pose.json 해석 실패: {msg}",
      "log.calLive": "영점을 진짜 로봇에 반영하려면 \"실시간\" 을 켜세요", "log.calReset": "보정값 지움",
      "log.hidden": "창이 가려져서 움직임을 멈췄어요"
    },
    en: {
      title: "edge-lab — Robot factory", lang: "한",
      "hdr.sim": "Simulation — moves in 3D without a robot", "hdr.on": "Robot connected · {port} · {baud}", "hdr.lost": "Robot connection lost",
      "hdr.simHint": "For the real robot, connect in [Open Board] at 115200 with line end \"none\".",
      "hdr.onHint": "Move commands go to the 3D view and the real robot.",
      "hdr.eolWarn": "Line end is \"{eol}\" — this robot needs \"none\"",
      "hdr.baudWarn": "Speed is {baud} — this robot uses {want}",
      "hdr.board": "Open Board", "hdr.stop": "STOP (ESC)",
      "hdr.idle": "Resting", "hdr.working": "Working", "hdr.released": "Relaxed", "hdr.playing": "Playing motion",
      "hdr.safe": "Safe start", "hdr.safeTitle": "When the robot connects, relax the arm and slow it down",
      "sim.tag": "Simulation", "sim.live": "With the real robot",
      "arm.title": "Robot arm (ch1-4)", "arm.live": "Live", "arm.liveTitle": "When on, the robot follows while you drag a slider",
      j1: "Turn", j2: "Shoulder", j3: "Elbow", j4: "Gripper",
      "arm.note": "−/+ moves 1°, hold to keep going · Gripper 0=wide open(45mm) 180=closed(about 22mm)",
      "arm.move": "Go to this pose", "arm.home": "Home", "arm.reset": "Start pose", "arm.resetTitle": "ch1-3=90, gripper=0",
      "arm.slowHome": "Slow to centre", "arm.slowHomeTitle": "Moves one axis at a time to 90°: gripper, elbow, shoulder, base",
      "arm.off": "Relax", "arm.on": "Hold",
      "pose.title": "Saved poses", "pose.ph": "pose name", "pose.save": "Save",
      "pose.note": "Click to go there · Shift+click = delete · call it in the program with \"pose name\"",
      "pose.fileSave": "Save pose.json", "pose.fileLoad": "Load", "pose.del": "(Shift+click: delete)",
      "cal.btn": "Zero calibration", "cal.reset": "Clear offsets", "cal.txt": "Offset",
      "cal.help": "Zero mode: −/+ changes the ch1-3 offset by 1° (only for what goes to the real robot, saved on this computer). Adjust until the robot stands straight.",
      "spd.label": "Speed", "spd.unit": "deg/s", "spd.send": "Apply", "spd.ease": "Smooth start and stop",
      "view.title": "3D factory", "view.echo": "Shows what you commanded (not the real position)",
      "view.hud": "Drag: orbit · Right/Shift: pan · Wheel: zoom · Click: part",
      "view.all": "All", "view.arm": "Arm", "view.belt": "Belt", "view.flag": "Gate", "view.top": "Top",
      "view.grid": "Grid", "view.wire": "Wire", "view.axes": "Axes", "view.shot": "Snapshot", "view.zoom": "Zoom",
      "view.no3d": "This computer can't draw the 3D view. Robot control still works.",
      "tl.title": "Motion timeline (ch1-4)", "tl.kf": "{n} keyframes", "tl.toStart": "To start", "tl.play": "Play / pause", "tl.stop": "Stop",
      "tl.add": "Add keyframe", "tl.del": "Delete", "tl.len": "Length", "tl.speed": "Speed", "tl.loop": "Loop", "tl.save": "motion.txt", "tl.load": "Load",
      "tl.hint": "Make a pose and [Add keyframe] — move the time bar and add the next pose. Drag keyframes to move them; double-click adds one there.",
      "row.cut": "Off",
      "side.title": "Conveyor · Program · Talk",
      "conv.title": "Conveyor (ch5-6)", "conv.roll": "Belt", "conv.fwd": "Forward", "conv.back": "Backward", "conv.stop": "Stop",
      "conv.flag": "Gate", "conv.flagNote": "Belt speed 15~40 · Gate 0 = block, 90 = open",
      "conv.rollNote": "Belt speed works only between 15 and 40 (the motor does not turn below that)",
      "seq.title": "Step program", "seq.example": "Example", "seq.run": "Run", "seq.stop": "Stop", "seq.loop": "Loop",
      "seq.help": "pose name · wait ms · waitdone · #command! · loop",
      "seq.helpTitle": "One per line: pose name = go to a saved pose · wait 500 = rest 0.5 s · waitdone = wait until it arrives · #command! = straight to the robot · loop = back to the top",
      "term.title": "Talk to the robot", "term.pos": "Where?", "term.clear": "Clear", "term.send": "Send",
      "lbl.arm": "ARM ch1-4", "lbl.belt": "BELT ch5", "lbl.flag": "GATE ch6",
      "log.sim": "(simulation)", "log.preCal": "(before offset {cmd})",
      "log.ready": "Ready! You can preview in 3D even without a robot.",
      "log.connected": "Robot connected · {port} · {baud}", "log.disconnected": "Robot disconnected — simulation now",
      "log.safeStart": "Safe start: the arm is relaxed and slowed down. Pose it by hand, then move it.",
      "log.slowHomeRun": "Going slowly to centre, one axis at a time", "log.slowHomeDone": "Centre pose reached", "log.slowHomeBusy": "Already moving",
      "log.txFail": "Send failed: {msg}", "log.stopped": "Stopped",
      "log.seqEmpty": "The program is empty", "log.seqStart": "Program started!", "log.seqStopped": "Program stopped", "log.seqDone": "Program finished! Nice job",
      "log.poseMissing": "No such pose: {name}", "log.parseFail": "I don't understand: {line}",
      "log.needKf": "Add a keyframe first", "log.motionSaved": "motion.txt saved ({n} keyframes)", "log.motionLoaded": "{name} loaded ({n} keyframes, {dur}s)", "log.motionErr": "Motion file error: {msg}",
      "log.poseName": "Type a pose name first", "log.poseLoaded": "{name} loaded: {v}", "log.poseErr": "pose.json error: {msg}",
      "log.calLive": "Turn on \"Live\" to apply zeroing to the real robot", "log.calReset": "Offsets cleared",
      "log.hidden": "The window was hidden, so motion stopped"
    }
  };
  function t(key, vars) {
    let s = I18N[LANG][key] !== undefined ? I18N[LANG][key] : I18N.ko[key] !== undefined ? I18N.ko[key] : key;
    if (vars) for (const k of Object.keys(vars)) s = s.split("{" + k + "}").join(vars[k]);
    return s;
  }

  /* 아이콘 — 선으로만 그린 24×24 (lib/icons.js 와 같은 방식: 폰트·CDN 없이) */
  const svg = (d, fill) => '<svg viewBox="0 0 24 24" aria-hidden="true" fill="' + (fill ? "currentColor" : "none") +
    '" stroke="' + (fill ? "none" : "currentColor") + '" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round">' + d + "</svg>";
  const IC = {
    chip: svg('<rect x="6" y="6" width="12" height="12" rx="1.5"/><path d="M9 2.5V6M15 2.5V6M9 18v3.5M15 18v3.5M2.5 9H6M2.5 15H6M18 9h3.5M18 15h3.5"/>'),
    hand: svg('<path d="M8 13V5.5a1.5 1.5 0 0 1 3 0V11M11 11V4a1.5 1.5 0 0 1 3 0v7M14 11V5.5a1.5 1.5 0 0 1 3 0V13M17 9.5a1.5 1.5 0 0 1 3 0V15a7 7 0 0 1-7 7h-.5a7 7 0 0 1-5.6-2.8L4 15.5a1.6 1.6 0 0 1 2.5-2l1.5 1.5"/>'),
    right: svg('<path d="M5 12h14M13 6l6 6-6 6"/>'),
    left: svg('<path d="M19 12H5M11 6l-6 6 6 6"/>'),
    home: svg('<path d="M3 10 12 3l9 7"/><path d="M5.5 9.5V20h13V9.5"/><path d="M10 20v-5.5h4V20"/>'),
    reset: svg('<path d="M4 4v6h6"/><path d="M4.5 10A8 8 0 1 1 6 16.5"/>'),
    gauge: svg('<path d="M4.2 17a9 9 0 1 1 15.6 0"/><path d="m12 13 4-5"/><circle cx="12" cy="13" r="1.3"/>'),
    moon: svg('<path d="M20 14.5A8.5 8.5 0 1 1 9.5 4a7 7 0 0 0 10.5 10.5Z"/>'),
    bolt: svg('<path d="M13 2 4 14h7l-1 8 9-12h-7Z"/>'),
    star: svg('<path d="m12 3 2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1-4.4-4.3 6.1-.9Z"/>'),
    plus: svg('<path d="M12 5v14M5 12h14"/>'),
    minus: svg('<path d="M5 12h14"/>'),
    download: svg('<path d="M12 4v11M7 10.5l5 5 5-5"/><path d="M4 20h16"/>'),
    upload: svg('<path d="M12 16V5M7 9.5l5-5 5 5"/><path d="M4 20h16"/>'),
    cross: svg('<circle cx="12" cy="12" r="7"/><path d="M12 2.5v5M12 16.5v5M2.5 12h5M16.5 12h5"/>'),
    eraser: svg('<path d="m7 20-3.5-3.5a1.5 1.5 0 0 1 0-2.1L13.4 4.5a1.5 1.5 0 0 1 2.1 0l4 4a1.5 1.5 0 0 1 0 2.1L10.1 20Z"/><path d="M7 20h13M9 10l5 5"/>'),
    grid: svg('<rect x="3.5" y="3.5" width="17" height="17" rx="1.5"/><path d="M3.5 9.2h17M3.5 14.8h17M9.2 3.5v17M14.8 3.5v17"/>'),
    cube: svg('<path d="M12 2.8 20 7.2v9.6L12 21.2 4 16.8V7.2Z"/><path d="M4 7.2 12 11.6l8-4.4M12 11.6v9.6"/>'),
    axes: svg('<path d="M12 12V3.5M12 12l7.5 4.3M12 12l-7.5 4.3"/><path d="m10 5.5 2-2 2 2"/>'),
    camera: svg('<path d="M4 7.5h3.2L9 5h6l1.8 2.5H20a1 1 0 0 1 1 1V18a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V8.5a1 1 0 0 1 1-1Z"/><circle cx="12" cy="13" r="3.4"/>'),
    zoom: svg('<circle cx="10.5" cy="10.5" r="6.5"/><path d="m15.5 15.5 5 5M10.5 7.5v6M7.5 10.5h6"/>'),
    film: svg('<rect x="3" y="5" width="18" height="14" rx="1.5"/><path d="M3 9h18M7 5l2 4M12 5l2 4M17 5l2 4"/>'),
    first: svg('<path d="M6 5v14"/><path d="M18 5.5v13L9 12Z" fill="currentColor"/>'),
    play: svg('<path d="M7 4.5v15l12.5-7.5Z"/>', true),
    pause: svg('<rect x="6" y="5" width="4" height="14" rx="1"/><rect x="14" y="5" width="4" height="14" rx="1"/>', true),
    square: svg('<rect x="6" y="6" width="12" height="12" rx="2"/>', true),
    trash: svg('<path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13"/>'),
    repeat: svg('<path d="M4 11V9a3 3 0 0 1 3-3h12M16 3l3 3-3 3"/><path d="M20 13v2a3 3 0 0 1-3 3H5M8 21l-3-3 3-3"/>'),
    factory: svg('<path d="M3 20V10l5 3V10l5 3V10l5 3V4h3v16Z"/><path d="M7 17h2M12 17h2"/>'),
    list: svg('<path d="M9 6h11M9 12h11M9 18h11"/><path d="M4 5h1.5v2M4 11.5h2l-2 2h2M4 17h2v1.5H4.8M6 18.5V20H4"/>'),
    term: svg('<rect x="3" y="4.5" width="18" height="15" rx="1.5"/><path d="m7 10 3 2.5L7 15M12.5 15H17"/>'),
    pin: svg('<path d="M12 21s-6.5-6-6.5-11a6.5 6.5 0 0 1 13 0c0 5-6.5 11-6.5 11Z"/><circle cx="12" cy="10" r="2.4"/>'),
    send: svg('<path d="M21 3 3 10.5l7 2.5 2.5 7Z"/><path d="m10 13 5-5"/>'),
    bulb: svg('<path d="M9 18h6M10 21h4"/><path d="M12 3a6 6 0 0 0-3.5 10.9c.6.5 1 1.2 1 2V16h5v-.1c0-.8.4-1.5 1-2A6 6 0 0 0 12 3Z"/>')
  };

  /* data-i18n(+data-ic) · data-i18n-title · data-i18n-ph 를 한 번에 채운다 */
  function paintText() {
    document.title = t("title");
    $("langButton").textContent = t("lang");
    document.querySelectorAll("[data-i18n]").forEach(el => {
      const ic = el.dataset.ic;
      if (ic && IC[ic]) el.innerHTML = IC[ic] + "<span>" + esc(t(el.dataset.i18n)) + "</span>";
      else el.textContent = t(el.dataset.i18n);
    });
    document.querySelectorAll("[data-ic]:not([data-i18n]):not(.st)").forEach(el => { if (IC[el.dataset.ic]) el.innerHTML = IC[el.dataset.ic]; });
    document.querySelectorAll("[data-i18n-title]").forEach(el => { el.title = t(el.dataset.i18nTitle); });
    document.querySelectorAll("[data-i18n-ph]").forEach(el => { el.placeholder = t(el.dataset.i18nPh); });
    // .st 안의 글자 칸(data-i18n)은 아이콘을 앞에 따로 붙인다
    document.querySelectorAll(".st[data-ic]:not([data-i18n])").forEach(el => {
      const first = el.firstElementChild;
      if (first && !first.matches("svg")) el.insertAdjacentHTML("afterbegin", IC[el.dataset.ic]);
    });
    $("seq").placeholder = "pose home\nwaitdone\n#m1:45,1500!\nwait 1600\n#m2:90,1200!";
  }
  function esc(s) { return String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])); }

  /* ── 축 슬라이더 줄 네 개 (ch1-4) ── */
  $("strips").innerHTML = [1, 2, 3, 4].map(ch =>
    '<div class="strip" data-ch="' + ch + '"><div class="top"><label for="j' + ch + '" data-i18n="j' + ch + '"></label>' +
    '<span class="sub" id="u' + ch + '"></span><input class="inp" id="v' + ch + '" type="number" min="0" max="180" value="90"></div>' +
    '<div class="bot"><button class="nb" type="button" data-ch="' + ch + '" data-dir="-1" aria-label="-1">' + IC.minus + "</button>" +
    '<input type="range" id="j' + ch + '" min="0" max="180" value="90">' +
    '<button class="nb" type="button" data-ch="' + ch + '" data-dir="1" aria-label="+1">' + IC.plus + "</button></div></div>").join("");

  /* ===================== 로봇과 대화하기 (기록) ===================== */
  const term = $("term");
  function log(text, cls = "rx") {
    const at = term.scrollTop + term.clientHeight >= term.scrollHeight - 30;
    const el = document.createElement("div"); el.className = cls;
    const tm = new Date(), p = n => String(n).padStart(2, "0");
    el.innerHTML = '<span class="tm">' + p(tm.getHours()) + ":" + p(tm.getMinutes()) + ":" + p(tm.getSeconds()) + "</span>" +
      (cls === "tx" ? "→ " : cls === "rx" ? "← " : "") + esc(text);
    term.appendChild(el);
    while (term.childElementCount > 500) term.removeChild(term.firstChild);
    if (at) term.scrollTop = term.scrollHeight;
  }
  function download(name, blob) {
    const a = document.createElement("a");
    a.download = name; a.href = URL.createObjectURL(blob);
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 2000);
  }

  /* ===== 채널별 각도 리밋 — 기구가 물리는 각도를 실측하면 LIM 한 줄만 고친다.
     슬라이더뿐 아니라 직접 입력(#m: / #j: / #raw:)까지 calOut() 에서 최종적으로 잘린다. ===== */
  const LIM = { 1: [0, 180], 2: [0, 180], 3: [0, 180], 4: [0, 180], 6: [0, 180] };
  const limOf = ch => LIM[ch] || [0, 180];
  const clampCh = (ch, v) => { const [a, b] = limOf(ch); return clamp(Math.round(v) || 0, a, b); };
  const jointCh = i => (i < 4 ? i + 1 : 6);          // sim.joints 인덱스 → 채널 (0~3 = ch1~4, 4 = ch6)

  /* ===== 영점 보정 (ch1-3, 로봇으로 나가는 값에만) ===== */
  let calibMode = false;
  let cal = [0, 0, 0];
  try { const s = JSON.parse(localStorage.getItem(CAL_KEY) || "null"); if (Array.isArray(s)) cal = [0, 1, 2].map(i => +s[i] || 0); } catch (e) {}
  const saveCal = () => { try { localStorage.setItem(CAL_KEY, JSON.stringify(cal)); } catch (e) {} };
  const calOf = ch => (ch >= 1 && ch <= 3) ? cal[ch - 1] : 0;
  const hasCal = () => cal.some(v => v);
  const withCal = (ch, v) => clampCh(ch, v + calOf(ch));
  // 실물 서보가 화면과 반대로 도는 축 — 로봇으로 나가는 각도만 뒤집는다 (슬라이더·3D 값은 그대로)
  const FLIP = { 2: true, 3: true };
  const toMotor = (ch, v) => withCal(ch, FLIP[ch] ? 180 - clampCh(ch, v) : clampCh(ch, v));
  const fromMotor = (ch, v) => { const u = clampCh(ch, v - calOf(ch)); return FLIP[ch] ? clampCh(ch, 180 - u) : u; };
  function calOut(cmd) {
    let x;
    if ((x = cmd.match(/^#m:(-?\d+),(-?\d+),(-?\d+),(-?\d+)(.*)$/)))
      return "#m:" + [1, 2, 3, 4].map(ch => toMotor(ch, +x[ch])).join(",") + x[5];
    if ((x = cmd.match(/^#j:(\d+),(-?\d+)(.*)$/)))
      return "#j:" + x[1] + "," + toMotor(+x[1], +x[2]) + x[3];
    if ((x = cmd.match(/^#raw:(\d+),(-?\d+)(.*)$/))) {  // 펄스폭 직접 지령도 같은 리밋 안으로 접는다
      const ch = +x[1], us = clamp(+x[2], US_MIN, US_MAX);
      if (ch >= 1 && ch <= 4) return "#raw:" + ch + "," + angToUs(clampCh(ch, usToAng(us))) + x[3];
      return "#raw:" + ch + "," + us + x[3];
    }
    return cmd;
  }

  /* ===== 지령 모델 : 펌웨어 ServoJoint 와 같은 smoothstep / deg per sec =====
     3D 는 "보낸 명령"을 그린다. 로봇이 없어도(시뮬레이션) 똑같이 움직인다. */
  const sim = {
    joints: [
      { cur: 90, from: 90, to: 90, t0: 0, dur: 0, dps: 60 },
      { cur: 90, from: 90, to: 90, t0: 0, dur: 0, dps: 60 },
      { cur: 90, from: 90, to: 90, t0: 0, dur: 0, dps: 60 },
      { cur: 90, from: 90, to: 90, t0: 0, dur: 0, dps: 120 },
      { cur: 90, from: 90, to: 90, t0: 0, dur: 0, dps: 67 }     // ch6 차단봉
    ],
    easing: true, roller: 0, rollerUntil: 0, flagReturnAt: 0, released: false
  };
  function simMove(i, target) {
    const j = sim.joints[i]; if (!j) return;
    target = clampCh(jointCh(i), target);
    const d = Math.abs(target - j.cur);
    j.from = j.cur; j.to = target; j.t0 = performance.now();
    j.dur = d < 0.5 ? 0 : (d / j.dps) * 1000;
    if (!j.dur) j.cur = target;
    sim.released = false;
  }
  function simSet(i, v) {        // 타임라인: 보간값을 곧바로
    const j = sim.joints[i]; if (!j) return;
    j.cur = j.from = j.to = clampCh(jointCh(i), v); j.dur = 0;
    sim.released = false;
  }
  function simStop() { sim.joints.forEach(j => { j.dur = 0; j.to = j.cur; }); }
  const simBusy = () => sim.joints.some(j => j.dur > 0);
  function simTick(now) {
    for (const j of sim.joints) {
      if (!j.dur) continue;
      const tt = (now - j.t0) / j.dur;
      if (tt >= 1) { j.cur = j.to; j.dur = 0; continue; }
      const r = sim.easing ? tt * tt * (3 - 2 * tt) : tt;
      j.cur = j.from + (j.to - j.from) * r;
    }
    if (sim.rollerUntil && now >= sim.rollerUntil) { sim.rollerUntil = 0; sim.roller = 0; beltDir = 0; }
    if (sim.flagReturnAt && now >= sim.flagReturnAt) { sim.flagReturnAt = 0; simMove(4, 90); $("flag").value = $("flagVal").value = 0; }
  }

  /* ===================== 서버 시리얼 ===================== */
  const L = window.EL_FACTORY_LINK.create({
    onLine(e) {
      if (e.dir === "rx") onLine(e.text);
      else if (e.dir === "sys") log(e.text, "sys");
      // tx 는 보낼 때 이미 적었다 — 서버 기록의 tx 까지 적으면 두 번 찍힌다
    },
    onConnect(on, st) {
      if (on) attach(st);
      else if (attached) { attached = false; seqAbort = true; lastPacket = ""; log(t("log.disconnected"), "sys"); }
      paintLink();
    },
    onStatus: paintLink
  });
  let attached = false;
  /* 로봇이 연결된 것을 알아챘을 때 — factory-lab 이 포트를 연 직후에 하던 일 */
  function attach(st) {
    attached = true; lastPacket = "";
    log(t("log.connected", { port: st.port, baud: st.baud }), "sys");
    send("#ver!", { local: false });
    send("#pos!", { local: false });
    // 안전 시작: 연결되자마자 힘을 빼고 속도를 느리게 해서, 그 뒤로는 손으로 자세를 잡을 수 있게 한다
    if ($("safeStart").checked) {
      send("#off!");
      for (const ch of [1, 2, 3]) send("#s:" + ch + "," + SLOW_DPS + "!");
      send("#s:4," + SLOW_DPS * 2 + "!");
      log(t("log.safeStart"), "sys");
    }
  }
  function paintLink() {
    const st = L.status, on = L.connected;
    const s = $("state");
    s.className = "state " + (on ? "on" : st.lost ? "bad" : "sim");
    $("stateText").textContent = on ? t("hdr.on", { port: st.port, baud: st.baud }) : st.lost ? t("hdr.lost") : t("hdr.sim");
    $("linkHint").textContent = on ? t("hdr.onHint") : t("hdr.simHint");
    const warn = [];
    if (on && st.eol && st.eol !== "none") warn.push(t("hdr.eolWarn", { eol: st.eol }));
    if (on && st.baud && +st.baud !== FW_BAUD) warn.push(t("hdr.baudWarn", { baud: st.baud, want: FW_BAUD }));
    $("linkWarn").hidden = !warn.length; $("linkWarn").textContent = warn.join(" · ");
    const tag = $("simTag");
    tag.textContent = on ? t("sim.live") : t("sim.tag"); tag.classList.toggle("live", on);
  }
  $("btnBoard").onclick = () => { if (window.EL_WIN) EL_WIN.open("/board"); else location.href = "/board"; };

  function onLine(line) {
    log(line, /^Err|\[ERR\]|\[REJ|collision/.test(line) ? "err" : "rx");
    const mm = line.match(/arm:\s*([\d,\s-]+?)\s+sort:\s*(-?\d+)\s+roller:\s*(-?\d+)/);
    if (mm) {
      if (/^(Moved|Stopped):/.test(line)) busy = false;
      const a = mm[1].split(",").map(Number);
      if (a.length === 4 && !tl.playing) a.forEach((v, i) => {
        const s = fromMotor(i + 1, v);                  // 로봇값(보정·반전 포함) → 슬라이더 값
        const j = sim.joints[i]; j.cur = s; j.to = s; j.dur = 0; setSlider(i + 1, s);
      });
      const f = +mm[2];
      sim.joints[4].cur = f + 90; sim.joints[4].to = f + 90; sim.joints[4].dur = 0;
      $("flag").value = $("flagVal").value = f;
      sim.roller = +mm[3]; beltDir = Math.sign(sim.roller);
      if (sim.roller) $("roller").value = $("rollerVal").value = clamp(Math.abs(sim.roller), BELT_MIN, BELT_MAX);
    }
    if (/^\d$/.test(line)) busy = line === "1";
  }

  /* ===== 송신 ===== */
  function applyLocal(cmd) {
    let x;
    if ((x = cmd.match(/^#m:(-?\d+),(-?\d+),(-?\d+),(-?\d+)/))) { for (let i = 0; i < 4; i++) simMove(i, +x[i + 1]); }
    else if ((x = cmd.match(/^#j:(\d+),(-?\d+)/))) simMove(+x[1] - 1, +x[2]);
    else if ((x = cmd.match(/^#m1:(-?\d+)(?:,(\d+))?/))) {
      sim.roller = clamp(+x[1], -90, 90); beltDir = Math.sign(sim.roller);
      sim.rollerUntil = (x[2] && sim.roller) ? performance.now() + +x[2] : 0;
    }
    else if ((x = cmd.match(/^#m2:(-?\d+)(?:,(\d+))?/))) {
      simMove(4, clamp(+x[1], -90, 90) + 90);
      sim.flagReturnAt = x[2] ? performance.now() + +x[2] : 0;
    }
    else if ((x = cmd.match(/^#s:(\d+),([\d.]+)/))) { const j = sim.joints[+x[1] - 1]; if (j) j.dps = Math.max(0.5, +x[2]); }
    else if ((x = cmd.match(/^#e:(\d)/))) sim.easing = x[1] === "1";
    else if (/^#home/.test(cmd)) { for (let i = 0; i < 5; i++) simMove(i, 90); sim.roller = 0; sim.rollerUntil = 0; beltDir = 0; }
    else if (/^#stop/.test(cmd)) { simStop(); sim.roller = 0; sim.rollerUntil = 0; sim.flagReturnAt = 0; beltDir = 0; }
    else if (/^#off/.test(cmd)) { simStop(); sim.roller = 0; beltDir = 0; sim.released = true; }
    else if (/^#on/.test(cmd)) sim.released = false;
    else if ((x = cmd.match(/^#raw:(\d+),(\d+)/))) {
      const ch = +x[1], ang = clampCh(ch, usToAng(clamp(+x[2], US_MIN, US_MAX)));
      if (ch === 5) sim.roller = ang - 90;
      else if (ch === 6) simMove(4, ang);
      else if (ch >= 1 && ch <= 4) simMove(ch - 1, ang);
    }
  }
  // opt.local=false : 3D 반영 생략(타임라인이 직접 구동) / opt.quiet : 시뮬레이션일 때 기록 생략
  // opt.silent : 연결돼 있어도 기록 생략 (#busy 확인, 재생 중 #s 속도 맞추기)
  function send(cmd, opt = {}) {
    if (!cmd.endsWith("!")) cmd += "!";
    if (opt.local !== false) applyLocal(cmd);
    if (/^#(m:|m2:|j:|home)/.test(cmd)) busy = true;
    const out = calOut(cmd);
    if (!L.connected) { if (!opt.quiet) log(out + "   " + t("log.sim"), "tx"); return Promise.resolve(); }
    if (!opt.silent) log(out + (out !== cmd ? "   " + t("log.preCal", { cmd }) : ""), "tx");
    return L.send(out).catch(e => { if (L.connected) log(t("log.txFail", { msg: e.message }), "err"); });
  }

  // 실시간: 슬라이더·미세조정·타임라인 값을 #m 으로 흘려보낸다 (값이 바뀔 때만, 0.1초에 한 번까지 — link.js)
  let lastPacket = "";
  function sendArmNow(force) {
    if (!L.connected) return;
    const p = "#m:" + armVals().join(",") + "!";
    if (!force && p === lastPacket) return;
    lastPacket = p;
    busy = true;
    L.stream(calOut(p), out => log(out, "tx"));        // 실제로 나간 것만 적는다 — 버려진 중간값은 적지 않는다
  }
  function liveArmTick(force) {
    if (!$("liveArm").checked || !L.connected) return;
    sendArmNow(force);
  }

  /* ===================== 3D ===================== */
  const CH_KEY = ["j1", "j2", "j3", "j4"];
  let tipTimer = 0;
  const S = window.EL_FACTORY_3D.create({
    canvas: $("sim"), box: $("sceneBox"), label: t,
    onZoom(z) { $("camZoom").value = clamp(z, 0.15, 10).toFixed(2); $("camZoomTxt").textContent = z.toFixed(1) + "x"; },
    onCam: markCam,
    onPick(ch, x, y) {
      document.querySelectorAll(".strip.hl").forEach(el => el.classList.remove("hl"));
      const tip = $("tip");
      if (!ch) { tip.style.display = "none"; return; }
      const row = document.querySelector('.strip[data-ch="' + ch + '"]');
      if (row) { row.classList.add("hl"); row.scrollIntoView({ block: "nearest", behavior: "smooth" }); }
      tip.textContent = "ch" + ch + " · " + t(CH_KEY[ch - 1]);
      tip.style.left = (x + 10) + "px"; tip.style.top = (y + 8) + "px"; tip.style.display = "block";
      clearTimeout(tipTimer); tipTimer = setTimeout(() => { tip.style.display = "none"; }, 2000);
    }
  });
  const camBtns = [...document.querySelectorAll("[data-cam]")];
  function markCam(name) { camBtns.forEach(b => b.classList.toggle("on", b.dataset.cam === name)); }
  if (S.ok) {
    camBtns.forEach(b => { b.onclick = () => { S.setCam(b.dataset.cam); markCam(b.dataset.cam); }; });
    markCam("all"); S.setCam("all");
    $("camZoom").oninput = e => { S.zoom(+e.target.value); $("camZoomTxt").textContent = (+e.target.value).toFixed(1) + "x"; };
    $("btnGrid").onclick = function () { this.classList.toggle("on", S.toggleGrid()); };
    $("btnWire").onclick = function () { this.classList.toggle("on", S.toggleWire()); };
    $("btnAxes").onclick = function () { this.classList.toggle("on", S.toggleAxes()); };
    $("btnShot").onclick = () => S.snapshot(b => b && download("robot_factory.png", b));
    new ResizeObserver(() => S.resize()).observe($("sceneBox"));
    // 라벨 글꼴(Gowun Dodum)은 필요한 글자 조각만 받아 온다 — 받은 뒤에 라벨을 다시 그린다
    if (document.fonts && document.fonts.load) {
      const txt = ["lbl.arm", "lbl.belt", "lbl.flag"].map(t).join("");
      document.fonts.load('30px "Gowun Dodum"', txt).then(() => S.relabel(), () => {});
    }
  } else {
    const el = document.createElement("div"); el.className = "no3d"; el.textContent = t("view.no3d");
    $("sceneBox").appendChild(el);
    ["btnGrid", "btnWire", "btnAxes", "btnShot", "camZoom"].forEach(id => { $(id).disabled = true; });
    camBtns.forEach(b => { b.disabled = true; });
  }

  /* ===================== 타임라인 (ch1-4) ===================== */
  const tl = { kfs: [], nextId: 0, t: 0, dur: 30, playing: false, speed: 1, loop: false, sel: null, last: null, dragId: null, seeking: false };
  const tlCanvas = $("tlCanvas"), tlWrap = $("tlWrap");
  let tlW = 300, tlH = 60;
  const TL_PAD = 10;
  const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
  let TC = {};
  function tlColors() {
    TC = { blue: css("--pen-blue") || "#1f5f7a", blueD: css("--pen-blue-d") || "#12455c", red: css("--pen-red") || "#b4451c",
           ink: css("--ink") || "#2a2620", ink2: css("--ink-2") || "#4a423a", line: css("--line") || "#9a8f7d" };
  }
  tlColors();
  function resizeTl() {
    const r = tlWrap.getBoundingClientRect(), dpr = Math.min(2, window.devicePixelRatio || 1);
    if (!r.width) return;
    tlW = Math.max(50, r.width); tlH = Math.max(30, r.height);
    tlCanvas.width = Math.round(tlW * dpr); tlCanvas.height = Math.round(tlH * dpr);
    tlCanvas.getContext("2d").setTransform(dpr, 0, 0, dpr, 0, 0);
  }
  const tToX = tt => TL_PAD + (tt / tl.dur) * (tlW - TL_PAD * 2);
  const xToT = x => Math.round(clamp((x - TL_PAD) / (tlW - TL_PAD * 2), 0, 1) * tl.dur);
  const sortedKfs = () => [...tl.kfs].sort((a, b) => a.time - b.time);
  const kfCount = () => { $("tlKfCount").textContent = t("tl.kf", { n: tl.kfs.length }); };

  function applyArm(vals) {
    vals.forEach((v, i) => { simSet(i, v); setSlider(i + 1, Math.round(v)); });
    liveArmTick();
  }
  function applyAtTime(tt) {
    const s = sortedKfs(); if (!s.length) return;
    if (s.length === 1 || tt <= s[0].time) return applyArm(s[0].joints);
    if (tt >= s[s.length - 1].time) return applyArm(s[s.length - 1].joints);
    let a = s[0], b = s[1];
    for (let i = 0; i < s.length - 1; i++) if (s[i].time <= tt && s[i + 1].time >= tt) { a = s[i]; b = s[i + 1]; break; }
    syncSegSpeed(a, b);
    const al = b.time === a.time ? 1 : (tt - a.time) / (b.time - a.time);
    const e = al * al * (3 - 2 * al);
    applyArm(a.joints.map((v, i) => v + (b.joints[i] - v) * e));
  }
  function addKeyframe() {
    const time = Math.round(tl.t);
    const ex = tl.kfs.find(k => k.time === time);
    if (ex) { ex.joints = armVals(); tl.sel = ex.id; }
    else { const k = { id: tl.nextId++, time, joints: armVals() }; tl.kfs.push(k); tl.sel = k.id; }
    tl.t = time; kfCount();
  }
  /* 재생 중 속도 맞추기 — 펌웨어는 #m 을 받을 때마다 |Δ| / speed 로 이동 시간을 다시 잡는다.
     speed 가 타임라인 실제 각속도보다 빠르면 한 스텝을 순식간에 끝내고 다음 명령까지 멈춰 서서 "톡톡" 튄다.
     그래서 구간이 바뀔 때마다 그 구간의 실제 각속도를 #s 로 내려보낸다. ×1.2 는 smoothstep 중간이 평균보다 빨라서.
     HTTP 로는 0.1초마다 한 번이라 50ms 보다 스텝이 크다 — 그래도 같은 식이 맞다(각속도는 스텝 간격과 무관). */
  const userDps = FW_DPS.slice();
  let segKey = null;
  function syncSegSpeed(a, b) {
    if (!tl.playing || !L.connected) return;
    const key = a.id + ":" + b.id + ":" + tl.speed;
    if (key === segKey) return;
    segKey = key;
    const dt = (b.time - a.time) / tl.speed;
    if (dt <= 0) return;
    for (let i = 0; i < 4; i++) {
      const d = Math.abs(b.joints[i] - a.joints[i]);
      if (d < 1) continue;
      const dps = clamp(d / dt * 1.2, 0.5, MAX_DPS[i + 1]);
      send("#s:" + (i + 1) + "," + dps.toFixed(1) + "!", { local: false, silent: true });
    }
  }
  function setPlay(on) {
    const was = tl.playing;
    tl.playing = on; tl.last = null;
    if (L.connected && on && !was) {
      segKey = null;
      send("#e:0!", { local: false, silent: true });      // 웹이 이미 smoothstep 을 먹였다. 펌웨어까지 걸면 이중 가감속
    } else if (L.connected && !on && was) {
      segKey = null;
      L.cancelStream();
      send("#e:" + ($("easing").checked ? 1 : 0) + "!", { local: false, silent: true });
      userDps.forEach((d, i) => send("#s:" + (i + 1) + "," + d + "!", { local: false, silent: true }));
    }
    $("tlPlay").innerHTML = on ? IC.pause : IC.play;
    $("tlPlay").classList.toggle("on", on);
  }
  function tlTick(now) {
    if (tl.playing) {
      if (tl.last !== null) {
        tl.t += (now - tl.last) / 1000 * tl.speed;
        if (tl.t >= tl.dur) {
          if (tl.loop) tl.t %= tl.dur;
          else { tl.t = tl.dur; setPlay(false); }
        }
      }
      if (tl.playing) tl.last = now;
      applyAtTime(tl.t);
    }
    drawTimeline();
    $("tlTime").textContent = tl.t.toFixed(2) + "s";
  }
  function drawTimeline() {
    const g = tlCanvas.getContext("2d"), W = tlW, H = tlH, TH = H - 16, mid = TH / 2;
    g.clearRect(0, 0, W, H);
    g.fillStyle = "#fbfaf5"; g.fillRect(0, 0, W, H);
    const step = tl.dur <= 30 ? 1 : tl.dur <= 60 ? 2 : 5;
    g.font = '12px "Gowun Dodum", sans-serif';
    for (let tt = 0; tt <= tl.dur; tt += step) {
      const x = Math.round(tToX(tt)) + .5;
      g.strokeStyle = tt % 5 === 0 ? "#dcd5c6" : "#efeae0"; g.lineWidth = 1;
      g.beginPath(); g.moveTo(x, 0); g.lineTo(x, TH); g.stroke();
      if (tt % (step * 5) === 0) { g.fillStyle = TC.ink2; g.fillText(tt + "s", x + 2, H - 3); }
    }
    const ex = Math.round(tToX(tl.dur)) + .5;
    g.strokeStyle = TC.blue; g.setLineDash([3, 3]);
    g.beginPath(); g.moveTo(ex, 0); g.lineTo(ex, TH); g.stroke(); g.setLineDash([]);
    const s = sortedKfs();
    if (s.length > 1) {
      g.strokeStyle = TC.line; g.lineWidth = 2;
      g.beginPath(); g.moveTo(tToX(s[0].time), mid);
      s.slice(1).forEach(k => g.lineTo(tToX(k.time), mid)); g.stroke();
    }
    for (const k of s) {
      const x = tToX(k.time), sel = k.id === tl.sel, R = sel ? 8 : 6;
      g.fillStyle = sel ? TC.blueD : TC.blue;
      g.beginPath(); g.moveTo(x, mid - R); g.lineTo(x + R, mid); g.lineTo(x, mid + R); g.lineTo(x - R, mid); g.closePath(); g.fill();
      if (sel) {
        g.strokeStyle = TC.red; g.lineWidth = 1.5; g.stroke();
        g.fillStyle = TC.ink; const lab = k.joints.map(Math.round).join(",");
        const lw = g.measureText(lab).width;
        g.fillText(lab, x + 10 + lw > W ? x - 10 - lw : x + 10, mid - 8);
      }
    }
    const px = tToX(tl.t);
    g.strokeStyle = TC.red; g.lineWidth = 2;
    g.beginPath(); g.moveTo(px, 0); g.lineTo(px, TH); g.stroke();
    g.fillStyle = TC.red;
    g.beginPath(); g.moveTo(px - 5, 0); g.lineTo(px + 5, 0); g.lineTo(px, 7); g.closePath(); g.fill();
  }
  const tlX = e => e.clientX - tlCanvas.getBoundingClientRect().left;
  const kfAt = x => tl.kfs.find(k => Math.abs(tToX(k.time) - x) < 9) || null;
  tlCanvas.addEventListener("pointerdown", e => {
    const x = tlX(e), k = kfAt(x);
    tlCanvas.setPointerCapture(e.pointerId);
    if (k) { tl.sel = k.id; tl.dragId = k.id; tl.t = k.time; if (!tl.playing) applyAtTime(k.time); }
    else { tl.seeking = true; tl.t = xToT(x); if (!tl.playing) applyAtTime(tl.t); }
  });
  tlCanvas.addEventListener("pointermove", e => {
    if (tl.dragId !== null) {
      const k = tl.kfs.find(q => q.id === tl.dragId);
      if (k) { k.time = xToT(tlX(e)); tl.t = k.time; if (!tl.playing) applyAtTime(k.time); }
    } else if (tl.seeking) { tl.t = xToT(tlX(e)); if (!tl.playing) applyAtTime(tl.t); }
  });
  const tlUp = () => { tl.dragId = null; tl.seeking = false; };
  tlCanvas.addEventListener("pointerup", tlUp);
  tlCanvas.addEventListener("pointercancel", tlUp);
  tlCanvas.addEventListener("dblclick", e => { tl.t = xToT(tlX(e)); addKeyframe(); });

  $("tlToStart").onclick = () => { setPlay(false); tl.t = 0; applyAtTime(0); };
  $("tlPlay").onclick = () => {
    if (!tl.kfs.length) { log(t("log.needKf"), "err"); return; }
    if (!tl.playing && tl.t >= tl.dur) tl.t = 0;
    setPlay(!tl.playing);
    if (tl.playing) { liveArmTick(true); if (window.vapiStat) vapiStat("factory_play"); }
  };
  $("tlStop").onclick = () => { setPlay(false); tl.t = 0; applyAtTime(0); };
  $("tlAdd").onclick = addKeyframe;
  $("tlDel").onclick = () => { if (tl.sel === null) return; tl.kfs = tl.kfs.filter(k => k.id !== tl.sel); tl.sel = null; kfCount(); };
  $("tlDur").onchange = e => {
    tl.dur = clamp(Math.round(+e.target.value) || 30, 1, 120); e.target.value = tl.dur;
    tl.kfs.forEach(k => { k.time = Math.min(k.time, tl.dur); });
    if (tl.t > tl.dur) tl.t = tl.dur;
  };
  $("tlSpeed").onchange = e => { tl.speed = +e.target.value; };
  $("tlLoop").onclick = function () { tl.loop = !tl.loop; this.classList.toggle("on", tl.loop); };
  $("tlSave").onclick = () => {
    if (!tl.kfs.length) { log(t("log.needKf"), "err"); return; }
    const fmt = d => Number.isInteger(d) ? String(d) : d.toFixed(2).replace(/0+$/, "").replace(/\.$/, "");
    const s = sortedKfs(), lines = [];
    s.forEach((k, i) => {
      lines.push("m:" + k.joints.map((v, j) => toMotor(j + 1, v)).join(","));   // 보정·반전 포함 모터값
      if (i < s.length - 1) { const dt = s[i + 1].time - k.time; if (dt > 0) lines.push("sleep " + fmt(dt)); }
    });
    download("motion.txt", new Blob([lines.join("\n") + "\n"], { type: "text/plain" }));
    log(t("log.motionSaved", { n: s.length }), "sys");
  };
  $("tlLoad").onclick = () => $("motionFileIn").click();
  $("motionFileIn").addEventListener("change", async e => {
    const f = e.target.files[0]; e.target.value = ""; if (!f) return;
    const raw = (await f.text()).trim();
    const names = DEFAULT_JOINT_NAMES;
    try {
      if (raw[0] === "{") {                              // robot-arm-sim JSON
        const d = JSON.parse(raw);
        tl.dur = clamp(Math.round(d.duration || 30), 1, 120);
        tl.kfs = (d.keyframes || []).map((k, i) => ({
          id: i, time: Math.round(k.time || 0),
          joints: (Array.isArray(k.joints) ? k.joints.slice(0, 4).map(Number)
            : names.map((n, j) => +((k.joints && k.joints[n]) ?? (j === 3 ? 0 : 90)))).map((v, j) => clampCh(j + 1, v))
        }));
      } else {                                          // m:.. / #m:..! / sleep 초
        const kfs = []; let tt = 0;
        for (const ln of raw.split(/\r?\n/)) {
          const s = ln.trim(); if (!s) continue;
          if (/^#?m:/.test(s)) {
            const n = s.replace(/^#?m:/, "").replace(/!$/, "").split(",").map(x => parseInt(x.trim(), 10));
            // 저장값은 보정 포함 → 슬라이더 값으로 되돌림
            kfs.push({ id: kfs.length, time: Math.round(tt), joints: [0, 1, 2, 3].map(j => fromMotor(j + 1, isNaN(n[j]) ? 90 : n[j])) });
          } else if (/^sleep/i.test(s)) tt += parseFloat(s.replace(/sleep/i, "").trim()) || 0;
        }
        tl.kfs = kfs;
        tl.dur = clamp(Math.max(5, Math.ceil(tt)), 1, 120);
      }
      tl.nextId = tl.kfs.reduce((m, k) => Math.max(m, k.id + 1), 0);
      $("tlDur").value = tl.dur; tl.sel = null; tl.t = 0; setPlay(false);
      kfCount(); applyAtTime(0);
      log(t("log.motionLoaded", { name: f.name, n: tl.kfs.length, dur: tl.dur }), "sys");
    } catch (err) { log(t("log.motionErr", { msg: err.message }), "err"); }
  });

  /* ===================== 프레임 — 보이는 동안만 ===================== */
  let fpsN = 0, fpsT = performance.now(), rafId = 0;
  function frame(now) {
    rafId = 0;
    simTick(now);
    tlTick(now);
    if (S.ok) S.render({ joints: sim.joints.slice(0, 4).map(j => j.cur), flag: sim.joints[4].cur, roller: sim.roller });
    updateHud();
    fpsN++;
    if (now - fpsT >= 1000) { $("fpsTxt").textContent = "FPS " + fpsN; fpsN = 0; fpsT = now; }
    startFrame();
  }
  function startFrame() { if (!rafId) rafId = requestAnimationFrame(frame); }
  function stopFrame() { if (rafId) cancelAnimationFrame(rafId); rafId = 0; }

  function updateHud() {
    for (let i = 1; i <= 4; i++) {
      const v = +$("v" + i).value;
      let s = angToUs(toMotor(i, v)) + "µs";
      if (i === 4) s = Math.round(gripGapMm(v)) + "mm " + s;
      else if (calibMode) { const o = calOf(i); s = "(" + (o >= 0 ? "+" : "") + o + ") " + s; }
      $("u" + i).textContent = s;
    }
    $("u5").textContent = sim.roller ? angToUs(90 + sim.roller) + "µs" : t("row.cut");
    $("u6").textContent = angToUs(+$("flagVal").value + 90) + "µs";
    const b = simBusy() || sim.roller !== 0 || seqRunning || tl.playing;
    $("lampBusy").className = b ? "lamp busy" : "lamp";
    $("lampBusyTxt").textContent = sim.released ? t("hdr.released") : tl.playing ? t("hdr.playing") : b ? t("hdr.working") : t("hdr.idle");
    $("calibTxt").textContent = hasCal() ? t("cal.txt") + " " + cal.map(v => (v >= 0 ? "+" : "") + v).join(" / ") : "";
  }
  const GRIP_K = 135 / 180;
  const gripGapMm = v => 45 - (v * GRIP_K / 180) * 30;   // 0 = 열림 45mm, 180 = 약 22mm

  /* ===================== 조종 ===================== */
  function setSlider(i, v) { const w = clampCh(i, v); $("j" + i).value = w; $("v" + i).value = w; }
  function setJoint(i, v) {
    v = clampCh(i, +v || 0);
    setSlider(i, v);
    simMove(i - 1, v);
    liveArmTick(true);                                   // 손을 뗀 값은 꼭 보낸다
  }
  for (let i = 1; i <= 4; i++) {
    $("j" + i).addEventListener("input", e => {
      if (tl.playing) setPlay(false);
      const w = clampCh(i, +e.target.value); $("v" + i).value = w; simMove(i - 1, w);
      liveArmTick();                                     // 끄는 동안에도 따라오게 — 0.1초에 한 번, 최신 값만
    });
    $("j" + i).addEventListener("change", e => setJoint(i, e.target.value));
    $("v" + i).addEventListener("change", e => setJoint(i, e.target.value));
  }
  const armVals = () => [1, 2, 3, 4].map(i => clampCh(i, +$("v" + i).value || 0));

  // −/+ 미세조정 (클릭 1°, 길게 누르면 연속) — 영점 모드에서는 ch1-3 보정값
  function nudge(ch, dir) {
    if (calibMode && ch <= 3) {
      cal[ch - 1] = clamp(cal[ch - 1] + dir, -90, 90);
      saveCal();
      if ($("liveArm").checked) sendArmNow(true);
      return;
    }
    if (tl.playing) setPlay(false);
    const v = clampCh(ch, +$("v" + ch).value + dir);
    setSlider(ch, v);
    simMove(ch - 1, v);
    liveArmTick();
  }
  document.querySelectorAll(".nb").forEach(btn => {
    const ch = +btn.dataset.ch, dir = +btn.dataset.dir;
    let to = 0, iv = 0;
    const stop = () => { clearTimeout(to); clearInterval(iv); to = iv = 0; };
    btn.addEventListener("pointerdown", e => {
      e.preventDefault(); btn.setPointerCapture(e.pointerId);
      nudge(ch, dir);
      to = setTimeout(() => { iv = setInterval(() => nudge(ch, dir), 60); }, 350);
    });
    ["pointerup", "pointercancel", "lostpointercapture"].forEach(ev => btn.addEventListener(ev, stop));
  });

  $("btnCalib").onclick = function () {
    calibMode = !calibMode;
    this.classList.toggle("on", calibMode);
    document.body.classList.toggle("calib", calibMode);
    $("btnCalibReset").hidden = !calibMode;
    $("calibHelp").hidden = !calibMode;
    if (calibMode) { if (!$("liveArm").checked) log(t("log.calLive"), "sys"); sendArmNow(true); }
  };
  $("btnCalibReset").onclick = () => { cal = [0, 0, 0]; saveCal(); sendArmNow(true); log(t("log.calReset"), "sys"); };

  $("btnArmMove").onclick = () => send("#m:" + armVals().join(",") + "!");
  $("btnArmHome").onclick = () => {
    setPlay(false);
    [1, 2, 3, 4].forEach(i => setSlider(i, 90)); $("flag").value = $("flagVal").value = 0;
    send("#home!");
    if (hasCal()) send("#m:90,90,90,90!", { local: false });   // 펌웨어 홈(90)에 보정값 반영
  };
  $("btnReset").onclick = () => {
    setPlay(false);
    [90, 90, 90, 0].forEach((v, i) => { setSlider(i + 1, v); simMove(i, v); });
    liveArmTick(true);
  };
  $("btnSpeed").onclick = () => {
    const ch = +$("spdJoint").value, dps = +$("spdVal").value;
    if (ch >= 1 && ch <= 4) userDps[ch - 1] = dps;
    send("#s:" + ch + "," + dps + "!");
  };
  $("easing").onchange = e => send("#e:" + (e.target.checked ? 1 : 0) + "!");

  // 한 축씩 천천히 가운데로. 집게 → 팔꿈치 → 어깨 → 회전 (회전을 마지막에 둬서 팔이 펴진 채 옆으로 휩쓸지 않게)
  async function slowHome() {
    if (slowHoming || seqRunning) { log(t("log.slowHomeBusy"), "err"); return; }
    slowHoming = true; seqAbort = false;
    $("btnSlowHome").disabled = true;
    setPlay(false);
    log(t("log.slowHomeRun"), "sys");
    try {
      for (const ch of [1, 2, 3]) send("#s:" + ch + "," + SLOW_DPS + "!");
      send("#s:4," + SLOW_DPS * 2 + "!");
      for (const [ch, target] of [[4, 0], [3, 90], [2, 90], [1, 90]]) {
        if (seqAbort) break;
        setSlider(ch, target);
        send("#j:" + ch + "," + target + "!");
        await waitDone(12000);
      }
    } finally {
      slowHoming = false;
      $("btnSlowHome").disabled = false;
      log(seqAbort ? t("log.seqStopped") : t("log.slowHomeDone"), "sys");
    }
  }
  $("btnSlowHome").onclick = slowHome;
  $("btnOff").onclick = () => { setPlay(false); send("#off!"); };
  $("btnOn").onclick = () => send("#on!");
  $("liveArm").onchange = e => { if (e.target.checked) sendArmNow(true); else L.cancelStream(); };

  /* ── 자세 (이 컴퓨터에 저장) ── */
  let poses = {};
  try { poses = JSON.parse(localStorage.getItem(PKEY) || "{}") || {}; } catch (e) {}
  if (!Object.keys(poses).length) poses = { home: [90, 90, 90, 90], pick: [40, 120, 110, 30], place: [90, 120, 110, 150] };
  for (const k of Object.keys(poses)) poses[k] = (poses[k] || []).slice(0, 4).map((v, i) => clampCh(i + 1, +v));
  function savePoses() { try { localStorage.setItem(PKEY, JSON.stringify(poses)); } catch (e) {} renderPoses(); }
  function renderPoses() {
    const box = $("presets"); box.innerHTML = "";
    for (const [name, v] of Object.entries(poses)) {
      const b = document.createElement("button");
      b.type = "button"; b.textContent = name; b.title = v.join(",") + "  " + t("pose.del");
      b.onclick = ev => {
        if (ev.shiftKey) { delete poses[name]; savePoses(); return; }
        setPlay(false);
        const w = v.map((a, i) => clampCh(i + 1, a));
        w.forEach((a, i) => setSlider(i + 1, a));
        send("#m:" + w.join(",") + "!");
      };
      box.appendChild(b);
    }
  }
  $("btnPresetSave").onclick = () => {
    const name = $("presetName").value.trim().replace(/\s+/g, "_");     // 순서 프로그램이 "pose 이름" 한 낱말로 부른다
    if (!name) { log(t("log.poseName"), "err"); return; }
    poses[name] = armVals(); savePoses(); $("presetName").value = "";
  };
  $("presetName").addEventListener("keydown", e => { if (e.key === "Enter" && !e.isComposing) $("btnPresetSave").click(); });
  $("btnPoseFileSave").onclick = () => {
    const v = armVals(), o = {};
    DEFAULT_JOINT_NAMES.forEach((n, i) => { o[n] = v[i]; });
    download("pose.json", new Blob([JSON.stringify(o, null, 2)], { type: "application/json" }));
  };
  $("btnPoseFileLoad").onclick = () => $("poseFileIn").click();
  $("poseFileIn").addEventListener("change", async e => {
    const f = e.target.files[0]; e.target.value = ""; if (!f) return;
    try {
      const d = JSON.parse(await f.text());
      let v;
      if (Array.isArray(d)) v = d.slice(0, 4);
      else v = DEFAULT_JOINT_NAMES.map((n, i) => d[n] ?? d["ch" + (i + 1)] ?? Object.values(d)[i]);
      v = v.map((x, i) => isNaN(+x) ? +$("v" + (i + 1)).value : clampCh(i + 1, +x));
      setPlay(false);
      v.forEach((a, i) => setSlider(i + 1, a));
      send("#m:" + v.join(",") + "!");
      log(t("log.poseLoaded", { name: f.name, v: v.join(",") }), "sys");
    } catch (err) { log(t("log.poseErr", { msg: err.message }), "err"); }
  });

  /* ── 컨베이어: 슬라이더 = 빠르기(15~40, 그 아래는 모터가 안 돎), 단추 = 방향 ── */
  function beltGo(dir) {
    beltDir = dir;
    const v = clamp(Math.round(Math.abs(+$("rollerVal").value) || BELT_MIN), BELT_MIN, BELT_MAX);
    $("roller").value = $("rollerVal").value = v;
    send("#m1:" + dir * v + "!");
  }
  $("roller").addEventListener("input", e => { $("rollerVal").value = e.target.value; if (beltDir) sim.roller = beltDir * +e.target.value; });
  $("roller").addEventListener("change", () => { if (beltDir) beltGo(beltDir); });
  $("rollerVal").addEventListener("change", e => { $("roller").value = e.target.value; if (beltDir) beltGo(beltDir); });
  $("btnBeltFwd").onclick = () => beltGo(1);
  $("btnBeltBack").onclick = () => beltGo(-1);
  $("btnRollerStop").onclick = () => { beltDir = 0; send("#m1:0!"); };
  $("flag").addEventListener("input", e => { $("flagVal").value = e.target.value; simMove(4, +e.target.value + 90); });
  $("flag").addEventListener("change", e => send("#m2:" + e.target.value + "!"));
  $("flagVal").addEventListener("change", e => { $("flag").value = e.target.value; send("#m2:" + e.target.value + "!"); });

  /* ── 멈춰! — 줄 서 있던 명령을 버리고 곧바로 보낸다 ── */
  function eStop() {
    seqAbort = true;
    applyLocal("#stop!"); beltDir = 0;
    log("#stop!" + (L.connected ? "" : "   " + t("log.sim")), "tx");
    L.urgent("#stop!");
    setPlay(false);                                      // 재생 속도 복원(#e · #s)은 멈춤 뒤에 간다
  }
  $("btnStop").onclick = eStop;
  document.addEventListener("keydown", e => { if (e.key === "Escape") { e.preventDefault(); eStop(); } });
  $("btnPos").onclick = () => send("#pos!", { local: false });
  $("btnSend").onclick = () => { const c = $("cmd").value.trim(); if (c) { send(c); $("cmd").value = ""; } };
  $("cmd").addEventListener("keydown", e => { if (e.key === "Enter" && !e.isComposing) $("btnSend").click(); });
  $("btnClear").onclick = () => { term.innerHTML = ""; };

  /* ===================== 순서 프로그램 ===================== */
  // 멈춤을 누르면 긴 wait 도 곧바로 끝나게 — 조금씩 잔다
  async function nap(ms) { const end = Date.now() + ms; while (!seqAbort && Date.now() < end) await sleep(Math.min(50, end - Date.now())); }
  async function waitDone(timeoutMs = 15000) {
    const t0 = Date.now();
    if (!L.connected) { while (simBusy() && !seqAbort && Date.now() - t0 < timeoutMs) await sleep(60); return; }
    await L.drain();                                     // 움직임 명령이 실제로 나간 뒤부터 기다린다
    busy = true;
    // 펌웨어는 이동이 끝나면 스스로 "Moved: ..." 를 보낸다. /board/read 로 그 줄을 곧바로 받는다 (0.3초 폴링을 기다리지 않게).
    // #busy 확인은 그 줄을 놓쳤을 때를 위한 백업 — 1초에 한 번만 (자주 쏘면 재생 중 #m 과 시리얼을 다툰다)
    let after = L.lastTx, lastPoll = Date.now();
    while (busy && !seqAbort && L.connected && Date.now() - t0 < timeoutMs) {
      const ln = await L.read(after, 0.4);
      if (ln) {
        after = ln.seq;
        if (/^(Moved|Stopped):/.test(ln.text) || ln.text === "0") busy = false;
        continue;
      }
      if (Date.now() - lastPoll >= 1000) { lastPoll = Date.now(); await send("#busy!", { local: false, silent: true }); await L.drain(); }
    }
  }
  $("btnSeqExample").onclick = () => {
    $("seq").value = ["pose home", "waitdone",
                      "#m2:0!", "wait 400",
                      "#m1:45,2000!", "wait 2100",
                      "#m2:90,1200!", "wait 1400",
                      "pose pick", "waitdone",
                      "#j:4,150!", "wait 500",
                      "pose place", "waitdone",
                      "#j:4,30!", "wait 400"].join("\n");
  };
  async function runSeq() {
    if (seqRunning || slowHoming) return;
    const lines = $("seq").value.split("\n").map(s => s.trim()).filter(s => s && !s.startsWith("# ") && !s.startsWith("//"));
    if (!lines.length) { log(t("log.seqEmpty"), "err"); return; }
    setPlay(false);
    seqRunning = true; seqAbort = false;
    $("btnSeqRun").disabled = true; $("btnSeqStop").disabled = false;
    log(t("log.seqStart"), "sys");
    if (window.vapiStat) vapiStat("factory_seq");
    try {
      let again;
      do {
        again = false;
        for (const line of lines) {
          if (seqAbort) break;
          let x;
          if ((x = line.match(/^wait\s+(\d+)$/i))) await nap(+x[1]);
          else if (/^waitdone$/i.test(line)) await waitDone();
          else if (/^loop$/i.test(line)) { again = true; break; }        // 처음으로 — 멈춤을 누를 때까지
          else if ((x = line.match(/^pose\s+(\S+)$/i))) {
            const p = poses[x[1]];
            if (!p) { log(t("log.poseMissing", { name: x[1] }), "err"); seqAbort = true; break; }
            p.forEach((a, i) => setSlider(i + 1, a));
            send("#m:" + p.join(",") + "!");
          }
          else if (line.startsWith("#")) { send(line); await nap(30); }
          else { log(t("log.parseFail", { line }), "err"); seqAbort = true; break; }
        }
        if (again && !seqAbort) await sleep(0);
      } while ((again || $("seqLoop").checked) && !seqAbort);
    } finally {
      seqRunning = false;
      $("btnSeqRun").disabled = false; $("btnSeqStop").disabled = true;
      log(seqAbort ? t("log.seqStopped") : t("log.seqDone"), "sys");
    }
  }
  $("btnSeqRun").onclick = runSeq;
  $("btnSeqStop").onclick = () => { seqAbort = true; };

  /* ===================== 창이 가려지면 / 다시 보이면 =====================
     가려진 창은 아무도 보지 않는다 — 재생·순서가 로봇을 계속 움직이면 안 된다.
     움직이던 중이었으면 멈춤까지 보내고, 받은 줄 읽기와 3D 그리기도 쉰다. */
  if (window.EL_WIN) {
    EL_WIN.onHide(() => {
      const moving = tl.playing || seqRunning || slowHoming;
      seqAbort = true;
      L.cancelStream();
      if (moving) { applyLocal("#stop!"); L.urgent("#stop!"); log(t("log.hidden"), "sys"); }
      setPlay(false);
      L.stop(); stopFrame();
    });
    EL_WIN.onShow(() => { L.start(); if (S.ok) S.resize(); resizeTl(); startFrame(); });
  }

  $("langButton").addEventListener("click", () => {
    try { localStorage.setItem("vapiLang", LANG === "ko" ? "en" : "ko"); } catch (e) {}
    location.reload();
  });

  /* ── 시작 ── */
  paintText();
  $("tlPlay").innerHTML = IC.play;
  kfCount(); renderPoses(); paintLink();
  if (S.ok) S.relabel();
  resizeTl();
  new ResizeObserver(resizeTl).observe(tlWrap);
  if (!(window.EL_WIN && EL_WIN.hidden)) { L.start(); startFrame(); }
  log(t("log.ready"), "sys");

  /* 시험용 */
  window.EL_FACTORY = {
    link: L, sim, tl, scene: S, get poses() { return poses; }, send, armVals, setSlider, eStop, runSeq, waitDone,
    get connected() { return L.connected; }, get seqRunning() { return seqRunning; }, get busy() { return busy; },
    addKeyframe, setPlay
  };
})();
