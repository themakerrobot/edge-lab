/* 헤더 이동 탭 — 여섯 페이지가 함께 쓴다.
 *
 * 전에는 첫 화면(체험하기)에만 [블록][파이썬][가르치기][대화][설정] 이 있고
 * 나머지 화면에는 집(⌂) 하나뿐이었다. 그래서 다른 화면으로 가려면 반드시
 * 집으로 돌아왔다 다시 들어가야 했고, "지금 어디에 있는지" 도 안 보였다.
 *
 * 이제 어느 화면에서나 같은 탭 줄이 서고, 지금 보고 있는 화면의 탭이 눌린
 * 모양으로 표시된다 — 탭을 눌러 옮겨 다니는 느낌이 되도록.
 *
 * 쓰는 법 — 페이지 </body> 앞에 한 줄 (sysbar.js 보다 먼저):
 *     <script src="/lib/nav.js"></script>
 * 헤더의 .h-tools 안, [한/영] 앞에 탭이 자동으로 붙는다.
 * 페이지 HTML 에는 이동 링크를 두지 않는다 — 여섯 벌로 갈라지는 자리라서다.
 *
 * 생김새(네모 탭 · 지금 화면 강조)는 lib/ui.css 가 정한다.
 */
(function () {
  "use strict";

  /* 경로 · 라벨 — 순서가 곧 탭 순서다.
     아이콘은 두지 않는다: 파이보 랩·센스 랩의 탭도 글자만이라, 셋을 나란히
     열었을 때 같은 제품으로 보이려면 여기도 글자여야 한다. */
  var TABS = [
    { id: "homeLink",    href: "/",        ko: "체험하기",   en: "Try it" },
    { id: "blocksLink",  href: "/blocks",  ko: "블록",     en: "Blocks" },
    { id: "codeLink",    href: "/code",    ko: "파이썬",   en: "Python" },
    { id: "trainLink",   href: "/train",   ko: "가르치기", en: "Train" },
    { id: "talkLink",    href: "/talk",    ko: "대화",     en: "Talk" },
    { id: "optionsLink", href: "/options", ko: "설정",     en: "Settings" },
  ];

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

  function build() {
    var tools = document.querySelector(".header .h-tools");
    if (!tools || tools.querySelector(".nav-tab")) return;

    var L = lang(), now = here();
    var langBtn = document.getElementById("langButton");
    var frag = document.createDocumentFragment();

    TABS.forEach(function (tab) {
      var a = document.createElement("a");
      a.className = "nav-tab" + (tab.href === now ? " on" : "");
      a.id = tab.id;
      a.href = tab.href;
      a.title = tab[L];
      if (tab.href === now) {
        a.setAttribute("aria-current", "page");
        a.removeAttribute("href");            /* 지금 화면은 눌러도 새로 안 읽는다 */
      }
      a.innerHTML = '<span class="tx">' + tab[L] + '</span>';
      frag.appendChild(a);
    });

    if (langBtn) tools.insertBefore(frag, langBtn);
    else tools.appendChild(frag);
  }

  /* 페이지가 언어를 바꾸면 글자도 따라 바꾼다 (새로고침하는 페이지도 있지만
     대화·체험하기처럼 그 자리에서 바꾸는 페이지가 있어 둘 다 대응한다) */
  function repaint() {
    var L = lang();
    TABS.forEach(function (tab) {
      var a = document.getElementById(tab.id);
      if (!a) return;
      var tx = a.querySelector(".tx");
      if (tx) tx.textContent = tab[L];
      a.title = tab[L];
    });
  }
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
