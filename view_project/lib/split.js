/* 끌어서 크기 바꾸기 — 여섯 페이지가 이 파일 하나를 쓴다.
 *
 * 쓰는 법: 나누고 싶은 상자에 data-split 을 단다.
 *     <div class="main" data-split="h" data-split-key="code">
 * 그 상자의 자식(패널) 사이마다 손잡이가 생기고, 끌면 좌우(h) 또는
 * 위아래(v) 크기가 바뀐다. 바꾼 크기는 localStorage 에 남아 다음에도 그대로.
 *
 * 페이지 JS 를 고치지 않아도 되도록 flex-basis 만 건드린다.
 * display:none 인 패널(도움말처럼 접히는 것)은 건너뛰고, 패널이 다시 열리면
 * 손잡이도 함께 살아난다.
 *
 * 좁은 화면(세로로 쌓이는 구간)에서는 스스로 물러난다 — 손잡이를 감추고
 * 저장한 크기도 풀어, 페이지의 반응형 배치가 그대로 살아나게 한다.
 */
(function () {
  "use strict";

  var MIN = 80;            // 패널이 이보다 작아지지는 않게 (기본값)

  /* 패널마다 더 큰 최소 크기가 필요할 때가 있다 — 블록판은 왼쪽 도구 칸이,
     무대는 사진이 알아볼 만한 크기가 있어야 한다. 그런 칸에는 HTML 에
     data-min="360" 을 달아 둔다. 없으면 위 기본값을 쓴다.
     (CSS 의 min-width 를 읽지 않는 이유: 나누기가 켜진 칸은 줄어들 수 있어야 해서
      공용 CSS 가 min-width 를 0 으로 덮는다 — 읽어 봐야 늘 0 이다.) */
  function minOf(panel) {
    var v = parseInt(panel && panel.getAttribute("data-min"), 10);
    return (v > 0) ? v : MIN;
  }

  /* 크기가 바뀌었다고 알린다.
     Blockly·CodeMirror 같은 것들은 "창 크기가 바뀔 때"만 스스로 다시 그린다.
     손잡이로 끌면 창 크기는 그대로라 캔버스가 옛 크기에 머문다 — 안 움직이는
     것처럼 보이는 진짜 이유. resize 를 한 번 흘려 주면 각자 알아서 맞춘다. */
  function notify() {
    try { window.dispatchEvent(new Event("resize")); } catch (e) {
      var ev = document.createEvent("Event");        // 오래된 브라우저 대비
      ev.initEvent("resize", true, true);
      window.dispatchEvent(ev);
    }
  }

  /* 예전 판이 남긴 저장값 치우기.
     ①양쪽을 다 고정해 창이 넓으면 오른쪽이 비던 판 ②써보기·가르치기·대화·점검에도
     손잡이를 달아 폭을 px 로 못박던 판 — 그때 저장된 값이 남아 있으면 고쳐도 증상이
     이어지므로, 판이 바뀔 때마다 한 번씩 지운다. */
  try {
    if (!localStorage.getItem("vapi-split-v4")) {
      for (var n = localStorage.length - 1; n >= 0; n--) {
        var k = localStorage.key(n);
        if (k && k.indexOf("vapi-split-") === 0) localStorage.removeItem(k);
      }
      localStorage.removeItem("vapi-split-v2");
      localStorage.removeItem("vapi-split-v3");
      localStorage.setItem("vapi-split-v4", "1");
    }
  } catch (e) {}

  function key(box, i) {
    return "vapi-split-" + (box.getAttribute("data-split-key") || "x") + "-" + i;
  }

  function lastPanel(box) {
    var list = panels(box);
    return list[list.length - 1];
  }

  /* 크기를 px 가 아니라 "칸 전체의 몇 %" 로 적어 둔다.
     px 로 적으면 그때의 창 폭에서만 맞다 — 파일 목록을 접었다 펴거나, 다른 화면을
     들렀다 오거나, 창 크기가 달라지면 그 px 가 더는 안 맞아서 한쪽에 빈칸이 남는다.
     비율이면 어떤 폭에서도 같은 배분이 된다. */
  function share(box, p, vertical) {
    var whole = (vertical ? box.clientHeight : box.clientWidth) || 0;
    var mine = (vertical ? p.offsetHeight : p.offsetWidth) || 0;
    if (!whole || !mine) return p.style.flexBasis;      // 잴 수 없으면 있는 값 그대로
    return (Math.max(3, Math.min(97, mine * 100 / whole))).toFixed(2) + "%";
  }

  function panels(box) {
    return Array.prototype.filter.call(box.children, function (n) {
      /* 파일 목록(#filePanel)은 크기를 나눠 갖는 패널이 아니다 — 접었다 펴는 곁칸이다.
         패널로 세면 손잡이가 그 옆에도 생겨서 엉뚱한 자리를 끌게 된다. */
      return n.nodeType === 1 && !n.classList.contains("split-bar") &&
             n.id !== "filePanel" &&
             getComputedStyle(n).display !== "none";
    });
  }

  function setup(box) {
    var dir = (box.getAttribute("data-split") || "h").toLowerCase();
    var vertical = dir === "v";

    /* 페이지가 지금 어느 방향으로 놓고 있는지 직접 물어본다.
       화면이 좁아지면 각 페이지가 스스로 세로로 쌓는데, 그 기준이 페이지마다
       다르다(860·960·1200px). 여기서 숫자를 따로 정해 두면 그 사이 폭에서
       "페이지는 세로로 쌓았는데 손잡이는 가로로 잡는" 상태가 되어, 높이가 고정돼
       창을 키워도 안 커진다. 그래서 숫자 대신 실제 배치를 본다. */
    var flow = "";
    try { flow = getComputedStyle(box).flexDirection || ""; } catch (e) {}
    var stacked = flow.indexOf("column") === 0;

    /* 손잡이는 매번 다시 만든다 — 패널이 접혔다 열리면 자리가 달라지므로 */
    Array.prototype.slice.call(box.querySelectorAll(":scope > .split-bar"))
      .forEach(function (b) { b.parentNode.removeChild(b); });

    /* 쌓여 있는데 가로로 나누려 하면 손잡이를 쓰지 않는다 — 페이지가 정한 배치를 살린다 */
    var narrow = stacked && !vertical;
    var list = panels(box);

    /* 크기를 정한 칸은 flex-shrink 도 0 으로 둔다.
       기본값 1 이면, 칸을 넓혔을 때 남는 자리가 모자라면 브라우저가 그만큼 도로 줄인다 —
       "오른쪽으로 끌어 편집기를 넓히면 놓는 순간 되돌아가는" 증상이 이것이다.
       왼쪽으로 끌 때는 줄이는 쪽이라 남는 자리가 생겨서 증상이 안 보였다.

       마지막 패널은 크기를 고정하지 않는다.
       모두 고정해 버리면 창이 그보다 넓을 때 남는 폭이 빈칸으로 남는다(창을 키우거나
       다른 화면 크기에서 열면 오른쪽이 텅 빈다). 앞쪽만 폭을 정하고, 마지막 하나가
       남는 자리를 다 먹게 둔다 — 이게 편집기들이 쓰는 방식이다. */
    list.forEach(function (p, i) {
      var last = (i === list.length - 1);
      if (narrow) { p.style.flexBasis = ""; p.style.flexGrow = ""; p.style.flexShrink = ""; return; }
      if (last) { p.style.flexBasis = "auto"; p.style.flexGrow = "1";
                  p.style.flexShrink = "1"; return; }
      var saved = null;
      try { saved = localStorage.getItem(key(box, i)); } catch (e) {}
      if (saved) { p.style.flexBasis = saved; p.style.flexGrow = "0"; p.style.flexShrink = "0"; }
    });
    /* 배치를 마쳤으면 알린다 — Blockly·CodeMirror 는 "창 크기가 바뀔 때"만 다시 그린다.
       처음 열 때나 파일 목록이 붙어 칸이 좁아졌을 때 안 알리면, 캔버스는 예전 폭 그대로
       남아서 칸과 캔버스 사이에 흰 빈칸이 생긴다(이게 작업창·무대 사이의 그 공백이다). */
    setTimeout(notify, 0);

    if (narrow) return;

    for (var i = 0; i < list.length - 1; i++) {
      var bar = document.createElement("div");
      bar.className = "split-bar" + (vertical ? " v" : "");
      bar.setAttribute("role", "separator");
      bar.setAttribute("aria-orientation", vertical ? "horizontal" : "vertical");
      bar.setAttribute("tabindex", "0");
      bar.title = "끌어서 크기를 바꿔요 (두 번 누르면 원래대로)";
      box.insertBefore(bar, list[i + 1]);
      drag(bar, box, list[i], list[i + 1], i, vertical);
    }
  }

  /* 지금 끌고 있는 중인지.
     아래 감시기는 패널이 접히거나 펼쳐지면 손잡이를 다시 놓는데, 그 감시가
     style 변화를 본다 — 그런데 끌면서 바꾸는 것도 style 이다. 그대로 두면
     내가 끈 것을 감시기가 보고 다시 배치해서, 놓자마자 원래 크기로 돌아간다. */
  var dragging = false;

  var raf = (typeof window !== "undefined" && window.requestAnimationFrame)
    ? window.requestAnimationFrame.bind(window)
    : function (fn) { return setTimeout(fn, 16); };

  function drag(bar, box, a, b, i, vertical) {
    var start = 0, sizeA = 0, sizeB = 0, pending = false;

    function down(e) {
      var pt = e.touches ? e.touches[0] : e;
      start = vertical ? pt.clientY : pt.clientX;
      sizeA = vertical ? a.offsetHeight : a.offsetWidth;
      sizeB = vertical ? b.offsetHeight : b.offsetWidth;
      bar.classList.add("on");
      dragging = true;
      document.body.style.userSelect = "none";
      document.body.style.cursor = vertical ? "row-resize" : "col-resize";
      window.addEventListener("mousemove", move);
      window.addEventListener("touchmove", move, { passive: false });
      window.addEventListener("mouseup", up);
      window.addEventListener("touchend", up);
      e.preventDefault();
    }

    function move(e) {
      var pt = e.touches ? e.touches[0] : e;
      var d = (vertical ? pt.clientY : pt.clientX) - start;
      var minA = minOf(a), minB = minOf(b);
      if (sizeA + d < minA) d = minA - sizeA;
      if (sizeB - d < minB) d = sizeB - minB;
      a.style.flexBasis = (sizeA + d) + "px";
      a.style.flexGrow = "0";
      a.style.flexShrink = "0";
      if (b === lastPanel(box)) {            // 마지막이면 남는 자리를 먹게 둔다
        b.style.flexBasis = "auto";
        b.style.flexGrow = "1";
        b.style.flexShrink = "1";
      } else {
        b.style.flexBasis = (sizeB - d) + "px";
        b.style.flexGrow = "0";
        b.style.flexShrink = "0";
      }
      /* 끄는 동안에도 알린다 — 안 알리면 Blockly 캔버스가 만들 때 크기에 머물러서
         칸만 넓어지고 블록판은 그대로인 어긋난 그림이 된다(놓아야 맞춰짐).
         다만 마우스 움직임마다 다시 그리면 버벅이므로 한 프레임에 한 번만 보낸다. */
      if (!pending) {
        pending = true;
        raf(function () { pending = false; notify(); });
      }
      if (e.cancelable) e.preventDefault();
    }

    function up() {
      bar.classList.remove("on");
      dragging = false;
      notify();
      document.body.style.userSelect = "";
      document.body.style.cursor = "";
      window.removeEventListener("mousemove", move);
      window.removeEventListener("touchmove", move);
      window.removeEventListener("mouseup", up);
      window.removeEventListener("touchend", up);
      try {
        localStorage.setItem(key(box, i), share(box, a, vertical));
        if (b !== lastPanel(box)) {
          localStorage.setItem(key(box, i + 1), share(box, b, vertical));
        }
      } catch (e) {}
    }

    /* 두 번 누르면 원래 크기로 — 잘못 끌어 화면이 망가졌을 때 되돌릴 길 */
    function reset() {
      [a, b].forEach(function (p, n) {
        p.style.flexBasis = ""; p.style.flexGrow = ""; p.style.flexShrink = "";
        try { localStorage.removeItem(key(box, i + n)); } catch (e) {}
      });
      notify();
    }

    /* 손잡이에 맞추고 화살표로도 옮길 수 있게(마우스가 어려운 아이들) */
    function keydown(e) {
      var step = e.shiftKey ? 40 : 12;
      var back = vertical ? "ArrowUp" : "ArrowLeft";
      var fwd = vertical ? "ArrowDown" : "ArrowRight";
      if (e.key !== back && e.key !== fwd) return;
      var d = (e.key === fwd ? step : -step);
      sizeA = vertical ? a.offsetHeight : a.offsetWidth;
      sizeB = vertical ? b.offsetHeight : b.offsetWidth;
      if (sizeA + d < minOf(a) || sizeB - d < minOf(b)) return;
      a.style.flexBasis = (sizeA + d) + "px"; a.style.flexGrow = "0";
      if (b === lastPanel(box)) {
        b.style.flexBasis = "auto"; b.style.flexGrow = "1";
      } else {
        b.style.flexBasis = (sizeB - d) + "px"; b.style.flexGrow = "0";
      }
      notify();
      try {
        localStorage.setItem(key(box, i), share(box, a, vertical));
        if (b !== lastPanel(box)) {
          localStorage.setItem(key(box, i + 1), share(box, b, vertical));
        }
      } catch (e2) {}
      e.preventDefault();
    }

    bar.addEventListener("mousedown", down);
    bar.addEventListener("touchstart", down, { passive: false });
    bar.addEventListener("dblclick", reset);
    bar.addEventListener("keydown", keydown);
  }

  function all() {
    Array.prototype.forEach.call(document.querySelectorAll("[data-split]"), setup);
  }

  function boot() {
    var css = document.createElement("style");
    css.textContent = [
      ".split-bar{flex:0 0 var(--split,6px);align-self:stretch;cursor:col-resize;",
      "  background:transparent;position:relative;z-index:5;}",
      ".split-bar.v{cursor:row-resize;}",
      ".split-bar::after{content:'';position:absolute;inset:0;margin:auto;",
      "  width:2px;height:28px;border-radius:2px;background:var(--line,#9a8f7d);opacity:.35;}",
      ".split-bar.v::after{width:28px;height:2px;}",
      ".split-bar:hover::after,.split-bar.on::after,.split-bar:focus::after{",
      "  opacity:1;background:var(--cyan,#1f5f7a);}",
      ".split-bar:focus{outline:none;}",
      "@media print{.split-bar{display:none;}}"
    ].join("\n");
    document.head.appendChild(css);
    all();

    var t = null;
    function relayout() { if (!dragging) all(); }     // 끄는 중에는 건드리지 않는다
    window.addEventListener("resize", function () {
      clearTimeout(t); t = setTimeout(relayout, 150);
    });
    /* 패널이 접히거나 펼쳐지면 손잡이를 다시 놓는다 */
    if (window.MutationObserver) {
      var mo = new MutationObserver(function () {
        if (dragging) return;                          // 내가 끈 것은 무시
        clearTimeout(t); t = setTimeout(relayout, 60);
      });
      Array.prototype.forEach.call(document.querySelectorAll("[data-split]"), function (b) {
        mo.observe(b, { attributes: true, attributeFilter: ["style", "class"], subtree: true });
      });
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else { boot(); }
})();
