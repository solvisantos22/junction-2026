// Lightlag · Mars ops demo. One file, no build step; three.js is the only dependency.
// Everything shown comes from recorded runs in window.LIGHTLAG_DATA (see viewer/build_mars.py).
import * as THREE from 'three';

if (document.readyState === 'loading') await new Promise(resolve => document.addEventListener('DOMContentLoaded', resolve, { once: true }));

const DATA = window.LIGHTLAG_DATA;
const $ = (selector, root = document) => root.querySelector(selector);
const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
const lerp = (a, b, t) => a + (b - a) * t;
const smooth = (a, b, x) => { const t = clamp((x - a) / (b - a), 0, 1); return t * t * (3 - 2 * t); };
const TAU = Math.PI * 2;
const C = { accent: 0xff8a3d, cmd: 0xffd166, tel: 0x5ce1ff, ok: 0x7cf29c, bad: 0xff5d5d, holo: 0xc7a6ff };

// ---------------------------------------------------------------- noise
const hash2 = (x, y) => { const h = Math.sin(x * 127.1 + y * 311.7) * 43758.5453; return h - Math.floor(h); };
function vnoise(x, y) {
  const xi = Math.floor(x), yi = Math.floor(y), xf = x - xi, yf = y - yi;
  const u = xf * xf * (3 - 2 * xf), v = yf * yf * (3 - 2 * yf);
  return lerp(lerp(hash2(xi, yi), hash2(xi + 1, yi), u), lerp(hash2(xi, yi + 1), hash2(xi + 1, yi + 1), u), v);
}
function fbm(x, y, octaves = 4) {
  let sum = 0, amp = 0.5, norm = 0;
  for (let i = 0; i < octaves; i++) { sum += amp * vnoise(x, y); norm += amp; x *= 2.03; y *= 2.03; amp *= 0.5; }
  return sum / norm;
}
// Ground height in metres at scene coordinates. Flat where the rover drives, hills beyond.
function terrainHeight(x, z) {
  const d = Math.max(Math.abs(x), Math.abs(z));
  const out = smooth(22, 52, d);
  const micro = (fbm(x * 0.4 + 11, z * 0.4 + 3, 3) - 0.5) * 0.05;
  const dunes = (fbm(x * 0.04 + 40, z * 0.04 + 7, 4) - 0.42) * 11 * out;
  const r = Math.hypot(x, z);
  const mesas = smooth(75, 120, r) * (4 + 22 * Math.pow(fbm(x * 0.017 + 3, z * 0.017 + 9, 3), 1.6));
  return micro + dunes + mesas;
}

// ---------------------------------------------------------------- procedural textures
function canvasTexture(size, draw, repeat = 1) {
  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = size;
  draw(canvas.getContext('2d'), size);
  const texture = new THREE.CanvasTexture(canvas);
  texture.wrapS = texture.wrapT = THREE.RepeatWrapping;
  texture.repeat.set(repeat, repeat);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.anisotropy = 8;
  return texture;
}
const TEX = {
  grain: canvasTexture(512, (g, s) => {
    g.fillStyle = '#d9d2cc'; g.fillRect(0, 0, s, s);
    for (let i = 0; i < 9000; i++) {
      const v = 150 + Math.random() * 105 | 0;
      g.fillStyle = `rgba(${v},${v - 8},${v - 16},${0.25 + Math.random() * 0.5})`;
      g.fillRect(Math.random() * s, Math.random() * s, 1 + Math.random() * 2.2, 1 + Math.random() * 2.2);
    }
    for (let i = 0; i < 70; i++) {
      const x = Math.random() * s, y = Math.random() * s, r = 6 + Math.random() * 26;
      const grad = g.createRadialGradient(x, y, 0, x, y, r);
      const dark = Math.random() < 0.6;
      grad.addColorStop(0, dark ? 'rgba(70,50,44,.35)' : 'rgba(255,246,236,.3)'); grad.addColorStop(1, 'rgba(0,0,0,0)');
      g.fillStyle = grad; g.fillRect(x - r, y - r, r * 2, r * 2);
    }
  }, 60),
  ripple: canvasTexture(512, (g, s) => {
    const image = g.createImageData(s, s);
    for (let y = 0; y < s; y++) for (let x = 0; x < s; x++) {
      const wobble = Math.sin(y * TAU * 2 / s) * 0.9 + Math.sin(y * TAU * 5 / s + 1.3) * 0.35;
      const wave = Math.sin((x * TAU * 14 / s) + wobble * 2.2);
      const v = 205 + wave * 34 + (Math.random() - 0.5) * 16;
      const i = (y * s + x) * 4;
      image.data[i] = v; image.data[i + 1] = v - 6; image.data[i + 2] = v - 14; image.data[i + 3] = 255;
    }
    g.putImageData(image, 0, 0);
  }),
  dot: canvasTexture(128, (g, s) => {
    const grad = g.createRadialGradient(s / 2, s / 2, 0, s / 2, s / 2, s / 2);
    grad.addColorStop(0, 'rgba(255,255,255,1)'); grad.addColorStop(0.35, 'rgba(255,255,255,.55)'); grad.addColorStop(1, 'rgba(255,255,255,0)');
    g.fillStyle = grad; g.fillRect(0, 0, s, s);
  }),
  beam: canvasTexture(64, (g, s) => {
    const grad = g.createLinearGradient(0, s, 0, 0);
    grad.addColorStop(0, 'rgba(255,255,255,.95)'); grad.addColorStop(0.25, 'rgba(255,255,255,.4)'); grad.addColorStop(1, 'rgba(255,255,255,0)');
    g.fillStyle = grad; g.fillRect(0, 0, s, s);
  }),
};
function labelSprite(text, color = '#ffffff', scale = 1) {
  const canvas = document.createElement('canvas');
  const g = canvas.getContext('2d');
  const font = '700 44px -apple-system, "Segoe UI", sans-serif';
  g.font = font;
  canvas.width = Math.ceil(g.measureText(text).width) + 44; canvas.height = 72;
  g.font = font; g.textBaseline = 'middle';
  g.fillStyle = 'rgba(14,8,5,.72)';
  g.beginPath(); g.roundRect(0, 6, canvas.width, 60, 16); g.fill();
  g.fillStyle = color; g.fillText(text, 22, 38);
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  const sprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: texture, transparent: true, depthTest: false, fog: false }));
  sprite.scale.set(canvas.width / 72 * 0.95 * scale, 0.95 * scale, 1);
  sprite.renderOrder = 10;
  sprite.center.set(0.5, 0);
  sprite.userData = { text, aspect: canvas.width / 72, px: 25 * scale };   // px: height on screen
  return sprite;
}

// ---------------------------------------------------------------- runs
class Run {
  constructor(raw) {
    Object.assign(this, raw);
    const replay = raw.replay;
    this.cfg = replay.config; this.world = replay.world; this.states = replay.states;
    this.T = this.states.length - 1; this.K = this.cfg.delay_ticks;
    this.result = replay.result;
    this.reward = this.result.max_available_value > 0 ? this.result.raw_score / this.result.max_available_value : 0;
    const executed = new Set(), stops = [];
    this.events = [];
    for (const s of this.states) for (const e of s.events) {
      if (e.type === 'command_executed') executed.add(e.command_id);
      else { this.events.push({ tick: s.tick, ...e }); if (e.type === 'safety_stop' || e.type === 'battery_depleted') stops.push(s.tick); }
    }
    this.commands = replay.commands.map(c => {
      const done = executed.has(c.command_id);
      let until = c.execute_tick;
      if (!done) { const stop = stops.find(s => s > c.sent_tick && s <= c.execute_tick); if (stop !== undefined) until = stop; }
      return { id: c.command_id, ...c.command, sent: c.sent_tick, exec: c.execute_tick, until, done };
    });
    this.belief = new Map((raw.belief || []).map(b => [b.tick, b.position]));
    this.moved = this.states.map((s, i) => i ? Math.hypot(s.position[0] - this.states[i - 1].position[0], s.position[1] - this.states[i - 1].position[1]) : 0);
    this.wheel = []; let w = 0; for (const s of this.states) { w += s.wheel_odometry || 0; this.wheel.push(w); }
    let lastTick = -1, n = 0;
    this.calls = raw.calls.map((c, index) => {
      if (c.tick !== lastTick) { lastTick = c.tick; n = 0; }
      const at = c.tick + Math.min(0.9, n++ * 0.17);
      return { ...c, index, at };
    });
    this.targetValue = Object.fromEntries(this.world.targets.map(t => [t.id, t.value]));
    const xs = [this.world.base[0], ...this.world.targets.map(t => t.x), ...this.states.map(s => s.position[0])];
    const ys = [this.world.base[1], ...this.world.targets.map(t => t.y), ...this.states.map(s => s.position[1])];
    const pad = 5.5;
    this.bounds = { x0: Math.max(-2, Math.min(...xs) - pad), x1: Math.min(this.world.width + 2, Math.max(...xs) + pad),
      y0: Math.max(-2, Math.min(...ys) - pad), y1: Math.min(this.world.height + 2, Math.max(...ys) + pad) };
  }
  // Continuous pose at time t: the rover turns at the start of a tick, then drives.
  sample(t) {
    t = clamp(t, 0, this.T);
    const i = Math.min(this.T - 1, Math.floor(t)), f = t - i;
    const a = this.states[i], b = this.states[i + 1];
    const moving = this.moved[i + 1] > 1e-6;
    const drive = moving ? smooth(0.16, 1, f) : 0;
    const turn = moving ? smooth(0, 0.2, f) : 0;
    const delta = ((b.heading_deg - a.heading_deg + 540) % 360) - 180;
    return {
      x: lerp(a.position[0], b.position[0], drive), y: lerp(a.position[1], b.position[1], drive),
      heading: a.heading_deg + (moving ? delta * turn : 0),
      wheel: lerp(this.wheel[i], this.wheel[i + 1], drive),
      moving: moving && f > 0.16 && f < 0.985, slip: moving && b.wheel_odometry ? 1 - b.visual_odometry / b.wheel_odometry : 0,
      battery: lerp(a.battery, b.battery, f), sand: b.terrain === 'sand',
    };
  }
  stateAt(t) { return this.states[clamp(Math.floor(t + 1e-6), 0, this.T)]; }
}
const RUNS = DATA.runs.map(raw => new Run(raw));

