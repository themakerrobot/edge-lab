// themakerrobot/ml-lab acts/word/presets.js (커밋 e17acd7) 에서 옮김. 계산·상수는 원본 그대로 둔다.
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
// 문장 활동 — 예시 글 (전부 이 저장소에서 새로 쓴 글. 저작권 걱정 없음)
// ═══════════════════════════════════════════════════════════
// 수업 포인트
//  · animals : 같은 틀(누가 / 어디서 / 무엇을)이 반복돼 AI가 틀을 빨리 배운다
//  · times   : 2~6단만 가르친다. "7 × 8 =" 을 넣으면 AI가 그럴듯한 답을 지어낸다
//              → "AI는 계산하지 않고 글자 모양을 흉내 낸다" (환각)
//  · poem    : "~하면 ~해요" 틀. 온도를 올리면 새로운 문장을 지어낸다

function timesTable(from, to, sep) {
  const out = [];
  for (let a = from; a <= to; a++)
    for (let b = 1; b <= 9; b++) out.push(`${a} ${sep} ${b} = ${a * b}`);
  return out.join('\n');
}

export const PRESETS = {
  ko: [
    {
      id: 'animals', label: '동물',
      text: [
        '토끼는 산에서 뛰어요. 토끼는 풀을 먹어요. 거북이는 바다에서 헤엄쳐요. 거북이는 천천히 걸어요.',
        '강아지는 마당에서 뛰어요. 강아지는 뼈를 먹어요. 고양이는 지붕에서 자요. 고양이는 생선을 먹어요.',
        '새는 하늘에서 날아요. 새는 벌레를 먹어요. 물고기는 바다에서 헤엄쳐요. 물고기는 천천히 자요.',
        '토끼는 천천히 걸어요. 강아지는 하늘을 봐요. 고양이는 마당에서 뛰어요. 새는 지붕에서 자요.',
      ].join('\n'),
      seed: '강아지는 ',
    },
    {
      id: 'times', label: '구구단',
      text: timesTable(2, 6, '×'),
      seed: '7 × 8 =',
    },
    {
      id: 'poem', label: '날씨 동시',
      text: [
        '바람이 불면 나뭇잎이 춤을 춰요.',
        '비가 오면 우산이 꽃처럼 피어요.',
        '해가 뜨면 창문이 반짝 웃어요.',
        '눈이 오면 마당이 하얀 종이가 돼요.',
        '바람이 불면 구름이 멀리 여행을 가요.',
        '비가 오면 개구리가 노래를 불러요.',
        '해가 지면 하늘이 주황색 옷을 입어요.',
        '눈이 오면 강아지가 발자국 도장을 찍어요.',
      ].join('\n'),
      seed: '비가 오면 ',
    },
  ],
  en: [
    {
      id: 'animals', label: 'Animals',
      text: [
        'The rabbit runs on the hill. The rabbit eats grass. The turtle swims in the sea. The turtle walks slowly.',
        'The dog runs in the yard. The dog eats a bone. The cat sleeps on the roof. The cat eats fish.',
        'The bird flies in the sky. The bird eats bugs. The fish swims in the sea. The fish sleeps slowly.',
        'The rabbit walks slowly. The dog looks at the sky. The cat runs in the yard. The bird sleeps on the roof.',
      ].join('\n'),
      seed: 'The dog ',
    },
    {
      id: 'times', label: 'Times table',
      text: timesTable(2, 6, 'x'),
      seed: '7 x 8 =',
    },
    {
      id: 'poem', label: 'Weather poem',
      text: [
        'When the wind blows, the leaves dance.',
        'When it rains, umbrellas bloom like flowers.',
        'When the sun rises, the window smiles.',
        'When it snows, the yard turns into white paper.',
        'When the wind blows, the clouds travel far.',
        'When it rains, the frogs sing a song.',
        'When the sun sets, the sky wears orange.',
        'When it snows, the puppy stamps its paws.',
      ].join('\n'),
      seed: 'When it rains, ',
    },
  ],
};
