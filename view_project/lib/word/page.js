// 문장 — 화면 로직 (word.html)
// themakerrobot/ml-lab acts/word/page.js (커밋 e17acd7) 의 흐름을 이 저장소 화면(패널·토큰·I18N)에 맞게 다시 짰다.
// 계산은 전부 worker.js 에서 한다. 여기서는 화면만 다룬다.
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

// 흐름: 글 넣기 → 배우기(워커) → 이어 쓰기 → 들여다보기 / 맞히기 대결

import { PRESETS } from './presets.js';

let LANG = 'ko';
try { LANG = localStorage.getItem('vapiLang') === 'en' ? 'en' : 'ko'; } catch (e) {}
document.documentElement.lang = LANG;

const I18N = {
  ko: {
    title: 'edge-lab — 문장', app: '문장', lang: 'EN',
    q1: '가르칠 글', q2: '이어 쓰기', q3: '들여다보기',
    s1: '① 글 넣기', s2: '② 배우기', s3: '③ 이어 쓰기', s4: '④ 들여다보기',
    examples: '예시 글', corpusPh: '여기에 글을 써요. 줄마다 한 문장씩!',
    letters: '글자', kinds: '글자 종류', cut: '앞쪽 5000글자만 배워요', tooShort: '글이 너무 짧아요. 조금 더 써 주세요',
    pick: 'AI 고르기', mlp: '작은 신경망', mlpSub: '앞 몇 글자만 봐요', gpt: 'Transformer', gptSub: '앞 글을 다 봐요',
    ctx: '앞을 몇 글자 볼까요?',
    train: '배우기 시작', more: '더 배우기', stop: '멈추기',
    notYet: '아직 안 배웠어요', learning: '배우는 중', learningMore: '더 배우는 중', learned: '다 배웠어요',
    stopped: '멈췄어요. 지금까지 배운 걸로 해 봐요', failed: '배우다가 멈췄어요. 다시 해 보세요',
    loss: '틀린 정도 (낮을수록 잘 맞혀요)', params: 'AI 속 숫자', practice: '연습 {n}번 · {s}초',
    engine: '인터넷 없이 이 컴퓨터에서 배워요', loadFail: '불러오지 못했어요. 새로고침해 주세요',
    seed: '시작 글자', seedPh: '예: 강아지는', step: '한 글자', stepTip: '한 글자만 이어 쓰기', gen: '이어 쓰기',
    temp: '온도 — 높을수록 엉뚱해요', outIdle: '배운 뒤에 이어 쓸 수 있어요',
    madeWord: '밑줄', madeNote: '= 가르친 글에 없는 문장이에요. AI가 지어냈어요.',
    probs: '다음 글자 후보', afterTrain: '배운 뒤에 보여요', unknown: '배운 적 없는 글자예요', ends: '여기서 문장이 끝났대요',
    hist: '지금까지 쓴 글', histNone: '이어 쓰기를 누르면 여기에 모여요. 온도나 AI를 바꿔 가며 비교해 봐요.',
    tagMlp: '작은 신경망 · 앞 {n}글자', tagGpt: 'Transformer', tagTemp: '온도 {t}',
    lookIdle: '배운 뒤에 AI가 어느 글자를 보는지 나와요', sees: 'AI가 보는 글자',
    mlpHint1: '작은 신경망은 바로 앞 글자 몇 개만 봐요.', mlpHint2: '· 는 줄 앞의 빈칸이에요.', mlpHint3: '더 앞의 글자는 몰라요.',
    head: '{l}층 · 눈{h}', attHint1: '줄마다 그 글자가 앞의 어느 글자를 봤는지예요.', attHint2: '진할수록 많이 봤어요.',
    attBest: '가장 많이 본 글자: {a} → {b}',
    duel: '맞히기 대결 — 나 vs AI', duelIdle: '문제를 내 볼까요?', duelPh: '다음 글자', duelGo: '내기', duelNew: '새 문제',
    me: '나', ai: 'AI', duelAsk: '다음 글자를 써 보세요', duelOne: '한 글자를 써 주세요', answer: '정답',
  },
  en: {
    title: 'edge-lab — Words', app: 'Words', lang: '한',
    q1: 'Text to teach', q2: 'Write on', q3: 'Look inside',
    s1: '① Add text', s2: '② Teach', s3: '③ Write on', s4: '④ Look inside',
    examples: 'Examples', corpusPh: 'Write here. One sentence per line!',
    letters: 'Letters', kinds: 'Kinds of letters', cut: 'Only the first 5000 letters are used', tooShort: 'Too short. Please write a bit more',
    pick: 'Pick an AI', mlp: 'Small neural net', mlpSub: 'Sees a few letters back', gpt: 'Transformer', gptSub: 'Sees everything before',
    ctx: 'How many letters back?',
    train: 'Start teaching', more: 'Teach more', stop: 'Stop',
    notYet: 'Not taught yet', learning: 'Learning', learningMore: 'Learning more', learned: 'All done learning',
    stopped: 'Stopped. Try what it learned so far', failed: 'Learning stopped. Please try again',
    loss: 'Mistakes (lower is better)', params: 'Numbers inside the AI', practice: 'Practice {n} · {s}s',
    engine: 'Learns on this computer, no internet', loadFail: 'Could not load. Please refresh',
    seed: 'Start with', seedPh: 'e.g. The dog', step: 'One letter', stepTip: 'Write just one letter', gen: 'Write on',
    temp: 'Temperature — higher is wilder', outIdle: 'Teach it first, then it can write',
    madeWord: 'Underlined', madeNote: '= not in your text. The AI made it up.',
    probs: 'Next letter guesses', afterTrain: 'Shows up after teaching', unknown: 'Never learned these letters', ends: 'The AI says the sentence ends here',
    hist: 'Written so far', histNone: 'Each "Write on" lands here. Change the temperature or the AI and compare.',
    tagMlp: 'Small net · {n} back', tagGpt: 'Transformer', tagTemp: 'temp {t}',
    lookIdle: 'After teaching, see which letters the AI looks at', sees: 'Letters the AI sees',
    mlpHint1: 'The small net only sees a few letters back.', mlpHint2: '· is empty space before the line.', mlpHint3: 'It can’t see further back.',
    head: 'Layer {l} · Eye {h}', attHint1: 'Each row shows which earlier letters that letter looked at.', attHint2: 'Darker means it looked more.',
    attBest: 'Looked at most: {a} → {b}',
    duel: 'Guessing game — you vs AI', duelIdle: 'Ready for a question?', duelPh: 'Next letter', duelGo: 'Go', duelNew: 'New question',
    me: 'Me', ai: 'AI', duelAsk: 'Write the next letter', duelOne: 'Please write one letter', answer: 'Answer',
  },
};
const t = k => (I18N[LANG][k] !== undefined ? I18N[LANG][k] : I18N.ko[k]);
const $ = id => document.getElementById(id);

