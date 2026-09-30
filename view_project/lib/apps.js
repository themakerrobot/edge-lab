/* 앱 목록 — 런처(/)와 체험하기(/try)가 함께 쓴다.
 *
 * 전에는 SERVICE_LIST 와 GROUPS 가 index.html 안에만 있었다. 런처를 만들면서
 * 그대로 두면 두 벌이 되어, 모델을 하나 더할 때 한쪽만 고치는 일이 생긴다.
 * 여기가 유일한 출처다.
 *
 * 쓰는 법:
 *     <script src="/lib/apps.js"></script>
 *     EL_APPS.SERVICE_LIST / EL_APPS.GROUPS / EL_APPS.APPS
 *
 * 키(예: "얼굴 인식")는 한국어 그대로 둔다 — API 매핑과 저장된 설정이 이 키를
 * 쓰고 있어서다. 화면에 보이는 글자는 name(key) 가 골라 준다.
 * 아이콘 이름은 lib/icons.js 의 것이다.
 */
(function () {
  "use strict";

  var GROUPS = [
    ["face",    "얼굴",           "Face"],
    ["body",    "몸 · 손",        "Body & hands"],
    ["object",  "사물",           "Objects"],
    ["vlm",     "말로 답하는 AI",  "AI that answers in words"],
    ["image",   "사진 바꾸기",     "Change the photo"],
    ["text",    "글자 · QR",      "Text & QR"]
  ];

  var SERVICE_LIST = {
    /* ----- 얼굴 ----- */
    "얼굴 인식": { "g": "face", "ic": "face", "api": "face/face_detect", "params": {}, "tooltip": "얼굴을 인식합니다.", "en": "Face detection", "tooltip_en": "Finds faces in the image." },
    "얼굴 분석": { "g": "face", "ic": "face", "api": "face/face_analyze", "params": {}, "tooltip": "얼굴의 나이/성별/감정/방향을 한 번에 분석합니다.", "en": "Face analysis", "tooltip_en": "Estimates age, gender, emotion and gaze direction." },
    "얼굴 감정 분석": { "g": "face", "ic": "face", "api": "face/face_emotion", "params": {}, "tooltip": "얼굴의 감정을 분석합니다.", "en": "Face emotion", "tooltip_en": "Reads the emotion on each face." },
    "얼굴 나이/성별 분석": { "g": "face", "ic": "faceAge", "api": "face/face_age_gender", "params": {}, "tooltip": "얼굴의 나이/성별을 분석합니다.", "en": "Face age / gender", "tooltip_en": "Estimates each face's age and gender." },
    "얼굴 거리·방향": { "g": "face", "ic": "faceDir", "api": "face/mesh", "params": {}, "tooltip": "카메라와의 거리(cm)와 얼굴이 보는 방향을 함께 알려줍니다.", "en": "Face distance / direction", "tooltip_en": "Tells how far the face is (cm) and which way it is looking." },
    "마스크 인식": { "g": "face", "ic": "mask", "api": "face/mask_detect", "params": {}, "tooltip": "얼굴의 마스크 착용 여부를 인식합니다.", "en": "Mask detection", "tooltip_en": "Checks whether each face is wearing a mask." },

    /* ----- 몸 · 손 ----- */
    "사람 포즈 인식": { "g": "body", "ic": "pose", "api": "object/object_pose", "params": {}, "tooltip": "인체의 17개 주요 포인트를 인식합니다.", "en": "Human pose", "tooltip_en": "Finds 17 key points of the human body." },
    "손동작 인식": { "g": "body", "ic": "hand", "api": "object/hand", "params": {}, "tooltip": "손 모양(엄지척, 브이, 주먹 등)과 손가락 21개 포인트를 인식합니다.", "en": "Hand gesture", "tooltip_en": "Recognizes hand gestures (thumbs-up, victory, fist...) and 21 finger points." },

    /* ----- 사물 ----- */
    "사물 인식": { "g": "object", "ic": "object", "api": "object/object_search", "params": {}, "tooltip": "80가지 사물의 이름/위치를 인식합니다. 사람도 함께 찾아요.", "en": "Object detection", "tooltip_en": "Finds 80 kinds of objects (people too) and where they are." },
    "사물 분할": { "g": "object", "ic": "seg", "api": "object/object_seg", "params": {}, "tooltip": "80가지 사물의 영역을 색으로 칠해 표시합니다.", "en": "Object segmentation", "tooltip_en": "Colors in the exact area of each object." },

    /* ----- 말로 답하는 AI (VLM — 몇 초 걸려요) ----- */
    "이미지 질문·설명": { "g": "vlm", "ic": "vlm", "api": "vlm/look", "params": {}, "tooltip": "사진에 대해 물어봐요. 프롬프트를 비우면 사진을 설명해 줍니다.", "en": "Ask about the image", "tooltip_en": "Ask about the photo. Leave the prompt empty to get a description." },

    /* ----- 사진 바꾸기 ----- */
    "배경 제거": { "g": "image", "ic": "bg", "api": "gan/portrait", "params": {}, "tooltip": "인물/사물만 남기고 배경을 제거합니다.", "en": "Remove background", "tooltip_en": "Keeps the subject and removes the background." },
    "화질 개선(4배)": { "g": "image", "ic": "sr", "api": "gan/sr", "params": {}, "tooltip": "이미지 화질을 4배로 개선합니다.", "en": "Upscale (4x)", "tooltip_en": "Improves the image quality four times." },
    "깊이 지도": { "g": "image", "ic": "depth", "api": "gan/depth", "params": {}, "tooltip": "멀고 가까움을 색으로 칠합니다 — 가까울수록 밝아요.", "en": "Depth map", "tooltip_en": "Colors near and far — brighter is closer." },

    /* ----- 글자 · QR ----- */
    "글자 인식": { "g": "text", "ic": "text", "api": "code/ocr", "params": {}, "tooltip": "이미지에서 문자/숫자를 인식합니다.", "en": "Text recognition", "tooltip_en": "Reads letters and numbers in the image." },
    "QR코드 인식": { "g": "text", "ic": "qr", "api": "code/barcode", "params": {}, "tooltip": "이미지에서 바코드를 인식합니다.", "en": "QR code", "tooltip_en": "Reads QR codes in the image." }
  };

  /* 앱 — 셸 바탕화면·시작 메뉴·상단바가 이 순서와 묶음(cat)대로 보여 준다.
     설명은 한 줄로 — 아이가 타일만 보고 고른다.
     cat: ai(AI 를 써 보고 가르치기) · dev(만들기 — 블록·파이썬) · tool(도구) · sys(시스템). 묶음마다 색이 다르다.
     core: 기본 앱 — 앱 가게에서 뺄 수 없다. 나머지는 아이가 앱 가게에서 빼고(el-removed) 다시 넣는다. */
  var CATS = [
    ["ai",   "AI",     "AI"],
    ["dev",  "개발",   "Develop"],
    ["tool", "도구",   "Tools"],
    ["sys",  "시스템", "System"]
  ];

  var APPS = [
    { href: "/try",     ic: "eye",    cat: "ai", core: true,   ko: "체험하기",   en: "Try it",
      ko_d: "AI 16가지를 눌러 봐요",        en_d: "Try 16 kinds of AI" },
    { href: "/talk",    ic: "talk",   cat: "ai", core: true,   ko: "대화",       en: "Talk",
      ko_d: "말하거나 써서 물어봐요",       en_d: "Ask by voice or text" },
    { href: "/train",   ic: "train",  cat: "ai", core: true,   ko: "가르치기",   en: "Train",
      ko_d: "내가 직접 AI를 가르쳐요",      en_d: "Teach the AI yourself" },
    { href: "/drive",   ic: "car",    cat: "ai",   ko: "자동차 가르치기", en: "Teach a car",
      ko_d: "내 운전을 보고 AI가 배워요",   en_d: "The AI learns from your driving" },
    { href: "/eye",  ic: "scan",  cat: "ai", ko: "AI 눈", en: "AI eye",
      ko_d: "AI 속을 들여다보고 속여 봐요", en_d: "Look inside an AI and fool it" },
    { href: "/blocks",  ic: "blocks", cat: "dev", core: true,  ko: "블록",       en: "Blocks",
      ko_d: "블록을 끼워 AI를 움직여요",    en_d: "Snap blocks to run the AI" },
    { href: "/code",    ic: "code",   cat: "dev", core: true,  ko: "파이썬",     en: "Python",
      ko_d: "themaker 로 한 줄이면 돼요",   en_d: "One line with themaker" },
    { href: "/paint",   ic: "paint",  cat: "tool", ko: "그림판",     en: "Paint",
      ko_d: "그리고 AI 에게 보여 줘요",     en_d: "Draw, then show the AI" },
    { href: "/typing",  ic: "keys",   cat: "tool", ko: "타자 연습",  en: "Typing",
      ko_d: "한글 · 영어 자판과 낱말 비",   en_d: "Korean & English, word rain" },
    { href: "/calc",    ic: "calc",   cat: "tool", ko: "계산기",     en: "Calculator",
      ko_d: "큰 수를 우리말로 읽어 줘요",   en_d: "Reads numbers out in words" },
    { href: "/notes",   ic: "note",   cat: "tool", ko: "메모장",     en: "Notes",
      ko_d: "짧은 글을 적어 둬요",          en_d: "Jot things down" },
    { href: "/recorder", ic: "mic",   cat: "tool", ko: "녹음기",     en: "Recorder",
      ko_d: "말 → 글자 → 다시 읽기",        en_d: "Speech → text → read aloud" },
    { href: "/story",   ic: "book",   cat: "tool", ko: "이야기 극장", en: "Story theater",
      ko_d: "인물마다 다른 목소리로",       en_d: "A voice for each character" },
    { href: "/works",   ic: "folder", cat: "sys", core: true,  ko: "내 작품",    en: "My work",
      ko_d: "만든 것을 한곳에서 열어요",    en_d: "Open everything you made" },
    { href: "/tasks",   ic: "gauge",  cat: "sys", core: true,  ko: "AI 작업 관리자", en: "AI task manager",
      ko_d: "어떤 AI 가 어디서 도는지",      en_d: "Which AI runs where" },
    { href: "/board",   ic: "chip",   cat: "sys",  ko: "보드",       en: "Board",
      ko_d: "보드 연결 · 명령 보내 보기",   en_d: "Connect a board, try commands" },
    { href: "/store",   ic: "store",  cat: "sys",  core: true, ko: "앱 가게", en: "App store",
      ko_d: "앱을 넣고 빼요",               en_d: "Add and remove apps" },
    { href: "/options", ic: "gear",   cat: "sys", core: true,  ko: "설정",       en: "Settings",
      ko_d: "수업 전 카메라·소리 점검",     en_d: "Check camera and sound" }
  ];


  function lang() {
    try { return localStorage.getItem("vapiLang") === "en" ? "en" : "ko"; }
    catch (e) { return "ko"; }
  }

  window.EL_APPS = {
    GROUPS: GROUPS,
    SERVICE_LIST: SERVICE_LIST,
    APPS: APPS,
    CATS: CATS,
    /* 앱 가게에서 뺀 앱 — 기본 앱(core)은 빠지지 않는다 */
    removed: function () {
      var r = [];
      try { r = JSON.parse(localStorage.getItem("el-removed") || "[]") || []; } catch (e) {}
      return r.filter(function (h) { return APPS.some(function (a) { return a.href === h && !a.core; }); });
    },
    isRemoved: function (href) { return this.removed().indexOf(href) >= 0; },
    catName: function (c, L) { var x = CATS.filter(function (k) { return k[0] === c; })[0]; return x ? ((L || lang()) === "en" ? x[2] : x[1]) : c; },
    lang: lang,
    /* 화면에 보이는 이름 — 영어 화면이면 en, 없으면 키 그대로 */
    name: function (key, L) {
      var sv = SERVICE_LIST[key];
      if (!sv) return key;
      return (L || lang()) === "en" ? (sv.en || key) : key;
    },
    tip: function (key, L) {
      var sv = SERVICE_LIST[key];
      if (!sv) return "";
      return (L || lang()) === "en" ? (sv.tooltip_en || sv.tooltip) : sv.tooltip;
    }
  };
})();
