// themakerrobot/teach-lab lib/sources.js (커밋 74f421a) 의 소리 부분(applySoundTransform)만 옮김 — 계산은 그대로다.
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
// ── 소리 특징 다듬기 ──
// YAMNet 이 내놓는 521개 점수는 sigmoid 출력이라 대부분 0 근처에 몰려 있고
// (521칸 중 60칸 남짓만 0이 아니다) 값도 작다. 그대로 넣으면 Dense 층이 쓸
// 것이 거의 없어서 잘 못 배운다. 제곱근으로 작은 값을 펴 주고 L2 로 크기를
// 맞추면 훨씬 잘 갈린다.
//
// 합성 소리 4종으로 재어 본 결과 (같은 분류기·같은 학습 조건, 10회 평균)
//   박수·휘파람·조용히 :  날것 67.5%  →  sqrt+L2 98.2%
//   4종 전부           :  날것 70.0%  →  sqrt+L2 91.9%
//
// 옛 모델은 날것으로 배웠으므로 프로젝트 파일에 어느 쪽인지 적어 둔다.
// featureTransform 이 없으면 'raw' 로 본다.
export const SOUND_TRANSFORM = 'sqrt-l2';

export function applySoundTransform(vec, kind) {
  if (kind !== 'sqrt-l2') return vec;              // 'raw' 또는 옛 모델
  const out = new Float32Array(vec.length);
  let sum = 0;
  for (let i = 0; i < vec.length; i++) {
    const v = Math.sqrt(vec[i] > 0 ? vec[i] : 0);
    out[i] = v;
    sum += v * v;
  }
  const n = Math.sqrt(sum) || 1;
  for (let i = 0; i < out.length; i++) out[i] /= n;
  return out;
}

