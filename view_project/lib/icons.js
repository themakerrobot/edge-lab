/* 아이콘 — 레일과 런처가 함께 쓴다.
 *
 * Font Awesome 을 쓰지 않는 이유가 둘 있다.
 *   1) assets/svg/ 에 있던 47개는 파일 헤더가 "Font Awesome Pro" 다.
 *      이 저장소는 AGPL-3.0 으로 재배포하므로 Pro 파일을 담아 보낼 수 없다.
 *   2) lib/fa/ 의 Free 판(CC BY 4.0)은 써도 되지만, 글리프 스무 개 때문에
 *      CSS 101KB + 웹폰트 155KB 를 교실 노트북에서 페이지마다 읽게 된다.
 * 그래서 필요한 것만 직접 그렸다 — 원·네모·선으로만 이뤄져 있어 다 합쳐 4KB 다.
 *
 * 쓰는 법:
 *     <script src="/lib/icons.js"></script>
 *     el.innerHTML = elIcon("home");        // <svg> 문자열을 돌려준다
 *
 * 선 굵기는 stroke-width 1.7 로 통일했다 — 아이가 보는 화면이라 26px 로 키워도
 * 획이 뭉치지 않고, 밝은 교실에서도 형태가 남는다. 색은 currentColor 를 따른다.
 */
(function () {
  "use strict";

  /* viewBox 는 전부 0 0 24 24. 채우기 없이 선으로만 그린다. */
  var P = {
    /* ── 앱 ── */
    home:    '<path d="M3 10 12 3l9 7"/><path d="M5.5 9.5V20h13V9.5"/><path d="M10 20v-5.5h4V20"/>',
    eye:     '<path d="M2 12c3.2-4.6 6.6-6.9 10-6.9S18.8 7.4 22 12c-3.2 4.6-6.6 6.9-10 6.9S5.2 16.6 2 12Z"/><circle cx="12" cy="12" r="3.1"/>',
    blocks:  '<rect x="3" y="3" width="8" height="8" rx="1.2"/><rect x="13" y="3" width="8" height="8" rx="1.2"/><rect x="3" y="13" width="8" height="8" rx="1.2"/><path d="M13 17h8M17 13v8"/>',
    code:    '<path d="M8.5 7.5 3.5 12l5 4.5"/><path d="M15.5 7.5 20.5 12l-5 4.5"/><path d="M13.4 4.5 10.6 19.5"/>',
    train:   '<path d="M12 4 22 8.6 12 13.2 2 8.6 12 4Z"/><path d="M6 10.6v4.9c0 1.7 2.7 3.1 6 3.1s6-1.4 6-3.1v-4.9"/><path d="M22 8.6v5.2"/>',
    talk:    '<path d="M3.5 5.5h17v11h-9l-5 4v-4h-3v-11Z"/><path d="M8 10h1.5M11.5 10H13M15 10h1.5"/>',
    gear:    '<circle cx="12" cy="12" r="3.2"/><path d="M12 2.6v3M12 18.4v3M2.6 12h3M18.4 12h3M5.3 5.3l2.1 2.1M16.6 16.6l2.1 2.1M18.7 5.3l-2.1 2.1M7.4 16.6l-2.1 2.1"/>',

    /* ── AI 앱 ── */
    face:    '<circle cx="12" cy="12" r="9"/><path d="M8.4 14.4c1 1.3 2.2 2 3.6 2s2.6-.7 3.6-2"/><path d="M9 9.4v1M15 9.4v1"/>',
    faceAge: '<circle cx="12" cy="12" r="9"/><path d="M9 9.4v1M15 9.4v1"/><path d="M8.6 15h6.8"/>',
    faceDir: '<circle cx="10" cy="12" r="8"/><path d="M7.4 9.6v1M12.4 9.6v1"/><path d="M18.4 12h4M20.2 9.8 22.4 12l-2.2 2.2"/>',
    mask:    '<path d="M4.4 8.6c2.6-1.2 4.8-1.8 7.6-1.8s5 .6 7.6 1.8v5.2c0 2.6-3.6 4.6-7.6 4.6s-7.6-2-7.6-4.6V8.6Z"/><path d="M4.4 11.4h15.2M2 8l2.4.6M22 8l-2.4.6"/>',
    pose:    '<circle cx="12" cy="4.6" r="2.3"/><path d="M12 7.2v6.4M12 13.6 8.4 20.4M12 13.6l3.6 6.8M12 9.2 7.6 11M12 9.2l4.4 1.8"/>',
    hand:    '<path d="M8.5 11V4.8a1.6 1.6 0 0 1 3.2 0V11"/><path d="M11.7 11V6.4a1.6 1.6 0 0 1 3.2 0V11"/><path d="M14.9 11V8.2a1.6 1.6 0 0 1 3.2 0V15c0 3.3-2.4 5.6-5.7 5.6S6.2 18.3 6.2 15v-2.4l-1.4-1.9a1.5 1.5 0 0 1 2.3-1.9l1.4 1.6"/>',
    object:  '<rect x="2.8" y="6" width="11" height="9" rx="1"/><rect x="10.2" y="10.5" width="11" height="8" rx="1" stroke-dasharray="3 2.2"/>',
    seg:     '<path d="M3.4 12.6c1.8-4.4 4.6-6.6 8.6-6.6s6.8 2.2 8.6 6.6c-1.8 4-4.6 6-8.6 6s-6.8-2-8.6-6Z" stroke-dasharray="3 2.2"/><path d="M9.4 12.3h5.2"/>',
    vlm:     '<path d="M3.4 4.6h17.2v12.2H12l-5.3 4.1v-4.1H3.4V4.6Z"/><path d="M9.9 8.6a2.2 2.2 0 1 1 2.6 2.4v1.4"/><path d="M12.4 14.3v.9"/>',
    bg:      '<path d="M3.2 3.2h4M9.6 3.2h4.8M16.8 3.2h4v4M20.8 9.6v4.8M20.8 16.8v4h-4M14.4 20.8H9.6M7.2 20.8h-4v-4M3.2 14.4V9.6"/><circle cx="12" cy="12" r="3.4"/>',
    sr:      '<circle cx="10.6" cy="10.6" r="6.6"/><path d="m15.6 15.6 4.6 4.6"/><path d="M10.6 7.9v5.4M7.9 10.6h5.4"/>',
    depth:   '<path d="M12 3.2 21.4 8 12 12.8 2.6 8 12 3.2Z"/><path d="m2.6 12 9.4 4.8 9.4-4.8"/><path d="m2.6 16 9.4 4.8 9.4-4.8"/>',
    text:    '<path d="M4.6 19 11 5h2l6.4 14"/><path d="M7.3 14.2h9.4"/>',
    qr:      '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><path d="M14 14h3v3h-3zM19.5 14v2M14 19.5h2M19 19.5h2M19.5 21.5v-1"/>',
    custom:  '<path d="M12 2.8 14.6 8.4 20.7 9.2 16.3 13.4 17.4 19.4 12 16.5 6.6 19.4 7.7 13.4 3.3 9.2 9.4 8.4 12 2.8Z"/>'
  };

  /* name 이 없으면 빈 네모를 준다 — 화면이 무너지는 것보다 낫다 */
  window.elIcon = function (name) {
    var d = P[name] || '<rect x="4" y="4" width="16" height="16" rx="2"/>';
    return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" ' +
           'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">' +
           d + '</svg>';
  };
  window.elIconNames = function () { return Object.keys(P); };
})();
