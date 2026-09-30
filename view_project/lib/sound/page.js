// 소리 가르치기 — 화면 로직 (view_project/sound.html)
// themakerrobot/teach-lab lib/learn.js · lib/exam.js (커밋 74f421a) 의 소리 흐름
// (꾹 눌러 모으기 → sqrt-L2 → 배우기 → 실시간 맞히기)을 이 저장소 화면(패널·토큰·I18N)에 맞게 다시 짰다.
//
// MIT License
//
// Copyright (c) 2026 themakerrobot
//
// Permission is hereby granted, free of charge, to any person obtaining a copy
// of this software and associated documentation files (the "Software"), to deal
// in the Software without restriction, including without limitation the rights
// to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
// copies of the Software, and to permit persons to whom the Software is
// furnished to do so, subject to the following conditions:
//
// The above copyright notice and this permission notice shall be included in all
// copies or substantial portions of the Software.
//
// THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
// IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
// FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
// AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
// LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
// OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
// SOFTWARE.

// 흐름: ① 종류 만들고 꾹 눌러 소리 모으기 → ② 배우기(TF.js, 1초 남짓) → ③ 실시간으로 해 보기
// 마이크는 모으는 동안과 "해 보기" 를 켠 동안에만 연다. 소리는 이 컴퓨터 밖으로 나가지 않는다.

import { createSoundEngine, preloadSound, labelNames, SOUND_DIM, WAVE_BINS } from './engine.js';
import { trainModel } from './trainer.js';
import { serialize, deserialize, predict, bytesToB64, b64ToBytes } from './classifier.js';
import { applySoundTransform, SOUND_TRANSFORM } from './features.js';
import { labelOf } from './labels.js';

let LANG = 'ko';
try { LANG = localStorage.getItem('vapiLang') === 'en' ? 'en' : 'ko'; } catch (e) {}
document.documentElement.lang = LANG;

const I18N = {
  ko: {
    title: 'edge-lab — 소리 가르치기', app: '소리 가르치기', lang: 'EN',
    q1: '소리 모으기', q2: '배우기', q3: '해 보기',
    newP: '새로', exportP: '파일로 저장', importP: '파일 열기',
    newSure: '정말 새로?', newDone: '새로 시작해요', exported: '파일로 저장했어요',
    imported: '파일을 열었어요', importFail: '이 앱에서 저장한 파일이 아니에요',
    q1hint: '종류마다 단추를 꾹 누르고 소리를 내요. 누르는 동안 1초 조각이 계속 모여요.',
    rec: '꾹 눌러 녹음', recOn: '듣는 중… 놓으면 멈춰요', recWait: '귀를 여는 중…',
    count: '{n}개', empty: '아직 예시가 없어요',
    colorTip: '색 바꾸기', delCls: '종류 지우기', delSure: '지울까요?', delSmp: '이 예시 지우기',
    namePh: '소리 이름', bgTag: '배경',
    addCls: '종류 추가', maxCls: '종류는 6개까지예요', minCls: '종류가 2개는 있어야 해요',
    quiet: '조용함', clap: '박수', whistle: '휘파람', newName: '소리 {n}',
    full: '한 종류에 {n}개까지 모을 수 있어요',
    micFail: '마이크를 쓸 수 없어요 — 설정에서 마이크를 확인해 주세요.',
    earFail: 'AI 귀(YAMNet)를 불러오지 못했어요. 새로고침해 주세요.',
    train: '배우기', trainAgain: '다시 배우기', learning: '배우는 중', notYet: '아직 안 배웠어요',
    needCls: '종류가 2개 이상 있어야 배울 수 있어요', needSmp: '종류마다 예시가 {n}개는 있어야 해요 — {c}',
    learned: '다 배웠어요! 정확도 {p}%', learnedN: '예시 {n}개 · {s}초 걸렸어요', trainFail: '배우다가 멈췄어요: ',
    stale: '배운 뒤에 예시가 바뀌었어요. 다시 배우면 반영돼요.', changed: '종류가 바뀌었어요. 다시 배워 주세요.',
    accLbl: '맞힘', lossLbl: '틀린 정도',
    perCls: '종류별로 맞힌 수', perRow: '{n}개 중 {k}개',
    confused: '가장 많이 헷갈린 것: {a} → {b} ({n}번)', noConfuse: '헷갈린 것이 없어요',
    tipsT: '잘 가르치는 비결', tip1: '예시가 많고 다양할수록 잘 배워요 — 크게·작게, 가까이·멀리.',
    tip2: '"조용함" 도 한 종류예요. 아무 소리 없을 때를 가르쳐야 엉뚱한 답을 안 해요.',
    tip3: '종류마다 예시 수를 비슷하게 맞춰요.',
    warnFew: '{c} 예시가 적어요 (10개 이상 추천)', warnBg: '"조용함" 종류가 없어요', addBg: '조용함 추가',
    warnImb: '예시 수 차이가 커요 — 적은 쪽을 더 모아요',
    live: '듣기 시작', liveStop: '멈추기', liveIdle: '"듣기 시작" 을 누르고 소리를 내 보세요',
    afterTrain: '배운 뒤에 대답해요', unsure: '잘 모르겠어요', waiting: '듣는 중…',
    thr: '이만큼은 확실해야 대답해요', thrV: '{p}%',
    earT: 'AI 귀에 들린 숫자', earCap: '소리 1초 → 숫자 {n}개. 막대 하나가 숫자 하나예요. 이 숫자로 배워요.',
    earOff: '마이크를 켜면 보여요', earLoading: 'AI 귀 준비 중…', earSample: '고른 예시를 AI 는 이렇게 들었어요',
    topT: 'AI 가 원래 아는 이름 (1~3등)', topHint: 'YAMNet 은 소리 521가지를 이미 알아요. 내가 가르친 이름은 이 숫자들 위에 새로 배운 거예요.',
    notified: '소리 가르치기 · 다 배웠어요 ({p}%)',
  },
  en: {
    title: 'edge-lab — Teach sounds', app: 'Teach sounds', lang: '한',
    q1: 'Collect sounds', q2: 'Train', q3: 'Try it',
    newP: 'New', exportP: 'Save file', importP: 'Open file',
    newSure: 'Really new?', newDone: 'Started fresh', exported: 'Saved to a file',
    imported: 'File opened', importFail: 'This file was not saved by this app',
    q1hint: 'Hold a button and make the sound. While you hold, 1-second pieces keep coming in.',
    rec: 'Hold to record', recOn: 'Listening… let go to stop', recWait: 'Opening ears…',
    count: '{n}', empty: 'No examples yet',
    colorTip: 'Change color', delCls: 'Delete sound', delSure: 'Delete?', delSmp: 'Delete this example',
    namePh: 'Sound name', bgTag: 'background',
    addCls: 'Add sound', maxCls: 'Up to 6 sounds', minCls: 'You need at least 2 sounds',
    quiet: 'Quiet', clap: 'Clap', whistle: 'Whistle', newName: 'Sound {n}',
    full: 'Up to {n} examples per sound',
    micFail: 'The mic cannot be used — check it in Settings.',
    earFail: 'Could not load the AI ears (YAMNet). Please reload.',
    train: 'Train', trainAgain: 'Train again', learning: 'Learning', notYet: 'Not trained yet',
    needCls: 'You need 2 or more sounds to train', needSmp: 'Each sound needs {n} examples — {c}',
    learned: 'Done! Accuracy {p}%', learnedN: '{n} examples · took {s} s', trainFail: 'Training stopped: ',
    stale: 'Examples changed after training. Train again to use them.', changed: 'The sounds changed. Please train again.',
    accLbl: 'correct', lossLbl: 'error',
    perCls: 'Correct per sound', perRow: '{k} of {n}',
    confused: 'Mixed up most: {a} → {b} ({n}×)', noConfuse: 'Nothing got mixed up',
    tipsT: 'Tips for teaching well', tip1: 'More and more varied examples help — loud, soft, near, far.',
    tip2: '"Quiet" is a sound too. Teach what silence sounds like so the AI does not guess wildly.',
    tip3: 'Keep the number of examples similar for each sound.',
    warnFew: '{c} has few examples (10+ is better)', warnBg: 'There is no "Quiet" sound', addBg: 'Add Quiet',
    warnImb: 'Example counts are very uneven — collect more of the small ones',
    live: 'Start listening', liveStop: 'Stop', liveIdle: 'Press "Start listening" and make a sound',
    afterTrain: 'It answers after training', unsure: 'Not sure', waiting: 'Listening…',
    thr: 'Answer only when this sure', thrV: '{p}%',
    earT: 'Numbers the AI hears', earCap: '1 s of sound → {n} numbers. Each bar is one number. These are what it learns from.',
    earOff: 'Shows up when the mic is on', earLoading: 'Getting the AI ears ready…', earSample: 'How the AI heard the chosen example',
    topT: 'Names the AI already knows (top 3)', topHint: 'YAMNet already knows 521 sounds. Your names are learned on top of these numbers.',
    notified: 'Teach sounds · done ({p}%)',
  },
};
function t(k, v) {
  let s = I18N[LANG][k] !== undefined ? I18N[LANG][k] : I18N.ko[k];
  if (v) for (const n in v) s = s.split('{' + n + '}').join(v[n]);
  return s;
}
const $ = id => document.getElementById(id);
const esc = s => String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

