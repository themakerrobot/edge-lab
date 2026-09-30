/* 셸 — 바탕화면 위젯: 고르기 · 빼기 · 순서 바꾸기.
 *
 * 바탕화면 오른쪽 줄(.d-side)의 카드들이다. 전에는 "내가 가르친 AI" 와 "이 컴퓨터" 둘이 고정이었다.
 * 이제 아이가 [위젯 편집] 에서 넣고 빼고 순서를 바꾼다 — "내 컴퓨터" 라는 느낌은 여기서 생긴다.
 *
 *   mine  내가 가르친 AI      (os.html 이 그린다 — /custom/models)
 *   pc    이 컴퓨터            (os.html 이 그린다 — /system)
 *   clock 시계                (바늘 시계 — 바탕화면이 보일 때만 1초마다)
 *   cal   달력                (이번 달, 일기를 쓴 날에 점)
 *   memo  최근 메모            (메모장 el-notes 의 가장 최근 것)
 *   diary 오늘 일기            (일기 el-diary 의 오늘 칸)
 *
 * 고른 것과 순서는 localStorage "el-widgets" 에. os.html 이 EL_SHELL.api 를 연 뒤에 읽는다.
 * 그리는 일은 os.html 의 paintDesk 가 끝날 때마다 EL_WIDGETS.paint() 로 한 번 더 한다.
 */
