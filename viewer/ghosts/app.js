// Lightlag Live · ghost replay. One file, no build step; three.js is the only dependency.
// Every rover shown drove a recorded campaign: window.LIGHTLAG_GHOSTS (see viewer/build_ghosts.py).
// The terrain, rover and lander are the Mars demo's (viewer/mars/app.js), so both pages share one look.
import * as THREE from 'three';

if (document.readyState === 'loading') await new Promise(resolve => document.addEventListener('DOMContentLoaded', resolve, { once: true }));

const DATA = window.LIGHTLAG_GHOSTS;
const $ = (selector, root = document) => root.querySelector(selector);
const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
const lerp = (a, b, t) => a + (b - a) * t;
const smooth = (a, b, x) => { const t = clamp((x - a) / (b - a), 0, 1); return t * t * (3 - 2 * t); };
const TAU = Math.PI * 2, rad = THREE.MathUtils.degToRad;
const fmt = n => String(+(+n).toFixed(2));
const two = n => (+n).toFixed(2);
const esc = text => String(text).replace(/&/g, '&amp;').replace(/</g, '&lt;');
// Gold is the reference, ice is the Claude run being followed, shade is every other Claude run.
const INK = 0xf3ead9, GOLD = 0xffb224, ICE = 0x9fd8ff, RED = 0xff4a2f, LIME = 0xb6e35a, MUTE = 0x8a7466, LINE = 0x1b1310, SHADE = 0x1a100c;
const css = n => '#' + n.toString(16).padStart(6, '0');
const FONT = '"DIN Condensed", "Avenir Next Condensed", "Roboto Condensed", "Arial Narrow", sans-serif';

// ---------------------------------------------------------------- noise and terrain
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
function terrainHeight(x, z) {
  const d = Math.max(Math.abs(x), Math.abs(z)), out = smooth(22, 52, d);
  const micro = (fbm(x * 0.4 + 11, z * 0.4 + 3, 3) - 0.5) * 0.03;
  const dunes = (fbm(x * 0.04 + 40, z * 0.04 + 7, 4) - 0.42) * 11 * out;
  const mesas = smooth(75, 120, Math.hypot(x, z)) * (4 + 22 * Math.pow(fbm(x * 0.017 + 3, z * 0.017 + 9, 3), 1.6));
  return micro + dunes + mesas;
}
function canvasTexture(size, draw) {
  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = size;
  draw(canvas.getContext('2d'), size);
  const texture = new THREE.CanvasTexture(canvas);
  texture.wrapS = texture.wrapT = THREE.RepeatWrapping;
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.anisotropy = 8;
  return texture;
}
const SAND = canvasTexture(256, (g, s) => {
  g.fillStyle = '#dba25b'; g.fillRect(0, 0, s, s);
  for (const [color, width, shift] of [['#c88d49', 8, 0], ['#ecbd78', 3, 10]]) {
    g.strokeStyle = color; g.lineWidth = width;
    for (let k = -1; k < 9; k++) {
      g.beginPath();
      for (let x = 0; x <= s; x += 8) g.lineTo(x, k * 32 + 16 + shift + Math.sin(x / s * TAU * 2 + k * 0.9) * 5);
      g.stroke();
    }
  }
});

// A line of text that faces the camera, with an optional timer bar under it.
class Label {
  constructor(px = 54) {
    this.canvas = document.createElement('canvas'); this.canvas.width = 512; this.canvas.height = 128;
    this.texture = new THREE.CanvasTexture(this.canvas); this.texture.colorSpace = THREE.SRGBColorSpace;
    this.sprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: this.texture, transparent: true, depthTest: false, fog: false }));
    this.sprite.center.set(0.5, 0); this.sprite.renderOrder = 10;
    this.sprite.userData = { px, aspect: 4 };
    this.key = null;
  }
  set(text, color = css(INK), bar = null, barColor = css(GOLD)) {
    const key = `${text}|${color}|${bar === null ? '' : Math.round(bar * 50)}|${barColor}`;
    if (key === this.key) return this;
    this.key = key;
    const g = this.canvas.getContext('2d');
    g.clearRect(0, 0, 512, 128);
    g.font = `700 62px ${FONT}`; g.textAlign = 'center'; g.textBaseline = 'alphabetic'; g.lineJoin = 'round';
    const y = bar === null ? 112 : 82;
    g.lineWidth = 13; g.strokeStyle = css(LINE); g.strokeText(text, 256, y);
    g.fillStyle = color; g.fillText(text, 256, y);
    if (bar !== null) {
      const w = 190, x = 256 - w / 2;
      g.fillStyle = css(LINE); g.fillRect(x - 5, 93, w + 10, 26);
      g.fillStyle = 'rgba(243,234,217,.25)'; g.fillRect(x, 98, w, 16);
      g.fillStyle = barColor; g.fillRect(x, 98, w * clamp(bar, 0, 1), 16);
    }
    this.texture.needsUpdate = true;
    return this;
  }
}

