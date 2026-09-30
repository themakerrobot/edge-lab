// themakerrobot/ml-lab acts/word/minigpt.js (커밋 e17acd7) 에서 옮김. 계산·상수는 원본 그대로 둔다.
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
// minigpt.js — 글자 단위 미니 Transformer (의존성 없음, Float32Array)
// ═══════════════════════════════════════════════════════════
// 구조 (GPT 와 같은 pre-LN decoder):
//   글자 임베딩 + 위치 임베딩
//   → [LayerNorm → 인과 멀티헤드 어텐션 → 잔차
//      → LayerNorm → MLP(d→4d→d, ReLU) → 잔차] × layers
//   → LayerNorm → Dense(V) → softmax
// 역전파·Adam·기울기 자르기를 손으로 짰다. TF.js·WebGL 없이 cpu 에서 돈다.
// 수업 화면용으로 attention() 이 [층][헤드][T×T] 어텐션 가중치를 돌려준다.
// 무거운 학습은 Web Worker 에서 돌릴 것 (메인 스레드에서 돌리면 화면이 멈춘다).

// ── 공통 연산 ────────────────────────────────────────────────
// X[T×a] · W[a×n] (+ b[n]) → Y[T×n]
function linear(X, T, a, W, b, n) {
  const Y = new Float32Array(T * n);
  for (let t = 0; t < T; t++) {
    const y = Y.subarray(t * n, (t + 1) * n);
    if (b) y.set(b);
    for (let i = 0; i < a; i++) {
      const xi = X[t * a + i]; if (xi === 0) continue;
      const r = i * n;
      for (let j = 0; j < n; j++) y[j] += xi * W[r + j];
    }
  }
  return Y;
}

// linear 의 역전파. gW, gb 에 누적하고 dX 를 돌려준다
function linearBack(dY, X, T, a, W, n, gW, gb) {
  const dX = new Float32Array(T * a);
  for (let t = 0; t < T; t++) {
    const dy = dY.subarray(t * n, (t + 1) * n);
    if (gb) for (let j = 0; j < n; j++) gb[j] += dy[j];
    for (let i = 0; i < a; i++) {
      const xi = X[t * a + i], r = i * n;
      let s = 0;
      for (let j = 0; j < n; j++) { gW[r + j] += xi * dy[j]; s += W[r + j] * dy[j]; }
      dX[t * a + i] = s;
    }
  }
  return dX;
}

function lnFwd(X, T, d, g, b) {
  const Y = new Float32Array(T * d), Xh = new Float32Array(T * d), R = new Float32Array(T);
  for (let t = 0; t < T; t++) {
    let m = 0; for (let i = 0; i < d; i++) m += X[t * d + i]; m /= d;
    let v = 0; for (let i = 0; i < d; i++) { const z = X[t * d + i] - m; v += z * z; } v /= d;
    const r = 1 / Math.sqrt(v + 1e-5); R[t] = r;
    for (let i = 0; i < d; i++) {
      const xh = (X[t * d + i] - m) * r;
      Xh[t * d + i] = xh; Y[t * d + i] = xh * g[i] + b[i];
    }
  }
  return { Y, Xh, R };
}

function lnBack(dY, c, T, d, g, gg, gb) {
  const dX = new Float32Array(T * d);
  for (let t = 0; t < T; t++) {
    let s1 = 0, s2 = 0;
    for (let i = 0; i < d; i++) {
      const k = t * d + i, dxh = dY[k] * g[i];
      gg[i] += dY[k] * c.Xh[k]; gb[i] += dY[k];
      s1 += dxh; s2 += dxh * c.Xh[k];
    }
    s1 /= d; s2 /= d;
    for (let i = 0; i < d; i++) {
      const k = t * d + i;
      dX[k] = c.R[t] * (dY[k] * g[i] - s1 - c.Xh[k] * s2);
    }
  }
  return dX;
}

