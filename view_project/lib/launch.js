/* 화면 전환 — 앱을 열고 닫을 때 화면이 끊기지 않게 한다. 일곱 페이지가 이 파일 하나를 쓴다.
 *
 * 전에는 홈의 타일이 그냥 <a href="/try"> 였다. 링크니까 브라우저가 문서를 통째로
 * 새로 읽는데, 그동안 화면에서 셋이 겹쳐 일어났다.
 *
 *   누른 순간   아무 반응이 없다. 아이는 눌렸는지 모르고 한 번 더 누른다.
 *   이동 중     html 배경이 없어 브라우저 기본 **흰색**이 한 프레임 번쩍인다.
 *               (페이지들은 body 에만 배경을 줬고, 그것이 캔버스로 전파되기 전이다)
 *   첫 페인트   무거운 <script> 가 <body> 안에 있어(blocks · code · train)
 *               **반쯤 그려진 화면**이 먼저 보인다 — 블록 서랍이 비어 있고
 *               무대가 새까맣고 [닫기] 도 아직 없다.
 *
 * 하는 일은 하나다. 누른 순간 종이색 덮개가 스며들고, 새 문서가 그 덮개를 이어받아
 * 준비되면 걷는다. 아이콘이 날아가거나 가운데에 뜨는 연출은 **두지 않는다** —
 * 이 화면들은 대개 1초 안에 열려서, 그 사이에 무엇이 왔다 갔다 하면 열리는 것을
 * 도와주는 게 아니라 한 번 튀는 것처럼 보인다.
 *
 * 이동을 막지 않는다
 * -----------------
 * preventDefault 를 하지 않는다. 브라우저는 새 문서의 첫 페인트까지 이전 문서를
 * 계속 그리므로, 누른 쪽에 띄운 덮개가 그 공백을 그대로 채운다. 연출 때문에
 * 이동이 1ms 도 늦지 않는다.
 *
 * 이어 그리기 — 여기서 두 번 헛디뎠다
 * ----------------------------------
 * 문서가 둘이라 연출도 둘로 끊긴다. 누른 시각(t0)을 넘겨주고 받는 쪽이 그 중간부터
 * 이어야 하는데, 처음 두 방식이 다 틀렸다.
 *
 *   1) @keyframes 안에 var() 를 쓰면 Chromium 이 그 애니메이션을 컴포지터로 올리지
 *      못한다. 새 문서가 무거운 <script> 를 해석하며 메인 스레드를 잡고 있으면
 *      그대로 멈춘다.
 *   2) **새 문서는 첫 프레임을 그리기 전까지 애니메이션을 시작하지 않는다.**
 *      만들 때 음수 지연을 줘 봐야 pending 인 채 기다리다 첫 프레임에서야 그
 *      지점부터 시작하므로, 그사이 흐른 시간이 통째로 날아간다.
 *
 * 그래서 **멈춘 채로 만들어 두고, 첫 requestAnimationFrame 에서 그때의 실제 경과
 * 시간으로 되감아 재생한다**. 첫 rAF 가 곧 이 문서가 처음 그려지는 순간이다.
 * 움직이는 것은 opacity 하나뿐이라 컴포지터에서 돈다.
 *
 * 덮개를 언제 넣느냐
 * -----------------
 * DOMContentLoaded 는 늦다 — 그건 <body> 안의 무거운 <script> 를 다 받은 뒤라서,
 * 그때까지 1.5초를 맨 화면으로 보내게 된다. <body> 가 생기는 그 순간
 * (MutationObserver) 에 넣는다. 그때 <body> 는 아직 비어 있으므로, 뒤이어 파싱되는
 * 내용은 전부 덮개 아래에 깔린다.
 *
 * 덮개에는 아무것도 그리지 않는다. 종이색 한 장이다 — 이 화면들은 그냥 페이지가
 * 바뀌는 수준이라, 무엇을 띄워도 보이기 전에 걷힌다. 오래 걸리는 것은 페이지를
 * 여는 쪽이 아니라 모델을 **실행**하는 쪽이고, 그건 각 화면이 스스로 알린다.
 *
 * 부팅(모델 로딩) 덮개와는 배타적이다. lib/boot.js 는 sessionStorage vapi-ready 가
 * 서기 전까지 #boot 를 그리고, 이 파일은 그것이 선 뒤에만 그린다.
 *
 * 쓰는 법 — 페이지 <head> 에서 tokens.css **뒤에**:
 *     <script src="/lib/launch.js"></script>
 */
