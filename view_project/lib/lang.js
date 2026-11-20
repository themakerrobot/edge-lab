/* 요청의 말 — 이 서버로 가는 모든 요청에 화면 언어(X-Lang: ko · en)를 붙인다.
 * 서버가 오류 · 안내 글을 화면 언어로 돌려준다 (i18n.py · main.py 의 _request_lang).
 * 언어를 바꾸면 다음 요청부터 바로 따른다(보낼 때마다 localStorage 의 vapiLang 을 읽는다).
 * 헤더를 못 붙이는 요청(<img src> 등)을 위해 같은 값을 쿠키 vapiLang 에도 둔다.
 *
 * 쓰는 법 — 모든 화면의 <head>, lib/brand.js 바로 뒤:
 *     <script src="/lib/lang.js"></script>      (tools/release_check.py 가 본다)
 */
(function () {
  "use strict";
  function lang() {
    try { return localStorage.getItem("vapiLang") === "en" ? "en" : "ko"; } catch (e) { return "ko"; }
  }
  function cookie(L) {
    try { document.cookie = "vapiLang=" + L + "; path=/; SameSite=Lax"; } catch (e) {}
  }
  cookie(lang());
  window.addEventListener("storage", function (e) { if (e.key === "vapiLang") cookie(lang()); });

  if (!window.fetch || window.__vapiLangFetch) return;
  window.__vapiLangFetch = true;
  var raw = window.fetch.bind(window);
  window.fetch = function (url, opt) {
    try {
      var isReq = typeof Request !== "undefined" && url instanceof Request;
      if (new URL(isReq ? url.url : String(url), location.href).origin === location.origin) {
        var L = lang();
        cookie(L);
        opt = Object.assign({}, opt || {});
        var h = new Headers(opt.headers || (isReq ? url.headers : undefined));
        if (!h.has("X-Lang")) h.set("X-Lang", L);
        opt.headers = h;
      }
    } catch (e) { /* 이상한 주소면 그대로 보낸다 */ }
    return raw(url, opt);
  };
})();
