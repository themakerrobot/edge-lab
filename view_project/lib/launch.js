/* 앱 실행 연출 — 홈에서 누른 아이콘이 커져 앱 화면이 되고, 닫으면 다시 아이콘으로 접힌다.
 * 일곱 페이지가 이 파일 하나를 쓴다.
 *
 * 전에는 홈의 타일이 그냥 <a href="/try"> 였다. 링크니까 브라우저가 문서를 통째로
 * 새로 읽는데, 그동안 화면에는 아무 일도 일어나지 않았다. 아이는 자기가 눌렀는지
 * 모르고 한 번 더 누른다. blocks(Blockly 700KB) · code(CodeMirror 402KB) ·
 * train(TF.js 1.2MB) 은 그 공백이 1초를 넘는다.
 *
 * 이동을 막지 않는다
 * -----------------
 * preventDefault 를 하지 않는다. 브라우저는 새 문서의 첫 페인트까지 **이전 문서를
 * 계속 그리므로**, 누른 쪽에 띄운 덮개가 그 공백을 그대로 채운다. 연출 때문에
 * 이동이 1ms 도 늦지 않는다.
 *
 * 이어 그리기 — 이 파일에서 가장 중요한 부분
 * ------------------------------------------
 * 문서가 둘이라 연출도 둘로 끊긴다. 누른 시각(t0)과 움직임의 값을 넘겨주고,
 * 받는 쪽은 그 중간부터 잇는다. 이때 두 번 헛디뎠다.
 *
 *   1) @keyframes 안에 var(--dx) 를 쓰면 Chromium 이 그 애니메이션을 컴포지터로
 *      올리지 못한다. 값을 박아 넣은 transform 만 컴포지터에서 돈다.
 *      그래서 이동은 CSS 가 아니라 Element.animate 로 준다.
 *
 *   2) **새 문서는 첫 프레임을 그리기 전까지 애니메이션을 시작하지 않는다.**
 *      만들 때 음수 지연(delay: -지난시간)을 줘 봐야, 그 애니메이션은 pending 인
 *      채로 기다리다가 첫 프레임에서야 그 지점부터 시작한다. 그사이 흐른 200ms 가
 *      통째로 날아가 아이콘이 한참 멈춰 있다가 튄다 — 가벼운 페이지(설정·대화)에서
 *      컷이 튀는 것처럼 보인 이유가 이것이다. 무거운 페이지는 어차피 다 끝난 뒤에
 *      그려져서 안 보였을 뿐이다.
 *      그래서 **멈춘 채로 만들어 두고, 첫 requestAnimationFrame 에서 그때의
 *      실제 경과 시간으로 되감아 재생한다**(resume). 첫 프레임이 곧 첫 그림이다.
 *
 * 덮개를 언제 넣느냐
 * -----------------
 * DOMContentLoaded 는 늦다 — 그건 <body> 안의 무거운 <script> 를 다 받은 뒤라서,
 * 그때까지 1.5초를 빈 종이로 보내게 된다. <body> 가 생기는 그 순간
 * (MutationObserver) 에 넣는다. 그때 <body> 는 아직 비어 있으므로, 뒤이어 파싱되는
 * 내용은 전부 덮개 아래에 깔린다 — 반쯤 그려진 화면이 새어 나오지 않는다.
 *
 * 그 시점에는 lib/icons.js 가 아직 안 실렸다(여섯 페이지는 body 끝에서 싣는다).
 * 그래서 여는 쪽 아이콘 그림은 **홈이 SVG 마크업째 넘겨준다**. 표를 두 벌 갖지 않는다.
 *
 * 부팅(모델 로딩) 덮개와는 배타적이다. lib/boot.js 는 sessionStorage vapi-ready 가
 * 서기 전까지 #boot 를 그리고, 이 파일은 그것이 선 뒤에만 그린다.
 *
 * 쓰는 법 — 페이지 <head> 에서 tokens.css **뒤에**:
 *     <script src="/lib/launch.js"></script>
 * 닫기 연출은 그 페이지가 어느 앱인지 알아야 하므로 lib/apps.js 와 lib/icons.js 가
 * 실려 있어야 한다. body 끝이어도 된다 — [닫기] 를 누를 때는 이미 실렸다.
 */
