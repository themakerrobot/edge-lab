// ═══════════════════════════════════════════════════════════
// 튜토리얼 — 파이보가 말풍선으로 화면을 한 바퀴 안내한다
//   (sense-lab 의 tour.js 방식을 edge-lab 에 맞춰 옮김)
// ═══════════════════════════════════════════════════════════
//  · 페이지별 첫 방문에 자동으로 시작한다 (localStorage 로 1회 기억)
//  · 헤더의 ? 버튼으로 언제든 다시 볼 수 있다
//  · 강조는 스포트라이트(구멍 뚫린 어두운 막) 방식 — 대상 요소는 건드리지 않는다
//
// sense-lab 과 다른 점(이 환경에 맞춘 것):
//  · 페이지 판별: <header data-tab> 이 없으므로 URL 경로로 잡는다(nav.js 와 같은 규칙).
//  · 문구: 공용 GL_T 가 없으므로 한·영을 이 파일이 직접 들고, vapiLang 으로 고른다.
//  · 색·패널: --acc/--panel 대신 --cyan/--box.
//  · ? 버튼: 이동 탭과 도구([한/영]) 사이에 놓는다.
//  · 파이보 그림: /assets/pibo-hello.png (이미 있는 자산).

(function () {
  "use strict";

  function lang() {
    try { return localStorage.getItem("vapiLang") === "en" ? "en" : "ko"; }
    catch (e) { return "ko"; }
  }
  function here() {
    var p = (location.pathname || "/").replace(/\/+$/, "");
    return p === "" ? "/" : p;
  }

  // 단계: [강조할 요소 선택자(없으면 화면 가운데), {ko, en} 문구]
  // 선택자는 페이지 분석으로 확인한 실제 id 를 쓴다. 없는 요소는 자동으로 건너뛴다.
  var TOURS = {
    "/": [
      [null, { ko: "안녕! 여기는 체험하기예요.\n내 컴퓨터 안의 AI를 눌러서 만나 봐요.",
               en: "Hi! This is Try-It.\nMeet the AI running on your own computer." }],
      ["#modelSelect", { ko: "무엇을 알아볼지 골라요.\n얼굴·사물·손·글자 같은 것들이 있어요.",
                          en: "Pick what to recognize —\nfaces, objects, hands, text, and more." }],
      ["#promptInput", { ko: "고른 것에 따라 여기에\n물어볼 말을 적기도 해요.",
                          en: "For some, type your question here." }],
      ["#captureWebcam", { ko: "웹캠으로 사진을 찍거나,\n[사진 올리기]로 가져와요.",
                            en: "Take a webcam photo,\nor upload one." }],
      ["#liveCheck", { ko: "[실시간]을 켜면 웹캠을 보며\nAI가 계속 알아봐요.",
                        en: "Turn on Live to keep\nrecognizing from the webcam." }],
      ["#mainRunButton", { ko: "준비되면 눌러서 AI에게 물어봐요.",
                            en: "Press to ask the AI." }],
      [".panel:last-child", { ko: "결과가 여기 나와요.\n마음에 들면 저장할 수도 있어요.",
                               en: "Results show here.\nYou can save the ones you like." }],
      [".nav-tab#blocksLink", { ko: "위 탭으로 블록·파이썬·가르치기로\n옮겨 다닐 수 있어요.",
                                 en: "Use the tabs above to move to\nBlocks, Python, and Train." }],
    ],
    "/blocks": [
      [null, { ko: "여기는 블록이에요.\n블록을 끼워 맞춰 AI를 움직여요.",
               en: "This is Blocks.\nSnap blocks together to run the AI." }],
      ["#exampleButton", { ko: "처음이라면 [예제]를 눌러\n만들어진 블록을 구경해요.",
                            en: "New here? Press Examples to\nload a ready-made program." }],
      ["#runButton", { ko: "[실행]으로 블록을 움직여요.\n결과는 오른쪽에 나와요.",
                        en: "Run the blocks. Results\nappear on the right." }],
      ["#saveButton", { ko: "만든 작품을 저장하고,\n[불러오기]로 다시 열어요.",
                         en: "Save your work, and\nreopen it with Load." }],
      ["#pyOpen", { ko: "내가 만든 블록이 파이썬으로\n어떻게 되는지 볼 수 있어요.",
                     en: "See how your blocks look\nas Python code." }],
    ],
    "/code": [
      [null, { ko: "여기는 파이썬이에요.\n글로 코드를 적어 AI를 움직여요.",
               en: "This is Python.\nWrite code to run the AI." }],
      ["#exampleButton", { ko: "[예제]로 짧은 코드를 불러와\n그대로 실행해 봐요.",
                            en: "Load a short example\nand run it as-is." }],
      ["#runButton", { ko: "[실행]으로 코드를 돌려요.\n결과는 가운데에 나와요.",
                        en: "Run the code. Output\nshows in the middle." }],
      ["#guideButton", { ko: "쓸 수 있는 명령이 궁금하면\n[도움말]을 열어 봐요.",
                          en: "Open Help to see the\ncommands you can use." }],
    ],
    "/train": [
      [null, { ko: "여기는 가르치기예요.\n내가 직접 AI를 가르쳐요.",
               en: "This is Train.\nTeach the AI yourself." }],
      ["#addClassBtn", { ko: "먼저 무엇과 무엇을 구별할지\n종류를 만들어요. 예: 가위·바위·보",
                          en: "First make the classes to tell\napart — e.g. rock, paper, scissors." }],
      ["#camToggle", { ko: "카메라를 켜요.",
                        en: "Turn on the camera." }],
      ["#holdShot", { ko: "종류를 고른 뒤 꾹 눌러\n예시 사진을 모아요.",
                       en: "Pick a class, then press and\nhold to collect example photos." }],
      ["#trainBtn", { ko: "예시를 다 모으면\n[학습]을 눌러요.",
                       en: "When you have enough,\npress Train." }],
      ["#testLive", { ko: "잘 배웠는지 웹캠으로\n바로 시험해 봐요.",
                       en: "Test it live with the\nwebcam right away." }],
      ["#saveBtn", { ko: "만든 AI를 저장하면\n체험하기·블록·파이썬에서 쓸 수 있어요.",
                      en: "Save your AI to use it in\nTry-It, Blocks, and Python." }],
    ],
    "/talk": [
      [null, { ko: "여기는 대화예요.\nAI와 이야기를 나눠요.",
               en: "This is Talk.\nHave a conversation with the AI." }],
      ["#micBtn", { ko: "마이크를 눌러 말하거나,\n아래에 글로 적어 보내요.",
                     en: "Press the mic to speak,\nor type below and send." }],
      ["#ttsChk", { ko: "[읽어주기]를 켜면\nAI가 목소리로 답해요.",
                     en: "Turn on Read-aloud and\nthe AI answers by voice." }],
      ["#dbAdd", { ko: "여기에 자료를 넣어 두면\nAI가 그걸 보고 답해요.",
                    en: "Add your own notes here and\nthe AI answers from them." }],
    ],
    "/options": [
      [null, { ko: "여기는 설정이에요.\n수업 전에 점검하고, 결과물을 봐요.",
               en: "This is Settings.\nCheck before class, and view results." }],
      ["#camBtn", { ko: "수업 전에 카메라·소리·마이크가\n잘 되는지 확인해요.",
                     en: "Before class, check the\ncamera, sound, and mic." }],
      ["#userName", { ko: "이름을 적어 두면\n결과물에 함께 남아요.",
                       en: "Enter a name to tag\nyour results." }],
      ["#hcToggle", { ko: "밝은 곳에서 화면이 안 보이면\n여기로 또렷하게 바꿔요.",
                       en: "Hard to see in bright light?\nSwitch to high contrast here." }],
      ["#exportBtn", { ko: "한 일을 파일로 내보내\n선생님께 드릴 수 있어요.",
                        en: "Export what you did as a\nfile to share with a teacher." }],
    ],
  };

  var steps = TOURS[here()];
  if (!steps) return;

  var UI = {
    ko: { skip: "그만 볼래요", next: "다음", done: "다 봤어요", help: "도움말" },
    en: { skip: "Skip", next: "Next", done: "Done", help: "Help" },
  };
  function T(k) { return (UI[lang()] || UI.ko)[k]; }
  function say(step) { return step[1][lang()] || step[1].ko; }

  var SEEN_KEY = "vapi-tour-" + here();
  var idx = -1, box = null;

  function el(tag, cls, parent) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (parent) parent.appendChild(e);
    return e;
  }

  function stop() {
    if (box) { box.remove(); box = null; }
    window.removeEventListener("resize", place);
    idx = -1;
    try { localStorage.setItem(SEEN_KEY, "1"); } catch (e) {}
  }

  // 대상이 없거나 숨어 있으면 다음 단계로 건너뛴다 — 페이지 상태에 따라 없는 버튼이 있다
  function usable(sel) {
    if (!sel) return true;                     // null 은 "화면 가운데" 라 항상 유효
    var t = document.querySelector(sel);
    return t && t.offsetParent !== null;
  }
  function nextUsable(from, dir) {
    var i = from;
    while (i >= 0 && i < steps.length) {
      if (usable(steps[i][0])) return i;
      i += dir;
    }
    return -1;
  }

  function place() {
    if (!box || idx < 0) return;
    var sel = steps[idx][0];
    var spot = box.querySelector(".tour-spot");
    var bub = box.querySelector(".tour-bubble");
    var target = sel ? document.querySelector(sel) : null;

    if (target && target.offsetParent !== null) {
      try { target.scrollIntoView({ block: "center" }); } catch (e) {}
      var r = target.getBoundingClientRect();
      var pad = 6;
      spot.style.display = "";
      spot.style.left = (r.left - pad) + "px";
      spot.style.top = (r.top - pad) + "px";
      spot.style.width = (r.width + pad * 2) + "px";
      spot.style.height = (r.height + pad * 2) + "px";

      var bw = Math.min(320, window.innerWidth - 24);
      bub.style.width = bw + "px";
      var left = Math.max(12, Math.min(r.left, window.innerWidth - bw - 12));
      bub.style.left = left + "px";
      var bh = bub.offsetHeight || 150;
      if (r.bottom + pad + bh + 20 < window.innerHeight) {
        bub.style.top = (r.bottom + pad + 12) + "px";
        bub.style.bottom = "";
      } else if (r.top - pad - bh - 20 > 0) {
        bub.style.top = (r.top - pad - bh - 12) + "px";
        bub.style.bottom = "";
      } else {
        bub.style.top = "";
        bub.style.bottom = "16px";
      }
    } else {
      spot.style.display = "none";
      var bw2 = Math.min(320, window.innerWidth - 24);
      bub.style.width = bw2 + "px";
      bub.style.left = Math.round((window.innerWidth - bw2) / 2) + "px";
      bub.style.top = Math.round(window.innerHeight * 0.3) + "px";
      bub.style.bottom = "";
    }
  }

  function show(i) {
    idx = i;
    if (!box) {
      box = el("div", "tour");
      el("div", "tour-spot", box);
      var bub = el("div", "tour-bubble", box);
      var img = el("img", "tour-char", bub);
      img.src = "/assets/pibo-hello.png";
      img.alt = "";
      el("div", "tour-text", bub);
      var foot = el("div", "tour-foot", bub);
      el("div", "tour-dots", foot);
      var skip = el("button", "tour-skip", foot);
      skip.type = "button";
      skip.addEventListener("click", stop);
      var next = el("button", "tour-next", foot);
      next.type = "button";
      next.addEventListener("click", function () {
        var n = nextUsable(idx + 1, 1);
        if (n < 0) stop();
        else show(n);
      });
      document.body.appendChild(box);
      window.addEventListener("resize", place);
    }
    box.querySelector(".tour-text").textContent = say(steps[i]);

    // 점: 유효한 단계만 센다(숨은 버튼은 세지 않아 개수가 정확하다)
    var live = steps.map(function (s, k) { return usable(s[0]) ? k : -1; })
                    .filter(function (k) { return k >= 0; });
    var dots = box.querySelector(".tour-dots");
    dots.innerHTML = "";
    live.forEach(function (k) { el("span", "dot" + (k === i ? " on" : ""), dots); });

    var last = nextUsable(i + 1, 1) < 0;
    box.querySelector(".tour-next").textContent = last ? T("done") : T("next");
    box.querySelector(".tour-skip").style.display = last ? "none" : "";
    box.querySelector(".tour-skip").textContent = T("skip");
    place();
    requestAnimationFrame(place);
  }

  function start() {
    if (idx >= 0) return;
    var first = nextUsable(0, 1);
    if (first >= 0) show(first);
  }
  window.tourStart = start;

  // 헤더 ? 버튼 (다시 보기) — 이동 탭과 도구([한/영]) 사이
  function addButton() {
    var tools = document.querySelector(".header .h-tools");
    if (!tools || document.getElementById("helpTourBtn")) return;
    var b = el("button", "tour-help");
    b.id = "helpTourBtn";
    b.type = "button";
    b.title = T("help");
    b.setAttribute("aria-label", T("help"));
    b.textContent = "?";
    b.addEventListener("click", start);
    var langBtn = document.getElementById("langButton");
    if (langBtn) tools.insertBefore(b, langBtn);
    else tools.appendChild(b);
  }

  /* 첫 화면에는 모델을 올리는 동안 부팅 덮개(#boot)가 떠 있다.
     그게 떠 있을 때 시작하면 짚을 요소가 아직 없고 로딩 화면까지 가린다.
     덮개가 사라진(=.done) 뒤에 시작한다. 덮개가 없는 화면은 바로 시작. */
  function bootGone() {
    var b = document.getElementById("boot");
    return !b || b.classList.contains("done") || b.offsetParent === null;
  }

  function startWhenReady() {
    if (bootGone()) { setTimeout(start, 700); return; }
    var mo = new MutationObserver(function () {
      if (bootGone()) { mo.disconnect(); setTimeout(start, 700); }
    });
    mo.observe(document.getElementById("boot"), { attributes: true, attributeFilter: ["class", "style"] });
  }

  function boot() {
    addButton();
    var seen = false;
    try { seen = localStorage.getItem(SEEN_KEY) === "1"; } catch (e) {}
    if (!seen) startWhenReady();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
