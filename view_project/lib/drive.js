/* 자동차 가르치기(/drive) — 트랙 · 차 · AI 운전사. 화면(DOM)은 쓰지 않는다.
 *
 * 흐름: 내가 운전한다 → 차의 센서 7개와 내가 고른 운전(왼쪽·곧게·오른쪽)이 쌓인다 →
 * 작은 신경망이 그 짝을 배운다 → AI 가 센서만 보고 운전한다 → 처음 보는 트랙에서 시험한다.
 * 서버의 AI 는 쓰지 않는다 — 데이터가 수천 장면이라 브라우저 안에서 1초 안에 배운다.
 * 그래서 모델 준비 중에도 바로 된다.
 *
 * 쓰는 법 (브라우저):
 *     <script src="/lib/drive.js"></script>
 *     var D = EL_DRIVE;  D.TRACKS, D.buildTrack, D.Car, D.Policy, D.teacher, ...
 * node 에서도 require 로 읽힌다 (시험용).
 *
 * 출처: themakerrobot/ml-lab 의 acts/drive/track.js · sim.js · policy.js (커밋 e17acd7) 를
 * ES 모듈에서 이 저장소의 방식(전역 하나, var)으로 옮겼다. 계산은 바꾸지 않았다 —
 * 상수(속도·회전·센서 각도)를 바꾸면 ml-lab DEVELOP.md 에서 잰 "양쪽 30장면이면 세 트랙 완주"
 * 가 더는 맞지 않는다. 저장소는 담지 않고 이 파일에 옮겨 적었으므로 MIT 고지를 함께 둔다.
 *
 * ---------------------------------------------------------------------------
 * MIT License
 *
 * Copyright (c) 2026 themakerrobot
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all
 * copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
 * SOFTWARE.
 * ---------------------------------------------------------------------------
 */