const IC = {
  learn: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"><path d="M12 4 22 8.6 12 13.2 2 8.6 12 4Z"/><path d="M6 10.6v4.9c0 1.7 2.7 3.1 6 3.1s6-1.4 6-3.1v-4.9"/></svg>',
  more: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 12a8 8 0 1 1-2.3-5.7"/><path d="M20 4v5h-5"/></svg>',
  stop: '<svg viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="6" width="12" height="12" rx="2"/></svg>',
  play: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M7 4.5v15l12.5-7.5Z"/></svg>',
  step: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M5 5v14l10-7Z"/><rect x="16" y="5" width="3" height="14" rx="1"/></svg>',
  shuffle: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 7h3.5c4.5 0 6.5 10 11 10H21M3 17h3.5c1.6 0 2.8-1.3 3.9-3M14 9.5c.9-1.4 2-2.5 3.5-2.5H21M18 4l3 3-3 3M18 14l3 3-3 3"/></svg>',
  // 작은 신경망 = 점과 선 몇 개, Transformer = 서로 다 이어진 점들
  mlp: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="5" cy="7" r="2"/><circle cx="5" cy="17" r="2"/><circle cx="12" cy="12" r="2"/><circle cx="19" cy="12" r="2"/><path d="M7 7.8l3.2 3M7 16.2l3.2-3M14 12h3"/></svg>',
  gpt: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="4" cy="18" r="1.8"/><circle cx="9.3" cy="18" r="1.8"/><circle cx="14.7" cy="18" r="1.8"/><circle cx="20" cy="18" r="1.8"/><path d="M20 16c-2-8-12-8-16 0M20 16c-1.5-5-8.5-5-10.7 0M20 16c-1-2.6-4-2.6-5.3 0"/></svg>',
  user: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="8" r="4"/><path d="M4.5 20c.8-4 3.8-6 7.5-6s6.7 2 7.5 6"/></svg>',
  robot: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"><rect x="4" y="8" width="16" height="12" rx="3"/><path d="M12 4v4M9 13h.01M15 13h.01M9.5 17h5" stroke-linecap="round"/></svg>',
};