// ---------------------------------------------------------------- shared scene pieces
const MAT = {
  ground: new THREE.MeshStandardMaterial({ vertexColors: true, map: TEX.grain, roughness: 1, metalness: 0 }),
  sand: new THREE.MeshStandardMaterial({ color: 0xe0a56a, map: TEX.ripple, bumpMap: TEX.ripple, bumpScale: 1.4, roughness: 1, metalness: 0,
    transparent: true, vertexColors: true, depthWrite: false, polygonOffset: true, polygonOffsetFactor: -2, polygonOffsetUnits: -2 }),
  rock: new THREE.MeshStandardMaterial({ color: 0x6b4233, roughness: 0.95, metalness: 0, flatShading: true }),
  basalt: new THREE.MeshStandardMaterial({ color: 0x2f2320, roughness: 0.9, metalness: 0.05, flatShading: true }),
  white: new THREE.MeshStandardMaterial({ color: 0xe9e4dc, roughness: 0.55, metalness: 0.25 }),
  dark: new THREE.MeshStandardMaterial({ color: 0x23201f, roughness: 0.8, metalness: 0.3 }),
  metal: new THREE.MeshStandardMaterial({ color: 0x8d8a86, roughness: 0.4, metalness: 0.8 }),
  solar: new THREE.MeshStandardMaterial({ color: 0x1b2f6b, roughness: 0.3, metalness: 0.6, emissive: 0x0a1433, emissiveIntensity: 0.6 }),
  gold: new THREE.MeshStandardMaterial({ color: 0xd19a3a, roughness: 0.45, metalness: 0.85 }),
  lens: new THREE.MeshStandardMaterial({ color: 0x0d1b22, emissive: 0x5ce1ff, emissiveIntensity: 1.6, roughness: 0.2 }),
  pad: new THREE.MeshStandardMaterial({ color: 0x3a302c, roughness: 0.9, metalness: 0.1 }),
  holo: new THREE.MeshBasicMaterial({ color: C.holo, transparent: true, opacity: 0.13, depthWrite: false, fog: false }),
  holoLine: new THREE.LineBasicMaterial({ color: C.holo, transparent: true, opacity: 0.6, fog: false }),
};
const worldCache = new Map();
function sharedWorld(world) {
  const key = JSON.stringify(world);
  if (worldCache.has(key)) return worldCache.get(key);
  const cx = world.width / 2, cy = world.height / 2;
  const inSand = (x, y) => world.sand.some(r => x >= r.x1 && x <= r.x2 && y >= r.y1 && y <= r.y2);
  // ground
  const size = 420, segments = 210;
  const ground = new THREE.PlaneGeometry(size, size, segments, segments);
  ground.rotateX(-Math.PI / 2);
  const pos = ground.attributes.position, colors = new Float32Array(pos.count * 3), color = new THREE.Color();
  for (let i = 0; i < pos.count; i++) {
    const x = pos.getX(i), z = pos.getZ(i), h = terrainHeight(x, z);
    pos.setY(i, h);
    const n = fbm(x * 0.06 + 5, z * 0.06 + 2, 4), n2 = fbm(x * 0.21 + 9, z * 0.21 + 4, 2);
    color.setRGB(0.50 + n * 0.20 + n2 * 0.05, 0.245 + n * 0.10 + n2 * 0.03, 0.135 + n * 0.055, THREE.SRGBColorSpace);
    if (h > 3) color.lerp(new THREE.Color().setRGB(0.42, 0.23, 0.16, THREE.SRGBColorSpace), smooth(3, 16, h) * 0.55);
    colors[i * 3] = color.r; colors[i * 3 + 1] = color.g; colors[i * 3 + 2] = color.b;
  }
  ground.setAttribute('color', new THREE.BufferAttribute(colors, 3));
  ground.computeVertexNormals();
  // sand overlays with soft edges
  const sands = world.sand.map(r => {
    const w = r.x2 - r.x1, h = r.y2 - r.y1, sx = Math.max(2, Math.round(w / 0.75)), sy = Math.max(2, Math.round(h / 0.75));
    const g = new THREE.PlaneGeometry(w, h, sx, sy);
    g.rotateX(-Math.PI / 2);
    const p = g.attributes.position, rgba = new Float32Array(p.count * 4), uv = g.attributes.uv;
    for (let i = 0; i < p.count; i++) {
      const lx = p.getX(i) + w / 2, lz = p.getZ(i) + h / 2;
      const gx = r.x1 + lx, gy = r.y2 - lz;
      const edge = Math.min(gx > 0.5 && r.x1 > 0.01 ? lx : 9, r.x2 < world.width - 0.01 ? w - lx : 9, r.y2 < world.height - 0.01 ? lz : 9, r.y1 > 0.01 ? h - lz : 9);
      const dune = 0.05 + 0.09 * fbm(gx * 0.35, gy * 0.35, 3);
      p.setY(i, dune * smooth(0, 1.6, edge));
      const tone = 0.86 + 0.2 * fbm(gx * 0.12 + 3, gy * 0.12, 3);
      rgba[i * 4] = tone; rgba[i * 4 + 1] = tone; rgba[i * 4 + 2] = tone; rgba[i * 4 + 3] = smooth(0, 0.9, edge);
      uv.setXY(i, gx / 4.5, gy / 4.5);
    }
    g.setAttribute('color', new THREE.BufferAttribute(rgba, 4));
    g.computeVertexNormals();
    return { geometry: g, x: r.x1 + w / 2 - cx, z: -(r.y1 + h / 2 - cy) };
  });
  // scattered rocks: pebbles in the driving area, boulders outside it
  const rocks = [];
  const rng = (() => { let s = 12345; return () => (s = (s * 16807) % 2147483647) / 2147483647; })();
  for (let i = 0; i < 620; i++) {
    const far = i > 170;
    const radius = far ? 26 + rng() * 150 : rng() * 27;
    const angle = rng() * TAU;
    const x = Math.cos(angle) * radius, z = Math.sin(angle) * radius;
    const sx = x + cx, sy = cy - z;
    const inside = sx > -1 && sx < world.width + 1 && sy > -1 && sy < world.height + 1;
    const nearEdge = !inside && sx > -5 && sx < world.width + 5 && sy > -5 && sy < world.height + 5;
    if (nearEdge || (inside && (inSand(sx, sy) || Math.hypot(sx - world.base[0], sy - world.base[1]) < 3))) continue;
    const scale = inside ? 0.05 + rng() * 0.11 : 0.3 + Math.pow(rng(), 2.2) * 2.6;
    rocks.push({ x, z, y: terrainHeight(x, z) + scale * 0.25, scale, rx: rng() * TAU, ry: rng() * TAU, sq: 0.55 + rng() * 0.5 });
  }
  const shared = { key, cx, cy, ground, sands, rocks, rockGeometry: new THREE.IcosahedronGeometry(1, 1) };
  // roughen the rock shape once
  const rp = shared.rockGeometry.attributes.position;
  for (let i = 0; i < rp.count; i++) {
    const k = 0.78 + 0.44 * hash2(rp.getX(i) * 3.1 + rp.getY(i) * 1.7, rp.getZ(i) * 2.3);
    rp.setXYZ(i, rp.getX(i) * k, rp.getY(i) * k, rp.getZ(i) * k);
  }
  shared.rockGeometry.computeVertexNormals();
  worldCache.set(key, shared);
  return shared;
}

