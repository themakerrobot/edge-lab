/* 셸 — 선생님 모드.
 *
 * 빠른 설정의 [선생님 모드] 나 찾기에서 들어온다. 선생님 번호가 있으면 번호를 묻고,
 * 처음이면 번호를 정하게 한다(비워 두면 번호 없이). 들어오면 상단바에 "선생님" 칩이
 * 생기고, 판에서 다음을 한다:
 *
 *   수업 전 점검   모델 · 장치 · 메모리 · 웹캠 · AI 준비를 한 번에 (/custom/selftest + /ready)
 *   수업 모드      오늘 쓸 앱만 학생에게 보이게 한다 (상단바 · 바탕화면 · 찾기에서 숨김)
 *   오늘의 미션    제목과 단계 셋 — 바탕화면 맨 위 카드로 보이고, 학생이 단계를 체크한다
 *   기록           오늘 앱별 사용 시간, 학습 성적표 수, 결과물 모두 내려받기
 *
 * 저장은 이 컴퓨터(앱 창 프로필)의 localStorage 다 — 교실 PC 마다 선생님이 정한다.
 *   el-teacher-pin  번호   el-class  {on, hidden:[경로]}   el-mission  {title, steps:[{text, href, done}]}
 * 번호는 아이들이 쉽게 못 들어오게 하는 문턱일 뿐 보안 장치가 아니다.
 */
