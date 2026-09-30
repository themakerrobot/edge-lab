// themakerrobot/ml-lab acts/eye/imgops.js (커밋 e17acd7) 에서 옮김 — 계산·상수는 그대로 두었다.
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
// AI 눈 활동 — 그림 다루기 (DOM 없음)
// ═══════════════════════════════════════════════════════════
//  · transform : 돌리기 · 옮기기 · 크기 · 밝기 (데이터 늘리기와 "AI 속이기" 가 같이 쓴다)
//  · makeAugment : 배울 때마다 조금씩 다르게 흔드는 함수
//  · drawShape : 예시 그림 세트 — 종이에 펜으로 그린 ○ △ ☆ □ 처럼 만든다
//
// 그림은 Float32Array(32*32), 0 = 검정 잉크 · 1 = 흰 종이

import { IMG } from './cnn.js';

// 역방향 매핑 + 양선형 보간. 밖으로 나간 자리는 가장자리 색으로 채운다
export function transform(x, { rot = 0, dx = 0, dy = 0, scale = 1, bright = 1 } = {}) {
  const out = new Float32Array(IMG * IMG), c = (IMG - 1) / 2;
  const cs = Math.cos(-rot), sn = Math.sin(-rot);
  const at = (xx, yy) => {
    xx = xx < 0 ? 0 : xx > IMG - 1 ? IMG - 1 : xx;
    yy = yy < 0 ? 0 : yy > IMG - 1 ? IMG - 1 : yy;
    return x[yy * IMG + xx];
  };
  for (let y = 0; y < IMG; y++) for (let x2 = 0; x2 < IMG; x2++) {
    const ux = (x2 - c - dx) / scale, uy = (y - c - dy) / scale;
    const sx = cs * ux - sn * uy + c, sy = sn * ux + cs * uy + c;
    const x0 = Math.floor(sx), y0 = Math.floor(sy), fx = sx - x0, fy = sy - y0;
    const v = (1 - fx) * (1 - fy) * at(x0, y0) + fx * (1 - fy) * at(x0 + 1, y0)
            + (1 - fx) * fy * at(x0, y0 + 1) + fx * fy * at(x0 + 1, y0 + 1);
    out[y * IMG + x2] = Math.min(1, Math.max(0, v * bright));
  }
  return out;
}

// opts: { rotate, shift, bright } 켜진 것만 흔든다
export function makeAugment(opts, rnd = Math.random) {
  if (!opts || !(opts.rotate || opts.shift || opts.bright)) return null;
  return x => transform(x, {
    rot: opts.rotate ? (rnd() - 0.5) * 2 * Math.PI / 4 : 0,          // ±45°
    dx: opts.shift ? (rnd() - 0.5) * 8 : 0,                           // ±4칸
    dy: opts.shift ? (rnd() - 0.5) * 8 : 0,
    scale: opts.shift ? 0.8 + rnd() * 0.35 : 1,
    bright: opts.bright ? 0.45 + rnd() * 0.65 : 1,                    // 어두운 방 ~ 밝은 방
  });
}

// ── 예시 그림 세트 ─────────────────────────────────────────
export const SHAPES = ['circle', 'triangle', 'star', 'square'];

function segDist(px, py, ax, ay, bx, by) {
  const dx = bx - ax, dy = by - ay, L = dx * dx + dy * dy || 1;
  let t = ((px - ax) * dx + (py - ay) * dy) / L;
  t = t < 0 ? 0 : t > 1 ? 1 : t;
  return Math.hypot(ax + t * dx - px, ay + t * dy - py);
}

function polygon(n, r, rot, inner = 0) {
  const pts = [], m = inner ? n * 2 : n;
  for (let i = 0; i < m; i++) {
    const a = rot - Math.PI / 2 + i * 2 * Math.PI / m;
    const rr = inner && i % 2 ? r * inner : r;
    pts.push([Math.cos(a) * rr, Math.sin(a) * rr]);
  }
  return pts;
}

// 종이(밝은 바탕) 위에 펜 선으로 그린 도형. rnd 를 넘기면 매번 모양이 조금씩 다르다
export function drawShape(kind, rnd = Math.random, { rot = null, bright = 1 } = {}) {
  const r = 8 + rnd() * 5, cx = 15.5 + (rnd() - 0.5) * 6, cy = 15.5 + (rnd() - 0.5) * 6;
  const angle = rot === null ? (rnd() - 0.5) * 0.35 : rot;          // 기본은 거의 똑바로
  const pen = 0.9 + rnd() * 0.9, paper = 0.8 + rnd() * 0.15, ink = 0.08 + rnd() * 0.12;
  const pts = kind === 'triangle' ? polygon(3, r * 1.1, angle)
    : kind === 'square' ? polygon(4, r * 1.05, angle + Math.PI / 4)
    : kind === 'star' ? polygon(5, r * 1.15, angle, 0.45) : null;
  const img = new Float32Array(IMG * IMG);
  for (let y = 0; y < IMG; y++) for (let x = 0; x < IMG; x++) {
    let cover = 0;
    for (const [sx, sy] of [[0.25, 0.25], [0.75, 0.25], [0.25, 0.75], [0.75, 0.75]]) {
      const px = x + sx - cx, py = y + sy - cy;
      let d;
      if (!pts) d = Math.abs(Math.hypot(px, py) - r);
      else {
        d = Infinity;
        for (let i = 0; i < pts.length; i++) {
          const [ax, ay] = pts[i], [bx, by] = pts[(i + 1) % pts.length];
          d = Math.min(d, segDist(px, py, ax, ay, bx, by));
        }
      }
      if (d <= pen / 2) cover++;
    }
    const v = paper + (ink - paper) * cover / 4 + (rnd() - 0.5) * 0.06;
    img[y * IMG + x] = Math.min(1, Math.max(0, v * bright));
  }
  return img;
}