function box(w, h, d, material, x = 0, y = 0, z = 0) {
  const mesh = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), material);
  mesh.position.set(x, y, z); mesh.castShadow = true; mesh.receiveShadow = true;
  return mesh;
}
function cyl(rt, rb, h, material, x = 0, y = 0, z = 0, seg = 16) {
  const mesh = new THREE.Mesh(new THREE.CylinderGeometry(rt, rb, h, seg), material);
  mesh.position.set(x, y, z); mesh.castShadow = true; mesh.receiveShadow = true;
  return mesh;
}
// A six-wheeled rover facing +x, about 2.4 m long.
function makeRover() {
  const rover = new THREE.Group(), body = new THREE.Group();
  body.add(box(1.3, 0.3, 0.82, MAT.white, 0, 0.66, 0));
  body.add(box(1.5, 0.045, 1.02, MAT.solar, -0.05, 0.86, 0));
  body.add(box(0.34, 0.3, 0.42, MAT.metal, -0.78, 0.74, 0));           // power unit
  body.add(box(0.5, 0.12, 0.5, MAT.gold, 0.5, 0.56, 0));               // instrument bay
  body.add(cyl(0.035, 0.045, 0.82, MAT.metal, 0.5, 1.28, 0.26, 8));    // mast
  const head = new THREE.Group();
  head.add(box(0.3, 0.17, 0.4, MAT.white));
  for (const z of [-0.1, 0.1]) { const eye = cyl(0.05, 0.05, 0.05, MAT.lens, 0.16, 0, z, 12); eye.rotation.z = Math.PI / 2; head.add(eye); }
  head.position.set(0.5, 1.74, 0.26); body.add(head);
  const dish = cyl(0.27, 0.05, 0.1, MAT.white, -0.36, 1.2, -0.24, 18); dish.rotation.set(0.5, 0, 0.35); body.add(dish);
  body.add(cyl(0.02, 0.02, 0.36, MAT.metal, -0.36, 1.02, -0.24, 6));
  const arm = box(0.62, 0.06, 0.06, MAT.metal, 0.92, 0.6, -0.2); arm.rotation.z = -0.5; body.add(arm);
  const wheels = [];
  for (const side of [-1, 1]) {
    body.add(box(1.36, 0.07, 0.07, MAT.metal, 0, 0.46, side * 0.5));
    for (const x of [0.6, 0, -0.6]) {
      body.add(box(0.06, 0.26, 0.06, MAT.metal, x, 0.36, side * 0.5));
      const wheel = new THREE.Group();
      const tyre = cyl(0.25, 0.25, 0.2, MAT.dark, 0, 0, 0, 14); tyre.rotation.x = Math.PI / 2; wheel.add(tyre);
      for (let k = 0; k < 7; k++) { const tread = box(0.07, 0.035, 0.21, MAT.metal); const a = k * TAU / 7; tread.position.set(Math.cos(a) * 0.25, Math.sin(a) * 0.25, 0); tread.rotation.z = a + Math.PI / 2; wheel.add(tread); }
      wheel.position.set(x, 0.25, side * 0.58);
      body.add(wheel); wheels.push(wheel);
    }
  }
  rover.add(body);
  rover.scale.setScalar(1.3);
  rover.userData = { wheels, head, body };
  return rover;
}
// The same shape as a hologram: where the operator last saw the rover.
function makeGhost(source) {
  const ghost = new THREE.Group();
  source.updateMatrixWorld(true);
  source.traverse(node => {
    if (!node.isMesh) return;
    const fill = new THREE.Mesh(node.geometry, MAT.holo);
    fill.applyMatrix4(node.matrixWorld); ghost.add(fill);
    const lines = new THREE.LineSegments(new THREE.EdgesGeometry(node.geometry, 30), MAT.holoLine);
    lines.applyMatrix4(node.matrixWorld); ghost.add(lines);
  });
  return ghost;
}
function makeLander() {
  const lander = new THREE.Group();
  lander.add(cyl(1.15, 1.4, 0.9, MAT.gold, 0, 1.25, 0, 6));
  lander.add(cyl(0.9, 1.15, 0.35, MAT.white, 0, 1.87, 0, 6));
  for (let k = 0; k < 3; k++) {
    const a = k * TAU / 3 + 0.4, leg = cyl(0.05, 0.05, 1.9, MAT.metal, Math.cos(a) * 1.5, 0.75, Math.sin(a) * 1.5, 6);
    leg.rotation.z = Math.cos(a) * 0.55; leg.rotation.x = -Math.sin(a) * 0.55; lander.add(leg);
    lander.add(cyl(0.3, 0.34, 0.07, MAT.metal, Math.cos(a) * 2.0, 0.04, Math.sin(a) * 2.0, 12));
  }
  for (const side of [-1, 1]) { const wing = box(2.6, 0.05, 1.2, MAT.solar, side * 2.5, 1.55, 0); wing.rotation.z = side * -0.12; lander.add(wing); }
  lander.add(cyl(0.03, 0.03, 1.5, MAT.metal, 0.2, 2.75, 0.1, 6));
  const dish = cyl(0.62, 0.08, 0.2, MAT.white, 0.2, 3.5, 0.1, 20); dish.rotation.set(0.75, 0.4, 0.2); lander.add(dish);
  const beacon = new THREE.Mesh(new THREE.SphereGeometry(0.1, 12, 8), new THREE.MeshBasicMaterial({ color: C.tel, fog: false }));
  beacon.position.set(-0.4, 2.2, -0.3); lander.add(beacon);
  lander.userData.beacon = beacon;
  return lander;
}
const SKY = new THREE.Mesh(new THREE.SphereGeometry(900, 32, 18), new THREE.ShaderMaterial({
  side: THREE.BackSide, depthWrite: false, fog: false,
  uniforms: { sun: { value: new THREE.Vector3(-0.55, 0.42, -0.72).normalize() } },
  vertexShader: 'varying vec3 d; void main(){ d = normalize(position); gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }',
  fragmentShader: `varying vec3 d; uniform vec3 sun;
    void main(){ vec3 n = normalize(d); float h = max(n.y, 0.0);
      vec3 col = mix(vec3(0.905, 0.705, 0.50), vec3(0.50, 0.375, 0.325), pow(h, 0.5));
      float s = max(dot(n, sun), 0.0);
      col += vec3(0.62, 0.78, 1.0) * pow(s, 420.0) * 1.3 + vec3(0.55, 0.68, 0.92) * pow(s, 24.0) * 0.26 + vec3(0.95, 0.8, 0.62) * pow(s, 4.0) * 0.10;
      if (n.y < 0.0) col = mix(vec3(0.905, 0.705, 0.50), vec3(0.42, 0.25, 0.17), clamp(-n.y * 6.0, 0.0, 1.0));
      gl_FragColor = vec4(col, 1.0); }`,
}));
const FOG_COLOR = new THREE.Color().setRGB(0.905, 0.705, 0.50, THREE.SRGBColorSpace);