(function (root) {
  "use strict";

  /* ════════ 트랙 ════════
   * 트랙 = 닫힌 중심선(Catmull-Rom 곡선) + 폭. 도로 판정은 픽셀 마스크(Uint8Array) 로 한다 —
   * 센서 광선을 쏠 때 한 점을 O(1) 로 본다. 세계 좌표는 800×520 고정, 화면에서 늘린다. */
  var WORLD_W = 800, WORLD_H = 520;

  function oval() {
    var out = [];
    for (var i = 0; i < 12; i++) {
      var a = i / 12 * Math.PI * 2;
      out.push([400 + 300 * Math.cos(a), 260 + 180 * Math.sin(a)]);
    }
    return out;
  }

  /* 차는 pts[0] 에서 pts[1] 쪽으로 출발한다 */
  var TRACKS = [
    { id: "oval", ko: "둥근 트랙", en: "Round track", width: 74, ctrl: oval() },
    { id: "wavy", ko: "구불구불 트랙", en: "Wavy track", width: 70,
      ctrl: [[110, 130], [300, 90], [400, 200], [500, 90], [690, 120], [720, 300],
             [640, 440], [470, 390], [330, 450], [140, 410], [90, 270]] },
    { id: "test", ko: "처음 보는 트랙", en: "New track", width: 70, unseen: true,
      ctrl: [[100, 250], [190, 100], [350, 130], [420, 250], [560, 110], [720, 170],
             [710, 400], [540, 450], [420, 380], [270, 450], [120, 420]] }
  ];

  function spline(ctrl, per) {
    per = per || 24;
    var n = ctrl.length, out = [];
    for (var i = 0; i < n; i++) {
      var p0 = ctrl[(i - 1 + n) % n], p1 = ctrl[i], p2 = ctrl[(i + 1) % n], p3 = ctrl[(i + 2) % n];
      for (var s = 0; s < per; s++) {
        var t = s / per, t2 = t * t, t3 = t2 * t;
        var f = function (a, b, c, d) {
          return 0.5 * (2 * b + (-a + c) * t + (2 * a - 5 * b + 4 * c - d) * t2 + (-a + 3 * b - 3 * c + d) * t3);
        };
        out.push([f(p0[0], p1[0], p2[0], p3[0]), f(p0[1], p1[1], p2[1], p3[1])]);
      }
    }
    return out;
  }

  function buildTrack(def) {
    var pts = spline(def.ctrl), n = pts.length, hw = def.width / 2;
    var mask = new Uint8Array(WORLD_W * WORLD_H);
    /* 선분마다 주변 상자만 훑어서 도로 픽셀을 칠한다 */
    for (var i = 0; i < n; i++) {
      var ax = pts[i][0], ay = pts[i][1], bx = pts[(i + 1) % n][0], by = pts[(i + 1) % n][1];
      var dx = bx - ax, dy = by - ay, L2 = dx * dx + dy * dy || 1;
      var x0 = Math.max(0, Math.floor(Math.min(ax, bx) - hw)), x1 = Math.min(WORLD_W - 1, Math.ceil(Math.max(ax, bx) + hw));
      var y0 = Math.max(0, Math.floor(Math.min(ay, by) - hw)), y1 = Math.min(WORLD_H - 1, Math.ceil(Math.max(ay, by) + hw));
      for (var y = y0; y <= y1; y++) {
        for (var x = x0; x <= x1; x++) {
          var t = ((x - ax) * dx + (y - ay) * dy) / L2;
          t = t < 0 ? 0 : t > 1 ? 1 : t;
          var ex = ax + t * dx - x, ey = ay + t * dy - y;
          if (ex * ex + ey * ey <= hw * hw) mask[y * WORLD_W + x] = 1;
        }
      }
    }
    var start = { x: pts[0][0], y: pts[0][1], th: Math.atan2(pts[1][1] - pts[0][1], pts[1][0] - pts[0][0]) };
    return { def: def, pts: pts, n: n, hw: hw, mask: mask, start: start };
  }

  function onRoad(track, x, y) {
    var xi = x | 0, yi = y | 0;
    if (xi < 0 || yi < 0 || xi >= WORLD_W || yi >= WORLD_H) return false;
    return track.mask[yi * WORLD_W + xi] === 1;
  }

  /* 지난번 위치 근처에서 가장 가까운 중심선 점 번호 (한 바퀴 진행도 계산용) */
  function nearestIdx(track, x, y, around) {
    var pts = track.pts, n = track.n, best = around, bd = Infinity;
    for (var k = -12; k <= 30; k++) {
      var i = ((around + k) % n + n) % n;
      var ddx = pts[i][0] - x, ddy = pts[i][1] - y, d = ddx * ddx + ddy * ddy;
      if (d < bd) { bd = d; best = i; }
    }
    return best;
  }

  /* ════════ 차와 센서 ════════
   * 차는 일정한 속도로 달리고 운전은 셋 중 하나만 한다: 0 왼쪽 · 1 곧게 · 2 오른쪽.
   * 센서는 앞쪽 부채꼴 광선 7개, 도로 끝까지 거리를 0~1 로 준다(1 = 멀다).
   * AI 는 이 숫자 7개만 본다 — 사람이 보는 트랙 그림은 못 본다. */
  var RAY_DEG = [-90, -60, -30, 0, 30, 60, 90];
  var RAY_MAX = 160;           // 센서가 볼 수 있는 가장 먼 거리
  var SPEED = 120;             // 초당 이동 (세계 좌표)
  var TURN = 2.8;              // 초당 회전 (라디안)
  var DT = 1 / 60;             // 한 번 움직이는 시간
  var ACTIONS = [-1, 0, 1];    // 왼쪽 · 곧게 · 오른쪽 (화면 y 가 아래쪽이라 왼쪽이 -)

  function Car(track) { this.reset(track); }
  Car.prototype.reset = function (track) {
    this.track = track;
    this.x = track.start.x; this.y = track.start.y; this.th = track.start.th;
    this.idx = 0; this.laps = 0; this.dist = 0; this.crashed = false;
  };
  Car.prototype.sense = function () {
    var self = this;
    return RAY_DEG.map(function (d) {
      var a = self.th + d * Math.PI / 180, c = Math.cos(a), s = Math.sin(a), r = 0;
      while (r < RAY_MAX && onRoad(self.track, self.x + c * r, self.y + s * r)) r += 2;
      return Math.min(r, RAY_MAX) / RAY_MAX;
    });
  };
  /* action: 0/1/2. 돌려주는 값: 부딪혔는지 */
  Car.prototype.step = function (action) {
    if (this.crashed) return true;
    this.th += ACTIONS[action] * TURN * DT;
    this.x += Math.cos(this.th) * SPEED * DT;
    this.y += Math.sin(this.th) * SPEED * DT;
    this.dist += SPEED * DT;
    /* 차 앞머리와 가운데가 도로 위에 있어야 한다 */
    var fx = this.x + Math.cos(this.th) * 9, fy = this.y + Math.sin(this.th) * 9;
    if (!onRoad(this.track, this.x, this.y) || !onRoad(this.track, fx, fy)) this.crashed = true;
    /* 진행도: 중심선 번호가 끝에서 처음으로 넘어가면 한 바퀴 */
    var n = this.track.n, prev = this.idx;
    this.idx = nearestIdx(this.track, this.x, this.y, prev);
    if (prev > n * 0.8 && this.idx < n * 0.2) this.laps++;
    else if (prev < n * 0.2 && this.idx > n * 0.8) this.laps--;
    return this.crashed;
  };
  /* 지금까지 간 정도 (바퀴 단위, 1.5 = 한 바퀴 반) */
  Object.defineProperty(Car.prototype, "progress", {
    get: function () { return this.laps + this.idx / this.track.n; }
  });

  /* 시험용 "선생님" 운전 — 좌우 센서를 비교해 넓은 쪽으로 튼다. 화면에는 안 나온다. */
  function teacher(s) {
    var left = s[1] + s[2], right = s[4] + s[5], diff = right - left;
    if (s[3] < 0.35) return diff > 0 ? 2 : 0;        // 앞이 막히면 크게 튼다
    if (diff > 0.12) return 2;
    if (diff < -0.12) return 0;
    return 1;
  }

  /* ════════ AI 운전사 ════════
   * 센서 7개 → Dense(24, tanh) → Dense(3) → softmax → 왼쪽 / 곧게 / 오른쪽.
   * 한 번 학습에 1초도 안 걸려 워커 없이 화면 스레드에서 한 에폭씩 끊어 돌린다(fitEpoch). */
  function Policy(nIn, opt) {
    nIn = nIn || 7; opt = opt || {};
    var hid = opt.hid || 24, nOut = opt.nOut || 3, s = (opt.seed || 1) >>> 0;
    this.nIn = nIn; this.hid = hid; this.nOut = nOut;
    var rnd = function () { s = (s * 1664525 + 1013904223) >>> 0; return s / 4294967296 - 0.5; };
    var U = function (n, sc) { var a = new Float32Array(n); for (var i = 0; i < n; i++) a[i] = rnd() * 2 * sc; return a; };
    this.p = { W1: U(nIn * hid, 1 / Math.sqrt(nIn)), b1: new Float32Array(hid),
               W2: U(hid * nOut, 1 / Math.sqrt(hid)), b2: new Float32Array(nOut) };
    this.g = {}; this.m = {}; this.v = {}; this.t = 0;
    for (var k in this.p) {
      var n = this.p[k].length;
      this.g[k] = new Float32Array(n); this.m[k] = new Float32Array(n); this.v[k] = new Float32Array(n);
    }
  }
  Policy.prototype.numParams = function () {
    var n = 0; for (var k in this.p) n += this.p[k].length; return n;
  };
  Policy.prototype.forward = function (x) {
    var nIn = this.nIn, hid = this.hid, nOut = this.nOut, p = this.p;
    var h = new Float32Array(hid), P = new Float32Array(nOut), j, i, k, s;
    for (j = 0; j < hid; j++) {
      s = p.b1[j];
      for (i = 0; i < nIn; i++) s += x[i] * p.W1[i * hid + j];
      h[j] = Math.tanh(s);
    }
    var mx = -Infinity;
    for (k = 0; k < nOut; k++) {
      s = p.b2[k];
      for (j = 0; j < hid; j++) s += h[j] * p.W2[j * nOut + k];
      P[k] = s; if (s > mx) mx = s;
    }
    var sum = 0;
    for (k = 0; k < nOut; k++) { P[k] = Math.exp(P[k] - mx); sum += P[k]; }
    for (k = 0; k < nOut; k++) P[k] /= sum;
    return { h: h, P: P };
  };
  Policy.prototype.predict = function (x) { return this.forward(x).P; };
  /* 배치 기울기를 this.g 에 쌓고 평균 loss 를 돌려준다 */
  Policy.prototype.grad = function (X, Y, idx) {
    var nIn = this.nIn, hid = this.hid, nOut = this.nOut, p = this.p, g = this.g, key;
    for (key in g) g[key].fill(0);
    var B = idx.length, dh = new Float32Array(hid), loss = 0;
    for (var q = 0; q < B; q++) {
      var n = idx[q], x = X[n], y = Y[n], f = this.forward(x), h = f.h, P = f.P, j, k, i, d, s;
      loss -= Math.log(P[y] + 1e-9);
      for (k = 0; k < nOut; k++) {
        d = (P[k] - (k === y ? 1 : 0)) / B;
        g.b2[k] += d;
        for (j = 0; j < hid; j++) g.W2[j * nOut + k] += h[j] * d;
      }
      for (j = 0; j < hid; j++) {
        s = 0;
        for (k = 0; k < nOut; k++) s += p.W2[j * nOut + k] * ((P[k] - (k === y ? 1 : 0)) / B);
        dh[j] = s * (1 - h[j] * h[j]);
      }
      for (j = 0; j < hid; j++) {
        g.b1[j] += dh[j];
        for (i = 0; i < nIn; i++) g.W1[i * hid + j] += x[i] * dh[j];
      }
    }
    return loss / B;
  };
  Policy.prototype.adam = function (lr, b1, b2, eps) {
    lr = lr || 0.01; b1 = b1 || 0.9; b2 = b2 || 0.999; eps = eps || 1e-8;
    this.t++;
    var c1 = 1 - Math.pow(b1, this.t), c2 = 1 - Math.pow(b2, this.t);
    for (var k in this.p) {
      var w = this.p[k], g = this.g[k], m = this.m[k], v = this.v[k];
      for (var i = 0; i < w.length; i++) {
        m[i] = b1 * m[i] + (1 - b1) * g[i];
        v[i] = b2 * v[i] + (1 - b2) * g[i] * g[i];
        w[i] -= lr * (m[i] / c1) / (Math.sqrt(v[i] / c2) + eps);
      }
    }
  };
  /* 한 에폭: 섞어서 batch 씩. 돌려주는 값 { loss, acc } (acc = 이번 에폭 전체에서 맞힌 비율) */
  Policy.prototype.fitEpoch = function (X, Y, opt) {
    opt = opt || {};
    var batch = opt.batch || 32, lr = opt.lr || 0.01, N = X.length, order = [], i, j, tmp;
    for (i = 0; i < N; i++) order.push(i);
    for (i = N - 1; i > 0; i--) { j = (Math.random() * (i + 1)) | 0; tmp = order[i]; order[i] = order[j]; order[j] = tmp; }
    var tot = 0, nb = 0;
    for (var s = 0; s < N; s += batch) {
      tot += this.grad(X, Y, order.slice(s, s + batch)); nb++;
      this.adam(lr);
    }
    var ok = 0;
    for (var n = 0; n < N; n++) if (argmax(this.predict(X[n])) === Y[n]) ok++;
    return { loss: tot / nb, acc: ok / N };
  };

  function argmax(P) {
    var b = 0;
    for (var i = 1; i < P.length; i++) if (P[i] > P[b]) b = i;
    return b;
  }

  var API = {
    WORLD_W: WORLD_W, WORLD_H: WORLD_H, TRACKS: TRACKS, buildTrack: buildTrack, onRoad: onRoad,
    RAY_DEG: RAY_DEG, RAY_MAX: RAY_MAX, SPEED: SPEED, TURN: TURN, DT: DT,
    Car: Car, teacher: teacher, Policy: Policy, argmax: argmax
  };
  if (typeof module === "object" && module.exports) module.exports = API;
  else root.EL_DRIVE = API;
})(this);
