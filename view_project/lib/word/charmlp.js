// themakerrobot/ml-lab acts/word/charmlp.js (커밋 e17acd7) 에서 옮김. 계산·상수는 원본 그대로 둔다.
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
// charmlp.js — 글자 단위 고정 창 MLP (의존성 없음, Float32Array)
// ═══════════════════════════════════════════════════════════
// 앞 글자 ctx개 → Embedding(emb) → concat → Dense(hid, tanh) → Dense(V) → softmax
// 역전파·Adam 을 손으로 짰다. TF.js cpu 백엔드보다 훨씬 빨라서
// WebGL 이 없는 저사양 PC 에서도 수업 시간 안에 학습된다.
// 브라우저(Web Worker 권장)·Node 양쪽에서 그대로 쓴다.

export class CharMLP {
  constructor(V, { ctx = 8, emb = 24, hid = 128, seed = 1 } = {}) {
    Object.assign(this, { V, ctx, emb, hid });
    this.IN = ctx * emb;
    let s = seed >>> 0;
    const rnd = () => { s = (s * 1664525 + 1013904223) >>> 0; return s / 4294967296 - 0.5; };
    const init = (n, scale) => Float32Array.from({ length: n }, () => rnd() * 2 * scale);
    // 파라미터
    this.p = {
      E: init(V * emb, 1),                          // [V, emb]
      W1: init(this.IN * hid, 1 / Math.sqrt(this.IN)), // [IN, hid]
      b1: new Float32Array(hid),
      W2: init(hid * V, 1 / Math.sqrt(hid)),        // [hid, V]
      b2: new Float32Array(V),
    };
    this.g = {}; this.m = {}; this.v = {};
    for (const k in this.p) {
      const n = this.p[k].length;
      this.g[k] = new Float32Array(n); this.m[k] = new Float32Array(n); this.v[k] = new Float32Array(n);
    }
    this.t = 0;
  }

  get numParams() { return Object.values(this.p).reduce((a, x) => a + x.length, 0); }

  // x: Int32Array [B*ctx]. 반환: 확률 [B*V], 은닉 [B*hid], 입력 [B*IN]
  forward(x, B) {
    const { V, ctx, emb, hid, IN, p } = this;
    const X = new Float32Array(B * IN), H = new Float32Array(B * hid), P = new Float32Array(B * V);
    for (let b = 0; b < B; b++) {
      for (let c = 0; c < ctx; c++) X.set(p.E.subarray(x[b * ctx + c] * emb, (x[b * ctx + c] + 1) * emb), b * IN + c * emb);
      const h = H.subarray(b * hid, (b + 1) * hid); h.set(p.b1);
      for (let i = 0; i < IN; i++) {
        const xi = X[b * IN + i]; if (xi === 0) continue;
        const row = i * hid;
        for (let j = 0; j < hid; j++) h[j] += xi * p.W1[row + j];
      }
      for (let j = 0; j < hid; j++) h[j] = Math.tanh(h[j]);
      const o = P.subarray(b * V, (b + 1) * V); o.set(p.b2);
      for (let j = 0; j < hid; j++) {
        const hj = h[j], row = j * V;
        for (let k = 0; k < V; k++) o[k] += hj * p.W2[row + k];
      }
      let mx = -Infinity; for (let k = 0; k < V; k++) if (o[k] > mx) mx = o[k];
      let sum = 0; for (let k = 0; k < V; k++) { o[k] = Math.exp(o[k] - mx); sum += o[k]; }
      for (let k = 0; k < V; k++) o[k] /= sum;
    }
    return { X, H, P };
  }

  // 한 배치 학습. 반환: 평균 loss
  step(x, y, B, lr = 0.005) {
    const { V, ctx, emb, hid, IN, p, g } = this;
    const { X, H, P } = this.forward(x, B);
    for (const k in g) g[k].fill(0);
    let loss = 0;
    const dh = new Float32Array(hid), dX = new Float32Array(IN);
    for (let b = 0; b < B; b++) {
      const o = P.subarray(b * V, (b + 1) * V), h = H.subarray(b * hid, (b + 1) * hid);
      loss -= Math.log(o[y[b]] + 1e-9);
      // dlogits = (softmax - onehot) / B  (o 를 제자리에서 덮어쓴다)
      o[y[b]] -= 1; for (let k = 0; k < V; k++) o[k] /= B;
      for (let k = 0; k < V; k++) g.b2[k] += o[k];
      for (let j = 0; j < hid; j++) {
        const hj = h[j], row = j * V; let s = 0;
        for (let k = 0; k < V; k++) { g.W2[row + k] += hj * o[k]; s += p.W2[row + k] * o[k]; }
        dh[j] = s * (1 - hj * hj);   // tanh'
      }
      for (let j = 0; j < hid; j++) g.b1[j] += dh[j];
      for (let i = 0; i < IN; i++) {
        const xi = X[b * IN + i], row = i * hid; let s = 0;
        for (let j = 0; j < hid; j++) { g.W1[row + j] += xi * dh[j]; s += p.W1[row + j] * dh[j]; }
        dX[i] = s;
      }
      for (let c = 0; c < ctx; c++) {
        const e = x[b * ctx + c] * emb;
        for (let d = 0; d < emb; d++) g.E[e + d] += dX[c * emb + d];
      }
    }
    this.adam(lr);
    return loss / B;
  }