// ---------------------------------------------------------------- one run's scene
class MarsScene {
  constructor(run) {
    this.run = run;
    const world = run.world, shared = this.shared = sharedWorld(world);
    const scene = this.scene = new THREE.Scene();
    scene.fog = new THREE.FogExp2(FOG_COLOR, 0.0052);
    scene.background = FOG_COLOR;
    scene.add(SKY.clone());
    scene.add(new THREE.HemisphereLight(0xf2d2b0, 0x6e3d28, 1.25));
    const sun = this.sun = new THREE.DirectionalLight(0xfff0dc, 2.7);
    sun.position.set(-55, 42, -72).multiplyScalar(0.9);
    sun.castShadow = true; sun.shadow.mapSize.set(2048, 2048); sun.shadow.bias = -0.0006; sun.shadow.normalBias = 0.03;
    Object.assign(sun.shadow.camera, { left: -34, right: 34, top: 34, bottom: -34, near: 10, far: 220 });
    scene.add(sun, sun.target);
    const ground = new THREE.Mesh(shared.ground, MAT.ground); ground.receiveShadow = true; scene.add(ground);
    for (const s of shared.sands) { const mesh = new THREE.Mesh(s.geometry, MAT.sand); mesh.position.set(s.x, 0.012, s.z); mesh.receiveShadow = true; mesh.renderOrder = 1; scene.add(mesh); }
    const rocks = new THREE.InstancedMesh(shared.rockGeometry, MAT.rock, shared.rocks.length);
    const m = new THREE.Matrix4(), q = new THREE.Quaternion(), e = new THREE.Euler();
    shared.rocks.forEach((r, i) => { e.set(r.rx, r.ry, 0); q.setFromEuler(e); m.compose(new THREE.Vector3(r.x, r.y, r.z), q, new THREE.Vector3(r.scale, r.scale * r.sq, r.scale)); rocks.setMatrixAt(i, m); });
    rocks.castShadow = rocks.receiveShadow = true; scene.add(rocks);
    this.tactical = new THREE.Group(); scene.add(this.tactical);   // drawn only on the map
    this.cinematic = new THREE.Group(); scene.add(this.cinematic); // drawn only in 3D views
    this.buildArena(world); this.buildHazards(world); this.buildBase(world); this.buildTargets(world); this.buildDynamic();
  }
  P(x, y, h = 0) { return new THREE.Vector3(x - this.shared.cx, h, -(y - this.shared.cy)); }
  // Scale every label so it is the same height in pixels whatever the camera distance.
  fitLabels(camera, viewHeight) {
    const v = new THREE.Vector3();
    this.scene.traverse(node => {
      if (!node.isSprite || !node.userData.px) return;
      let perPixel;
      if (camera.isOrthographicCamera) perPixel = (camera.top - camera.bottom) / viewHeight;
      else perPixel = 2 * Math.tan(THREE.MathUtils.degToRad(camera.fov) / 2) * Math.max(0.5, camera.position.distanceTo(node.getWorldPosition(v))) / viewHeight;
      const h = perPixel * node.userData.px;
      node.scale.set(h * node.userData.aspect, h, 1);
    });
  }
  buildArena(world) {
    const { width: w, height: h } = world, corners = [[0, 0], [w, 0], [w, h], [0, h], [0, 0]].map(([x, y]) => this.P(x, y, 0.06));
    const border = new THREE.Line(new THREE.BufferGeometry().setFromPoints(corners), new THREE.LineDashedMaterial({ color: 0xffe2c4, dashSize: 0.9, gapSize: 0.9, transparent: true, opacity: 0.5 }));
    border.computeLineDistances(); this.scene.add(border);
    for (const [x, y] of [[0, 0], [w, 0], [w, h], [0, h]]) { const post = cyl(0.07, 0.07, 1.5, MAT.metal, 0, 0.75, 0, 6); post.position.copy(this.P(x, y, 0.75)); this.scene.add(post);
      const lamp = new THREE.Mesh(new THREE.SphereGeometry(0.13, 10, 8), new THREE.MeshBasicMaterial({ color: C.accent, fog: false })); lamp.position.copy(this.P(x, y, 1.55)); this.scene.add(lamp); }
    const grid = new THREE.GridHelper(Math.max(w, h), Math.max(w, h) / 5, 0xffe2c4, 0xffe2c4);
    grid.material.transparent = true; grid.material.opacity = 0.16; grid.material.fog = false; grid.position.y = 0.05; this.tactical.add(grid);
  }
  buildHazards(world) {
    this.hazardLines = [];
    let seed = 7; const rng = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
    for (const r of world.hazards) {
      const w = r.x2 - r.x1, h = r.y2 - r.y1, count = Math.round(w * h * 2.4) + 6;
      const boulders = new THREE.InstancedMesh(this.shared.rockGeometry, MAT.basalt, count), m = new THREE.Matrix4(), q = new THREE.Quaternion(), e = new THREE.Euler();
      for (let i = 0; i < count; i++) {
        const s = 0.22 + rng() * 0.5; e.set(rng() * TAU, rng() * TAU, 0); q.setFromEuler(e);
        m.compose(this.P(r.x1 + rng() * w, r.y1 + rng() * h, s * 0.45), q, new THREE.Vector3(s, s * (0.7 + rng() * 0.7), s)); boulders.setMatrixAt(i, m);
      }
      boulders.castShadow = boulders.receiveShadow = true; this.scene.add(boulders);
      const pts = [[r.x1, r.y1], [r.x2, r.y1], [r.x2, r.y2], [r.x1, r.y2], [r.x1, r.y1]].map(([x, y]) => this.P(x, y, 0.09));
      const line = new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), new THREE.LineBasicMaterial({ color: C.bad, transparent: true, fog: false }));
      this.scene.add(line); this.hazardLines.push(line);
      const plate = new THREE.Mesh(new THREE.PlaneGeometry(w, h), new THREE.MeshBasicMaterial({ color: C.bad, transparent: true, opacity: 0.32, depthWrite: false, fog: false }));
      plate.rotation.x = -Math.PI / 2; plate.position.copy(this.P((r.x1 + r.x2) / 2, (r.y1 + r.y2) / 2, 0.07)); this.tactical.add(plate);
    }
  }
  buildBase(world) {
    const [bx, by] = world.base, cfg = this.run.cfg;
    const pad = cyl(1.7, 1.7, 0.05, MAT.pad, 0, 0, 0, 40); pad.position.copy(this.P(bx, by, 0.02)); pad.castShadow = false; this.scene.add(pad);
    const ring = new THREE.Mesh(new THREE.RingGeometry(cfg.base_radius - 0.06, cfg.base_radius + 0.06, 48), new THREE.MeshBasicMaterial({ color: C.tel, side: THREE.DoubleSide, transparent: true, opacity: 0.95, fog: false }));
    ring.rotation.x = -Math.PI / 2; ring.position.copy(this.P(bx, by, 0.06)); this.scene.add(ring);
    this.lander = makeLander(); this.lander.position.copy(this.P(bx + 8.5, by - 9.5, 0)); this.lander.rotation.y = 2.4; this.cinematic.add(this.lander);
    const label = labelSprite('BASE', '#5ce1ff'); label.position.copy(this.P(bx, by, 2.6)); this.cinematic.add(label);
    const mapLabel = labelSprite('BASE', '#5ce1ff', 0.9); mapLabel.position.copy(this.P(bx, by - 3.6, 3)); this.tactical.add(mapLabel);
  }
  buildTargets(world) {
    this.targets = world.targets.map(t => {
      const group = new THREE.Group(); group.position.copy(this.P(t.x, t.y, 0));
      const material = new THREE.MeshBasicMaterial({ color: C.cmd, transparent: true, opacity: 0.95, side: THREE.DoubleSide, fog: false });
      const r = this.run.cfg.target_radius;
      const ring = new THREE.Mesh(new THREE.RingGeometry(r - 0.07, r + 0.03, 48), material); ring.rotation.x = -Math.PI / 2; ring.position.y = 0.2; group.add(ring);
      const disc = new THREE.Mesh(new THREE.CircleGeometry(r - 0.07, 40), new THREE.MeshBasicMaterial({ color: C.cmd, transparent: true, opacity: 0.16, depthWrite: false, fog: false }));
      disc.rotation.x = -Math.PI / 2; disc.position.y = 0.19; group.add(disc);
      const beam = new THREE.Mesh(new THREE.CylinderGeometry(0.16, 0.16, 14, 12, 1, true), new THREE.MeshBasicMaterial({ color: C.cmd, map: TEX.beam, transparent: true, opacity: 0.75, depthWrite: false, side: THREE.DoubleSide, blending: THREE.AdditiveBlending, fog: false }));
      beam.material.map = TEX.beam.clone(); beam.material.map.repeat.set(1, 1); beam.position.y = 7; group.add(beam);
      const gem = new THREE.Mesh(new THREE.OctahedronGeometry(0.34), new THREE.MeshStandardMaterial({ color: C.cmd, emissive: C.cmd, emissiveIntensity: 0.9, roughness: 0.3, metalness: 0.4 })); gem.position.y = 2.3; group.add(gem);
      const name = `${t.id.toUpperCase()} · ${t.value} pt${t.value === 1 ? '' : 's'}`;
      const open = labelSprite(name, '#ffd166'), done = labelSprite('✓ ' + name, '#7cf29c');
      open.position.y = done.position.y = 3.25; group.add(open, done);
      const mapOpen = labelSprite(name, '#ffd166', 0.9), mapDone = labelSprite('✓ ' + name, '#7cf29c', 0.9);
      for (const s of [mapOpen, mapDone]) { s.position.copy(this.P(t.x, t.y + 1.5, 3)); this.tactical.add(s); }
      this.cinematic.add(beam, gem, open, done); // re-parented so they stay off the map
      for (const node of [beam, gem, open, done]) node.position.add(group.position);
      this.scene.add(group);
      return { id: t.id, group, ring, disc, beam, gem, open, done, mapOpen, mapDone, material };
    });
  }
  buildDynamic() {
    const scene = this.scene;
    this.rover = makeRover(); scene.add(this.rover);
    this.ghost = makeGhost(makeRover()); scene.add(this.ghost);
    this.ghostBeam = new THREE.Mesh(new THREE.CylinderGeometry(0.05, 0.05, 5, 8), new THREE.MeshBasicMaterial({ color: C.holo, transparent: true, opacity: 0.55, fog: false })); scene.add(this.ghostBeam);
    this.ghostLabel = labelSprite(`seen ${this.run.K} ticks ago`, '#c7a6ff', 0.8); this.cinematic.add(this.ghostLabel);
    this.tether = new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(), new THREE.Vector3()]), new THREE.LineDashedMaterial({ color: C.holo, dashSize: 0.35, gapSize: 0.25, transparent: true, opacity: 0.8, fog: false })); scene.add(this.tether);
    // wheel tracks: two ribbons revealed as time passes
    const quads = this.run.T * 2;
    this.trackPositions = new Float32Array(quads * 18);
    const trackGeometry = new THREE.BufferGeometry(); trackGeometry.setAttribute('position', new THREE.BufferAttribute(this.trackPositions, 3));
    this.tracks = new THREE.Mesh(trackGeometry, new THREE.MeshBasicMaterial({ color: 0x4a2414, transparent: true, opacity: 0.6, depthWrite: false, polygonOffset: true, polygonOffsetFactor: -4, polygonOffsetUnits: -4 }));
    this.tracks.frustumCulled = false; this.tracks.renderOrder = 2; scene.add(this.tracks);
    this.pathPositions = new Float32Array((this.run.T + 2) * 3);
    const pathGeometry = new THREE.BufferGeometry(); pathGeometry.setAttribute('position', new THREE.BufferAttribute(this.pathPositions, 3));
    this.path = new THREE.Line(pathGeometry, new THREE.LineBasicMaterial({ color: C.ok, transparent: true, opacity: 0.95, fog: false })); this.path.frustumCulled = false; this.tactical.add(this.path);
    this.ribbonPositions = new Float32Array(this.run.T * 18);
    const ribbonGeometry = new THREE.BufferGeometry(); ribbonGeometry.setAttribute('position', new THREE.BufferAttribute(this.ribbonPositions, 3));
    this.ribbon = new THREE.Mesh(ribbonGeometry, new THREE.MeshBasicMaterial({ color: C.ok, transparent: true, opacity: 0.85, depthWrite: false, depthTest: false, side: THREE.DoubleSide, fog: false }));
    this.ribbon.frustumCulled = false; this.ribbon.renderOrder = 4; this.tactical.add(this.ribbon);
    const marker = (color, inner, outer) => { const m = new THREE.Mesh(new THREE.RingGeometry(inner, outer, 40), new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.95, side: THREE.DoubleSide, depthTest: false, fog: false })); m.rotation.x = -Math.PI / 2; m.renderOrder = 6; this.tactical.add(m); return m; };
    this.mapRover = marker(C.ok, 1.25, 1.6); this.mapGhost = marker(C.holo, 1.25, 1.5);
    this.mapNose = new THREE.Mesh(new THREE.ConeGeometry(0.75, 1.5, 3), new THREE.MeshBasicMaterial({ color: C.ok, depthTest: false, fog: false })); this.mapNose.renderOrder = 6; this.tactical.add(this.mapNose);
    // queued commands
    this.queuePositions = new Float32Array(64 * 3);
    const queueGeometry = new THREE.BufferGeometry(); queueGeometry.setAttribute('position', new THREE.BufferAttribute(this.queuePositions, 3));
    this.queue = new THREE.Line(queueGeometry, new THREE.LineDashedMaterial({ color: C.cmd, dashSize: 0.45, gapSize: 0.28, fog: false })); this.queue.frustumCulled = false; scene.add(this.queue);
    this.queueTip = new THREE.Mesh(new THREE.ConeGeometry(0.28, 0.7, 12), new THREE.MeshBasicMaterial({ color: C.cmd, fog: false })); scene.add(this.queueTip);
    this.queueNodes = Array.from({ length: 8 }, () => { const node = new THREE.Mesh(new THREE.SphereGeometry(0.13, 10, 8), new THREE.MeshBasicMaterial({ color: C.cmd, fog: false })); scene.add(node); return node; });
    // belief marker
    this.believed = new THREE.Group();
    for (const a of [Math.PI / 4, -Math.PI / 4]) { const bar = new THREE.Mesh(new THREE.BoxGeometry(1.5, 0.06, 0.14), new THREE.MeshBasicMaterial({ color: 0xffffff, fog: false })); bar.rotation.y = a; this.believed.add(bar); }
    this.believed.position.y = 0.3; scene.add(this.believed);
    // effects
    const glow = color => new THREE.Mesh(new THREE.RingGeometry(0.9, 1.0, 48), new THREE.MeshBasicMaterial({ color, transparent: true, side: THREE.DoubleSide, depthWrite: false, fog: false }));
    this.pulse = glow(C.ok); this.pulse.rotation.x = -Math.PI / 2; scene.add(this.pulse);
    this.signal = new THREE.Mesh(new THREE.CylinderGeometry(0.5, 0.12, 40, 16, 1, true), new THREE.MeshBasicMaterial({ color: C.cmd, map: TEX.beam, transparent: true, depthWrite: false, side: THREE.DoubleSide, blending: THREE.AdditiveBlending, fog: false }));
    scene.add(this.signal);
    this.dust = Array.from({ length: 22 }, () => { const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: TEX.dot, color: 0xd8a476, transparent: true, depthWrite: false })); scene.add(s); return s; });
    this.dead = labelSprite('POWER LOST', '#ff5d5d'); this.cinematic.add(this.dead);
    const motes = 420, mp = new Float32Array(motes * 3);
    for (let i = 0; i < motes; i++) { mp[i * 3] = (hash2(i, 1.3) - 0.5) * 90; mp[i * 3 + 1] = 0.3 + hash2(i, 7.7) * 9; mp[i * 3 + 2] = (hash2(i, 4.1) - 0.5) * 90; }
    const moteGeometry = new THREE.BufferGeometry(); moteGeometry.setAttribute('position', new THREE.BufferAttribute(mp, 3));
    this.motes = new THREE.Points(moteGeometry, new THREE.PointsMaterial({ map: TEX.dot, color: 0xffd9b0, size: 0.085, transparent: true, opacity: 0.4, depthWrite: false, sizeAttenuation: true }));
    this.motes.frustumCulled = false; this.cinematic.add(this.motes);
  }
  // Draw the world for one screen. kind: 'live' | 'feed' | 'map' | 'wide'. t: mission time in ticks.
  apply(kind, t, wall) {
    const run = this.run, feed = kind === 'feed', map = kind === 'map';
    const tv = feed ? Math.max(0, t - run.K) : t;          // the moment this screen shows
    const pose = run.sample(tv), state = run.stateAt(tv);
    this.pose = pose;
    this.tactical.visible = map; this.cinematic.visible = !map;
    this.scene.fog.density = map ? 0 : 0.0052;
    // rover
    const p = this.P(pose.x, pose.y, 0);
    this.rover.position.copy(p); this.rover.rotation.y = THREE.MathUtils.degToRad(pose.heading);
    for (const wheel of this.rover.userData.wheels) wheel.rotation.z = -pose.wheel / 0.25;
    this.rover.userData.body.position.y = pose.moving ? Math.sin(wall * 19) * 0.012 : 0;
    this.rover.userData.head.rotation.y = Math.sin(wall * 0.7) * 0.5;
    this.rover.scale.setScalar(map ? 2.1 : 1.3);
    // where the operator last saw it (not on the delayed feed, which *is* that view)
    const seen = run.sample(Math.max(0, t - run.K)), gp = this.P(seen.x, seen.y, 0);
    const apart = Math.hypot(seen.x - pose.x, seen.y - pose.y);
    const showGhost = !feed && apart > 0.25;
    this.ghost.visible = this.ghostBeam.visible = this.tether.visible = showGhost; this.ghostLabel.visible = showGhost && !map;
    this.mapGhost.visible = showGhost; this.mapGhost.position.set(gp.x, 0.45, gp.z);
    if (showGhost) {
      this.ghost.position.copy(gp); this.ghost.rotation.y = THREE.MathUtils.degToRad(seen.heading); this.ghost.scale.setScalar(map ? 2.1 : 1.3);
      this.ghostBeam.position.set(gp.x, 2.5, gp.z); this.ghostLabel.position.set(gp.x, 4.1, gp.z);
      const line = this.tether.geometry.attributes.position; line.setXYZ(0, p.x, 0.5, p.z); line.setXYZ(1, gp.x, 0.5, gp.z); line.needsUpdate = true; this.tether.computeLineDistances();
    }
    // tracks and path up to the shown moment
    let v = 0, rv = 0; const tp = this.trackPositions, pp = this.pathPositions, rp = this.ribbonPositions, upto = Math.min(run.T, Math.ceil(tv));
    pp[0] = this.P(run.states[0].position[0], run.states[0].position[1]).x; pp[1] = 0.25; pp[2] = this.P(run.states[0].position[0], run.states[0].position[1]).z;
    let pathCount = 1;
    for (let i = 0; i < upto; i++) {
      if (run.moved[i + 1] < 1e-6) continue;
      const a = run.states[i].position, last = i + 1 > tv, b = last ? [pose.x, pose.y] : run.states[i + 1].position;
      const A = this.P(a[0], a[1], 0.03), B = this.P(b[0], b[1], 0.03), dx = B.x - A.x, dz = B.z - A.z, len = Math.hypot(dx, dz) || 1, nx = -dz / len, nz = dx / len;
      for (const side of [-0.72, 0.72]) for (const [ox, oz, w] of [[A, A, -1], [B, B, -1], [B, B, 1], [A, A, -1], [B, B, 1], [A, A, 1]]) {
        const base = ox; tp[v++] = base.x + nx * (side + w * 0.1); tp[v++] = 0.035; tp[v++] = base.z + nz * (side + w * 0.1);
      }
      pp[pathCount * 3] = B.x; pp[pathCount * 3 + 1] = 0.25; pp[pathCount * 3 + 2] = B.z; pathCount++;
      for (const [base, w] of [[A, -1], [B, -1], [B, 1], [A, -1], [B, 1], [A, 1]]) { rp[rv++] = base.x + nx * w * 0.2; rp[rv++] = 0.2; rp[rv++] = base.z + nz * w * 0.2; }
    }
    this.ribbon.geometry.setDrawRange(0, rv / 3); this.ribbon.geometry.attributes.position.needsUpdate = true;
    const hr = THREE.MathUtils.degToRad(pose.heading);
    this.mapRover.position.set(p.x, 0.5, p.z);
    this.mapNose.position.set(p.x + Math.cos(hr) * 2.3, 0.5, p.z - Math.sin(hr) * 2.3); this.mapNose.rotation.set(0, 0, 0); this.mapNose.rotation.z = -Math.PI / 2; this.mapNose.rotation.y = hr; this.mapNose.rotation.order = 'YXZ';
    this.tracks.geometry.setDrawRange(0, v / 3); this.tracks.geometry.attributes.position.needsUpdate = true;
    this.path.geometry.setDrawRange(0, pathCount); this.path.geometry.attributes.position.needsUpdate = true;
    // commands that have been sent but whose effect this screen has not shown yet
    const pending = run.commands.filter(c => c.sent <= t && (feed ? c.exec > tv : tv < c.until) && (feed || c.done || tv < c.until));
    const qp = this.queuePositions; let cursor = p.clone(), count = 1, nodes = 0; qp[0] = cursor.x; qp[1] = 0.32; qp[2] = cursor.z;
    for (const c of pending) if (c.action === 'drive' && count < 63) {
      const a = THREE.MathUtils.degToRad(c.heading_deg); cursor = cursor.clone().add(new THREE.Vector3(Math.cos(a) * c.metres, 0, -Math.sin(a) * c.metres));
      qp[count * 3] = cursor.x; qp[count * 3 + 1] = 0.32; qp[count * 3 + 2] = cursor.z; count++;
      if (nodes < this.queueNodes.length) this.queueNodes[nodes++].position.set(cursor.x, 0.32, cursor.z);
    }
    this.queue.visible = this.queueTip.visible = count > 1;
    this.queueNodes.forEach((node, i) => { node.visible = i < nodes - 1; node.scale.setScalar(map ? 2 : 1); });
    if (count > 1) {
      this.queue.geometry.setDrawRange(0, count); this.queue.geometry.attributes.position.needsUpdate = true; this.queue.computeLineDistances();
      const ax = qp[(count - 2) * 3], az = qp[(count - 2) * 3 + 2];
      this.queueTip.position.set(cursor.x, 0.32, cursor.z); this.queueTip.rotation.set(0, 0, 0);
      this.queueTip.lookAt(cursor.x * 2 - ax, 0.32, cursor.z * 2 - az); this.queueTip.rotateX(Math.PI / 2); this.queueTip.scale.setScalar(map ? 2.2 : 1);
    }
    // the controller's own estimate, when it recorded one
    const belief = !feed && run.belief.get(Math.floor(tv + 1e-6));
    this.believed.visible = !!belief;
    if (belief) { const bp = this.P(belief[0], belief[1]); this.believed.position.set(bp.x, 0.34, bp.z); this.believed.scale.setScalar(map ? 1.5 : 0.8); this.believed.rotation.y = wall * 0.8; }
    // targets as known at the shown moment
    for (const target of this.targets) {
      const got = state.sampled_targets.includes(target.id);
      target.material.color.setHex(got ? C.ok : C.cmd); target.disc.material.color.setHex(got ? C.ok : C.cmd); target.disc.material.opacity = got ? 0.4 : 0.14 + 0.06 * Math.sin(wall * 2.5);
      target.beam.material.color.setHex(got ? C.ok : C.cmd); target.beam.material.opacity = got ? 0.35 : 0.6 + 0.2 * Math.sin(wall * 2.2 + target.group.position.x);
      target.gem.material.color.setHex(got ? C.ok : C.cmd); target.gem.material.emissive.setHex(got ? C.ok : C.cmd);
      target.gem.rotation.y = wall * (got ? 0.3 : 1.4); target.gem.position.y = (got ? 1.3 : 2.3 + Math.sin(wall * 2 + target.group.position.z) * 0.12);
      target.open.visible = !got; target.done.visible = got; target.mapOpen.visible = !got; target.mapDone.visible = got;
      const s = map ? 1.6 : 1; target.ring.scale.setScalar(s); target.disc.scale.setScalar(s);
    }
    for (const line of this.hazardLines) line.material.opacity = 0.55 + 0.4 * Math.sin(wall * 3);
    this.lander.userData.beacon.visible = Math.sin(wall * 4) > 0.2;
    // one-shot effects, as pure functions of the shown time so scrubbing works
    let pulse = 0, pulseColor = C.ok, pulseAge = 0;
    for (const event of run.events) {
      const age = tv - event.tick; if (age < 0 || age > 1.6) continue;
      if (event.type === 'sample_taken') { pulse = 1 - age / 1.6; pulseColor = C.ok; pulseAge = age; }
      if (event.type === 'safety_stop' || event.type === 'battery_depleted' || event.type === 'sample_failed') { pulse = 1 - age / 1.6; pulseColor = C.bad; pulseAge = age; }
    }
    this.pulse.visible = pulse > 0;
    if (pulse > 0) { this.pulse.position.set(p.x, 0.25, p.z); this.pulse.scale.setScalar(1 + pulseAge * 4.5); this.pulse.material.color.setHex(pulseColor); this.pulse.material.opacity = pulse; }
    let flash = 0;
    for (const c of run.commands) if (c.done) { const age = tv - (c.exec - 1); if (age >= -0.05 && age < 0.45) flash = Math.max(flash, 1 - age / 0.45); }
    this.signal.visible = flash > 0 && !map;
    if (this.signal.visible) { this.signal.position.set(p.x, 21, p.z); this.signal.material.opacity = flash * 0.85; }
    this.dust.forEach((sprite, i) => {
      const age = i * 0.07 + ((wall * 1.3) % 0.07), then = run.sample(tv - age * 0.9);
      sprite.visible = then.moving && !map && tv - age * 0.9 > 0;
      if (!sprite.visible) return;
      const d = this.P(then.x, then.y), jitter = hash2(i * 3.7, Math.floor(wall * 1.3 / 0.07) + i);
      sprite.position.set(d.x + (jitter - 0.5) * 0.9, 0.25 + age * 1.5, d.z + (hash2(jitter, i) - 0.5) * 0.9);
      const size = (0.5 + age * 3.2) * (then.sand ? 1.5 : 1); sprite.scale.set(size, size, 1);
      sprite.material.opacity = (then.sand ? 0.5 : 0.3) * (1 - age / 1.6);
    });
    this.dead.visible = !state.alive && !map; this.dead.position.set(p.x, 3.4, p.z);
    this.motes.position.set(((wall * 1.1) % 90) - 45 + p.x * 0.5, 0, Math.sin(wall * 0.11) * 4 + p.z * 0.5);
    this.sun.target.position.set(0, 0, 0);
    return { pose, state, tv, pending: pending.length, apart };
  }
}

