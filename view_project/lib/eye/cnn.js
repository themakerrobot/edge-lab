// themakerrobot/ml-lab acts/eye/cnn.js (커밋 e17acd7) 에서 옮김 — 계산·상수는 그대로 두었다.
// edge-lab 에서는 /lib/eye/ 아래 ES 모듈로 쓴다 (화면: view_project/eye.html).
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
// AI 눈 활동 — 아주 작은 합성곱 신경망 (의존성 없음, DOM 없음)
// ═══════════════════════════════════════════════════════════
// 32×32 흑백 → 합성곱(필터 F개, 5×5) → ReLU → 최대 풀링 2×2 → 완전연결 → softmax
//
//  · 층이 하나뿐이라 필터 F개를 그대로 그림으로 보여 주고 해석할 수 있다 (수업 2차시)
//  · 이미 학습된 모델을 쓰지 않고 매번 처음부터 배운다 — teach-lab 과 다른 점
//  · 계산은 Web Worker 에서 한다 (worker.js)

export const IMG = 32, K = 5, OUT = IMG - K + 1, POOL = OUT / 2;   // 32 → 28 → 14

export class TinyCNN {
  constructor(nClass, { filters = 8, seed = 1 } = {}) {
    const F = filters;
    Object.assign(this, { F, nClass, nFeat: F * POOL * POOL });
    let s = seed >>> 0;
    const rnd = () => { s = (s * 1664525 + 1013904223) >>> 0; return s / 4294967296 - 0.5; };
    const U = (n, sc) => Float32Array.from({ length: n }, () => rnd() * 2 * sc);
    this.p = {
      W: U(F * K * K, 1 / K), b: new Float32Array(F),
      Wd: U(this.nFeat * nClass, 1 / Math.sqrt(this.nFeat)), bd: new Float32Array(nClass),
    };
    this.g = {}; this.m = {}; this.v = {}; this.t = 0;
    for (const k in this.p) {
      const n = this.p[k].length;
      this.g[k] = new Float32Array(n); this.m[k] = new Float32Array(n); this.v[k] = new Float32Array(n);
    }
  }

  get numParams() { return Object.values(this.p).reduce((a, x) => a + x.length, 0); }

  // x: Float32Array(32*32), 0 = 검정 · 1 = 흰색
  // 반환: Z(합성곱 결과, ReLU 후) · P(풀링) · arg(풀링 자리) · out(확률)
  forward(x) {
    const { F, nClass, nFeat, p } = this;
    const Z = new Float32Array(F * OUT * OUT);
    for (let f = 0; f < F; f++) {
      const zf = f * OUT * OUT;
      Z.fill(p.b[f], zf, zf + OUT * OUT);
      for (let ky = 0; ky < K; ky++) for (let kx = 0; kx < K; kx++) {
        const w = p.W[(f * K + ky) * K + kx];
        for (let oy = 0; oy < OUT; oy++) {
          const ri = (oy + ky) * IMG + kx, ro = zf + oy * OUT;
          for (let ox = 0; ox < OUT; ox++) Z[ro + ox] += w * x[ri + ox];
        }
      }
    }
    for (let i = 0; i < Z.length; i++) if (Z[i] < 0) Z[i] = 0;
    const P = new Float32Array(nFeat), arg = new Int32Array(nFeat);
    for (let f = 0; f < F; f++) for (let py = 0; py < POOL; py++) for (let px = 0; px < POOL; px++) {
      const base = f * OUT * OUT + (py * 2) * OUT + px * 2;
      let bi = base, bv = Z[base];
      for (const d of [1, OUT, OUT + 1]) if (Z[base + d] > bv) { bv = Z[base + d]; bi = base + d; }
      const k = (f * POOL + py) * POOL + px;
      P[k] = bv; arg[k] = bi;
    }
    const out = new Float32Array(nClass);
    let mx = -Infinity;
    for (let c = 0; c < nClass; c++) {
      let s = p.bd[c];
      for (let i = 0; i < nFeat; i++) s += P[i] * p.Wd[i * nClass + c];
      out[c] = s; if (s > mx) mx = s;
    }
    let sum = 0;
    for (let c = 0; c < nClass; c++) { out[c] = Math.exp(out[c] - mx); sum += out[c]; }
    for (let c = 0; c < nClass; c++) out[c] /= sum;
    return { Z, P, arg, out };
  }