// 인과(앞만 보는) 멀티헤드 어텐션. A[h][t][s] 는 s ≤ t 칸만 쓴다
function attnFwd(Q, K, V, T, d, H) {
  const hd = d / H, sc = 1 / Math.sqrt(hd);
  const O = new Float32Array(T * d), A = new Float32Array(H * T * T);
  for (let h = 0; h < H; h++) {
    const off = h * hd;
    for (let t = 0; t < T; t++) {
      const a = A.subarray((h * T + t) * T, (h * T + t + 1) * T);
      let mx = -Infinity;
      for (let s = 0; s <= t; s++) {
        let dot = 0;
        for (let j = 0; j < hd; j++) dot += Q[t * d + off + j] * K[s * d + off + j];
        a[s] = dot * sc; if (a[s] > mx) mx = a[s];
      }
      let sum = 0;
      for (let s = 0; s <= t; s++) { a[s] = Math.exp(a[s] - mx); sum += a[s]; }
      for (let s = 0; s <= t; s++) {
        a[s] /= sum;
        for (let j = 0; j < hd; j++) O[t * d + off + j] += a[s] * V[s * d + off + j];
      }
    }
  }
  return { O, A };
}

function attnBack(dO, Q, K, V, A, T, d, H) {
  const hd = d / H, sc = 1 / Math.sqrt(hd);
  const dQ = new Float32Array(T * d), dK = new Float32Array(T * d), dV = new Float32Array(T * d);
  const dA = new Float32Array(T);
  for (let h = 0; h < H; h++) {
    const off = h * hd;
    for (let t = 0; t < T; t++) {
      const a = A.subarray((h * T + t) * T, (h * T + t + 1) * T);
      let tot = 0;
      for (let s = 0; s <= t; s++) {
        let dot = 0;
        for (let j = 0; j < hd; j++) {
          dot += dO[t * d + off + j] * V[s * d + off + j];
          dV[s * d + off + j] += a[s] * dO[t * d + off + j];
        }
        dA[s] = dot; tot += a[s] * dot;
      }
      for (let s = 0; s <= t; s++) {
        const ds = a[s] * (dA[s] - tot) * sc;
        for (let j = 0; j < hd; j++) {
          dQ[t * d + off + j] += ds * K[s * d + off + j];
          dK[s * d + off + j] += ds * Q[t * d + off + j];
        }
      }
    }
  }
  return { dQ, dK, dV };
}

// ── 모델 ────────────────────────────────────────────────────
export class MiniGPT {
  constructor(V, { ctx = 32, d = 32, heads = 2, layers = 2, seed = 1 } = {}) {
    if (d % heads) throw new Error('d 는 heads 로 나누어떨어져야 합니다');
    Object.assign(this, { V, ctx, d, heads, layers, f: 4 * d });
    let s = seed >>> 0;
    const rnd = () => { s = (s * 1664525 + 1013904223) >>> 0; return s / 4294967296 - 0.5; };
    const U = (n, scale) => Float32Array.from({ length: n }, () => rnd() * 2 * scale);
    const Z = n => new Float32Array(n), O = n => new Float32Array(n).fill(1);
    const f = this.f, res = 1 / Math.sqrt(2 * layers);   // 잔차로 들어가는 층은 작게 시작
    const p = { tok: U(V * d, 0.1), pos: U(ctx * d, 0.1) };
    for (let l = 0; l < layers; l++) {
      Object.assign(p, {
        [`${l}.ln1g`]: O(d), [`${l}.ln1b`]: Z(d),
        [`${l}.Wq`]: U(d * d, 1 / Math.sqrt(d)), [`${l}.Wk`]: U(d * d, 1 / Math.sqrt(d)),
        [`${l}.Wv`]: U(d * d, 1 / Math.sqrt(d)),
        [`${l}.Wo`]: U(d * d, res / Math.sqrt(d)), [`${l}.bo`]: Z(d),
        [`${l}.ln2g`]: O(d), [`${l}.ln2b`]: Z(d),
        [`${l}.W1`]: U(d * f, 1 / Math.sqrt(d)), [`${l}.b1`]: Z(f),
        [`${l}.W2`]: U(f * d, res / Math.sqrt(f)), [`${l}.b2`]: Z(d),
      });
    }
    Object.assign(p, { lnfg: O(d), lnfb: Z(d), Wout: U(d * V, 1 / Math.sqrt(d)), bout: Z(V) });
    this.p = p; this.g = {}; this.m = {}; this.v = {}; this.t = 0;
    for (const k in p) { const n = p[k].length; this.g[k] = Z(n); this.m[k] = Z(n); this.v[k] = Z(n); }
  }

