/* 작업폴더 파일 패널 — 블록·파이썬 화면 왼쪽에 붙는다.
 *
 * 두 화면이 같은 모듈을 쓴다. 페이지는 "글 파일을 눌렀을 때 무엇을 할지"만
 * 정해 주면 된다:
 *
 *     VapiFiles.mount({ onOpen: function (path, text) { ... } });
 *
 * 서버는 작업폴더 하나만 보여 준다(/system/files). 폴더 밖으로 나가는 길은
 * 서버가 막는다 — 화면에서도 위로 올라가는 단추는 작업폴더 뿌리까지만 간다.
 *
 * 접었다 펼 수 있고, 접힘 상태와 마지막으로 열어 둔 폴더를 기억한다.
 */
window.VapiFiles = (function () {
  "use strict";

  var KEY_OPEN = "vapi-files-open";
  var KEY_PATH = "vapi-files-path";

  var CSS = [
    "#filePanel{display:flex;flex-direction:column;background:var(--box,#fff);",
    "  border:2px solid var(--line-d,#4a3f2e);border-radius:3px;overflow:hidden;",
    "  flex:0 0 210px;min-width:0;}",
    /* 접었을 때는 단추 하나만 남긴다.
       예전에는 34px 에 단추 두 개(📁 ↻)가 들어가 새로고침 단추가 잘려 보였다. */
    "#filePanel.closed{flex:0 0 30px;}",
    "#filePanel.closed .fp-head{padding:4px 0;justify-content:center;gap:0;}",
    "#filePanel.closed .fp-refresh{display:none;}",
    "#filePanel.closed button{padding:2px 3px;}",
    "#filePanel .fp-head{display:flex;align-items:center;gap:6px;padding:4px 6px;",
    "  border-bottom:1.5px dashed var(--line,#9a8f7d);flex:0 0 auto;}",
    "#filePanel.closed .fp-head{border-bottom:none;}",
    "#filePanel .fp-title{font-weight:700;font-size:.86rem;color:var(--cyan-d,#17475c);",
    "  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}",
    "#filePanel.closed .fp-title,#filePanel.closed .fp-body,",
    "#filePanel.closed .fp-crumb{display:none;}",
    "#filePanel button{font-family:inherit;font-size:.8rem;border:1.5px solid var(--line-d,#4a3f2e);",
    "  background:#fff;border-radius:3px;cursor:pointer;padding:2px 6px;color:var(--ink,#2a2620);}",
    "#filePanel .fp-crumb{padding:3px 7px;font-size:.76rem;color:var(--ink-2,#4a423a);",
    "  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;direction:rtl;text-align:left;}",
    "#filePanel .fp-body{flex:1 1 auto;min-height:0;overflow:auto;padding:2px 0;}",
    "#filePanel .fp-item{display:flex;align-items:center;gap:6px;padding:3px 8px;",
    "  cursor:pointer;font-size:.84rem;border:none;background:none;width:100%;text-align:left;}",
    "#filePanel .fp-item:hover{background:rgba(31,95,122,.10);}",
    "#filePanel .fp-item.on{background:rgba(31,95,122,.18);font-weight:700;}",
    "#filePanel .fp-item .nm{flex:1 1 auto;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}",
    "#filePanel .fp-item .sz{flex:0 0 auto;font-size:.72rem;color:var(--ink-2,#4a423a);}",
    "#filePanel .fp-item.dim{opacity:.55;cursor:default;}",
    "#filePanel .fp-msg{padding:8px;font-size:.8rem;color:var(--ink-2,#4a423a);}"
  ].join("\n");

  var box, bodyEl, crumbEl, titleEl, here = "", opts = {}, cur = "";

  function el(tag, attrs, text) {
    var n = document.createElement(tag);
    if (attrs) Object.keys(attrs).forEach(function (k) { n.setAttribute(k, attrs[k]); });
    if (text != null) n.textContent = text;
    return n;
  }

  function size(n) {
    if (!n) return "";
    if (n < 1024) return n + "B";
    if (n < 1024 * 1024) return Math.round(n / 1024) + "K";
    return (n / 1048576).toFixed(1) + "M";
  }

  function icon(item) {
    if (item.dir) return "📁";
    var e = (item.name.split(".").pop() || "").toLowerCase();
    if (e === "py") return "🐍";
    if (["png", "jpg", "jpeg", "gif", "bmp"].indexOf(e) >= 0) return "🖼";
    if (["wav", "mp3"].indexOf(e) >= 0) return "🔊";
    if (e === "json") return "🧩";
    return "📄";
  }

  function load(path) {
    here = path || "";
    bodyEl.textContent = "";
    bodyEl.appendChild(el("div", { "class": "fp-msg" }, "읽는 중…"));
    fetch("/system/files?path=" + encodeURIComponent(here))
      .then(function (r) { return r.json(); })
      .then(function (j) {
        if (!j || j.result !== "ok") throw new Error((j && j.data) || "실패");
        here = j.data.path || "";
        try { localStorage.setItem(KEY_PATH, here); } catch (e) {}
        draw(j.data.items || []);
      })
      .catch(function (ex) {
        bodyEl.textContent = "";
        bodyEl.appendChild(el("div", { "class": "fp-msg" }, "폴더를 읽지 못했어요 — " + ex.message));
      });
  }

  function draw(items) {
    crumbEl.textContent = here ? "작업폴더/" + here : "작업폴더";
    crumbEl.title = crumbEl.textContent;
    bodyEl.textContent = "";

    if (here) {                                  // 위로 — 작업폴더 뿌리까지만
      var up = el("button", { "class": "fp-item", type: "button" });
      up.appendChild(el("span", null, "↩"));
      up.appendChild(el("span", { "class": "nm" }, "위로"));
      up.addEventListener("click", function () {
        load(here.indexOf("/") < 0 ? "" : here.replace(/\/[^/]*$/, ""));
      });
      bodyEl.appendChild(up);
    }
    if (!items.length) {
      bodyEl.appendChild(el("div", { "class": "fp-msg" }, "아직 파일이 없어요."));
      return;
    }
    items.forEach(function (it) {
      var canOpen = it.dir || it.text;
      var b = el("button", { "class": "fp-item" + (canOpen ? "" : " dim") +
                                      (it.path === cur ? " on" : ""), type: "button" });
      b.title = it.name + (it.dir ? "" : "  " + size(it.size));
      b.appendChild(el("span", null, icon(it)));
      b.appendChild(el("span", { "class": "nm" }, it.name));
      if (!it.dir) b.appendChild(el("span", { "class": "sz" }, size(it.size)));
      if (it.dir) {
        b.addEventListener("click", function () { load(it.path); });
      } else if (it.text) {
        b.addEventListener("click", function () { open(it.path); });
      }
      bodyEl.appendChild(b);
    });
  }

  function open(path) {
    fetch("/system/file?path=" + encodeURIComponent(path))
      .then(function (r) { return r.json(); })
      .then(function (j) {
        if (!j || j.result !== "ok") throw new Error((j && j.data) || "실패");
        cur = path;
        Array.prototype.forEach.call(bodyEl.querySelectorAll(".fp-item"), function (n) {
          n.classList.remove("on");
        });
        if (typeof opts.onOpen === "function") opts.onOpen(path, j.data.code);
        load(here);
      })
      .catch(function (ex) { alert("파일을 열지 못했어요 — " + ex.message); });
  }

  function setOpen(on) {
    box.classList.toggle("closed", !on);
    try { localStorage.setItem(KEY_OPEN, on ? "1" : "0"); } catch (e) {}
    if (on && !bodyEl.childNodes.length) load(here);
  }

  function mount(o) {
    opts = o || {};
    var main = document.querySelector("[data-split]") || document.querySelector(".main");
    if (!main) return null;

    var style = el("style"); style.textContent = CSS;
    document.head.appendChild(style);

    box = el("div", { id: "filePanel" });
    var head = el("div", { "class": "fp-head" });
    var toggle = el("button", { type: "button", title: "파일 목록 접기/펼치기" }, "📁");
    titleEl = el("span", { "class": "fp-title" }, "작업폴더");
    var refresh = el("button", { type: "button", "class": "fp-refresh", title: "새로 읽기" }, "↻");
    head.appendChild(toggle); head.appendChild(titleEl); head.appendChild(refresh);
    crumbEl = el("div", { "class": "fp-crumb" }, "작업폴더");
    bodyEl = el("div", { "class": "fp-body" });
    box.appendChild(head); box.appendChild(crumbEl); box.appendChild(bodyEl);
    main.insertBefore(box, main.firstChild);

    toggle.addEventListener("click", function () { setOpen(box.classList.contains("closed")); });
    refresh.addEventListener("click", function () { load(here); });

    /* 처음 열 때는 펴 둔다 — 접혀 있으면 왼쪽에 📁 단추만 보여서
       이런 칸이 있는 줄도 모른다. 한 번 접으면 그 뒤로는 접힌 채로 기억한다. */
    var saved = null;
    try {
      saved = localStorage.getItem(KEY_OPEN);
      here = localStorage.getItem(KEY_PATH) || "";
    } catch (e) {}
    setOpen(saved === null ? true : saved === "1");
    return box;
  }

  return { mount: mount, reload: function () { load(here); }, open: open };
})();
