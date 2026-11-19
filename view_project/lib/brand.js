/* 제품 이름 — brand.json 에서 tools/rename_brand.py 가 만든다. 손으로 고치지 않는다.
 *   EL_BRAND.label()  화면에 보이는 이름 (한국어 화면은 name_ko, 영어 화면은 name)
 *   EL_BRAND.tag()    부제
 *   EL_BRAND.ko("을") 한국어 이름 + 맞는 조사 */
window.EL_BRAND = {
 "name": "edge-lab",
 "name_ko": "edge-lab",
 "tagline": "인터넷 없이 내 컴퓨터에서 실행돼요",
 "tagline_en": "Runs on this computer, no internet needed",
 "slug": "edge-lab",
 "work_folder": "Edge Lab",
 "appdata_folder": "EdgeLab",
 "repo_github": "themakerrobot/edge-lab",
 "repo_hf": "leeyunjai/edge-lab"
};
(function (B) {
  function lang() { try { return localStorage.getItem("vapiLang") === "en" ? "en" : "ko"; } catch (e) { return "ko"; } }
  B.label = function (L) { return (L || lang()) === "en" ? B.name : B.name_ko; };
  B.tag = function (L) { return (L || lang()) === "en" ? B.tagline_en : B.tagline; };
  function batchim(w) {
    var c = String(w).replace(/\s+$/, "").slice(-1);
    if (c >= "가" && c <= "힣") return (c.charCodeAt(0) - 0xAC00) % 28 !== 0;
    return "bklmnpt".indexOf(c.toLowerCase()) >= 0;
  }
  var PAIRS = { "을": ["을", "를"], "를": ["을", "를"], "은": ["은", "는"], "는": ["은", "는"],
               "이": ["이", "가"], "가": ["이", "가"], "과": ["과", "와"], "와": ["과", "와"] };
  B.ko = function (p) {
    var pr = PAIRS[p || "을"] || [p, p], n = B.name_ko, last = n.slice(-1);
    return n + (last >= "가" && last <= "힣" ? "" : " ") + (batchim(n) ? pr[0] : pr[1]);
  };
})(window.EL_BRAND);
