const { JSDOM, VirtualConsole } = require('jsdom');
const B='http://127.0.0.1:57900';
process.on('unhandledRejection',()=>{}); process.on('uncaughtException',()=>{});
// 실제 브라우저처럼 폭을 계산해 주는 대역: 컨테이너 1200, 각 칸은 flex-basis 를 따른다
function prep(win, contW) {
  Object.defineProperty(win.HTMLElement.prototype,'clientWidth',{ get(){
    if (this.hasAttribute('data-split')) return contW;
    const b = this.style.flexBasis;
    if (b && b.endsWith('%')) return contW * parseFloat(b) / 100;
    if (b && b.endsWith('px')) return parseFloat(b);
    if (this.id === 'filePanel') return this.classList.contains('closed') ? 30 : 210;
    return 300; } });
  Object.defineProperty(win.HTMLElement.prototype,'offsetWidth',{
    get(){ return this.clientWidth; } });
}
async function page(store, fileOpen) {
  const html = await (await fetch(B+'/code')).text();
  const dom = new JSDOM(html,{url:B+'/code',runScripts:'dangerously',resources:'usable',
    pretendToBeVisual:true,virtualConsole:new VirtualConsole(),
    beforeParse(win){
      win.fetch=(u,o)=>fetch(new URL(u,B).href,o);
      const rect=()=>({top:0,left:0,right:0,bottom:0,width:0,height:0,x:0,y:0});
      win.Range.prototype.getBoundingClientRect=rect;
      win.Range.prototype.getClientRects=()=>({length:0,item:()=>null,[Symbol.iterator]:function*(){}});
      win.HTMLCanvasElement.prototype.getContext=()=>new Proxy({},{get:()=>()=>({}),set:()=>true});
      win.matchMedia=win.matchMedia||(()=>({matches:false,addListener(){},addEventListener(){}}));
      win.prompt=()=>null; win.alert=()=>{}; win.confirm=()=>true;
      for (const k in store) win.localStorage.setItem(k, store[k]);
      win.localStorage.setItem('vapi-files-open', fileOpen ? '1' : '0');
      prep(win, 1200);
    }});
  await new Promise(r=>setTimeout(r,4500));
  return dom;
}
(async () => {
  // 1) 파일목록 접은 채로 끌어서 편집기를 700px 로
  let dom = await page({}, false);
  let win = dom.window, doc = win.document;
  const main = doc.querySelector('[data-split]');
  const bar = main.querySelector('.split-bar');
  const ed = main.querySelector('.ed-panel');
  bar.dispatchEvent(new win.MouseEvent('mousedown',{clientX:500,bubbles:true,cancelable:true}));
  win.dispatchEvent(new win.MouseEvent('mousemove',{clientX:700,bubbles:true,cancelable:true}));
  win.dispatchEvent(new win.MouseEvent('mouseup',{bubbles:true}));
  await new Promise(r=>setTimeout(r,500));
  const saved = win.localStorage.getItem('vapi-split-code-0');
  console.log('접은 채 끌고 저장한 값:', saved, '| 그때 편집기 폭:', ed.clientWidth + 'px');
  win.close();

  // 2) 나갔다 들어오되 파일 목록을 편 상태
  dom = await page({ 'vapi-split-v4':'1', 'vapi-split-code-0': saved }, true);
  win = dom.window; doc = win.document;
  const ed2 = doc.querySelector('.ed-panel');
  const out2 = doc.querySelector('.out-panel');
  const fp = doc.getElementById('filePanel');
  const total = fp.clientWidth + ed2.clientWidth + out2.clientWidth;
  console.log('다시 들어왔을 때  : 파일', fp.clientWidth, '+ 편집기', ed2.clientWidth,
              '+ 결과', out2.clientWidth, '=', total, '/ 1200');
  console.log('→', total <= 1200 ? '넘치지 않음 O' : '넘침 ✗ (' + (total-1200) + 'px 초과)');
  win.close();
})();