const IC = {
  mic: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21"/></svg>',
  stop: '<svg viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="6" width="12" height="12" rx="2"/></svg>',
  trash: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13M10 11v6M14 11v6"/></svg>',
  plus: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg>',
  x: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round"><path d="M6 6l12 12M18 6L6 18"/></svg>',
  learn: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="5" cy="7" r="2"/><circle cx="5" cy="17" r="2"/><circle cx="19" cy="12" r="2"/><path d="M7 7.5l10 4M7 16.5l10-4"/></svg>',
  ear: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M7 9a5 5 0 0 1 10 0c0 3-3 4-3 7a3 3 0 0 1-5.5 1.6"/><path d="M10 9.5a2 2 0 0 1 4 0c0 1-1 1.5-1.5 2"/></svg>',
  save: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 4v11M7 10l5 5 5-5M5 20h14"/></svg>',
  open: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20V9M7 13l5-5 5 5M5 4h14"/></svg>',
  fresh: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 12a8 8 0 1 0 2.5-5.8M4 4v5h5"/></svg>',
};

// 종류 색 — 종이색 바탕에서 서로 잘 갈리는 여섯 가지 (첫째는 "조용함" 용 회청색)
const COLORS = ['#6b7f8e', '#d9412b', '#2f8f4e', '#c98a12', '#7a4fb0', '#1f7fb5'];
const MIN_CLS = 2, MAX_CLS = 6;
const MAX_PER_CLASS = 80;      // 한 종류 예시 상한 — 저장 크기(예시 하나 2KB 남짓)와 학습 시간을 묶어 둔다
const MIN_TO_TRAIN = 3;        // 이보다 적으면 배우기를 막는다 (한두 개로는 운에 맡기는 셈이라)
const FEW = 10;                // 이보다 적으면 "적어요" 알림

/* ── 상태 ── */
let classes = [];      // {id, name, color, bg, samples: [{vec: Float32Array(521) 날것 점수, wave: Uint8Array(24)}]}
let nextId = 1;
let model = null;      // {json, bin, classIds, acc, confusion, history, ms, n, sig}
let clf = null;        // 추론용 (classifier.js deserialize)
let threshold = 0.6;
let training = false, hist = [];
let rec = null;        // 녹음 중: {cid, held, got}
let live = false, liveWasOn = false;
let sel = null;        // 고른 예시 {cid, i}
let names = null;      // YAMNet 이름표 521개
let earState = 'loading';
let lastEar = null;    // 마지막으로 그린 {vec, top}
const eng = createSoundEngine();