// ---------------------------------------------------------------- screens
const renderer = new THREE.WebGLRenderer({ canvas: $('#gl'), antialias: true, powerPreference: 'high-performance' });
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.setClearColor(0x0a0605, 1);
const scenes = new Map(RUNS.map(run => [run.id, new MarsScene(run)]));

class Screen {
  constructor(kind, run) {
    this.kind = kind; this.run = run; this.scene = scenes.get(run.id);
    this.camera = kind === 'map' ? new THREE.OrthographicCamera(-1, 1, 1, -1, 1, 400) : new THREE.PerspectiveCamera(kind === 'wide' ? 40 : 52, 1, 0.3, 1600);
    this.eye = null; this.look = new THREE.Vector3(); this.heading = null;
  }
  frame(info, aspect, dt, wall) {
    const camera = this.camera, world = this.run.world, pose = info.pose;
    const p = this.scene.P(pose.x, pose.y, 0);
    if (this.kind === 'map') {
      // frame the part of the map this run uses
      const b = this.run.bounds, c = this.scene.P((b.x0 + b.x1) / 2, (b.y0 + b.y1) / 2);
      let hy = (b.y1 - b.y0) / 2, hx = (b.x1 - b.x0) / 2;
      if (hx / hy < aspect) hx = hy * aspect; else hy = hx / aspect;
      hy = Math.max(hy, 9); hx = hy * aspect;
      Object.assign(camera, { left: -hx, right: hx, top: hy, bottom: -hy }); camera.position.set(c.x, 200, c.z); camera.up.set(0, 0, -1); camera.lookAt(c.x, 0, c.z);
    } else if (this.kind === 'wide') {
      // a drone shot that keeps the rover and the base in frame
      const base = this.scene.P(world.base[0], world.base[1]);
      const focus = new THREE.Vector3(lerp(base.x, p.x, 0.62), 0, lerp(base.z, p.z, 0.62));
      if (!this.eye) this.look.copy(focus);
      this.look.lerp(focus, 1 - Math.exp(-dt * 1.4));
      const a = -0.72 + Math.sin(wall * 0.06) * 0.2, r = 27;
      this.eye = new THREE.Vector3(this.look.x + Math.sin(a) * r, 15.5, this.look.z + Math.cos(a) * r);
      camera.position.copy(this.eye); camera.lookAt(this.look);
    } else {
      // chase camera: behind and above, easing so the cut between ticks stays smooth
      const target = THREE.MathUtils.degToRad(pose.heading);
      if (this.heading === null) this.heading = target;
      const diff = Math.atan2(Math.sin(target - this.heading), Math.cos(target - this.heading));
      this.heading += diff * (1 - Math.exp(-dt * 1.6));
      const h = this.heading + Math.sin(wall * 0.13) * 0.25 + 0.5;
      const want = new THREE.Vector3(p.x - Math.cos(h) * 8.4, 4.1, p.z + Math.sin(h) * 8.4);
      const lander = this.scene.lander.position, away = Math.hypot(want.x - lander.x, want.z - lander.z);
      if (away < 7.5) { const k = 7.5 / Math.max(away, 0.01); want.x = lander.x + (want.x - lander.x) * k; want.z = lander.z + (want.z - lander.z) * k; want.y = 5.6; }
      if (!this.eye) { this.eye = want.clone(); this.look.set(p.x, 1, p.z); }
      this.eye.lerp(want, 1 - Math.exp(-dt * 2.6)); this.look.lerp(new THREE.Vector3(p.x, 1.05, p.z), 1 - Math.exp(-dt * 5));
      camera.position.copy(this.eye); camera.lookAt(this.look);
    }
    if (camera.isPerspectiveCamera) camera.aspect = aspect;
    camera.updateProjectionMatrix();
  }
}

