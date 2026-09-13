/* 앱 실행 연출 — 홈에서 누른 아이콘이 커져 앱 화면이 된다. 일곱 페이지가 이 파일 하나를 쓴다.
 *
 * 전에는 홈의 타일이 그냥 <a href="/try"> 였다. 링크니까 브라우저가 문서를 통째로
 * 새로 읽는데, 그동안 화면에는 아무 일도 일어나지 않았다. 아이는 자기가 눌렀는지
 * 모르고 한 번 더 누른다. blocks(Blockly 700KB) · code(CodeMirror 402KB) ·
 * train(TF.js 1.2MB) 은 그 공백이 1초를 넘는다.
 *
 * 고친 것 둘 —
 *
 *  1) 누른 즉시 홈 위에 덮개가 뜬다. 이동을 막지 않는다(preventDefault 안 한다).
 *     브라우저는 새 문서의 첫 페인트까지 **이전 문서를 계속 그리므로**, 이 덮개가
 *     그 공백을 그대로 채운다. 연출 때문에 이동이 1ms 도 늦지 않는다.
 *
 *  2) 새 문서에서 같은 모양의 덮개를 이어받아, 페이지가 준비될 때까지 덮고 있다.
 *     무거운 <script> 가 <body> 안에 있어서(blocks.html · code.html · train.html)
 *     첫 페인트는 **반쯤 그려진 화면**으로 일어난다 — 서랍이 비어 있고 무대가
 *     새까맣고 [닫기] 도 아직 없는 꼴이다. 덮개가 그보다 먼저 깔려 있어야 한다.
 *
 * 덮개를 언제 넣느냐가 이 파일의 전부다
 * ------------------------------------
 * DOMContentLoaded 를 기다리면 늦다 — 그건 <body> 안의 무거운 <script> 가 다
 * 받아진 뒤라서, 그때까지 1.5초를 빈 종이로 보내게 된다. 그래서 <body> 가
 * 생기는 그 순간(MutationObserver)에 넣는다. 무거운 스크립트보다 앞이다.
 *
 * 그 시점에는 lib/icons.js 가 아직 안 실렸다(여섯 페이지는 body 끝에서 싣는다).
 * 그래서 아이콘 그림은 **홈이 누를 때 sessionStorage 에 넣어 준다** — 홈은
 * icons.js 를 head 에서 싣는다. 앱 이름도 같이 넘긴다. 표를 두 벌 갖지 않는다.
 *
 * 최소 표시 시간은 두지 않는다 — options 처럼 가벼운 화면에서 이미 준비된 것을
 * 200ms 가려 버리면 연출이 손해다. window.load 가 뜨는 즉시 걷는다.
 *
 * 부팅(모델 로딩) 덮개와는 배타적이다. lib/boot.js 는 sessionStorage vapi-ready 가
 * 서기 전까지 #boot 를 그리고, 이 파일은 그것이 선 뒤에만 그린다. 둘이 겹치지 않는다.
 *
 * 쓰는 법 — 페이지 <head> 에서 tokens.css **뒤에**:
 *     <script src="/lib/launch.js"></script>
 */
