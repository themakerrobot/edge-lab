/* 시스템 상태 오버레이 — 다섯 페이지가 함께 쓴다.
 *
 * 페이지 아래를 차지하던 상태바를 없애고, 헤더의 작은 버튼으로 열고 닫는
 * 반투명 패널로 바꾼다. 화면은 아이 작업 공간이 넓어야 하고, 장치 정보는
 * 궁금할 때만 보면 되는 것이기 때문.
 *
 * 쓰는 법 — 페이지 <head> 나 </body> 앞에 한 줄:
 *     <script src="/lib/sysbar.js"></script>
 * 헤더의 .h-tools 안(맨 앞)에 버튼이 자동으로 붙고, 패널은 우상단에 뜬다.
 *
 * 넣는 정보는 "어느 PC 에서나 되는 것"만 — 장치 칩(CPU/GPU/NPU), 마지막 실행,
 * CPU 사용률, 메모리. GPU·NPU 사용률은 넣지 않는다(성능 카운터가 드라이버마다
 * 있기도 없기도 해서 어떤 PC 에서는 빈칸이 되고, 그게 고장으로 읽힌다).
 *
 * 기존 페이지 코드는 그대로 둔다 — chipCPU/chipGPU/chipNPU, stCPU/stGPU/stNPU 등
 * 쓰던 id 를 패널 안에 그대로 옮겨 담으므로 각 페이지의 점멸·수치 코드가 계속 돈다.
 * 페이지마다 다른 계기판(last/exec/runs, 상태, fps)은 옮겨 온 것을 그대로 쓴다.
 */
