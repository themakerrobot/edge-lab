/* 로봇 공장(/factory) — 서버 시리얼(/board/*)로 로봇과 이야기하기. 화면(DOM)은 쓰지 않는다.
 *
 * factory-lab 은 브라우저 Web Serial 로 포트를 직접 열었다. edge-lab 에서는 포트를 서버(board.py)가 쥔다 —
 * 블록·파이썬·보드 앱이 같은 연결을 써야 해서다. 그래서 여기서는 HTTP 로만 말한다.
 *
 *   보내기   POST /board/send {text}      줄 끝은 보드 앱에서 고른 것 — 이 펌웨어는 "!" 가 명령 끝이라 "없음"
 *   받기     GET  /board/lines?after=N    0.3초마다 (보이는 동안만)
 *   기다리기 POST /board/read {after, timeout}  "Moved:" 같은 줄을 바로 받으려고 — 폴링을 기다리지 않는다
 *
 * 보내기는 한 번에 하나만 날린다. 슬라이더를 끌면 초당 수십 번 값이 바뀌는데, 그걸 다 요청으로
 * 쌓으면 손을 놓은 뒤에도 로봇이 한참 따라온다. 그래서 두 갈래로 나눴다.
 *   send(글)    순서가 중요한 명령(#s → #j 등). 줄을 서서 차례로 간다.
 *   stream(글)  계속 바뀌는 자세(#m). 자리 하나뿐 — 새 값이 오면 헌 값을 버린다. 0.1초에 한 번까지.
 *   urgent(글)  멈춰! — 줄과 자리를 비우고 곧바로 보낸다.
 *
 * 출처: themakerrobot/factory-lab index.html (커밋 7a67b5f) 의 연결·송신 부분을 이 방식으로 다시 짰다 — 같은 저작자.
 */
