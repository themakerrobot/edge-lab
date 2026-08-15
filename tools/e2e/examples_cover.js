/* 예제 커버리지 점검 — 서버 없이 파일만 읽어 돈다.
 *
 *   node tools/e2e/examples_cover.js
 *
 * 무엇을 보나:
 *   1) 툴박스에 있는 블록이 예제에 한 번이라도 나오는가
 *   2) 예제가 쓰는 블록이 JS·파이썬 생성기에 다 있는가
 *   3) themaker 의 공개 함수가 파이썬 "전체 점검" 예제에 나오는가
 *
 * 기능을 늘릴 때 예제를 같이 안 고치면 여기서 걸린다.
 * 일부러 뺀 것은 아래 SKIP 에 이유와 함께 적는다.
 */
const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..", "..");
const blocksHtml = fs.readFileSync(path.join(ROOT, "view_project/blocks.html"), "utf8");
const codeHtml = fs.readFileSync(path.join(ROOT, "view_project/code.html"), "utf8");
const themaker = fs.readFileSync(path.join(ROOT, "themaker.py"), "utf8");

/* 일부러 예제에 안 넣은 것들 — 사람 손이나 준비물이 있어야 해서
   자동 점검이 그 자리에서 멈춘다. */
const SKIP_BLOCKS = {
  ai_upload: "사진 파일을 사람이 골라야 함",
  ev_wait_hand: "손을 들 때까지 멈춰 섬",
  ev_wait_custom: "가르친 모델이 있어야 함",
};
const SKIP_FUNCS = {
  listen: "마이크에 대고 말해야 함",
  wav_to_text: "wav 파일이 있어야 함",
  load: "사진 파일이 있어야 함",
  language: "화면 언어를 통째로 바꿔 버림",
};

function examples(html, marker, endMark, arg) {
  const s = html.indexOf(marker);
  const e = html.indexOf(endMark, s);
  return new Function(...(arg ? ["t"] : []), html.slice(s, e + endMark.length) +
    (arg ? " return EXAMPLES();" : " return EXAMPLES;"))(...(arg ? [k => k] : []));
}

let fails = 0;
const fail = (msg) => { fails++; console.log("FAIL " + msg); };

/* ── 1) 블록 커버리지 ─────────────────────────────────────────── */
const EXB = examples(blocksHtml, "function EXAMPLES()", "\n  }\n", true);
const ts = blocksHtml.indexOf("function buildToolbox()");
const te = blocksHtml.indexOf("const WS_OPTS");
const toolbox = [...new Set([...blocksHtml.slice(ts, te)
  .matchAll(/kind: "block", type: "([a-z_0-9]+)"/g)].map(m => m[1]))];

const used = new Set();
const walk = (b) => {
  if (!b || typeof b !== "object") return;
  if (b.type) used.add(b.type);
  if (b.next) walk(b.next.block);
  if (b.inputs) for (const k in b.inputs) { walk(b.inputs[k].block); walk(b.inputs[k].shadow); }
};
EXB.forEach(ex => ex.state.blocks.blocks.forEach(walk));

const missBlocks = toolbox.filter(t => !used.has(t) && !SKIP_BLOCKS[t]);
if (missBlocks.length) fail("예제에 없는 블록: " + missBlocks.join(" "));
console.log(`  블록 예제 ${EXB.length}종 | 툴박스 ${toolbox.length} 중 ${toolbox.filter(t => used.has(t)).length} 사용`
  + ` (일부러 뺀 것 ${Object.keys(SKIP_BLOCKS).length})`);

/* ── 2) 생성기 대응 ───────────────────────────────────────────── */
const stmtTypes = new Set([...blocksHtml.matchAll(/T === "([a-z_0-9]+)"/g)].map(m => m[1]));
const pyAnchor = blocksHtml.indexOf("ai_capture: () =>");
const valTypes = new Set([...blocksHtml.slice(pyAnchor - 5000, pyAnchor + 9000)
  .matchAll(/^\s{6}([a-z_0-9]+):/gm)].map(m => m[1]));
const jsTypes = new Set([...blocksHtml.matchAll(/G\.forBlock\["([a-z_0-9]+)"\]/g)].map(m => m[1]));
const builtin = /^(controls_|logic_|math_|text|lists_|variables_|procedures_)/;

const noPy = [...used].filter(u => !builtin.test(u) && !stmtTypes.has(u) && !valTypes.has(u));
const noJs = [...used].filter(u => !builtin.test(u) && !jsTypes.has(u));
if (noPy.length) fail("파이썬 생성기 없음: " + noPy.join(" "));
if (noJs.length) fail("JS 생성기 없음: " + noJs.join(" "));

/* ── 3) 파이썬 예제 ───────────────────────────────────────────── */
const EXP = examples(codeHtml, "const EXAMPLES = [", "\n    ];");
const fullCheck = EXP[EXP.length - 1].code;
const funcs = [...themaker.matchAll(/^def ([a-z_]+)\(/gm)].map(m => m[1]).filter(f => !f.startsWith("_"));
const missFuncs = funcs.filter(f => !SKIP_FUNCS[f] && !new RegExp("\\b" + f + "\\s*\\(").test(fullCheck));
/* ---- vision(kind) 가 도움말·자동완성에 다 있는가 ----
   themaker 에 기능을 더하고 code.html 을 안 고치면 아이가 그 기능을 못 찾는다
   (depth 가 실제로 자동완성에만 있고 도움말에는 빠져 있었다). */
const kindsBlock = themaker.match(/_API\s*=\s*\{([\s\S]*?)\n\}/);
if (kindsBlock) {
  const kinds = [...new Set([...kindsBlock[1].matchAll(/"([a-z_0-9]+)":\s*\(/g)].map(m => m[1]))];
  /* 예제 코드 안의 vision(...) 까지 세면 도움말이 비어도 통과한다 —
     도움말 항목의 n: 'vision("kind" ...' 형태만 센다. */
  const inHelp = new Set([...codeHtml.matchAll(/n: 'vision\("([a-z_0-9]+)"/g)].map(m => m[1]));
  const autoM = codeHtml.match(/const KINDS = \[([\s\S]*?)\];/);
  const inAuto = new Set(autoM ? [...autoM[1].matchAll(/"([a-z_0-9]+)"/g)].map(m => m[1]) : []);
  const noHelp = kinds.filter(k => !inHelp.has(k));
  const noAuto = kinds.filter(k => !inAuto.has(k));
  console.log("vision 기능 " + kinds.length + "종 | 도움말 빠짐: " +
              (noHelp.join(" ") || "없음") + " | 자동완성 빠짐: " + (noAuto.join(" ") || "없음"));
  if (noHelp.length || noAuto.length) fail("vision 기능이 code.html 에 빠짐");
}

if (missFuncs.length) fail("전체 점검에 없는 함수: " + missFuncs.join(" "));
console.log(`  파이썬 예제 ${EXP.length}종 | themaker 함수 ${funcs.length} 중`
  + ` ${funcs.filter(f => new RegExp("\\b" + f + "\\s*\\(").test(fullCheck)).length} 를 전체 점검이 사용`
  + ` (일부러 뺀 것 ${Object.keys(SKIP_FUNCS).length})`);

console.log(fails ? `\n예제 점검 실패 ${fails}건` : "\n예제 점검 통과");
process.exit(fails ? 1 : 0);