(function () {
  "use strict";

  var KEY = "el-go";       /* {p, t0} — 떠나는 쪽이 남기고 도착하는 쪽이 한 번 쓴다 */

  var IN = 110;            /* 덮개가 스며드는 시간 */
  var OUT = 160;           /* 덮개가 걷히는 시간 */
  var CAP = 4000;          /* 받는 쪽에서 덮개가 영원히 남지 않게 하는 상한 */
  var STUCK = 6000;        /* 이동이 끝내 일어나지 않은 경우의 상한 */

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

  /* 한 번만 쓴다 — 새로고침·주소 직접 입력에는 안 뜬다 */
  function take() {
    var raw = get(KEY);
    del(KEY);
    if (!raw) return null;
    try { return JSON.parse(raw) || null; } catch (e) { return null; }
  }

  /* ── 스타일. html 바탕색을 여기서 못박는 것이 중요하다 — 페이지들은 body 에만
     배경을 줘 놨고, 그것이 캔버스로 전파되기 전 한 프레임이 흰색이었다. */
  var CSS = [
    "html{background-color:var(--paper,#fbf7ef)}",

    "#elGo{position:fixed;inset:0;z-index:121;pointer-events:none;",
    "  background:var(--paper,#fbf7ef)}"
  ].join("\n");

  var st = document.createElement("style");
  st.id = "elGoCss";
  st.textContent = CSS;
  (document.head || document.documentElement).appendChild(st);

  function anim(el, from, to, dur) {
    if (!el || !el.animate || calm()) return null;
    return el.animate([{ opacity: from }, { opacity: to }],
                      { duration: dur, easing: "ease-out", fill: "both" });
  }

  function cover() {
    var d = document.createElement("div");
    d.id = "elGo";
    d.setAttribute("aria-hidden", "true");
    return d;
  }
  function drop(el) {
    el = el || document.getElementById("elGo");
    if (el && el.parentNode) el.parentNode.removeChild(el);
  }

  /* <body> 가 생기는 그 순간에 넣는다 — DOMContentLoaded 는 무거운 <script> 뒤다 */
  function whenBody(fn) {
    if (document.body) { fn(); return; }
    if (window.MutationObserver) {
      var mo = new MutationObserver(function () {
        if (document.body) { mo.disconnect(); fn(); }
      });
      mo.observe(document.documentElement, { childList: true });
    } else {
      document.addEventListener("DOMContentLoaded", fn);
    }
  }

  /* ═══════════ 도착한 쪽 — 떠난 쪽의 덮개를 이어받아 걷는다 ═══════════ */
  function arrive(want) {
    /* 모델 로딩 덮개(#boot)가 뜰 차례면 비켜 준다 — 덮개 둘이 겹치면 안 된다 */
    if (here() !== "/" && get("vapi-ready") !== "1") return;

    whenBody(function () {
      if (document.getElementById("elGo")) return;
      var el = cover();
      document.body.insertBefore(el, document.body.firstChild);
      var capped = setTimeout(function () { drop(el); }, CAP);

      /* 떠난 쪽에서 스며들던 중이었으면 그 중간부터 잇는다.
         멈춰 뒀다가 **첫 프레임에** 되감는다 — 만들 때 음수 지연을 주면 첫 프레임을
         기다리는 동안 흐른 시간이 통째로 날아가 덮개가 한 번 튄다. */
      var a = anim(el, 0, 1, IN);
      if (a) {
        a.pause();
        requestAnimationFrame(function () {
          var e = Math.max(0, Date.now() - (want.t0 || 0));
          if (e >= IN) a.finish();
          else { a.currentTime = e; a.play(); }
        });
      }

      function done() {
        clearTimeout(capped);
        var o = anim(el, 1, 0, OUT);
        if (!o) { drop(el); return; }
        setTimeout(function () { drop(el); }, OUT + 40);
      }
      if (document.readyState === "complete") setTimeout(done, 40);
      else window.addEventListener("load", function () { setTimeout(done, 40); });
    });
  }

  /* ═══════════ 떠나는 쪽 — 누른 즉시 덮는다 ═══════════
     홈의 앱 타일, 그리고 앱의 [× 닫기]·브랜드(둘 다 "/" 로 간다). */
  function leave() {
    document.addEventListener("click", function (e) {
      if (!e.target.closest) return;
      var a = e.target.closest("#appGrid a.app, .titlebar a");
      if (!a || !a.getAttribute("href")) return;
      if (a.target) return;                     /* API Docs 처럼 새 창으로 가는 것 */
      /* 새 탭·새 창으로 여는 것은 건드리지 않는다 — 이 창은 그대로 있어야 한다 */
      if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
      if (document.getElementById("elGo")) return;

      var path = new URL(a.href, location.href).pathname.replace(/\/+$/, "") || "/";
      if (path === here()) return;              /* 지금 보고 있는 화면이면 아무 일도 없다 */

      var el = cover();
      document.body.appendChild(el);
      anim(el, 0, 1, IN);
      /* 이동이 끝내 일어나지 않는 경우(Esc, 서버가 죽음) 화면이 덮인 채로 남는다 */
      setTimeout(function () { drop(el); }, STUCK);

      /* 이동을 막지 않는다 — preventDefault 없음 */
      set(KEY, JSON.stringify({ p: path, t0: Date.now() }));
    }, true);
  }

  window.EL_GO = { drop: drop };

  /* 뒤로가기로 되살아난 문서(bfcache)에는 떠날 때의 덮개가 그대로 남아 있다.
     persisted 일 때만 걷는다 — 처음 열릴 때도 pageshow 는 뜨므로, 가리지 않고
     지우면 방금 넣은 덮개를 스스로 없애게 된다. */
  window.addEventListener("pageshow", function (e) { if (e.persisted) drop(); });

  var go = take();
  if (go && go.p === here()) arrive(go);
  whenBody(leave);
})();
