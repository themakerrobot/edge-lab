// themakerrobot/ml-lab acts/word/worker.js (커밋 e17acd7) 에서 옮김. 계산·상수는 원본 그대로 둔다.
// (DEVELOP.md 의 잰 값이 이 숫자들로 나왔다 — 바꾸면 수업 시간 계산이 깨진다)
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

// ═══════════════════════════════════════════════════════════
// 문장 활동 — 학습 워커 (메인 화면이 멈추지 않도록 계산은 전부 여기서)
// ═══════════════════════════════════════════════════════════
// 모델 두 가지를 같은 약속으로 다룬다
//   mlp : 앞 글자 ctx개만 보는 작은 신경망 (charmlp.js)
//   gpt : 앞 글 전체(최대 32글자)를 보는 미니 Transformer (minigpt.js)
//
// 메인 → 워커 : { id, type, ... }   워커 → 메인 : { id, ... } 답장
// 학습 중에는 { type:'progress' } / { type:'done' } 를 따로 보낸다.
// 학습은 10번마다 한 번 쉬어서(setTimeout 0) '멈추기'·'후보 보기' 요청을 받는다.

import { CharMLP, prepare as prepMLP } from './charmlp.js';
import { MiniGPT, prepare as prepGPT, attention } from './minigpt.js';

const MAX_VOCAB = 300;          // 글자 종류 상한. 출력층 크기라서 속도를 좌우한다
const MLP_BATCH = 32, MLP_LR = 0.005;
const GPT_BATCH = 8, GPT_LR = 3e-3;
const GPT_CFG = { ctx: 32, d: 32, heads: 2, layers: 2 };

let S = null;                   // { kind, model, data, step, avg, corpus }
let stopFlag = false, busy = false;

const nextTick = () => new Promise(r => setTimeout(r, 0));

function mlpStep() {
  const { model, data } = S, ctx = model.ctx, B = Math.min(MLP_BATCH, data.n);
  const bx = new Int32Array(B * ctx), by = new Int32Array(B);
  for (let b = 0; b < B; b++) {
    const k = (Math.random() * data.n) | 0;
    bx.set(data.x.subarray(k * ctx, (k + 1) * ctx), b * ctx);
    by[b] = data.y[k];
  }
  return model.step(bx, by, B, MLP_LR);
}

function gptStep() {
  const { model, data } = S, n = data.ids.length, T = Math.min(model.ctx, n - 1);
  const xs = [], ys = [];
  for (let b = 0; b < GPT_BATCH; b++) {
    const i = Math.floor(Math.random() * (n - T));
    xs.push(Array.from(data.ids.subarray(i, i + T)));
    ys.push(Array.from(data.ids.subarray(i + 1, i + T + 1)));
  }
  return model.step(xs, ys, GPT_LR);
}

async function run(steps) {
  busy = true; stopFlag = false;
  const t0 = performance.now(), target = S.step + steps;
  while (S.step < target && !stopFlag) {
    const loss = S.kind === 'mlp' ? mlpStep() : gptStep();
    S.avg = S.avg === null ? loss : 0.95 * S.avg + 0.05 * loss;
    S.step++;
    if (S.step % 10 === 0) {
      postMessage({ type: 'progress', step: S.step, target, loss: S.avg });
      await nextTick();
    }
  }
  busy = false;
  postMessage({ type: 'done', step: S.step, loss: S.avg, sec: (performance.now() - t0) / 1000, stopped: stopFlag });
}

// 글자 → 번호. 모르는 글자는 UNK
function encode(text) { return Array.from(text, S.data.enc); }

// 줄 시작에서 prefix 까지 읽었을 때 모델이 보는 번호들
function context(prefix) {
  const { kind, model, data } = S;
  if (kind === 'mlp') return [...Array(model.ctx).fill(0), ...encode(prefix)].slice(-model.ctx);
  return [data.enc('\n'), ...encode(prefix)].slice(-model.ctx);
}

function probs(prefix) {
  return S.model.predict(context(prefix));
}

function top(p, k) {
  const idx = Array.from(p.keys()).sort((a, b) => p[b] - p[a]).slice(0, k);
  return idx.map(i => [S.data.itos[i], p[i]]);
}

function sample(p, temp) {
  // 온도: 확률을 1/temp 제곱해서 다시 나눈다. 낮으면 뻔한 글자, 높으면 엉뚱한 글자
  const w = Array.from(p, v => Math.pow(v, 1 / temp));
  let r = Math.random() * w.reduce((a, b) => a + b, 0), k = 0;
  for (; k < w.length - 1; k++) { r -= w[k]; if (r <= 0) break; }
  return k;
}

// 배운 적 없는 글자 (사전에 없는 글자)
function unknown(text) {
  return [...new Set(Array.from(text).filter(ch => !S.data.stoi.has(ch)))];
}

const handlers = {
  train({ kind, text, ctx, steps }) {
    if (kind === 'mlp') {
      const data = prepMLP(text, { ctx, maxVocab: MAX_VOCAB });
      S = { kind, data, model: new CharMLP(data.itos.length, { ctx }) };
    } else {
      const data = prepGPT(text, { maxVocab: MAX_VOCAB });
      S = { kind, data, model: new MiniGPT(data.itos.length, GPT_CFG) };
    }
    S.step = 0; S.avg = null;
    const samples = kind === 'mlp' ? S.data.n : S.data.ids.length;
    setTimeout(() => run(steps), 0);   // 답장(글자 종류 등)이 진행 소식보다 먼저 가도록
    return { vocab: S.data.itos.length, params: S.model.numParams, samples, ctx: S.model.ctx };
  },
  more({ steps }) { if (!busy) setTimeout(() => run(steps), 0); return { ok: true }; },
  stop() { stopFlag = true; return { ok: true }; },
  probs({ prefix, k = 5 }) {
    return { top: top(probs(prefix), k), unknown: unknown(prefix) };
  },
  generate({ seed, temp, max = 80 }) {
    const nl = S.data.enc('\n');
    let out = '';
    for (let i = 0; i < max; i++) {
      const k = sample(probs(seed + out), temp);
      if (k === nl) break;
      out += S.data.itos[k];
    }
    return { text: out };
  },
  step({ seed, temp }) {
    const k = sample(probs(seed), temp);
    return { ch: S.data.itos[k] };
  },
  look({ text }) {
    if (S.kind === 'mlp') {
      // 모델이 실제로 보는 창. 줄 앞쪽의 빈칸(PAD)은 '·' 로 보인다
      const win = context(text).map(i => S.data.itos[i]);
      return { kind: 'mlp', window: win };
    }
    const shown = Array.from(text).slice(-15).join('');
    return { kind: 'gpt', ...attention(S.model, S.data, shown) };
  },
};

onmessage = ({ data: msg }) => {
  const { id, type } = msg;
  try {
    if (type !== 'train' && !S) throw new Error('아직 배우지 않았어요');
    postMessage({ id, ok: true, ...handlers[type](msg) });
  } catch (e) {
    postMessage({ id, ok: false, error: String(e.message || e) });
  }
};