function defaults() {
  nextId = 1;
  classes = [
    { id: nextId++, name: t('quiet'), color: COLORS[0], bg: true, samples: [] },
    { id: nextId++, name: t('clap'), color: COLORS[1], samples: [] },
    { id: nextId++, name: t('whistle'), color: COLORS[2], samples: [] },
  ];
  model = null; clf = null; threshold = 0.6; hist = []; sel = null;
}
const byId = id => classes.find(c => c.id === id);
const total = () => classes.reduce((n, c) => n + c.samples.length, 0);
// 학습 뒤 예시가 바뀌었는지 — 종류별 개수 목록으로 가늠한다 (지우고 같은 수만큼 모으면 못 알아채지만 수업에는 충분)
const sampleSig = () => classes.map(c => c.id + ':' + c.samples.length).join(',');

/* ── 저장 — IndexedDB (예시가 수백 개면 수 MB 라 localStorage 로는 모자란다) ── */
const DB = 'edge-lab-sound', STORE = 'kv', KEY = 'autosave';
let dbp = null;
function db() {
  if (!dbp) dbp = new Promise((ok, no) => {
    const r = indexedDB.open(DB, 1);
    r.onupgradeneeded = () => r.result.createObjectStore(STORE);
    r.onsuccess = () => ok(r.result);
    r.onerror = () => no(r.error);
  });
  return dbp;
}
function snapshot() {
  return { v: 1, nextId, threshold, classes: classes.map(c => ({ id: c.id, name: c.name, color: c.color, bg: !!c.bg, samples: c.samples })), model };
}
async function saveNow() {
  clearTimeout(saveTimer); saveTimer = null;
  try {
    const d = await db();
    await new Promise((ok, no) => {
      const tx = d.transaction(STORE, 'readwrite');
      tx.objectStore(STORE).put(snapshot(), KEY);
      tx.oncomplete = ok; tx.onerror = () => no(tx.error);
    });
  } catch (e) { console.warn('sound save', e); }
}
let saveTimer = null;
function save() { clearTimeout(saveTimer); saveTimer = setTimeout(saveNow, 400); }
async function loadSaved() {
  try {
    const d = await db();
    return await new Promise((ok, no) => {
      const r = d.transaction(STORE).objectStore(STORE).get(KEY);
      r.onsuccess = () => ok(r.result || null); r.onerror = () => no(r.error);
    });
  } catch (e) { return null; }
}
function restore(s) {
  if (!s || s.v !== 1 || !Array.isArray(s.classes) || s.classes.length < MIN_CLS) return false;
  classes = s.classes.map(c => ({ id: c.id, name: String(c.name || ''), color: c.color || COLORS[0], bg: !!c.bg,
    samples: (c.samples || []).map(x => ({ vec: new Float32Array(x.vec), wave: new Uint8Array(x.wave || WAVE_BINS) })) }));
  nextId = Math.max(s.nextId || 1, ...classes.map(c => c.id + 1));
  threshold = typeof s.threshold === 'number' ? s.threshold : 0.6;
  model = s.model || null; clf = null; hist = model && model.history ? model.history : [];
  if (model) {
    try { clf = deserialize(model.json, model.bin); } catch (e) { model = null; hist = []; }
  }
  sel = null;
  return true;
}

/* ── 파일로 저장 / 열기 — 다른 컴퓨터로 옮기거나 선생님께 내기 ── */
function f32ToB64(a) { return bytesToB64(new Uint8Array(a.buffer, a.byteOffset, a.byteLength)); }
function exportFile() {
  const s = snapshot();
  const out = {
    format: 'edge-lab-sound', version: 1, savedAt: new Date().toISOString(), featureTransform: SOUND_TRANSFORM,
    threshold: s.threshold, nextId: s.nextId,
    classes: s.classes.map(c => ({ id: c.id, name: c.name, color: c.color, bg: c.bg,
      samples: c.samples.map(x => ({ vec: f32ToB64(x.vec), wave: bytesToB64(x.wave) })) })),
    model: model ? { json: model.json, bin: bytesToB64(new Uint8Array(model.bin)), classIds: model.classIds, acc: model.acc,
                     confusion: model.confusion, history: model.history, ms: model.ms, n: model.n, sig: model.sig } : null,
  };
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([JSON.stringify(out)], { type: 'application/json' }));
  a.download = (LANG === 'ko' ? '소리-가르치기' : 'teach-sounds') + '.json';
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 2000);
  toast(t('exported'));
}
function importText(text) {
  let j;
  try { j = JSON.parse(text); } catch (e) { j = null; }
  if (!j || j.format !== 'edge-lab-sound') { toast(t('importFail')); return false; }
  const s = {
    v: 1, nextId: j.nextId, threshold: j.threshold,
    classes: (j.classes || []).map(c => ({ id: c.id, name: c.name, color: c.color, bg: c.bg,
      samples: (c.samples || []).map(x => ({ vec: new Float32Array(b64ToBytes(x.vec).buffer), wave: b64ToBytes(x.wave) })) })),
    model: j.model ? Object.assign({}, j.model, { bin: b64ToBytes(j.model.bin).buffer }) : null,
  };
  if (!restore(s)) { toast(t('importFail')); return false; }
  stopAll(); paintAll(); save(); toast(t('imported'));
  return true;
}

/* ── 마이크 — 모으는 중이거나 "해 보기" 를 켠 동안에만 ── */
function micWanted() { return !!rec || live; }
function syncMic() {
  if (micWanted()) {
    if (!eng.running) eng.start().then(() => { if (!micWanted()) eng.stop(); loopLevel(); })
      .catch(err => { console.warn(err); toast(earState === 'fail' ? t('earFail') : t('micFail')); rec = null; live = false; paintRec(); paintLive(); });
  } else if (eng.running) { eng.stop(); paintEarIdle(); }
}
function stopAll() {
  rec = null; live = false; syncMic(); paintRec(); paintLive();
}

eng.onTick = latest => onHear(latest);
function onHear(latest) {
  lastEar = latest;
  sel = null; paintSel();
  paintEar(latest.vec, latest.top);
  if (rec) {
    const c = byId(rec.cid);
    if (c && c.samples.length < MAX_PER_CLASS) {
      addSample(c, latest.vec, latest.wave);
      rec.got++;
    } else if (c) { toast(t('full', { n: MAX_PER_CLASS })); endRec(); }
    if (rec && !rec.held) endRec();          // 짧게 톡 누르면 첫 조각(1초) 하나만 받고 끝낸다
  }
  if (live || !rec) paintAnswer(latest.vec);
}