(function () {
  "use strict";
  var S = window.EL_SHELL, A = S && S.api;
  if (!A) return;
  var $ = function (id) { return document.getElementById(id); };
  var esc = A.esc, icon = A.icon;

  var UI = {
    ko: { edit: "위젯 편집", done: "다 됐어요", add: "+ 위젯 넣기", none: "넣을 수 있는 위젯을 다 넣었어요",
          up: "위로", down: "아래로", remove: "빼기",
          name: { mine: "내가 가르친 AI", pc: "이 컴퓨터", clock: "시계", cal: "달력", memo: "최근 메모", diary: "오늘 일기" },
          memoNone: "아직 메모가 없어요", memoGo: "메모장", diaryNone: "오늘 일기를 아직 안 썼어요", diaryGo: "일기 쓰기",
          diaryDone: "오늘 일기를 썼어요", calGo: "일기",
          days: ["일", "월", "화", "수", "목", "금", "토"], ampm: ["오전", "오후"] },
    en: { edit: "Edit widgets", done: "Done", add: "+ Add a widget", none: "All widgets are already on the desk",
          up: "Up", down: "Down", remove: "Remove",
          name: { mine: "My trained AI", pc: "This computer", clock: "Clock", cal: "Calendar", memo: "Latest note", diary: "Today's diary" },
          memoNone: "No notes yet", memoGo: "Notes", diaryNone: "You have not written today's diary", diaryGo: "Write",
          diaryDone: "Today's diary is written", calGo: "Diary",
          days: ["S", "M", "T", "W", "T", "F", "S"], ampm: ["AM", "PM"] }
  };
  function T(k) { var L = A.lang() === "en" ? "en" : "ko"; return UI[L][k] !== undefined ? UI[L][k] : UI.ko[k]; }
  function lsj(k, d) { try { return JSON.parse(localStorage.getItem(k) || "null") || d; } catch (e) { return d; } }

  var ALL = ["mine", "pc", "clock", "cal", "memo", "diary"];
  var DEFAULT = ["mine", "pc"];
  var ICON = { mine: "train", pc: "gauge", clock: "clock", cal: "cal", memo: "note", diary: "book" };
  var SVG = {
    clock: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>',
    cal: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="3.5" y="5" width="17" height="15" rx="2.5"/><path d="M3.5 10h17M8 3v4M16 3v4"/></svg>'
  };
  function ic(k) { return SVG[ICON[k]] || icon(ICON[k]); }

  var list = lsj("el-widgets", DEFAULT).filter(function (k) { return ALL.indexOf(k) >= 0; });
  var editing = false;
  function save() { try { localStorage.setItem("el-widgets", JSON.stringify(list)); } catch (e) {} }

  /* ── 모양 ── */
  var css = document.createElement("style");
  css.textContent = [
    ".w{position:relative}",
    ".w-ctl{position:absolute;top:8px;right:8px;display:none;gap:4px;z-index:2}",
    ".d-side.editing .w-ctl{display:flex}",
    ".d-side.editing .w{outline:2px dashed rgba(31,95,122,.35);outline-offset:2px}",
    ".w-ctl button{width:28px;height:28px;border-radius:8px;border:1px solid rgba(74,63,46,.2);background:#fff;font:inherit;font-size:14px;line-height:1;cursor:pointer;color:var(--ink)}",
    ".w-ctl button:hover{border-color:var(--cyan)}.w-ctl button.x:hover{border-color:#a3321f;color:#a3321f}",
    ".w-edit{display:flex;gap:8px;flex-wrap:wrap;justify-content:flex-end}",
    ".w-edit button{height:32px;padding:0 12px;border-radius:16px;border:1px solid rgba(74,63,46,.2);background:rgba(255,255,255,.7);font:inherit;font-size:13px;cursor:pointer;color:var(--ink-2)}",
    ".w-edit button:hover{background:#fff;color:var(--ink)}",
    ".w-add{display:flex;flex-direction:column;gap:6px}",
    ".w-add button{display:flex;align-items:center;gap:10px;height:40px;padding:0 10px;border-radius:10px;border:1px solid rgba(74,63,46,.15);background:#fff;font:inherit;font-size:14px;cursor:pointer;text-align:left}",
    ".w-add button:hover{border-color:var(--cyan)}.w-add svg{width:18px;height:18px;color:var(--cyan-d)}",
    /* 시계 */
    ".w-clock{display:flex;align-items:center;gap:16px}.w-clock svg.face{width:96px;height:96px;flex:0 0 auto}",
    ".w-clock b{display:block;font-family:Menlo,Consolas,monospace;font-size:26px;letter-spacing:.02em}",
    ".w-clock small{font-size:13px;color:var(--ink-2)}",
    /* 달력 */
    ".w-cal{display:grid;grid-template-columns:repeat(7,1fr);gap:2px;text-align:center;font-size:12.5px}",
    ".w-cal i{font-style:normal;color:var(--ink-2);font-size:11.5px;padding-bottom:2px}",
    ".w-cal span{position:relative;height:26px;line-height:26px;border-radius:8px}",
    ".w-cal span.today{background:var(--cyan);color:#fff;font-weight:700}",
    ".w-cal span.sun{color:#b4451c}.w-cal span.today.sun{color:#fff}",
    ".w-cal span.has::after{content:'';position:absolute;left:50%;bottom:2px;width:4px;height:4px;margin-left:-2px;border-radius:2px;background:#d07a3e}",
    ".w-memo{font-size:14px;line-height:1.55;white-space:pre-wrap;word-break:keep-all;max-height:6.2em;overflow:hidden;cursor:pointer}",
    ".w-memo b{display:block;font-size:14.5px;margin-bottom:2px}"
  ].join("\n");
  document.head.appendChild(css);

  /* ── 카드 만들기 — mine · pc 는 os.html 에 이미 있다 ── */
  var side = document.querySelector(".d-side");
  if (!side) return;
  var ELS = { mine: $("wMine"), pc: $("wPc") };
  ["clock", "cal", "memo", "diary"].forEach(function (k) {
    var d = document.createElement("div");
    d.className = "w"; d.id = "w" + k.charAt(0).toUpperCase() + k.slice(1);
    d.innerHTML = '<div class="w-body"></div>';      // 편집 단추(.w-ctl)는 body 밖에 — 1초마다 다시 그려도 남게
    side.appendChild(d); ELS[k] = d;
  });
  var bar = document.createElement("div");
  bar.className = "w-edit";
  var addBox = document.createElement("div");
  addBox.className = "w w-addbox";

  function head(k, extra) {
    return "<h3>" + ic(k) + esc(T("name")[k]) + (extra || "") + "</h3>";
  }

  /* ── 위젯 그리기 ── */
  function hand(len, deg, w) {
    var r = (deg - 90) * Math.PI / 180;
    return '<line x1="50" y1="50" x2="' + (50 + len * Math.cos(r)).toFixed(1) + '" y2="' + (50 + len * Math.sin(r)).toFixed(1) +
           '" stroke-width="' + w + '" stroke-linecap="round"/>';
  }
  function paintClock() {
    if (ELS.clock.hidden) return;
    var el = ELS.clock.firstChild;
    var n = new Date(), h = n.getHours(), m = n.getMinutes(), s = n.getSeconds();
    var ticks = "";
    for (var i = 0; i < 12; i++) {
      var r = i * 30 * Math.PI / 180, a = i % 3 ? 40 : 36;
      ticks += '<line x1="' + (50 + a * Math.sin(r)).toFixed(1) + '" y1="' + (50 - a * Math.cos(r)).toFixed(1) +
               '" x2="' + (50 + 44 * Math.sin(r)).toFixed(1) + '" y2="' + (50 - 44 * Math.cos(r)).toFixed(1) + '" stroke-width="' + (i % 3 ? 1.5 : 3) + '"/>';
    }
    var face = '<svg class="face" viewBox="0 0 100 100"><circle cx="50" cy="50" r="47" fill="#fff" stroke="#4a3f2e" stroke-width="2"/>' +
      '<g stroke="#4a3f2e">' + ticks + '</g><g stroke="#2a2620">' + hand(26, (h % 12) * 30 + m / 2, 4.5) + hand(37, m * 6 + s / 10, 3) + "</g>" +
      '<g stroke="#b4451c">' + hand(40, s * 6, 1.5) + '</g><circle cx="50" cy="50" r="3.2" fill="#b4451c"/></svg>';
    var hh = h % 12 || 12;
    el.innerHTML = head("clock") + '<div class="w-clock">' + face + "<div><small>" + esc(T("ampm")[h < 12 ? 0 : 1]) + "</small><b>" +
      hh + ":" + String(m).padStart(2, "0") + '<span style="font-size:16px;color:var(--ink-2)">:' + String(s).padStart(2, "0") + "</span></b><small>" +
      (n.getMonth() + 1) + "/" + n.getDate() + " (" + esc(T("days")[n.getDay()]) + ")</small></div></div>";
  }
  function key(d) { return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0"); }
  function paintCal() {
    if (ELS.cal.hidden) return;
    var el = ELS.cal.firstChild;
    var now = new Date(), y = now.getFullYear(), mo = now.getMonth(), first = new Date(y, mo, 1).getDay(), last = new Date(y, mo + 1, 0).getDate();
    var diary = lsj("el-diary", {}), cells = T("days").map(function (d) { return "<i>" + esc(d) + "</i>"; }).join("");
    for (var i = 0; i < first; i++) cells += "<span></span>";
    for (var d = 1; d <= last; d++) {
      var dt = new Date(y, mo, d), cls = [];
      if (d === now.getDate()) cls.push("today");
      if (dt.getDay() === 0) cls.push("sun");
      if (diary[key(dt)]) cls.push("has");
      cells += '<span class="' + cls.join(" ") + '">' + d + "</span>";
    }
    el.innerHTML = head("cal", "<em>" + (A.lang() === "en" ? (mo + 1) + "/" + y : y + "년 " + (mo + 1) + "월") + "</em>") + '<div class="w-cal">' + cells + "</div>";
  }
  function paintMemo() {
    if (ELS.memo.hidden) return;
    var el = ELS.memo.firstChild;
    var notes = lsj("el-notes", []).slice().sort(function (a, b) { return (b.at || 0) - (a.at || 0); });
    var n = notes[0], lines = n ? String(n.text || "").split("\n").filter(function (x) { return x.trim(); }) : [];
    el.innerHTML = head("memo", '<em>' + esc(T("memoGo")) + " ›</em>") + (n
      ? '<div class="w-memo"><b>' + esc(lines[0] || "") + "</b>" + esc(lines.slice(1, 4).join("\n")) + "</div>"
      : '<div class="w-empty">' + esc(T("memoNone")) + "</div>");
  }
  function paintDiary() {
    if (ELS.diary.hidden) return;
    var el = ELS.diary.firstChild;
    var e = lsj("el-diary", {})[key(new Date())];
    var text = e ? String(e.title || e.text || "").split("\n")[0] : "";
    el.innerHTML = head("diary", '<em>' + esc(T("diaryGo")) + " ›</em>") +
      '<div class="w-memo">' + (e ? "<b>" + esc(T("diaryDone")) + "</b>" + esc(text) : esc(T("diaryNone"))) + "</div>";
  }
  ELS.memo.addEventListener("click", function () { if (!editing) A.open("/notes"); });
  ELS.diary.addEventListener("click", function () { if (!editing) A.open("/diary"); });
  ELS.cal.addEventListener("click", function () { if (!editing) A.open("/diary"); });
  [ELS.memo, ELS.diary, ELS.cal].forEach(function (x) { x.style.cursor = "pointer"; });

  /* ── 배치 · 편집 ── */
  function arrange() {
    ALL.forEach(function (k) { ELS[k].hidden = list.indexOf(k) < 0; });
    list.forEach(function (k) { side.appendChild(ELS[k]); });
    side.appendChild(addBox); side.appendChild(bar);
    side.classList.toggle("editing", editing);
    ALL.forEach(function (k) {
      var c = ELS[k].querySelector(":scope > .w-ctl");
      if (c) c.remove();
      if (!editing || ELS[k].hidden) return;
      var i = list.indexOf(k);
      c = document.createElement("div"); c.className = "w-ctl";
      c.innerHTML = (i > 0 ? '<button type="button" data-a="up" title="' + esc(T("up")) + '">↑</button>' : "") +
                    (i < list.length - 1 ? '<button type="button" data-a="down" title="' + esc(T("down")) + '">↓</button>' : "") +
                    '<button type="button" class="x" data-a="x" title="' + esc(T("remove")) + '">×</button>';
      c.addEventListener("click", function (ev) {
        ev.stopPropagation();
        var b = ev.target.closest("[data-a]"); if (!b) return;
        var a = b.getAttribute("data-a"), j = list.indexOf(k);
        if (a === "x") list.splice(j, 1);
        else if (a === "up" && j > 0) { list[j] = list[j - 1]; list[j - 1] = k; }
        else if (a === "down" && j < list.length - 1) { list[j] = list[j + 1]; list[j + 1] = k; }
        save(); arrange(); paint();
      });
      ELS[k].appendChild(c);
    });
    var left = ALL.filter(function (k) { return list.indexOf(k) < 0; });
    addBox.hidden = !editing;
    addBox.innerHTML = "<h3>" + esc(T("add")) + "</h3>" + (left.length ? '<div class="w-add">' + left.map(function (k) {
      return '<button type="button" data-k="' + k + '">' + ic(k) + esc(T("name")[k]) + "</button>";
    }).join("") + "</div>" : '<div class="w-empty">' + esc(T("none")) + "</div>");
    bar.innerHTML = '<button type="button" id="wEditBtn">' + esc(editing ? T("done") : T("edit")) + "</button>";
  }
  addBox.addEventListener("click", function (e) {
    var b = e.target.closest("[data-k]"); if (!b) return;
    list.push(b.getAttribute("data-k")); save(); arrange(); paint();
  });
  bar.addEventListener("click", function (e) {
    if (!e.target.closest("#wEditBtn")) return;
    editing = !editing; arrange(); paint();
  });

  function paint() {
    paintClock(); paintCal(); paintMemo(); paintDiary();
    if (editing) arrange();                  // os.html 이 mine · pc 를 통째로 다시 그리면 편집 단추가 지워진다
  }

  /* 바늘 시계는 바탕화면이 보이고 시계 위젯이 있을 때만 1초마다 */
  setInterval(function () { if (!$("desk").hidden && !ELS.clock.hidden) paintClock(); }, 1000);
  window.addEventListener("storage", function (e) { if (e.key === "el-notes" || e.key === "el-diary") paint(); });
  A.onLang(function () { arrange(); paint(); });

  window.EL_WIDGETS = { paint: paint, list: function () { return list.slice(); } };
  arrange(); paint();
})();