const MAX_CHARS = 5000;                      // 저사양 PC 에서 한 수업 안에 끝나는 크기 (ml-lab 그대로)
const STEPS = { mlp: 1500, gpt: 400 };       // 한 번 "배우기"에 하는 연습 횟수 (ml-lab 그대로)
let steps = { ...STEPS };                    // 자동 시험만 EL_WORD.setSteps 로 줄인다 — 수업 값은 위 STEPS
const HIST_MAX = 8;

// ── 워커 RPC ────────────────────────────────────────────────
const worker = new Worker('/lib/word/worker.js', { type: 'module' });
let seq = 0;
const pending = new Map();
function call(type, body = {}) {
  return new Promise((resolve, reject) => {
    const id = ++seq;
    pending.set(id, { resolve, reject });
    worker.postMessage({ id, type, ...body });
  });
}
worker.onmessage = ({ data: m }) => {
  if (m.id) {
    const p = pending.get(m.id); pending.delete(m.id);
    if (p) m.ok ? p.resolve(m) : p.reject(new Error(m.error));
  } else if (m.type === 'progress') onProgress(m);
  else if (m.type === 'done') onDone(m);
};
// 모듈 워커를 못 띄우면(서버가 .js 를 자바스크립트로 알려 주지 않는 등) 여기로 온다
worker.onerror = e => { toast(t('loadFail')); console.error(e); };

// ── 상태 ────────────────────────────────────────────────────
let kind = 'mlp';
let trained = null;          // { kind, corpus, ctx } — 배운 모델의 정보
let training = false;
let losses = [];             // [step, loss]
let lastTarget = 0;
let duel = null;
const score = { me: 0, ai: 0 };
let step = 1;
let infoBase = '';           // "글자 종류 · AI 속 숫자" — 연습 횟수는 끝날 때마다 바꿔 쓴다
const hist = [];             // 이어 쓴 글 기록 [{ tag, html }]

// ── 공통 도우미 ─────────────────────────────────────────────
let toastTimer = 0;
function toast(msg) {
  const el = $('toast'); el.textContent = msg; el.classList.add('on');
  clearTimeout(toastTimer); toastTimer = setTimeout(() => el.classList.remove('on'), 2200);
}
const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const shown = ch => ch === '\n' ? '↵' : ch === ' ' ? '␣' : ch;
const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const hintBox = k => `<div class="hint">${esc(t(k))}</div>`;

function setStep(n) {
  step = n;
  [...$('steps').children].forEach(el => {
    const s = +el.dataset.s;
    el.classList.toggle('on', s === n); el.classList.toggle('done', s < n);
  });
}

// ── 글자 칠하기 ─────────────────────────────────────────────
function paintText() {
  document.title = t('title'); $('langButton').textContent = t('lang');
  $('txtQ1').textContent = t('q1'); $('txtQ2').textContent = t('q2'); $('txtQ3').textContent = t('q3');
  [...$('steps').children].forEach(el => { el.textContent = t('s' + el.dataset.s); });
  $('txtExamples').textContent = t('examples'); $('corpus').placeholder = t('corpusPh');
  $('txtPick').textContent = t('pick'); $('txtCtx').textContent = t('ctx');
  const [bm, bg] = $('modelPick').children;
  bm.innerHTML = `<span class="nm">${IC.mlp}${esc(t('mlp'))}</span><small>${esc(t('mlpSub'))}</small>`;
  bg.innerHTML = `<span class="nm">${IC.gpt}${esc(t('gpt'))}</span><small>${esc(t('gptSub'))}</small>`;
  $('trainBtn').innerHTML = `${IC.learn} ${esc(t('train'))}`;
  $('moreBtn').innerHTML = `${IC.more} ${esc(t('more'))}`;
  $('stopBtn').innerHTML = `${IC.stop} ${esc(t('stop'))}`;
  $('prgLabel').textContent = t('notYet');
  $('trainInfo').textContent = t('engine');     // 배우기 전에는 "인터넷 없이" 안내 자리
  $('txtSeed').textContent = t('seed'); $('seed').placeholder = t('seedPh');
  $('stepBtn').innerHTML = `${IC.step} ${esc(t('step'))}`; $('stepBtn').title = t('stepTip');
  $('genBtn').innerHTML = `${IC.play} ${esc(t('gen'))}`;
  $('txtTemp').textContent = t('temp');
  $('madeNote').innerHTML = `<span class="made">${esc(t('madeWord'))}</span> ${esc(t('madeNote'))}`;
  $('txtProbs').textContent = t('probs'); $('txtHist').textContent = t('hist');
  $('txtDuel').textContent = t('duel'); $('duelQ').textContent = t('duelIdle');
  $('duelIn').placeholder = t('duelPh');
  $('duelGo').textContent = t('duelGo');
  $('duelNew').innerHTML = `${IC.shuffle} ${esc(t('duelNew'))}`;
  $('score').innerHTML = `<span>${IC.user} ${esc(t('me'))} <b class="num" id="scoreMe">0</b></span>` +
                         `<span>${IC.robot} ${esc(t('ai'))} <b class="num" id="scoreAi">0</b></span>`;
  if (window.navRepaint) window.navRepaint();
}

