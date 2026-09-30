// themakerrobot/ml-lab acts/eye/worker.js (커밋 e17acd7) 에서 옮김 — 계산·상수는 그대로 두었다.
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
// AI 눈 활동 — 학습 워커
// ═══════════════════════════════════════════════════════════
// 메인 → { type:'train', X, Y, nClass, aug, epochs }
// 워커 → { type:'progress', epoch, epochs, loss, acc }
//        { type:'done', model, acc, wrong, exam }
//
// exam = "속이기 시험" (exam.js)

import { TinyCNN } from './cnn.js';
import { makeAugment } from './imgops.js';
import { runExam } from './exam.js';

onmessage = async ({ data: m }) => {
  if (m.type !== 'train') return;
  const X = m.X.map(a => Float32Array.from(a)), Y = m.Y;
  const model = new TinyCNN(m.nClass, { seed: (Math.random() * 1e9) | 0 });
  const aug = makeAugment(m.aug);
  for (let e = 0; e < m.epochs; e++) {
    const loss = model.fitEpoch(X, Y, { aug });
    const acc = (e % 5 === 4 || e === m.epochs - 1) ? model.accuracy(X, Y) : null;
    postMessage({ type: 'progress', epoch: e + 1, epochs: m.epochs, loss, acc });
    await new Promise(r => setTimeout(r, 0));
  }
  // 틀린 그림 번호 (배운 그림 그대로 물었는데도 틀린 것)
  const wrong = [];
  X.forEach((x, n) => {
    const o = model.predict(x), a = o.indexOf(Math.max(...o));
    if (a !== Y[n]) wrong.push([n, a]);
  });
  postMessage({ type: 'done', model: model.toJSON(), acc: model.accuracy(X, Y), wrong, exam: runExam(model, X, Y) });
};