  predict(x) { return this.forward(x).out; }

  // 한 장의 기울기를 this.g 에 더한다 (scale = 1/배치 크기). 반환: loss
  accumulate(x, y, scale) {
    const { F, nClass, nFeat, p, g } = this;
    const { P, arg, out } = this.forward(x);
    const dOut = new Float32Array(nClass);
    for (let c = 0; c < nClass; c++) dOut[c] = (out[c] - (c === y ? 1 : 0)) * scale;
    const dZ = new Float32Array(F * OUT * OUT);
    for (let i = 0; i < nFeat; i++) {
      let s = 0;
      const pi = P[i];
      for (let c = 0; c < nClass; c++) {
        g.Wd[i * nClass + c] += pi * dOut[c];
        s += p.Wd[i * nClass + c] * dOut[c];
      }
      if (pi > 0) dZ[arg[i]] += s;     // 풀링 1등 자리로만, ReLU 가 0 이면 흐르지 않는다
    }
    for (let c = 0; c < nClass; c++) g.bd[c] += dOut[c];
    for (let f = 0; f < F; f++) {
      const zf = f * OUT * OUT;
      let sb = 0;
      for (let i = zf; i < zf + OUT * OUT; i++) sb += dZ[i];
      g.b[f] += sb;
      for (let ky = 0; ky < K; ky++) for (let kx = 0; kx < K; kx++) {
        let s = 0;
        for (let oy = 0; oy < OUT; oy++) {
          const ri = (oy + ky) * IMG + kx, ro = zf + oy * OUT;
          for (let ox = 0; ox < OUT; ox++) s += dZ[ro + ox] * x[ri + ox];
        }
        g.W[(f * K + ky) * K + kx] += s;
      }
    }
    return -Math.log(out[y] + 1e-9);
  }

  zeroGrad() { for (const k in this.g) this.g[k].fill(0); }

  adam(lr = 0.003, b1 = 0.9, b2 = 0.999, eps = 1e-8) {
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

  // 한 에폭. aug(x) 가 있으면 매번 새로 흔든 그림으로 배운다 (데이터 늘리기)
  fitEpoch(X, Y, { batch = 16, lr = 0.003, aug = null } = {}) {
    const N = X.length, order = Array.from({ length: N }, (_, i) => i);
    for (let i = N - 1; i > 0; i--) { const j = (Math.random() * (i + 1)) | 0; [order[i], order[j]] = [order[j], order[i]]; }
    let loss = 0;
    for (let s = 0; s < N; s += batch) {
      const idx = order.slice(s, s + batch);
      this.zeroGrad();
      for (const n of idx) loss += this.accumulate(aug ? aug(X[n]) : X[n], Y[n], 1 / idx.length);
      this.adam(lr);
    }
    return loss / N;
  }

  accuracy(X, Y) {
    let ok = 0;
    for (let n = 0; n < X.length; n++) {
      const o = this.predict(X[n]);
      if (o.indexOf(Math.max(...o)) === Y[n]) ok++;
    }
    return X.length ? ok / X.length : 0;
  }

  toJSON() {
    const o = { F: this.F, nClass: this.nClass, p: {} };
    for (const k in this.p) o.p[k] = Array.from(this.p[k], v => +v.toFixed(5));
    return o;
  }
  static fromJSON(o) {
    const m = new TinyCNN(o.nClass, { filters: o.F });
    for (const k in o.p) m.p[k].set(o.p[k]);
    return m;
  }
}