// ── 1. 글 넣기 ──────────────────────────────────────────────
const presets = PRESETS[LANG] || PRESETS.ko;
function paintPresets() {
  $('presetRow').innerHTML = presets.map((p, i) => `<button class="btn" type="button" data-i="${i}">${esc(p.label)}</button>`).join('');
}
function usePreset(i) {
  $('corpus').value = presets[i].text;
  $('seed').value = presets[i].seed;
  [...$('presetRow').children].forEach((b, j) => b.classList.toggle('on', j === i));
  corpusInfo();
}
function corpusInfo() {
  const txt = $('corpus').value, n = Array.from(txt).length;
  const kinds = new Set(Array.from(txt.replace(/\n/g, ''))).size;
  $('corpusInfo').textContent = `${t('letters')} ${n.toLocaleString()} · ${t('kinds')} ${kinds}` + (n > MAX_CHARS ? ` — ${t('cut')}` : '');
}
$('presetRow').addEventListener('click', e => {
  const b = e.target.closest('[data-i]'); if (b && !training) usePreset(+b.dataset.i);
});
$('corpus').addEventListener('input', () => {
  [...$('presetRow').children].forEach(b => b.classList.remove('on'));
  corpusInfo();
});

// AI 고르기
function pickKind(k) {
  if (training) return;
  kind = k;
  [...$('modelPick').children].forEach(o => o.classList.toggle('on', o.dataset.kind === k));
  $('ctxRow').hidden = k !== 'mlp';
}
$('modelPick').addEventListener('click', e => {
  const b = e.target.closest('[data-kind]'); if (b) pickKind(b.dataset.kind);
});
$('ctx').addEventListener('input', () => { $('ctxVal').textContent = $('ctx').value; });

// ── 2. 배우기 ───────────────────────────────────────────────
function setTraining(on) {
  training = on;
  $('trainBtn').disabled = on;
  $('stopBtn').disabled = !on;
  $('moreBtn').disabled = on || !trained;
  [...$('modelPick').children].forEach(o => { o.disabled = on; });
  $('ctx').disabled = on;
  $('corpus').disabled = on;
  [...$('presetRow').children].forEach(b => { b.disabled = on; });
}

$('trainBtn').addEventListener('click', async () => {
  let text = $('corpus').value.trim();
  if (Array.from(text).length > MAX_CHARS) text = Array.from(text).slice(0, MAX_CHARS).join('');
  const lines = text.split('\n').filter(l => l.trim());
  if (Array.from(text).length < 20 || !lines.length) { toast(t('tooShort')); return; }

  losses = []; drawChart();
  trained = null; resetOutputs();
  setTraining(true); setStep(2);
  $('prgLabel').textContent = t('learning');
  $('prgFill').style.width = '0%'; $('prgPct').textContent = '0%';
  $('trainInfo').textContent = '';
  const ctx = +$('ctx').value;
  try {
    const info = await call('train', { kind, text, ctx, steps: steps[kind] });
    lastTarget = steps[kind];
    trained = { kind, corpus: text, ctx: info.ctx };
    infoBase = `${t('kinds')} ${info.vocab} · ${t('params')} ${info.params.toLocaleString()}`;
    $('trainInfo').textContent = infoBase;
    if (window.vapiStat) vapiStat('word_train');
  } catch (e) {
    console.error(e);
    setTraining(false); toast(t('failed'));
  }
});

