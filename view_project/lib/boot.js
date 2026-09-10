/* 부팅(로딩) 화면 — 모델을 올리는 동안 무엇이 일어나는지 보여준다.
 *
 * 전에는 index.html(체험하기) 안에 박혀 있었다. "/" 가 곧 체험하기였으니 첫 화면에
 * 저절로 나왔는데, "/" 가 홈(런처)으로 바뀌자 첫 화면에서 사라졌다 — 홈은 그 코드를
 * 갖고 있지 않았으니까. 여기로 빼서 홈과 체험하기가 같이 쓴다.
 *
 * 쓰는 법 — <head> 안, 페이지 <style> 뒤:
 *     <script src="/lib/boot.js"></script>
 * 스스로 <style> 과 #boot 덮개를 만들어 body 맨 앞에 넣고, /ready 를 물으며
 * 진행 막대를 채운다. 준비가 끝난 세션(sessionStorage vapi-ready)이면 아예 안 그린다 —
 * 페이지를 오갈 때마다 덮개가 번쩍이면 방해가 된다.
 *
 * 그림은 전부 인라인 SVG — 파일을 더 받지 않는다.
 */
(function () {
  "use strict";

  /* 같은 세션에서 이미 로딩이 끝났다면(페이지 이동) 아예 그리지 않는다 */
  var already = false;
  try { already = sessionStorage.getItem("vapi-ready") === "1"; } catch (e) {}
  if (already) return;

  var LANG = "ko";
  try { LANG = localStorage.getItem("vapiLang") === "en" ? "en" : "ko"; } catch (e) {}

  var UI = {
    ko: {
      sub: "인터넷 없이 내 컴퓨터에서 실행돼요",
      skip: "건너뛰기", wait: "준비 중...", start: "시작하기",
      done: "준비 끝!", error: "문제가 생겼어요: ", sec: "초", min: "분 ",
      s1h: "인터넷 없이 동작해요",
      s1b: "이 프로그램은 인터넷에 연결하지 않아요. 웹캠으로 찍은 사진은 이 컴퓨터 밖으로 나가지 않고, 여기 안에서만 처리돼요.",
      s2h: "AI를 내 컴퓨터에 올리는 중이에요",
      s2b: "사물 찾기, 얼굴 분석, 손 인식, 글자 읽기, 그림 바꾸기까지 여러 개의 AI를 지금 메모리에 올리고 있어요. 아래 막대가 그 진행 상황이에요.",
      s3h: "일을 나눠서 해요",
      s3b: "컴퓨터 안에는 계산을 맡는 부품이 여러 개 있어요. 얼굴은 NPU, 그림 바꾸기는 GPU, 나머지는 CPU가 나눠 맡아 더 빠르게 움직여요.",
      s4h: "오늘 할 수 있는 것",
      s4b: "체험하기에서 AI를 눌러 보고, 블록 코딩과 파이썬으로 나만의 프로그램을 짜고, 가르치기에서 내가 직접 AI를 학습시킬 수 있어요.",
      s5h: "곧 시작해요",
      s5b: "준비가 끝나면 아래 [시작하기] 버튼이 켜져요. 먼저 웹캠이 잘 보이는지 확인해 두면 좋아요."
    },
    en: {
      sub: "Runs on this computer, no internet needed",
      skip: "Skip", wait: "Getting ready...", start: "Start",
      done: "Ready!", error: "Something went wrong: ", sec: "s", min: "m ",
      s1h: "It works without the internet",
      s1b: "This program never connects to the internet. Photos from your webcam stay on this computer and are processed right here.",
      s2h: "Loading the AI models",
      s2b: "Object detection, face analysis, hand tracking, text reading and image transforms are being loaded into memory. The bar below shows the progress.",
      s3h: "The work is shared out",
      s3b: "Your computer has several chips for computing. Faces go to the NPU, image transforms to the GPU, and the rest to the CPU — so everything runs faster.",
      s4h: "What you can do today",
      s4b: "Try the AIs in Use, write your own program in Blocks or Python, and train your very own AI in Train.",
      s5h: "Almost there",
      s5b: "The [Start] button turns on when everything is ready. It is a good moment to check that your webcam works."
    }
  };
  function T(k) { return UI[LANG][k] !== undefined ? UI[LANG][k] : UI.ko[k]; }

  var CSS = [
    "#boot{position:fixed;inset:0;z-index:100;display:flex;align-items:center;justify-content:center;",
    "  padding:20px;background:#fbf7ef;",
    "  background-image:radial-gradient(rgba(31,95,122,.07) 1px,transparent 1px);background-size:22px 22px;}",
    "#boot.done{display:none;}",
    ".boot-card{width:min(880px,100%);background:#fff;border:2px solid #4a3f2e;border-radius:4px;",
    "  box-shadow:0 2px 0 rgba(44,74,124,.2);padding:28px 32px 24px;display:flex;flex-direction:column;gap:20px;}",
    ".boot-brand{display:flex;align-items:center;gap:12px;}",
    ".boot-brand img{height:62px;}",
    ".boot-brand b{display:block;font-family:Menlo,Consolas,ui-monospace,monospace;font-size:1.6rem;line-height:1.2;color:#17475c;}",
    ".boot-brand i{font-style:normal;font-size:1.02rem;color:#4a423a;}",
    ".boot-slide{display:flex;align-items:center;gap:26px;min-height:200px;transition:opacity .35s;}",
    ".boot-slide.fade{opacity:0;}",
    ".boot-art{flex:0 0 200px;height:180px;}",
    ".boot-art svg{width:100%;height:100%;}",
    ".boot-text h2{font-family:'Gowun Dodum',sans-serif;font-size:1.5rem;color:#17475c;margin:0 0 10px;}",
    ".boot-text p{font-size:1.18rem;color:#2a2620;line-height:1.7;margin:0;}",
    ".boot-dots{display:flex;gap:8px;justify-content:center;}",
    ".boot-dots span{width:10px;height:10px;border-radius:50%;background:#9a8f7d;}",
    ".boot-dots span.on{background:#1f5f7a;}",
    ".boot-progress{display:flex;flex-direction:column;gap:5px;}",
    ".boot-bar{height:18px;background:#e6eef6;border-radius:9px;overflow:hidden;}",
    ".boot-bar>i{display:block;height:100%;width:0;background:#1f5f7a;transition:width .4s;}",
    ".boot-status{display:flex;align-items:baseline;gap:10px;font-family:Menlo,Consolas,monospace;font-size:1rem;color:#4a423a;}",
    ".boot-status #bootNow{flex:1 1 auto;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}",
    ".boot-meter{flex:0 0 auto;display:flex;align-items:baseline;gap:7px;font-variant-numeric:tabular-nums;}",
    ".boot-meter .sep{color:#9a8f7d;}",
    ".boot-meter #bootTime{color:#6b6255;}",
    ".boot-actions{display:flex;gap:8px;}",
    /* 단추는 48px — 아이 손가락 기준 (lib/tokens.css --tap) */
    ".boot-actions button{font-family:inherit;font-size:1.08rem;font-weight:600;cursor:pointer;",
    "  border:1.5px solid #4a3f2e;border-radius:6px;min-height:48px;padding:0 24px;",
    "  background:#1f5f7a;color:#fff;margin-left:auto;}",
    ".boot-actions button:disabled{background:#c4b9a5;border-color:#c4b9a5;cursor:default;}",
    ".boot-actions button.ghost{background:#fff;color:#4a423a;border-color:#9a8f7d;margin-left:0;}",
    "@media (max-width:639px){",
    "  .boot-slide{flex-direction:column;text-align:center;}",
    "  .boot-art{flex:0 0 auto;height:150px;}",
    "  .boot-text h2{font-size:1.3rem;}",
    "  .boot-text p{font-size:1.05rem;}}"
  ].join("\n");

  var HTML = [
    '<div id="boot">',
    '  <div class="boot-card">',
    '    <div class="boot-brand">',
    '      <img src="/assets/pibo-prof.png" alt="">',
    '      <span><b>edge-lab</b><i id="bootSub"></i></span>',
    '    </div>',
    '    <div class="boot-slide">',
    '      <div class="boot-art" id="bootArt"></div>',
    '      <div class="boot-text"><h2 id="bootHead"></h2><p id="bootBody"></p></div>',
    '    </div>',
    '    <div class="boot-dots" id="bootDots"></div>',
    '    <div class="boot-progress">',
    '      <div class="boot-bar"><i id="bootBar"></i></div>',
    '      <div class="boot-status">',
    '        <span id="bootNow"></span>',
    '        <span class="boot-meter"><span id="bootCount">0 / 0</span><span class="sep">·</span><span id="bootTime"></span></span>',
    '      </div>',
    '    </div>',
    '    <div class="boot-actions">',
    '      <button id="bootSkip" class="ghost" type="button"></button>',
    '      <button id="bootStart" type="button" disabled></button>',
    '    </div>',
    '  </div>',
    '</div>'
  ].join("\n");

  var ART = {
    offline: '<svg viewBox="0 0 120 105"><rect x="14" y="18" width="92" height="60" rx="5" fill="#fff" stroke="#4a3f2e" stroke-width="3"/><rect x="24" y="28" width="72" height="40" rx="3" fill="#eaf6fb"/><path d="M44 88h32l4 9H40z" fill="#9a8f7d"/><circle cx="60" cy="48" r="13" fill="none" stroke="#1f5f7a" stroke-width="3"/><path d="M60 41v9M60 55h.01" stroke="#17475c" stroke-width="3" stroke-linecap="round"/><path d="M96 14 22 90" stroke="#b4451c" stroke-width="5" stroke-linecap="round"/></svg>',
    models: '<svg viewBox="0 0 120 105"><g fill="none" stroke="#4a3f2e" stroke-width="3"><rect x="10" y="14" width="30" height="24" rx="4"/><rect x="45" y="14" width="30" height="24" rx="4"/><rect x="80" y="14" width="30" height="24" rx="4"/><rect x="10" y="44" width="30" height="24" rx="4"/><rect x="45" y="44" width="30" height="24" rx="4"/><rect x="80" y="44" width="30" height="24" rx="4"/></g><rect x="10" y="44" width="30" height="24" rx="4" fill="#1f5f7a" opacity=".35"/><rect x="45" y="14" width="30" height="24" rx="4" fill="#1f5f7a" opacity=".35"/><rect x="80" y="44" width="30" height="24" rx="4" fill="#1f5f7a" opacity=".35"/><path d="M22 84h76" stroke="#9a8f7d" stroke-width="8" stroke-linecap="round"/><path d="M22 84h44" stroke="#1f5f7a" stroke-width="8" stroke-linecap="round"/></svg>',
    chips: '<svg viewBox="0 0 120 105"><rect x="26" y="26" width="68" height="56" rx="6" fill="#fff" stroke="#4a3f2e" stroke-width="3"/><rect x="38" y="38" width="44" height="32" rx="3" fill="#eaf6fb" stroke="#17475c" stroke-width="2"/><g stroke="#4a3f2e" stroke-width="3" stroke-linecap="round"><path d="M40 26v-9M60 26v-9M80 26v-9M40 82v9M60 82v9M80 82v9M26 42h-9M26 60h-9M94 42h9M94 60h9"/></g><text x="60" y="59" font-size="13" font-family="monospace" fill="#17475c" text-anchor="middle">NPU</text></svg>',
    menus: '<svg viewBox="0 0 120 105"><rect x="8" y="24" width="32" height="56" rx="5" fill="#fff" stroke="#4a3f2e" stroke-width="3"/><rect x="44" y="24" width="32" height="56" rx="5" fill="#fff" stroke="#4a3f2e" stroke-width="3"/><rect x="80" y="24" width="32" height="56" rx="5" fill="#fff" stroke="#4a3f2e" stroke-width="3"/><circle cx="24" cy="44" r="7" fill="#1f5f7a"/><path d="M15 66h18M15 72h12" stroke="#9a8f7d" stroke-width="3" stroke-linecap="round"/><rect x="52" y="38" width="16" height="9" rx="2" fill="#2fa35c"/><rect x="52" y="50" width="16" height="9" rx="2" fill="#d97b2b"/><path d="M51 66h18M51 72h12" stroke="#9a8f7d" stroke-width="3" stroke-linecap="round"/><path d="M88 52l6 6 12-14" stroke="#1f5f7a" stroke-width="4" fill="none" stroke-linecap="round" stroke-linejoin="round"/><path d="M87 66h18M87 72h12" stroke="#9a8f7d" stroke-width="3" stroke-linecap="round"/></svg>',
    go: '<svg viewBox="0 0 120 105"><circle cx="60" cy="52" r="34" fill="#eaf6fb" stroke="#1f5f7a" stroke-width="3"/><path d="M46 52l10 11 20-24" stroke="#1f5f7a" stroke-width="6" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>'
  };
  var SLIDES = [
    { art: "offline", key: "s1" }, { art: "models", key: "s2" },
    { art: "chips", key: "s3" },   { art: "menus", key: "s4" },
    { art: "go", key: "s5" }
  ];

  function $(id) { return document.getElementById(id); }

  /* 덮개를 body 맨 앞에 심는다 — 화면이 그려지기 전에 덮여 있어야 깜빡이지 않는다 */
  function mount() {
    var st = document.createElement("style");
    st.textContent = CSS;
    document.head.appendChild(st);
    var wrap = document.createElement("div");
    wrap.innerHTML = HTML;
    document.body.insertBefore(wrap.firstElementChild, document.body.firstChild);
    boot();
  }

  function boot() {
    var box = $("boot");
    var idx = 0, ready = false, timer = null, shown = false;

    function paint() {
      var sl = SLIDES[idx];
      $("bootArt").innerHTML = ART[sl.art];
      $("bootHead").textContent = T(sl.key + "h");
      $("bootBody").textContent = T(sl.key + "b");
      $("bootDots").innerHTML = SLIDES.map(function (_, i) {
        return '<span class="' + (i === idx ? "on" : "") + '"></span>';
      }).join("");
    }
    function next() {
      var slide = box.querySelector(".boot-slide");
      slide.classList.add("fade");
      setTimeout(function () {
        idx = (idx + 1) % SLIDES.length;
        paint();
        slide.classList.remove("fade");
      }, 350);
    }
    function finish() {
      box.classList.add("done");
      if (timer) clearInterval(timer);
    }

    /* 로딩이 끝난 뒤 다시 들어온 경우에는 안내를 띄우지 않는다.
       (블록 코딩 → 체험 실습 처럼 페이지를 오갈 때마다 나오면 방해가 된다) */
    function show() {
      if (shown) return;
      shown = true;
      box.classList.remove("done");
      $("bootSub").textContent = T("sub");
      $("bootSkip").textContent = T("skip");
      $("bootStart").textContent = T("wait");
      $("bootNow").textContent = T("wait");
      $("bootTime").textContent = "0" + T("sec");
      paint();
      timer = setInterval(next, 8000);
      $("bootSkip").addEventListener("click", finish);
      $("bootStart").addEventListener("click", function () { if (ready) finish(); });
    }

    var t0 = Date.now();
    function elapsed() {
      var s = Math.floor((Date.now() - t0) / 1000);   /* 내림 — 59.5 가 "60초" 로 보이지 않게 */
      return s < 60 ? s + T("sec") : Math.floor(s / 60) + T("min") + (s % 60) + T("sec");
    }

    function poll() {
      fetch("/ready").then(function (r) { return r.json(); }).then(function (r) {
        if (r.ready) { try { sessionStorage.setItem("vapi-ready", "1"); } catch (e) {} }
        if (r.ready && !shown) { finish(); return; }   /* 이미 준비 끝 → 바로 화면 */
        show();
        var pct = r.total ? Math.round(r.loaded / r.total * 100) : 0;
        $("bootBar").style.width = pct + "%";
        $("bootCount").textContent = r.loaded + " / " + r.total;
        $("bootTime").textContent = elapsed();
        if (r.error) {
          $("bootNow").textContent = T("error") + r.error;
          return;                                       /* 더 묻지 않는다 */
        }
        $("bootNow").textContent = r.ready
          ? T("done")
          : (LANG === "en" ? (r.current_en || "") : (r.current_ko || "")) + " ...";
        if (r.ready) {
          ready = true;
          $("bootTime").textContent = elapsed();        /* 총 걸린 시간 — 느린 PC 를 가늠하는 데 쓴다 */
          var b = $("bootStart");
          b.disabled = false;
          b.textContent = T("start");
          return;                                       /* 자동 전환하지 않는다 */
        }
        setTimeout(poll, 700);
      }).catch(function () {
        show();                                         /* 서버가 아직 못 뜬 상태 → 안내를 띄운다 */
        setTimeout(poll, 700);
      });
    }
    poll();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", mount);
  else mount();
})();
