const { JSDOM, VirtualConsole } = require('jsdom');
const B='http://127.0.0.1:57900';
process.on('unhandledRejection',()=>{}); process.on('uncaughtException',()=>{});
const wait=ms=>new Promise(r=>setTimeout(r,ms));
async function run(label, gum) {
  const html = await (await fetch(B+'/train')).text();
  const dom = new JSDOM(html,{url:B+'/train',runScripts:'dangerously',resources:'usable',
    pretendToBeVisual:true,virtualConsole:new VirtualConsole(),
    beforeParse(win){
      win.fetch=(u,o)=>fetch(new URL(u,B).href,o);
      const rect=()=>({top:0,left:0,right:0,bottom:0,width:0,height:0,x:0,y:0});
      win.Range.prototype.getBoundingClientRect=rect;
      win.Range.prototype.getClientRects=()=>({length:0,item:()=>null,[Symbol.iterator]:function*(){}});
      win.HTMLCanvasElement.prototype.getContext=()=>new Proxy({},{get:()=>()=>({}),set:()=>true});
      win.matchMedia=win.matchMedia||(()=>({matches:false,addListener(){},addEventListener(){}}));
      win.alert=m=>console.log('   ★ 팝업:', m);
      Object.defineProperty(win.navigator,'mediaDevices',{configurable:true,
        get:()=>gum?{getUserMedia:gum,enumerateDevices:async()=>[]}:undefined});
    }});
  await wait(4000);
  const doc=dom.window.document;
  const box=doc.getElementById('camMsg');
  console.log(('  '+label).padEnd(16), '안내:', box ? JSON.stringify(box.textContent).slice(0,62) : '자리 없음',
              '| 사진넣기 단추:', doc.getElementById('fileImgs') ? '있음' : '없음');
  dom.window.close();
}
(async () => {
  await run('카메라 없음', null);
  await run('권한 거부', () => Promise.reject(Object.assign(new Error('x'),{name:'NotAllowedError'})));
  await run('사용 중',   () => Promise.reject(Object.assign(new Error('x'),{name:'NotReadableError'})));
})();