(function () {
  "use strict";
  var S = window.EL_SHELL, A = S && S.api;
  if (!A) return;
  var esc = A.esc, icon = A.icon, APPS = window.EL_APPS;

  var UI = {
    ko: {
      chip: "선생님", title: "선생님 모드", exit: "선생님 모드 끝내기",
      pinAsk: "선생님 번호", pinSet: "선생님 번호를 정해 주세요", pinSetHint: "숫자 4자리 이상. 비워 두면 번호 없이 들어와요.",
      pinBad: "번호가 달라요", ok: "확인", cancel: "그만두기", pinChange: "번호 바꾸기",
      checkSec: "수업 전 점검", checkRun: "점검하기", checkHint: "수업 5분 전에 한 번 눌러 주세요.",
      k: { ai: "AI 준비", backbone: "특징 추출 모델", pose: "손 인식", face: "표정 인식", memory: "메모리", cpu: "CPU", storage: "저장 현황", camera: "웹캠", speaker: "소리" },
      aiLoading: "준비 중 {n}", sndBtn: "소리 시험", camNone: "웹캠을 쓸 수 없어요",
      classSec: "수업 모드", classOn: "수업 모드 켜기", classOff: "수업 모드 끄기", classHint: "체크한 앱만 학생에게 보여요. 켜 둔 창은 그대로 둬요.",
      classChip: "수업 중",
      misSec: "오늘의 미션", misTitle: "미션 제목", misStep: "{n}단계", misApp: "열 앱", misNone: "(앱 없음)",
      misSave: "바탕화면에 올리기", misClear: "미션 내리기", misSaved: "바탕화면에 올렸어요.",
      misCard: "오늘의 미션", misBy: "선생님이 정했어요",
      logSec: "기록", logToday: "오늘 쓴 시간", logNone: "아직 기록이 없어요.", min: "{n}분",
      logReports: "학습 성적표 {n}개", logOpen: "설정에서 자세히", logExport: "결과물 모두 내려받기",
      lockNow: "화면 잠그기"
    },
    en: {
      chip: "Teacher", title: "Teacher mode", exit: "Leave teacher mode",
      pinAsk: "Teacher number", pinSet: "Set a teacher number", pinSetHint: "4 or more digits. Leave empty to enter without one.",
      pinBad: "Wrong number", ok: "OK", cancel: "Cancel", pinChange: "Change number",
      checkSec: "Pre-class check", checkRun: "Run check", checkHint: "Press once, five minutes before class.",
      k: { ai: "AI ready", backbone: "Feature model", pose: "Hand tracking", face: "Face expressions", memory: "Memory", cpu: "CPU", storage: "Storage", camera: "Webcam", speaker: "Sound" },
      aiLoading: "loading {n}", sndBtn: "Sound test", camNone: "The webcam cannot be used",
      classSec: "Class mode", classOn: "Start class mode", classOff: "End class mode", classHint: "Only the checked apps are shown to students. Open windows stay.",
      classChip: "In class",
      misSec: "Today's mission", misTitle: "Mission title", misStep: "Step {n}", misApp: "App", misNone: "(no app)",
      misSave: "Put on the desktop", misClear: "Take it down", misSaved: "It is on the desktop.",
      misCard: "Today's mission", misBy: "Set by your teacher",
      logSec: "Records", logToday: "Time used today", logNone: "No records yet.", min: "{n} min",
      logReports: "{n} training reports", logOpen: "Details in Settings", logExport: "Download all student work",
      lockNow: "Lock the screen"
    }
  };
  function T(k) { var L = UI[A.lang()] || UI.ko; return L[k] !== undefined ? L[k] : UI.ko[k]; }
  function ls(k, v) {
    try {
      if (v === undefined) return localStorage.getItem(k);
      if (v === null) localStorage.removeItem(k); else localStorage.setItem(k, v);
    } catch (e) { return null; }
  }
  function lsj(k, d) { try { return JSON.parse(ls(k) || "null") || d; } catch (e) { return d; } }
  function appName(a) { return A.lang() === "en" ? a.en : a.ko; }

  var css = document.createElement("style");
  css.textContent = [
    "#osTeach{position:fixed;inset:0;z-index:95;display:grid;place-items:center;background:rgba(42,38,32,.3)}#osTeach[hidden]{display:none}",
    "#osTeach .card{width:min(860px,calc(100% - 24px));max-height:calc(100dvh - 60px);overflow-y:auto;background:var(--paper);",
    "  border:1.5px solid var(--line-d);border-radius:18px;padding:18px 20px;box-shadow:0 20px 50px rgba(44,74,124,.3)}",
    "#osTeach .hd{display:flex;align-items:center;gap:10px;margin-bottom:6px}",
    "#osTeach .hd h2{font-family:'Gowun Batang',serif;font-size:21px}#osTeach .hd .sp{flex:1}",
    ".t-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}",
    ".t-box{background:#fff;border:1px solid rgba(74,63,46,.14);border-radius:14px;padding:12px 14px;min-width:0}",
    ".t-box h3{font-size:14px;color:var(--cyan-d);margin-bottom:6px;display:flex;align-items:center;gap:8px}",
    ".t-box h3 .sp{flex:1}.t-hint{font-size:12.5px;color:var(--ink-2);margin-bottom:8px}",
    ".t-btn{height:34px;padding:0 13px;border-radius:17px;border:1px solid rgba(74,63,46,.25);background:#fff;font:inherit;font-size:13px;font-weight:700;cursor:pointer;color:var(--ink)}",
    ".t-btn.pri{background:var(--cyan);border-color:var(--cyan);color:#fff}.t-btn.danger{color:#a33b16;border-color:#f0b8a6}",
    ".t-chk{display:flex;align-items:center;gap:8px;padding:5px 2px;font-size:13.5px;border-bottom:1px dashed rgba(74,63,46,.14)}",
    ".t-chk .m{width:20px;height:20px;border-radius:50%;display:grid;place-items:center;color:#fff;font-size:12px;font-weight:700;background:#c9bda6;flex:0 0 auto}",
    ".t-chk.ok .m{background:#3a9a55}.t-chk.no .m{background:#d9412b}.t-chk b{flex:0 0 110px}.t-chk i{font-style:normal;color:var(--ink-2);font-size:12.5px;word-break:break-all}",
    ".t-apps{display:grid;grid-template-columns:1fr 1fr;gap:4px 10px;margin-bottom:10px}",
    ".t-apps label{display:flex;align-items:center;gap:7px;font-size:13.5px;padding:3px 0}.t-apps svg{width:17px;height:17px;color:var(--cyan-d)}",
    ".t-in{width:100%;height:36px;border-radius:10px;border:1.5px solid var(--line);padding:0 10px;font:inherit;font-size:14px;margin-bottom:6px;background:#fff}",
    ".t-step{display:grid;grid-template-columns:1fr 130px;gap:6px}.t-step select{height:36px;border-radius:10px;border:1.5px solid var(--line);font:inherit;font-size:13px;background:#fff}",
    ".t-row{display:flex;gap:6px;flex-wrap:wrap;align-items:center;margin-top:6px}.t-note{font-size:12.5px;color:var(--cyan-d)}",
    ".t-bar{display:flex;align-items:center;gap:6px;font-size:13px;margin:3px 0}.t-bar span{flex:0 0 76px}.t-bar i{flex:1;height:9px;border-radius:5px;background:#ece5d6;overflow:hidden}",
    ".t-bar i b{display:block;height:100%;background:var(--cyan)}.t-bar em{flex:0 0 48px;font-style:normal;text-align:right;color:var(--ink-2)}",
    "#osPin{position:fixed;inset:0;z-index:205;display:grid;place-items:center;background:rgba(42,38,32,.34)}#osPin[hidden]{display:none}",
    "#osPin .card{width:min(360px,calc(100% - 32px));background:var(--paper);border:1.5px solid var(--line-d);border-radius:16px;padding:18px;text-align:center}",
    "#osPin h2{font-family:'Gowun Batang',serif;font-size:18px;margin-bottom:6px}#osPin p{font-size:12.5px;color:var(--ink-2);margin-bottom:10px}",
    "#osPin input{width:170px;height:46px;border-radius:12px;border:1.5px solid var(--line);font:inherit;font-size:20px;text-align:center;letter-spacing:.3em}",
    "#osPin .bad{color:#a3321f;font-size:13px;min-height:1.3em;margin-top:4px}#osPin .row{display:flex;gap:8px;justify-content:center;margin-top:10px}",
    ".os-chip.t-chip{background:#f2a33a;border-color:#e0922c;color:#3a2508;font-weight:700;cursor:pointer}",
    ".os-chip.c-chip{background:#fff3db;border-color:#efc977;color:#6b4a0c;font-weight:700}",
    /* 바탕화면 미션 카드 */
    ".d-mission{grid-column:1/-1;display:grid;grid-template-columns:auto 1fr;gap:6px 16px;align-items:center;background:#fff8ea;border:1.5px solid #efc977;border-radius:18px;padding:12px 18px}",
    ".d-mission .bdg{grid-row:1/3;width:52px;height:52px;border-radius:16px;background:#f2a33a;color:#3a2508;display:grid;place-items:center;",
    "  font-family:'Gowun Batang',serif;font-weight:700;font-size:13px;text-align:center;line-height:1.15}",
    ".d-mission b{font-family:'Gowun Batang',serif;font-size:18px}.d-mission b small{font-family:inherit;font-weight:400;font-size:12.5px;color:var(--ink-2);margin-left:8px}",
    ".d-mission ol{display:flex;gap:6px;list-style:none;flex-wrap:wrap}",
    ".d-mission li{display:flex;align-items:center;gap:4px;background:#fff;border:1px solid #efc977;border-radius:16px;padding:0 4px 0 6px;font-size:13px;min-height:32px}",
    ".d-mission li.done{background:#eef4ec;border-color:#b9d8bd;color:#2f6a3a}",
    ".d-mission li .ck{width:22px;height:22px;border-radius:50%;border:1.5px solid #d8b35e;background:#fff;display:grid;place-items:center;font-size:12px;cursor:pointer;color:#2f6a3a}",
    ".d-mission li.done .ck{background:#3a9a55;border-color:#3a9a55;color:#fff}",
    ".d-mission li .go{padding:3px 8px;border-radius:12px;cursor:pointer;font-weight:700;color:var(--cyan-d)}.d-mission li .go:hover{background:var(--cyan-bg)}",
    "@media (max-width:760px){.t-grid{grid-template-columns:1fr}}"
  ].join("\n");
  document.head.appendChild(css);

  /* ─────────── 번호 ─────────── */
  var pinBox = document.createElement("div");
  pinBox.id = "osPin"; pinBox.hidden = true;
  document.body.appendChild(pinBox);
  function askPin(setting, done) {
    pinBox.innerHTML = '<div class="card"><h2>' + esc(setting ? T("pinSet") : T("pinAsk")) + "</h2>" +
      (setting ? "<p>" + esc(T("pinSetHint")) + "</p>" : "") +
      '<input type="password" inputmode="numeric" maxlength="8"><div class="bad"></div>' +
      '<div class="row"><button class="t-btn" type="button" data-p="no">' + esc(T("cancel")) + '</button>' +
      '<button class="t-btn pri" type="button" data-p="ok">' + esc(T("ok")) + "</button></div></div>";
    pinBox.hidden = false;
    var inp = pinBox.querySelector("input");
    setTimeout(function () { inp.focus(); }, 30);
    var go = function () {
      var v = inp.value.trim();
      if (setting) {
        if (v && !/^\d{4,8}$/.test(v)) { pinBox.querySelector(".bad").textContent = T("pinSetHint"); return; }
        ls("el-teacher-pin", v || null);
        ls("el-teacher-pin-set", "1");
        pinBox.hidden = true; done(true);
      } else if (v === ls("el-teacher-pin")) { pinBox.hidden = true; done(true); }
      else { pinBox.querySelector(".bad").textContent = T("pinBad"); inp.value = ""; }
    };
    pinBox.onclick = function (e) {
      e.stopPropagation();
      var b = e.target.closest("[data-p]");
      if (!b) return;
      if (b.getAttribute("data-p") === "no") { pinBox.hidden = true; done(false); } else go();
    };
    inp.onkeydown = function (e) { if (e.key === "Enter") go(); if (e.key === "Escape") { pinBox.hidden = true; done(false); } };
  }

  /* ─────────── 상단바 칩 ─────────── */
  var tray = document.querySelector(".os-tray");
  var tChip = document.createElement("button");
  tChip.type = "button"; tChip.className = "os-chip t-chip"; tChip.hidden = true;
  var cChip = document.createElement("span");
  cChip.className = "os-chip c-chip"; cChip.hidden = true;
  tray.insertBefore(cChip, tray.firstChild);
  tray.insertBefore(tChip, tray.firstChild);
  tChip.addEventListener("click", function (e) { e.stopPropagation(); openPanel(); });
  function paintChips() {
    tChip.hidden = !S.teacher; tChip.textContent = T("chip");
    var c = lsj("el-class", {});
    cChip.hidden = !c.on; cChip.textContent = T("classChip");
  }

  /* ─────────── 수업 모드 적용 ─────────── */
  function applyClass() {
    var c = lsj("el-class", {});
    S.hidden = c.on ? (c.hidden || []) : [];
    A.repaint();
    paintChips();
  }

  /* ─────────── 미션 카드 (바탕화면) ─────────── */
  function paintMission() {
    var desk = document.getElementById("desk");
    var card = document.getElementById("dMission");
    var mis = lsj("el-mission", null);
    if (!mis || !mis.title) { if (card) card.remove(); return; }
    if (!card) {
      card = document.createElement("div");
      card.id = "dMission"; card.className = "d-mission";
      var hero = desk.querySelector(".d-hero");
      desk.insertBefore(card, hero ? hero.nextSibling : desk.firstChild);
      card.addEventListener("click", function (e) {
        var ck = e.target.closest("[data-ck]"), go = e.target.closest("[data-go]");
        if (ck) {
          var m = lsj("el-mission", null); if (!m) return;
          var i = +ck.getAttribute("data-ck");
          m.steps[i].done = !m.steps[i].done;
          ls("el-mission", JSON.stringify(m)); paintMission();
        } else if (go) A.open(go.getAttribute("data-go"));
      });
    }
    var steps = (mis.steps || []).filter(function (s) { return s && s.text; });
    card.innerHTML = '<span class="bdg">' + esc(T("misCard")).replace(" ", "<br>") + "</span>" +
      "<b>" + esc(mis.title) + "<small>" + esc(T("misBy")) + "</small></b>" +
      "<ol>" + steps.map(function (s, i) {
        return '<li class="' + (s.done ? "done" : "") + '"><span class="ck" data-ck="' + i + '" title="✓">' + (s.done ? "✓" : "") + "</span>" +
               (s.href ? '<span class="go" data-go="' + esc(s.href) + '">' : "<span>") + (i + 1) + ". " + esc(s.text) + "</span></li>";
      }).join("") + "</ol>";
  }

  /* ─────────── 선생님 판 ─────────── */
  var box = document.createElement("div");
  box.id = "osTeach"; box.hidden = true;
  document.body.appendChild(box);
  box.addEventListener("click", function (e) { e.stopPropagation(); if (e.target === box) box.hidden = true; });

  function openPanel() {
    var c = lsj("el-class", {});
    var mis = lsj("el-mission", { title: "", steps: [] });
    var hidden = c.hidden || [];
    var appOpts = '<option value="">' + esc(T("misNone")) + "</option>" + APPS.APPS.map(function (a) {
      return '<option value="' + a.href + '">' + esc(appName(a)) + "</option>";
    }).join("");
    var step = function (i) {
      var s = (mis.steps || [])[i] || {};
      return '<div class="t-step"><input class="t-in" data-st="' + i + '" placeholder="' + esc(T("misStep").replace("{n}", i + 1)) +
             '" value="' + esc(s.text || "") + '"><select data-sa="' + i + '">' + appOpts.replace('value="' + (s.href || "") + '"', 'value="' + (s.href || "") + '" selected') + "</select></div>";
    };
    box.innerHTML = '<div class="card"><div class="hd"><h2>' + esc(T("title")) + '</h2><span class="sp"></span>' +
        '<button class="t-btn" type="button" data-t="lock">' + esc(T("lockNow")) + "</button>" +
        '<button class="t-btn" type="button" data-t="pin">' + esc(T("pinChange")) + "</button>" +
        '<button class="t-btn danger" type="button" data-t="exit">' + esc(T("exit")) + "</button></div>" +
      '<div class="t-grid">' +
        '<div class="t-box"><h3>' + esc(T("checkSec")) + '<span class="sp"></span><button class="t-btn" type="button" data-t="snd">' + esc(T("sndBtn")) +
          '</button><button class="t-btn pri" type="button" data-t="check">' + esc(T("checkRun")) + '</button></h3>' +
          '<div class="t-hint">' + esc(T("checkHint")) + '</div><div id="tChecks">' + lastChecks + '</div></div>' +
        '<div class="t-box"><h3>' + esc(T("classSec")) + '<span class="sp"></span><button class="t-btn' + (c.on ? "" : " pri") + '" type="button" data-t="class">' +
          esc(c.on ? T("classOff") : T("classOn")) + '</button></h3><div class="t-hint">' + esc(T("classHint")) + '</div><div class="t-apps">' +
          APPS.APPS.map(function (a) {
            return '<label><input type="checkbox" data-app="' + a.href + '"' + (hidden.indexOf(a.href) < 0 ? " checked" : "") + ">" + icon(a.ic) + esc(appName(a)) + "</label>";
          }).join("") + "</div></div>" +
        '<div class="t-box"><h3>' + esc(T("misSec")) + '</h3><input class="t-in" id="tMisT" placeholder="' + esc(T("misTitle")) + '" value="' + esc(mis.title || "") + '">' +
          step(0) + step(1) + step(2) +
          '<div class="t-row"><button class="t-btn pri" type="button" data-t="misSave">' + esc(T("misSave")) + '</button>' +
          '<button class="t-btn" type="button" data-t="misClear">' + esc(T("misClear")) + '</button><span class="t-note" id="tMisNote"></span></div></div>' +
        '<div class="t-box"><h3>' + esc(T("logSec")) + '</h3><div id="tLog"><div class="t-hint">…</div></div>' +
          '<div class="t-row"><button class="t-btn" type="button" data-t="options">' + esc(T("logOpen")) + '</button>' +
          '<button class="t-btn" type="button" data-t="export">' + esc(T("logExport")) + "</button></div></div>" +
      "</div></div>";
    box.hidden = false;
    loadLog();
  }

  box.addEventListener("change", function (e) {
    var a = e.target.getAttribute && e.target.getAttribute("data-app");
    if (!a) return;
    var c = lsj("el-class", {});
    var h = (c.hidden || []).filter(function (x) { return x !== a; });
    if (!e.target.checked) h.push(a);
    c.hidden = h;
    ls("el-class", JSON.stringify(c));
    applyClass();
  });
  box.addEventListener("click", function (e) {
    var b = e.target.closest("[data-t]");
    if (!b) return;
    var k = b.getAttribute("data-t");
    if (k === "exit") { S.teacher = false; box.hidden = true; applyClass(); }
    else if (k === "lock") { box.hidden = true; if (S.lock) S.lock(); }
    else if (k === "pin") askPin(true, function () {});
    else if (k === "snd") { if (S.quick) S.quick.snd(); }
    else if (k === "check") runCheck(b);
    else if (k === "class") {
      var c = lsj("el-class", {});
      c.on = !c.on;
      ls("el-class", JSON.stringify(c));
      applyClass(); openPanel();
    }
    else if (k === "misSave") {
      var m = { title: box.querySelector("#tMisT").value.trim(), steps: [] };
      var old = lsj("el-mission", { steps: [] });
      for (var i = 0; i < 3; i++) {
        var t = box.querySelector('[data-st="' + i + '"]').value.trim();
        var h = box.querySelector('[data-sa="' + i + '"]').value;
        var was = (old.steps || [])[i];
        m.steps.push({ text: t, href: h, done: !!(was && was.text === t && was.done) });
      }
      ls("el-mission", m.title ? JSON.stringify(m) : null);
      paintMission();
      box.querySelector("#tMisNote").textContent = T("misSaved");
    }
    else if (k === "misClear") { ls("el-mission", null); paintMission(); openPanel(); }
    else if (k === "options") { box.hidden = true; A.open("/options"); }
    else if (k === "export") {
      var a = document.createElement("a");                    // 내려받기 — 창을 옮기지 않는다
      a.href = "/custom/export"; a.download = "";
      document.body.appendChild(a); a.click(); a.remove();
    }
  });

  var lastChecks = "";           // 판을 다시 그려도(수업 모드 켜기 등) 점검 결과는 남긴다
  function runCheck(btn) {
    btn.disabled = true;
    var out = document.getElementById("tChecks");
    out.innerHTML = '<div class="t-hint">…</div>';
    var rows = [];
    var K = T("k");
    var put = function () {
      out.innerHTML = rows.map(function (r) {
        return '<div class="t-chk ' + (r.ok === null ? "" : r.ok ? "ok" : "no") + '"><span class="m">' + (r.ok === null ? "…" : r.ok ? "✓" : "!") +
               "</span><b>" + esc(K[r.key] || r.key) + "</b><i>" + esc(r.detail || "") + "</i></div>";
      }).join("");
    };
    var ready = fetch("/ready").then(function (r) { return r.json(); }).then(function (r) {
      rows.unshift({ key: "ai", ok: !!r.ready && !r.error, detail: r.error ? r.error : r.ready ? (r.loaded + "/" + r.total) : T("aiLoading").replace("{n}", r.loaded + "/" + r.total) });
    }).catch(function (e) { rows.unshift({ key: "ai", ok: false, detail: String(e) }); });
    var self = fetch("/custom/selftest").then(function (r) { return r.json(); }).then(function (j) {
      ((j && j.data && j.data.checks) || []).forEach(function (c) { rows.push(c); });
    }).catch(function () {});
    var cam = (navigator.mediaDevices && navigator.mediaDevices.getUserMedia
      ? navigator.mediaDevices.getUserMedia({ video: true }).then(function (s) {
          var tr = s.getVideoTracks()[0];
          rows.push({ key: "camera", ok: true, detail: tr ? tr.label : "" });
          s.getTracks().forEach(function (t) { t.stop(); });
        })
      : Promise.reject(new Error(T("camNone")))).catch(function (e) { rows.push({ key: "camera", ok: false, detail: (e && e.message) || T("camNone") }); });
    Promise.all([ready, self, cam]).then(function () { put(); lastChecks = out.innerHTML; btn.disabled = false; });
  }

  function loadLog() {
    var out = function (h) { var el = document.getElementById("tLog"); if (el) el.innerHTML = h; };
    Promise.all([
      fetch("/stats/summary").then(function (r) { return r.json(); }).catch(function () { return null; }),
      fetch("/custom/reports").then(function (r) { return r.json(); }).catch(function () { return null; })
    ]).then(function (r) {
      var d = r[0] && r[0].data || {};
      var pages = Array.isArray(d.pages) ? d.pages : [];
      var name = { index: "/try", blocks: "/blocks", code: "/code", train: "/train", talk: "/talk", works: "/works", options: "/options" };
      var rows = pages.filter(function (p) { return p.seconds > 0 && name[p.page]; });
      var max = Math.max.apply(null, [1].concat(rows.map(function (p) { return p.seconds; })));
      var h = '<div class="t-hint">' + esc(T("logToday")) + (d.since ? " · " + esc(String(d.since).slice(0, 10)) + " ~" : "") + "</div>";
      h += rows.length ? rows.map(function (p) {
        var a = APPS.APPS.filter(function (x) { return x.href === name[p.page]; })[0];
        return '<div class="t-bar"><span>' + esc(a ? appName(a) : p.page) + '</span><i><b style="width:' + Math.round(p.seconds / max * 100) +
               '%"></b></i><em>' + esc(T("min").replace("{n}", Math.round(p.seconds / 60))) + "</em></div>";
      }).join("") : '<div class="t-hint">' + esc(T("logNone")) + "</div>";
      var reps = r[1] && Array.isArray(r[1].data) ? r[1].data.length : 0;
      h += '<div class="t-hint" style="margin-top:8px">' + esc(T("logReports").replace("{n}", reps)) + "</div>";
      out(h);
    });
  }

  /* ─────────── 들어가기 · 나가기 ─────────── */
  S.teacherToggle = function () {
    if (S.teacher) { openPanel(); return; }
    var enter = function (ok) { if (!ok) return; S.teacher = true; applyClass(); openPanel(); };
    if (ls("el-teacher-pin")) askPin(false, enter);
    else if (!ls("el-teacher-pin-set")) askPin(true, enter);
    else enter(true);
  };

  A.onLang(function () { paintChips(); paintMission(); if (!box.hidden) openPanel(); });
  applyClass();
  paintMission();
})();
