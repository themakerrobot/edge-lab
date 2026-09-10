/* 셸 — 세로 레일과 앱 이름을 만든다. 일곱 페이지가 이 파일 하나를 쓴다.
 *
 * lib/nav.js(헤더 가로 글자 탭)를 대신한다. 왜 눕혔는지는 lib/shell.css 주석에.
 *
 * 페이지가 갖춰야 할 마크업 — 이것뿐이다:
 *
 *     <div class="titlebar">
 *       <a class="tb-brand" href="/" title="홈으로">
 *         <img src="/assets/pibo-logo.png" alt=""><b>edge-lab</b>
 *       </a>
 *       <span class="tb-sep"></span>
 *       <span class="tb-app" id="txtTitle"></span>
 *       <div class="h-tools">
 *         <button id="langButton" title="한국어 / English"><b>EN</b></button>
 *       </div>
 *     </div>
 *     <div class="shell-body">
 *       <div class="workbench">
 *         ... 페이지 내용 (.main-container 등) ...
 *       </div>
 *     </div>
 *
 * </body> 앞에 (icons.js 뒤, sysbar.js 앞):
 *     <script src="/lib/icons.js"></script>
 *     <script src="/lib/shell.js"></script>
 *
 * 레일과 앱 이름은 이 파일이 **혼자** 갖는다. 페이지가 #txtTitle 을 따로
 * 채우지 않는다 — 전에 헤더 제목을 페이지마다 자기 UI 사전에서 채우는 바람에
 * 같은 자리 글자가 여섯 벌로 갈라져 있었다.
 */
(function () {
  "use strict";

  /* 경로 · 아이콘 · 이름 — 순서가 곧 레일 순서다.
     id 는 예전 nav.js 가 쓰던 이름을 그대로 이어받는다(tour.js 가 잡고 있다). */
  var TABS = [
    { id: "homeLink",    href: "/",        ic: "home",   ko: "홈",       en: "Home" },
    { id: "tryLink",     href: "/try",     ic: "eye",    ko: "체험",     en: "Try it" },
    { id: "blocksLink",  href: "/blocks",  ic: "blocks", ko: "블록",     en: "Blocks" },
    { id: "codeLink",    href: "/code",    ic: "code",   ko: "파이썬",   en: "Python" },
    { id: "trainLink",   href: "/train",   ic: "train",  ko: "가르치기", en: "Train" },
    { id: "talkLink",    href: "/talk",    ic: "talk",   ko: "대화",     en: "Talk" },
    { id: "SPACER" },
    { id: "optionsLink", href: "/options", ic: "gear",   ko: "설정",     en: "Settings" }
  ];

  /* 타이틀바에 적는 지금 앱 이름. 레일 라벨은 좁아서 줄였지만(체험), 여기는
     화면 제목이라 온전한 이름을 쓴다(체험하기). */
  var APP = {
    "/":         { ko: "홈",         en: "Home" },
    "/try":      { ko: "체험하기",   en: "Try it" },
    "/blocks":   { ko: "블록",       en: "Blocks" },
    "/code":     { ko: "파이썬",     en: "Python" },
    "/train":    { ko: "가르치기",   en: "Train" },
    "/talk":     { ko: "대화",       en: "Talk" },
    "/options":  { ko: "설정",       en: "Settings" }
  };

  function lang() {
    try {
      var v = localStorage.getItem("vapiLang");
      return v === "en" ? "en" : "ko";
    } catch (e) { return "ko"; }
  }

  /* 지금 화면 — /code?from=blocks 처럼 뒤에 무엇이 붙어도 경로만 본다 */
  function here() {
    var p = (location.pathname || "/").replace(/\/+$/, "");
    return p === "" ? "/" : p;
  }

  function icon(name) {
    /* icons.js 가 안 실렸으면 글자만으로도 읽히므로 조용히 넘어간다 */
    return (typeof window.elIcon === "function") ? window.elIcon(name) : "";
  }

  function build() {
    var body = document.querySelector(".shell-body");
    if (!body || body.querySelector(".rail")) return;

    var L = lang(), now = here();
    var rail = document.createElement("nav");
    rail.className = "rail";
    rail.setAttribute("aria-label", L === "en" ? "Apps" : "화면 이동");

    TABS.forEach(function (tab) {
      if (tab.id === "SPACER") {
        var sp = document.createElement("span");
        sp.className = "spacer";
        rail.appendChild(sp);
        return;
      }
      var a = document.createElement("a");
      a.id = tab.id;
      a.href = tab.href;
      a.title = tab[L];
      a.innerHTML = icon(tab.ic) + '<span class="tx">' + tab[L] + "</span>";
      if (tab.href === now) {
        a.classList.add("on");
        a.setAttribute("aria-current", "page");
        a.removeAttribute("href");        /* 지금 화면은 눌러도 새로 안 읽는다 */
      }
      rail.appendChild(a);
    });

    body.insertBefore(rail, body.firstChild);
    paintApp();
  }

  /* 타이틀바의 앱 이름 */
  function paintApp() {
    var el = document.getElementById("txtTitle");
    if (!el) return;
    var a = APP[here()];
    el.textContent = a ? a[lang()] : "";
  }

  /* 페이지가 언어를 바꾸면 글자도 따라 바꾼다. 새로고침하는 페이지가 대부분이지만
     대화·체험하기처럼 그 자리에서 바꾸는 페이지가 있어 둘 다 대응한다. */
  function repaint() {
    var L = lang();
    TABS.forEach(function (tab) {
      if (tab.id === "SPACER") return;
      var a = document.getElementById(tab.id);
      if (!a) return;
      var tx = a.querySelector(".tx");
      if (tx) tx.textContent = tab[L];
      a.title = tab[L];
    });
    paintApp();
  }
  /* 이름은 예전 그대로 둔다 — 여섯 페이지가 이미 이 이름으로 부르고 있다 */
  window.navRepaint = repaint;

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", build);
  } else {
    build();
  }
  /* 언어 단추는 페이지마다 처리가 달라 클릭을 가로채지 않고, 눌린 뒤에 다시 그린다 */
  document.addEventListener("click", function (e) {
    if (e.target && e.target.closest && e.target.closest("#langButton")) {
      setTimeout(repaint, 0);
    }
  }, true);
})();
