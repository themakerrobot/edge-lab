const { JSDOM, VirtualConsole } = require('jsdom');
const B='http://127.0.0.1:57900';
process.on('unhandledRejection',()=>{}); process.on('uncaughtException',()=>{});
const wait=ms=>new Promise(r=>setTimeout(r,ms));
async function open_(mic) {
  const html = await (await fetch(B+'/options')).text();
  return new JSDOM(html,{url:B+'/options',runScripts:'dangerously',resources:'usable',
    pretendToBeVisual:true,virtualConsole:new VirtualConsole(),
    beforeParse(win){
      win.fetch=(u,o)=>fetch(new URL(u,B).href,o);
      const rect=()=>({top:0,left:0,right:0,bottom:0,width:0,height:0,x:0,y:0});
      win.Range.prototype.getBoundingClientRect=rect;
      win.Range.prototype.getClientRects=()=>({length:0,item:()=>null,[Symbol.iterator]:function*(){}});
      win.HTMLCanvasElement.prototype.getContext=()=>new Proxy({},{get:()=>()=>({}),set:()=>true});
      win.matchMedia=win.matchMedia||(()=>({matches:false,addListener(){},addEventListener(){}}));
      win.alert=m=>console.log('  ★ 팝업:', m);
      // 마이크 상황
      Object.defineProperty(win.navigator,'mediaDevices',{configurable:true,
        get:()=>mic?{getUserMedia:mic}:undefined});
      // Web Audio 흉내 — 녹음·재생 흐름이 끝까지 도는지만 본다
      let ended=null;
      win.AudioContext = function(){
        this.sampleRate=16000; this.currentTime=0; this.destination={};
        this.createMediaStreamSource=()=>({connect(){},disconnect(){}});
        this.createScriptProcessor=()=>({connect(){},disconnect(){},onaudioprocess:null});
        this.createBuffer=(c,len)=>({getChannelData:()=>new Float32Array(len)});
        this.createBufferSource=()=>{ const o={connect(){},start(){ setTimeout(()=>o.onended&&o.onended(),50); },onended:null}; return o; };
        this.createOscillator=()=>({type:'',frequency:{},connect(){return {connect(){}};},start(){},stop(){}});
        this.createGain=()=>({gain:{setValueAtTime(){},exponentialRampToValueAtTime(){}},connect(){return {connect(){}};}});
        this.close=()=>{};
      };
    }});
}
(async () => {
  console.log('═══ 마이크 있음');
  let dom = await open_(async () => ({ getTracks: () => [{ stop(){} }] }));
  await wait(3500);
  let doc = dom.window.document;
  console.log('  단추:', doc.getElementById('txtMicTest').textContent,
              '/', doc.getElementById('txtMicOpen').textContent);
  doc.getElementById('micTest').click();
  await wait(1200);
  console.log('  녹음 중 안내:', doc.getElementById('txtMicHint').textContent.slice(0,40));
  console.log('  단추 표시   :', doc.getElementById('txtMicTest').textContent);
  await wait(3500);
  console.log('  끝난 뒤 안내:', doc.getElementById('txtMicHint').textContent.slice(0,45));
  dom.window.close();

  for (const [label, gum] of [['마이크 없음', null],
      ['권한 거부', () => Promise.reject(Object.assign(new Error('x'),{name:'NotAllowedError'}))],
      ['사용 중',   () => Promise.reject(Object.assign(new Error('x'),{name:'NotReadableError'}))]]) {
    dom = await open_(gum); await wait(3500);
    doc = dom.window.document;
    doc.getElementById('micTest').click();
    await wait(800);
    console.log(('═══ '+label).padEnd(16), doc.getElementById('txtMicHint').textContent.slice(0,40),
                '| 단추:', doc.getElementById('txtMicTest').textContent);
    dom.window.close();
  }
})();