(function () {
  "use strict";

  var OPEN = "el-open";    /* {p, n, s, dx, dy, sc, t0} — 홈 → 앱 */
  var SHUT = "el-shut";    /* {p, n, s, t0}             — 앱 → 홈 (p 는 떠나온 앱) */

  var BG = 120;            /* 바탕이 스며드는 시간 */
  var FLY = 200;           /* 아이콘이 타일 ↔ 가운데를 오가는 시간 */
  var OUT = 140;           /* 덮개가 걷히는 시간 */
  var CAP = 4000;          /* 받는 쪽에서 덮개가 영원히 남지 않게 하는 상한 */
  var STUCK = 6000;        /* 이동이 끝내 일어나지 않은 경우의 상한 */

  var EASE = "cubic-bezier(.2,.7,.3,1)";

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

  /* 넘겨받은 것 하나를 꺼내 본다 — 한 번만 쓴다(새로고침·주소 직접 입력에는 안 뜬다) */
  function take(key) {
    var raw = get(key);
    del(key);
    if (!raw) return null;
    try { return JSON.parse(raw) || null; } catch (e) { return null; }
  }

  /* ── 스타일 — <head> 에서 바로 심는다.
     html 바탕색을 여기서 못박는 것이 중요하다. 페이지들은 body 에만 배경을
     줘 놨는데, body 배경이 캔버스로 전파되기 전(=CSS 가 도착하기 전)의 한
     프레임은 브라우저 기본 흰색이었다. 앱을 옮길 때마다 그 흰색이 번쩍였다. */
  var CSS = [
    "html{background-color:var(--paper,#fbf7ef)}",

    "#elOpen{position:fixed;inset:0;z-index:121;pointer-events:none;",
    "  display:flex;flex-direction:column;align-items:center;justify-content:center;gap:15px;",
    "  transition:opacity " + OUT + "ms;",
    "  font-family:'Gowun Dodum','Apple SD Gothic Neo',system-ui,sans-serif}",
    "#elOpen.gone{opacity:0}",
    "#elOpen .bg{position:absolute;inset:0;background:var(--paper,#fbf7ef)}",

    /* 홈 타일의 .ic 와 같은 생김새 — 모양이 다르면 "커진 것" 으로 안 읽힌다 */
    "#elOpen .ic{position:relative;width:140px;height:140px;border-radius:30px;",
    "  display:grid;place-items:center;",
    "  background:var(--cyan,#1f5f7a);border:1.5px solid var(--cyan,#1f5f7a);color:#fff;",
    "  box-shadow:0 5px 0 rgba(31,95,122,.22)}",
    "#elOpen .ic svg{width:74px;height:74px}",
    "#elOpen b{position:relative;font-size:21px;font-weight:700;line-height:1.3;",
    "  color:var(--ink,#2a2620)}",
    "#elOpen .dots{position:relative;display:flex;gap:7px}",
    "#elOpen .dots i{width:8px;height:8px;border-radius:50%;background:var(--cyan,#1f5f7a);",
    "  opacity:.22;animation:elDot 1s infinite}",
    "#elOpen .dots i:nth-child(2){animation-delay:.15s}",
    "#elOpen .dots i:nth-child(3){animation-delay:.3s}",
    "@keyframes elDot{0%,100%{opacity:.22}50%{opacity:1}}",

    "@media (max-width:639px){",
    "  #elOpen .ic{width:96px;height:96px;border-radius:22px}",
    "  #elOpen .ic svg{width:52px;height:52px}",
    "  #elOpen b{font-size:17px}}",

    /* 움직임을 줄인 설정 — 여는 쪽 덮개는 그대로 둔다(반쯤 그려진 화면을 가리는
       것은 장식이 아니라 제 몫이다). 움직이는 것만 멈춘다.
       Element.animate 로 준 것들은 이 블록을 타지 않으므로 JS 에서 따로 막는다. */
    "@media (prefers-reduced-motion:reduce){",
    "  #elOpen{transition:none}",
    "  #elOpen .dots i{animation:none;opacity:.5}}"
  ].join("\n");

  var st = document.createElement("style");
  st.id = "elOpenCss";
  st.textContent = CSS;
  (document.head || document.documentElement).appendChild(st);

  /* ══════════ 움직임 ══════════
     전부 transform / opacity 뿐이고 값을 박아 넣는다 — 컴포지터에서 돈다. */

  function anim(el, frames, dur, ease) {
    if (!el || !el.animate || calm()) return null;
    return el.animate(frames, { duration: dur, easing: ease || "linear", fill: "both" });
  }
  function flyIn(el, from) { return anim(el, [{ transform: from }, { transform: "none" }], FLY, EASE); }
  function flyOut(el, to)  { return anim(el, [{ transform: "none" }, { transform: to }], FLY, EASE); }
  function fadeIn(el)      { return anim(el, [{ opacity: 0 }, { opacity: 1 }], BG, "ease-out"); }
  function fadeOut(el, d)  { return anim(el, [{ opacity: 1 }, { opacity: 0 }], d || FLY, "ease-in"); }

  /* 한 rect 에서 다른 rect 로 가는 transform */
  function shift(f, t) {
    return "translate(" + ((f.left + f.width / 2) - (t.left + t.width / 2)) + "px," +
                          ((f.top + f.height / 2) - (t.top + t.height / 2)) + "px) " +
           "scale(" + (f.width / t.width) + ")";
  }

  /* 받는 쪽 — 멈춘 채로 만들어 두고 **첫 프레임에** 실제 경과 시간으로 되감는다.
     첫 프레임이 곧 이 문서가 처음 그려지는 순간이다. 만들 때 음수 지연을 주면
     그때까지 흐른 시간이 통째로 날아가 아이콘이 멈췄다 튄다. */
  function resume(list, t0) {
    var live = list.filter(Boolean);
    live.forEach(function (a) { a.pause(); });
    if (!live.length) return;
    requestAnimationFrame(function () {
      var e = Math.max(0, Date.now() - (t0 || 0));
      live.forEach(function (a) {
        var d = a.effect.getComputedTiming().duration;
        if (e >= d) { a.finish(); return; }
        a.currentTime = e;
        a.play();
      });
    });
  }

  /* ── 덮개 하나 만들기. svg 는 markup 문자열이다. ── */
  function card(svg, name, dots) {
    var d = document.createElement("div");
    d.id = "elOpen";
    d.setAttribute("aria-hidden", "true");
    d.innerHTML = '<span class="bg"></span>' +
                  '<span class="ic">' + (svg || "") + "</span>" +
                  "<b></b>" +
                  (dots ? '<span class="dots"><i></i><i></i><i></i></span>' : "");
    d.querySelector("b").textContent = name || "";
    return d;
  }
  function parts(ov) {
    return { bg: ov.querySelector(".bg"), ic: ov.querySelector(".ic"), nm: ov.querySelector("b") };
  }

  function drop() {
    var o = document.getElementById("elOpen");
    if (o && o.parentNode) o.parentNode.removeChild(o);
  }
  function fade() {
    var el = document.getElementById("elOpen");
    if (!el || el.classList.contains("gone")) return;
    el.classList.add("gone");
    /* 걷히는 도중에 [닫기] 를 누를 수 있다 — 그때 되돌리려면 이 예약을 취소해야 한다 */
    el.elRm = setTimeout(function () {
      if (el.parentNode) el.parentNode.removeChild(el);
    }, OUT + 80);
  }
  function unfade(el) {
    if (el.elRm) { clearTimeout(el.elRm); el.elRm = 0; }
    el.classList.remove("gone");
  }

  /* <body> 가 생기는 그 순간에 넣는다. DOMContentLoaded 는 <body> 안의 무거운
     <script> 를 다 받은 뒤라서, 그때까지 빈 종이만 보이게 된다. */
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
  function whenReady(fn) {
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", fn);
    else fn();
  }

  /* 경로로 앱 하나 찾기 — lib/apps.js 가 유일한 출처다 */
  function appAt(path) {
    if (!window.EL_APPS) return null;
    var found = null;
    window.EL_APPS.APPS.forEach(function (x) { if (x.href === path) found = x; });
    return found;
  }
  function appName(app) {
    if (!app) return "";
    return (window.EL_APPS && window.EL_APPS.lang() === "en") ? app.en : app.ko;
  }

  /* ═══════════ 받는 쪽 — 앱 화면이 홈의 움직임을 이어받는다 ═══════════ */
  function receiveOpen(want) {
    /* 모델 로딩 덮개(#boot)가 뜰 차례면 비켜 준다 — 덮개 둘이 겹치면 안 된다 */
    if (get("vapi-ready") !== "1") return;
    setTimeout(fade, CAP);                      /* 무슨 일이 있어도 걷힌다 */

    whenBody(function () {
      if (document.getElementById("elOpen")) return;
      var ov = card(want.s, want.n, true);
      document.body.insertBefore(ov, document.body.firstChild);
      var q = parts(ov);

      var run = [fadeIn(q.bg), fadeIn(q.nm)];
      if (want.dx !== undefined) {
        run.push(flyIn(q.ic,
          "translate(" + want.dx + "px," + want.dy + "px) scale(" + want.sc + ")"));
      }
      resume(run, want.t0);

      /* 준비되면 걷는다. 최소 표시 시간은 두지 않는다 — 가벼운 화면에서 이미
         준비된 것을 가리면 손해다. 다만 날아가던 아이콘이 도착은 해야 한다.
         그러지 않으면 화면 한가운데에서 움직임이 뚝 끊긴다. */
      function done() {
        setTimeout(fade, Math.max(40, (want.t0 || 0) + FLY - Date.now()));
      }
      if (document.readyState === "complete") done();
      else window.addEventListener("load", done);
    });
  }

  /* ═══════════ 받는 쪽 — 홈이 앱을 아이콘 자리로 도로 접는다 ═══════════ */
  function receiveShut(want) {
    setTimeout(drop, CAP);

    whenBody(function () {
      if (document.getElementById("elOpen")) return;
      /* 아이콘 그림은 앱 쪽에서 넘겨받는다 — 홈도 <body> 가 막 생긴 이 시점에는
         lib/icons.js 를 아직 안 실었다(body 끝에서 싣는다). 여는 쪽과 같다. */
      var ov = card(want.s, want.n, false);
      document.body.insertBefore(ov, document.body.firstChild);
      var q = parts(ov);
      resume([fadeIn(q.bg), fadeIn(q.ic), fadeIn(q.nm)], want.t0);

      /* 접기를 시작하기 전에 셋을 다 기다린다.
           1) 타일이 그려져야 어디로 접을지 알 수 있다 (whenReady)
           2) 이 문서가 한 프레임이라도 그려야 한다 (requestAnimationFrame) —
              setTimeout 만 믿으면, 아직 아무것도 안 그려진 채로 접기가 끝나
              화면에는 갑자기 홈이 나타난다. 여는 쪽과 같은 함정이다.
           3) 바탕이 다 스며든 뒤라야 한다 — 밝아지다 말고 어두워지면 한 번 출렁인다. */
      whenReady(function () {
        requestAnimationFrame(function () {
          setTimeout(function () { shrink(ov, q); },
                     Math.max(0, (want.t0 || 0) + BG - Date.now()));
        });
      });
    });

    function shrink(ov, q) {
      if (!ov.parentNode) return;
      var tile = document.querySelector('#appGrid a.app[href="' + want.p + '"] .ic');
      var t = q.ic.getBoundingClientRect();
      if (tile && t.width) flyOut(q.ic, shift(tile.getBoundingClientRect(), t));
      fadeOut(q.bg);
      fadeOut(q.nm, Math.round(FLY / 2));
      setTimeout(drop, FLY + 40);
    }
  }

  /* ═══════════ 보내는 쪽 — 홈에서 앱을 연다 ═══════════ */
  function sendOpen() {
    var grid = document.getElementById("appGrid");
    if (!grid) return;

    grid.addEventListener("click", function (e) {
      var a = e.target.closest ? e.target.closest("a.app") : null;
      if (!a || !a.href) return;
      /* 새 탭·새 창으로 여는 것은 건드리지 않는다 — 이 창은 그대로 있어야 한다 */
      if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
      if (document.getElementById("elOpen")) return;

      var path = new URL(a.href, location.href).pathname.replace(/\/+$/, "") || "/";
      var app = appAt(path);
      var label = appName(app);
      /* 아이콘 그림을 통째로 넘긴다 — 받는 쪽은 아직 icons.js 가 없다 */
      var svg = (window.elIcon && app) ? window.elIcon(app.ic) : "";

      var ov = card(svg, label, true);
      document.body.appendChild(ov);
      /* 이동이 끝내 일어나지 않는 경우(Esc, 서버가 죽음) 홈이 덮인 채로 남는다 */
      setTimeout(function () { if (ov.parentNode) ov.parentNode.removeChild(ov); }, STUCK);

      var q = parts(ov);
      var pass = { p: path, n: label, s: svg, t0: Date.now() };
      var from = a.querySelector(".ic");
      var t = q.ic.getBoundingClientRect();

      fadeIn(q.bg);
      fadeIn(q.nm);
      if (!calm() && from && t.width) {
        var f = from.getBoundingClientRect();
        pass.dx = (f.left + f.width / 2) - (t.left + t.width / 2);
        pass.dy = (f.top + f.height / 2) - (t.top + t.height / 2);
        pass.sc = f.width / t.width;
        flyIn(q.ic, "translate(" + pass.dx + "px," + pass.dy + "px) scale(" + pass.sc + ")");
      }
      /* 이동을 막지 않는다 — preventDefault 없음 */
      set(OPEN, JSON.stringify(pass));
    }, true);
  }

  /* ═══════════ 보내는 쪽 — 앱에서 [× 닫기] 를 누른다 ═══════════
     [닫기] 와 왼쪽 위 브랜드가 둘 다 "/" 로 간다. 둘 다 같은 연출을 탄다. */
  function sendShut() {
    document.addEventListener("click", function (e) {
      var a = e.target.closest ? e.target.closest(".titlebar a") : null;
      if (!a || !a.getAttribute("href")) return;
      if (a.target) return;                     /* API Docs 처럼 새 창으로 가는 것 */
      if (new URL(a.href, location.href).pathname.replace(/\/+$/, "") !== "") return;
      if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
      /* 홈은 가벼워 가릴 이유가 없다 — 움직임을 줄인 설정에서는 그냥 간다 */
      if (calm()) return;

      var app = appAt(here());
      var svg = (window.elIcon && app) ? window.elIcon(app.ic) : "";
      /* 아이콘 그림을 통째로 넘긴다 — 받는 홈도 그 시점엔 icons.js 가 없다 */
      set(SHUT, JSON.stringify({ p: here(), n: appName(app), s: svg, t0: Date.now() }));

      /* 여는 덮개가 아직 떠 있을 수 있다 — 무거운 화면을 열자마자 닫으면 늘 그렇다.
         그때는 **그것을 그대로 쓴다**. 같은 아이콘이 이미 가운데에 떠 있으니
         새로 그릴 것이 없고, 지우고 다시 그리면 한 번 깜빡인다.
         전에는 여기서 그냥 돌아서서(중복 방지) 닫는 연출이 통째로 없어졌다. */
      var ov = document.getElementById("elOpen");
      if (ov) { unfade(ov); var od = ov.querySelector(".dots"); if (od) od.remove(); return; }

      ov = card(svg, appName(app), false);
      document.body.appendChild(ov);
      setTimeout(function () { if (ov.parentNode) ov.parentNode.removeChild(ov); }, STUCK);

      var q = parts(ov);
      fadeIn(q.bg); fadeIn(q.ic); fadeIn(q.nm);
    }, true);
  }

  window.EL_OPEN = { done: fade };              /* 페이지가 직접 걷고 싶을 때 */

  /* 뒤로가기로 되살아난 문서(bfcache)에는 떠날 때의 덮개가 그대로 남아 있다.
     persisted 일 때만 걷는다 — 처음 열릴 때도 pageshow 는 뜨므로, 가리지 않고
     지우면 방금 넣은 덮개를 스스로 없애게 된다. */
  window.addEventListener("pageshow", function (e) { if (e.persisted) drop(); });

  if (here() === "/") {
    var shut = take(SHUT);
    del(OPEN);                                  /* 앱으로 가다 만 것이 남아 있을 수 있다 */
    if (shut && shut.p && shut.p !== "/" && !calm()) receiveShut(shut);
    whenReady(sendOpen);
  } else {
    var open = take(OPEN);
    del(SHUT);
    if (open && open.p === here()) receiveOpen(open);
    whenBody(sendShut);
  }
})();