  adam(lr, b1 = 0.9, b2 = 0.999, eps = 1e-8) {
    this.t++;
    const c1 = 1 - Math.pow(b1, this.t), c2 = 1 - Math.pow(b2, this.t);
    for (const k in this.p) {
      const w = this.p[k], g = this.g[k], m = this.m[k], v = this.v[k];
      for (let i = 0; i < w.length; i++) {
        m[i] = b1 * m[i] + (1 - b1) * g[i];
        v[i] = b2 * v[i] + (1 - b2) * g[i] * g[i];
        w[i] -= lr * (m[i] / c1) / (Math.sqrt(v[i] / c2) + eps);
      }
    }
  }

  // 한 창(ctx개 id) → 다음 글자 확률
  predict(win) { return this.forward(Int32Array.from(win), 1).P; }

  toJSON() { const o = { V: this.V, ctx: this.ctx, emb: this.emb, hid: this.hid, p: {} };
    for (const k in this.p) o.p[k] = Array.from(this.p[k]); return o; }
  static fromJSON(o) { const m = new CharMLP(o.V, o);
    for (const k in o.p) m.p[k].set(o.p[k]); return m; }
}

// 글 → 사전·데이터셋. PAD=0, UNK=1
export function prepare(text, { ctx = 8, maxVocab = 800 } = {}) {
  const count = new Map();
  for (const ch of text) count.set(ch, (count.get(ch) || 0) + 1);
  if (!count.has('\n')) count.set('\n', 1);
  const itos = ['·', '?', ...[...count].sort((a, b) => b[1] - a[1]).slice(0, maxVocab - 2).map(e => e[0])];
  const stoi = new Map(itos.map((c, i) => [c, i]));
  const enc = ch => stoi.get(ch) ?? 1;
  const xs = [], ys = [];
  for (const line of text.split('\n')) {
    const t = line.trim(); if (!t) continue;
    const ids = [...Array(ctx).fill(0), ...Array.from(t, enc), stoi.get('\n')];
    for (let i = ctx; i < ids.length; i++) { xs.push(...ids.slice(i - ctx, i)); ys.push(ids[i]); }
  }
  return { itos, stoi, enc, x: Int32Array.from(xs), y: Int32Array.from(ys), n: ys.length };
}

// 에폭 단위 학습. onEpoch(ep, loss) — 워커에서 postMessage 로 넘기면 된다
export function train(model, data, { epochs = 30, batch = 64, lr = 0.005, onEpoch } = {}) {
  const { ctx } = model, idx = Int32Array.from({ length: data.n }, (_, i) => i);
  const bx = new Int32Array(batch * ctx), by = new Int32Array(batch);
  for (let ep = 0; ep < epochs; ep++) {
    for (let i = idx.length - 1; i > 0; i--) { const j = (Math.random() * (i + 1)) | 0; [idx[i], idx[j]] = [idx[j], idx[i]]; }
    let tot = 0, nb = 0;
    for (let s = 0; s < data.n; s += batch) {
      const B = Math.min(batch, data.n - s);
      for (let b = 0; b < B; b++) {
        const k = idx[s + b];
        bx.set(data.x.subarray(k * ctx, (k + 1) * ctx), b * ctx); by[b] = data.y[k];
      }
      tot += model.step(bx.subarray(0, B * ctx), by.subarray(0, B), B, lr); nb++;
    }
    onEpoch?.(ep, tot / nb);
  }
}

// 온도 샘플링으로 이어 쓰기
export function generate(model, data, seed, { temp = 0.8, maxLen = 60 } = {}) {
  let ids = [...Array(model.ctx).fill(0), ...Array.from(seed, data.enc)], out = seed;
  for (let n = 0; n < maxLen; n++) {
    const p = model.predict(ids.slice(-model.ctx));
    const w = Array.from(p, v => Math.pow(v, 1 / temp)); let r = Math.random() * w.reduce((a, b) => a + b, 0), k = 0;
    for (; k < w.length - 1; k++) { r -= w[k]; if (r <= 0) break; }
    const ch = data.itos[k]; if (ch === '\n') break;
    out += ch; ids.push(k);
  }
  return out;
}