// ---------------------------------------------------------------- the recorded campaigns
const MISSIONS = DATA.missions, K = MISSIONS.length, T = MISSIONS[0].ticks, TOTAL = K * T;
// One rover in one mission: where it really was at every tick.
class Track {
  constructor(raw) {
    this.raw = raw;
    this.moved = [0]; for (let i = 1; i <= T; i++) this.moved.push(Math.hypot(raw.p[2 * i] - raw.p[2 * i - 2], raw.p[2 * i + 1] - raw.p[2 * i - 1]));
    const dead = raw.events.find(e => e.k === 'dead');
    this.deadTick = dead ? dead.t : null;
    this.samples = raw.samples.slice().sort((a, b) => a.t - b.t);
  }
  at(t) {
    t = clamp(t, 0, T);
    const i = Math.min(T - 1, Math.floor(t)), f = t - i, p = this.raw.p, h = this.raw.h;
    const moving = this.moved[i + 1] > 1e-6, drive = moving ? smooth(0.16, 1, f) : 0, turn = moving ? smooth(0, 0.2, f) : 0;
    const delta = ((h[i + 1] - h[i] + 540) % 360) - 180;
    return {
      x: lerp(p[2 * i], p[2 * i + 2], drive), y: lerp(p[2 * i + 1], p[2 * i + 3], drive),
      heading: h[i] + (moving ? delta * turn : 0), moving: moving && f > 0.16 && f < 0.985,
      battery: lerp(this.raw.b[i], this.raw.b[i + 1], f), alive: this.deadTick === null || t < this.deadTick,
    };
  }
  carried(t) { let sum = 0; for (const s of this.samples) if (s.t <= t + 1e-6) sum += s.v; return sum; }
}
const RUNS = DATA.runs.map((raw, index) => ({ ...raw, index, tracks: raw.missions.map(m => new Track(m)), ref: raw.kind === 'reference' }));
const REF = RUNS.find(r => r.ref), CLAUDE = RUNS.filter(r => !r.ref);
const state = { g: 0, playing: false, speed: 2, follow: CLAUDE.find(r => r.id === DATA.best) || CLAUDE[0] || null };
const SPEEDS = [[1, '1×'], [2, '2×'], [4, '4×'], [8, '8×'], [16, '16×']];
// The score a run shows at campaign time g: finished missions as graded, the one in progress as value carried so far.
function standing(run, g) {
  const mission = Math.min(K - 1, Math.floor(g / T)), done = g >= TOTAL ? K : mission;
  let sum = 0; for (let k = 0; k < done; k++) sum += run.missions[k].reward;
  const now = done < K ? run.tracks[mission].carried(g - mission * T) / run.missions[mission].max : 0;
  // `live` counts the mission under way at what the rover is carrying; it settles to the graded score when the mission ends
  return { done, now, mean: done ? sum / done : 0, live: done < K ? (sum + now) / (done + 1) : sum / K };
}