  get numParams() { return Object.values(this.p).reduce((a, x) => a + x.length, 0); }

  // ids: 길이 T (≤ ctx) 인 글자 번호 배열. 캐시를 돌려준다
  forward(ids) {
    const { d, f, V, heads: H, p } = this, T = ids.length;
    if (T > this.ctx) throw new Error(`한 번에 ${this.ctx}글자까지 볼 수 있습니다`);
    let x = new Float32Array(T * d);
    for (let t = 0; t < T; t++)
      for (let j = 0; j < d; j++) x[t * d + j] = p.tok[ids[t] * d + j] + p.pos[t * d + j];
    const L = [];
    for (let l = 0; l < this.layers; l++) {
      const w = k => p[`${l}.${k}`];
      const ln1 = lnFwd(x, T, d, w('ln1g'), w('ln1b'));
      const Q = linear(ln1.Y, T, d, w('Wq'), null, d);
      const K = linear(ln1.Y, T, d, w('Wk'), null, d);
      const Vv = linear(ln1.Y, T, d, w('Wv'), null, d);
      const { O, A } = attnFwd(Q, K, Vv, T, d, H);
      const P = linear(O, T, d, w('Wo'), w('bo'), d);
      const x1 = new Float32Array(T * d); for (let i = 0; i < x1.length; i++) x1[i] = x[i] + P[i];
      const ln2 = lnFwd(x1, T, d, w('ln2g'), w('ln2b'));
      const Hp = linear(ln2.Y, T, d, w('W1'), w('b1'), f);
      const Hr = Hp.map(v => v > 0 ? v : 0);
      const M = linear(Hr, T, f, w('W2'), w('b2'), d);
      const x2 = new Float32Array(T * d); for (let i = 0; i < x2.length; i++) x2[i] = x1[i] + M[i];
      L.push({ ln1, Q, K, V: Vv, O, A, ln2, Hp, Hr });
      x = x2;
    }
    const lnf = lnFwd(x, T, d, p.lnfg, p.lnfb);
    const P = linear(lnf.Y, T, d, p.Wout, p.bout, V);
    for (let t = 0; t < T; t++) {
      const o = P.subarray(t * V, (t + 1) * V);
      let mx = -Infinity; for (let k = 0; k < V; k++) if (o[k] > mx) mx = o[k];
      let sum = 0; for (let k = 0; k < V; k++) { o[k] = Math.exp(o[k] - mx); sum += o[k]; }
      for (let k = 0; k < V; k++) o[k] /= sum;
    }
    return { ids, T, L, lnf, P };
  }