(function () {
  "use strict";

  const STREAM_MS = 100;       // 자세 흘려보내기 최소 간격 — factory-lab 은 50ms(직접 시리얼), HTTP 라 두 배로
  const POLL_MS = 300;         // 받은 줄 읽기 — 보드 앱과 같은 값
  const STATUS_MS = 2000;      // 연결 상태 — 보드 앱에서 끊거나 케이블이 빠진 것을 알아채려고

  async function api(url, body) {
    const r = await fetch(url, body === undefined ? {} :
      { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    const j = await r.json();
    if (!j || j.result !== "ok") throw new Error((j && j.data) || "?");
    return j.data;
  }

  function create(o) {
    const L = {
      status: { connected: false },
      get connected() { return !!L.status.connected; },
      seq: 0,                  // 여기까지 받은 기록 번호
      lastTx: 0,               // 마지막으로 보낸 줄의 번호 — 그 뒤에 온 답만 본다
      count: { req: 0, send: 0, stream: 0, dropped: 0 }   // 시험용
    };
    const queue = [];          // { text, resolve, reject }
    let slot = null;           // { text, onSent } — 자세 하나
    let flying = false, lastStreamT = 0, pumpTimer = 0;
    let pollTimer = 0, statusTimer = 0, running = false, primed = false;

    function setStatus(st) {
      const was = L.connected;
      L.status = st || { connected: false };
      if (was !== L.connected || !primed) { primed = true; if (o.onConnect) o.onConnect(L.connected, L.status); }
      if (o.onStatus) o.onStatus(L.status);
      if (!L.connected) { queue.splice(0).forEach(q => q.reject(new Error("not connected"))); slot = null; }
    }
    L.refresh = async function () {
      try { setStatus(await api("/board/status")); } catch (e) { setStatus({ connected: false }); }
      return L.status;
    };

    /* ── 보내기 ── */
    async function post(text) {
      L.count.req++;
      const d = await api("/board/send", { text });
      if (d && d.seq) L.lastTx = Math.max(L.lastTx, d.seq);
      return d;
    }
    function pump() {
      clearTimeout(pumpTimer); pumpTimer = 0;
      if (flying || !L.connected) return;
      if (queue.length) {
        const q = queue.shift();
        flying = true; L.count.send++;
        post(q.text).then(q.resolve, e => { q.reject(e); L.refresh(); })
          .then(() => { flying = false; pump(); });
        return;
      }
      if (!slot) return;
      const wait = STREAM_MS - (performance.now() - lastStreamT);
      if (wait > 0) { pumpTimer = setTimeout(pump, wait); return; }
      const s = slot; slot = null;
      flying = true; lastStreamT = performance.now(); L.count.stream++;
      post(s.text).then(() => { if (s.onSent) s.onSent(s.text); }, () => L.refresh())
        .then(() => { flying = false; pump(); });
    }
    L.send = function (text) {
      if (!L.connected) return Promise.reject(new Error("not connected"));
      return new Promise((resolve, reject) => { queue.push({ text, resolve, reject }); pump(); });
    };
    L.stream = function (text, onSent) {
      if (!L.connected) return;
      if (slot) L.count.dropped++;
      slot = { text, onSent };
      pump();
    };
    L.cancelStream = function () { slot = null; };
    L.urgent = function (text) {
      if (!L.connected) return Promise.resolve();
      slot = null;
      queue.splice(0).forEach(q => q.resolve(null));      // 멈출 때는 밀린 명령을 버린다 — 보내지 않은 것으로 끝낸다
      const wasFlying = flying;
      const p = post(text).catch(() => L.refresh());
      // 이미 날아간 요청(#m 등)이 이 멈춤보다 늦게 도착할 수 있다 — 그 뒤에 한 번 더 멈춘다
      if (wasFlying) queue.push({ text, resolve() {}, reject() {} });
      return p;
    };
    /* 줄에 선 명령이 다 나갈 때까지 */
    L.drain = function () {
      return new Promise(res => {
        (function chk() { if ((!queue.length && !flying) || !L.connected) res(); else setTimeout(chk, 15); })();
      });
    };

    /* ── 받기 ── */
    let pulling = null;
    L.pull = function () {
      if (pulling) return pulling;
      pulling = api("/board/lines?after=" + L.seq).then(d => {
        let sys = false;
        d.lines.forEach(e => {
          if (e.seq <= L.seq) return;
          if (e.dir === "sys") sys = true;
          o.onLine(e);
        });
        if (d.seq < L.seq) L.seq = d.seq;                   // 서버가 다시 켜졌다 — 번호가 처음부터
        else L.seq = Math.max(L.seq, d.seq);
        if (sys) L.refresh();
      }).catch(() => {}).then(() => { pulling = null; });
      return pulling;
    };
    /* after 다음에 온 받은 줄 하나를 기다린다 (없으면 null). 폴링보다 빨리 "Moved:" 를 잡으려고 */
    L.read = async function (after, timeout) {
      if (!L.connected) return null;
      try {
        const d = await api("/board/read", { after, timeout: timeout || 1 });
        return d.line == null ? null : { seq: d.seq, text: d.line };
      } catch (e) { return null; }
    };

    /* ── 보이는 동안만 ── */
    L.start = async function () {
      if (running) return;
      running = true;
      if (!primed) {
        // 처음에는 지금까지의 기록을 건너뛴다 — 다른 앱이 주고받은 옛 줄이 로봇 자세로 읽히면 안 된다
        const st = await L.refresh();
        L.seq = Math.max(L.seq, st.seq || 0);
      } else await L.refresh();
      if (!running) return;
      pollTimer = setInterval(L.pull, POLL_MS);
      statusTimer = setInterval(L.refresh, STATUS_MS);
      L.pull();
    };
    L.stop = function () {
      running = false;
      clearInterval(pollTimer); clearInterval(statusTimer); pollTimer = statusTimer = 0;
      slot = null;
    };
    return L;
  }

  window.EL_FACTORY_LINK = { create };
})();