// ---------------------------------------------------------------- shared scene pieces
const flat = (color, extra = {}) => new THREE.MeshStandardMaterial({ color, roughness: 0.9, metalness: 0, flatShading: true, ...extra });
const MAT = {
  ground: flat(0xffffff, { vertexColors: true, roughness: 1 }),
  sand: new THREE.MeshStandardMaterial({ map: SAND, roughness: 1, metalness: 0, polygonOffset: true, polygonOffsetFactor: -2, polygonOffsetUnits: -2 }),
  rock: flat(0x7a3d27), basalt: flat(0x2c211d), pad: flat(0x3b2f2a),
  white: flat(0xefe6d6), dark: flat(0x2a2421), metal: flat(0x8c8782, { roughness: 0.7 }), solar: flat(0x24407e), tan: flat(0xc59a55),
  lamp: new THREE.MeshBasicMaterial({ color: 0xfff2c8 }),
  shell: new THREE.MeshBasicMaterial({ color: LINE, side: THREE.BackSide }),
  ghostDepth: new THREE.MeshBasicMaterial({ colorWrite: false }),
};
const BANDS = [0x8f4126, 0xa34b2b, 0xb35631, 0xc2633a].map(c => new THREE.Color(c)), HILL = new THREE.Color(0x6f3322);
function buildWorld(mission) {
  const cx = mission.width / 2, cy = mission.height / 2;
  const inSand = (x, y) => mission.sand.some(r => x >= r.x1 - 0.4 && x <= r.x2 + 0.4 && y >= r.y1 - 0.4 && y <= r.y2 + 0.4);
  const grid = new THREE.PlaneGeometry(420, 420, 120, 120);
  grid.rotateX(-Math.PI / 2);
  for (let i = 0, p = grid.attributes.position; i < p.count; i++) p.setY(i, terrainHeight(p.getX(i), p.getZ(i)));
  const ground = grid.toNonIndexed(), pos = ground.attributes.position, colors = new Float32Array(pos.count * 3), color = new THREE.Color();
  for (let i = 0; i < pos.count; i += 3) {
    const x = (pos.getX(i) + pos.getX(i + 1) + pos.getX(i + 2)) / 3, z = (pos.getZ(i) + pos.getZ(i + 1) + pos.getZ(i + 2)) / 3, h = (pos.getY(i) + pos.getY(i + 1) + pos.getY(i + 2)) / 3;
    const n = fbm(x * 0.045 + 5, z * 0.045 + 2, 3) + (hash2(i, 3.3) - 0.5) * 0.09;
    color.copy(BANDS[n < 0.4 ? 0 : n < 0.5 ? 1 : n < 0.6 ? 2 : 3]);
    if (h > 3) color.lerp(HILL, smooth(3, 16, h) * 0.6);
    for (let k = 0; k < 3; k++) { colors[(i + k) * 3] = color.r; colors[(i + k) * 3 + 1] = color.g; colors[(i + k) * 3 + 2] = color.b; }
  }
  ground.setAttribute('color', new THREE.BufferAttribute(colors, 3));
  ground.computeVertexNormals();
  const rocks = [];
  const rng = (() => { let s = 12345; return () => (s = (s * 16807) % 2147483647) / 2147483647; })();
  for (let i = 0; i < 520; i++) {
    const far = i > 130, radius = far ? 26 + rng() * 150 : rng() * 27, angle = rng() * TAU;
    const x = Math.cos(angle) * radius, z = Math.sin(angle) * radius, sx = x + cx, sy = cy - z;
    const inside = sx > -1 && sx < mission.width + 1 && sy > -1 && sy < mission.height + 1;
    const nearEdge = !inside && sx > -5 && sx < mission.width + 5 && sy > -5 && sy < mission.height + 5;
    const scale = inside ? 0.06 + rng() * 0.12 : 0.3 + Math.pow(rng(), 2.2) * 2.6;
    const sq = 0.55 + rng() * 0.5, rx = rng() * TAU, ry = rng() * TAU;
    if (nearEdge || (inside && (inSand(sx, sy) || Math.hypot(sx - mission.base[0], sy - mission.base[1]) < 3))) continue;
    rocks.push({ x, z, y: terrainHeight(x, z) + scale * 0.25, scale, rx, ry, sq });
  }
  return { cx, cy, ground, rocks };
}
const ROCK = (() => {
  const g = new THREE.IcosahedronGeometry(1, 0), p = g.attributes.position;
  for (let i = 0; i < p.count; i++) { const k = 0.74 + 0.5 * hash2(p.getX(i) * 3.1 + p.getY(i) * 1.7, p.getZ(i) * 2.3); p.setXYZ(i, p.getX(i) * k, p.getY(i) * k, p.getZ(i) * k); }
  g.computeVertexNormals();
  return g;
})();

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
function collect(root, width = 0) {
  root.updateMatrixWorld(true);
  const inverse = root.matrixWorld.clone().invert(), buckets = new Map(), shells = [], size = new THREE.Vector3();
  const add = (list, geometry, matrix) => { const g = geometry.index ? geometry.toNonIndexed() : geometry.clone(); g.applyMatrix4(matrix); list.push(g); };
  root.traverse(node => {
    if (!node.isMesh) return;
    const local = inverse.clone().multiply(node.matrixWorld);
    if (!buckets.has(node.material)) buckets.set(node.material, []);
    add(buckets.get(node.material), node.geometry, local);
    if (!width) return;
    node.geometry.computeBoundingBox(); node.geometry.boundingBox.getSize(size);
    const grow = new THREE.Matrix4().makeScale((size.x + 2 * width) / Math.max(size.x, 1e-3), (size.y + 2 * width) / Math.max(size.y, 1e-3), (size.z + 2 * width) / Math.max(size.z, 1e-3));
    add(shells, node.geometry, local.multiply(grow));
  });
  return { buckets, shells };
}
function join(list) {
  let count = 0; for (const g of list) count += g.attributes.position.count;
  const position = new Float32Array(count * 3), normal = new Float32Array(count * 3);
  let offset = 0;
  for (const g of list) { position.set(g.attributes.position.array, offset); normal.set(g.attributes.normal.array, offset); offset += g.attributes.position.count * 3; }
  const out = new THREE.BufferGeometry();
  out.setAttribute('position', new THREE.BufferAttribute(position, 3)); out.setAttribute('normal', new THREE.BufferAttribute(normal, 3));
  return out;
}
function bake(root, width = 0.028) {
  const { buckets, shells } = collect(root, width), out = new THREE.Group();
  for (const [material, list] of buckets) { const mesh = new THREE.Mesh(join(list), material); mesh.castShadow = mesh.receiveShadow = true; out.add(mesh); }
  if (shells.length) out.add(new THREE.Mesh(join(shells), MAT.shell));
  out.position.copy(root.position); out.rotation.copy(root.rotation); out.scale.copy(root.scale);
  return out;
}
// The Mars demo's six-wheeled rover facing +x. `paint` is its livery: gold for the reference, ice for a Claude run.
function roverParts(paint) {
  const accent = flat(paint), lens = new THREE.MeshBasicMaterial({ color: paint });
  const rover = new THREE.Group(), body = new THREE.Group(), fixed = new THREE.Group();
  fixed.add(box(1.36, 0.26, 0.88, MAT.white, 0, 0.78, 0));
  fixed.add(box(1.36, 0.07, 0.88, MAT.tan, 0, 0.615, 0));
  fixed.add(box(1.4, 0.035, 0.94, accent, 0, 0.93, 0));                    // the deck carries the livery
  const power = new THREE.Group();
  power.add(box(0.52, 0.2, 0.28, MAT.metal));
  for (const k of [-1, 0, 1]) power.add(box(0.48, 0.3, 0.02, MAT.dark, 0, 0, k * 0.11));
  power.position.set(-0.88, 0.95, 0); power.rotation.z = 0.5; fixed.add(power);
  fixed.add(cyl(0.04, 0.05, 0.98, MAT.metal, 0.46, 1.42, 0.3, 8));
  const dish = cyl(0.3, 0.05, 0.1, MAT.white, -0.34, 1.34, -0.26, 6); dish.rotation.set(0.5, 0, 0.35); fixed.add(dish);
  fixed.add(cyl(0.02, 0.02, 0.4, MAT.metal, -0.34, 1.13, -0.26, 6));
  fixed.add(cyl(0.015, 0.015, 0.5, MAT.metal, -0.6, 1.2, 0.34, 6));
  const hubs = [[0.76, 0.3], [0.04, 0.3], [-0.72, 0.3]], bogie = [0.4, 0.52], pivot = [-0.14, 0.66];
  const strut = (a, b, side) => { const dx = b[0] - a[0], dy = b[1] - a[1], beam = box(Math.hypot(dx, dy), 0.06, 0.06, MAT.metal, (a[0] + b[0]) / 2, (a[1] + b[1]) / 2, side * 0.52); beam.rotation.z = Math.atan2(dy, dx); fixed.add(beam); };
  for (const side of [-1, 1]) { strut(hubs[0], bogie, side); strut(bogie, hubs[1], side); strut(bogie, pivot, side); strut(pivot, hubs[2], side); }
  const spare = new THREE.Group();
  const tyre = cyl(0.3, 0.3, 0.22, MAT.dark, 0, 0, 0, 12); tyre.rotation.x = Math.PI / 2; spare.add(tyre);
  const cap = cyl(0.13, 0.13, 0.24, MAT.metal, 0, 0, 0, 8); cap.rotation.x = Math.PI / 2; spare.add(cap);
  for (const side of [-1, 1]) for (const [x, y] of hubs) { const wheel = spare.clone(); wheel.position.set(x, y, side * 0.62); fixed.add(wheel); }
  const skull = new THREE.Group();
  skull.add(box(0.32, 0.18, 0.44, MAT.white)); skull.add(box(0.06, 0.2, 0.46, accent, -0.14, 0, 0));
  skull.position.set(0.46, 1.98, 0.3); fixed.add(skull);
  body.add(bake(fixed));
  const eyes = [-0.11, 0.11].map(z => { const eye = cyl(0.055, 0.055, 0.05, lens, 0.63, 1.98, 0.3 + z, 10); eye.rotation.z = Math.PI / 2; eye.castShadow = false; body.add(eye); return eye; });
  const lamps = [-0.3, 0.3].map(z => { const lamp = new THREE.Mesh(new THREE.SphereGeometry(0.045, 8, 6), MAT.lamp); lamp.position.set(0.69, 0.8, z); body.add(lamp); return lamp; });
  rover.add(body);
  rover.userData = { body, lights: [...lamps, ...eyes] };
  return rover;
}
// The same shape as one flat silhouette: a shadow. Drawn in two passes, depth first, so it never reads as a stack of parts.
const SILHOUETTE = (() => { const { buckets } = collect(roverParts(INK)), all = []; for (const [material, list] of buckets) if (material !== MAT.shell) all.push(...list); return join(all); })();
function makeShadow() {
  const group = new THREE.Group(), fill = new THREE.MeshBasicMaterial({ color: SHADE, transparent: true, opacity: 0.5, depthWrite: false, depthFunc: THREE.LessEqualDepth, fog: false });
  const depth = new THREE.Mesh(SILHOUETTE, MAT.ghostDepth), body = new THREE.Mesh(SILHOUETTE, fill);
  depth.renderOrder = 1; body.renderOrder = 3; group.add(depth, body);
  group.userData = { fill };
  return group;
}
function makeLander() {
  const lander = new THREE.Group();
  lander.add(cyl(1.15, 1.4, 0.9, MAT.tan, 0, 1.25, 0, 6));
  lander.add(cyl(0.9, 1.15, 0.35, MAT.white, 0, 1.87, 0, 6));
  for (let k = 0; k < 3; k++) {
    const a = k * TAU / 3 + 0.4, leg = cyl(0.05, 0.05, 1.9, MAT.metal, Math.cos(a) * 1.5, 0.75, Math.sin(a) * 1.5, 6);
    leg.rotation.z = Math.cos(a) * 0.55; leg.rotation.x = -Math.sin(a) * 0.55; lander.add(leg);
    lander.add(cyl(0.3, 0.34, 0.07, MAT.metal, Math.cos(a) * 2.0, 0.04, Math.sin(a) * 2.0, 8));
  }
  for (const side of [-1, 1]) { const wing = box(2.6, 0.05, 1.2, MAT.solar, side * 2.5, 1.55, 0); wing.rotation.z = side * -0.12; lander.add(wing); }
  lander.add(cyl(0.03, 0.03, 1.5, MAT.metal, 0.2, 2.75, 0.1, 6));
  const dish = cyl(0.62, 0.08, 0.2, MAT.white, 0.2, 3.5, 0.1, 8); dish.rotation.set(0.75, 0.4, 0.2); lander.add(dish);
  return bake(lander, 0.035);
}
const SKY = new THREE.Mesh(new THREE.SphereGeometry(900, 24, 12), new THREE.ShaderMaterial({
  side: THREE.BackSide, depthWrite: false, fog: false,
  uniforms: { sun: { value: new THREE.Vector3(-0.55, 0.42, -0.72).normalize() } },
  vertexShader: 'varying vec3 d; void main(){ d = normalize(position); gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }',
  fragmentShader: `varying vec3 d; uniform vec3 sun;
    void main(){ vec3 n = normalize(d); float h = max(n.y, 0.0);
      vec3 col = mix(vec3(0.925, 0.735, 0.545), vec3(0.60, 0.40, 0.345), pow(h, 0.55));
      float s = max(dot(n, sun), 0.0);
      col = mix(col, vec3(0.86, 0.93, 1.0), smoothstep(0.99962, 0.99972, s));
      col += vec3(0.70, 0.80, 0.95) * pow(s, 60.0) * 0.16;
      if (n.y < 0.0) col = vec3(0.925, 0.735, 0.545);
      gl_FragColor = vec4(col, 1.0); }`,
}));
const FOG_COLOR = new THREE.Color().setRGB(0.925, 0.735, 0.545, THREE.SRGBColorSpace);
const flatMark = (color, opacity = 1) => new THREE.MeshBasicMaterial({ color, transparent: true, opacity, side: THREE.DoubleSide, depthWrite: false, fog: false });