$('moreBtn').addEventListener('click', async () => {
  if (!trained || training) return;
  setTraining(true);
  $('prgLabel').textContent = t('learningMore');
  lastTarget = steps[trained.kind];
  await call('more', { steps: steps[trained.kind] });
  if (window.vapiStat) vapiStat('word_more');
});

$('stopBtn').addEventListener('click', () => call('stop'));

function onProgress(m) {
  losses.push([m.step, m.loss]);
  const done = m.step - (m.target - lastTarget);
  const pct = Math.max(0, Math.min(100, Math.round(done / lastTarget * 100)));
  $('prgFill').style.width = pct + '%';
  $('prgPct').textContent = pct + '%';
  drawChart();
}

function onDone(m) {
  setTraining(false);
  $('prgFill').style.width = '100%';
  $('prgPct').textContent = '';
  $('prgLabel').textContent = m.stopped ? t('stopped') : t('learned');
  // 연습 횟수는 모두 합친 것, 초는 이번에 배운 시간
  $('trainInfo').textContent = infoBase + ' · ' + t('practice').replace('{n}', m.step.toLocaleString()).replace('{s}', m.sec.toFixed(1));
  ['genBtn', 'stepBtn', 'duelNew'].forEach(id => { $(id).disabled = false; });
  setStep(3);
  refresh();
  newDuel();
  // 워커에서 배우므로 창이 가려져도 계속 배운다. 다 배우면 알려 준다
  if (window.EL_WIN && EL_WIN.hidden) {
    EL_WIN.notify(`${t('app')} · ${m.stopped ? t('stopped') : t('learned')}`, { actions: [{ label: t('app'), href: '/word' }] });
  }
}

// 학습 곡선 — 자동차 가르치기와 같이 "틀린 정도"는 빨간펜 색
function drawChart() {
  const c = $('chart'), dpr = window.devicePixelRatio || 1;
  const W = c.clientWidth, H = c.clientHeight;
  if (!W || !H) return;                       // 가려진 창 — 다시 보일 때 resize 로 다시 그린다
  c.width = W * dpr; c.height = H * dpr;
  const g = c.getContext('2d'); g.scale(dpr, dpr);
  g.clearRect(0, 0, W, H);
  // 범례는 캔버스 오른쪽 위 줄에 쓴다
  g.font = '13px "Gowun Dodum", sans-serif'; g.textAlign = 'right'; g.textBaseline = 'top';
  g.fillStyle = css('--ink-2') || '#4a423a'; g.fillText(t('loss'), W - 8, 6);
  g.fillStyle = css('--pen-red') || '#b4451c'; g.fillRect(W - 14 - g.measureText(t('loss')).width - 18, 13, 14, 3);
  if (losses.length < 2) return;
  const maxS = losses[losses.length - 1][0], maxL = Math.max(...losses.map(l => l[1]));
  g.strokeStyle = css('--pen-red') || '#b4451c';
  g.lineWidth = 2; g.beginPath();
  const top = 24;                             // 범례 줄 아래부터 그린다 — 곡선과 글자가 겹치지 않게
  losses.forEach(([s, l], i) => {
    const x = 6 + s / maxS * (W - 12), y = H - 6 - l / maxL * (H - 6 - top);
    i ? g.lineTo(x, y) : g.moveTo(x, y);
  });
  g.stroke();
}
window.addEventListener('resize', drawChart);
if (document.fonts) document.fonts.ready.then(drawChart);   // 범례 글꼴이 늦게 오면 다시 그린다

// ── 3. 이어 쓰기 ────────────────────────────────────────────
function resetOutputs() {
  stopReveal();
  $('out').className = 'answer idk';
  $('out').textContent = t('outIdle');
  $('madeNote').hidden = true;
  $('probs').innerHTML = hintBox('afterTrain');
  $('look').innerHTML = hintBox('lookIdle');
  $('unkNote').hidden = true;
  ['genBtn', 'stepBtn', 'duelNew', 'duelGo'].forEach(id => { $(id).disabled = true; });
  $('duelIn').disabled = true;
  $('duelQ').textContent = t('duelIdle'); $('duelMsg').textContent = '';
  duel = null;
}