// 소리 크기 — 녹음 단추 테두리와 "귀" 크기 막대. 마이크가 켜진 동안만 돈다
let levelOn = false;
function loopLevel() {
  if (levelOn) return;
  levelOn = true;
  (function f() {
    if (!eng.running) { levelOn = false; $('lvl').style.width = '0'; $('fill').hidden = true; setRecGlow(0); return; }
    const lv = Math.min(1, eng.level * 6);
    $('lvl').style.width = (lv * 100).toFixed(1) + '%';
    const fl = eng.filled;
    $('fill').hidden = fl >= 1;
    if (fl < 1) $('fillBar').style.width = (fl * 100).toFixed(0) + '%';
    setRecGlow(lv);
    requestAnimationFrame(f);
  })();
}
function setRecGlow(lv) {
  const b = rec && document.querySelector('.cls[data-c="' + rec.cid + '"] .recb');
  document.querySelectorAll('.recb').forEach(x => { if (x !== b) x.style.removeProperty('--lv'); });
  if (b) b.style.setProperty('--lv', (4 + lv * 14).toFixed(1) + 'px');
}

/* ── 모으기 ── */
function addSample(c, vec, wave) {
  const w = new Uint8Array(WAVE_BINS);
  for (let i = 0; i < WAVE_BINS; i++) w[i] = Math.round(Math.min(1, (wave ? wave[i] : 0)) * 255);
  c.samples.push({ vec: Float32Array.from(vec), wave: w });
  const strip = document.querySelector('.cls[data-c="' + c.id + '"] .smps');
  if (strip) {
    const em = strip.querySelector('.empty'); if (em) em.remove();
    strip.appendChild(thumbEl(c, c.samples.length - 1));
    strip.scrollTop = strip.scrollHeight;
  }
  paintCount(c); paintTrain(); save();
}
function startRec(cid) {
  if (training || rec) return;
  const c = byId(cid);
  if (!c) return;
  if (c.samples.length >= MAX_PER_CLASS) { toast(t('full', { n: MAX_PER_CLASS })); return; }
  rec = { cid, held: true, got: 0 };
  paintRec(); syncMic();
  if (window.vapiStat) vapiStat('sound_rec');
}
function releaseRec() {
  if (!rec) return;
  rec.held = false;
  if (rec.got > 0) endRec();
  else { const r = rec; setTimeout(() => { if (rec === r) endRec(); }, 4000); }   // 귀가 끝내 안 열리면 포기
  paintRec();
}
function endRec() { rec = null; syncMic(); paintRec(); }

/* ── 배우기 ── */
function readiness() {
  if (classes.length < MIN_CLS) return t('needCls');
  const short = classes.filter(c => c.samples.length < MIN_TO_TRAIN);
  if (short.length) return t('needSmp', { n: MIN_TO_TRAIN, c: short.map(c => c.name || '?').join(', ') });
  return '';
}
async function train() {
  const why = readiness();
  if (why || training) { if (why) toast(why); return null; }
  if (rec) endRec();
  training = true; hist = [];
  paintTrain(); drawChart();
  $('prgLabel').textContent = t('learning');
  const X = [], Y = [];
  classes.forEach((c, k) => c.samples.forEach(s => { X.push(applySoundTransform(s.vec, SOUND_TRANSFORM)); Y.push(k); }));
  const t0 = performance.now();
  try {
    const r = await trainModel(X, Y, classes.length, SOUND_DIM, (ep, all, h) => {
      hist.push(h);
      const pct = Math.round(ep / all * 100);
      $('prgFill').style.width = pct + '%'; $('prgPct').textContent = pct + '%';
      drawChart();
    });
    const { json, bin } = await serialize(r.model, classes.map(c => c.name), SOUND_DIM);
    json.featureTransform = SOUND_TRANSFORM;
    r.model.dispose();
    model = { json, bin, classIds: classes.map(c => c.id), acc: r.accuracy, confusion: r.confusion, history: hist,
              ms: Math.round(performance.now() - t0), n: X.length, sig: sampleSig() };
    clf = deserialize(json, bin);
    training = false;
    const p = Math.round(r.accuracy * 100);
    if (window.vapiStat) vapiStat('sound_train');
    if (window.EL_WIN && EL_WIN.hidden) EL_WIN.notify(t('notified', { p }), { actions: [{ label: t('app'), href: '/sound' }] });
    save();
    paintTrain(); paintAnswer(lastEar && eng.running ? lastEar.vec : null);
    return { acc: r.accuracy, ms: model.ms, n: X.length };
  } catch (e) {
    training = false; console.error(e);
    paintTrain(); $('prgLabel').textContent = t('trainFail') + ((e && e.message) || e);
    return null;
  }
}
// 모델이 지금 종류와 맞는가 — 종류를 더하거나 지우면 출력 칸 수가 달라져 못 쓴다
function modelFits() {
  return !!(model && clf && model.classIds.length === classes.length && model.classIds.every((id, k) => classes[k] && classes[k].id === id));
}

