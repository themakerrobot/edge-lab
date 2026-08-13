const { JSDOM, VirtualConsole } = require('jsdom');
const B = 'http://127.0.0.1:57900';
process.on('unhandledRejection', () => {}); process.on('uncaughtException', () => {});

async function page(path) {
  const errs = [];
  const vc = new VirtualConsole();
  vc.on('jsdomError', e => errs.push(String(e.message).split('\n')[0]));
  const html = await (await fetch(B + path)).text();
  const dom = new JSDOM(html, { url: B + path, runScripts:'dangerously', resources:'usable',
    pretendToBeVisual:true, virtualConsole:vc,
    beforeParse(win) {
      win.fetch = (u, o) => fetch(new URL(u, B).href, o);
      const rect = () => ({top:0,left:0,right:0,bottom:0,width:0,height:0,x:0,y:0});
      win.Range.prototype.getBoundingClientRect = rect;
      win.Range.prototype.getClientRects = () => ({length:0,item:()=>null,[Symbol.iterator]:function*(){}});
      const ctx = new Proxy({}, { get: () => () => ({}), set: () => true });
      win.HTMLCanvasElement.prototype.getContext = () => ctx;
      win.matchMedia = win.matchMedia || (()=>({matches:false,addListener(){},addEventListener(){}}));
      win.prompt = t => win.__answer;                       // 이름 물어보면 이걸로 답한다
      win.alert = m => errs.push('alert: ' + m);
      win.confirm = () => true;
    }});
  await new Promise(r => setTimeout(r, 4500));
  return { dom, doc: dom.window.document, win: dom.window, errs };
}
const click = (doc, id) => { const e = doc.getElementById(id);
  if (!e) throw new Error('단추 없음: ' + id); e.click(); };
const wait = ms => new Promise(r => setTimeout(r, ms));

(async () => {
  console.log('═══ 블록: 저장 → 목록 → 이름 표시 ═══');
  {
    const { doc, win, errs, dom } = await page('/blocks');
    console.log('  파일 패널      :', doc.getElementById('filePanel') ? '보임' : '없음');
    console.log('  머리줄 이름    :', JSON.stringify(doc.getElementById('curFile').textContent));
    win.__answer = '나의 첫 블록';
    click(doc, 'saveButton');
    await wait(1200);
    console.log('  저장 후 이름   :', JSON.stringify(doc.getElementById('curFile').textContent));
    const list = await (await fetch(B + '/blocks/works')).json();
    console.log('  서버 저장 목록 :', list.data.map(x => x.name));
    win.__answer = null;                                  // 다시 저장 — 안 물어봐야 함
    click(doc, 'saveButton');
    await wait(1200);
    console.log('  덮어쓰기 후    :', JSON.stringify(doc.getElementById('curFile').textContent),
                '| 목록 수:', (await (await fetch(B + '/blocks/works')).json()).data.length);
    console.log('  오류           :', errs.length ? errs[0].slice(0,60) : '없음');
    dom.window.close();
  }
  console.log('\n═══ 파이썬: 저장 → 이름 표시 ═══');
  {
    const { doc, win, errs, dom } = await page('/code');
    console.log('  파일 패널      :', doc.getElementById('filePanel') ? '보임' : '없음');
    console.log('  머리줄 이름    :', JSON.stringify(doc.getElementById('curFile').textContent));
    win.__answer = '나의 첫 파이썬';
    click(doc, 'saveButton');
    await wait(1200);
    console.log('  저장 후 이름   :', JSON.stringify(doc.getElementById('curFile').textContent));
    const list = await (await fetch(B + '/pycode/works')).json();
    console.log('  서버 저장 목록 :', list.data.map(x => x.name));
    console.log('  오류           :', errs.length ? errs[0].slice(0,60) : '없음');
    dom.window.close();
  }
})();