  // 한 시퀀스의 역전파. targets[t] = ids[t] 다음 글자. scale = 1/(배치 전체 글자 수)
  backward(c, targets, scale) {
    const { d, f, V, heads: H, p, g } = this, { T, L, lnf, P, ids } = c;
    let loss = 0;
    const dl = new Float32Array(T * V);
    for (let t = 0; t < T; t++) {
      loss -= Math.log(P[t * V + targets[t]] + 1e-9);
      for (let k = 0; k < V; k++) dl[t * V + k] = P[t * V + k] * scale;
      dl[t * V + targets[t]] -= scale;
    }
    let dx = lnBack(linearBack(dl, lnf.Y, T, d, p.Wout, V, g.Wout, g.bout), lnf, T, d, p.lnfg, g.lnfg, g.lnfb);
    for (let l = this.layers - 1; l >= 0; l--) {
      const w = k => p[`${l}.${k}`], gw = k => g[`${l}.${k}`], c1 = L[l];
      // MLP
      const dH = linearBack(dx, c1.Hr, T, f, w('W2'), d, gw('W2'), gw('b2'));
      for (let i = 0; i < dH.length; i++) if (c1.Hp[i] <= 0) dH[i] = 0;
      const d2 = lnBack(linearBack(dH, c1.ln2.Y, T, d, w('W1'), f, gw('W1'), gw('b1')), c1.ln2, T, d, w('ln2g'), gw('ln2g'), gw('ln2b'));
      const dx1 = new Float32Array(T * d); for (let i = 0; i < dx1.length; i++) dx1[i] = dx[i] + d2[i];
      // 어텐션
      const dO = linearBack(dx1, c1.O, T, d, w('Wo'), d, gw('Wo'), gw('bo'));
      const { dQ, dK, dV } = attnBack(dO, c1.Q, c1.K, c1.V, c1.A, T, d, H);
      const dn = linearBack(dQ, c1.ln1.Y, T, d, w('Wq'), d, gw('Wq'), null);
      const dk = linearBack(dK, c1.ln1.Y, T, d, w('Wk'), d, gw('Wk'), null);
      const dv = linearBack(dV, c1.ln1.Y, T, d, w('Wv'), d, gw('Wv'), null);
      for (let i = 0; i < dn.length; i++) dn[i] += dk[i] + dv[i];
      const d1 = lnBack(dn, c1.ln1, T, d, w('ln1g'), gw('ln1g'), gw('ln1b'));
      dx = new Float32Array(T * d); for (let i = 0; i < dx.length; i++) dx[i] = dx1[i] + d1[i];
    }
    for (let t = 0; t < T; t++)
      for (let j = 0; j < d; j++) { g.tok[ids[t] * d + j] += dx[t * d + j]; g.pos[t * d + j] += dx[t * d + j]; }
    return loss;
  }

  // 배치(시퀀스 여러 개)의 평균 loss 와 기울기. 기울기는 this.g 에 남는다
  lossAndGrad(xs, ys) {
    for (const k in this.g) this.g[k].fill(0);
    const n = xs.reduce((a, x) => a + x.length, 0);
    let loss = 0;
    for (let b = 0; b < xs.length; b++) loss += this.backward(this.forward(xs[b]), ys[b], 1 / n);
    return loss / n;
  }

  step(xs, ys, lr = 3e-3, clip = 1.0) {
    const loss = this.lossAndGrad(xs, ys);
    // 기울기 전체 크기가 clip 을 넘으면 줄인다 (학습이 튀는 것 방지)
    let nrm = 0; for (const k in this.g) for (const v of this.g[k]) nrm += v * v;
    nrm = Math.sqrt(nrm);
    const s = nrm > clip ? clip / nrm : 1;
    this.adam(lr, s);
    return loss;
  }

  adam(lr, gs = 1, b1 = 0.9, b2 = 0.999, eps = 1e-8) {
    this.t++;
    const c1 = 1 - Math.pow(b1, this.t), c2 = 1 - Math.pow(b2, this.t);
    for (const k in this.p) {
      const w = this.p[k], g = this.g[k], m = this.m[k], v = this.v[k];
      for (let i = 0; i < w.length; i++) {
        const gi = g[i] * gs;
        m[i] = b1 * m[i] + (1 - b1) * gi;
        v[i] = b2 * v[i] + (1 - b2) * gi * gi;
        w[i] -= lr * (m[i] / c1) / (Math.sqrt(v[i] / c2) + eps);
      }
    }
  }

  // 마지막 글자 다음에 올 글자 확률
  predict(ids) {
    const c = this.forward(ids.slice(-this.ctx));
    return c.P.subarray((c.T - 1) * this.V, c.T * this.V);
  }