/* ── 그리기: 종류 카드 ── */
function paintClasses() {
  const box = $('classes');
  box.innerHTML = '';
  classes.forEach(c => box.appendChild(classEl(c)));
  $('addCls').disabled = classes.length >= MAX_CLS || training;
  $('addCls').title = classes.length >= MAX_CLS ? t('maxCls') : '';
  paintRec();
}
function classEl(c) {
  const d = document.createElement('div');
  d.className = 'cls'; d.dataset.c = c.id; d.style.setProperty('--c', c.color);
  d.innerHTML =
    '<div class="cls-top">' +
      '<button class="dot" type="button" title="' + esc(t('colorTip')) + '" aria-label="' + esc(t('colorTip')) + '"></button>' +
      '<input class="cname" type="text" maxlength="14" spellcheck="false" placeholder="' + esc(t('namePh')) + '" value="' + esc(c.name) + '">' +
      (c.bg ? '<span class="bgtag">' + esc(t('bgTag')) + '</span>' : '') +
      '<span class="cnt num"></span>' +
      '<button class="icon del" type="button" title="' + esc(t('delCls')) + '" aria-label="' + esc(t('delCls')) + '">' + IC.trash + '</button>' +
    '</div>' +
    '<div class="cls-row">' +
      '<button class="recb" type="button">' + IC.mic + '<span></span></button>' +
      '<div class="smps"></div>' +
    '</div>';
  const strip = d.querySelector('.smps');
  if (!c.samples.length) strip.innerHTML = '<span class="empty hint">' + esc(t('empty')) + '</span>';
  c.samples.forEach((s, i) => strip.appendChild(thumbEl(c, i)));
  paintCount(c, d);
  return d;
}
function paintCount(c, el) {
  const d = el || document.querySelector('.cls[data-c="' + c.id + '"]');
  if (!d) return;
  const n = c.samples.length;
  const cnt = d.querySelector('.cnt');
  cnt.textContent = t('count', { n }) + (n >= MAX_PER_CLASS ? ' · max' : '');
  cnt.classList.toggle('few', n < FEW);
}
function thumbEl(c, i) {
  const b = document.createElement('button');
  b.type = 'button'; b.className = 'smp'; b.dataset.i = i;
  const cv = document.createElement('canvas');
  cv.width = 60; cv.height = 40;
  const g = cv.getContext('2d'), w = c.samples[i].wave;
  g.fillStyle = c.color;
  const bw = 60 / WAVE_BINS;
  for (let k = 0; k < WAVE_BINS; k++) {
    const h = Math.max(2, Math.min(1, Math.sqrt(w[k] / 255) * 1.1) * 36);
    g.fillRect(k * bw + bw * 0.18, (40 - h) / 2, bw * 0.64, h);
  }
  b.appendChild(cv);
  const x = document.createElement('span');
  x.className = 'sx'; x.innerHTML = IC.x; x.title = t('delSmp');
  b.appendChild(x);
  return b;
}
function paintRec() {
  document.querySelectorAll('.cls').forEach(d => {
    const on = !!rec && rec.cid === +d.dataset.c;
    d.classList.toggle('on', on);
    const b = d.querySelector('.recb');
    b.classList.toggle('on', on);
    b.querySelector('span').textContent = on ? (rec.got || eng.ready ? t('recOn') : t('recWait')) : t('rec');
    b.disabled = training || (!!rec && !on);
  });
}
function paintSel() {
  document.querySelectorAll('.smp.on').forEach(x => x.classList.remove('on'));
  if (!sel) return;
  const el = document.querySelector('.cls[data-c="' + sel.cid + '"] .smp[data-i="' + sel.i + '"]');
  if (el) el.classList.add('on');
}

/* ── 그리기: 배우기 ── */
function paintTrain() {
  const why = readiness();
  $('trainBtn').innerHTML = IC.learn + '<span>' + esc(model ? t('trainAgain') : t('train')) + '</span>';
  $('trainBtn').disabled = training || !!why;
  $('trainWhy').textContent = training ? '' : why;
  document.querySelectorAll('.recb').forEach(b => { if (training) b.disabled = true; });
  $('addCls').disabled = classes.length >= MAX_CLS || training;
  // 알림: 적은 예시·배경 소리·쏠림
  const warns = [];
  if (!classes.some(c => c.bg)) warns.push('<div class="warn">' + esc(t('warnBg')) + ' <button class="btn sm" id="addBg" type="button">' + IC.plus + esc(t('addBg')) + '</button></div>');
  const few = classes.filter(c => c.samples.length > 0 && c.samples.length < FEW);
  if (few.length) warns.push('<div class="warn">' + esc(t('warnFew', { c: few.map(c => c.name || '?').join(', ') })) + '</div>');
  const ns = classes.map(c => c.samples.length).filter(n => n > 0);
  if (ns.length >= 2 && Math.max(...ns) > 3 * Math.min(...ns) && Math.max(...ns) >= FEW) warns.push('<div class="warn">' + esc(t('warnImb')) + '</div>');
  $('warns').innerHTML = warns.join('');
  const ab = $('addBg'); if (ab) { ab.disabled = classes.length >= MAX_CLS; ab.onclick = () => addClass(true); }
  if (training) return;
  $('prgFill').style.width = model ? '100%' : '0';
  $('prgPct').textContent = '';
  if (!model) { $('prgLabel').textContent = t('notYet'); $('result').hidden = true; $('stale').hidden = true; drawChart(); return; }
  $('prgLabel').textContent = t('learned', { p: Math.round(model.acc * 100) });
  $('learnedN').textContent = t('learnedN', { n: model.n, s: (model.ms / 1000).toFixed(1) });
  const fits = modelFits();
  $('stale').hidden = fits && model.sig === sampleSig();
  $('stale').textContent = fits ? t('stale') : t('changed');
  // 종류별 맞힌 수 — 모델이 배운 순서(classIds)대로. 지금 이름·색을 쓴다
  const conf = model.confusion || [];
  $('perCls').innerHTML = model.classIds.map((id, k) => {
    const c = byId(id), row = conf[k] || [], n = row.reduce((a, b) => a + b, 0), ok = row[k] || 0;
    const nm = c ? c.name : model.json.classes[k], col = c ? c.color : '#999';
    return '<div class="bar"><div class="bl"><span>' + esc(nm) + '</span><span class="num">' + esc(t('perRow', { n, k: ok })) + '</span></div>' +
      '<div class="bt"><div class="bf" style="width:' + (n ? ok / n * 100 : 0) + '%;background:' + col + '"></div></div></div>';
  }).join('');
  let worst = null;
  conf.forEach((row, a) => row.forEach((v, b) => { if (a !== b && v > 0 && (!worst || v > worst.n)) worst = { a, b, n: v }; }));
  const nameK = k => { const c = byId(model.classIds[k]); return c ? c.name : model.json.classes[k]; };
  $('confused').textContent = worst ? t('confused', { a: nameK(worst.a), b: nameK(worst.b), n: worst.n }) : t('noConfuse');
  $('result').hidden = false;
  drawChart();
}
function css(v) { return getComputedStyle(document.documentElement).getPropertyValue(v).trim(); }
function drawChart() {
  const c = $('chart'), dpr = window.devicePixelRatio || 1, W = c.clientWidth, H = c.clientHeight;
  if (!W || !H) return;
  c.width = W * dpr; c.height = H * dpr;
  const g = c.getContext('2d'); g.scale(dpr, dpr); g.clearRect(0, 0, W, H);
  g.strokeStyle = '#ece5d6'; g.lineWidth = 1;
  for (let k = 1; k < 4; k++) { const y = Math.round(6 + k / 4 * (H - 12)) + 0.5; g.beginPath(); g.moveTo(0, y); g.lineTo(W, y); g.stroke(); }
  if (hist.length < 2) return;
  const maxL = Math.max(...hist.map(h => h.loss)) || 1, N = 40;
  const line = (vals, color) => {
    g.strokeStyle = color; g.lineWidth = 2; g.beginPath();
    vals.forEach((v, i) => { const x = 6 + i / (N - 1) * (W - 12), y = H - 6 - v * (H - 12); if (i) g.lineTo(x, y); else g.moveTo(x, y); });
    g.stroke();
  };
  line(hist.map(h => h.acc || 0), css('--pen-blue'));
  line(hist.map(h => h.loss / maxL), css('--pen-red'));
}