// ---------------------------------------------------------------- one mission: the ground and every rover that drove it
class MissionScene {
  constructor(index) {
    const mission = this.mission = MISSIONS[index]; this.index = index;
    const shared = this.shared = buildWorld(mission), scene = this.scene = new THREE.Scene();
    scene.fog = new THREE.FogExp2(FOG_COLOR, 0.0048); scene.background = FOG_COLOR;
    scene.add(SKY.clone());
    scene.add(new THREE.HemisphereLight(0xffe1c2, 0x7a3d27, 1.2));
    const sun = new THREE.DirectionalLight(0xfff1dd, 2.7);
    sun.position.set(-55, 42, -72).multiplyScalar(0.9);
    sun.castShadow = true; sun.shadow.mapSize.set(2048, 2048); sun.shadow.bias = -0.0006; sun.shadow.normalBias = 0.03;
    Object.assign(sun.shadow.camera, { left: -30, right: 30, top: 30, bottom: -30, near: 10, far: 220 });
    scene.add(sun, sun.target);
    const ground = new THREE.Mesh(shared.ground, MAT.ground); ground.receiveShadow = true; scene.add(ground);
    mission.sand.forEach((r, i) => {
      const w = r.x2 - r.x1, h = r.y2 - r.y1, g = new THREE.PlaneGeometry(w, h);
      g.rotateX(-Math.PI / 2);
      for (let k = 0, p = g.attributes.position, uv = g.attributes.uv; k < p.count; k++) uv.setXY(k, (r.x1 + p.getX(k) + w / 2) / 5, (r.y2 - (p.getZ(k) + h / 2)) / 5);
      const mesh = new THREE.Mesh(g, MAT.sand); mesh.position.copy(this.P(r.x1 + w / 2, r.y1 + h / 2, 0.018 + i * 0.004)); mesh.receiveShadow = true; scene.add(mesh);
    });
    const rocks = new THREE.InstancedMesh(ROCK, MAT.rock, shared.rocks.length), m = new THREE.Matrix4(), q = new THREE.Quaternion(), e = new THREE.Euler();
    shared.rocks.forEach((r, i) => { e.set(r.rx, r.ry, 0); q.setFromEuler(e); m.compose(new THREE.Vector3(r.x, r.y, r.z), q, new THREE.Vector3(r.scale, r.scale * r.sq, r.scale)); rocks.setMatrixAt(i, m); });
    rocks.castShadow = rocks.receiveShadow = true; scene.add(rocks);
    this.buildHazards(); this.buildBase(); this.buildTargets(); this.buildRovers(); this.frame();
  }
  P(x, y, h = 0) { return new THREE.Vector3(x - this.shared.cx, h, -(y - this.shared.cy)); }
  buildHazards() {
    let seed = 7 + this.index; const rng = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
    for (const r of this.mission.hazards) {
      const w = r.x2 - r.x1, h = r.y2 - r.y1, count = Math.round(w * h * 2.2) + 6;
      const boulders = new THREE.InstancedMesh(ROCK, MAT.basalt, count), m = new THREE.Matrix4(), q = new THREE.Quaternion(), e = new THREE.Euler();
      for (let i = 0; i < count; i++) {
        const s = 0.22 + rng() * 0.5; e.set(rng() * TAU, rng() * TAU, 0); q.setFromEuler(e);
        m.compose(this.P(r.x1 + rng() * w, r.y1 + rng() * h, s * 0.45), q, new THREE.Vector3(s, s * (0.7 + rng() * 0.7), s)); boulders.setMatrixAt(i, m);
      }
      boulders.castShadow = boulders.receiveShadow = true; this.scene.add(boulders);
      const pts = [[r.x1, r.y1], [r.x2, r.y1], [r.x2, r.y2], [r.x1, r.y2], [r.x1, r.y1]].map(([x, y]) => this.P(x, y, 0.09));
      this.scene.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), new THREE.LineBasicMaterial({ color: RED, transparent: true, opacity: 0.8, fog: false })));
    }
  }
  buildBase() {
    const [bx, by] = this.mission.base, r = this.mission.base_radius;
    const pad = cyl(1.7, 1.7, 0.05, MAT.pad, 0, 0, 0, 10); pad.position.copy(this.P(bx, by, 0.02)); pad.castShadow = false; this.scene.add(pad);
    const ring = new THREE.Mesh(new THREE.RingGeometry(r - 0.1, r, 40), flatMark(INK)); ring.rotation.x = -Math.PI / 2; ring.position.copy(this.P(bx, by, 0.065)); this.scene.add(ring);
    const lander = makeLander(); lander.position.copy(this.P(bx + 8.5, by + 11.5, 0)); lander.rotation.y = 2.4; this.scene.add(lander);
    const label = new Label(40).set('BASE'); label.sprite.position.copy(this.P(bx, by, 0.4)); this.scene.add(label.sprite);
  }
  // Each target is a survey flag with a ring on the ground, a timer over it, and one pip per rover that sampled it.
  buildTargets() {
    const r = this.mission.target_radius, pennant = new THREE.BufferGeometry();
    pennant.setAttribute('position', new THREE.BufferAttribute(new Float32Array([0, 0, 0, 0, -0.56, 0, 0.95, -0.28, 0]), 3));
    this.targets = this.mission.targets.map(t => {
      const group = new THREE.Group(); group.position.copy(this.P(t.x, t.y, 0));
      const material = flatMark(INK);
      const ring = new THREE.Mesh(new THREE.RingGeometry(r - 0.1, r, 40), material); ring.rotation.x = -Math.PI / 2; ring.position.y = 0.07; group.add(ring);
      const pole = cyl(0.03, 0.03, 2.3, MAT.dark, 0, 1.15, 0, 6); group.add(pole);
      const flag = new THREE.Mesh(pennant, material); flag.position.y = 2.3; group.add(flag);
      const pips = RUNS.map((run, i) => {
        const a = -Math.PI / 2 + (i - (RUNS.length - 1) / 2) * 0.42, pip = new THREE.Mesh(new THREE.CircleGeometry(0.17, 14), flatMark(SHADE));
        pip.rotation.x = -Math.PI / 2; pip.position.set(Math.cos(a) * (r + 0.42), 0.09, -Math.sin(a) * (r + 0.42)); pip.renderOrder = 4; group.add(pip);
        return pip;
      });
      const label = new Label(46);
      this.scene.add(group, label.sprite);
      return { ...t, group, flag, material, pips, label };
    });
  }
  buildRovers() {
    this.actors = RUNS.map(run => {
      const track = run.tracks[this.index], actor = { run, track };
      actor.shadow = makeShadow(); this.scene.add(actor.shadow);
      actor.rover = null;                                  // the full rover is built the first time this run is shown in colour
      const positions = new Float32Array(T * 18), geometry = new THREE.BufferGeometry();
      geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
      actor.trail = new THREE.Mesh(geometry, new THREE.MeshBasicMaterial({ color: SHADE, transparent: true, opacity: 0.4, depthWrite: false, side: THREE.DoubleSide, fog: false, polygonOffset: true, polygonOffsetFactor: -4, polygonOffsetUnits: -4 }));
      actor.trail.frustumCulled = false; actor.trail.renderOrder = 2; this.scene.add(actor.trail);
      actor.name = new Label(40); this.scene.add(actor.name.sprite);
      actor.toast = new Label(50); this.scene.add(actor.toast.sprite);
      actor.fix = new THREE.Mesh(new THREE.RingGeometry(0.5, 0.6, 28), flatMark(ICE, 0.9)); actor.fix.rotation.x = -Math.PI / 2; this.scene.add(actor.fix);
      actor.tether = new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(), new THREE.Vector3()]), new THREE.LineBasicMaterial({ color: ICE, transparent: true, opacity: 0.7, fog: false })); this.scene.add(actor.tether);
      return actor;
    });
  }
  // Frame everything any rover touched in this mission, so the camera never has to chase.
  frame() {
    const m = this.mission, xs = [m.base[0], ...m.targets.map(t => t.x)], ys = [m.base[1], ...m.targets.map(t => t.y)];
    for (const run of RUNS) { const p = run.missions[this.index].p; for (let i = 0; i < p.length; i += 2) { xs.push(p[i]); ys.push(p[i + 1]); } }
    const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys);
    this.center = this.P((x0 + x1) / 2, (y0 + y1) / 2, 0);
    this.radius = Math.max(7, Math.hypot(x1 - x0, y1 - y0) / 2 + 2.5);
  }
  // Draw the mission at local time t (in ticks). `follow` is the Claude run shown in colour.
  apply(t, wall, follow) {
    const whole = Math.floor(t + 1e-6);
    for (const actor of this.actors) {
      const { run, track } = actor, pose = track.at(t), p = this.P(pose.x, pose.y, 0);
      const role = run.ref ? 'ref' : run === follow ? 'on' : 'shade', paint = role === 'ref' ? GOLD : ICE;
      const full = role !== 'shade';
      if (full && (!actor.rover || actor.paint !== paint)) {
        if (actor.rover) this.scene.remove(actor.rover);
        actor.rover = roverParts(paint); actor.paint = paint; this.scene.add(actor.rover);
      }
      if (actor.rover) actor.rover.visible = full;
      actor.shadow.visible = !full;
      const body = full ? actor.rover : actor.shadow;
      body.position.copy(p); body.rotation.y = rad(pose.heading); body.scale.setScalar(1.3);
      if (full) {
        const parts = actor.rover.userData;
        parts.body.position.y = pose.moving ? Math.sin(wall * 19 + run.index) * 0.012 : 0;
        parts.body.rotation.z = pose.alive ? 0 : 0.16;                       // a dead rover slumps
        for (const light of parts.lights) light.visible = pose.alive;
      } else {
        actor.shadow.userData.fill.color.setHex(pose.alive ? SHADE : RED);
        actor.shadow.userData.fill.opacity = pose.alive ? 0.46 : 0.62;
      }
      // the path driven so far, as a ribbon on the ground
      const tp = actor.trail.geometry.attributes.position.array, raw = track.raw.p, width = role === 'shade' ? 0.06 : 0.12;
      let v = 0; const upto = Math.min(T, Math.ceil(t - 1e-9));
      for (let i = 0; i < upto; i++) {
        if (track.moved[i + 1] < 1e-6) continue;
        const A = this.P(raw[2 * i], raw[2 * i + 1]), B = i + 1 > t - 1e-9 ? p : this.P(raw[2 * i + 2], raw[2 * i + 3]);
        const dx = B.x - A.x, dz = B.z - A.z, len = Math.hypot(dx, dz) || 1, nx = -dz / len * width, nz = dx / len * width, y = role === 'shade' ? 0.045 : 0.06;
        for (const [base, w] of [[A, -1], [B, -1], [B, 1], [A, -1], [B, 1], [A, 1]]) { tp[v++] = base.x + nx * w; tp[v++] = y; tp[v++] = base.z + nz * w; }
      }
      actor.trail.geometry.setDrawRange(0, v / 3); actor.trail.geometry.attributes.position.needsUpdate = true;
      actor.trail.material.color.setHex(role === 'ref' ? GOLD : role === 'on' ? ICE : SHADE);
      actor.trail.material.opacity = role === 'shade' ? 0.42 : 0.95;
      actor.trail.renderOrder = role === 'shade' ? 2 : 3;
      // name over the two rovers in colour; a lost shadow keeps a red mark so the spot stays readable
      const name = role === 'ref' ? 'REFERENCE' : run.label.toUpperCase();
      actor.name.sprite.visible = full || !pose.alive;
      if (full) actor.name.set(pose.alive ? name : name + ' LOST', css(pose.alive ? paint : RED));
      else if (!pose.alive) actor.name.set('LOST', css(RED));
      actor.name.sprite.position.set(p.x, full ? 3.5 : 2.5, p.z);
      actor.name.sprite.userData.px = full ? 40 : 28;
      // one-shot notes for the rovers in colour, as pure functions of time so scrubbing works
      let note = null;
      if (full) {
        for (const s of track.samples) { const age = t - s.t; if (age >= 0 && age < 1.5) note = { age, text: `+${fmt(s.v)}${s.ok ? '' : ' LATE'}`, color: s.ok ? LIME : GOLD }; }
        for (const e of track.raw.events) { const age = t - e.t; if (age >= 0 && age < 1.5 && e.k !== 'dead') note = { age, text: e.k === 'miss' ? 'MISS' : 'STOPPED', color: RED }; }
      }
      actor.toast.sprite.visible = !!note;
      if (note) { actor.toast.set(note.text, css(note.color)); actor.toast.sprite.position.set(p.x, 4.7 + note.age * 1.1, p.z); actor.toast.sprite.material.opacity = clamp(1.6 - note.age, 0, 1); }
      // what this rover's program was last told: a position fix that is `delay` ticks old and noisy
      const seenTick = whole - this.mission.delay, showFix = role === 'on' && pose.alive && seenTick >= 1;
      actor.fix.visible = actor.tether.visible = showFix;
      if (showFix) {
        const s = track.raw.seen, f = this.P(s[2 * seenTick], s[2 * seenTick + 1], 0.1);
        actor.fix.position.copy(f);
        const line = actor.tether.geometry.attributes.position; line.setXYZ(0, p.x, 0.5, p.z); line.setXYZ(1, f.x, 0.12, f.z); line.needsUpdate = true;
      }
    }
    for (const target of this.targets) {
      const known = t >= target.appear - 1e-6;
      target.group.visible = target.label.sprite.visible = known;
      if (!known) continue;
      const left = target.deadline === null ? null : target.deadline - whole, late = left !== null && left < 0;
      const hue = late ? MUTE : left !== null && left <= 3 ? RED : INK, id = target.id.toUpperCase();
      target.material.color.setHex(hue);
      const fresh = target.appear > 0 ? clamp((t - target.appear) / 0.5, 0, 1) : 1;
      target.group.scale.set(1, fresh, 1);
      target.flag.rotation.y = Math.sin(wall * 2.1 + target.x) * 0.3;
      if (late) target.label.set(`${id} ${fmt(target.value * this.mission.late)}PT`, css(MUTE));
      else target.label.set(`${id} ${target.value}PT`, css(hue), left === null ? null : (target.deadline + 1 - t) / Math.max(1, target.deadline + 1 - target.appear), css(hue));
      target.label.sprite.position.copy(this.P(target.x, target.y, 2.6));
      this.actors.forEach((actor, i) => {
        const got = actor.track.samples.find(s => s.id === target.id && s.t <= t + 1e-6), pip = target.pips[i];
        pip.visible = !!got;
        if (got) pip.material.color.setHex(actor.run.ref ? GOLD : actor.run === follow ? ICE : SHADE);
      });
    }
  }
  fitLabels(camera, viewHeight) {
    const v = new THREE.Vector3();
    this.scene.traverse(node => {
      if (!node.isSprite || !node.userData.px) return;
      const far = Math.max(0.5, camera.position.distanceTo(node.getWorldPosition(v)));
      const h = 2 * Math.tan(rad(camera.fov) / 2) * far / viewHeight * node.userData.px;
      node.scale.set(h * node.userData.aspect, h, 1);
    });
  }
}