// ---------------------------------------------------------------- interface
const stage = $('#stage'), scrub = $('#scrub'), playButton = $('#play'), clock = $('#clock b');
const state = { t: 0, playing: false, speed: 1.5, mode: 'mission', run: RUNS[0], screens: [], wall: 0 };
const T = Math.max(...RUNS.map(r => r.T));
scrub.max = T; $('#clock span').textContent = `/ ${T} ticks`; $('#introK').textContent = RUNS[0].K;
for (const run of RUNS) { const option = document.createElement('option'); option.value = run.id; option.textContent = run.label; $('#runpick').appendChild(option); }

const TOOLS = [
  ['rules', 'free', 'delay, costs, slip ranges', '§'], ['map', 'free', 'base, targets, hazards, sand', '⌖'], ['telemetry_log', 'free', 'every packet received so far', '≋'],
  ['uplink', 'send', 'queue 1–5 commands', '⇡'], ['advance', 'time', 'let 1–5 ticks pass', '»'], ['shell', 'shell', 'its own code, not an MCP tool', '>_'],
];
function describeCall(call) {
  if (call.kind === 'shell') { const text = (call.arguments.command || JSON.stringify(call.arguments)).replace(/\s+/g, ' '); return [`shell`, text.length > 80 ? text.slice(0, 78) + '…' : text]; }
  if (call.tool === 'uplink') {
    const list = (call.arguments.commands || []).map(c => c.action === 'drive' ? `drive ${(+c.heading_deg).toFixed(0)}° ${(+c.metres).toFixed(2)} m` : c.action).join(', ');
    const tail = call.ok ? ` → executes at tick ${(call.summary.execute_ticks || []).join(', ')}` : ` ✗ ${call.error}`;
    return ['uplink', `[${list}]${tail}`];
  }
  if (call.tool === 'advance') {
    if (!call.ok) return ['advance', `✗ ${call.error}`];
    const packets = (call.summary.packet_ticks || []);
    return ['advance', `${call.arguments.ticks ?? 1} ticks → tick ${call.tick_after}${packets.length ? ` · telemetry for tick ${packets[0]}${packets.length > 1 ? '–' + packets[packets.length - 1] : ''} arrived` : ' · no telemetry yet'}`];
  }
  if (call.tool === 'telemetry_log') return ['telemetry_log', `${call.summary.packets ?? ''} packets`];
  return [call.tool, call.tool === 'rules' ? 'reads the published rules' : 'reads the map'];
}
const pills = run => `
  <div class="pill bat">battery<b class="bat-v"></b><div class="meter"><i></i></div></div>
  <div class="pill samples">samples${run.world.targets.map(t => `<i data-id="${t.id}">${t.id} ${t.value}</i>`).join('')}</div>`;