/* ── 그리기: 해 보기 ── */
function paintLive() {
  $('liveBtn').innerHTML = (live ? IC.stop : IC.ear) + '<span>' + esc(live ? t('liveStop') : t('live')) + '</span>';
  $('liveBtn').classList.toggle('on', live);
  if (!live && !lastAnswerShown) paintAnswer(null);
}
let lastAnswerShown = false;
function paintAnswer(vec) {
  const ans = $('answer'), bars = $('probs');
  const fits = modelFits();
  if (!fits) {
    ans.className = 'answer idle'; ans.innerHTML = '<span>' + esc(model ? t('changed') : t('afterTrain')) + '</span>';
    bars.innerHTML = ''; lastAnswerShown = false; return;
  }
  if (!vec) {
    ans.className = 'answer idle'; ans.innerHTML = '<span>' + esc(live ? t('waiting') : t('liveIdle')) + '</span>';
    bars.innerHTML = classes.map(c => probRow(c, 0, false)).join(''); lastAnswerShown = false; return;
  }
  const P = predict(clf, applySoundTransform(vec, SOUND_TRANSFORM));
  let best = 0;
  for (let k = 1; k < P.length; k++) if (P[k] > P[best]) best = k;
  const sure = P[best] >= threshold, c = classes[best];
  ans.className = 'answer' + (sure ? '' : ' unsure');
  ans.style.setProperty('--c', sure ? c.color : '#9a8f7d');
  ans.innerHTML = sure ? '<i></i><b>' + esc(c.name) + '</b><span class="num">' + Math.round(P[best] * 100) + '%</span>'
                       : '<i></i><b>' + esc(t('unsure')) + '</b><span class="num">' + Math.round(P[best] * 100) + '%</span>';
  bars.innerHTML = classes.map((cc, k) => probRow(cc, P[k], k === best && sure)).join('');
  lastAnswerShown = true;
  return { label: sure ? c.name : null, best, probs: Array.from(P) };
}
function probRow(c, p, top) {
  return '<div class="bar' + (top ? ' top' : '') + '"><div class="bl"><span>' + esc(c.name) + '</span><span class="num">' + Math.round(p * 100) + '%</span></div>' +
    '<div class="bt"><div class="bf" style="width:' + (p * 100).toFixed(1) + '%;background:' + c.color + '"></div></div></div>';
}
function paintThr() {
  $('thr').value = Math.round(threshold * 100);
  $('thrV').textContent = t('thrV', { p: Math.round(threshold * 100) });
  $('thrMark').style.left = (threshold * 100) + '%';
}

/* ── 그리기: AI 귀 (YAMNet 521개 점수와 1~3등 이름) ── */
function topOf(vec, n) {
  const idx = [];
  for (let i = 0; i < vec.length; i++) idx.push(i);
  idx.sort((a, b) => vec[b] - vec[a]);
  return idx.slice(0, n).map(i => ({ index: i, name: names ? names[i] : '#' + i, score: vec[i] }));
}
function paintEar(vec, top) {
  const top3 = (top && top.length && top[0].index != null ? top : topOf(vec, 3)).slice(0, 3);
  $('earNote').textContent = sel ? t('earSample') : t('earCap', { n: SOUND_DIM });
  drawStrip(vec, top3.map(x => x.index));
  $('top3').innerHTML = top3.map((x, k) => {
    const ko = labelOf(x.name, LANG), en = x.name;
    return '<div class="bar top3"><div class="bl"><span><b class="rank">' + (k + 1) + '</b>' + esc(ko) +
      (LANG === 'ko' && ko !== en ? ' <small>' + esc(en) + '</small>' : '') + '</span><span class="num">' + Math.round(x.score * 100) + '%</span></div>' +
      '<div class="bt"><div class="bf" style="width:' + (x.score * 100).toFixed(1) + '%"></div></div></div>';
  }).join('');
}
function paintEarIdle() {
  if (sel) return;
  $('earNote').textContent = earState === 'loading' ? t('earLoading') : earState === 'fail' ? t('earFail') : t('earOff');
  drawStrip(null, []);
  $('top3').innerHTML = '';
}
function drawStrip(vec, marks) {
  const c = $('strip'), dpr = window.devicePixelRatio || 1, W = c.clientWidth, H = c.clientHeight;
  if (!W || !H) return;
  c.width = W * dpr; c.height = H * dpr;
  const g = c.getContext('2d'); g.scale(dpr, dpr); g.clearRect(0, 0, W, H);
  const base = H - 14;
  g.fillStyle = '#ece5d6'; g.fillRect(0, base, W, 1);
  if (!vec) return;
  const bw = W / SOUND_DIM;
  g.fillStyle = css('--cyan') || '#1f5f7a';
  // 점수는 대부분 0 근처라 제곱근으로 펴서 보여 준다 — 학습에 쓰는 sqrt-L2 와 같은 생각
  for (let i = 0; i < SOUND_DIM; i++) {
    const h = Math.sqrt(Math.max(0, vec[i])) * (base - 4);
    if (h > 0.3) g.fillRect(i * bw, base - h, Math.max(1, bw), h);
  }
  g.fillStyle = css('--pen-red') || '#b4451c';
  g.font = '700 11px system-ui, sans-serif'; g.textAlign = 'center';
  marks.forEach((i, k) => {
    const h = Math.sqrt(Math.max(0, vec[i])) * (base - 4), x = i * bw;
    g.fillRect(x - 0.5, base - h, Math.max(2, bw + 1), h);
    g.fillText(String(k + 1), Math.min(W - 6, Math.max(6, x)), H - 2);
  });
}

