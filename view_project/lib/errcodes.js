/* 오류 코드 — 파이썬 · 블록이 멈췄을 때 Traceback 대신 "코드 · 쉬운 설명 · 몇 번째 줄 · 해 볼 것" 을 보여 준다.
 *
 *   PY-…  파이썬 문법 · 실행 오류 (예외 종류로 가른다)
 *   TM-…  themaker 라이브러리가 낸 오류 (themaker.TheMakerError 의 code)
 *   BK-…  블록 실행 오류 (블록 화면이 던지는 오류의 키 · 자바스크립트 오류 종류로 가른다)
 *
 * 서버(code_routes · pyrunner)는 예외 종류 · 메시지 · 줄 번호만 넘기고, 글은 여기서 화면 말로 만든다.
 * 원래 오류(Traceback · 메시지)는 버리지 않는다 — 카드의 [원래 오류 보기] 에 그대로 둔다.
 * 코드를 더하면 docs/MANUAL.md 의 "오류 코드" 표도 같이 고친다 (tools/release_check.py 가 본다).
 *
 *   EL_ERR.fromPython(info, lang)  info = { type, msg, line, text, tm, raw, exit }   → err
 *   EL_ERR.fromBlocks(e, lang)     블록 화면 catch 의 e                              → err
 *   EL_ERR.card(err, lang, onLine) 결과 칸에 넣을 카드 (줄 번호를 누르면 onLine(줄))
 *   err = { code, title, hint, line, text, detail, raw }
 */
