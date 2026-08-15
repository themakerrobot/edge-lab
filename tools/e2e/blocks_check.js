/* 블록 화면 정적 점검 — 서버 없이 돈다.
 *   node tools/e2e/blocks_check.js      (저장소 루트에서)
 *
 * 세 가지를 본다.
 *   1) 한/영 사전 키가 짝을 이루는지
 *   2) 블록 문구의 %n 개수가 인자 개수와 맞는지 (한·영 각각)
 *      — 예전에 영문 문구에만 %1 을 빠뜨려 예제가 중간에 잘린 적이 있다
 *
 * 예제 커버리지는 examples_cover.js 가 따로 본다 — 여기서는 말(사전)만 본다.
 */
const fs=require("fs"),h=fs.readFileSync("view_project/blocks.html","utf8");
const L=h.split("\n");
let ko=-1,en=-1; L.forEach((l,i)=>{if(/^\s*ko:\s*\{/.test(l)&&ko<0)ko=i; else if(/^\s*en:\s*\{/.test(l)&&en<0)en=i;});
const ind=L[en].match(/^\s*/)[0].length; let end=-1;
for(let i=en+1;i<L.length;i++) if(new RegExp("^\\s{"+ind+"}\\},?\\s*$").test(L[i])){end=i;break;}
const KO=new Function("return {"+L.slice(ko+1,en).join("\n").replace(/,\s*\}\s*,?\s*$/,"")+"}")();
const EN=new Function("return {"+L.slice(en+1,end).join("\n").replace(/,\s*\}\s*,?\s*$/,"")+"}")();
const ds=h.indexOf("Blockly.defineBlocksWithJsonArray([");
const src=h.slice(ds, h.indexOf("]);", ds));
// 블록 경계: 6칸 들여쓴 '{ type:' 줄들
const starts=[]; src.split("\n").forEach((l,i)=>{ if(/^      \{ type: "[a-z_0-9]+"/.test(l)) starts.push(i); });
const lines=src.split("\n");
let bad=[], n=0;
starts.forEach((st,k)=>{
  const body=lines.slice(st, starts[k+1]??lines.length).join("\n");
  const type=body.match(/\{ type: "([a-z_0-9]+)"/)[1];
  const km=body.match(/message0: (?:"%1 " \+ )?t\("([a-z_0-9]+)"\)/);
  if(!km) return; n++;
  const prefix=/message0: "%1 " \+ /.test(body)?1:0;
  const nArgs=(body.match(/type: "(?:input_value|field_dropdown|field_image|field_number|field_input)"/g)||[]).length
            + (body.match(/\bIMG(?:,|\s*\])/g)||[]).length;
  for(const [lang,D] of [["ko",KO],["en",EN]]){
    const msg=D[km[1]];
    if(msg===undefined){ bad.push(type+" 사전없음("+lang+")"); continue; }
    /* 가장 큰 번호만 보면 %1 이 빠지고 %2 만 있어도 통과한다 —
       Blockly 는 %1..%n 이 하나씩 다 있어야 하므로 번호 집합을 그대로 견준다. */
    const ns=[...String(msg).matchAll(/%(\d+)/g)].map(x=>+x[1]+0);
    const got=[...new Set(prefix ? [1].concat(ns.map(v=>v+prefix)) : ns)].sort((a,b)=>a-b);
    const want=Array.from({length:nArgs},(_,i)=>i+1);
    if(got.join(",")!==want.join(",")) bad.push(`${type}.${lang}: 문구 %${got.join(" %")||"없음"} vs 인자 ${nArgs}개`);
  }
});
/* ---- 1) 사전 키 짝 ---- */
const kk=new Set(Object.keys(KO)), ek=new Set(Object.keys(EN));
const onlyKo=[...kk].filter(k=>!ek.has(k)), onlyEn=[...ek].filter(k=>!kk.has(k));
console.log("사전 키: 한", kk.size, "영", ek.size,
  "| 한쪽에만:", (onlyKo.concat(onlyEn)).join(" ") || "없음 ✓");
if (onlyKo.length || onlyEn.length) bad.push("사전 키 짝 안 맞음");

/* ---- 2) 문구 자리표시 ---- */
console.log("검사한 블록:", n);
console.log("문구·인자 불일치:", bad.length? "\n  "+bad.join("\n  ") : "없음 ✓");


if (bad.length) process.exit(1);
