/* 로봇 공장(/factory) — 3D 공장 그림. 로봇팔 1대 + 컨베이어 1대 + 차단봉.
 *
 * 출처: themakerrobot/factory-lab index.html (커밋 7a67b5f) 에서 옮김 — 같은 저작자.
 * 모양·치수·카메라 값은 그대로 두었다. 실물 로봇과 맞춰 둔 값이라 바꾸면 화면과 로봇이 어긋난다.
 * 바뀐 것: 전역 하나(EL_FACTORY_3D)로 묶었고, 라벨 글꼴을 이 저장소의 Gowun Dodum 으로,
 * WebGL 이 없는 컴퓨터에서는 ok=false 로 돌려 페이지가 3D 없이도 돌게 했다.
 *
 * 쓰는 법:
 *     <script src="/lib/factory/three.min.js"></script>
 *     <script src="/lib/factory/scene.js"></script>
 *     var S = EL_FACTORY_3D.create({ canvas, box, label: key => 글, onPick: (ch, x, y) => {}, onZoom: z => {} });
 *     S.render({ joints: [j1, j2, j3, j4], flag: 0~180, roller: -90~90 });   // 매 프레임
 */
(function () {
  "use strict";

  const clamp = (v, a, b) => v < a ? a : v > b ? b : v;

  /* 배치 (TOP 뷰 기준): 벨트는 좌→우(+x), 로봇팔은 벨트 중앙 앞쪽(+z), 차단봉은 벨트 건너편(-z) 상류 쪽 */
  const BELT = { x0: -2.4, x1: 2.4, w: 1.0, top: 1.1 };   // top = 벨트 면 높이
  const BASE = { x: 0, z: 2.0, h: 1.04 };                 // 받침 높이: 바닥판 윗면이 벨트 면과 같아지게
  const L1 = 1.35, L2 = 1.05;
  const FLAG = { x: -1.5, z: -(BELT.w / 2 + 0.18), len: 1.18 };
  const GRIP_K = 135 / 180;                               // 실물 집게: 180° 지령 = 예전 135° 만큼만 닫힘
  const DIR = { ch1: 1, ch2: 1, ch3: 1 };                 // 3D 회전 방향 (화면만). 실물 방향은 페이지의 FLIP 이 맞춘다

  /* 카메라는 +z(팔 쪽)에서 -z 방향을 봄 → 화면 오른쪽 = +x, 화면 위 = -z(차단봉 쪽) */
  const CAM = {
    all:  { t: [0, 1.1, 0.8], d: 8.0, th: -Math.PI / 2, ph: 1.05 },
    arm:  { t: [BASE.x, 0.9 + BASE.h, BASE.z - 0.6], d: 4.6, th: 1.0, ph: 1.0 },
    belt: { t: [(BELT.x0 + BELT.x1) / 2, 1.0, 0], d: 6.4, th: 1.45, ph: 0.85 },
    flag: { t: [-FLAG.x, 1.05, -FLAG.z - 0.3], d: 2.8, th: 1.1, ph: 0.95 },   // 컨베이어 그룹이 180° 돌아 있어 부호 반전
    top:  { t: [0, 0.9, 0.6], d: 10.5, th: Math.PI / 2, ph: 0.12 }
  };
  const LABEL_FONT = '30px "Gowun Dodum", "Apple SD Gothic Neo", "Malgun Gothic", sans-serif';

  function create(o) {
    const THREE = window.THREE;
    const api = { ok: false, CAM };
    if (!THREE) return api;
    const cv = o.canvas, box = o.box;
    let renderer;
    try {
      renderer = new THREE.WebGLRenderer({ canvas: cv, antialias: true, preserveDrawingBuffer: true });
    } catch (e) { return api; }                            // WebGL 이 꺼진 컴퓨터 — 페이지는 3D 없이 돈다
    api.ok = true;
    renderer.setClearColor(0xF3EFE6, 1);
    const scene = new THREE.Scene();
    scene.fog = new THREE.Fog(0xF3EFE6, 30, 110);
    const camera = new THREE.PerspectiveCamera(48, 1, 0.05, 400);
    const parts = {}, procAxes = [], labels = [];
    let beltTex, grid, worldAxes, wireMode = false, axisMode = false;

    /* ── 라벨 (글자 → 캔버스 텍스처) ── */
    function labelTexture(text, color) {
      const c = document.createElement("canvas"); c.width = 320; c.height = 80;
      const g = c.getContext("2d");
      g.font = LABEL_FONT;
      const w = Math.min(310, g.measureText(text).width + 40);
      g.fillStyle = "rgba(255,255,255,.92)";
      g.beginPath();
      if (g.roundRect) g.roundRect((320 - w) / 2, 12, w, 56, 28); else g.rect((320 - w) / 2, 12, w, 56);
      g.fill();
      g.fillStyle = color; g.textAlign = "center"; g.textBaseline = "middle"; g.fillText(text, 160, 41);
      const tex = new THREE.CanvasTexture(c); tex.minFilter = THREE.LinearFilter; return tex;
    }
    function label(key, color) {
      const sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: labelTexture(o.label(key), color), transparent: true, depthTest: false }));
      sp.scale.set(1.5, 0.375, 1);
      labels.push({ sprite: sp, key, color });
      return sp;
    }
    api.relabel = function () {
      for (const l of labels) {
        const old = l.sprite.material.map;
        l.sprite.material.map = labelTexture(o.label(l.key), l.color);
        l.sprite.material.needsUpdate = true;
        if (old) old.dispose();
      }
    };

    /* ── 장면 ── */
    scene.add(new THREE.HemisphereLight(0xffffff, 0xCFC7B8, 0.95));
    const dl = new THREE.DirectionalLight(0xffffff, 0.7); dl.position.set(-4, 8, 5); scene.add(dl);
    const dl2 = new THREE.DirectionalLight(0xfff0d0, 0.3); dl2.position.set(6, 4, -6); scene.add(dl2);
    const rim = new THREE.DirectionalLight(0xffffff, 0.25); rim.position.set(0, 3, -8); scene.add(rim);

    grid = new THREE.GridHelper(80, 80, 0xCFC7B8, 0xE6E0D3); scene.add(grid);
    const floor = new THREE.Mesh(new THREE.PlaneGeometry(80, 80), new THREE.MeshLambertMaterial({ color: 0xF3EFE6 }));
    floor.rotation.x = -Math.PI / 2; floor.position.y = -0.01; scene.add(floor);
    worldAxes = new THREE.AxesHelper(1.6); worldAxes.position.set(0, 0.02, 0); worldAxes.visible = false; scene.add(worldAxes);

    /* --- 컨베이어 : 벨트·차단봉·구동 서보를 한 그룹으로 묶고 통째로 180° 돌린다 --- */
    const conv = new THREE.Group(); conv.rotation.y = Math.PI; scene.add(conv);
    const len = BELT.x1 - BELT.x0, cx = (BELT.x0 + BELT.x1) / 2;
    const T = BELT.top, fr = Math.min(0.34, T), rr = Math.min(0.16, T / 2);
    const frame = new THREE.Mesh(new THREE.BoxGeometry(len, fr, BELT.w + 0.22), new THREE.MeshLambertMaterial({ color: 0x1F5F7A }));
    frame.position.set(cx, T - fr / 2, 0); conv.add(frame);
    [-1, 1].forEach(sz => {
      const rail = new THREE.Mesh(new THREE.BoxGeometry(len, 0.06, 0.07), new THREE.MeshLambertMaterial({ color: 0x9A8F7D }));
      rail.position.set(cx, T + 0.03, sz * (BELT.w / 2 + 0.06)); conv.add(rail);
    });
    if (T - fr > 0.04) [BELT.x0 + 0.3, BELT.x1 - 0.3].forEach(lx => [-1, 1].forEach(sz => {
      const leg = new THREE.Mesh(new THREE.BoxGeometry(0.12, T - fr, 0.12), new THREE.MeshLambertMaterial({ color: 0x12455C }));
      leg.position.set(lx, (T - fr) / 2, sz * (BELT.w / 2 - 0.1)); conv.add(leg);
    }));
    const tc = document.createElement("canvas"); tc.width = 64; tc.height = 64;
    const tg = tc.getContext("2d");
    tg.fillStyle = "#4A423A"; tg.fillRect(0, 0, 64, 64);
    tg.fillStyle = "rgba(255,255,255,.28)"; tg.fillRect(0, 0, 8, 64);
    beltTex = new THREE.CanvasTexture(tc);
    beltTex.wrapS = beltTex.wrapT = THREE.RepeatWrapping;
    beltTex.repeat.set(len * 1.6, 1);
    const belt = new THREE.Mesh(new THREE.PlaneGeometry(len, BELT.w), new THREE.MeshLambertMaterial({ map: beltTex }));
    belt.rotation.x = -Math.PI / 2; belt.position.set(cx, T + 0.002, 0); conv.add(belt);
    parts.rollers = [];
    [BELT.x0, BELT.x1].forEach(x => {
      const r = new THREE.Mesh(new THREE.CylinderGeometry(rr, rr, BELT.w, 20), new THREE.MeshLambertMaterial({ color: 0x9A8F7D }));
      r.rotation.x = Math.PI / 2; r.position.set(x, T - rr, 0);
      conv.add(r); parts.rollers.push(r);
    });
    const drv = new THREE.Mesh(new THREE.BoxGeometry(0.4, 0.4, 0.26), new THREE.MeshLambertMaterial({ color: 0x2A2620 }));
    drv.position.set(BELT.x0, T - rr, (BELT.w + 0.22) / 2 + 0.13); conv.add(drv);   // 구동 서보(ch5) — 끝 롤러 축에

    /* --- 차단봉 (ch6) : 벨트 건너편 수평 스윕, 0° 차단 / +90° 개방 --- */
    const servo = new THREE.Mesh(new THREE.BoxGeometry(0.48, 0.3, 0.26), new THREE.MeshLambertMaterial({ color: 0x2A2620 }));
    servo.position.set(FLAG.x, Math.max(0.15, BELT.top - 0.02), FLAG.z - 0.1); conv.add(servo);
    parts.flag = new THREE.Group();
    parts.flag.position.set(FLAG.x, BELT.top + 0.16, FLAG.z);
    const horn = new THREE.Mesh(new THREE.BoxGeometry(FLAG.len, 0.05, 0.1), new THREE.MeshLambertMaterial({ color: 0xffffff }));
    horn.position.x = FLAG.len / 2;
    const sc = document.createElement("canvas"); sc.width = 64; sc.height = 8;
    const sg = sc.getContext("2d");
    sg.fillStyle = "#ffffff"; sg.fillRect(0, 0, 64, 8);
    sg.fillStyle = "#B4451C"; sg.fillRect(0, 0, 16, 8); sg.fillRect(32, 0, 16, 8);
    const stripeTex = new THREE.CanvasTexture(sc); stripeTex.wrapS = THREE.RepeatWrapping; stripeTex.repeat.set(2, 1);
    const blade = new THREE.Mesh(new THREE.BoxGeometry(FLAG.len * 0.66, 0.26, 0.05), new THREE.MeshLambertMaterial({ map: stripeTex }));
    blade.position.set(FLAG.len * 0.66, 0.06, 0);
    parts.flag.add(horn); parts.flag.add(blade); conv.add(parts.flag);

    /* --- 로봇팔 (하비서보 브래킷 구조) --- */
    const MAT = {
      anod:  new THREE.MeshPhongMaterial({ color: 0x1F5F7A, shininess: 30 }),
      dark:  new THREE.MeshPhongMaterial({ color: 0x2A2620, shininess: 18 }),
      hub:   new THREE.MeshPhongMaterial({ color: 0xB4451C, shininess: 60 }),
      steel: new THREE.MeshPhongMaterial({ color: 0xC9C2B4, shininess: 70 }),
      pad:   new THREE.MeshPhongMaterial({ color: 0x4A3F2E, shininess: 8 })
    };
    function servoBlock(s) {
      const g = new THREE.Group();
      g.add(new THREE.Mesh(new THREE.BoxGeometry(0.22 * s, 0.4 * s, 0.44 * s), MAT.dark));
      const ears = new THREE.Mesh(new THREE.BoxGeometry(0.22 * s, 0.05 * s, 0.64 * s), MAT.dark);
      ears.position.y = 0.12 * s; g.add(ears);
      const gearbox = new THREE.Mesh(new THREE.CylinderGeometry(0.07 * s, 0.07 * s, 0.08 * s, 14), MAT.steel);
      gearbox.rotation.z = Math.PI / 2; gearbox.position.set(0.13 * s, 0.1 * s, 0.1 * s); g.add(gearbox);
      const stripe = new THREE.Mesh(new THREE.BoxGeometry(0.005, 0.1 * s, 0.3 * s), MAT.hub);
      stripe.position.x = 0.111 * s; g.add(stripe);
      return g;
    }
    function plate(l, wid, thk) {
      const g = new THREE.Group();
      const body = new THREE.Mesh(new THREE.BoxGeometry(wid, l, thk), MAT.anod);
      body.position.y = l / 2; g.add(body);
      [0, l].forEach(y => {
        const cap = new THREE.Mesh(new THREE.CylinderGeometry(wid / 2, wid / 2, thk, 16), MAT.anod);
        cap.rotation.x = Math.PI / 2; cap.position.y = y; g.add(cap);
      });
      return g;
    }
    function uLink(l, wid, gap) {
      const g = new THREE.Group();
      [-1, 1].forEach(sgn => { const pl = plate(l, wid, 0.05); pl.position.z = sgn * gap / 2; g.add(pl); });
      const web = new THREE.Mesh(new THREE.BoxGeometry(wid * 0.5, l * 0.72, gap - 0.02), MAT.anod);
      web.position.y = l * 0.5; g.add(web);
      return g;
    }
    const bolt = (x, y, z, r = 0.028, h = 0.04) => {
      const b = new THREE.Mesh(new THREE.CylinderGeometry(r, r, h, 8), MAT.steel);
      b.position.set(x, y, z); return b;
    };

    parts.armRoot = new THREE.Group(); parts.armRoot.position.set(BASE.x, 0, BASE.z);
    parts.armRoot.rotation.y = Math.PI / 2;                 // ch1=90° 에서 팔 정면이 벨트(-z)를 향함
    scene.add(parts.armRoot);
    const riser = new THREE.Mesh(new THREE.CylinderGeometry(0.5, 0.56, BASE.h, 28), MAT.dark);
    riser.position.y = BASE.h / 2; parts.armRoot.add(riser);
    parts.armProc = new THREE.Group(); parts.armProc.position.y = BASE.h; parts.armRoot.add(parts.armProc);
    const P = parts.armProc;
    const basePlate = new THREE.Mesh(new THREE.CylinderGeometry(0.62, 0.66, 0.06, 28), MAT.anod);
    basePlate.position.y = 0.03; P.add(basePlate);
    for (let i = 0; i < 4; i++) {
      const a = i * Math.PI / 2 + Math.PI / 4;
      P.add(bolt(Math.cos(a) * 0.5, 0.07, Math.sin(a) * 0.5));
    }
    // 첫 서보의 혼은 바닥판에 고정 — 실물처럼 서보 몸체가 팔과 함께 돈다
    const horn0 = new THREE.Mesh(new THREE.CylinderGeometry(0.13, 0.13, 0.03, 20), MAT.steel);
    horn0.position.y = 0.075; P.add(horn0);

    // ch1 베이스 회전
    parts.yaw = new THREE.Group(); parts.yaw.position.y = 0.09; P.add(parts.yaw);
    const sv1body = new THREE.Mesh(new THREE.BoxGeometry(0.4, 0.38, 0.2), MAT.dark);
    sv1body.position.y = 0.19; parts.yaw.add(sv1body);
    const sv1tabs = new THREE.Mesh(new THREE.BoxGeometry(0.6, 0.05, 0.2), MAT.dark);
    sv1tabs.position.y = 0.06; parts.yaw.add(sv1tabs);
    const sv1stripe = new THREE.Mesh(new THREE.BoxGeometry(0.3, 0.1, 0.005), MAT.hub);
    sv1stripe.position.set(0, 0.3, 0.101); parts.yaw.add(sv1stripe);
    [-0.25, 0.25].forEach(x => parts.yaw.add(bolt(x, 0.09, 0, 0.022, 0.03)));
    const shoulderBr = new THREE.Mesh(new THREE.BoxGeometry(0.3, 0.1, 0.5), MAT.anod);
    shoulderBr.position.y = 0.43; parts.yaw.add(shoulderBr);
    const sv2 = servoBlock(1.0); sv2.position.set(0, 0.53, 0); sv2.rotation.y = Math.PI / 2; parts.yaw.add(sv2);
    parts.yaw.add(bolt(0.14, 0.48, 0.2)); parts.yaw.add(bolt(-0.14, 0.48, -0.2));

    // ch2 어깨 → 위팔
    parts.link1 = new THREE.Group(); parts.link1.position.y = 0.53; parts.yaw.add(parts.link1);
    const hub1 = new THREE.Mesh(new THREE.CylinderGeometry(0.1, 0.1, 0.46, 18), MAT.hub);
    hub1.rotation.x = Math.PI / 2; parts.link1.add(hub1);
    parts.link1.add(uLink(L1, 0.26, 0.42));
    const rib1 = new THREE.Mesh(new THREE.BoxGeometry(0.05, L1 * 0.8, 0.06), MAT.steel);
    rib1.position.set(0.14, L1 * 0.5, 0); parts.link1.add(rib1);

    // ch3 팔꿈치 → 아래팔
    parts.link2 = new THREE.Group(); parts.link2.position.y = L1; parts.link1.add(parts.link2);
    const sv3 = servoBlock(0.85); sv3.position.set(0, 0.1, 0); sv3.rotation.y = Math.PI / 2; parts.link2.add(sv3);
    const hub2 = new THREE.Mesh(new THREE.CylinderGeometry(0.085, 0.085, 0.4, 18), MAT.hub);
    hub2.rotation.x = Math.PI / 2; parts.link2.add(hub2);
    parts.link2.add(uLink(L2, 0.21, 0.34));

    // ch4 손목 · 평행 집게
    parts.wrist = new THREE.Group(); parts.wrist.position.y = L2; parts.link2.add(parts.wrist);
    const wristHub = new THREE.Mesh(new THREE.CylinderGeometry(0.07, 0.07, 0.3, 16), MAT.hub);
    wristHub.rotation.x = Math.PI / 2; parts.wrist.add(wristHub);
    const sv4 = servoBlock(0.7); sv4.position.set(0, 0.16, 0); sv4.rotation.y = Math.PI / 2; parts.wrist.add(sv4);
    const palm = new THREE.Mesh(new THREE.BoxGeometry(0.2, 0.07, 0.46), MAT.anod);
    palm.position.y = 0.34; parts.wrist.add(palm);
    parts.jaws = [];
    [-1, 1].forEach(sgn => {
      const jaw = new THREE.Group();
      const finger = new THREE.Mesh(new THREE.BoxGeometry(0.16, 0.46, 0.08), MAT.anod);
      finger.position.y = 0.23; jaw.add(finger);
      const tip = new THREE.Mesh(new THREE.BoxGeometry(0.18, 0.22, 0.07), MAT.pad);
      tip.position.set(0, 0.42, -sgn * 0.05); jaw.add(tip);
      const grip = new THREE.Mesh(new THREE.BoxGeometry(0.19, 0.2, 0.02), MAT.hub);
      grip.position.set(0, 0.42, -sgn * 0.085); jaw.add(grip);
      const linkbar = new THREE.Mesh(new THREE.BoxGeometry(0.07, 0.2, 0.04), MAT.steel);
      linkbar.position.set(0, 0.06, -sgn * 0.04); linkbar.rotation.x = sgn * 0.25; jaw.add(linkbar);
      jaw.position.set(0, 0.17, sgn * 0.12);
      parts.wrist.add(jaw); parts.jaws.push(jaw);
    });

    // 재질 개별화(뼈대/선택 하이라이트용) + 채널 태깅 (안쪽부터)
    P.traverse(m => { if (m.isMesh) m.material = m.material.clone(); });
    const tag = (g, ch) => g.traverse(m => { if (m.isMesh && !m.userData.ch) m.userData.ch = ch; });
    tag(parts.wrist, 4); tag(parts.link2, 3); tag(parts.link1, 2); tag(P, 1);
    [parts.yaw, parts.link1, parts.link2, parts.wrist].forEach(g => {
      const ax = new THREE.AxesHelper(0.55); ax.visible = false; g.add(ax); procAxes.push(ax);
    });

    const l1s = label("lbl.arm", "#12455C"); l1s.position.set(BASE.x, BASE.h + 0.3, BASE.z + 1.0); scene.add(l1s);
    const l2s = label("lbl.belt", "#2A2620"); l2s.position.set(BELT.x0 + 0.25, BELT.top + 0.55, 0); conv.add(l2s);
    const l3s = label("lbl.flag", "#B4451C"); l3s.position.set(FLAG.x + 0.1, BELT.top + 0.7, FLAG.z - 0.35); conv.add(l3s);

    /* ── 카메라 ── */
    const view = { target: new THREE.Vector3(CAM.all.t[0], CAM.all.t[1], CAM.all.t[2]), dist: CAM.all.d, theta: CAM.all.th, phi: CAM.all.ph };
    function updateCamera() {
      view.dist = clamp(view.dist, 0.9, 80);
      view.phi = clamp(view.phi, 0.08, 1.5);
      const tg2 = view.target;
      camera.position.set(
        tg2.x + view.dist * Math.sin(view.phi) * Math.cos(view.theta),
        tg2.y + view.dist * Math.cos(view.phi),
        tg2.z + view.dist * Math.sin(view.phi) * Math.sin(view.theta));
      camera.lookAt(tg2);
    }
    api.setCam = function (name) {
      const c = CAM[name]; if (!c) return;
      view.target.set(c.t[0], c.t[1], c.t[2]);
      view.dist = c.d; view.theta = c.th; view.phi = c.ph;
      zoomed();
    };
    api.zoom = function (z) { view.dist = clamp(12 / z, 0.9, 80); };
    function zoomed() { if (o.onZoom) o.onZoom(12 / clamp(view.dist, 0.9, 80)); }
    api.resize = function () {
      const r = cv.parentElement.getBoundingClientRect();
      if (!r.width || !r.height) return;                  // 가려진 창 — 보일 때 다시 잰다
      renderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1));
      renderer.setSize(Math.max(160, r.width), Math.max(120, r.height), false);
      camera.aspect = Math.max(160, r.width) / Math.max(120, r.height); camera.updateProjectionMatrix();
    };

    /* ── 매 프레임 ── */
    api.render = function (s) {
      const j = s.joints;
      parts.yaw.rotation.y = DIR.ch1 * (j[0] - 90) * Math.PI / 180;
      parts.link1.rotation.z = -DIR.ch2 * (j[1] - 90) * Math.PI / 180;
      parts.link2.rotation.z = -DIR.ch3 * (j[2] - 90) * Math.PI / 180;
      const open = (1 - (j[3] * GRIP_K) / 180) * 0.26 + 0.07;   // 실물은 180°에서도 다 안 닫힘
      parts.jaws[0].position.z = -open; parts.jaws[1].position.z = open;
      // 차단봉: 0 = 벨트 가로질러 차단, +90 = 하류로 눕혀 개방
      parts.flag.rotation.y = clamp((s.flag - 90) - 90, -200, 20) * Math.PI / 180;
      // 화면 전용 계수 — 실물 벨트 속도(#m1)와는 무관하다. 같은 값에서 3D 가 빨라 보여 절반으로 낮췄다
      beltTex.offset.x -= s.roller * 0.0008;
      parts.rollers.forEach(r => { r.rotation.y += s.roller * 0.002; });
      updateCamera();
      renderer.render(scene, camera);
    };

    /* ── 보기 도구 ── */
    api.toggleGrid = function () { grid.visible = !grid.visible; return grid.visible; };
    api.toggleWire = function () {
      wireMode = !wireMode;
      parts.armRoot.traverse(m => { if (m.isMesh) m.material.wireframe = wireMode; });
      return wireMode;
    };
    api.toggleAxes = function () {
      axisMode = !axisMode;
      worldAxes.visible = axisMode; procAxes.forEach(a => { a.visible = axisMode; });
      return axisMode;
    };
    api.snapshot = function (cb) { renderer.render(scene, camera); cv.toBlob(cb, "image/png"); };

    /* ── 부품 클릭 → 채널 ── */
    const raycaster = new THREE.Raycaster();
    let picked = null, pickedColor = 0;
    function pickAt(x, y) {
      const rect = cv.getBoundingClientRect();
      const m = new THREE.Vector2(((x - rect.left) / rect.width) * 2 - 1, -((y - rect.top) / rect.height) * 2 + 1);
      raycaster.setFromCamera(m, camera);
      const list = [];
      parts.armProc.traverse(q => { if (q.isMesh) list.push(q); });
      const hits = raycaster.intersectObjects(list, false);
      if (picked) { if (picked.material.emissive) picked.material.emissive.setHex(pickedColor); picked = null; }
      if (!hits.length) { o.onPick(0, x - rect.left, y - rect.top); return; }
      picked = hits[0].object;
      if (picked.material.emissive) { pickedColor = picked.material.emissive.getHex(); picked.material.emissive.setHex(0x5A2A10); }
      o.onPick(picked.userData.ch || 1, x - rect.left, y - rect.top);
    }

    /* ── 마우스 : 왼쪽 끌기 = 돌리기, 오른쪽/Shift = 옮기기, 휠 = 확대 ── */
    box.addEventListener("wheel", e => { e.preventDefault(); view.dist *= Math.exp(e.deltaY * 0.0022); zoomed(); }, { passive: false });
    box.addEventListener("contextmenu", e => e.preventDefault());
    let drag = null;
    box.addEventListener("pointerdown", e => {
      drag = { x: e.clientX, y: e.clientY, x0: e.clientX, y0: e.clientY, btn: e.button, pan: e.button === 2 || e.shiftKey };
      box.classList.add("dragging"); box.setPointerCapture(e.pointerId);
    });
    box.addEventListener("pointermove", e => {
      if (!drag) return;
      const dx = e.clientX - drag.x, dy = e.clientY - drag.y;
      if (drag.pan) {
        const k = view.dist * 0.0016, sinT = Math.sin(view.theta), cosT = Math.cos(view.theta);
        view.target.x += (-dx * sinT + dy * cosT * 0.6) * k;
        view.target.z += (dx * cosT + dy * sinT * 0.6) * k;
      } else { view.theta -= dx * 0.006; view.phi -= dy * 0.005; }
      drag.x = e.clientX; drag.y = e.clientY;
    });
    box.addEventListener("pointerup", e => {
      if (drag && drag.btn === 0 && Math.hypot(e.clientX - drag.x0, e.clientY - drag.y0) < 4) pickAt(e.clientX, e.clientY);
      drag = null; box.classList.remove("dragging");
    });
    box.addEventListener("pointercancel", () => { drag = null; box.classList.remove("dragging"); });
    box.addEventListener("dblclick", () => { api.setCam("all"); if (o.onCam) o.onCam("all"); });

    api.resize(); updateCamera();
    return api;
  }

  window.EL_FACTORY_3D = { create };
})();
