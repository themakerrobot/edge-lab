const { JSDOM, VirtualConsole } = require('jsdom');
const B = 'http://127.0.0.1:57900';
process.on('unhandledRejection', () => {}); process.on('uncaughtException', () => {});

async function open(path, wait) {
  const errs = [];
  const vc = new VirtualConsole();
  vc.on('jsdomError', e => errs.push(String(e.message).split('\n')[0]));
  const html = await (await fetch(B + path)).text();
  const dom = new JSDOM(html, { url: B + path, runScripts: 'dangerously',
    resources: 'usable', pretendToBeVisual: true, virtualConsole: vc,
    beforeParse(win) {                       // 페이지 스크립트가 돌기 전에 넣어야 한다
      win.fetch = (u, o) => fetch(new URL(u, B).href, o);
      // jsdom 에 없는 표준 기능 채우기 (실제 브라우저에는 있다 — CodeMirror 가 쓴다)
      const rect = () => ({ top:0, left:0, right:0, bottom:0, width:0, height:0, x:0, y:0 });
      win.Range.prototype.getBoundingClientRect = rect;
      win.Range.prototype.getClientRects = () => ({ length:0, item:()=>null, [Symbol.iterator]:function*(){} });
      // 캔버스 그리기도 jsdom 엔 없다 — 있는 척만 해 준다(실제 브라우저에는 있다)
      const ctx = new Proxy({}, { get: () => () => ({}), set: () => true });
      win.HTMLCanvasElement.prototype.getContext = () => ctx;
      win.matchMedia = win.matchMedia || (() => ({ matches:false, addListener(){}, addEventListener(){} }));
    } });
  await new Promise(r => setTimeout(r, wait || 4500));
  return { dom, doc: dom.window.document, win: dom.window, errs };
}
const only = e => e.filter(x => !/blockly|Not implemented|getContext|createObjectURL|SVG|canvas/i.test(x));

(async () => {
  console.log('페이지        레일 도구 파일패널 오버레이 실제오류');
  for (const p of ['/', '/try', '/blocks', '/code', '/train', '/talk', '/options']) {
    try {
      const { doc, errs, dom } = await open(p);
      /* 이동은 레일(lib/shell.js), 도구는 타이틀바(한/영·AI·?). 둘을 따로 센다 —
         전에는 헤더 하나에 섞여 있어서 한 숫자로 셌고, 셸로 바꾸면 그 숫자가
         조용히 0 이 되어 시험이 통과한 척했다. */
      const rail = doc.querySelectorAll('.rail a').length;
      const btns = doc.querySelectorAll('.titlebar .h-tools > a, .titlebar .h-tools > button').length;
      const fp = doc.getElementById('filePanel') ? 'O' : '-';
      const ov = doc.getElementById('sysPanel') || doc.getElementById('chipCPU') ? 'O' : '✗';
      const real = only(errs);
      console.log(p.padEnd(13), String(rail).padEnd(4), String(btns).padEnd(4), fp.padEnd(8), ov.padEnd(9),
        real.length ? real[0].slice(0, 55) : '없음');
      dom.window.close();
    } catch (e) { console.log(p.padEnd(13), '열기 실패:', String(e.message).slice(0, 50)); }
  }
})();