(function () {
  "use strict";

  var KEY = "el-open";     /* {p: 경로, n: 앱 이름, s: 아이콘 SVG} */
  var CAP = 4000;          /* 앱 화면에서 덮개가 영원히 남지 않게 하는 상한 */
  var STUCK = 6000;        /* 홈에서 이동이 끝내 일어나지 않은 경우의 상한 */

  function here() {
    var p = (location.pathname || "/").replace(/\/+$/, "");
    return p === "" ? "/" : p;
  }
  function calm() {
    try { return window.matchMedia("(prefers-reduced-motion: reduce)").matches; }
    catch (e) { return false; }
  }
  function get(k) { try { return sessionStorage.getItem(k); } catch (e) { return null; } }
  function set(k, v) { try { sessionStorage.setItem(k, v); } catch (e) {} }
  function del(k) { try { sessionStorage.removeItem(k); } catch (e) {} }

  /* ── 스타일 — <head> 에서 바로 심는다.
     html 바탕색을 여기서 못박는 것이 중요하다. 페이지들은 body 에만 배경을
     줘 놨는데, body 배경이 캔버스로 전파되기 전(=CSS 가 도착하기 전)의 한
     프레임은 브라우저 기본 흰색이었다. 앱을 옮길 때마다 그 흰색이 번쩍였다. */
  var CSS = [
    "html{background-color:var(--paper,#fbf7ef)}",

    /* body 가 아직 없는 동안의 바탕. 반쯤 그려진 페이지를 가린다. */
    "html.el-open::before{content:'';position:fixed;inset:0;z-index:120;",
    "  background:var(--paper,#fbf7ef)}",

    "#elOpen{position:fixed;inset:0;z-index:121;pointer-events:none;",
    "  display:flex;flex-direction:column;align-items:center;justify-content:center;gap:15px;",
    "  background:var(--paper,#fbf7ef);transition:opacity .16s;",
    "  font-family:'Gowun Dodum','Apple SD Gothic Neo',system-ui,sans-serif}",
    "#elOpen.gone{opacity:0;animation:none}",

    /* 홈에서만 — 바탕이 스며들듯 덮는다. 이것 없이 곧바로 불투명하면 홈이 한
       프레임에 통째로 지워져, 아이콘이 "커진" 것이 아니라 화면이 "꺼진" 것으로 읽힌다.
       앱 화면 쪽 덮개에는 붙이지 않는다 — 거기는 첫 프레임부터 가리고 있어야 한다. */
    "#elOpen.enter{animation:elOpenBg .14s ease-out both}",
    "@keyframes elOpenBg{from{opacity:0}to{opacity:1}}",

    /* 홈 타일의 .ic 와 같은 생김새 — 모양이 다르면 "커진 것" 으로 안 읽힌다 */
    "#elOpen .ic{width:140px;height:140px;border-radius:30px;display:grid;place-items:center;",
    "  background:var(--cyan,#1f5f7a);border:1.5px solid var(--cyan,#1f5f7a);color:#fff;",
    "  box-shadow:0 5px 0 rgba(31,95,122,.22)}",
    "#elOpen .ic svg{width:74px;height:74px}",
    "#elOpen b{font-size:21px;font-weight:700;line-height:1.3;color:var(--ink,#2a2620)}",
    "#elOpen .dots{display:flex;gap:7px}",
    "#elOpen .dots i{width:8px;height:8px;border-radius:50%;background:var(--cyan,#1f5f7a);",
    "  opacity:.22;animation:elOpenDot 1s infinite}",
    "#elOpen .dots i:nth-child(2){animation-delay:.15s}",
    "#elOpen .dots i:nth-child(3){animation-delay:.3s}",
    "@keyframes elOpenDot{0%,100%{opacity:.22}50%{opacity:1}}",

    /* 아이콘이 눌린 자리에서 가운데로 — transform 하나만 움직인다(컴포지터에서 돈다).
       rAF 로 두 단계를 나누면 이동이 먼저 커밋될 때 첫 프레임을 놓친다.
       애니메이션은 다음 프레임에 저절로 시작하므로 @keyframes 에 맡긴다. */
    "@keyframes elOpenIc{from{transform:translate(var(--dx,0),var(--dy,0)) scale(var(--s,1))}",
    "  to{transform:none}}",
    "@keyframes elOpenTx{from{opacity:0}to{opacity:1}}",

    "@media (max-width:639px){",
    "  #elOpen .ic{width:96px;height:96px;border-radius:22px}",
    "  #elOpen .ic svg{width:52px;height:52px}",
    "  #elOpen b{font-size:17px}}",

    "@media (prefers-reduced-motion:reduce){",
    "  #elOpen{transition:none}",
    "  #elOpen.enter{animation:none}",
    "  #elOpen .ic,#elOpen b,#elOpen .dots{animation:none!important}",
    "  #elOpen .dots i{animation:none;opacity:.5}}"
  ].join("\n");

  var st = document.createElement("style");
  st.id = "elOpenCss";
  st.textContent = CSS;
  (document.head || document.documentElement).appendChild(st);

  /* ── 덮개 하나 만들기. svg 는 markup 문자열이다(홈이 넘겨 준 것). ── */
  function card(svg, name) {
    var d = document.createElement("div");
    d.id = "elOpen";
    d.setAttribute("aria-hidden", "true");
    d.innerHTML = '<span class="ic">' + (svg || "") + "</span>" +
                  "<b></b>" +
                  '<span class="dots"><i></i><i></i><i></i></span>';
    d.querySelector("b").textContent = name || "";
    return d;
  }

  function drop() {
    var o = document.getElementById("elOpen");
    if (o && o.parentNode) o.parentNode.removeChild(o);
  }
  function hide() {
    document.documentElement.classList.remove("el-open");
    var el = document.getElementById("elOpen");
    if (!el || el.classList.contains("gone")) return;
    el.classList.add("gone");
    setTimeout(function () { if (el.parentNode) el.parentNode.removeChild(el); }, 220);
  }

  /* ═══════════ 앱 화면 — 홈에서 넘어온 경우에만 이어받는다 ═══════════ */
  function receive() {
    var raw = get(KEY);
    del(KEY);                                   /* 한 번만 쓴다 — 새로고침에는 안 뜬다 */
    if (!raw) return;

    var want;
    try { want = JSON.parse(raw); } catch (e) { return; }
    if (!want || want.p !== here()) return;

    /* 모델 로딩 덮개(#boot)가 뜰 차례면 비켜 준다 — 덮개 둘이 겹치면 안 된다 */
    if (get("vapi-ready") !== "1") return;

    document.documentElement.classList.add("el-open");
    setTimeout(hide, CAP);                      /* 무슨 일이 있어도 걷힌다 */

    function put() {
      if (document.getElementById("elOpen")) return;
      document.body.insertBefore(card(want.s, want.n), document.body.firstChild);
      /* window.load — 무거운 <script> 와 그 초기화까지 끝난 시점이다.
         60ms 는 마지막 배치가 자리 잡는 시간이지 최소 표시 시간이 아니다. */
      if (document.readyState === "complete") setTimeout(hide, 60);
      else window.addEventListener("load", function () { setTimeout(hide, 60); });
    }

    /* <body> 가 생기는 그 순간에 넣는다. DOMContentLoaded 는 <body> 안의 무거운
       <script> 를 다 받은 뒤라서, 그때까지 빈 종이만 보이게 된다. */
    if (document.body) put();
    else if (window.MutationObserver) {
      var mo = new MutationObserver(function () {
        if (document.body) { mo.disconnect(); put(); }
      });
      mo.observe(document.documentElement, { childList: true });
    } else {
      document.addEventListener("DOMContentLoaded", put);
    }
  }

  /* ═══════════ 홈 — 누른 즉시 덮는다 ═══════════ */
  function send() {
    var grid = document.getElementById("appGrid");
    if (!grid) return;

    /* 뒤로가기로 홈에 돌아오면 브라우저가 **떠날 때의 문서를 그대로 되살린다**
       (bfcache). 그때 덮개가 DOM 에 남아 있으면 홈이 덮인 채로 보인다.
       pageshow 는 되살아날 때도 뜨므로 여기서 걷는다. */
    window.addEventListener("pageshow", drop);

    grid.addEventListener("click", function (e) {
      var a = e.target.closest ? e.target.closest("a.app") : null;
      if (!a || !a.href) return;
      /* 새 탭·새 창으로 여는 것은 건드리지 않는다 — 이 창은 그대로 있어야 한다 */
      if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
      if (document.getElementById("elOpen")) return;

      var path = new URL(a.href, location.href).pathname.replace(/\/+$/, "") || "/";
      var app = null, L = (window.EL_APPS ? window.EL_APPS.lang() : "ko");
      if (window.EL_APPS) {
        window.EL_APPS.APPS.forEach(function (x) { if (x.href === path) app = x; });
      }
      var label = app ? (L === "en" ? app.en : app.ko) : "";
      /* 아이콘 그림을 통째로 넘긴다 — 받는 쪽은 아직 icons.js 가 없다 */
      var svg = (window.elIcon && app) ? window.elIcon(app.ic) : "";

      set(KEY, JSON.stringify({ p: path, n: label, s: svg }));

      /* 이동을 막지 않는다. 덮개는 새 문서의 첫 페인트까지만 보이면 된다. */
      var ov = card(svg, label);
      ov.className = "enter";
      document.body.appendChild(ov);

      /* 이동이 끝내 일어나지 않는 경우(Esc, 서버가 죽음) 홈이 덮인 채로 남는다.
         6초는 가장 느린 페이지보다도 넉넉하다 — 여기까지 왔으면 이동이 없었다. */
      setTimeout(function () { if (ov.parentNode) ov.parentNode.removeChild(ov); }, STUCK);

      if (calm()) return;                       /* 움직임을 줄인 설정 — 덮개만 둔다 */

      var ic = ov.querySelector(".ic");
      var from = a.querySelector(".ic");
      if (!from) return;
      var f = from.getBoundingClientRect();
      var t = ic.getBoundingClientRect();       /* 이미 가운데에 놓여 있다 */
      if (!t.width) return;

      ic.style.setProperty("--dx", ((f.left + f.width / 2) - (t.left + t.width / 2)) + "px");
      ic.style.setProperty("--dy", ((f.top + f.height / 2) - (t.top + t.height / 2)) + "px");
      ic.style.setProperty("--s", f.width / t.width);
      ic.style.animation = "elOpenIc .22s cubic-bezier(.2,.7,.3,1) both";
      ov.querySelector("b").style.animation = "elOpenTx .2s .07s both";
      ov.querySelector(".dots").style.animation = "elOpenTx .2s .1s both";
    }, true);
  }

  window.EL_OPEN = { done: hide };              /* 페이지가 직접 걷고 싶을 때 */

  if (here() === "/") {
    if (document.body) send();
    else document.addEventListener("DOMContentLoaded", send);
  } else {
    receive();
  }
})();
