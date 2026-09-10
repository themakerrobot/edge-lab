/* 셸 — 타이틀바의 [닫기] 와 앱 이름을 만든다. 일곱 페이지가 이 파일 하나를 쓴다.
 *
 * 휴대폰 홈 화면 방식이다. 홈(/)에는 아이콘만 있고, 하나를 누르면 그 앱이
 * 화면을 통째로 쓰고, 오른쪽 위 [×] 로 닫으면 홈으로 돌아간다.
 * 항상 떠 있는 이동 줄(예전 헤더 탭, 그 다음의 세로 레일)은 두지 않는다 —
 * 홈이 곧 이동이라 둘이 겹쳤고, 화면 폭만 먹었다.
 *
 * 페이지가 갖춰야 할 마크업 — 이것뿐이다:
 *
 *     <div class="titlebar">
 *       <a class="tb-brand" href="/"><img src="/assets/pibo-logo.png" alt=""><b>edge-lab</b></a>
 *       <span class="tb-sep"></span>
 *       <span class="tb-app" id="txtTitle"></span>
 *       <div class="h-tools">
 *         <button id="langButton" title="한국어 / English">EN</button>
 *       </div>
 *     </div>
 *     <div class="shell-body"><div class="workbench"> ... 페이지 내용 ... </div></div>
 *
 * </body> 앞에 (sysbar.js 앞):
 *     <script src="/lib/shell.js"></script>
 *
 * 앱 이름은 이 파일이 **혼자** 갖는다. 페이지가 #txtTitle 을 따로 채우지 않는다.
 */
(function () {
  "use strict";

  var APP = {
    "/":         { ko: "홈",         en: "Home" },
    "/try":      { ko: "체험하기",   en: "Try it" },
    "/blocks":   { ko: "블록",       en: "Blocks" },
    "/code":     { ko: "파이썬",     en: "Python" },
    "/train":    { ko: "가르치기",   en: "Train" },
    "/talk":     { ko: "대화",       en: "Talk" },
    "/options":  { ko: "설정",       en: "Settings" }
  };
  var CLOSE = { ko: "닫기", en: "Close" };

  function lang() {
    try { return localStorage.getItem("vapiLang") === "en" ? "en" : "ko"; }
    catch (e) { return "ko"; }
  }
  function here() {
    var p = (location.pathname || "/").replace(/\/+$/, "");
    return p === "" ? "/" : p;
  }

  /* [× 닫기] — 홈이 아닌 화면에만. 도구 무리의 맨 끝, 창의 닫기 단추 자리다. */
  function build() {
    var tools = document.querySelector(".titlebar .h-tools");
    if (!tools || here() === "/" || document.getElementById("closeApp")) { paint(); return; }
    var a = document.createElement("a");
    a.id = "closeApp";
    a.className = "close";
    a.href = "/";
    a.innerHTML = '<span class="x" aria-hidden="true">×</span><span class="tx"></span>';
    tools.appendChild(a);
    paint();
  }

  function paint() {
    var L = lang();
    var el = document.getElementById("txtTitle");
    if (el) { var a = APP[here()]; el.textContent = a ? a[L] : ""; }
    var c = document.getElementById("closeApp");
    if (c) { c.title = CLOSE[L]; c.querySelector(".tx").textContent = CLOSE[L]; }
  }
  /* 이름은 예전 그대로 둔다 — 여섯 페이지가 이미 이 이름으로 부르고 있다 */
  window.navRepaint = paint;

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", build);
  else build();
  document.addEventListener("click", function (e) {
    if (e.target && e.target.closest && e.target.closest("#langButton")) setTimeout(paint, 0);
  }, true);
})();
