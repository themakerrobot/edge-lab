#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""같은 점수 점검 — 같은 사진을 로봇 · PC(edge-lab) · 브라우저에 넣어 특징과 점수를 비교한다 (261104).

로봇 연동 일원화 6단계. 파이보 · PiBrain(system/score_check.py) · edge-lab(tools/score_check.py) 에 **같은 파일**이 있다.
어디서 도는지는 스스로 알아낸다(openpibo 가 있으면 로봇, train_routes 가 있으면 PC).

1) 각자 돌려서 결과 파일을 만든다 — 같은 사진 폴더, 같은 모델

  로봇   sudo /home/pi/.pyenv/bin/python3 /home/pi/openpibo-os/system/score_check.py run /home/pi/mymodel/<이름> <사진 폴더> --out robot.json
  PC     python tools\\score_check.py run <저장한 AI 이름(slug) 또는 model.zip> <사진 폴더> --out pc.json      (edge-lab 폴더에서)
  브라우저 로봇 분류기를 켠 뒤 http://<로봇 IP>:50010/static/check.html → 모델 고르기 · 사진 넣기 → [결과 파일 받기]

2) 두세 개를 견준다 (어디서 돌려도 된다)

  python score_check.py compare robot.json pc.json browser.json

결과 파일(JSON): {"tool": "teachlab-score-check", "where": robot|pc|browser, "model", "source", "variant", "classes",
                  "items": [{"file", "found", "label", "probs": [...], "feature": base64 float32}]}
