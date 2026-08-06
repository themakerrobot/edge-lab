/* vapi-od : 사용 통계 수집 (오프라인, 이 PC 안에서만)
 *
 * 페이지에 이 한 줄만 넣으면 된다:
 *   <script src="/lib/usage.js" data-page="train"></script>
 *
 * 세는 것
 *   - 페이지 연 횟수
 *   - "활동 중" 체류시간 — 탭이 보이고, 최근 60초 안에 조작이 있었을 때만 센다
 *     (창만 띄워두고 자리 비운 시간은 빼기 위해서다)
 *   - 이벤트 — 각 페이지에서 vapiStat("block_run") 처럼 호출
 *
 * 누가 썼는지는 기록하지 않는다. 횟수와 시간만 보낸다.
 */
(function () {
  "use strict";
  var el = document.currentScript;
  var PAGE = (el && el.dataset && el.dataset.page) || "etc";

  var HEARTBEAT_MS = 30000;   // 30초마다 보고
  var IDLE_MS = 60000;        // 마지막 조작이 이보다 오래되면 자리 비운 것으로 본다
  var TICK_MS = 1000;

  var activeSec = 0;          // 아직 안 보낸 활동 시간
  var pending = {};           // 아직 안 보낸 이벤트
  var lastInput = Date.now();
  var opened = true;          // 첫 보고에 "열었다"를 함께 실는다

  ["mousedown", "keydown", "touchstart", "wheel", "pointermove"].forEach(function (e) {
    window.addEventListener(e, function () { lastInput = Date.now(); }, { passive: true });
  });

  setInterval(function () {
    if (document.visibilityState === "visible" && Date.now() - lastInput < IDLE_MS) {
      activeSec += TICK_MS / 1000;
    }
  }, TICK_MS);

  function payload() {
    var body = { page: PAGE, seconds: Math.round(activeSec), events: pending };
    if (opened) { body.open = true; }
    return body;
  }
  function clearBuf() { activeSec = 0; pending = {}; opened = false; }

  function send(useBeacon) {
    var sec = Math.round(activeSec);
    var hasEvents = Object.keys(pending).length > 0;
    if (!opened && !sec && !hasEvents) { return; }
    var body = JSON.stringify(payload());
    clearBuf();
    try {
      if (useBeacon && navigator.sendBeacon) {
        navigator.sendBeacon("/stats/event", new Blob([body], { type: "application/json" }));
      } else {
        fetch("/stats/event", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: body, keepalive: true,
        });
      }
    } catch (e) { /* 통계는 실패해도 수업에 지장이 없어야 한다 */ }
  }

  setInterval(function () { send(false); }, HEARTBEAT_MS);
  window.addEventListener("pagehide", function () { send(true); });
  document.addEventListener("visibilitychange", function () {
    if (document.visibilityState === "hidden") { send(true); }
  });
  send(false);   // 페이지를 열었다는 사실은 바로 알린다

  /* 각 페이지에서 쓰는 이벤트 기록 함수 */
  window.vapiStat = function (name, n) {
    if (!name) { return; }
    pending[name] = (pending[name] || 0) + (n || 1);
  };
})();
