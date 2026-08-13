const { JSDOM, VirtualConsole } = require('jsdom');
const B='http://127.0.0.1:57900';
process.on('unhandledRejection',()=>{}); process.on('uncaughtException',()=>{});
const wait=ms=>new Promise(r=>setTimeout(r,ms));
// 상황 3가지: ①웹캠 자체가 없음 ②권한 거부 ③다른 앱이 사용 중
const CASES = {
  '카메라 없음': null,
  '권한 거부'  : () => Promise.reject(Object.assign(new Error('denied'), { name:'NotAllowedError' })),
  '사용 중'    : () => Promise.reject(Object.assign(new Error('busy'),   { name:'NotReadableError' })),
};
async function run(path, label, gum) {
  const errs=[]; const vc=new VirtualConsole();
  vc.on('jsdomError', e=>errs.push(String(e.message).split('\n')[0]));
  const html = await (await fetch(B+path)).text();
  const dom = new JSDOM(html,{url:B+path,runScripts:'dangerously',resources:'usable',
    pretendToBeVisual:true,virtualConsole:vc,
    beforeParse(win){
      win.fetch=(u,o)=>fetch(new URL(u,B).href,o);
      const rect=()=>({top:0,left:0,right:0,bottom:0,width:0,height:0,x:0,y:0});
      win.Range.prototype.getBoundingClientRect=rect;
      win.Range.prototype.getClientRects=()=>({length:0,item:()=>null,[Symbol.iterator]:function*(){}});
      win.HTMLCanvasElement.prototype.getContext=()=>new Proxy({},{get:()=>()=>({}),set:()=>true});
      win.matchMedia=win.matchMedia||(()=>({matches:false,addListener(){},addEventListener(){}}));
      win.prompt=()=>null; win.alert=m=>errs.push('alert: '+m); win.confirm=()=>true;
      // 카메라 상황을 만든다
      Object.defineProperty(win.navigator, 'mediaDevices', {
        configurable:true, get: () => gum ? { getUserMedia: gum, enumerateDevices: async()=>[] } : undefined });
      win.__ok = false;
    }});
  await wait(4000);
  const doc=dom.window.document;
  const real = errs.filter(e=>!/blockly|Not implemented|getContext|SVG|canvas/i.test(e));
  // 페이지가 계속 살아 있는지: 나중에 실행되는 코드가 만든 것들이 있는가
  const marks = { '/': ['chipCPU'], '/blocks': ['chipCPU'], '/train': ['chipCPU'], '/talk': ['chipCPU'] };
  const bar = !!doc.querySelector('.split-bar');
  const late = (marks[path]||[]).every(id => !!doc.getElementById(id));
  const alive = late;                     // 오버레이는 스크립트 끝부분에서 만든다
  console.log(('  ' + label).padEnd(16), ('살아있음: ' + (alive?'O':'✗')).padEnd(16),
              real.length ? '오류: ' + real[0].slice(0,50) : '오류 없음');
  dom.window.close();
}
(async () => {
  for (const p of ['/', '/blocks', '/train', '/talk']) {
    console.log('═══', p);
    for (const [label, gum] of Object.entries(CASES)) await run(p, label, gum);
  }
})();