function paintAll() {
  paintClasses(); paintTrain(); paintThr(); paintLive(); paintAnswer(null);
  if (eng.running && lastEar) paintEar(lastEar.vec, lastEar.top); else paintEarIdle();
}

function paintText() {
  document.title = t('title');
  $('txtTitle').textContent = t('app'); $('langButton').textContent = t('lang');
  $('txtQ1').textContent = t('q1'); $('txtQ2').textContent = t('q2'); $('txtQ3').textContent = t('q3');
  $('q1hint').textContent = t('q1hint');
  $('newBtn').innerHTML = IC.fresh + '<span>' + esc(t('newP')) + '</span>';
  $('expBtn').innerHTML = IC.save + '<span>' + esc(t('exportP')) + '</span>';
  $('impBtn').innerHTML = IC.open + '<span>' + esc(t('importP')) + '</span>';
  $('addCls').innerHTML = IC.plus + '<span>' + esc(t('addCls')) + '</span>';
  $('txtAcc').textContent = t('accLbl'); $('txtLoss').textContent = t('lossLbl');
  $('txtPer').textContent = t('perCls');
  $('tipsT').textContent = t('tipsT');
  $('tips').innerHTML = ['tip1', 'tip2', 'tip3'].map(k => '<li>' + esc(t(k)) + '</li>').join('');
  $('thrT').textContent = t('thr');
  $('earT').textContent = t('earT'); $('topT').textContent = t('topT'); $('topHint').textContent = t('topHint');
  if (window.navRepaint) window.navRepaint();
}

let toastTimer = null;
function toast(msg) {
  const el = $('toast');
  el.textContent = msg; el.classList.add('on');
  clearTimeout(toastTimer); toastTimer = setTimeout(() => el.classList.remove('on'), 2600);
}

/* ── 종류 더하기·지우기 ── */
function addClass(bg) {
  if (classes.length >= MAX_CLS || training) return;
  const used = new Set(classes.map(c => c.color));
  const color = (bg && !used.has(COLORS[0])) ? COLORS[0] : (COLORS.find(x => x !== COLORS[0] && !used.has(x)) || COLORS.find(x => !used.has(x)) || COLORS[0]);
  let n = classes.length + 1;
  while (classes.some(c => c.name === t('newName', { n }))) n++;
  const c = { id: nextId++, name: bg ? t('quiet') : t('newName', { n }), color, bg: !!bg, samples: [] };
  if (bg) classes.unshift(c); else classes.push(c);
  paintClasses(); paintTrain(); paintAnswer(null); save();
  const inp = document.querySelector('.cls[data-c="' + c.id + '"] .cname');
  if (inp && !bg) { inp.focus(); inp.select(); }
}
function delClass(id) {
  if (classes.length <= MIN_CLS) { toast(t('minCls')); return; }
  if (rec && rec.cid === id) endRec();
  classes = classes.filter(c => c.id !== id);
  if (sel && sel.cid === id) sel = null;
  paintClasses(); paintTrain(); paintAnswer(null); save();
}

/* ── 이벤트 ── */
const box = $('classes');
box.addEventListener('pointerdown', e => {
  const b = e.target.closest('.recb');
  if (!b || e.button !== 0 || b.disabled) return;
  e.preventDefault();
  try { b.setPointerCapture(e.pointerId); } catch (err) {}
  startRec(+b.closest('.cls').dataset.c);
});
['pointerup', 'pointercancel', 'lostpointercapture'].forEach(ev => box.addEventListener(ev, e => {
  if (e.target.closest && e.target.closest('.recb')) releaseRec();
}));
box.addEventListener('keydown', e => {
  const b = e.target.closest('.recb');
  if (!b || (e.key !== ' ' && e.key !== 'Enter')) return;
  e.preventDefault();
  if (!e.repeat) startRec(+b.closest('.cls').dataset.c);
});
box.addEventListener('keyup', e => {
  if (e.target.closest('.recb') && (e.key === ' ' || e.key === 'Enter')) releaseRec();
});
let delArm = null;
box.addEventListener('click', e => {
  const card = e.target.closest('.cls');
  if (!card) return;
  const c = byId(+card.dataset.c);
  if (!c) return;
  if (e.target.closest('.dot')) {
    const used = new Set(classes.filter(x => x !== c).map(x => x.color));
    let k = COLORS.indexOf(c.color);
    for (let n = 0; n < COLORS.length; n++) { k = (k + 1) % COLORS.length; if (!used.has(COLORS[k])) break; }
    c.color = COLORS[k];
    card.style.setProperty('--c', c.color);
    card.querySelector('.smps').replaceChildren(...(c.samples.length ? c.samples.map((s, i) => thumbEl(c, i)) : []));
    if (!c.samples.length) card.querySelector('.smps').innerHTML = '<span class="empty hint">' + esc(t('empty')) + '</span>';
    paintSel(); paintTrain(); paintAnswer(null); save();
    return;
  }
  const del = e.target.closest('.del');
  if (del) {
    // 두 번 눌러 지운다 — 예시를 한가득 모은 종류가 한 번 실수로 사라지지 않게
    if (!c.samples.length || delArm === del) { delArm = null; delClass(c.id); return; }
    delArm = del; del.classList.add('armed'); del.title = t('delSure'); toast(t('delSure'));
    setTimeout(() => { if (delArm === del) { delArm = null; del.classList.remove('armed'); del.title = t('delCls'); } }, 3000);
    return;
  }
  const sx = e.target.closest('.sx'), smp = e.target.closest('.smp');
  if (smp) {
    const i = +smp.dataset.i;
    if (sx && sel && sel.cid === c.id && sel.i === i) {
      c.samples.splice(i, 1); sel = null;
      const strip = card.querySelector('.smps');
      strip.replaceChildren(...c.samples.map((s, k) => thumbEl(c, k)));
      if (!c.samples.length) strip.innerHTML = '<span class="empty hint">' + esc(t('empty')) + '</span>';
      paintCount(c); paintTrain(); save();
      if (!eng.running) paintEarIdle();
      return;
    }
    // 고른 예시를 AI 가 어떻게 들었는지 보여 준다 (마이크가 켜져 있으면 다음 조각이 덮어쓴다)
    sel = { cid: c.id, i }; paintSel();
    paintEar(c.samples[i].vec, null);
    paintAnswer(c.samples[i].vec);
  }
});
box.addEventListener('input', e => {
  const inp = e.target.closest('.cname');
  if (!inp) return;
  const c = byId(+inp.closest('.cls').dataset.c);
  c.name = inp.value.trim();
  paintTrain(); paintAnswer(null); save();
});
box.addEventListener('keydown', e => { if (e.target.closest('.cname') && e.key === 'Enter') e.target.blur(); });

