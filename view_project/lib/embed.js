/* 창 모드 — 페이지가 셸(/) 안의 창(iframe)으로 열렸을 때만 켜진다.
 *
 * 셸은 페이지 여럿을 창으로 띄워 두고 하나만 보여 준다. 뒤로 간 창도 살아 있다.
 * 그런데 iframe 은 가려져도 스스로 모른다 — display:none 이어도 visibilityState 는
 * 최상위 문서를 따라 "visible" 로 남는다. 그래서 카메라·실시간 인식이 뒤에서 계속
 * 돈다. 셸이 "숨김/보임" 을 알려 주고, 이 파일이 페이지에 전한다.
 *
 * 쓰는 법 — <head> 안, tokens.css 바로 뒤, 다른 스크립트보다 먼저:
 *     <script src="/lib/embed.js"></script>
 *
 * 페이지가 쓰는 것 (창이 아닐 때도 있으므로 늘 그대로 부르면 된다):
 *     EL_WIN.embedded          셸 안의 창인가
 *     EL_WIN.hidden            지금 가려져 있나
 *     EL_WIN.onHide(fn)        가려질 때 — 카메라를 끄고 실시간 인식을 멈춘다
 *     EL_WIN.onShow(fn)        다시 보일 때
 *     EL_WIN.open("/code?…")   다른 화면 열기. 창이면 셸에 부탁하고, 아니면 그냥 이동한다
 *     EL_WIN.notify(글, { actions: [{ label, href }], always })
 *                              알림. 셸 상단바 알림 목록에 남고, 이 창이 안 보이는 중이면
 *                              (always 면 보고 있어도) 토스트로 뜬다. 창이 아니면 아무 일도 없다
 *
 * 이 파일이 혼자 하는 것 (창일 때):
 *   - 제목줄·부팅 덮개·시스템 패널을 숨긴다 (셸이 한 번만 보여 준다)
 *   - 앱 화면으로 가는 링크를 가로채 셸에 넘긴다 (창 안에서 다른 페이지로 바뀌지 않게)
 *   - 셸 단축키를 셸로 넘긴다
 *   - 카메라·마이크를 쓰는지 셸에 알린다 (상단바 "사용 중" 표시)
 *   - 가려질 때 페이지가 끄지 못한 카메라·마이크를 마지막으로 끈다
 * 창이 아니어도 하는 것:
 *   - 다른 창에서 언어를 바꾸면 따라 바꾼다, 밝은 곳 모드도 따라간다
 */