// ---------------------------------------------------------------- renderer and camera
const renderer = new THREE.WebGLRenderer({ canvas: $('#gl'), antialias: true, powerPreference: 'high-performance' });
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFShadowMap;
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.setClearColor(0x0b0807, 1);
const camera = new THREE.PerspectiveCamera(36, 1, 0.3, 1600);
const scenes = new Map();
const sceneOf = index => { if (!scenes.has(index)) scenes.set(index, new MissionScene(index)); return scenes.get(index); };
const eye = new THREE.Vector3(), look = new THREE.Vector3(); let framed = -1;

// ---------------------------------------------------------------- interface
const scrub = $('#scrub'), marks = $('#marks'), board = $('#board'), banner = $('#banner'), title = $('#title');
scrub.max = TOTAL;
function fitUi() { document.documentElement.style.setProperty('--s', clamp(Math.min(window.innerWidth / 1500, window.innerHeight / 820), 0.75, 1.8).toFixed(3)); }
const short = run => run.ref ? 'REFERENCE' : run.label.toUpperCase();
function buildBoard() {
  board.innerHTML = `<h2>STANDINGS<span id="after"></span></h2><div id="rows"></div>
    <p id="foot">Mean score over the missions played so far. A bar is one mission: its width is the score, ½ means the rover finished away from base, LOST means its battery ran out. ${esc(DATA.note || '')}</p>`;
  const rows = $('#rows');
  for (const run of RUNS) {
    const row = document.createElement('div');
    row.className = 'row' + (run.ref ? ' ref' : '');
    row.innerHTML = `<div class="who"><b>${esc(short(run))}</b><em>0.00</em></div><div class="cells">${MISSIONS.map(() => '<div class="cell"><u></u></div>').join('')}</div><div class="how">${esc(run.how)}</div>`;
    if (!run.ref) row.onclick = () => { state.follow = run; };
    rows.append(row); run.row = row; run.cells = [...row.querySelectorAll('.cell')]; run.score = $('em', row);
  }
  $('#missions').innerHTML = MISSIONS.map((m, i) => `<button data-m="${i}">${i + 1}<i></i></button>`).join('');
  for (const button of $('#missions').children) button.onclick = () => seek(+button.dataset.m * T);
  $('#legend').innerHTML = `<span><i style="background:${css(GOLD)}"></i>Reference controller</span><span><i style="background:${css(ICE)}"></i>Claude run you follow</span><span><i style="background:${css(0x6f5a50)}"></i>Every other Claude run</span>`;
  $('#pitch').innerHTML = `${K} missions back to back, one second per tick. Nobody can joystick that, so each Claude model wrote an autopilot. <b>Gold is the reference controller on the same missions.</b>`;
  $('#cast').innerHTML = RUNS.map(run => `<li class="${run.ref ? 'ref' : ''}"><span>${esc(short(run))}</span><small>${esc(run.how)}</small></li>`).join('');
}
function drawMarks() {
  const w = marks.clientWidth, h = marks.clientHeight, ratio = window.devicePixelRatio || 1;
  if (marks.width !== Math.round(w * ratio)) { marks.width = Math.round(w * ratio); marks.height = Math.round(h * ratio); }
  const g = marks.getContext('2d'); g.setTransform(ratio, 0, 0, ratio, 0, 0); g.clearRect(0, 0, w, h);
  const x = t => t / TOTAL * w, mid = h / 2;
  g.fillStyle = 'rgba(243,234,217,.22)'; g.fillRect(0, mid - 1.5, w, 3);
  for (let k = 0; k <= K; k++) { g.fillStyle = 'rgba(243,234,217,.5)'; g.fillRect(Math.min(w - 2, x(k * T)), mid - 7, 2, 14); }
  for (const run of CLAUDE) run.tracks.forEach((track, k) => { if (track.deadTick !== null) { g.fillStyle = css(RED); g.fillRect(x(k * T + track.deadTick) - 1.5, mid - 9, 3, 7); } });
  g.fillStyle = css(INK); g.fillRect(0, mid - 1.5, x(state.g), 3);
  g.fillRect(x(state.g) - 1.5, mid - 10, 3, 20);
}
function setText(node, value) { if (node.textContent !== value) node.textContent = value; }
function updateBoard() {
  const g = state.g, mission = Math.min(K - 1, Math.floor(g / T)), local = g - mission * T, over = g >= TOTAL;
  const rows = RUNS.map(run => ({ run, s: standing(run, g) }));
  const order = rows.slice().sort((a, b) => b.s.live - a.s.live || a.run.index - b.run.index);
  const height = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--s')) * 62;
  order.forEach(({ run, s }, place) => {
    run.row.style.top = place * height + 'px';
    run.row.classList.toggle('on', run === state.follow);
    run.row.classList.toggle('shade', !run.ref && run !== state.follow);
    setText(run.score, two(s.live));
    run.cells.forEach((cell, k) => {
      const done = k < s.done, live = !done && k === mission && !over, m = run.missions[k], track = run.tracks[k];
      const dead = track.deadTick !== null && (done || (live && local >= track.deadTick));
      cell.classList.toggle('lost', dead); cell.classList.toggle('now', live);
      cell.classList.toggle('away', done && m.alive && !m.home);
      cell.firstChild.style.width = (done ? m.reward : live ? s.now : 0) * 100 + '%';
      cell.firstChild.style.opacity = done ? 1 : 0.55;
    });
  });
  setText($('#after'), over ? 'final' : g < 1e-6 ? 'before the start' : `mission ${mission + 1} of ${K}`);
  [...$('#missions').children].forEach((button, k) => {
    button.classList.toggle('on', k === mission && !over);
    const done = k < (over ? K : mission), best = Math.max(...CLAUDE.map(r => r.missions[k].reward));
    button.classList.toggle('ref', done && REF.missions[k].reward > best + 1e-9);
    button.classList.toggle('claude', done && best > REF.missions[k].reward + 1e-9);
  });
  $('#clock b').textContent = String(Math.min(T, Math.floor(local + 1e-6))).padStart(2, '0');
  $('#clock span').textContent = `/${T} · M${mission + 1}`;
  $('#tag').innerHTML = `<b>MISSION ${mission + 1}</b><span>of ${K} · every position fix is ${MISSIONS[mission].delay} ticks old and off by up to a metre</span>`;
  // banner: the mission card for its first ticks, the result at the very end
  let text = '', alpha = 0;
  if (over) {
    const best = CLAUDE.slice().sort((a, b) => b.reward - a.reward)[0], lost = CLAUDE.reduce((n, r) => n + r.lost, 0);
    text = `<b><em style="color:${css(GOLD)}">${two(REF.reward)}</em> · <em style="color:${css(ICE)}">${best ? two(best.reward) : '–'}</em></b><span>Reference against the best of ${CLAUDE.length} Claude runs${best ? ` (${esc(best.label)})` : ''} · ${lost} rover${lost === 1 ? '' : 's'} lost by Claude, ${REF.lost} by the reference</span>`;
    alpha = 1;
  } else if (local < 2.2 && g > 1e-6 || (g <= 1e-6 && !state.playing)) {
    text = `<b>MISSION ${mission + 1}</b><span>${MISSIONS[mission].targets.filter(t => !t.appear).length} targets on the map · more will appear</span>`;
    alpha = g <= 1e-6 ? 0 : clamp(Math.min(local / 0.25, (2.2 - local) / 0.6), 0, 1);
  }
  if (banner.dataset.text !== text) { banner.dataset.text = text; banner.innerHTML = text; }
  banner.classList.toggle('final', over);
  banner.style.opacity = alpha;
}

