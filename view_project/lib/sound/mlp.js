// 소리 분류기 학습 — 순수 JS (TF.js 없이)
// themakerrobot/teach-lab lib/trainer.js (커밋 74f421a) 의 층 구성과 학습 조건을 그대로 따라 순수 JS 로 다시 짰다.
//   입력 521 → Dense(64, relu) → Dropout(0.2) → Dense(N, softmax)
//   adam(0.001) / categoricalCrossentropy / epochs 40 / batch 16 / glorot-uniform 초기값
// 결과는 teach-lab lib/classifier.js 의 저장 형식({json, bin}) 그대로라 deserialize·predict 로 바로 쓴다.
//
// 왜 TF.js(/lib/tf.min-3.11.0.js)를 쓰지 않나: 같은 조건(예시 66개)에서 TF.js cpu 백엔드가 이 컴퓨터에서
// 4초 넘게 걸렸다 (배치마다 드는 고정 비용). sqrt-L2 를 거친 YAMNet 점수는 521칸 중 수십 칸만
// 0이 아니라서, 0이 아닌 칸만 곱하면 같은 계산이 수십 배 빠르다 — 아이가 누르고 1초 안에 끝난다.
// 달라진 점 하나: teach-lab 은 예시가 15개 이상이면 20% 를 검증용으로 떼지만, 여기서는 전부로 배운다
// (수업에서 보여 주는 정확도는 teach-lab 도 "모은 예시 전체" 기준이다).
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

import { CLF_FORMAT, CLF_VERSION } from './classifier.js';

export const EPOCHS = 40;
export const HIDDEN = 64;
const BATCH = 16;
const LR = 0.001, B1 = 0.9, B2 = 0.999, EPS = 1e-7;   // TF.js adam 기본값과 같다
const KEEP = 0.8;                                      // Dropout(0.2)