비교 기준: 사진마다 답(가장 높은 종류)이 같은지, 확률 차이, 특징 코사인·최대 차이.
로봇 · PC 는 같은 코드라 특징 차이가 1e-5 안쪽이어야 한다. 브라우저는 JPEG 풀기·줄이기가 브라우저 몫이라 조금 더 벌어진다
(그림을 짧은 변 240 으로 줄여서 넣으면 가장 가깝다 — 로봇 분류기가 학습 때 보내는 크기).
"""
import argparse
import base64
import glob
import json
import os
import sys

import numpy as np

EXTS = ('.jpg', '.jpeg', '.png', '.bmp', '.webp')


def _images(paths):
    out = []
    for p in paths:
        if os.path.isdir(p):
            out += sorted(f for f in glob.glob(os.path.join(p, '*')) if f.lower().endswith(EXTS))
        elif os.path.isfile(p):
            out.append(p)
    if not out:
        sys.exit('사진이 없어요 / no images: ' + ' '.join(paths))
    return out


def _b64(vec):
    return base64.b64encode(np.asarray(vec, '<f4').tobytes()).decode()


def _unb64(s):
    return np.frombuffer(base64.b64decode(s), '<f4') if s else None


# ── 로봇: openpibo CustomClassifier 와 같은 길(vision_classify.predict) ──
def run_robot(model, files):
    import cv2
    from openpibo.vision_classify import CustomClassifier, _as_stream_rgb
    cf = CustomClassifier()
    cf.load(model)
    items = []
    for f in files:
        bgr = cv2.imread(f)
        if bgr is None:
            items.append({'file': os.path.basename(f), 'found': False, 'error': 'decode'})
            continue
        rgb = _as_stream_rgb(bgr)
        vec = cf.extractor.embed_rgb(rgb, flip=False) if cf.source == 'image' else cf.extractor.vector(rgb)
        items.append(_item(f, vec, cf.classes, cf.classifier.predict_proba))
    proj = getattr(cf, 'project', {}) or {}
    return {'where': 'robot', 'model': os.path.basename(os.path.normpath(model)), 'source': cf.source,
            'variant': cf.variant, 'classes': list(cf.classes), 'items': items, 'app': proj.get('app')}


# ── PC: edge-lab train_routes (서버가 /custom/predict 에서 하는 것과 같은 길) ──
def run_pc(model, files):
    import cv2
    import train_routes as TR
    from paths import USER_DIR
    path = model if model.lower().endswith('.zip') else os.path.join(USER_DIR, TR._slugify(model), 'model.zip')
    with open(path, 'rb') as fh:
        head = TR.Head(fh.read())
    items = []
    for f in files:
        bgr = cv2.imread(f)
        if bgr is None:
            items.append({'file': os.path.basename(f), 'found': False, 'error': 'decode'})
            continue
        try:
            vec = head.features(bgr)
        except TR.SoftError:
            vec = None
        items.append(_item(f, vec, head.labels, head.predict))
    src, var = TR.KINDS.get(head.kind, (head.kind, None))
    return {'where': 'pc', 'model': os.path.basename(model), 'source': src, 'variant': var,
            'classes': list(head.labels), 'items': items, 'legacy': bool(head.legacy)}


def _item(f, vec, classes, predict):
    if vec is None:
        return {'file': os.path.basename(f), 'found': False}
    probs = np.asarray(predict(np.asarray(vec, np.float32)), np.float64)
    best = int(np.argmax(probs))
    return {'file': os.path.basename(f), 'found': True, 'label': classes[best],
            'probs': [round(float(p), 6) for p in probs], 'feature': _b64(vec)}


def cmd_run(a):
    files = [os.path.abspath(f) for f in _images(a.images)]
    out = os.path.abspath(a.out or 'score.json')
    model = os.path.abspath(a.model) if os.path.exists(a.model) else a.model
    where = a.where
    if not where:
        try:
            import openpibo.vision_classify  # noqa: F401
            where = 'robot'
        except Exception:
            here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            sys.path.insert(0, here)
            os.chdir(here)
            where = 'pc'
    rep = run_robot(model, files) if where == 'robot' else run_pc(model, files)
    rep = dict({'tool': 'teachlab-score-check', 'version': 1}, **rep)
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(rep, f, ensure_ascii=False)
    found = sum(1 for i in rep['items'] if i.get('found'))
    print(f'[{rep["where"]}] {rep["model"]} · {rep["source"]}/{rep["variant"] or "-"} · 사진 {len(rep["items"])}장(찾음 {found}) → {out}')
    for i in rep['items']:
        if i.get('found'):
            print(f'  {i["file"]:28s} {i["label"]}  {max(i["probs"]) * 100:.1f}%')
        else:
            print(f'  {i["file"]:28s} (못 찾음 / not found)')


def cmd_compare(a):
    reps = []
    for p in a.files:
        with open(p, encoding='utf-8') as f:
            reps.append(json.load(f))
    base = reps[0]
    print('비교 / compare: ' + ' · '.join(f'{r["where"]}({os.path.basename(p)})' for r, p in zip(reps, a.files)))
    for r in reps[1:]:
        if r.get('classes') != base.get('classes'):
            print(f'  !! 종류 이름·순서가 다르다: {base.get("classes")} vs {r.get("classes")}')
        if (r.get('source'), r.get('variant')) != (base.get('source'), base.get('variant')):
            print(f'  !! 특징 종류가 다르다: {base.get("source")}/{base.get("variant")} vs {r.get("source")}/{r.get("variant")}')
    idx = [{i['file']: i for i in r['items']} for r in reps]
    names = [i['file'] for i in base['items']]
    bad = 0
    stats = {k: {'same': 0, 'n': 0, 'pmax': 0.0, 'fmax': 0.0, 'cmin': 1.0, 'onlyone': 0} for k in range(1, len(reps))}
    for name in names:
        a0 = idx[0].get(name)
        line = [f'  {name:28s} {base["where"]}: ' + (f'{a0["label"]} {max(a0["probs"]) * 100:.1f}%' if a0.get('found') else '없음')]
        for k in range(1, len(reps)):
            b = idx[k].get(name)
            st = stats[k]
            if b is None:
                line.append(f'| {reps[k]["where"]}: (사진 없음)')
                continue
            if a0.get('found') != b.get('found'):
                st['onlyone'] += 1
                bad += 1
                line.append(f'| {reps[k]["where"]}: !! 한쪽만 찾음')
                continue
            if not a0.get('found'):
                line.append(f'| {reps[k]["where"]}: 없음')
                continue
            st['n'] += 1
            same = a0['label'] == b['label']
            st['same'] += int(same)
            bad += int(not same)
            pd = float(np.max(np.abs(np.array(a0['probs']) - np.array(b['probs'])))) if len(a0['probs']) == len(b['probs']) else 1.0
            st['pmax'] = max(st['pmax'], pd)
            fa, fb = _unb64(a0.get('feature')), _unb64(b.get('feature'))
            fd = cs = None
            if fa is not None and fb is not None and fa.size == fb.size:
                fd = float(np.max(np.abs(fa - fb)))
                cs = float(fa @ fb / ((np.linalg.norm(fa) * np.linalg.norm(fb)) or 1.0))
                st['fmax'] = max(st['fmax'], fd)
                st['cmin'] = min(st['cmin'], cs)
            line.append(f'| {reps[k]["where"]}: {"" if same else "!! "}{b["label"]} {max(b["probs"]) * 100:.1f}%'
                        + (f' (특징 차 {fd:.1e}, cos {cs:.6f})' if fd is not None else ' (특징 크기가 다르다)'))
        print(' '.join(line))
    print('요약 / summary')
    for k, st in stats.items():
        print(f'  {base["where"]} vs {reps[k]["where"]}: 답 같음 {st["same"]}/{st["n"]} · 한쪽만 찾음 {st["onlyone"]} · '
              f'확률 최대 차 {st["pmax"]:.4f} · 특징 최대 차 {st["fmax"]:.1e} · 최저 코사인 {st["cmin"]:.6f}')
    sys.exit(1 if bad else 0)


def main():
    ap = argparse.ArgumentParser(description='같은 점수 점검 (teachlab 분류기 — 로봇 · PC · 브라우저)')
    sub = ap.add_subparsers(dest='cmd', required=True)
    r = sub.add_parser('run', help='사진 폴더로 점수를 뽑아 결과 파일을 만든다')
    r.add_argument('model', help='로봇: 모델 폴더 / PC: 저장한 AI 이름(slug) 또는 model.zip')
    r.add_argument('images', nargs='+', help='사진 파일이나 폴더')
    r.add_argument('--out', default='', help='결과 파일 (기본 score.json)')
    r.add_argument('--where', choices=('robot', 'pc'), default='', help='자동으로 못 고를 때만')
    r.set_defaults(fn=cmd_run)
    c = sub.add_parser('compare', help='결과 파일 두세 개를 견준다')
    c.add_argument('files', nargs='+')
    c.set_defaults(fn=cmd_compare)
    a = ap.parse_args()
    if a.cmd == 'compare' and len(a.files) < 2:
        ap.error('결과 파일이 두 개 이상 필요해요')
    a.fn(a)


if __name__ == '__main__':
    main()