$('temp').addEventListener('input', () => { $('tempVal').textContent = (+$('temp').value).toFixed(1); });

// 문장 단위로 잘라서, 가르친 글에 없는 문장에 밑줄을 친다 (환각 보기)
// 반환: 밑줄 칠 [시작, 끝) 범위들 (full 의 글자 위치)
function madeRanges(full, seedLen) {
  const corpus = trained.corpus.replace(/\s+/g, ' ');
  const out = [], re = /[^.!?\n]+[.!?]*/g;
  let m;
  while ((m = re.exec(full))) {
    const s = m[0].trim().replace(/\s+/g, ' ');
    const end = m.index + m[0].length;
    // 끝나지 않은 마지막 조각도 따진다. 사용자가 쓴 부분 안에서 끝나는 조각은 뺀다
    if (end > seedLen && s.length > 1 && !corpus.includes(s)) out.push([Math.max(m.index, seedLen), end]);
  }
  return out;
}

// 글자마다 [사용자 글 / 지어낸 문장 / 이어 쓴 글] 표시가 같은 것끼리 묶는다
function segments(full, seedLen, made) {
  const inMade = i => made.some(([a, b]) => i >= a && i < b);
  const segs = [];
  for (let i = 0; i < full.length; i++) {
    const c = i < seedLen ? 'seed' : inMade(i) ? 'made' : 'gen';
    if (segs.length && segs[segs.length - 1].c === c) segs[segs.length - 1].s += full[i];
    else segs.push({ c, s: full[i] });
  }
  return segs;
}
// 앞에서 n 글자까지만 그린다 (한 글자씩 써 나가는 모습)
function segHtml(segs, n = Infinity) {
  let html = '', left = n;
  for (const { c, s } of segs) {
    if (left <= 0) break;
    const part = s.slice(0, left); left -= part.length;
    html += c === 'seed' ? `<span class="seedtxt">${esc(part)}</span>` : c === 'made' ? `<span class="made">${esc(part)}</span>` : esc(part);
  }
  return html;
}

// 이어 쓴 글이 한 글자씩 나타난다. 창이 가려지거나 다시 누르면 바로 끝까지 보여 준다
let reveal = null;
function stopReveal() {
  if (!reveal) return;
  clearInterval(reveal.timer);
  const r = reveal; reveal = null;
  r.finish();
}
function showOut(segs, seedLen, total, finish) {
  stopReveal();
  $('out').className = 'answer';
  const reduce = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (reduce || total <= seedLen) { $('out').innerHTML = segHtml(segs); finish(); return; }
  let n = seedLen;
  $('out').innerHTML = segHtml(segs, n);
  reveal = {
    finish: () => { $('out').innerHTML = segHtml(segs); finish(); },
    timer: setInterval(() => {
      n += 1;
      $('out').innerHTML = segHtml(segs, n);
      if (n >= total) stopReveal();
    }, 45),
  };
}

$('genBtn').addEventListener('click', async () => {
  if (!trained || training) return;
  const seed = $('seed').value, temp = +$('temp').value;
  const r = await call('generate', { seed, temp });
  const full = seed + r.text;
  const made = madeRanges(full, seed.length);
  const segs = segments(full, seed.length, made);
  const tag = (trained.kind === 'mlp' ? t('tagMlp').replace('{n}', trained.ctx) : t('tagGpt')) +
              ' · ' + t('tagTemp').replace('{t}', temp.toFixed(1));
  $('madeNote').hidden = true;
  showOut(segs, seed.length, full.length, () => {
    $('madeNote').hidden = !made.length;
    hist.unshift({ tag, html: segHtml(segs) || esc(full) });
    hist.length = Math.min(hist.length, HIST_MAX);
    paintHist();
  });
  setStep(4);
  if (window.vapiStat) vapiStat('word_write');
});

function paintHist() {
  $('hist').innerHTML = hist.length
    ? hist.map(h => `<div class="hi"><small>${esc(h.tag)}</small><div>${h.html}</div></div>`).join('')
    : hintBox('histNone');
}

$('stepBtn').addEventListener('click', async () => {
  if (!trained || training) return;
  const seed = $('seed').value;
  const r = await call('step', { seed, temp: +$('temp').value });
  if (r.ch === '\n') { toast(t('ends')); return; }
  $('seed').value = seed + r.ch;
  refresh();
});

