/* 셸 — 빠른 설정 · 잠금 · 끄기 · 배터리 · 바탕화면 그림.
 *
 * 상단바 오른쪽 끝 전원 단추가 연다. 흩어져 있던 것을 한 판에 모은다:
 * 이름, 한/EN, 밝은 곳 모드, 목소리, 소리·마이크 시험, 처음 안내, 작업 폴더,
 * 바탕화면 그림, 선생님 모드, 잠금, 설정, 끄기. 기능은 이미 있던 것이고
 * (설정 화면·각 앱), 여기서는 자리만 새로 준다.
 *
 * os.html 이 EL_SHELL.api 를 연 뒤에 읽는다.
 */
(function () {
  "use strict";
  var S = window.EL_SHELL, A = S && S.api;
  if (!A) return;
  var $ = function (id) { return document.getElementById(id); };
  var esc = A.esc, fill = A.fill;

  var UI = {
    ko: {
      quick: "빠른 설정", nameEdit: "이름 바꾸기", nameHint: "설정에 적은 이름 · 이 컴퓨터", noName: "이름 없음",
      namePh: "이름", save: "저장",
      lang: "한국어", langSub: "English 로 바꾸기", hc: "밝은 곳 모드", on: "켜짐", off: "꺼짐",
      snd: "소리 시험", sndSub: "말소리로 들어 보기", sndSay: "안녕하세요. 소리가 잘 들려요.",
      sndFail: "소리를 못 냈어요 — 윈도우 소리 설정을 확인해 주세요.",
      mic: "마이크 시험", micSub: "3초 말하면 되들려줘요", micRec: "말해 보세요… {n}", micPlay: "들려주는 중",
      micFail: "마이크를 못 썼어요 — 윈도우 마이크 설정을 확인해 주세요.",
      tour: "처음 안내", tourSub: "앱마다 다시 보기", tourDone: "다음에 앱을 열면 안내가 다시 나와요.",
      folder: "작업 폴더", folderSub: "탐색기로 열기",
      voice: "목소리", wall: "바탕화면", teacherSec: "선생님",
      teacher: "선생님 모드", teacherSub: "수업 · 점검 · 미션", docs: "API 문서", docsSub: "이 서버가 하는 일",
      lock: "잠금", settings: "설정 열기", power: "끄기",
      lockMsg: "잠깐! 선생님을 봐 주세요", lockHold: "길게 누르면 풀려요", lockPin: "선생님 번호", lockBad: "번호가 달라요",
      byeQ: "edge-lab 을 끌까요?", byeWins: "켜 둔 창: {w}", byeNone: "켜 둔 창이 없어요.",
      byeSafe: "짜던 블록·코드·가르치던 사진은 초안으로 남아서, 다음에 켜면 이어서 할 수 있어요.",
      byeGo: "끄기", byeCancel: "그만두기", byeing: "끄는 중…",
      byeDone: "꺼졌어요. 이 창을 닫아도 돼요.", byeFail: "끄지 못했어요: ",
      batt: "배터리", charging: "충전 중"
    },
    en: {
      quick: "Quick settings", nameEdit: "Change name", nameHint: "Name set in Settings · this computer", noName: "No name",
      namePh: "Name", save: "Save",
      lang: "English", langSub: "Switch to 한국어", hc: "Bright room", on: "On", off: "Off",
      snd: "Sound test", sndSub: "Hear a voice", sndSay: "Hello. The sound works.",
      sndFail: "No sound — check the Windows sound settings.",
      mic: "Mic test", micSub: "Talk for 3 s, hear it back", micRec: "Say something… {n}", micPlay: "Playing back",
      micFail: "Could not use the mic — check the Windows mic settings.",
      tour: "Guided tour", tourSub: "See it again in each app", tourDone: "The tour shows again next time you open an app.",
      folder: "Work folder", folderSub: "Open in Explorer",
      voice: "Voice", wall: "Desktop", teacherSec: "Teacher",
      teacher: "Teacher mode", teacherSub: "Class · checks · mission", docs: "API docs", docsSub: "What this server does",
      lock: "Lock", settings: "Open Settings", power: "Shut down",
      lockMsg: "Eyes on your teacher, please", lockHold: "Press and hold to unlock", lockPin: "Teacher number", lockBad: "Wrong number",
      byeQ: "Shut down edge-lab?", byeWins: "Open windows: {w}", byeNone: "No windows are open.",
      byeSafe: "Blocks, code and training photos you were working on are kept as drafts for next time.",
      byeGo: "Shut down", byeCancel: "Cancel", byeing: "Shutting down…",
      byeDone: "It's off. You can close this window.", byeFail: "Could not shut down: ",
      batt: "Battery", charging: "charging"
    }
  };
  function T(k) { var L = UI[A.lang()] || UI.ko; return L[k] !== undefined ? L[k] : UI.ko[k]; }
  function ls(k, v) {
    try { if (v === undefined) return localStorage.getItem(k); localStorage.setItem(k, v); } catch (e) { return null; }
  }

  var SVG = {
    lock: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="5" y="10.5" width="14" height="10" rx="2"/><path d="M8 10.5V7.5a4 4 0 0 1 8 0v3"/></svg>',
    pow: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M12 3v8"/><path d="M6.3 6.8a8 8 0 1 0 11.4 0"/></svg>',
    bat: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="2.5" y="7" width="17" height="10" rx="2"/><path d="M22 10.5v3"/><rect x="5" y="9.5" width="{w}" height="5" rx="1" fill="currentColor" stroke="none"/></svg>',
    bolt: '<svg viewBox="0 0 24 24" fill="currentColor" stroke="none"><path d="M13 2 4 14h7l-1 8 9-12h-7z"/></svg>'
  };

  /* ── 바탕화면 그림 — 그림 파일 없이 CSS 로만. 0 은 os.html 기본 ── */
  var WALLS = [
    null,
    "radial-gradient(900px 600px at 0% 0%, #dcd6f7 0%, rgba(220,214,247,0) 60%), radial-gradient(900px 600px at 100% 100%, #cfe8e0 0%, rgba(207,232,224,0) 60%), #f3efe6",
    "radial-gradient(1000px 640px at 50% 0%, #fde2c8 0%, rgba(253,226,200,0) 62%), radial-gradient(800px 520px at 0% 100%, #f7d4dc 0%, rgba(247,212,220,0) 60%), #f7efe4",
    "linear-gradient(160deg, #d9ecf4 0%, #eaf3ea 55%, #f6efe2 100%)",
    "#f1ece2"
  ];
  var css = document.createElement("style");
  css.textContent = [
    "#osQuick{position:fixed;top:46px;right:10px;z-index:85;width:min(372px,calc(100% - 20px));max-height:calc(100dvh - 58px);overflow-y:auto;",
    "  padding:14px;border-radius:18px;background:rgba(250,246,238,.97);border:1px solid rgba(74,63,46,.18);box-shadow:0 18px 44px rgba(44,74,124,.24);}",
    "#osQuick[hidden]{display:none}",
    ".q-who{display:flex;align-items:center;gap:10px;padding:0 2px 12px}",
    ".q-who img{height:42px}.q-who b{display:block;font-size:15px}.q-who i{display:block;font-style:normal;font-size:12px;color:var(--ink-2)}",
    ".q-who .q-edit{margin-left:auto;font-size:12.5px;padding:4px 9px;border-radius:9px;color:var(--cyan-d)}.q-who .q-edit:hover{background:rgba(31,95,122,.1)}",
    ".q-name{display:flex;gap:6px;margin:-4px 0 10px}.q-name[hidden]{display:none}",
    ".q-name input{flex:1;min-width:0;height:36px;padding:0 10px;border-radius:10px;border:1.5px solid var(--line);font:inherit;font-size:14px}",
    ".q-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px}",
    ".q-tile{min-height:58px;border-radius:14px;padding:9px 12px;background:#fff;border:1px solid rgba(74,63,46,.14);display:flex;flex-direction:column;",
    "  justify-content:center;gap:2px;font-size:14px;font-weight:700;text-align:left;cursor:pointer;color:var(--ink)}",
    ".q-tile small{font-weight:400;font-size:12px;color:var(--ink-2)}",
    ".q-tile:hover{border-color:var(--cyan)}",
    ".q-tile.on{background:var(--cyan);border-color:var(--cyan);color:#fff}.q-tile.on small{color:rgba(255,255,255,.88)}",
    ".q-sec{margin:13px 2px 6px;font-size:12px;color:var(--ink-2)}",
    ".q-note{font-size:12.5px;color:var(--cyan-d);margin:8px 2px 0;min-height:1em}",
    ".q-voice{width:100%;height:38px;border-radius:10px;border:1.5px solid var(--line);background:#fff;font:inherit;font-size:14px;padding:0 8px}",
    ".q-walls{display:flex;gap:8px}",
    ".q-wall{flex:1;height:40px;border-radius:10px;border:2px solid rgba(74,63,46,.16);cursor:pointer}",
    ".q-wall.on{border-color:var(--cyan);box-shadow:0 0 0 2px rgba(31,95,122,.25)}",
    ".q-bar{display:flex;gap:8px;margin-top:14px}",
    ".q-btn{flex:1;height:44px;border-radius:12px;border:1px solid rgba(74,63,46,.2);background:#fff;font:inherit;font-size:14px;font-weight:700;",
    "  display:inline-flex;align-items:center;justify-content:center;gap:6px;cursor:pointer;color:var(--ink)}",
    ".q-btn svg{width:16px;height:16px}.q-btn:hover{border-color:var(--cyan)}",
    ".q-btn.danger{color:#a33b16;border-color:#f0b8a6;background:#fff7f4}",
    /* 잠금 */
    "#osLock{position:fixed;inset:0;z-index:200;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:14px;",
    "  background:rgba(245,239,227,.94);backdrop-filter:blur(14px);text-align:center;user-select:none}",
    "#osLock[hidden]{display:none}",
    "#osLock .t{font-family:'Gowun Batang',serif;font-size:84px;font-weight:700;line-height:1;letter-spacing:-.02em}",
    "#osLock img{height:150px}#osLock h2{font-family:'Gowun Batang',serif;font-size:30px}",
    "#osLock .hold{position:relative;margin-top:10px;height:48px;padding:0 22px;border-radius:24px;border:1.5px solid rgba(74,63,46,.3);",
    "  background:#fff;font:inherit;font-size:15px;font-weight:700;overflow:hidden;cursor:pointer;color:var(--ink)}",
    "#osLock .hold i{position:absolute;left:0;top:0;bottom:0;width:0;background:rgba(31,95,122,.18)}",
    "#osLock .hold span{position:relative}",
    "#osLock .pin{display:flex;gap:8px}#osLock .pin[hidden]{display:none}",
    "#osLock .pin input{width:150px;height:46px;border-radius:12px;border:1.5px solid var(--line);font:inherit;font-size:20px;text-align:center;letter-spacing:.3em}",
    "#osLock .bad{color:#a3321f;font-size:14px;min-height:1.2em}",
    /* 끄기 */
    "#osBye{position:fixed;inset:0;z-index:210;display:grid;place-items:center;background:rgba(42,38,32,.34)}#osBye[hidden]{display:none}",
    "#osBye .card{width:min(420px,calc(100% - 32px));background:var(--paper);border:1.5px solid var(--line-d);border-radius:18px;padding:20px;",
    "  box-shadow:0 20px 50px rgba(44,74,124,.3)}",
    "#osBye h2{font-family:'Gowun Batang',serif;font-size:20px;margin-bottom:8px}",
    "#osBye p{font-size:14px;color:var(--ink-2);margin-bottom:6px}",
    "#osBye .row{display:flex;gap:8px;margin-top:14px}",
    "#osBye.off{background:#f1ece2}#osBye.off .card{text-align:center}#osBye.off img{height:110px;display:block;margin:0 auto 10px}",
    ".os-bat svg{width:17px;height:17px}.os-bat .bolt{width:11px;height:11px;margin-left:-4px}"
  ].join("\n");
  document.head.appendChild(css);

  function applyWall(i) {
    var w = WALLS[i] || null;
    document.body.style.background = w && !document.documentElement.classList.contains("hc") ? w : "";
  }
  applyWall(+ls("el-wall") || 0);

  /* ─────────── 빠른 설정 판 ─────────── */
  var q = document.createElement("div");
  q.id = "osQuick"; q.hidden = true;
  document.body.appendChild(q);
  var voices = null;

  function tile(id, title, sub, on) {
    return '<button class="q-tile' + (on ? " on" : "") + '" type="button" data-q="' + id + '">' + esc(title) + "<small>" + esc(sub) + "</small></button>";
  }
  function paint() {
    var hc = document.documentElement.classList.contains("hc");
    var who = A.who();
    var wall = +ls("el-wall") || 0;
    var h =
      '<div class="q-who"><img src="/assets/pibo-hello.png" alt=""><span><b>' + esc(who || T("noName")) + "</b><i>" + esc(T("nameHint")) +
        '</i></span><button class="q-edit" type="button" data-q="name">' + esc(T("nameEdit")) + "</button></div>" +
      '<div class="q-name" hidden><input maxlength="40" placeholder="' + esc(T("namePh")) + '" value="' + esc(who) + '">' +
        '<button class="q-btn" type="button" data-q="nameSave" style="flex:0 0 auto;padding:0 14px;height:36px">' + esc(T("save")) + "</button></div>" +
      '<div class="q-grid">' +
        tile("lang", T("lang"), T("langSub"), true) +
        tile("hc", T("hc"), hc ? T("on") : T("off"), hc) +
        tile("snd", T("snd"), T("sndSub")) +
        tile("mic", T("mic"), T("micSub")) +
        tile("tour", T("tour"), T("tourSub")) +
        tile("folder", T("folder"), T("folderSub")) +
      "</div>" +
      '<div class="q-note" id="qNote"></div>' +
      '<div class="q-sec">' + esc(T("voice")) + '</div><select class="q-voice" id="qVoice"></select>' +
      '<div class="q-sec">' + esc(T("wall")) + '</div><div class="q-walls">' +
        WALLS.map(function (w, i) {
          return '<button class="q-wall' + (i === wall ? " on" : "") + '" type="button" data-wall="' + i + '" style="background:' +
                 (w || "radial-gradient(60px 40px at 10% 0%, #d4e9f0, transparent), radial-gradient(60px 40px at 100% 100%, #fbe1cf, transparent), #f5efe3") + '"></button>';
        }).join("") + "</div>" +
      '<div class="q-sec">' + esc(T("teacherSec")) + '</div><div class="q-grid">' +
        tile("teacher", T("teacher"), T("teacherSub"), !!S.teacher) +
        tile("docs", T("docs"), T("docsSub")) +
      "</div>" +
      '<div class="q-bar">' +
        '<button class="q-btn" type="button" data-q="lock">' + SVG.lock + esc(T("lock")) + "</button>" +
        '<button class="q-btn" type="button" data-q="settings">' + esc(T("settings")) + "</button>" +
        '<button class="q-btn danger" type="button" data-q="power">' + SVG.pow + esc(T("power")) + "</button>" +
      "</div>";
    q.innerHTML = h;
    fillVoices();
  }
  function note(t) { var n = $("qNote"); if (n) n.textContent = t || ""; }

  function fillVoices() {
    var sel = $("qVoice");
    if (!sel) return;
    function put(list, def) {
      sel.innerHTML = "";
      list.forEach(function (v) { var o = document.createElement("option"); o.value = v; o.textContent = v; sel.appendChild(o); });
      sel.value = ls("vapi-voice") || def || list[0];
    }
    if (voices) { put(voices.voices, voices.def); return; }
    fetch("/speech/voices").then(function (r) { return r.json(); }).then(function (j) {
      var d = j && j.data;
      voices = { voices: (d && d.voices) || ["F1"], def: (d && d.default) || "F1" };
      put(voices.voices, voices.def);
    }).catch(function () { voices = { voices: ["F1"], def: "F1" }; put(voices.voices, voices.def); });
  }

  function openQuick(show) {
    q.hidden = !show;
    $("osPower").classList.toggle("open", show);
    if (show) paint();
  }
  $("osPower").title = T("quick");
  $("osPower").addEventListener("click", function (e) { e.stopPropagation(); openQuick(q.hidden); });
  q.addEventListener("click", function (e) { e.stopPropagation(); });
  document.addEventListener("click", function () { if (!q.hidden) openQuick(false); });
  A.onLang(function () { $("osPower").title = T("quick"); if (!q.hidden) paint(); paintBat(); });

  q.addEventListener("change", function (e) {
    if (e.target.id === "qVoice") ls("vapi-voice", e.target.value);   // 대화·블록이 같은 값을 읽는다
  });
  q.addEventListener("click", function (e) {
    var w = e.target.closest("[data-wall]");
    if (w) { ls("el-wall", w.getAttribute("data-wall")); applyWall(+w.getAttribute("data-wall")); paint(); return; }
    var b = e.target.closest("[data-q]");
    if (!b) return;
    var k = b.getAttribute("data-q");
    if (k === "lang") { A.setLang(A.lang() === "ko" ? "en" : "ko"); }
    else if (k === "hc") {
      var on = !document.documentElement.classList.contains("hc");
      document.documentElement.classList.toggle("hc", on);
      ls("vapi-hc", on ? "1" : "0");                           // 창들은 storage 이벤트로 따라온다 (lib/embed.js)
      applyWall(+ls("el-wall") || 0);
      paint();
    }
    else if (k === "snd") soundTest();
    else if (k === "mic") micTest(b);
    else if (k === "tour") {
      try { Object.keys(localStorage).forEach(function (x) { if (x.indexOf("vapi-tour-") === 0) localStorage.removeItem(x); }); } catch (err) {}
      note(T("tourDone"));
    }
    else if (k === "folder") fetch("/system/open_folder", { method: "POST" }).catch(function () {});
    else if (k === "name") { var box = q.querySelector(".q-name"); box.hidden = !box.hidden; if (!box.hidden) box.querySelector("input").focus(); }
    else if (k === "nameSave") saveName();
    else if (k === "teacher") { openQuick(false); if (S.teacherToggle) S.teacherToggle(); }
    else if (k === "docs") { openQuick(false); A.open("/docs"); }
    else if (k === "lock") { openQuick(false); lock(); }
    else if (k === "settings") { openQuick(false); A.open("/options"); }
    else if (k === "power") { openQuick(false); bye(); }
  });
  q.addEventListener("keydown", function (e) {
    if (e.key === "Enter" && e.target.closest(".q-name")) saveName();
  });
  function saveName() {
    var v = q.querySelector(".q-name input").value.trim();
    fetch("/system/username", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name: v }) })
      .then(function (r) { return r.json(); }).then(function (j) {
        A.setWho(v && j && j.result === "ok" ? v : "");
        paint();
      }).catch(function () {});
  }

  /* 소리 시험 — 이 컴퓨터의 목소리(TTS)로 한 문장. 안 되면 삐 소리라도 */
  function beep() {
    try {
      var ac = new (window.AudioContext || window.webkitAudioContext)();
      var o = ac.createOscillator(), g = ac.createGain();
      o.frequency.value = 880; g.gain.value = 0.15;
      o.connect(g); g.connect(ac.destination); o.start(); o.stop(ac.currentTime + 0.35);
      o.onended = function () { ac.close(); };
    } catch (e) { note(T("sndFail")); }
  }
  function soundTest() {
    note("…");
    fetch("/speech/tts", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: T("sndSay"), voice: ls("vapi-voice") || "F1", lang: A.lang() }) })
      .then(function (r) {
        if (!r.ok || (r.headers.get("Content-Type") || "").indexOf("audio") < 0) throw new Error("tts");
        return r.blob();
      }).then(function (b) {
        var au = new Audio(URL.createObjectURL(b));
        au.play().then(function () { note(""); }).catch(function () { note(T("sndFail")); });
      }).catch(function () { beep(); note(""); });
  }
  /* 마이크 시험 — 3초 녹음해서 그대로 되들려준다 (설정 화면과 같은 방식) */
  var micBusy = false;
  function micTest() {
    if (micBusy) return;
    micBusy = true;
    var stream = null, ac = null;
    navigator.mediaDevices.getUserMedia({ audio: true }).then(function (s) {
      stream = s;
      ac = new (window.AudioContext || window.webkitAudioContext)();
      var src = ac.createMediaStreamSource(s), node = ac.createScriptProcessor(4096, 1, 1), chunks = [];
      node.onaudioprocess = function (e) { chunks.push(new Float32Array(e.inputBuffer.getChannelData(0))); };
      src.connect(node); node.connect(ac.destination);
      var n = 3;
      note(fill(T("micRec"), { n: n }));
      var tm = setInterval(function () {
        n--;
        if (n > 0) { note(fill(T("micRec"), { n: n })); return; }
        clearInterval(tm);
        node.disconnect(); src.disconnect(); node.onaudioprocess = null;
        stream.getTracks().forEach(function (t) { t.stop(); });
        var total = chunks.reduce(function (a, c) { return a + c.length; }, 0);
        var buf = ac.createBuffer(1, Math.max(1, total), ac.sampleRate), ch = buf.getChannelData(0), at = 0;
        chunks.forEach(function (c) { ch.set(c, at); at += c.length; });
        var play = ac.createBufferSource();
        play.buffer = buf; play.connect(ac.destination);
        note(T("micPlay"));
        play.onended = function () { note(""); micBusy = false; try { ac.close(); } catch (e) {} };
        play.start();
      }, 1000);
    }).catch(function () {
      note(T("micFail")); micBusy = false;
      if (stream) stream.getTracks().forEach(function (t) { t.stop(); });
    });
  }

  /* ─────────── 잠금 ─────────── */
  var lk = document.createElement("div");
  lk.id = "osLock"; lk.hidden = true;
  document.body.appendChild(lk);
  var lockClock = null;
  function lock() {
    var pin = ls("el-teacher-pin");
    lk.innerHTML =
      '<span class="t" id="lkT"></span><img src="/assets/pibo-hello.png" alt=""><h2>' + esc(T("lockMsg")) + "</h2>" +
      (pin
        ? '<div class="pin"><input type="password" inputmode="numeric" maxlength="8" placeholder="' + esc(T("lockPin")) + '"></div><div class="bad" id="lkBad"></div>'
        : '<button class="hold" type="button"><i></i><span>' + esc(T("lockHold")) + "</span></button>");
    lk.hidden = false;
    A.broadcast("hide");                         // 잠긴 동안 카메라·실행 멈춤 (lib/embed.js)
    var tick = function () { var n = new Date(); $("lkT").textContent = String(n.getHours()).padStart(2, "0") + ":" + String(n.getMinutes()).padStart(2, "0"); };
    tick(); lockClock = setInterval(tick, 10000);
    if (pin) {
      var inp = lk.querySelector("input");
      setTimeout(function () { inp.focus(); }, 50);
      inp.addEventListener("keydown", function (e) {
        if (e.key !== "Enter") return;
        if (inp.value === pin) unlock(); else { $("lkBad").textContent = T("lockBad"); inp.value = ""; }
      });
    } else {
      var hb = lk.querySelector(".hold"), bar = hb.querySelector("i"), t0 = 0, raf = 0;
      var down = function (e) {
        e.preventDefault(); t0 = performance.now();
        var step = function () {
          var p = Math.min(1, (performance.now() - t0) / 2000);
          bar.style.width = (p * 100) + "%";
          if (p >= 1) { unlock(); return; }
          raf = requestAnimationFrame(step);
        };
        raf = requestAnimationFrame(step);
      };
      var up = function () { cancelAnimationFrame(raf); bar.style.width = "0"; };
      hb.addEventListener("pointerdown", down);
      hb.addEventListener("pointerup", up); hb.addEventListener("pointerleave", up);
    }
  }
  function unlock() {
    lk.hidden = true; lk.innerHTML = "";
    clearInterval(lockClock);
    A.resume();                                   // 보던 창에 "보임" 을 다시 알린다
  }
  S.lock = lock;
  /* 시작 메뉴의 찾기(lib/os-start.js)가 부르는 것 */
  S.quick = {
    open: function () { openQuick(true); },
    hc: function () { openQuick(true); q.querySelector('[data-q="hc"]').click(); },
    snd: function () { openQuick(true); soundTest(); },
    mic: function () { openQuick(true); micTest(); },
    tour: function () { openQuick(true); q.querySelector('[data-q="tour"]').click(); },
    folder: function () { fetch("/system/open_folder", { method: "POST" }).catch(function () {}); },
    name: function () { openQuick(true); q.querySelector('[data-q="name"]').click(); },
    bye: function () { bye(); }
  };
  S.keyFns["ctrl+alt+l"] = lock;
  S.keys.push("ctrl+alt+l");

  /* ─────────── 끄기 ─────────── */
  var by = document.createElement("div");
  by.id = "osBye"; by.hidden = true;
  document.body.appendChild(by);
  function bye() {
    var w = A.windows().map(A.appName);
    by.className = "";
    by.innerHTML = '<div class="card"><h2>' + esc(T("byeQ")) + "</h2><p>" +
      esc(w.length ? fill(T("byeWins"), { w: w.join(", ") }) : T("byeNone")) + "</p><p>" + esc(T("byeSafe")) + "</p>" +
      '<div class="row"><button class="q-btn" type="button" data-b="no">' + esc(T("byeCancel")) + '</button>' +
      '<button class="q-btn danger" type="button" data-b="go">' + SVG.pow + esc(T("byeGo")) + "</button></div></div>";
    by.hidden = false;
  }
  by.addEventListener("click", function (e) {
    var b = e.target.closest("[data-b]");
    if (!b) { if (e.target === by && !by.classList.contains("off")) by.hidden = true; return; }
    if (b.getAttribute("data-b") === "no") { by.hidden = true; return; }
    b.disabled = true; b.textContent = T("byeing");
    A.broadcast("hide");                          // 각 창이 초안을 적고 카메라를 끈다
    setTimeout(function () {
      fetch("/system/shutdown", { method: "POST" }).then(function (r) { return r.json(); }).then(function (j) {
        if (!j || j.result !== "ok") throw new Error(j && j.data);
        by.className = "off";
        by.innerHTML = '<div class="card"><img src="/assets/pibo-hello.png" alt=""><h2>' + esc(T("byeDone")) + "</h2></div>";
        A.windows().forEach(A.close);
        setTimeout(function () { try { window.close(); } catch (err) {} }, 1200);
      }).catch(function (err) {
        by.hidden = true;
        A.resume();
        A.notify(T("byeFail") + (err && err.message || err), [], true);
      });
    }, 500);
  });

  /* ─────────── 배터리 — 노트북일 때만 ─────────── */
  var bat = null;
  function paintBat() {
    var el = $("osBat");
    if (!el) return;
    /* 배터리가 없는 PC 는 "충전 중 · 100%" 로 보고한다 — 그때는 숨긴다 */
    if (!bat || (bat.charging && bat.level >= 0.999 && (bat.dischargingTime === Infinity))) { el.hidden = true; return; }
    var pct = Math.round(bat.level * 100);
    el.hidden = false;
    el.className = "os-chip os-bat mono";
    el.title = T("batt") + (bat.charging ? " · " + T("charging") : "");
    el.innerHTML = SVG.bat.replace("{w}", Math.max(1, Math.round(12 * bat.level))) +
                   (bat.charging ? SVG.bolt.replace("<svg", '<svg class="bolt"') : "") + pct + "%";
    el.style.color = !bat.charging && pct <= 15 ? "#a3321f" : "";
  }
  if (navigator.getBattery) {
    navigator.getBattery().then(function (b) {
      bat = b; paintBat();
      ["levelchange", "chargingchange", "dischargingtimechange"].forEach(function (ev) { b.addEventListener(ev, paintBat); });
    }).catch(function () {});
  }
})();
