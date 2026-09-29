/* 셸 — 시작 메뉴와 찾기.
 *
 * 상단바 왼쪽 로고(또는 Ctrl+K)가 연다. 비어 있으면 앱과 최근 작품을, 글자를 치면
 * 앱 · AI 기능(체험하기의 16가지와 내가 가르친 AI) · 작품 · 설정을 한꺼번에 찾는다.
 * "얼굴" 을 치면 체험하기의 얼굴 기능들, 얼굴이 들어간 작품, 관련 설정이 같이 나온다.
 * ↑↓ 로 고르고 Enter 로 연다.
 *
 * os.html 이 EL_SHELL.api 를, lib/os-quick.js 가 EL_SHELL.quick 을 연 뒤에 읽는다.
 */
(function () {
  "use strict";
  var S = window.EL_SHELL, A = S && S.api;
  if (!A) return;
  var esc = A.esc, icon = A.icon;
  var APPS = window.EL_APPS;

  var UI = {
    ko: {
      ph: "앱 · 기능 · 작품 · 설정 찾기", hint: "Ctrl+K",
      apps: "앱", funcs: "AI 기능", works: "작품", sets: "설정", recent: "최근 작품",
      none: "‘{q}’ 을(를) 찾지 못했어요.", desk: "바탕화면 보기", lock: "잠금", power: "끄기",
      inTry: "체험하기", mine: "내가 가르친 AI", noRecent: "아직 저장한 작품이 없어요.",
      kind: { blocks: "블록", code: "파이썬", project: "가르치기 작품" },
      set: {
        hc: ["밝은 곳 모드", "화면 대비 · 빛 반사"], snd: ["소리 시험", "스피커 · 소리 안 남"],
        mic: ["마이크 시험", "녹음 · 목소리 안 들림"], tour: ["처음 안내 다시 보기", "도움말 · 사용법"],
        folder: ["작업 폴더 열기", "탐색기 · 파일 · 저장 위치"], name: ["이름 바꾸기", "내 이름 · 사용자"],
        lock: ["잠금", "선생님 · 화면 가리기"], bye: ["끄기", "종료 · 전원"],
        teacher: ["선생님 모드", "수업 · 점검 · 미션"], docs: ["API 문서", "서버 · 선생님"],
        voice: ["목소리 고르기", "TTS · 말소리"], wall: ["바탕화면 그림", "배경 · 꾸미기"],
        settings: ["설정 열기", "수업 전 점검 · 결과물"]
      }
    },
    en: {
      ph: "Find apps, AI, work, settings", hint: "Ctrl+K",
      apps: "Apps", funcs: "AI", works: "Work", sets: "Settings", recent: "Recent work",
      none: "Nothing found for ‘{q}’.", desk: "Show desktop", lock: "Lock", power: "Shut down",
      inTry: "Try it", mine: "My own AI", noRecent: "Nothing saved yet.",
      kind: { blocks: "Blocks", code: "Python", project: "Train project" },
      set: {
        hc: ["Bright room", "contrast · glare"], snd: ["Sound test", "speaker · no sound"],
        mic: ["Mic test", "record · voice"], tour: ["Guided tour again", "help · how to"],
        folder: ["Open work folder", "explorer · files · where saved"], name: ["Change name", "user"],
        lock: ["Lock", "teacher · cover screen"], bye: ["Shut down", "exit · power"],
        teacher: ["Teacher mode", "class · checks · mission"], docs: ["API docs", "server · teacher"],
        voice: ["Choose voice", "TTS · speech"], wall: ["Desktop picture", "background"],
        settings: ["Open Settings", "checks · results"]
      }
    }
  };
  function T(k) { var L = UI[A.lang()] || UI.ko; return L[k] !== undefined ? L[k] : UI.ko[k]; }
  function en() { return A.lang() === "en"; }
  function hiddenApp(h) { return (S.hidden || []).indexOf(h) >= 0 && !S.teacher; }

  var SET_IC = {
    hc: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="12" r="8"/><path d="M12 4a8 8 0 0 1 0 16Z" fill="currentColor"/></svg>',
    lock: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><rect x="5" y="10.5" width="14" height="10" rx="2"/><path d="M8 10.5V7.5a4 4 0 0 1 8 0v3"/></svg>',
    bye: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 3v8"/><path d="M6.3 6.8a8 8 0 1 0 11.4 0"/></svg>',
    find: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><circle cx="11" cy="11" r="6.5"/><path d="m20 20-4.3-4.3"/></svg>',
    desk: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"><rect x="3" y="4" width="18" height="13" rx="2"/><path d="M8 20h8M12 17v3"/></svg>'
  };

  /* 설정 항목 → 이미 있는 아이콘 */
  var SET_AS = { snd: "talk", mic: "talk", voice: "talk", tour: "eye", folder: "folder", name: "face",
                 wall: "bg", teacher: "train", docs: "code", settings: "gear" };

  var css = document.createElement("style");
  css.textContent = [
    "#osStartMenu{position:fixed;top:46px;left:8px;z-index:86;width:min(560px,calc(100% - 16px));max-height:calc(100dvh - 58px);",
    "  display:flex;flex-direction:column;border-radius:20px;padding:14px;background:rgba(250,246,238,.98);",
    "  border:1px solid rgba(74,63,46,.18);box-shadow:0 22px 50px rgba(44,74,124,.26)}",
    "#osStartMenu[hidden]{display:none}",
    ".sm-find{display:flex;align-items:center;gap:10px;height:46px;padding:0 14px;border-radius:23px;background:#fff;border:2px solid var(--cyan)}",
    ".sm-find svg{width:19px;height:19px;color:var(--cyan);flex:0 0 auto}",
    ".sm-find input{flex:1;min-width:0;border:0;outline:0;font:inherit;font-size:16px;background:none;color:var(--ink)}",
    ".sm-find kbd{font-family:inherit;font-size:11.5px;color:var(--ink-2);border:1px solid rgba(74,63,46,.25);border-radius:6px;padding:1px 6px}",
    ".sm-body{overflow-y:auto;margin-top:6px;padding-right:2px}",
    ".sm-h{font-size:12px;color:var(--ink-2);margin:12px 4px 6px}",
    ".sm-apps{display:grid;grid-template-columns:repeat(4,1fr);gap:6px}",
    ".sm-app{display:flex;flex-direction:column;align-items:center;gap:6px;padding:10px 4px;border-radius:14px;font-size:13px;text-align:center;cursor:pointer}",
    ".sm-app:hover{background:rgba(31,95,122,.08)}",
    ".sm-app .g{width:44px;height:44px;border-radius:14px;display:grid;place-items:center;background:var(--cyan);color:#fff}",
    ".sm-app .g svg{width:24px;height:24px}",
    ".sm-r{display:flex;align-items:center;gap:12px;width:100%;min-height:46px;padding:5px 10px;border-radius:12px;text-align:left;cursor:pointer;font-size:14.5px;color:var(--ink)}",
    ".sm-r:hover,.sm-r.sel{background:var(--cyan-bg)}",
    ".sm-r .i{width:34px;height:34px;border-radius:11px;display:grid;place-items:center;background:var(--cyan);color:#fff;flex:0 0 auto}",
    ".sm-r .i svg{width:19px;height:19px}",
    ".sm-r .i.f{background:#fff;color:var(--ink-2);border:1.5px solid rgba(74,63,46,.22)}",
    ".sm-r .i.s{background:#5b6b76}",
    ".sm-r span.t{flex:1;min-width:0}",
    ".sm-r span.t i{display:block;font-style:normal;font-size:12px;color:var(--ink-2);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}",
    ".sm-r kbd{font-family:inherit;font-size:12px;color:var(--cyan-d);background:#fff;border:1px solid rgba(31,95,122,.3);border-radius:6px;padding:2px 7px}",
    ".sm-r mark{background:#ffe08a;color:inherit;border-radius:3px;padding:0 1px}",
    ".sm-none{font-size:13.5px;color:var(--ink-2);padding:16px 6px}",
    ".sm-foot{display:flex;align-items:center;gap:8px;margin-top:12px;padding-top:12px;border-top:1px solid rgba(74,63,46,.12)}",
    ".sm-foot img{width:32px;height:32px}.sm-foot b{font-size:14px;flex:1;min-width:0}",
    ".sm-btn{height:36px;padding:0 13px;border-radius:18px;border:1px solid rgba(74,63,46,.2);background:#fff;font:inherit;font-size:13.5px;",
    "  font-weight:700;display:inline-flex;align-items:center;gap:6px;cursor:pointer;color:var(--ink)}",
    ".sm-btn svg{width:15px;height:15px}.sm-btn:hover{border-color:var(--cyan)}",
    "@media (max-width:560px){.sm-apps{grid-template-columns:repeat(3,1fr)}}"
  ].join("\n");
  document.head.appendChild(css);

  var m = document.createElement("div");
  m.id = "osStartMenu"; m.hidden = true;
  m.innerHTML = '<div class="sm-find">' + SET_IC.find + '<input id="smQ" type="search" autocomplete="off"><kbd></kbd></div>' +
                '<div class="sm-body" id="smBody"></div>' +
                '<div class="sm-foot"><img src="/assets/pibo-hello.png" alt=""><b id="smWho"></b>' +
                '<button class="sm-btn" type="button" data-f="desk">' + SET_IC.desk + '<span></span></button>' +
                '<button class="sm-btn" type="button" data-f="lock">' + SET_IC.lock + '<span></span></button>' +
                '<button class="sm-btn" type="button" data-f="bye">' + SET_IC.bye + '<span></span></button></div>';
  document.body.appendChild(m);
  var q = m.querySelector("#smQ");

  /* ── 찾을 거리 ── */
  var works = [], models = [];
  function loadWorks() {
    var get = function (url) {
      return fetch(url).then(function (r) { return r.json(); })
        .then(function (j) { return j && j.result === "ok" && Array.isArray(j.data) ? j.data : []; })
        .catch(function () { return []; });
    };
    return Promise.all([get("/blocks/works"), get("/pycode/works"), get("/custom/projects"), get("/custom/models")]).then(function (r) {
      var when = function (s) { var d = s ? new Date(String(s).replace(" ", "T")) : null; return d && !isNaN(d) ? d.getTime() : 0; };
      works = [].concat(
        r[0].map(function (w) { return { kind: "blocks", ic: "blocks", name: w.name, at: w.mtime * 1000, href: "/blocks?open=" + encodeURIComponent(w.name) }; }),
        r[1].map(function (w) { return { kind: "code", ic: "code", name: w.name, at: w.mtime * 1000, href: "/code?open=" + encodeURIComponent(w.name) }; }),
        r[2].map(function (w) { return { kind: "project", ic: "train", name: w.title || w.slug, at: when(w.saved), href: "/train?project=" + encodeURIComponent(w.slug) }; })
      ).sort(function (a, b) { return b.at - a.at; });
      models = r[3];
    });
  }
  function funcs() {
    var L = A.lang(), out = [];
    Object.keys(APPS.SERVICE_LIST).forEach(function (k) {
      if (k.indexOf("custom:") === 0) return;
      var sv = APPS.SERVICE_LIST[k];
      out.push({ ic: sv.ic || "eye", name: APPS.name(k, L), sub: T("inTry") + " · " + APPS.tip(k, L),
                 keys: k + " " + (sv.en || "") + " " + (sv.tooltip || ""), href: "/try?m=" + encodeURIComponent(k) });
    });
    models.forEach(function (x) {
      out.push({ ic: "custom", name: x.title || x.slug, sub: T("mine") + " · " + (x.labels || []).join(" · "),
                 keys: T("mine") + " " + (x.labels || []).join(" "), href: "/try?m=" + encodeURIComponent("custom:" + x.slug) });
    });
    return out;
  }
  function settings() {
    var s = T("set"), Q = S.quick || {};
    var act = {
      hc: Q.hc, snd: Q.snd, mic: Q.mic, tour: Q.tour, folder: Q.folder, name: Q.name, bye: Q.bye, voice: Q.open, wall: Q.open,
      lock: function () { if (S.lock) S.lock(); },
      teacher: function () { if (S.teacherToggle) S.teacherToggle(); },
      docs: function () { A.open("/docs"); },
      settings: function () { A.open("/options"); }
    };
    return Object.keys(s).map(function (k) {
      return { ic: k, name: s[k][0], sub: s[k][1], keys: s[k][1], run: act[k] };
    });
  }

  /* ── 그리기 ── */
  var items = [], sel = 0;
  function mark(text, qq) {
    var s = String(text), i = qq ? s.toLowerCase().indexOf(qq) : -1;
    if (i < 0) return esc(s);
    return esc(s.slice(0, i)) + "<mark>" + esc(s.slice(i, i + qq.length)) + "</mark>" + esc(s.slice(i + qq.length));
  }
  function row(it, qq, cls) {
    var ic = SET_IC[it.ic] || icon(SET_AS[it.ic] || it.ic);
    return '<button class="sm-r" type="button" data-i="' + items.length + '"><span class="i' + (cls ? " " + cls : "") + '">' + ic +
           '</span><span class="t">' + mark(it.name, qq) + "<i>" + esc(it.sub || "") + "</i></span></button>";
  }
  function paint() {
    var qq = q.value.trim().toLowerCase();
    var body = m.querySelector("#smBody"), h = "";
    items = [];
    var hit = function (it) { return !qq || (it.name + " " + (it.sub || "") + " " + (it.keys || "")).toLowerCase().indexOf(qq) >= 0; };
    var apps = APPS.APPS.filter(function (a) { return !hiddenApp(a.href); }).map(function (a) {
      return { ic: a.ic, name: en() ? a.en : a.ko, sub: en() ? a.en_d : a.ko_d, keys: a.ko + " " + a.en, href: a.href };
    });
    if (!qq) {
      h += '<div class="sm-h">' + esc(T("apps")) + '</div><div class="sm-apps">';
      apps.forEach(function (a) {
        h += '<button class="sm-app" type="button" data-i="' + items.length + '"><span class="g">' + icon(a.ic) + "</span>" + esc(a.name) + "</button>";
        items.push(a);
      });
      h += '</div><div class="sm-h">' + esc(T("recent")) + "</div>";
      var rec = works.slice(0, 5);
      if (!rec.length) h += '<div class="sm-none">' + esc(T("noRecent")) + "</div>";
      rec.forEach(function (w) { var it = { ic: w.ic, name: w.name, sub: T("kind")[w.kind], href: w.href }; h += row(it, "", "f"); items.push(it); });
    } else {
      var groups = [
        [T("apps"), apps.filter(hit), ""],
        [T("funcs"), funcs().filter(hit).slice(0, 8), ""],
        [T("works"), works.map(function (w) { return { ic: w.ic, name: w.name, sub: T("kind")[w.kind], keys: T("kind")[w.kind], href: w.href }; }).filter(hit).slice(0, 6), "f"],
        [T("sets"), settings().filter(hit), "s"]
      ];
      groups.forEach(function (g) {
        if (!g[1].length) return;
        h += '<div class="sm-h">' + esc(g[0]) + "</div>";
        g[1].forEach(function (it) { h += row(it, qq, g[2]); items.push(it); });
      });
      if (!items.length) h = '<div class="sm-none">' + esc(T("none").replace("{q}", q.value.trim())) + "</div>";
    }
    body.innerHTML = h;
    sel = qq && items.length ? 0 : -1;
    paintSel();
    m.querySelector("#smWho").textContent = A.who() || "";
    m.querySelector('[data-f="desk"] span').textContent = T("desk");
    m.querySelector('[data-f="lock"] span').textContent = T("lock");
    m.querySelector('[data-f="bye"] span').textContent = T("power");
    q.placeholder = T("ph");
    m.querySelector(".sm-find kbd").textContent = T("hint");
  }
  function paintSel() {
    m.querySelectorAll("[data-i]").forEach(function (b) { b.classList.toggle("sel", +b.getAttribute("data-i") === sel); });
    var s = m.querySelector("[data-i].sel");
    if (s) s.scrollIntoView({ block: "nearest" });
  }
  function run(i) {
    var it = items[i];
    if (!it) return;
    show(false);
    if (it.run) it.run(); else if (it.href) A.open(it.href);
  }

  function show(on) {
    m.hidden = !on;
    document.getElementById("osStart").classList.toggle("on", on);
    if (on) {
      q.value = "";
      paint();
      setTimeout(function () { q.focus(); }, 0);
      loadWorks().then(function () { if (!m.hidden) paint(); });
    } else {
      document.getElementById("osStart").classList.toggle("on", A.active() === null);
    }
  }
  S.onStart = function () { show(m.hidden); };
  S.keyFns["ctrl+k"] = function () { show(true); };
  S.keys.push("ctrl+k");

  q.addEventListener("input", paint);
  q.addEventListener("keydown", function (e) {
    if (e.key === "ArrowDown") { e.preventDefault(); sel = Math.min(items.length - 1, sel + 1); paintSel(); }
    else if (e.key === "ArrowUp") { e.preventDefault(); sel = Math.max(0, sel - 1); paintSel(); }
    else if (e.key === "Enter") { e.preventDefault(); run(sel < 0 ? 0 : sel); }
    else if (e.key === "Escape") { show(false); }
  });
  m.addEventListener("click", function (e) {
    e.stopPropagation();
    var b = e.target.closest("[data-i]");
    if (b) { run(+b.getAttribute("data-i")); return; }
    var f = e.target.closest("[data-f]");
    if (!f) return;
    var k = f.getAttribute("data-f");
    show(false);
    if (k === "desk") A.showDesk();
    else if (k === "lock" && S.lock) S.lock();
    else if (k === "bye" && S.quick) S.quick.bye();
  });
  document.addEventListener("click", function () { if (!m.hidden) show(false); });
  document.addEventListener("keydown", function (e) { if (e.key === "Escape" && !m.hidden) show(false); });
  A.onLang(function () { if (!m.hidden) paint(); });
})();