let refreshTimer = 0;
$('seed').addEventListener('input', () => {
  clearTimeout(refreshTimer); refreshTimer = setTimeout(refresh, 150);
});
$('seed').addEventListener('keydown', e => { if (e.key === 'Enter' && !e.isComposing && !$('genBtn').disabled) $('genBtn').click(); });

async function refresh() {
  if (!trained || training) return;
  const seed = $('seed').value;
  const [p, l] = await Promise.all([call('probs', { prefix: seed, k: 5 }), call('look', { text: seed })]);
  $('probs').innerHTML = p.top.map(([ch, v], i) => `
    <div class="bar${i === 0 ? ' top' : ''}">
      <div class="bl"><span class="ch">${esc(shown(ch))}</span><span class="num">${(v * 100).toFixed(1)}%</span></div>
      <div class="bt"><div class="bf" style="width:${(v * 100).toFixed(1)}%"></div></div>
    </div>`).join('');
  if (p.unknown.length) {
    $('unkNote').hidden = false;
    $('unkNote').textContent = `${t('unknown')}: ${p.unknown.join(' ')}`;
  } else $('unkNote').hidden = true;
  drawLook(l);
}

// ── 4. 들여다보기 ───────────────────────────────────────────
let lookLayer = 0, lookHead = 0, lastLook = null;

function drawLook(l) {
  lastLook = l;
  if (l.kind === 'mlp') {
    $('look').innerHTML = `
      <div class="st">${esc(t('sees'))}</div>
      <div class="chips">${l.window.map(ch => `<span class="chip on">${esc(shown(ch))}</span>`).join('')}<span class="chip next">?</span></div>
      <div class="hint">${esc(t('mlpHint1'))}<br>${esc(t('mlpHint2'))} ${esc(t('mlpHint3'))}</div>`;
    return;
  }
  const { chars, A } = l;
  if (lookLayer >= A.length) lookLayer = 0;
  if (lookHead >= A[lookLayer].length) lookHead = 0;
  const tabs = [];
  A.forEach((heads, li) => heads.forEach((_, hi) => tabs.push([li, hi])));
  const M = A[lookLayer][lookHead], last = M.length - 1;
  const head = `<tr><th></th>${chars.map(c => `<th>${esc(shown(c))}</th>`).join('')}</tr>`;
  const rows = M.map((row, r) => `<tr class="${r === last ? 'last' : ''}"><th>${esc(shown(chars[r]))}</th>${row.map((v, s) =>
    s <= r ? `<td title="${(v * 100).toFixed(0)}%"><i style="opacity:${v.toFixed(3)}"></i></td>` : '<td class="off"></td>').join('')}</tr>`).join('');
  // 마지막 글자가 가장 많이 본 글자
  const best = M[last].indexOf(Math.max(...M[last]));
  // 칸 크기: 머리 칸까지 (글자 수 + 1)칸이 패널 폭에 들어가게. 15~30px
  const avail = $('look').clientWidth || 280;
  const cell = Math.max(15, Math.min(30, Math.floor(avail / (chars.length + 1)) - 2));
  $('look').innerHTML = `
    <div class="tabs" id="headTabs">${tabs.map(([li, hi]) =>
      `<button type="button" data-l="${li}" data-h="${hi}" class="${li === lookLayer && hi === lookHead ? 'on' : ''}">${esc(t('head').replace('{l}', li + 1).replace('{h}', hi + 1))}</button>`).join('')}</div>
    <div class="att-wrap"><table class="att" style="--cell:${cell}px">${head}${rows}</table></div>
    <div class="hint">${esc(t('attHint1'))} ${esc(t('attHint2'))}<br>
      ${esc(t('attBest')).replace('{a}', `<b>${esc(shown(chars[last]))}</b>`).replace('{b}', `<b>${esc(shown(chars[best]))}</b>`)}
      (${(M[last][best] * 100).toFixed(0)}%)</div>`;
}
$('look').addEventListener('click', e => {
  const b = e.target.closest('[data-l]'); if (!b || !lastLook) return;
  lookLayer = +b.dataset.l; lookHead = +b.dataset.h; drawLook(lastLook);
});

// ── 맞히기 대결 ────────────────────────────────────────────
// 문제는 지금 문장만 보여 준다 (앞 문장은 … 로). AI에게는 줄 처음부터 준다
function duelShown(prefix) {
  const cut = Math.max(prefix.lastIndexOf('. '), prefix.lastIndexOf('? '), prefix.lastIndexOf('! '));
  return cut >= 0 ? '… ' + prefix.slice(cut + 2) : prefix;
}