$('addCls').addEventListener('click', () => addClass(false));
$('trainBtn').addEventListener('click', () => { train(); });
$('liveBtn').addEventListener('click', () => {
  live = !live;
  if (!live) lastEar = null;
  syncMic(); paintLive(); paintAnswer(null);
  if (live && window.vapiStat) vapiStat('sound_live');
});
$('thr').addEventListener('input', e => {
  threshold = +e.target.value / 100; paintThr();
  if (lastEar && eng.running) paintAnswer(lastEar.vec);
  save();
});
let newArm = false;
$('newBtn').addEventListener('click', () => {
  if (total() && !newArm) {
    newArm = true; $('newBtn').classList.add('armed'); toast(t('newSure'));
    setTimeout(() => { newArm = false; $('newBtn').classList.remove('armed'); }, 3000);
    return;
  }
  newArm = false; $('newBtn').classList.remove('armed');
  stopAll(); defaults(); paintAll(); save(); toast(t('newDone'));
});
$('expBtn').addEventListener('click', exportFile);
$('impBtn').addEventListener('click', () => $('impFile').click());
$('impFile').addEventListener('change', e => {
  const f = e.target.files && e.target.files[0];
  e.target.value = '';
  if (f) f.text().then(importText);
});
new ResizeObserver(() => {
  drawChart();
  if (sel) { const c = byId(sel.cid); if (c && c.samples[sel.i]) drawStrip(c.samples[sel.i].vec, topOf(c.samples[sel.i].vec, 3).map(x => x.index)); }
  else if (eng.running && lastEar) drawStrip(lastEar.vec, lastEar.top.slice(0, 3).map(x => x.index));
}).observe(document.body);

/* 가려지면 마이크를 닫는다 — 셸에 "마이크 사용 중" 이 남지 않게. 해 보기를 켜 둔 채였으면 돌아올 때 다시 켠다.
   배우기는 계속한다 — 끝나면 알림으로 알린다 */
if (window.EL_WIN) {
  EL_WIN.onHide(() => { liveWasOn = live; rec = null; live = false; syncMic(); paintRec(); paintLive(); });
  EL_WIN.onShow(() => { if (liveWasOn) { liveWasOn = false; live = true; syncMic(); paintLive(); } });
}
window.addEventListener('pagehide', () => { if (saveTimer) saveNow(); });

$('langButton').addEventListener('click', () => {
  try { localStorage.setItem('vapiLang', LANG === 'ko' ? 'en' : 'ko'); } catch (e) {}
  location.reload();
});

/* ── 시작 ── */
defaults();
paintText(); paintAll();
const restored = loadSaved().then(s => { if (restore(s)) paintAll(); });
// AI 귀는 화면이 뜬 뒤에 불러 둔다 (wasm 6MB + 모델 4MB, 전부 이 컴퓨터의 /lib/sound/ 에서)
const earReady = new Promise(r => setTimeout(r, 0)).then(() => preloadSound()).then(() => labelNames()).then(n => {
  names = n; earState = 'ready'; if (!eng.running) paintEarIdle(); return true;
}).catch(e => { console.error(e); earState = 'fail'; paintEarIdle(); return false; });

/* ── 자동 시험용 — 마이크 없이도 모으기·배우기·해 보기를 돌릴 수 있게 ── */
function asVec(v) { const a = new Float32Array(SOUND_DIM); for (let i = 0; i < SOUND_DIM && i < v.length; i++) a[i] = +v[i] || 0; return a; }
window.EL_SOUND = {
  restored, earReady,
  get state() {
    return { classes: classes.map(c => ({ id: c.id, name: c.name, color: c.color, bg: !!c.bg, count: c.samples.length })),
             trained: !!model, fits: modelFits(), acc: model ? model.acc : null, ms: model ? model.ms : null,
             training, live, recording: !!rec, micOn: eng.running, earState, threshold };
  },
  names: () => names,
  // 가짜 예시 넣기 — vecs 는 YAMNet 날것 점수 521개짜리 배열들
  addSamples(ci, vecs, wave) {
    const c = classes[ci]; if (!c) return 0;
    vecs.forEach(v => { if (c.samples.length < MAX_PER_CLASS) addSample(c, asVec(v), wave || null); });
    return c.samples.length;
  },
  train,
  // 가짜 소리 한 조각 — 마이크 틱과 같은 길로 (귀 그림·대답 모두)
  feed(v) {
    const vec = asVec(v);
    lastEar = { vec, top: topOf(vec, 8), level: 0, wave: new Float32Array(WAVE_BINS) };
    paintEar(vec, lastEar.top);
    return paintAnswer(vec);
  },
  predict: v => (modelFits() ? Array.from(predict(clf, applySoundTransform(asVec(v), SOUND_TRANSFORM))) : null),
  flush: saveNow,
  engine: eng,
};
