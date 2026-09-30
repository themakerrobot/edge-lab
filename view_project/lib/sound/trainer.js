// themakerrobot/teach-lab lib/trainer.js (커밋 74f421a) 에서 옮김.
// edge-lab 에서 고친 점 (층 구성·EPOCHS·BATCH·검증 비율·혼동 행렬은 그대로다)
//   · TF.js 는 edge-lab 이 이미 가진 /lib/tf.min-3.11.0.js 를 처음 배울 때 불러 쓴다 (따로 들여오지 않는다)
//   · 백엔드는 cpu 먼저 — 입력이 521차원·작은 층이라 webgl 셰이더를 짓는 시간이 학습보다 길다
//   · 에폭 사이 쉬기를 tf.nextFrame 대신 rAF·setTimeout 중 빠른 쪽으로 —
//     셸에서 창이 가려지면 rAF 가 멈출 수 있는데, 가려진 채로도 학습은 끝까지 가야 한다(끝나면 알림)
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
// 분류기 학습 — TF.js
// ═══════════════════════════════════════════════════════════
// 입력 521차원(YAMNet 점수) → Dense(64, relu) → Dropout(0.2) → Dense(N, softmax)
// adam(0.001) / categoricalCrossentropy / epochs 40 / batch 16 / validationSplit 0.2
//
// tf 는 /lib/tf.min-3.11.0.js 가 전역으로 제공한다 (loadTf 가 처음 한 번 붙인다).

export const EPOCHS = 40;
export const HIDDEN = 64;
const BATCH = 16;
const TF_SRC = '/lib/tf.min-3.11.0.js';

// validationSplit 은 뒤쪽 20% 를 떼어 간다. 예시가 너무 적으면 한 장도 안 남아
// 학습이 멈추므로, 이 수보다 적으면 검증을 건너뛴다.
const MIN_FOR_VALID = 15;

// 1MB 가 넘는 파일이라 페이지를 열 때가 아니라 처음 배울 때 읽는다
let tfPromise = null;
function loadTf() {
  if (window.tf) return Promise.resolve(window.tf);
  if (!tfPromise) {
    tfPromise = new Promise((ok, no) => {
      const s = document.createElement('script');
      s.src = TF_SRC;
      s.onload = () => ok(window.tf);
      s.onerror = () => { tfPromise = null; s.remove(); no(new Error('tf.js load failed')); };
      document.head.appendChild(s);
    });
  }
  return tfPromise;
}

let backendPromise = null;
export function backendReady() {
  if (!backendPromise) {
    backendPromise = loadTf().then(async tf => {
      for (const b of ['cpu', 'webgl']) {
        try {
          if (await tf.setBackend(b)) { await tf.ready(); return b; }
        } catch (e) { /* 다음 백엔드로 */ }
      }
      await tf.ready();
      return tf.getBackend();
    }).catch(e => { backendPromise = null; throw e; });
  }
  return backendPromise;
}

// 한 프레임 양보 — 진행률 바가 그려지게. 가려진 창에서는 rAF 가 안 올 수 있어 시간으로도 깨운다
function breathe() {
  return new Promise(ok => {
    let done = false;
    const go = () => { if (!done) { done = true; ok(); } };
    requestAnimationFrame(go);
    setTimeout(go, 30);
  });
}

export function buildModel(dim, numClasses) {
  const m = tf.sequential();
  m.add(tf.layers.dense({ inputShape: [dim], units: HIDDEN, activation: 'relu' }));
  m.add(tf.layers.dropout({ rate: 0.2 }));
  m.add(tf.layers.dense({ units: numClasses, activation: 'softmax' }));
  m.compile({
    optimizer: tf.train.adam(0.001),
    loss: 'categoricalCrossentropy',
    metrics: ['accuracy'],
  });
  return m;
}

// vecs: Float32Array[], labels: int[] (같은 길이)
// onEpoch(epoch, total, {loss, acc, valLoss, valAcc}) 로 진행을 알린다.
export async function trainModel(vecs, labels, numClasses, dim, onEpoch) {
  await backendReady();

  const xs = vecs.slice(), ys = labels.slice();
  // validationSplit 은 뒤쪽을 떼므로 반드시 먼저 섞는다
  tf.util.shuffleCombo(xs, ys);

  // 벡터를 한 덩어리로 이어 붙여 텐서를 만든다 (521차원 × 수백 장)
  const flat = new Float32Array(xs.length * dim);
  xs.forEach((v, i) => flat.set(v, i * dim));
  const X = tf.tensor2d(flat, [xs.length, dim]);
  const Y = tf.oneHot(tf.tensor1d(ys, 'int32'), numClasses);

  const model = buildModel(dim, numClasses);
  const history = [];
  try {
    await model.fit(X, Y, {
      epochs: EPOCHS,
      batchSize: BATCH,
      shuffle: true,
      validationSplit: xs.length >= MIN_FOR_VALID ? 0.2 : 0,
      callbacks: {
        onEpochEnd: async (ep, logs) => {
          const rec = {
            loss: logs.loss,
            acc: logs.acc != null ? logs.acc : logs.accuracy,
            valLoss: logs.val_loss,
            valAcc: logs.val_acc != null ? logs.val_acc : logs.val_accuracy,
          };
          history.push(rec);
          if (onEpoch) onEpoch(ep + 1, EPOCHS, rec);
          await breathe();               // 진행률 바가 멈추지 않게 한 프레임 양보
        },
      },
    });
  } catch (e) {
    X.dispose(); Y.dispose(); model.dispose();
    throw e;
  }

  // 전체 예시로 헷갈린 표(혼동 행렬)를 만든다.
  // 수업용이라 "어떤 종류끼리 헷갈리는지" 경향만 보이면 된다.
  const pred = tf.tidy(() => model.predict(X).argMax(-1));
  const predArr = await pred.data();
  pred.dispose();
  const confusion = Array.from({ length: numClasses }, () => new Array(numClasses).fill(0));
  let correct = 0;
  for (let i = 0; i < ys.length; i++) {
    confusion[ys[i]][predArr[i]]++;
    if (ys[i] === predArr[i]) correct++;
  }
  const accuracy = ys.length ? correct / ys.length : 0;

  X.dispose(); Y.dispose();
  return { model, history, confusion, accuracy };
}