function glScreen(kind, run, title, sub, extra = '') {
  const el = document.createElement('section');
  el.className = `view ${kind}`;
  el.innerHTML = `<div class="chip"><b><i class="dot"></i>${title}</b><span>${sub}</span></div><div class="tag"></div><div class="toast"></div>
    <div class="stats">${pills(run)}<div class="pill extra"></div></div>${extra}<div class="result"><b></b><span></span></div>`;
  stage.appendChild(el);
  const screen = new Screen(kind, run); screen.el = el; screen.shown = {};
  return screen;
}
function consolePanel(run) {
  const el = document.createElement('section');
  el.className = 'view panel';
  el.innerHTML = `<div class="console">
    <div class="who"><h2>${run.label}<small>${run.sub}</small></h2><div class="score">reward<b>—</b></div></div>
    <div><div class="label">MCP tools the agent can call · server “lightlag”</div><div class="tools">${TOOLS.map(([name, kind, text, glyph]) => `<div class="tool ${kind}" data-tool="${name}"><i>${glyph}</i><em>0</em><b>${name}</b><span>${text}</span></div>`).join('')}</div><div class="now"></div></div>
    <div class="link"><div class="label">Signal · ${run.K} ticks each way</div><canvas></canvas></div>
    <div class="log"></div>
    <div class="foot">${pills(run)}<div class="pill extra"></div></div></div>`;
  stage.appendChild(el);
  return { kind: 'console', run, el, shown: {}, canvas: $('canvas', el) };
}
function build() {
  stage.innerHTML = '';
  for (const button of document.querySelectorAll('#mode button')) button.classList.toggle('on', button.dataset.mode === state.mode);
  $('#runpick').style.display = state.mode === 'mission' ? '' : 'none';
  $('#runpick').value = state.run.id;
  const run = state.run;
  if (state.mode === 'mission') {
    state.screens = [
      glScreen('live', run, 'MARS · WHAT IS REALLY HAPPENING', 'the rover right now, which nobody on Earth can see yet'),
      glScreen('feed', run, `EARTH · WHAT THE OPERATOR SEES`, `the picture is ${run.K} ticks old when it arrives`),
      glScreen('map', run, 'MISSION MAP', 'north is up',
        `<div class="legend"><div><i style="background:#7cf29c"></i>real rover and its path</div><div><i style="border:2px solid #c7a6ff"></i>where the operator last saw it</div><div><i style="background:#ffd166"></i>commands sent, not yet executed</div>${run.belief.size ? '<div><b style="margin-right:5px">✕</b>where the controller believes it is</div>' : ''}</div>`),
      consolePanel(run),
    ];
  } else {
    state.screens = RUNS.slice(0, 4).map(r => glScreen('wide', r, r.label.toUpperCase(), r.sub));
  }
  if (state.mode === 'mission') { const badge = document.createElement('div'); badge.className = 'delay'; badge.innerHTML = `<i></i><b>${run.K} TICKS</b><span>signal delay</span><i></i>`; stage.appendChild(badge); }
  drawMarks();
}
function fitUi() { document.documentElement.style.setProperty('--s', clamp(Math.min(window.innerWidth / 1500, window.innerHeight / 820), 0.85, 1.7).toFixed(3)); }
function drawMarks() {
  const canvas = $('#marks'), rect = canvas.getBoundingClientRect(), dpr = window.devicePixelRatio || 1;
  canvas.width = rect.width * dpr; canvas.height = rect.height * dpr;
  const g = canvas.getContext('2d'); g.scale(dpr, dpr);
  const w = rect.width, h = rect.height, x = t => 8 + (w - 16) * t / T, run = state.run;
  g.fillStyle = 'rgba(255,255,255,.1)'; g.beginPath(); g.roundRect(8, h / 2 - 3, w - 16, 6, 3); g.fill();
  g.fillStyle = '#ff8a3d'; g.beginPath(); g.roundRect(8, h / 2 - 3, x(state.t) - 8, 6, 3); g.fill();
  if (state.mode === 'mission') for (const c of run.calls) if (c.tool === 'uplink') { g.fillStyle = c.ok ? '#ffd166' : '#ff5d5d'; g.fillRect(x(c.tick) - 1, h / 2 - 11, 2, 7); }
  for (const e of (state.mode === 'mission' ? run.events : RUNS.flatMap(r => r.events))) {
    if (e.type === 'sample_failed') continue;
    g.fillStyle = e.type === 'sample_taken' ? '#7cf29c' : '#ff5d5d'; g.beginPath(); g.arc(x(e.tick), h / 2 + 10, 3.2, 0, TAU); g.fill();
  }
  g.fillStyle = '#fff'; g.beginPath(); g.arc(x(state.t), h / 2, 7, 0, TAU); g.fill();
  g.strokeStyle = '#ff8a3d'; g.lineWidth = 2.5; g.stroke();
}
function setText(holder, key, value, node) { if (holder.shown[key] !== value) { holder.shown[key] = value; node.textContent = value; } }
function updatePills(screen, info, root = screen.el) {
  const battery = info.pose.battery, state_ = info.state;
  setText(screen, 'bat', battery.toFixed(0), $('.bat-v', root));
  const meter = $('.meter i', root); meter.style.width = `${clamp(100 * battery / screen.run.cfg.initial_battery, 0, 100)}%`; meter.style.background = battery < 15 ? 'var(--bad)' : battery < 35 ? 'var(--cmd)' : 'var(--ok)';
  const got = state_.sampled_targets.join(',');
  if (screen.shown.got !== got) { screen.shown.got = got; for (const chip of root.querySelectorAll('.samples i')) chip.classList.toggle('got', state_.sampled_targets.includes(chip.dataset.id)); }
}
const EVENT_TEXT = { sample_taken: ['good', e => `SAMPLE TAKEN · ${e.target_id.toUpperCase()}`], sample_failed: ['bad', () => 'SAMPLE FAILED · nothing in range'],
  safety_stop: ['bad', e => `SAFETY STOP · ${e.reason === 'map_boundary' ? 'edge of the operating zone' : 'hazard'} · queue cleared`], battery_depleted: ['bad', () => 'BATTERY EMPTY · rover lost'] };