// ---------------------------------------------------------------- loop and input
function setPlaying(on) { state.playing = on; $('#play').textContent = on ? '❚❚' : '▶'; }
function seek(g) { state.g = clamp(g, 0, TOTAL); }
function setSpeed(i) { state.speed = clamp(i, 0, SPEEDS.length - 1); $('#speed').textContent = SPEEDS[state.speed][1]; }
function showTitle(on) { title.classList.toggle('gone', !on); if (on) setPlaying(false); }
function toggleFull() { if (document.fullscreenElement) document.exitFullscreen(); else document.documentElement.requestFullscreen(); }
$('#play').onclick = () => { if (state.g >= TOTAL) seek(0); setPlaying(!state.playing); };
$('#speed').onclick = () => setSpeed((state.speed + 1) % SPEEDS.length);
scrub.oninput = () => { seek(+scrub.value); setPlaying(false); };
title.onclick = () => { showTitle(false); setPlaying(true); };
window.addEventListener('keydown', event => {
  if (event.metaKey || event.ctrlKey || event.altKey) return;
  const key = event.key;
  if (!title.classList.contains('gone')) { if (key === 'Enter' || key === ' ') { event.preventDefault(); showTitle(false); setPlaying(true); } else if (key === 'f' || key === 'F') toggleFull(); return; }
  if (key === ' ') { event.preventDefault(); if (state.g >= TOTAL) seek(0); setPlaying(!state.playing); }
  else if (key === 'ArrowRight') { setPlaying(false); seek(Math.floor(state.g + 1e-6) + 1); }
  else if (key === 'ArrowLeft') { setPlaying(false); seek(Math.ceil(state.g - 1e-6) - 1); }
  else if (key >= '1' && key <= String(Math.min(9, K))) seek((+key - 1) * T);
  else if (key === '-' || key === '_') setSpeed(state.speed - 1);
  else if (key === '=' || key === '+') setSpeed(state.speed + 1);
  else if (key === 'f' || key === 'F') toggleFull();
  else if (key === 'Escape') showTitle(true);
  else if (key === 'Tab' && CLAUDE.length) { event.preventDefault(); state.follow = CLAUDE[(CLAUDE.indexOf(state.follow) + 1) % CLAUDE.length]; }
});
window.addEventListener('resize', fitUi);

