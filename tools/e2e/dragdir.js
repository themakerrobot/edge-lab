const { JSDOM, VirtualConsole } = require('jsdom');
const B='http://127.0.0.1:57900';
process.on('unhandledRejection',()=>{}); process.on('uncaughtException',()=>{});
const wait=ms=>new Promise(r=>setTimeout(r,ms));
async function test(path, dir) {
  const html = await (await fetch(B+path)).text();
  const dom = new JSDOM(html,{url:B+path,runScripts:'dangerously',resources:'usable',
    pretendToBeVisual:true,virtualConsole:new VirtualConsole(),
    beforeParse(win){
      win.fetch=(u,o)=>fetch(new URL(u,B).href,o);
      const rect=()=>({top:0,left:0,right:0,bottom:0,width:0,height:0,x:0,y:0});
      win.Range.prototype.getBoundingClientRect=rect;
      win.Range.prototype.getClientRects=()=>({length:0,item:()=>null,[Symbol.iterator]:function*(){}});
      win.HTMLCanvasElement.prototype.getContext=()=>new Proxy({},{get:()=>()=>({}),set:()=>true});
      win.matchMedia=win.matchMedia||(()=>({matches:false,addListener(){},addEventListener(){}}));
      win.prompt=()=>null; win.alert=()=>{}; win.confirm=()=>true;
      // 폭 계산: 컨테이너 1200, 각 칸은 style.flexBasis 를 따른다
      Object.defineProperty(win.HTMLElement.prototype,'clientWidth',{get(){
        if (this.hasAttribute && this.hasAttribute('data-split')) return 1200;
        const b=this.style.flexBasis;
        if (b && b.endsWith('%')) return 1200*parseFloat(b)/100;
        if (b && b.endsWith('px')) return parseFloat(b);
        return 600; }});
      Object.defineProperty(win.HTMLElement.prototype,'offsetWidth',{get(){return this.clientWidth;}});
    }});
  await wait(4200);
  const win=dom.window, doc=win.document;
  const main=doc.querySelector('[data-split]');
  const bar=main.querySelector('.split-bar');
  const list=[...main.children].filter(c=>!c.classList.contains('split-bar')
       && win.getComputedStyle(c).display!=='none');
  const a=list[0];
  const from=600, to=from+dir;              // dir>0 이면 오른쪽(편집기 넓히기)
  bar.dispatchEvent(new win.MouseEvent('mousedown',{clientX:from,bubbles:true,cancelable:true}));
  win.dispatchEvent(new win.MouseEvent('mousemove',{clientX:to,bubbles:true,cancelable:true}));
  const during=a.style.flexBasis;
  win.dispatchEvent(new win.MouseEvent('mouseup',{bubbles:true}));
  await wait(400);
  const after=a.style.flexBasis;
  await wait(1500);
  const later=a.style.flexBasis;
  console.log('  %s %s  끄는중 %-9s 놓은뒤 %-9s 1.9초뒤 %-9s %s',
    path.padEnd(8), dir>0?'오른쪽→':'←왼쪽 ', during, after, later,
    (after===later ? 'O' : '✗ 되돌아감'));
  win.close();
}
(async () => {
  for (const p of ['/blocks','/code']) { await test(p, 200); await test(p, -200); }
})();