(function () {
  "use strict";

  var html = document.documentElement;
  var shell = null;
  try {
    if (window.parent !== window && window.parent.EL_SHELL) shell = window.parent;
  } catch (e) { /* 다른 출처가 감싼 경우 — 창 모드가 아니다 */ }

  var hideFns = [], showFns = [];
  var W = window.EL_WIN = {
    embedded: !!shell,
    hidden: false,
    onHide: function (fn) { hideFns.push(fn); },
    onShow: function (fn) { showFns.push(fn); },
    open: function (href) {
      if (shell) post("open", { href: href });
      else location.href = href;
    },
    /* 브라우저 밖에서 쓰는 카메라·마이크를 알린다 — 파이썬 프로그램(서버)이 camera()·listen()
       을 부를 때. 브라우저가 쥔 것은 이 파일이 저절로 알린다. */
    useMedia: function (kind, on) {
      if (!shell || (kind !== "camera" && kind !== "mic")) return;
      extra[kind] = !!on;
      report();
    },
    notify: function (text, opts) {
      if (!shell) return;
      opts = opts || {};
      post("notify", { text: String(text || ""), actions: opts.actions || [], always: !!opts.always });
    }
  };

  /* ── 창이 아니어도: 다른 창의 설정 변경을 따라간다 ── */
  window.addEventListener("storage", function (e) {
    if (e.key === "vapiLang") location.reload();          // 글자가 페이지 곳곳에 박혀 있어 새로 그린다
    else if (e.key === "vapi-hc") html.classList.toggle("hc", e.newValue === "1");
  });

  if (!shell) return;

  function post(action, data) {
    var m = { type: "el-win", action: action };
    for (var k in data || {}) m[k] = data[k];
    try { shell.postMessage(m, location.origin); } catch (e) {}
  }

  /* ── 제목줄·부팅 덮개·시스템 패널 숨기기 — 그려지기 전에 ── */
  html.classList.add("el-win");
  var st = document.createElement("style");
  st.textContent =
    "html.el-win .titlebar,html.el-win #boot,html.el-win #sysPanel{display:none!important}";
  (document.head || html).appendChild(st);

  /* ── 카메라·마이크 사용 보고 ── */
  var live = [];
  var extra = { camera: false, mic: false };      // EL_WIN.useMedia 로 페이지가 알린 것
  function report() {
    var cam = false, mic = false;
    live = live.filter(function (t) { return t.readyState === "live"; });
    live.forEach(function (t) { if (t.kind === "video") cam = true; else if (t.kind === "audio") mic = true; });
    post("media", { camera: cam || extra.camera, mic: mic || extra.mic });
  }
  var md = navigator.mediaDevices;
  if (md && md.getUserMedia) {
    var gum = md.getUserMedia.bind(md);
    md.getUserMedia = function (c) {
      return gum(c).then(function (s) {
        s.getTracks().forEach(function (t) {
          live.push(t);
          t.addEventListener("ended", report);
        });
        report();
        return s;
      });
    };
  }
  if (window.MediaStreamTrack) {
    var stop = MediaStreamTrack.prototype.stop;
    MediaStreamTrack.prototype.stop = function () {
      stop.call(this);
      if (live.indexOf(this) >= 0) report();
    };
  }

  /* ── 숨김 / 보임 ── */
  function run(list) {
    list.forEach(function (fn) { try { fn(); } catch (e) { console.error(e); } });
  }
  function setHidden(h) {
    if (W.hidden === h) return;
    W.hidden = h;
    html.classList.toggle("el-hidden", h);
    if (h) {
      run(hideFns);
      /* 페이지가 끄지 못한 것 — 가려진 창이 카메라를 쥐고 있으면 안 된다 */
      live.forEach(function (t) { if (t.readyState === "live") t.stop(); });
      report();
    } else {
      run(showFns);
      window.dispatchEvent(new Event("resize"));   // 블록 작업판처럼 크기를 다시 재야 하는 것들
    }
  }
  window.addEventListener("message", function (e) {
    if (e.source !== shell || !e.data || e.data.type !== "el-shell") return;
    if (e.data.action === "hide") setHidden(true);
    else if (e.data.action === "show") setHidden(false);
  });

  /* ── 앱 화면으로 가는 링크는 셸이 연다 ── */
  var APP_PATHS = ["/", "/home", "/try", "/blocks", "/code", "/train", "/talk", "/drive", "/paint", "/typing", "/calc", "/notes", "/recorder", "/story", "/works", "/tasks", "/board", "/store", "/options"];
  document.addEventListener("click", function (e) {
    if (e.defaultPrevented || e.button !== 0 || e.ctrlKey || e.metaKey || e.shiftKey) return;
    var a = e.target && e.target.closest ? e.target.closest("a[href]") : null;
    if (!a || a.hasAttribute("download")) return;
    var u;
    try { u = new URL(a.getAttribute("href"), location.href); } catch (err) { return; }
    if (u.origin !== location.origin) return;
    var path = u.pathname.replace(/\/+$/, "") || "/";
    var blank = a.target === "_blank";
    if (APP_PATHS.indexOf(path) < 0 && !blank) return;   // 같은 화면 안의 링크는 그대로
    var here = location.pathname.replace(/\/+$/, "") || "/";
    if (path === here && u.hash && !blank) return;      // 같은 화면 안의 #책갈피
    e.preventDefault();
    post("open", { href: path + u.search + u.hash, blank: blank });
  });

  /* ── 셸 단축키는 셸로 ── */
  function combo(e) {
    return (e.ctrlKey ? "ctrl+" : "") + (e.altKey ? "alt+" : "") + (e.shiftKey ? "shift+" : "") +
           (e.metaKey ? "meta+" : "") + String(e.key || "").toLowerCase();
  }
  document.addEventListener("keydown", function (e) {
    var keys = [];
    try { keys = shell.EL_SHELL.keys || []; } catch (err) {}
    var k = combo(e);
    if (keys.indexOf(k) < 0) return;
    e.preventDefault();
    e.stopPropagation();
    post("key", { key: k });
  }, true);

  /* ── 창이 떴다고 알린다 ── */
  function hello() { post("hello", { path: location.pathname, title: document.title }); }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", hello);
  else hello();
})();