(function () {
  "use strict";

  var CSS = [
    "#sysPanel{position:fixed;top:56px;right:14px;z-index:80;display:none;",
    "  flex-wrap:wrap;align-items:center;gap:7px 14px;max-width:360px;",
    "  background:rgba(255,253,246,.9);backdrop-filter:blur(3px);",
    "  border:1.5px solid var(--line-d,#4a3f2e);border-radius:3px;padding:10px 14px;",
    "  font-family:Menlo,Consolas,ui-monospace,monospace;font-size:.82rem;",
    "  letter-spacing:.02em;color:var(--ink-2,#4a423a);",
    "  box-shadow:0 3px 14px rgba(44,74,124,.2);}",
    "#sysPanel.open{display:flex;}",
    "#sysPanel .meter{display:flex;flex-wrap:wrap;gap:4px 12px;}",
    "#sysPanel .k{color:#6b6255;}",
    "#sysPanel .v{color:var(--ink,#2a2620);font-variant-numeric:tabular-nums;}",
    "#sysPanel .sysrow{flex:1 0 100%;display:flex;gap:12px;}",
    "#sysBtn{display:inline-flex;align-items:center;justify-content:center;",
    "  background:#fff;border:1.5px solid var(--line-d,#4a3f2e);color:var(--ink-2,#4a423a);",
    "  min-width:46px;height:34px;padding:0 10px;border-radius:var(--r,3px);cursor:pointer;}",
    /* 글꼴·크기·굵기는 lib/ui.css 가 헤더 단추 전부에 한 번에 정한다.
       여기서 또 정하면 이 단추만 달라 보인다(전에 고정폭 700 이라 혼자 굵었다). */
    "#sysBtn.idle{color:var(--ink-2,#4a423a);opacity:.75;}",
    "#sysBtn.open{background:var(--ink,#2a2620);color:#fff;border-color:var(--ink,#2a2620);}",
    "#sysBtn.busy{border-color:var(--pen-red,#b4451c);color:var(--pen-red,#b4451c);",
    "  animation:sysblink 1s infinite;}",
    "@keyframes sysblink{50%{opacity:.35;}}"
  ].join("\n");

  function el(tag, attrs) {
    var e = document.createElement(tag);
    for (var k in attrs) { if (attrs.hasOwnProperty(k)) e.setAttribute(k, attrs[k]); }
    return e;
  }

  /* 패널 알맹이 — 여섯 페이지가 똑같다. 페이지 상태바를 옮겨 담지 않고
     여기서 직접 만든다(옮겨 담으면 페이지마다 항목이 달라진다).
     한 칸에 이름표를 여러 개 다는 이유: 페이지마다 같은 뜻을 다른 id 로
     갱신해 왔기 때문(마지막 시간 = sysElapsed / devLast). 페이지 코드를
     고치지 않고도 같은 자리에 값이 들어간다. */
  var PANEL = [
    '<span class="chip" id="chipCPU"><span class="dot"></span>CPU',
    '  <span class="st" id="stCPU"></span></span>',
    '<span class="chip" id="chipGPU"><span class="dot"></span>GPU',
    '  <span class="st" id="stGPU"></span></span>',
    '<span class="chip" id="chipNPU"><span class="dot"></span>NPU',
    '  <span class="st" id="stNPU"></span></span>',
    '<span class="meter">',
    '  <span><span class="k">last</span> ',
    '    <span class="v" id="sysElapsed"><span id="devLast">--</span></span></span>',
    '  <span><span class="k">exec</span> ',
    '    <span class="v" id="sysDevice"><span id="devExec">--</span></span></span>',
    '  <span><span class="k">runs</span> ',
    '    <span class="v" id="sysRuns"><span id="devCalls">0</span></span></span>',
    '  <span id="fpsBox" style="display:none;"><span class="k">fps</span> ',
    '    <span class="v" id="sysFps">--</span></span>',
    '  <span><span class="k" id="txtRunState">state</span> ',
    '    <span class="v" id="runState">-</span></span>',
    '</span>',
    '<span class="sysrow">',
    '  <span><span class="k">이름</span> <span class="v" id="sysWho">--</span></span>',
    '  <span><span class="k">CPU</span> <span class="v" id="sysCpu">--</span></span>',
    '  <span><span class="k">RAM</span> <span class="v" id="sysRam">--</span></span>',
    '</span>'
  ].join("\n");

  function start() {
    /* 페이지의 옛 상태바는 지운다 — 단, 장치 칩이 든 것만.
       점검 페이지처럼 칩 없이 그 페이지 내용(장치 목록·작품 수)을 보여 주는
       줄은 화면에 그대로 있어야 한다. */
    var old = document.getElementById("sysbar") || document.getElementById("devbar") ||
              document.querySelector(".sysbar") || document.querySelector(".devbar");
    if (old && !old.querySelector("#chipCPU")) old = null;
    if (old && old.parentNode) old.parentNode.removeChild(old);

    var style = el("style"); style.textContent = CSS;
    document.head.appendChild(style);

    var panel = el("div", { id: "sysPanel" });
    panel.innerHTML = PANEL;
    document.body.appendChild(panel);

    /* 페이지마다 하나씩 더 보고 싶은 값이 있다 — 파이썬은 실행 상태, 가르치기는 fps.
       페이지가 <body data-sys="state"> 처럼 스스로 밝히게 한다(모듈이 페이지를
       추측하지 않도록). 밝히지 않은 항목은 감춘다. */
    var want = (document.body.getAttribute("data-sys") || "").split(/[,\s]+/);
    ["state", "fps"].forEach(function (k) {
      if (want.indexOf(k) >= 0) return;
      var box = panel.querySelector(k === "fps" ? "#fpsBox" : "#runState");
      var wrap = (k === "fps") ? box : (box && box.parentNode);
      if (wrap) wrap.style.display = "none";
    });

    /* 버튼은 아이콘이 아니라 "지금 일하는 장치"를 글자로 보여 준다.
       뜻 없는 그림보다 낫고, 이 앱의 핵심(이 컴퓨터가 AI 를 돌린다)이 헤더에 늘
       보인다. 돌고 있으면 그 장치 이름이 뜨고, 쉬고 있으면 마지막에 쓴 장치를
       흐리게 남긴다. 누르면 자세한 판이 열린다. */
    var btn = el("button", { id: "sysBtn", type: "button",
                             title: "이 컴퓨터 상태 — CPU · GPU · NPU · 메모리",
                             "aria-label": "시스템 상태" });
    btn.textContent = "AI";
    var tools = document.querySelector(".h-tools");
    var lang = document.getElementById("langButton");
    if (lang && lang.parentNode) lang.parentNode.insertBefore(btn, lang.nextSibling);
    else if (tools) tools.appendChild(btn);
    else { btn.style.position = "fixed"; btn.style.top = "14px"; btn.style.right = "14px";
           btn.style.zIndex = "81"; document.body.appendChild(btn); }

    var timer = null;
    async function poll() {
      try {
        var j = await (await fetch("/system")).json();
        var m = j.mem;
        document.getElementById("sysRam").textContent =
          m ? (m.used_gb + " / " + m.total_gb + " GB (" + m.percent + "%)") : "--";
        document.getElementById("sysCpu").textContent =
          (j.cpu === null || j.cpu === undefined) ? "--" : (j.cpu + "%");
      } catch (e) { /* 서버가 아직이면 다음 번에 */ }
    }
    /* 설정 화면에서 이름을 바꾸면 바로 반영되게 창구를 하나 열어 둔다.
       (점검 페이지가 이름을 저장한 뒤 이 함수를 부른다) */
    window.vapiSetWho = function (nm) {
      var el2 = document.getElementById("sysWho");
      if (el2 && nm) { el2.textContent = nm; whoLoaded = true; }
    };
    var whoLoaded = false;
    async function loadWho() {
      if (whoLoaded) return;
      try {
        var j = await (await fetch("/system/workdir")).json();
        var nm = (j.data && j.data.name) || "";
        if (nm) {
          document.getElementById("sysWho").textContent = nm;
          whoLoaded = true;                 // 한 번 읽으면 그대로 둔다
        }
      } catch (e) { /* 서버가 아직이면 다음에 열 때 */ }
    }
    function setOpen(on) {
      panel.classList.toggle("open", on);
      btn.classList.toggle("open", on);
      clearInterval(timer); timer = null;
      if (on) { poll(); loadWho(); timer = setInterval(poll, 2000); }
    }
    btn.addEventListener("click", function (ev) {
      ev.stopPropagation();
      setOpen(!panel.classList.contains("open"));
    });
    document.addEventListener("click", function (ev) {      /* 바깥을 누르면 닫힌다 */
      if (!panel.classList.contains("open")) return;
      if (panel.contains(ev.target) || ev.target === btn) return;
      setOpen(false);
    });
    document.addEventListener("keydown", function (ev) {
      if (ev.key === "Escape" && panel.classList.contains("open")) setOpen(false);
    });

    /* 패널이 닫혀 있어도 "지금 일하는 중"은 보이게 — 칩이 켜지면 버튼도 점멸 */
    var chips = ["chipCPU", "chipGPU", "chipNPU"].map(function (id) {
      return document.getElementById(id);
    }).filter(Boolean);
    /* AI 가 일하는 동안 불이 들어오게 한다.
       추론을 부르는 자리가 페이지마다 흩어져 있어서(써보기·파이썬·대화는 아예
       칩을 켜지 않았다), 페이지를 고치는 대신 fetch 를 여기서 한 번 감싼다.
       그러면 어느 화면에서 무엇을 부르든 같은 규칙으로 불이 들어온다.

       불을 켤 주소만 고른다 — 그림·소리 파일이나 목록 조회에는 켜지 않는다. */
    var AI_PATHS = /^\/(vlm|object|face|hand|pose|chat|speech|custom\/(predict|train|test))/;
    var busyCount = 0;
    var lastDevice = "";        // 서버가 알려 준 마지막 장치 (X-Device)
    var runCount = 0;

    /* 판 안의 계기판도 같이 채운다. 페이지마다 이름이 달라 둘 다 본다. */
    function put(a, b, text) {
      [a, b].forEach(function (id) {
        var el = document.getElementById(id);
        if (el) el.textContent = text;
      });
    }
    function report(ms) {
      runCount++;
      put("sysElapsed", "devLast", ms + " ms");
      put("sysRuns", "devCalls", String(runCount));
      if (lastDevice) put("sysDevice", "devExec", lastDevice);
    }

    function chipFor(dev) {
      var id = "chip" + String(dev || "").toUpperCase();
      return document.getElementById(id);
    }
    function lightOn(dev) {
      busyCount++;
      var c = chipFor(dev) || chips[0];         // 장치를 모르면 CPU 로 표시
      if (c) c.classList.add("busy");
    }
    function lightOff() {
      if (--busyCount > 0) return;              // 여러 개가 겹쳐 돌 수 있다
      busyCount = 0;
      chips.forEach(function (c) { c.classList.remove("busy"); });
    }

    if (window.fetch && !window.__vapiFetchWrapped) {
      window.__vapiFetchWrapped = true;
      var rawFetch = window.fetch.bind(window);
      window.fetch = function (url, opt) {
        var path = "";
        try { path = new URL(url, location.origin).pathname; } catch (e) { path = String(url); }
        if (!AI_PATHS.test(path)) return rawFetch(url, opt);

        var t0 = performance.now();
        lightOn(lastDevice);                    // 지난번에 쓴 장치로 먼저 켠다
        return rawFetch(url, opt).then(function (r) {
          var ms = Math.round(performance.now() - t0);
          /* 서버는 어느 장치로 돌렸는지 응답 본문에 담아 준다("device").
             본문은 페이지가 읽어야 하므로 사본을 떠서 본다 — 원본을 읽어 버리면
             페이지 쪽에서 두 번 읽지 못해 화면이 빈다. */
          try {
            r.clone().json().then(function (j) {
              var dev = j && (j.device || (j.data && j.data.device));
              if (dev) {
                lastDevice = String(dev).toUpperCase();
                var c = chipFor(lastDevice);
                if (c && busyCount > 0) {
                  chips.forEach(function (x) { x.classList.remove("busy"); });
                  c.classList.add("busy");
                }
              }
              report(ms);
              lightOff();
            }, function () { report(ms); lightOff(); });     // JSON 이 아니면(그림 등)
          } catch (e) { report(ms); lightOff(); }
          return r;
        }, function (e) { lightOff(); throw e; });
      };
    }

    /* 어느 칩이 도는지 보고 버튼 글자를 바꾼다.
       칩 id 는 chipCPU/chipGPU/chipNPU — 뒤 세 글자가 곧 장치 이름이다.
       도는 동안만 장치 이름이고, 끝나면 바로 AI 로 돌아온다 —
       전에는 마지막 장치를 흐리게 남겼는데, 실행이 끝났는지가 안 읽혔다. */
    function nameOf(chip) {
      return String(chip.id || "").replace(/^chip/, "") || "AI";
    }
    function paintBtn() {
      var hot = null;
      for (var i = 0; i < chips.length; i++) {
        if (chips[i].classList.contains("busy")) { hot = chips[i]; break; }
      }
      if (hot) {
        btn.textContent = nameOf(hot);
        btn.classList.add("busy");
        btn.classList.remove("idle");
      } else {
        btn.textContent = "AI";
        btn.classList.remove("busy");
        btn.classList.remove("idle");
      }
    }
    if (chips.length && window.MutationObserver) {
      var mo = new MutationObserver(paintBtn);
      chips.forEach(function (c) {
        mo.observe(c, { attributes: true, attributeFilter: ["class"] });
      });
      paintBtn();
    }
  }

  /* 설정 단추에 쓰는 사람 이름을 붙인다 — "내 설정" 이라는 뜻이 되고,
     이름이 제대로 잡혔는지 매번 설정에 들어가 보지 않아도 안다.
     이름을 따로 정하지 않았으면(윈도우 로그인 이름을 쓰는 상태) 톱니만 둔다 —
     admin·user01 같은 계정명이 헤더에 뜨면 오히려 어수선하다. */
  async function paintName() {
    var link = document.getElementById("optionsLink");
    if (!link) return;                       // 톱니가 없는 페이지(서브 화면)
    try {
      var r = await fetch("/system/workdir");
      var d = (await r.json()).data || {};
      if (d.name && window.vapiSetWho) window.vapiSetWho(d.name);   // 오버레이도 함께
      if (!d.name || d.name_is_default) return;
      link.style.width = "auto";
      link.style.padding = "0 10px";
      link.style.gap = "7px";
      link.style.fontSize = ".88rem";
      link.innerHTML = "\u2699 <span>" + String(d.name).replace(/[<&]/g, "") + "</span>";
      link.title = d.name + " — 설정 · 점검";
    } catch (e) {}
  }

  window.vapiPaintName = paintName;         // 설정 화면이 이름을 바꾸면 다시 그리게

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () { start(); paintName(); });
  } else {
    start();
    paintName();
  }
})();
