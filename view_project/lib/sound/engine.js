// themakerrobot/teach-lab lib/sound.js (커밋 74f421a) 에서 옮김.
// edge-lab 에서 고친 점 (나머지 — 창 길이·링 버퍼·분류 주기 — 는 그대로다)
//   · wasm·모델 경로를 이 파일 기준(/lib/sound/…)으로 — 서버 정적 경로가 /lib 뿐이라서
//   · 한 창의 모양(파형 24칸)을 같이 넘긴다 — 예시 카드의 작은 파형 그림용
//   · labelNames() — 마이크 없이 무음 한 창을 분류해 521개 이름표를 미리 얻는다
//   · 파형 그리기(drawLevels)·마이크 목록(listMics)은 뺐다 — 화면(page.js)이 직접 그리고, 마이크는 기본 장치만 쓴다
//   · start() 를 두 곳에서 동시에 불러도 마이크를 한 번만 연다
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
// 소리 엔진 — 마이크 + YAMNet 분류 (MediaPipe Tasks Audio)
// ═══════════════════════════════════════════════════════════
// 전부 셀프호스팅이다: wasm 은 ./vendor/tasks-audio/, 모델은 ./models/yamnet.tflite.
//
//  · YAMNet 은 소리 한 창(0.975초)을 521가지 점수로 바꾼다 — 이 521개 숫자가
//    "AI 가 듣는 소리" 이고, 그대로 학습에 들어간다
//  · 마이크는 16kHz 모노로 받는다 (YAMNet 기대 입력. 브라우저가 리샘플한다)
//  · 250ms 마다 최근 창을 분류한다 — 모으기·실시간 표시 공용
//  · 소리는 어디로도 전송하지 않는다. 녹음 파일도 만들지 않는다

import { FilesetResolver, AudioClassifier } from './vendor/tasks-audio/audio_bundle.mjs';

// 페이지 주소와 상관없이 이 모듈 옆의 파일을 가리킨다 (끝의 / 없이 — FilesetResolver 가 붙인다)
const WASM_DIR = new URL('./vendor/tasks-audio', import.meta.url).href;
const MODEL = new URL('./models/yamnet.tflite', import.meta.url).href;
const RATE = 16000;            // YAMNet 입력 샘플레이트
const TICK_MS = 250;           // 분류 주기
export const SOUND_DIM = 521;
export const WAVE_BINS = 24;   // 예시 카드 파형 칸 수

// YAMNet 한 창의 길이. 16000(1초)이 아니라 15600(0.975초)이다.
// 1초를 통째로 넣으면 MediaPipe 가 창을 둘로 쪼개는데, 둘째 창은 400샘플만
// 진짜이고 나머지는 0으로 채운 것이라 늘 "Silence" 가 1등으로 나온다.
// 딱 한 창만 나오게 잘라서 넣는다.
export const WINDOW_SECONDS = 15600 / RATE;

let clfPromise = null;
function ensureClassifier() {
  if (!clfPromise) {
    clfPromise = FilesetResolver.forAudioTasks(WASM_DIR).then(fileset =>
      AudioClassifier.createFromOptions(fileset, {
        baseOptions: { modelAssetPath: MODEL },
        maxResults: SOUND_DIM,       // 521개 점수 전부 받는다
      })).catch(e => { clfPromise = null; throw e; });   // 실패하면 다음에 다시 시도
  }
  return clfPromise;
}

// 미리 내려받기 (페이지 진입 시 불러두면 첫 녹음이 빠르다)
export function preloadSound() { return ensureClassifier(); }

// 521개 이름표 — 무음 한 창을 분류하면 모든 칸의 이름이 같이 나온다.
// 모델 파일 안(메타데이터)에 든 영어 이름 그대로다. 첫 분류(예열)도 겸한다.
let namesPromise = null;
export function labelNames() {
  if (!namesPromise) {
    namesPromise = ensureClassifier().then(clf => {
      const r = clf.classify(new Float32Array(15600), RATE);
      const cats = r[0].classifications[0].categories;
      const names = new Array(SOUND_DIM).fill('');
      for (const c of cats) if (c.index < SOUND_DIM) names[c.index] = c.categoryName;
      return names;
    }).catch(e => { namesPromise = null; throw e; });
  }
  return namesPromise;
}

// 파형 칸: 창을 WAVE_BINS 칸으로 나눠 칸마다 가장 큰 진폭 (0~1)
function waveOf(buf) {
  const out = new Float32Array(WAVE_BINS), per = Math.floor(buf.length / WAVE_BINS);
  for (let b = 0; b < WAVE_BINS; b++) {
    let m = 0;
    for (let i = b * per, e = i + per; i < e; i += 4) { const v = Math.abs(buf[i]); if (v > m) m = v; }
    out[b] = Math.min(1, m);
  }
  return out;
}