function newDuel() {
  if (!trained) return;
  const lines = trained.corpus.split('\n').map(s => s.trim()).filter(s => Array.from(s).length >= 4);
  if (!lines.length) return;
  const line = Array.from(lines[(Math.random() * lines.length) | 0]);
  // 답이 될 자리: 빈칸·문장부호·기호(× =)가 아니고, 지금 문장 안에서 앞에 2글자 이상 있는 곳
  const cand = [];
  let sentStart = 0;
  for (let i = 0; i < line.length; i++) {
    if (i > 0 && /[.!?]/.test(line[i - 1])) sentStart = i + (line[i] === ' ' ? 1 : 0);
    const lone = line[i - 1] === ' ' && line[i + 1] === ' ';    // 영어 구구단의 x 같은 홀로 선 기호
    if (i - sentStart >= 2 && !lone && !/[\s.!?,×=]/.test(line[i])) cand.push(i);
  }
  const k = cand.length ? cand[(Math.random() * cand.length) | 0] : line.length - 1;
  duel = { prefix: line.slice(0, k).join(''), answer: line[k] };
  $('duelQ').innerHTML = `${esc(duelShown(duel.prefix))}<span class="blank">?</span>`;
  $('duelIn').value = ''; $('duelIn').disabled = false; $('duelGo').disabled = false;
  $('duelMsg').textContent = t('duelAsk');
}

async function playDuel() {
  if (!duel) return;
  const mine = Array.from($('duelIn').value.trim())[0];
  if (!mine) { toast(t('duelOne')); return; }
  const d = duel; duel = null;                 // 두 번 눌러도 한 번만 센다
  const p = await call('probs', { prefix: d.prefix, k: 1 });
  const [aiCh, aiP] = p.top[0];
  const meOk = mine === d.answer, aiOk = aiCh === d.answer;
  if (meOk) score.me++;
  if (aiOk) score.ai++;
  $('scoreMe').textContent = score.me; $('scoreAi').textContent = score.ai;
  $('duelQ').innerHTML = `${esc(duelShown(d.prefix))}<span class="blank ok">${esc(shown(d.answer))}</span>`;
  $('duelMsg').textContent =
    `${t('answer')} '${shown(d.answer)}' · ${t('me')} '${mine}' ${meOk ? '○' : '×'} · ` +
    `${t('ai')} '${shown(aiCh)}' (${(aiP * 100).toFixed(0)}%) ${aiOk ? '○' : '×'}`;
  $('duelIn').disabled = true; $('duelGo').disabled = true;
  $('duelNew').focus();
  if (window.vapiStat) vapiStat('word_duel');
}
$('duelNew').addEventListener('click', () => { newDuel(); $('duelIn').focus(); });
$('duelGo').addEventListener('click', playDuel);
$('duelIn').addEventListener('keydown', e => { if (e.key === 'Enter' && !e.isComposing) playDuel(); });

// ── 창 ─────────────────────────────────────────────────────
// 가려져도 배우기는 워커에서 계속한다 (끝나면 onDone 이 알림). 한 글자씩 써 나가던 것만 끝까지 보여 준다
if (window.EL_WIN) EL_WIN.onHide(stopReveal);

$('langButton').addEventListener('click', () => {
  try { localStorage.setItem('vapiLang', LANG === 'ko' ? 'en' : 'ko'); } catch (e) {}
  location.reload();
});

paintText(); paintPresets(); usePreset(0); pickKind('mlp');
resetOutputs(); paintHist(); setTraining(false); setStep(1); drawChart();

// 자동 시험용 — 상태 보기와 연습 횟수 줄이기 (수업 값 STEPS 는 건드리지 않는다)
window.EL_WORD = {
  STEPS,
  setSteps(o) { Object.assign(steps, o); return { ...steps }; },
  get kind() { return kind; },
  get trained() { return trained && { ...trained }; },
  get training() { return training; },
  get losses() { return losses.slice(); },
  get score() { return { ...score }; },
  get duel() { return duel && { ...duel }; },
  get step() { return step; },
  get hist() { return hist.map(h => h.tag); },
  get revealing() { return !!reveal; },
  call,
};