let last = performance.now(), hold = 0;
function frame(now) {
  const dt = Math.min(0.1, (now - last) / 1000); last = now;
  const wall = now / 1000;
  if (state.playing) {
    const before = state.g, mission = Math.floor(before / T);
    if (hold > 0) hold -= dt;                                             // a breath at the end of each mission
    else {
      let next = before + dt * SPEEDS[state.speed][0];
      if (next >= (mission + 1) * T && before < (mission + 1) * T - 1e-6) { next = (mission + 1) * T - 1e-6; hold = 1.4; }
      if (next >= TOTAL) { next = TOTAL; setPlaying(false); }
      state.g = next;
    }
  }
  const g = state.g, index = Math.min(K - 1, Math.floor(g / T)), local = Math.min(T, g - index * T);
  const world = sceneOf(index);
  world.apply(local, wall, state.follow);
  // viewport: everything left of the standings and under the top strip
  const s = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--s')) || 1;
  const W = window.innerWidth, H = window.innerHeight, barH = Math.round(42 * s), boardW = Math.round(340 * s);
  const vw = Math.max(200, W - boardW), vh = Math.max(200, H - barH);
  if (renderer.domElement.width !== Math.round(W * renderer.getPixelRatio()) || renderer.domElement.height !== Math.round(H * renderer.getPixelRatio())) renderer.setSize(W, H, false);
  camera.aspect = vw / vh;
  const fit = world.radius / Math.sin(rad(camera.fov) / 2) / Math.min(1, camera.aspect * 0.92), sway = Math.sin(wall * 0.09) * 0.16 - 0.35;
  const goal = new THREE.Vector3(world.center.x + Math.sin(sway) * fit * 0.62, fit * 0.72, world.center.z + Math.cos(sway) * fit * 0.62);
  if (framed !== index) { eye.copy(goal); look.copy(world.center); framed = index; }
  eye.lerp(goal, 1 - Math.exp(-dt * 2)); look.lerp(world.center, 1 - Math.exp(-dt * 2));
  camera.position.copy(eye); camera.lookAt(look.x, 0.5, look.z); camera.updateProjectionMatrix();
  world.fitLabels(camera, vh);
  renderer.setViewport(0, 0, vw, vh); renderer.setScissor(0, 0, vw, vh); renderer.setScissorTest(true);
  renderer.render(world.scene, camera);
  if (document.activeElement !== scrub) scrub.value = g;
  updateBoard(); drawMarks();
  requestAnimationFrame(frame);
}

// #auto starts by itself; #t=137.5 opens paused at that campaign tick (mission 3, tick 37.5), so a moment can be linked
function readHash() {
  const hash = location.hash;
  if (hash.includes('t=')) { showTitle(false); setPlaying(false); seek(parseFloat(hash.split('t=')[1]) || 0); }
  if (hash.includes('auto')) { showTitle(false); setPlaying(true); }
}
window.addEventListener('hashchange', readHash);
fitUi(); buildBoard(); setSpeed(2); readHash();
requestAnimationFrame(frame);