// createSoundEngine() → { start, stop, running, ready, latest, levels, onTick }
//  latest = { vec: Float32Array(521), top: [{index, name, score}…], level, wave }
//  levels = 최근 소리 크기(RMS) 기록 — 소리 크기 막대용
export function createSoundEngine() {
  let ctx = null, srcNode = null, proc = null, stream = null;
  let timer = null, classifier = null;
  // 링 버퍼 길이는 실제 샘플레이트를 알아야 정해진다 (start 에서 만든다).
  // 기기가 16kHz 를 못 맞춰 줘도 "0.975초어치" 라는 뜻은 그대로 지킨다.
  let ring = null;
  let ringPos = 0, ringFilled = 0;
  let level = 0;
  let starting = null;

  const eng = {
    running: false,
    ready: false,        // 첫 분류 결과가 나온 뒤 true
    latest: null,
    levels: [],
    level: 0,
    onTick: null,
    get filled() { return ring ? ringFilled / ring.length : 0; },   // 첫 창이 얼마나 찼나 (0~1)

    // 두 곳(모으기·해 보기)이 동시에 켤 수 있어 켜는 중인 약속을 함께 쓴다
    start(deviceId) {
      if (eng.running) return Promise.resolve(true);
      if (!starting) starting = doStart(deviceId).finally(() => { starting = null; });
      return starting;
    },

    stop() {
      clearInterval(timer); timer = null;
      if (proc) { proc.disconnect(); proc.onaudioprocess = null; proc = null; }
      if (srcNode) { srcNode.disconnect(); srcNode = null; }
      if (ctx) { ctx.close().catch(() => {}); ctx = null; }
      if (stream) { stream.getTracks().forEach(t => t.stop()); stream = null; }
      eng.running = false;
      eng.ready = false;
      eng.latest = null;
      eng.levels = [];
      eng.level = 0;
      ring = null; ringPos = 0; ringFilled = 0; level = 0;
    },
  };

  async function doStart(deviceId) {
    classifier = await ensureClassifier();
    const want = { echoCancellation: false, noiseSuppression: false, autoGainControl: false };
    if (deviceId) want.deviceId = { exact: deviceId };
    stream = await navigator.mediaDevices.getUserMedia({ audio: want, video: false });
    try { ctx = new AudioContext({ sampleRate: RATE }); }
    catch (e) { ctx = new AudioContext(); }   // 일부 기기는 샘플레이트 고정
    if (ctx.state === 'suspended') {
      ctx.resume().catch(() => {});
      // 사용자 조작 없이 만들면 멈춰 있을 수 있다 → 다음 터치/클릭에서 다시 깨운다
      const wake = () => { ctx && ctx.resume().catch(() => {}); };
      document.addEventListener('click', wake, { once: true });
      document.addEventListener('touchend', wake, { once: true });
    }
    ring = new Float32Array(Math.round(WINDOW_SECONDS * ctx.sampleRate));
    ringPos = 0; ringFilled = 0;
    srcNode = ctx.createMediaStreamSource(stream);
    proc = ctx.createScriptProcessor(4096, 1, 1);
    proc.onaudioprocess = ev => {
      const ch = ev.inputBuffer.getChannelData(0);
      let sum = 0;
      for (let i = 0; i < ch.length; i++) {
        ring[ringPos] = ch[i];
        ringPos = (ringPos + 1) % ring.length;
        sum += ch[i] * ch[i];
      }
      ringFilled = Math.min(ring.length, ringFilled + ch.length);
      level = Math.sqrt(sum / ch.length);
      eng.level = level;
    };
    srcNode.connect(proc);
    proc.connect(ctx.destination);   // 연결해야 콜백이 돈다 (출력은 무음)
    timer = setInterval(tick, TICK_MS);
    eng.running = true;
    return true;
  }

  function tick() {
    if (!classifier || !ring || ringFilled < ring.length) return;
    // 링 버퍼를 시간 순서대로 편다
    const buf = new Float32Array(ring.length);
    buf.set(ring.subarray(ringPos));
    buf.set(ring.subarray(0, ringPos), ring.length - ringPos);
    let results = null;
    try { results = classifier.classify(buf, ctx.sampleRate); } catch (e) { return; }
    // 창 하나만 나오도록 길이를 맞춰 두었지만, 혹시 여러 개가 나오면 첫 창을 쓴다.
    // 마지막 창은 0으로 채워진 꼬리라 늘 "Silence" 다.
    const r = results && results[0];
    const cats = r && r.classifications && r.classifications[0] && r.classifications[0].categories;
    if (!cats) return;
    const vec = new Float32Array(SOUND_DIM);
    for (const c of cats) if (c.index < SOUND_DIM) vec[c.index] = c.score;
    const top = cats.slice().sort((a, b) => b.score - a.score).slice(0, 8)
      .map(c => ({ index: c.index, name: c.categoryName, score: c.score }));
    eng.latest = { vec, top, level, wave: waveOf(buf) };
    eng.levels.push(level);
    if (eng.levels.length > 96) eng.levels.shift();
    eng.ready = true;
    if (eng.onTick) eng.onTick(eng.latest);
  }

  return eng;
}