function updateScreen(screen, info, t) {
  const run = screen.run, el = screen.el, tv = info.tv;
  updatePills(screen, info);
  const tag = screen.kind === 'feed' ? `showing tick <b>${String(Math.floor(tv)).padStart(2, '0')}</b><br>it is now tick ${Math.floor(t)}`
    : screen.kind === 'wide' ? `reward <b>${run.reward.toFixed(2)}</b>` : `tick <b>${String(Math.floor(t)).padStart(2, '0')}</b>`;
  if (screen.shown.tag !== tag) { screen.shown.tag = tag; $('.tag', el).innerHTML = tag; }
  const extra = screen.kind === 'feed' ? `unconfirmed commands<b>${info.pending}</b>` : `view is behind by<b>${info.apart.toFixed(1)} m</b> · in transit<b>${info.pending}</b>`;
  if (screen.shown.extra !== extra) { screen.shown.extra = extra; $('.extra', el).innerHTML = extra; }
  let toast = null;
  for (const event of run.events) { const age = tv - event.tick; if (age >= 0 && age < 2.4 && EVENT_TEXT[event.type]) toast = event; }
  const node = $('.toast', el), key = toast ? toast.tick + toast.type : '';
  if (screen.shown.toast !== key) { screen.shown.toast = key; node.className = 'toast' + (toast ? ` show ${EVENT_TEXT[toast.type][0]}` : ''); if (toast) node.textContent = EVENT_TEXT[toast.type][1](toast); }
  const finished = t >= run.T - 0.01 && screen.kind !== 'map';
  if (screen.shown.done !== finished) {
    screen.shown.done = finished; const result = $('.result', el); result.classList.toggle('show', finished);
    $('b', result).textContent = run.reward.toFixed(2); $('b', result).style.color = run.reward >= 0.99 ? 'var(--ok)' : run.reward > 0 ? 'var(--cmd)' : 'var(--bad)';
    $('span', result).textContent = `${run.result.sampled_targets.length} of ${run.world.targets.length} targets · ${run.result.alive ? (run.result.at_base ? 'back at base' : 'alive, away from base') : 'battery dead'}`;
  }
}
function updateConsole(panel, t, info) {
  const run = panel.run, el = panel.el;
  updatePills(panel, info, $('.foot', el));
  const extra = `tick<b>${Math.floor(t)}</b> · in transit<b>${info.pending}</b>`;
  if (panel.shown.extra !== extra) { panel.shown.extra = extra; $('.extra', el).innerHTML = extra; }
  const made = run.calls.filter(c => c.at <= t), latest = made[made.length - 1];
  const counts = {}; for (const c of made) { const name = c.kind === 'shell' ? 'shell' : c.tool; counts[name] = (counts[name] || 0) + 1; }
  for (const node of el.querySelectorAll('.tool')) {
    const name = node.dataset.tool, hit = latest && (latest.kind === 'shell' ? 'shell' : latest.tool) === name && (t - latest.at < 0.55 || (latest.tool === 'advance' && t < latest.tick_after));
    node.classList.toggle('hit', !!hit && latest.ok); node.classList.toggle('fail', !!hit && !latest.ok);
    setText(panel, 'n' + name, String(counts[name] || 0), $('em', node));
  }
  if (panel.shown.calls !== made.length) {
    panel.shown.calls = made.length;
    const nowNode = $('.now', el);
    if (latest) { const [name, text] = describeCall(latest); nowNode.className = 'now show' + (latest.ok ? '' : ' err') + (latest.kind === 'shell' ? ' sh' : ''); nowNode.innerHTML = `<b>${name}</b>${text.replace(/</g, '&lt;')}`; }
    else { nowNode.className = 'now'; nowNode.textContent = ''; }
    const esc = text => text.replace(/</g, '&lt;');
    const lines = [];
    for (const c of made.slice(-16, -1)) {
      if (c.say) lines.push(`<div class="said"><b>${run.label}:</b> “${esc(c.say)}”</div>`);
      const [name, text] = describeCall(c);
      lines.push(`<div class="${c.ok ? '' : 'err'}"><u>t${String(c.tick).padStart(2, '0')}</u><b>${name}</b> ${esc(text)}</div>`);
    }
    if (latest && latest.say) lines.push(`<div class="said"><b>${run.label}:</b> “${esc(latest.say)}”</div>`);
    panel.lines = lines;
  }
  const reported = t >= run.T - 0.01 && !!run.report;
  if (panel.shown.log !== made.length + (reported ? 'r' : '')) {
    panel.shown.log = made.length + (reported ? 'r' : '');
    const report = reported ? `<div class="said final"><b>${run.label}, final report:</b> “${run.report.split('\n')[0].replace(/</g, '&lt;')}”</div>` : '';
    $('.log', el).innerHTML = (panel.lines || []).join('') + report;
  }
  const finished = t >= run.T - 0.01;
  setText(panel, 'score', finished ? run.reward.toFixed(2) : '—', $('.score b', el));
  $('.score b', el).style.color = finished ? (run.reward >= 0.99 ? 'var(--ok)' : run.reward > 0 ? 'var(--cmd)' : 'var(--bad)') : '';
  // the signal lane: commands travelling out, telemetry travelling back
  const canvas = panel.canvas, rect = canvas.getBoundingClientRect(), dpr = window.devicePixelRatio || 1;
  if (canvas.width !== Math.round(rect.width * dpr)) { canvas.width = Math.round(rect.width * dpr); canvas.height = Math.round(rect.height * dpr); }
  const g = canvas.getContext('2d'); g.setTransform(dpr, 0, 0, dpr, 0, 0); g.clearRect(0, 0, rect.width, rect.height);
  const w = rect.width, x0 = 62, x1 = w - 62, yUp = 19, yDown = 41;
  g.font = '600 11px -apple-system, sans-serif'; g.textBaseline = 'middle';
  g.fillStyle = '#5ce1ff'; g.fillText('EARTH', 12, 30); g.fillStyle = '#ff8a3d'; g.fillText('MARS', w - 48, 30);
  g.strokeStyle = 'rgba(255,209,102,.3)'; g.lineWidth = 1; g.beginPath(); g.moveTo(x0, yUp); g.lineTo(x1, yUp); g.stroke();
  g.strokeStyle = 'rgba(92,225,255,.3)'; g.beginPath(); g.moveTo(x0, yDown); g.lineTo(x1, yDown); g.stroke();
  g.fillStyle = 'rgba(255,209,102,.75)'; g.fillText('commands ▶', x0 + 4, yUp - 10); g.fillStyle = 'rgba(92,225,255,.75)'; g.fillText('◀ telemetry', x1 - 70, yDown + 11);
  for (const c of run.commands) { const f = (t - c.sent) / (c.exec - c.sent); if (f < 0 || f > 1 || t >= c.until) continue; g.fillStyle = '#ffd166'; g.beginPath(); g.arc(lerp(x0, x1, f), yUp, c.action === 'sample' ? 5.5 : 4.5, 0, TAU); g.fill(); }
  for (let s = Math.max(1, Math.floor(t - run.K)); s <= Math.floor(t); s++) { const f = (t - s) / Math.max(run.K, 0.001); if (f < 0 || f > 1) continue; g.fillStyle = '#5ce1ff'; g.fillRect(lerp(x1, x0, f) - 3, yDown - 3, 6, 6); }
}

// ---------------------------------------------------------------- loop and input
function setPlaying(on) { state.playing = on; playButton.textContent = on ? '❚❚' : '▶'; if (on) $('#intro').classList.add('gone'); }
function seek(t) { state.t = clamp(t, 0, T); }
playButton.onclick = () => { if (!state.playing && state.t >= T - 0.01) seek(0); setPlaying(!state.playing); };
$('#start').onclick = () => { seek(0); setPlaying(true); };
scrub.oninput = () => { setPlaying(false); $('#intro').classList.add('gone'); seek(+scrub.value); };
$('#speed').onchange = e => { state.speed = +e.target.value; };
$('#runpick').onchange = e => { state.run = RUNS.find(r => r.id === e.target.value); build(); };
for (const button of document.querySelectorAll('#mode button')) button.onclick = () => { state.mode = button.dataset.mode; build(); };
$('#full').onclick = () => (document.fullscreenElement ? document.exitFullscreen() : document.documentElement.requestFullscreen());
addEventListener('keydown', e => {
  if (e.target.tagName === 'SELECT') return;
  if (e.key === ' ') { e.preventDefault(); playButton.click(); }
  if (e.key === 'ArrowRight') { setPlaying(false); seek(Math.floor(state.t + 1e-6) + 1); }
  if (e.key === 'ArrowLeft') { setPlaying(false); seek(Math.ceil(state.t - 1e-6) - 1); }
  if (e.key === 'm' || e.key === 'M') { state.mode = state.mode === 'mission' ? 'compare' : 'mission'; build(); }
  if (e.key === 'f' || e.key === 'F') $('#full').click();
  if (/^[1-4]$/.test(e.key) && RUNS[e.key - 1]) { state.run = RUNS[e.key - 1]; $('#runpick').value = state.run.id; state.mode = 'mission'; build(); }
});
addEventListener('resize', () => { fitUi(); drawMarks(); });
fitUi();
window.LIGHTLAG = { state, seek, setPlaying, build, RUNS };   // for checks from the browser console

let last = performance.now();
function frame(now) {
  const dt = Math.min(0.1, (now - last) / 1000); last = now; state.wall += dt;
  if (state.playing) { state.t += dt * state.speed; if (state.t >= T) { state.t = T; setPlaying(false); if (state.loop) setTimeout(() => { seek(0); setPlaying(true); }, 6000); } }
  const t = state.t, width = window.innerWidth, height = window.innerHeight;
  if (renderer.domElement.width !== Math.round(width * renderer.getPixelRatio()) || renderer.domElement.height !== Math.round(height * renderer.getPixelRatio())) renderer.setSize(width, height, false);
  renderer.setScissorTest(false); renderer.setViewport(0, 0, width, height); renderer.clear();
  renderer.setScissorTest(true);
  let liveInfo = null;
  for (const screen of state.screens) {
    if (screen.kind === 'console') continue;
    const rect = screen.el.getBoundingClientRect();
    if (rect.width < 4 || rect.height < 4) continue;
    const info = screen.scene.apply(screen.kind, t, state.wall);
    screen.frame(info, rect.width / rect.height, dt, state.wall);
    screen.scene.fitLabels(screen.camera, rect.height);
    renderer.setViewport(rect.left, height - rect.bottom, rect.width, rect.height);
    renderer.setScissor(rect.left, height - rect.bottom, rect.width, rect.height);
    renderer.render(screen.scene.scene, screen.camera);
    updateScreen(screen, info, t);
    if (screen.kind === 'live') liveInfo = info;
  }
  for (const screen of state.screens) if (screen.kind === 'console' && liveInfo) updateConsole(screen, t, liveInfo);
  const shownTick = String(Math.floor(t)).padStart(3, '0');
  if (clock.textContent !== shownTick) clock.textContent = shownTick;
  scrub.value = t; drawMarks();
  requestAnimationFrame(frame);
}
build();
if (location.hash === '#auto') { state.loop = true; setTimeout(() => setPlaying(true), 1800); }
requestAnimationFrame(frame);
