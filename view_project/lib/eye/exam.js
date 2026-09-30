// themakerrobot/ml-lab acts/eye/exam.js (커밋 e17acd7) 에서 옮김 — 계산·상수는 그대로 두었다.
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
// AI 눈 활동 — 속이기 시험 (DOM 없음)
// ═══════════════════════════════════════════════════════════
// 모은 그림을 정해진 방법으로 바꿔서 몇 %를 맞히는지 잰다.
// 흔드는 값은 시드로 고정 — 학습을 여러 번 해도 같은 시험지로 비교된다 (수업 3차시의 전후 비교표).

import { transform } from './imgops.js';

export const EXAMS = {
  straight: () => ({}),
  tilt: r => ({ rot: (r() < 0.5 ? -1 : 1) * (0.5 + r() * 0.4) }),                  // 30~50° 기울이기
  small: r => ({ scale: 0.6, dx: (r() - 0.5) * 10, dy: (r() - 0.5) * 10 }),        // 작게, 구석에
  dark: () => ({ bright: 0.35 }),                                                   // 어두운 방
};

export function seeded(seed) {
  let s = seed >>> 0;
  return () => { s = (s * 1664525 + 1013904223) >>> 0; return s / 4294967296; };
}

export function runExam(model, X, Y) {
  const out = {};
  for (const [name, make] of Object.entries(EXAMS)) {
    const r = seeded(12345);
    out[name] = model.accuracy(X.map(x => transform(x, make(r))), Y);
  }
  return out;
}