// 시드 난수 — 같은 예시면 같은 결과 (수업에서 "다시 배우기" 를 비교할 수 있게, 자동 시험도 결정적으로)
function rng(seed) {
  let a = seed >>> 0;
  return () => { a = (a + 0x6D2B79F5) >>> 0; let t = a; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
}

// 한 프레임 양보 — 진행률 바가 그려지게. 셸에서 창이 가려지면 rAF 가 안 올 수 있어 시간으로도 깨운다
function breathe() {
  return new Promise(ok => {
    let done = false;
    const go = () => { if (!done) { done = true; ok(); } };
    requestAnimationFrame(go);
    setTimeout(go, 30);
  });
}

// vecs: Float32Array[] (다듬은 값), labels: int[]
// onEpoch(epoch, total, {loss, acc}) 로 진행을 알린다.
// → { json, bin, history, confusion, accuracy }  (json.classes 는 부르는 쪽이 채운다)
export async function trainModel(vecs, labels, numClasses, dim, onEpoch, { seed = 1 } = {}) {
  const H = HIDDEN, N = numClasses, rnd = rng(seed);
  const glorot = (n, fanIn, fanOut) => { const a = new Float32Array(n), lim = Math.sqrt(6 / (fanIn + fanOut)); for (let i = 0; i < n; i++) a[i] = (rnd() * 2 - 1) * lim; return a; };
  const W1 = glorot(dim * H, dim, H), b1 = new Float32Array(H);
  const W2 = glorot(H * N, H, N), b2 = new Float32Array(N);
  const P = [W1, b1, W2, b2];
  const G = P.map(p => new Float32Array(p.length));
  const M = P.map(p => new Float32Array(p.length)), V = P.map(p => new Float32Array(p.length));
  const [gW1, gb1, gW2, gb2] = G;

  // 0이 아닌 칸만 추려 둔다 — 곱셈을 그 칸에만 한다
  const sp = vecs.map(v => {
    const idx = [], val = [];
    for (let i = 0; i < dim; i++) if (v[i] !== 0) { idx.push(i); val.push(v[i]); }
    return { idx: Int32Array.from(idx), val: Float32Array.from(val) };
  });
  const h = new Float32Array(H), a = new Float32Array(H), mask = new Float32Array(H), z = new Float32Array(N), dh = new Float32Array(H);

  // 한 장 앞으로 — train 이면 dropout 을 건다. 확률은 z 에 남는다
  function forward(s, train) {
    for (let j = 0; j < H; j++) h[j] = b1[j];
    for (let q = 0; q < s.idx.length; q++) {
      const x = s.val[q], row = s.idx[q] * H;
      for (let j = 0; j < H; j++) h[j] += x * W1[row + j];
    }
    for (let j = 0; j < H; j++) {
      mask[j] = train ? (rnd() < KEEP ? 1 / KEEP : 0) : 1;
      a[j] = h[j] > 0 ? h[j] * mask[j] : 0;
    }
    let mx = -Infinity;
    for (let k = 0; k < N; k++) {
      let v = b2[k];
      for (let j = 0; j < H; j++) v += a[j] * W2[j * N + k];
      z[k] = v; if (v > mx) mx = v;
    }
    let sum = 0;
    for (let k = 0; k < N; k++) { z[k] = Math.exp(z[k] - mx); sum += z[k]; }
    for (let k = 0; k < N; k++) z[k] /= sum;
  }

  const order = vecs.map((_, i) => i);
  const history = [];
  let step = 0;
  for (let ep = 0; ep < EPOCHS; ep++) {
    for (let i = order.length - 1; i > 0; i--) { const j = Math.floor(rnd() * (i + 1)); [order[i], order[j]] = [order[j], order[i]]; }
    let lossSum = 0, correct = 0;
    for (let s0 = 0; s0 < order.length; s0 += BATCH) {
      const batch = order.slice(s0, s0 + BATCH), inv = 1 / batch.length;
      G.forEach(g => g.fill(0));
      for (const n of batch) {
        const s = sp[n], y = labels[n];
        forward(s, true);
        lossSum -= Math.log(Math.max(z[y], 1e-7));
        let best = 0; for (let k = 1; k < N; k++) if (z[k] > z[best]) best = k;
        if (best === y) correct++;
        // 뒤로: softmax + 교차 엔트로피의 기울기는 (p - 정답)
        for (let k = 0; k < N; k++) { const d = (z[k] - (k === y ? 1 : 0)) * inv; z[k] = d; gb2[k] += d; }
        for (let j = 0; j < H; j++) {
          let da = 0;
          const aj = a[j];
          for (let k = 0; k < N; k++) { gW2[j * N + k] += aj * z[k]; da += W2[j * N + k] * z[k]; }
          dh[j] = h[j] > 0 ? da * mask[j] : 0;
          gb1[j] += dh[j];
        }
        for (let q = 0; q < s.idx.length; q++) {
          const x = s.val[q], row = s.idx[q] * H;
          for (let j = 0; j < H; j++) gW1[row + j] += x * dh[j];
        }
      }
      // adam
      step++;
      const c1 = 1 - Math.pow(B1, step), c2 = 1 - Math.pow(B2, step), lr = LR * Math.sqrt(c2) / c1;
      for (let p = 0; p < P.length; p++) {
        const w = P[p], g = G[p], m = M[p], v = V[p];
        for (let i = 0; i < w.length; i++) {
          const gi = g[i];
          m[i] = B1 * m[i] + (1 - B1) * gi;
          v[i] = B2 * v[i] + (1 - B2) * gi * gi;
          w[i] -= lr * m[i] / (Math.sqrt(v[i]) + EPS);
        }
      }
    }
    const rec = { loss: lossSum / order.length, acc: correct / order.length };
    history.push(rec);
    if (onEpoch) onEpoch(ep + 1, EPOCHS, rec);
    await breathe();                 // 진행률 바가 멈추지 않게 한 프레임 양보
  }

  // 전체 예시로 헷갈린 표(혼동 행렬) — dropout 없이
  const confusion = Array.from({ length: N }, () => new Array(N).fill(0));
  let correct = 0;
  sp.forEach((s, n) => {
    forward(s, false);
    let best = 0; for (let k = 1; k < N; k++) if (z[k] > z[best]) best = k;
    confusion[labels[n]][best]++;
    if (best === labels[n]) correct++;
  });

  // teach-lab classifier.json 형식 그대로 (kernel 은 [입력, 출력] 행 우선)
  const total = W1.length + b1.length + W2.length + b2.length;
  const bin = new Float32Array(total);
  bin.set(W1, 0); bin.set(b1, W1.length); bin.set(W2, W1.length + b1.length); bin.set(b2, W1.length + b1.length + W2.length);
  const json = {
    format: CLF_FORMAT, version: CLF_VERSION, inputDim: dim, classes: [], dtype: 'float32-le', weightsFile: 'classifier.bin', totalCount: total,
    layers: [
      { type: 'dense', activation: 'relu', kernel: { shape: [dim, H], offset: 0, count: W1.length }, bias: { shape: [H], offset: W1.length, count: H } },
      { type: 'dense', activation: 'softmax', kernel: { shape: [H, N], offset: W1.length + H, count: W2.length }, bias: { shape: [N], offset: W1.length + H + W2.length, count: N } },
    ],
  };
  return { json, bin: bin.buffer, history, confusion, accuracy: sp.length ? correct / sp.length : 0 };
}