(function () {
  "use strict";

  var C = {
    /* ---- 파이썬 ---- */
    "PY-SYNTAX": { ko: ["문법이 맞지 않아요", "괄호 ( ) · 따옴표 \" \" 짝이 맞는지, if · for · def 줄 끝에 콜론(:)이 있는지 봐요."],
                   en: ["The code doesn't follow Python's rules", "Check that ( ) and \" \" come in pairs, and that if / for / def lines end with a colon (:)."] },
    "PY-INDENT": { ko: ["들여쓰기가 맞지 않아요", "if · for · def 다음 줄은 같은 칸만큼(보통 4칸) 안으로 들여써요. 탭과 띄어쓰기를 섞지 않아요."],
                   en: ["The indentation is off", "Lines under if / for / def move in by the same amount (usually 4 spaces). Don't mix tabs and spaces."] },
    "PY-NAME":   { ko: ["모르는 이름이에요", "철자와 대문자 · 소문자를 확인해요. 변수는 쓰기 전에 먼저 만들어야 해요. 맨 위에 from themaker import * 가 있는지도 봐요."],
                   en: ["Python doesn't know this name", "Check the spelling and upper/lower case. Make a variable before using it, and keep from themaker import * at the top."] },
    "PY-TYPE":   { ko: ["값의 종류가 맞지 않아요", "숫자와 글자를 바로 더할 수 없어요. str(숫자) · int(글자) 로 바꿔요. 함수에 넣는 값의 개수도 봐요."],
                   en: ["The kinds of values don't match", "You can't add a number and text directly — use str(number) or int(text). Also check how many values the function takes."] },
    "PY-VALUE":  { ko: ["쓸 수 없는 값이에요", "넣은 값이 맞는 모양인지 봐요. 예: int(\"abc\") 는 숫자로 바꿀 수 없어요."],
                   en: ["That value can't be used here", "Check the value has the right form — e.g. int(\"abc\") can't become a number."] },
    "PY-INDEX":  { ko: ["목록의 범위를 넘었어요", "목록은 0번부터 세요. 3개짜리 목록의 마지막은 [2] 예요. len(목록) 으로 개수를 확인해요."],
                   en: ["Past the end of the list", "Lists count from 0 — the last of 3 items is [2]. Check the size with len(list)."] },
    "PY-KEY":    { ko: ["없는 항목이에요", "사전에 그 이름의 항목이 없어요. print(결과) 로 어떤 항목이 있는지 먼저 봐요."],
                   en: ["That key isn't there", "The dictionary has no item with that name. print(result) first to see which items it has."] },
    "PY-ATTR":   { ko: ["그런 기능이 없어요", "점(.) 뒤에 쓴 이름을 확인해요. 값이 None 이면(아무것도 못 찾았을 때) 기능을 쓸 수 없어요."],
                   en: ["That value has no such feature", "Check the name after the dot (.). A None value (nothing found) has no features."] },
    "PY-ZERO":   { ko: ["0 으로 나눴어요", "나누는 수가 0 이 아닌지 if 로 먼저 확인해요."],
                   en: ["Divided by zero", "Check with if that the number you divide by isn't 0."] },
    "PY-IMPORT": { ko: ["불러올 수 없는 모듈이에요", "이 컴퓨터에 없는 모듈이에요. 인터넷 없이 도는 프로그램이라 새로 설치할 수 없어요 — themaker · math · random · time 처럼 있는 것을 써요."],
                   en: ["That module can't be imported", "It isn't on this computer, and this offline program can't install new ones — use what's there, like themaker, math, random, time."] },
    "PY-FILE":   { ko: ["파일을 찾을 수 없어요", "파일 이름과 폴더를 확인해요. 파이썬은 작업 폴더의 pycode 에서 돌아요."],
                   en: ["File not found", "Check the file name and folder. Python runs inside the pycode folder of your work folder."] },
    "PY-INPUT":  { ko: ["input() 은 쓸 수 없어요", "이 화면에서는 키보드로 입력을 받을 수 없어요. 값을 코드에 직접 적어요."],
                   en: ["input() isn't supported", "This screen can't read the keyboard. Write the value into the code instead."] },
    "PY-LOOP":   { ko: ["함수가 자기 자신을 너무 많이 불렀어요", "멈추는 조건(if)이 있는지 봐요."],
                   en: ["A function called itself too many times", "Check there is a condition (if) that makes it stop."] },
    "PY-MEMORY": { ko: ["메모리가 모자라요", "큰 사진이나 아주 긴 목록을 너무 많이 만들지 않았는지 봐요. 다른 앱을 닫고 다시 해 봐요."],
                   en: ["Out of memory", "Avoid making too many big photos or huge lists. Close other apps and try again."] },
    "PY-ETC":    { ko: ["프로그램이 멈췄어요", "아래 [원래 오류 보기] 의 마지막 줄이 이유예요."],
                   en: ["The program stopped with an error", "The last line under [Show the original error] tells you why."] },

    /* ---- themaker ---- */
    "TM-SERVER": { ko: ["AI 서버에 연결할 수 없어요", "프로그램(run.bat)이 켜져 있는지 확인해요. 방금 켰다면 1~2분 기다려요."],
                   en: ["Can't reach the AI server", "Make sure the program (run.bat) is running. If you just started it, wait 1–2 minutes."] },
    "TM-READY":  { ko: ["AI 를 준비하는 중이에요", "처음 켤 때는 AI 를 올리느라 1~2분 걸려요. 조금 뒤에 다시 실행해요."],
                   en: ["The AI is still getting ready", "It takes 1–2 minutes to load the first time. Run it again in a moment."] },
    "TM-CAM":    { ko: ["웹캠을 쓸 수 없어요", "다른 프로그램(화상회의 등)이 웹캠을 쓰고 있지 않은지 봐요. 웹캠이 없으면 load(\"사진.jpg\") 로 사진 파일을 써요."],
                   en: ["The webcam can't be used", "Check no other app (like a video call) is using it. Without a webcam, use a photo file with load(\"photo.jpg\")."] },
    "TM-IMAGE":  { ko: ["사진이 아니에요", "camera() 나 load() 로 만든 사진을 넣어요. 파일이면 이름과 확장자(.jpg · .png)를 확인해요."],
                   en: ["That isn't a photo", "Pass a photo made with camera() or load(). For a file, check its name and extension (.jpg / .png)."] },
    "TM-ARG":    { ko: ["쓸 수 없는 값을 넣었어요", "오류 글에 쓸 수 있는 값이 적혀 있어요. [도움말] 에서 명령 쓰는 법을 봐요."],
                   en: ["A value the command doesn't accept", "The message lists the values you can use. See how to use the command in [Help]."] },
    "TM-AI":     { ko: ["AI 가 이 일을 하지 못했어요", "사진이 너무 어둡거나 작지 않은지 봐요. 계속되면 [설정] → [점검 실행] 을 눌러 봐요."],
                   en: ["The AI couldn't do this", "Check the photo isn't too dark or small. If it keeps happening, press Settings → Run check."] },
    "TM-NONE":   { ko: ["찾은 것이 없어요", "결과가 비어 있는지 if 로 먼저 확인해요. 예: if r: …"],
                   en: ["Nothing was found", "Check the result isn't empty with if first — e.g. if r: …"] },
    "TM-SOUND":  { ko: ["소리를 낼 수 없어요", "스피커가 연결돼 있는지, 윈도우 소리 설정의 기본 장치를 확인해요."],
                   en: ["Can't play sound", "Check a speaker is connected and the default device in Windows sound settings."] },
    "TM-VOICE":  { ko: ["말을 알아듣지 못했어요", "마이크 가까이에서 또박또박 말해요. [설정] → [마이크 시험] 으로 확인해요."],
                   en: ["Couldn't understand the speech", "Speak clearly close to the mic. Check it with Settings → Test microphone."] },
    "TM-BOARD":  { ko: ["보드와 연결할 수 없어요", "USB 케이블과 포트 이름을 확인해요. 다른 프로그램이 같은 포트를 쓰고 있지 않은지도 봐요."],
                   en: ["Can't connect to the board", "Check the USB cable and port name, and that no other app is using the port."] },
    "TM-FACE":   { ko: ["얼굴 명단을 쓸 수 없어요", "이름을 적었는지, 사진에 얼굴이 한 명만 보이는지 확인해요."],
                   en: ["The face list can't be used", "Check you typed a name and only one face is in the photo."] },
    "TM-DATA":   { ko: ["자료를 쓸 수 없어요", "자료 이름을 확인해요. [대화] 화면의 [자료 넣기] 에서 만든 자료를 써요."],
                   en: ["The material can't be used", "Check the material's name. Use one made with [Add material] in Talk."] },
    "TM-ETC":    { ko: ["themaker 가 멈췄어요", "오류 글을 읽고 넣은 값을 확인해요."],
                   en: ["themaker stopped", "Read the message and check the values you passed."] },

    /* ---- 블록 ---- */
    "BK-CAM":    { ko: ["웹캠을 쓸 수 없어요", "주소창 왼쪽의 카메라 아이콘에서 [허용] 을 눌러요. 웹캠이 없으면 무대의 [사진 올리기] 와 「업로드한 사진」 블록을 써요."],
                   en: ["The webcam can't be used", "Press Allow on the camera icon left of the address bar. Without a webcam, use [Upload photo] and the \"uploaded photo\" block."] },
    "BK-MIC":    { ko: ["마이크를 쓸 수 없어요", "주소창 왼쪽에서 마이크를 [허용] 하고, [설정] → [마이크 시험] 으로 확인해요."],
                   en: ["The microphone can't be used", "Allow the mic left of the address bar, and check it with Settings → Test microphone."] },
    "BK-IMAGE":  { ko: ["사진이 없어요", "사진 블록(웹캠에서 사진 찍기 · 업로드한 사진)을 AI 블록의 빈칸에 끼워요."],
                   en: ["There's no photo", "Snap a photo block (take a photo with the webcam / uploaded photo) into the AI block's slot."] },
    "BK-ORDER":  { ko: ["블록 순서가 맞지 않아요", "결과를 쓰는 블록보다 인식 블록이 먼저 와야 해요."],
                   en: ["The blocks are in the wrong order", "The recognition block has to come before the block that uses its result."] },
    "BK-MODEL":  { ko: ["모델을 고르지 않았어요", "블록의 목록에서 모델을 골라요. [가르치기] 에서 저장한 AI 나 [설정] → [모델 폴더] 에 넣은 파일이 나와요."],
                   en: ["No model picked", "Pick a model in the block's list — AIs saved in Train, or files in Settings → Models folder."] },
    "BK-DATA":   { ko: ["자료를 고르지 않았어요", "[대화] 화면의 [자료 넣기] 로 먼저 자료를 만들고 블록에서 골라요."],
                   en: ["No material picked", "Make one with [Add material] in Talk first, then pick it in the block."] },
    "BK-TABLE":  { ko: ["표에 넣을 수 없는 값이에요", "표에는 숫자나 글자만 넣어요. 사진은 [사진 저장] 블록으로 따로 저장해요."],
                   en: ["That can't go in the table", "Tables hold numbers or text only. Save photos separately with the save-photo block."] },
    "BK-AI":     { ko: ["AI 가 이 일을 하지 못했어요", "사진이 너무 어둡거나 작지 않은지 봐요. 계속되면 [설정] → [점검 실행] 을 눌러 봐요."],
                   en: ["The AI couldn't do this", "Check the photo isn't too dark or small. If it keeps happening, press Settings → Run check."] },
    "BK-SERVER": { ko: ["AI 서버에 연결할 수 없어요", "프로그램(run.bat)이 켜져 있는지 확인해요. 방금 켰다면 1~2분 기다려요."],
                   en: ["Can't reach the AI server", "Make sure the program (run.bat) is running. If you just started it, wait 1–2 minutes."] },
    "BK-BLOCK":  { ko: ["블록 연결이 맞지 않아요", "빈칸이 남은 블록이나 모양이 다른 값을 끼운 블록이 없는지 봐요. 노란 표시가 붙은 블록을 확인해요."],
                   en: ["The blocks don't fit together", "Look for blocks with empty slots or a value of the wrong kind. Check the block marked in yellow."] },
    "BK-ETC":    { ko: ["실행이 멈췄어요", "아래 [원래 오류 보기] 의 글이 이유예요."],
                   en: ["The run stopped with an error", "The text under [Show the original error] tells you why."] },
  };

  /* 파이썬 예외 종류 → 코드 */
  var PY_TYPE = {
    SyntaxError: "PY-SYNTAX", IndentationError: "PY-INDENT", TabError: "PY-INDENT",
    NameError: "PY-NAME", UnboundLocalError: "PY-NAME",
    TypeError: "PY-TYPE", ValueError: "PY-VALUE", IndexError: "PY-INDEX", KeyError: "PY-KEY",
    AttributeError: "PY-ATTR", ZeroDivisionError: "PY-ZERO",
    ModuleNotFoundError: "PY-IMPORT", ImportError: "PY-IMPORT",
    FileNotFoundError: "PY-FILE", IsADirectoryError: "PY-FILE", PermissionError: "PY-FILE",
    EOFError: "PY-INPUT", RecursionError: "PY-LOOP", MemoryError: "PY-MEMORY",
  };
  /* 블록 화면이 던지는 오류 키(blocks.html 의 m_…) → 코드 */
  var BK_KEY = {
    m_noCam: "BK-CAM", m_camNotReady: "BK-CAM",
    m_noMic: "BK-MIC", m_sttFail: "BK-MIC",
    m_noImage: "BK-IMAGE", m_needUpload: "BK-IMAGE",
    m_noDetect: "BK-ORDER", m_needDetect: "BK-ORDER",
    m_noCustom: "BK-MODEL", m_noFile: "BK-MODEL", m_noModel: "BK-MODEL",
    m_noDb: "BK-DATA",
    m_noImgInTable: "BK-TABLE", m_saveFail: "BK-TABLE",
    m_aiError: "BK-AI",
  };
  /* 윈도우 종료 코드 — 0xC0000005(접근 위반) · 0xC000013A(Ctrl+C) · 0xC00000FD(스택 넘침) */
  var EXIT_MEM = [3221225477, -1073741819, 3221225725, -1073741571];

  var UI = {
    ko: { err: "오류", line: "{n}번째 줄", lineGo: "{n}번째 줄로 가기", raw: "원래 오류 보기", hint: "해 볼 것" },
    en: { err: "Error", line: "line {n}", lineGo: "Go to line {n}", raw: "Show the original error", hint: "Try this" },
  };
  function L(lang) { return lang === "en" ? "en" : "ko"; }
  function make(code, lang, extra) {
    var c = C[code] || C["PY-ETC"], l = L(lang);
    var o = { code: code, title: c[l][0], hint: c[l][1], line: null, text: "", detail: "", raw: "" };
    for (var k in (extra || {})) if (extra[k] != null) o[k] = extra[k];
    return o;
  }

  /* 메시지에서 학생에게 보여 줄 한 줄 — NameError 면 그 이름, KeyError 면 그 항목 */
  function pyDetail(type, msg) {
    msg = String(msg || "");
    var m;
    if (type === "NameError" && (m = /name '([^']+)'/.exec(msg))) return "'" + m[1] + "'";
    if (type === "UnboundLocalError" && (m = /'([^']+)'/.exec(msg))) return "'" + m[1] + "'";
    if ((type === "ModuleNotFoundError" || type === "ImportError") && (m = /No module named '([^']+)'/.exec(msg))) return "'" + m[1] + "'";
    if (type === "AttributeError" && (m = /attribute '([^']+)'/.exec(msg))) return "." + m[1];
    return msg;
  }

  function fromPython(info, lang) {
    info = info || {};
    var code;
    if (info.tm) code = C[info.tm] ? info.tm : "TM-ETC";
    else if (info.type) code = PY_TYPE[info.type] || (/Error$/.test(info.type) && /^OS|IO/.test(info.type) ? "PY-FILE" : "PY-ETC");
    else if (EXIT_MEM.indexOf(info.exit) >= 0) code = "PY-MEMORY";
    else code = "PY-ETC";
    return make(code, lang, {
      line: info.line || null,
      text: info.text || "",
      detail: info.tm ? String(info.msg || "") : (info.type ? info.type + ": " + pyDetail(info.type, info.msg) : ""),
      raw: info.raw || (info.type ? info.type + ": " + (info.msg || "") : ""),
    });
  }

  function fromBlocks(e, lang) {
    var msg = (e && e.message) || String(e);
    var code = (e && e.elKey && BK_KEY[e.elKey]) ||
      (/Failed to fetch|NetworkError|Load failed/i.test(msg) ? "BK-SERVER" : null) ||
      (e && /^(TypeError|ReferenceError|RangeError|SyntaxError)$/.test(e.name) ? "BK-BLOCK" : "BK-ETC");
    return make(code, lang, { detail: e && e.elKey ? msg : "", raw: (e && e.stack) || msg });
  }

  function el(tag, cls, text) {
    var d = document.createElement(tag);
    if (cls) d.className = cls;
    if (text != null) d.textContent = text;
    return d;
  }
  /* 카드 — 글자는 textContent 로만 넣는다(학생 코드 · 서버 글이 섞이므로) */
  function card(err, lang, onLine) {
    var u = UI[L(lang)];
    var box = el("div", "el-err");
    var head = el("div", "el-err-head");
    head.appendChild(el("span", "el-err-code", u.err + " " + err.code));
    if (err.line) {
      var ln = el(onLine ? "button" : "span", "el-err-line", u.line.replace("{n}", err.line));
      if (onLine) { ln.type = "button"; ln.title = u.lineGo.replace("{n}", err.line); ln.addEventListener("click", function () { onLine(err.line); }); }
      head.appendChild(ln);
    }
    box.appendChild(head);
    box.appendChild(el("div", "el-err-title", err.title));
    if (err.text) box.appendChild(el("code", "el-err-src", err.text));
    if (err.detail) box.appendChild(el("div", "el-err-detail", err.detail));
    box.appendChild(el("div", "el-err-hint", "💡 " + err.hint));
    if (err.raw && err.raw !== err.detail) {
      var d = el("details", "el-err-raw");
      d.appendChild(el("summary", null, u.raw));
      d.appendChild(el("pre", null, err.raw));
      box.appendChild(d);
    }
    return box;
  }

  var CSS = [
    ".el-err{margin:8px 0 4px;padding:10px 12px;border:1.5px solid #e5484d;border-left-width:6px;border-radius:6px;",
    "  background:#fff4f3;color:#3a1d1b;font-family:Pretendard,'Malgun Gothic',sans-serif;font-size:.95rem;line-height:1.5;white-space:normal}",
    ".el-err-head{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:2px}",
    ".el-err-code{background:#e5484d;color:#fff;font-weight:700;font-size:.8rem;padding:1px 8px;border-radius:999px;font-family:Menlo,Consolas,monospace}",
    ".el-err-line{font-size:.85rem;font-weight:700;color:#b42318;background:none;border:1px solid #f2b8b5;border-radius:999px;padding:0 8px;cursor:default}",
    "button.el-err-line{cursor:pointer}button.el-err-line:hover{background:#ffe1de}",
    ".el-err-title{font-weight:700;font-size:1.02rem}",
    ".el-err-src{display:block;margin:4px 0;padding:3px 8px;background:#fff;border:1px dashed #f2b8b5;border-radius:4px;font-family:Menlo,Consolas,monospace;font-size:.88rem;white-space:pre-wrap;color:#3a1d1b}",
    ".el-err-detail{font-family:Menlo,Consolas,monospace;font-size:.85rem;color:#7a2e2a;word-break:break-all}",
    ".el-err-hint{margin-top:4px}",
    ".el-err-raw{margin-top:6px;font-size:.82rem}.el-err-raw summary{cursor:pointer;color:#7a2e2a}",
    ".el-err-raw pre{margin:4px 0 0;padding:6px 8px;max-height:180px;overflow:auto;background:#2b2f36;color:#ffb4ac;border-radius:4px;white-space:pre-wrap;font-size:.8rem}",
    "html.hc .el-err{border-width:2.5px;border-left-width:8px;background:#fff}",
  ].join("\n");
  function injectCss() {
    if (document.getElementById("el-err-css")) return;
    var s = document.createElement("style"); s.id = "el-err-css"; s.textContent = CSS;
    (document.head || document.documentElement).appendChild(s);
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", injectCss); else injectCss();

  window.EL_ERR = { CODES: C, PY_TYPE: PY_TYPE, BK_KEY: BK_KEY, fromPython: fromPython, fromBlocks: fromBlocks, card: card, make: make };
})();