  toJSON() {
    const o = { V: this.V, ctx: this.ctx, d: this.d, heads: this.heads, layers: this.layers, p: {} };
    for (const k in this.p) o.p[k] = Array.from(this.p[k]);
    return o;
  }
  static fromJSON(o) {
    const m = new MiniGPT(o.V, o);
    for (const k in o.p) m.p[k].set(o.p[k]);
    return m;
  }
}

// ── 데이터 · 학습 · 생성 ────────────────────────────────────
// 글 전체를 한 줄 글자 번호로 만든다. 0 = '?'(모르는 글자), 줄바꿈은 '\n' 글자
export function prepare(text, { maxVocab = 300 } = {}) {
  const lines = text.split('\n').map(s => s.trim()).filter(Boolean);
  const joined = '\n' + lines.join('\n') + '\n';
  const count = new Map();
  for (const ch of joined) count.set(ch, (count.get(ch) || 0) + 1);
  const itos = ['?', ...[...count].sort((a, b) => b[1] - a[1]).slice(0, maxVocab - 1).map(e => e[0])];
  const stoi = new Map(itos.map((c, i) => [c, i]));
  const enc = ch => stoi.get(ch) ?? 0;
  return { itos, stoi, enc, ids: Int32Array.from(Array.from(joined, enc)) };
}

// steps 번 학습. 한 번에 글에서 무작위로 batch 조각(길이 ctx)을 뽑는다
// onProgress(step, loss) 는 every 번마다 부른다 — 워커에서는 postMessage 로 넘길 것
export function train(model, data, { steps = 300, batch = 8, lr = 3e-3, every = 10, onProgress } = {}) {
  const n = data.ids.length, T = Math.min(model.ctx, n - 1);
  let avg = null;
  for (let s = 0; s < steps; s++) {
    const xs = [], ys = [];
    for (let b = 0; b < batch; b++) {
      const i = Math.floor(Math.random() * (n - T));
      xs.push(Array.from(data.ids.subarray(i, i + T)));
      ys.push(Array.from(data.ids.subarray(i + 1, i + T + 1)));
    }
    const loss = model.step(xs, ys, lr);
    avg = avg === null ? loss : 0.9 * avg + 0.1 * loss;
    if ((s + 1) % every === 0) onProgress?.(s + 1, avg);
  }
  return avg;
}

// 줄 시작('\n')부터 seed 를 이어 쓴다. temp: 낮으면 뻔하게, 높으면 엉뚱하게
export function generate(model, data, seed, { temp = 0.8, maxLen = 60 } = {}) {
  const nl = data.enc('\n');
  const ids = [nl, ...Array.from(seed, data.enc)];
  let out = seed;
  for (let n = 0; n < maxLen; n++) {
    const p = model.predict(ids);
    const w = Array.from(p, v => Math.pow(v, 1 / temp));
    let r = Math.random() * w.reduce((a, b) => a + b, 0), k = 0;
    for (; k < w.length - 1; k++) { r -= w[k]; if (r <= 0) break; }
    if (k === nl) break;
    out += data.itos[k]; ids.push(k);
  }
  return out;
}

// 수업 화면용: 글자마다 앞의 어느 글자를 얼마나 봤는지
// 반환 { chars: ['↵','토','끼',...], A: [층][헤드] = T×T 배열(행 t, 열 s ≤ t) }
export function attention(model, data, text) {
  const nl = data.enc('\n');
  const ids = [nl, ...Array.from(text, data.enc)].slice(-model.ctx);
  const c = model.forward(ids), T = c.T;
  const chars = ids.map(i => data.itos[i] === '\n' ? '↵' : data.itos[i]);
  const A = c.L.map(l => Array.from({ length: model.heads }, (_, h) =>
    Array.from({ length: T }, (_, t) => Array.from(l.A.subarray((h * T + t) * T, (h * T + t) * T + T)))));
  return { chars, A };
}
