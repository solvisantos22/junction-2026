// Lightlag · Mars ops demo. One file, no build step; three.js is the only dependency.
// Everything shown comes from recorded runs in window.LIGHTLAG_DATA (see viewer/build_mars.py).
import * as THREE from 'three';

if (document.readyState === 'loading') await new Promise(resolve => document.addEventListener('DOMContentLoaded', resolve, { once: true }));

const DATA = window.LIGHTLAG_DATA;
const $ = (selector, root = document) => root.querySelector(selector);
const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
const lerp = (a, b, t) => a + (b - a) * t;
const smooth = (a, b, x) => { const t = clamp((x - a) / (b - a), 0, 1); return t * t * (3 - 2 * t); };
const TAU = Math.PI * 2, rad = THREE.MathUtils.degToRad;
const fmt = n => String(+(+n).toFixed(2));
const esc = text => String(text).replace(/&/g, '&amp;').replace(/</g, '&lt;');
// Four signal colours: what the agent sends, what comes back, bad news, a sample in the bag.
const INK = 0xf3ead9, AMBER = 0xffb224, ICE = 0x9fd8ff, RED = 0xff4a2f, LIME = 0xb6e35a, MUTE = 0x8a7466, LINE = 0x1b1310;
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
// Ground height in metres at scene coordinates. Flat where the rover drives, hills beyond.
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
const TEX = {
  // sand: two flat tones in wind ripples
  sand: canvasTexture(256, (g, s) => {
    g.fillStyle = '#dba25b'; g.fillRect(0, 0, s, s);
    for (const [color, width, shift] of [['#c88d49', 8, 0], ['#ecbd78', 3, 10]]) {
      g.strokeStyle = color; g.lineWidth = width;
      for (let k = -1; k < 9; k++) {
        g.beginPath();
        for (let x = 0; x <= s; x += 8) g.lineTo(x, k * 32 + 16 + shift + Math.sin(x / s * TAU * 2 + k * 0.9) * 5);
        g.stroke();
      }
    }
  }),
  puff: canvasTexture(64, (g, s) => { g.fillStyle = '#fff'; g.beginPath(); g.arc(s / 2, s / 2, s / 2 - 2, 0, TAU); g.fill(); }),
};

// A line of text that faces the camera, with an optional timer bar under it.
class Label {
  constructor(px = 54) {
    this.canvas = document.createElement('canvas'); this.canvas.width = 512; this.canvas.height = 128;
    this.texture = new THREE.CanvasTexture(this.canvas); this.texture.colorSpace = THREE.SRGBColorSpace;
    this.sprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: this.texture, transparent: true, depthTest: false, fog: false }));
    this.sprite.center.set(0.5, 0); this.sprite.renderOrder = 10;
    this.sprite.userData = { px, aspect: 4 };   // px: height on screen
    this.key = null;
  }
  set(text, color = css(INK), bar = null, barColor = css(AMBER)) {
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

// ---------------------------------------------------------------- runs
class Run {
  constructor(raw) {
    Object.assign(this, raw);
    const replay = raw.replay, dynamic = replay.dynamic || {};
    this.cfg = replay.config; this.world = replay.world; this.states = replay.states;
    this.T = this.states.length - 1; this.K = this.cfg.delay_ticks;
    this.result = replay.result;
    this.lateFraction = dynamic.late_fraction ?? 1;
    this.value = Object.fromEntries(this.world.targets.map(t => [t.id, t.value]));
    this.plan = Object.fromEntries(this.world.targets.map(t => [t.id, { appear: 0, deadline: null }]));
    for (const t of dynamic.targets || []) this.plan[t.id] = { appear: t.appear_tick || 0, deadline: t.deadline_tick ?? null };
    this.samples = Object.fromEntries((this.result.samples || []).map(s => [s.target_id, { tick: s.tick, credited: s.credited_value, onTime: s.on_time }]));
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
    const step = list => list.map((s, i) => i ? Math.hypot(s.position[0] - list[i - 1].position[0], s.position[1] - list[i - 1].position[1]) : 0);
    this.moved = step(this.states);
    // what reached Earth: one packet per tick, with whatever sensor noise the mission has
    this.tele = this.states.slice();
    for (const packet of replay.received_telemetry || []) if (packet.tick <= this.T) this.tele[packet.tick] = packet;
    this.teleMoved = step(this.tele);
    this.wheel = []; let w = 0; for (const s of this.states) { w += s.wheel_odometry || 0; this.wheel.push(w); }
    // each drive as commanded against what the wheels achieved
    this.drive = this.states.map(() => null);
    const byTick = new Map(this.commands.filter(c => c.done && c.action === 'drive').map(c => [c.exec, c]));
    for (let i = 1; i <= this.T; i++) {
      const c = byTick.get(i); if (!c || c.metres < 0.3) continue;
      const from = this.states[i - 1].position, h = rad(c.heading_deg);
      this.drive[i] = { aim: [from[0] + Math.cos(h) * c.metres, from[1] + Math.sin(h) * c.metres], slip: clamp(1 - this.moved[i] / c.metres, 0, 1), sand: this.states[i].terrain === 'sand' };
    }
    // first saved tick with too little reserve to finish home alive, even with a straight drive and no slip
    const doomed = this.states.find(s => s.alive && s.battery < this.need(s.tick, s.position[0], s.position[1]));
    this.doomedTick = doomed ? doomed.tick : null;
    if (doomed) this.events.push({ tick: doomed.tick, type: 'doomed' });
    this.events.sort((a, b) => a.tick - b.tick);
    let lastTick = -1, n = 0;
    this.calls = raw.calls.map((c, index) => {
      if (c.tick !== lastTick) { lastTick = c.tick; n = 0; }
      return { ...c, index, at: c.tick + Math.min(0.9, n++ * 0.17) };
    });
    const xs = [this.world.base[0], ...this.world.targets.map(t => t.x), ...this.states.map(s => s.position[0])];
    const ys = [this.world.base[1], ...this.world.targets.map(t => t.y), ...this.states.map(s => s.position[1])];
    const pad = 4.5;
    this.bounds = { x0: Math.min(...xs) - pad, x1: Math.max(...xs) + pad, y0: Math.min(...ys) - pad, y1: Math.max(...ys) + pad };
  }
  // Lower bound for finishing home alive: remaining idle drain plus a straight drive to the accepted base radius, without slip or detours.
  need(t, x, y) { return (this.T - t) * this.cfg.idle_cost + Math.max(0, Math.hypot(x - this.world.base[0], y - this.world.base[1]) - this.cfg.base_radius) * this.cfg.drive_cost; }
  carried(t) { let sum = 0; for (const id in this.samples) if (this.samples[id].tick <= t + 1e-6) sum += this.samples[id].credited; return sum; }
  stateAt(t) { return this.states[clamp(Math.floor(t + 1e-6), 0, this.T)]; }
  // Where the rover really is at time t: it turns at the start of a tick, then drives.
  sample(t) {
    t = clamp(t, 0, this.T);
    const i = Math.min(this.T - 1, Math.floor(t)), f = t - i;
    const a = this.states[i], b = this.states[i + 1];
    const moving = this.moved[i + 1] > 1e-6, drive = moving ? smooth(0.16, 1, f) : 0, turn = moving ? smooth(0, 0.2, f) : 0;
    const delta = ((b.heading_deg - a.heading_deg + 540) % 360) - 180, d = this.drive[i + 1];
    return {
      x: lerp(a.position[0], b.position[0], drive), y: lerp(a.position[1], b.position[1], drive),
      heading: a.heading_deg + (moving ? delta * turn : 0), wheel: lerp(this.wheel[i], this.wheel[i + 1], drive),
      moving: moving && f > 0.16 && f < 0.985, slip: d ? d.slip : 0, sand: b.terrain === 'sand',
      battery: lerp(a.battery, b.battery, f), state: this.stateAt(t), tick: t,
    };
  }
  // What Earth has at time t: the packet for tick floor(t) - K. It drops into place when it lands, then holds still.
  seen(t) {
    const whole = Math.floor(t + 1e-6), s = clamp(whole - this.K, 0, this.T), b = this.tele[s], a = this.tele[Math.max(0, s - 1)];
    const k = whole - this.K > 0 ? smooth(0, 0.16, t - whole) : 1;
    const delta = ((b.heading_deg - a.heading_deg + 540) % 360) - 180;
    return {
      x: lerp(a.position[0], b.position[0], k), y: lerp(a.position[1], b.position[1], k), heading: a.heading_deg + delta * k,
      wheel: this.wheel[s], moving: false, slip: 0, sand: b.terrain === 'sand', battery: b.battery, state: b, tick: s,
    };
  }
}
const MISSIONS = DATA.missions.map(raw => {
  const runs = raw.runs.map(r => new Run(r));
  return { ...raw, runs, T: Math.max(...runs.map(r => r.T)), K: runs[0].K, featuredRun: runs.find(r => r.id === raw.featured) || runs[0] };
});

// ---------------------------------------------------------------- shared scene pieces
const flat = (color, extra = {}) => new THREE.MeshStandardMaterial({ color, roughness: 0.9, metalness: 0, flatShading: true, ...extra });
const MAT = {
  ground: flat(0xffffff, { vertexColors: true, roughness: 1 }),
  sand: new THREE.MeshStandardMaterial({ map: TEX.sand, roughness: 1, metalness: 0, polygonOffset: true, polygonOffsetFactor: -2, polygonOffsetUnits: -2 }),
  rock: flat(0x7a3d27), basalt: flat(0x2c211d), pad: flat(0x3b2f2a),
  white: flat(0xefe6d6), dark: flat(0x2a2421), metal: flat(0x8c8782, { roughness: 0.7 }), solar: flat(0x24407e), tan: flat(0xc59a55), accent: flat(0xff6a1f),
  lens: new THREE.MeshBasicMaterial({ color: ICE }), lamp: new THREE.MeshBasicMaterial({ color: 0xfff2c8 }),
  shell: new THREE.MeshBasicMaterial({ color: LINE, side: THREE.BackSide }),
  // the ghost is drawn in two passes, depth first, so it reads as one flat silhouette and not a stack of parts
  ghostDepth: new THREE.MeshBasicMaterial({ colorWrite: false }),
  ghost: new THREE.MeshBasicMaterial({ color: ICE, transparent: true, opacity: 0.42, depthWrite: false, depthFunc: THREE.LessEqualDepth, fog: false }),
};
const BANDS = [0x8f4126, 0xa34b2b, 0xb35631, 0xc2633a].map(c => new THREE.Color(c)), HILL = new THREE.Color(0x6f3322);
const worldCache = new Map();
function sharedWorld(world) {
  const key = JSON.stringify(world);
  if (worldCache.has(key)) return worldCache.get(key);
  const cx = world.width / 2, cy = world.height / 2;
  const inSand = (x, y) => world.sand.some(r => x >= r.x1 - 0.4 && x <= r.x2 + 0.4 && y >= r.y1 - 0.4 && y <= r.y2 + 0.4);
  // ground: big flat-shaded triangles in four tones
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
  // sand: flat sheets with the ripple texture laid in world coordinates, so overlapping sheets line up
  const sands = world.sand.map((r, index) => {
    const w = r.x2 - r.x1, h = r.y2 - r.y1, g = new THREE.PlaneGeometry(w, h);
    g.rotateX(-Math.PI / 2);
    for (let i = 0, p = g.attributes.position, uv = g.attributes.uv; i < p.count; i++) uv.setXY(i, (r.x1 + p.getX(i) + w / 2) / 5, (r.y2 - (p.getZ(i) + h / 2)) / 5);
    return { geometry: g, x: r.x1 + w / 2 - cx, y: 0.018 + index * 0.004, z: -(r.y1 + h / 2 - cy) };
  });
  // scattered rocks: pebbles in the driving area, boulders outside it
  const rocks = [];
  const rng = (() => { let s = 12345; return () => (s = (s * 16807) % 2147483647) / 2147483647; })();
  for (let i = 0; i < 520; i++) {
    const far = i > 130, radius = far ? 26 + rng() * 150 : rng() * 27, angle = rng() * TAU;
    const x = Math.cos(angle) * radius, z = Math.sin(angle) * radius, sx = x + cx, sy = cy - z;
    const inside = sx > -1 && sx < world.width + 1 && sy > -1 && sy < world.height + 1;
    const nearEdge = !inside && sx > -5 && sx < world.width + 5 && sy > -5 && sy < world.height + 5;
    const scale = inside ? 0.06 + rng() * 0.12 : 0.3 + Math.pow(rng(), 2.2) * 2.6;
    const sq = 0.55 + rng() * 0.5, rx = rng() * TAU, ry = rng() * TAU;
    if (nearEdge || (inside && (inSand(sx, sy) || Math.hypot(sx - world.base[0], sy - world.base[1]) < 3))) continue;
    rocks.push({ x, z, y: terrainHeight(x, z) + scale * 0.25, scale, rx, ry, sq });
  }
  const rockGeometry = new THREE.IcosahedronGeometry(1, 0), rp = rockGeometry.attributes.position;
  for (let i = 0; i < rp.count; i++) {
    const k = 0.74 + 0.5 * hash2(rp.getX(i) * 3.1 + rp.getY(i) * 1.7, rp.getZ(i) * 2.3);
    rp.setXYZ(i, rp.getX(i) * k, rp.getY(i) * k, rp.getZ(i) * k);
  }
  rockGeometry.computeVertexNormals();
  const shared = { key, cx, cy, ground, sands, rocks, rockGeometry };
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
// Gather a group's parts in the group's own coordinates: one list of geometries per material, plus, when
// `width` is given, an ink shell for each part: the same shape a few centimetres larger, drawn back-face only.
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
// One mesh per material and one for the outline, placed where the group was. Keeps a rover to about thirty draw calls.
function bake(root, width = 0.028) {
  const { buckets, shells } = collect(root, width), out = new THREE.Group();
  for (const [material, list] of buckets) { const mesh = new THREE.Mesh(join(list), material); mesh.castShadow = mesh.receiveShadow = true; out.add(mesh); }
  if (shells.length) out.add(new THREE.Mesh(join(shells), MAT.shell));
  out.position.copy(root.position); out.rotation.copy(root.rotation); out.scale.copy(root.scale);
  return out;
}
// A six-wheeled rover facing +x, about 2.6 m long, with rocker-bogie suspension.
function makeRover() {
  const rover = new THREE.Group(), body = new THREE.Group(), fixed = new THREE.Group();
  fixed.add(box(1.36, 0.26, 0.88, MAT.white, 0, 0.78, 0));                // chassis
  fixed.add(box(1.36, 0.07, 0.88, MAT.tan, 0, 0.615, 0));                 // foil underside
  fixed.add(box(1.4, 0.035, 0.94, MAT.solar, 0, 0.93, 0));                // deck
  fixed.add(box(0.2, 0.04, 0.94, MAT.accent, -0.28, 0.935, 0));           // mission stripe
  const power = new THREE.Group();                                         // power unit with cooling fins
  power.add(box(0.52, 0.2, 0.28, MAT.metal));
  for (const k of [-1, 0, 1]) power.add(box(0.48, 0.3, 0.02, MAT.dark, 0, 0, k * 0.11));
  power.position.set(-0.88, 0.95, 0); power.rotation.z = 0.5; fixed.add(power);
  fixed.add(cyl(0.04, 0.05, 0.98, MAT.metal, 0.46, 1.42, 0.3, 8));        // mast
  const dish = cyl(0.3, 0.05, 0.1, MAT.white, -0.34, 1.34, -0.26, 6); dish.rotation.set(0.5, 0, 0.35); fixed.add(dish);   // high-gain antenna
  fixed.add(cyl(0.02, 0.02, 0.4, MAT.metal, -0.34, 1.13, -0.26, 6));
  fixed.add(cyl(0.015, 0.015, 0.5, MAT.metal, -0.6, 1.2, 0.34, 6));       // whip antenna
  const shoulder = new THREE.Group();                                      // folded sampling arm
  const upper = box(0.6, 0.06, 0.06, MAT.metal, 0.3, 0, 0), lower = box(0.5, 0.05, 0.05, MAT.metal, 0.56, -0.14, 0), turret = cyl(0.11, 0.11, 0.16, MAT.tan, 0.34, -0.22, 0, 10);
  lower.rotation.z = 0.62; turret.rotation.x = Math.PI / 2; shoulder.add(upper, lower, turret);
  shoulder.position.set(0.62, 0.76, -0.34); shoulder.rotation.z = -0.25; fixed.add(shoulder);
  const hubs = [[0.76, 0.3], [0.04, 0.3], [-0.72, 0.3]], bogie = [0.4, 0.52], pivot = [-0.14, 0.66], wheels = [];
  const strut = (a, b, side) => { const dx = b[0] - a[0], dy = b[1] - a[1], beam = box(Math.hypot(dx, dy), 0.06, 0.06, MAT.metal, (a[0] + b[0]) / 2, (a[1] + b[1]) / 2, side * 0.52); beam.rotation.z = Math.atan2(dy, dx); fixed.add(beam); };
  for (const side of [-1, 1]) { strut(hubs[0], bogie, side); strut(bogie, hubs[1], side); strut(bogie, pivot, side); strut(pivot, hubs[2], side); }
  body.add(bake(fixed));
  const spare = new THREE.Group();                                         // one wheel, baked once and reused
  const tyre = cyl(0.3, 0.3, 0.22, MAT.dark, 0, 0, 0, 12); tyre.rotation.x = Math.PI / 2; spare.add(tyre);
  const cap = cyl(0.13, 0.13, 0.24, MAT.metal, 0, 0, 0, 8); cap.rotation.x = Math.PI / 2; spare.add(cap);
  for (let k = 0; k < 8; k++) { const tread = box(0.07, 0.035, 0.23, MAT.metal), a = k * TAU / 8; tread.position.set(Math.cos(a) * 0.3, Math.sin(a) * 0.3, 0); tread.rotation.z = a + Math.PI / 2; spare.add(tread); }
  const wheelParts = bake(spare);
  for (const side of [-1, 1]) for (const [x, y] of hubs) { const wheel = wheelParts.clone(); wheel.position.set(x, y, side * 0.62); body.add(wheel); wheels.push(wheel); }
  const skull = new THREE.Group();                                         // camera head on the mast
  skull.add(box(0.32, 0.18, 0.44, MAT.white)); skull.add(box(0.06, 0.2, 0.46, MAT.accent, -0.14, 0, 0));
  const head = bake(skull); head.position.set(0.46, 1.98, 0.3); body.add(head);
  const eyes = [-0.11, 0.11].map(z => { const eye = cyl(0.055, 0.055, 0.05, MAT.lens, 0.17, 0, z, 10); eye.rotation.z = Math.PI / 2; eye.castShadow = false; head.add(eye); return eye; });
  const lamps = [-0.3, 0.3].map(z => { const lamp = new THREE.Mesh(new THREE.SphereGeometry(0.045, 8, 6), MAT.lamp); lamp.position.set(0.69, 0.8, z); body.add(lamp); return lamp; });
  rover.add(body);
  rover.userData = { wheels, head, body, lights: [...lamps, ...eyes] };
  return rover;
}
// The same shape as a pale ghost: the rover as Earth last saw it. Two meshes: depth first, then one flat tint.
function makeGhost() {
  const { buckets } = collect(makeRover()), all = [];
  for (const [material, list] of buckets) if (material !== MAT.shell) all.push(...list);
  const shape = join(all), ghost = new THREE.Group(), depth = new THREE.Mesh(shape, MAT.ghostDepth), fill = new THREE.Mesh(shape, MAT.ghost);
  depth.renderOrder = 1; fill.renderOrder = 3; ghost.add(depth, fill);
  return ghost;
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
      col = mix(col, vec3(0.86, 0.93, 1.0), smoothstep(0.99962, 0.99972, s));          // a small hard sun
      col += vec3(0.70, 0.80, 0.95) * pow(s, 60.0) * 0.16;
      if (n.y < 0.0) col = vec3(0.925, 0.735, 0.545);
      gl_FragColor = vec4(col, 1.0); }`,
}));
const FOG_COLOR = new THREE.Color().setRGB(0.925, 0.735, 0.545, THREE.SRGBColorSpace);

// ---------------------------------------------------------------- one run's scene
const flatMark = (color, opacity = 1) => new THREE.MeshBasicMaterial({ color, transparent: true, opacity, side: THREE.DoubleSide, depthWrite: false, fog: false });
class MarsScene {
  constructor(run) {
    this.run = run;
    const world = run.world, shared = this.shared = sharedWorld(world);
    const scene = this.scene = new THREE.Scene();
    scene.fog = new THREE.FogExp2(FOG_COLOR, 0.0052);
    scene.background = FOG_COLOR;
    scene.add(SKY.clone());
    scene.add(new THREE.HemisphereLight(0xffe1c2, 0x7a3d27, 1.2));
    const sun = this.sun = new THREE.DirectionalLight(0xfff1dd, 2.7);
    sun.position.set(-55, 42, -72).multiplyScalar(0.9);
    sun.castShadow = true; sun.shadow.mapSize.set(1536, 1536); sun.shadow.bias = -0.0006; sun.shadow.normalBias = 0.03;
    Object.assign(sun.shadow.camera, { left: -34, right: 34, top: 34, bottom: -34, near: 10, far: 220 });
    scene.add(sun, sun.target);
    const ground = new THREE.Mesh(shared.ground, MAT.ground); ground.receiveShadow = true; scene.add(ground);
    for (const s of shared.sands) { const mesh = new THREE.Mesh(s.geometry, MAT.sand); mesh.position.set(s.x, s.y, s.z); mesh.receiveShadow = true; scene.add(mesh); }
    const rocks = new THREE.InstancedMesh(shared.rockGeometry, MAT.rock, shared.rocks.length);
    const m = new THREE.Matrix4(), q = new THREE.Quaternion(), e = new THREE.Euler();
    shared.rocks.forEach((r, i) => { e.set(r.rx, r.ry, 0); q.setFromEuler(e); m.compose(new THREE.Vector3(r.x, r.y, r.z), q, new THREE.Vector3(r.scale, r.scale * r.sq, r.scale)); rocks.setMatrixAt(i, m); });
    rocks.castShadow = rocks.receiveShadow = true; scene.add(rocks);
    this.tactical = new THREE.Group(); scene.add(this.tactical);   // drawn only on the map
    this.cinematic = new THREE.Group(); scene.add(this.cinematic); // drawn only in 3D views
    this.buildArena(world); this.buildHazards(world); this.buildBase(world); this.buildTargets(world); this.buildDynamic();
  }
  P(x, y, h = 0) { return new THREE.Vector3(x - this.shared.cx, h, -(y - this.shared.cy)); }
  // Size labels in pixels, not metres: full size near the camera, down to 60% far away, so a distant cluster stays readable.
  fitLabels(camera, viewHeight) {
    const v = new THREE.Vector3();
    this.scene.traverse(node => {
      if (!node.isSprite || !node.userData.px) return;
      const far = camera.isOrthographicCamera ? 0 : Math.max(0.5, camera.position.distanceTo(node.getWorldPosition(v)));
      const perPixel = far ? 2 * Math.tan(rad(camera.fov) / 2) * far / viewHeight : (camera.top - camera.bottom) / viewHeight;
      const h = perPixel * node.userData.px * (far ? clamp(13 / far, 0.6, 1.05) : 1);
      node.scale.set(h * node.userData.aspect, h, 1);
    });
  }
  buildArena(world) {
    const { width: w, height: h } = world, corners = [[0, 0], [w, 0], [w, h], [0, h], [0, 0]].map(([x, y]) => this.P(x, y, 0.06));
    const border = new THREE.Line(new THREE.BufferGeometry().setFromPoints(corners), new THREE.LineDashedMaterial({ color: INK, dashSize: 0.9, gapSize: 0.9, transparent: true, opacity: 0.4 }));
    border.computeLineDistances(); this.scene.add(border);
    const lines = new THREE.GridHelper(Math.max(w, h), Math.max(w, h) / 5, INK, INK);
    lines.material.transparent = true; lines.material.opacity = 0.13; lines.material.fog = false; lines.position.y = 0.05; this.tactical.add(lines);
  }
  buildHazards(world) {
    let seed = 7; const rng = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
    for (const r of world.hazards) {
      const w = r.x2 - r.x1, h = r.y2 - r.y1, count = Math.round(w * h * 2.2) + 6;
      const boulders = new THREE.InstancedMesh(this.shared.rockGeometry, MAT.basalt, count), m = new THREE.Matrix4(), q = new THREE.Quaternion(), e = new THREE.Euler();
      for (let i = 0; i < count; i++) {
        const s = 0.22 + rng() * 0.5; e.set(rng() * TAU, rng() * TAU, 0); q.setFromEuler(e);
        m.compose(this.P(r.x1 + rng() * w, r.y1 + rng() * h, s * 0.45), q, new THREE.Vector3(s, s * (0.7 + rng() * 0.7), s)); boulders.setMatrixAt(i, m);
      }
      boulders.castShadow = boulders.receiveShadow = true; this.scene.add(boulders);
      const pts = [[r.x1, r.y1], [r.x2, r.y1], [r.x2, r.y2], [r.x1, r.y2], [r.x1, r.y1]].map(([x, y]) => this.P(x, y, 0.09));
      this.scene.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), new THREE.LineBasicMaterial({ color: RED, transparent: true, opacity: 0.8, fog: false })));
      const plate = new THREE.Mesh(new THREE.PlaneGeometry(w, h), flatMark(RED, 0.3));
      plate.rotation.x = -Math.PI / 2; plate.position.copy(this.P((r.x1 + r.x2) / 2, (r.y1 + r.y2) / 2, 0.07)); this.tactical.add(plate);
    }
  }
  buildBase(world) {
    const [bx, by] = world.base, r = this.run.cfg.base_radius;
    const pad = cyl(1.7, 1.7, 0.05, MAT.pad, 0, 0, 0, 10); pad.position.copy(this.P(bx, by, 0.02)); pad.castShadow = false; this.scene.add(pad);
    const ring = new THREE.Mesh(new THREE.RingGeometry(r - 0.1, r, 40), flatMark(INK)); ring.rotation.x = -Math.PI / 2; ring.position.copy(this.P(bx, by, 0.065)); this.scene.add(ring);
    this.lander = makeLander(); this.lander.position.copy(this.P(bx + 8.5, by - 9.5, 0)); this.lander.rotation.y = 2.4; this.cinematic.add(this.lander);
    this.baseLabel = new Label(46).set('BASE'); this.baseLabel.sprite.position.copy(this.P(bx, by, 0.5)); this.cinematic.add(this.baseLabel.sprite);
    const home = new THREE.Shape(); home.moveTo(-1, -0.9); home.lineTo(1, -0.9); home.lineTo(1, 0.2); home.lineTo(0, 1.15); home.lineTo(-1, 0.2); home.closePath();
    const plate = new THREE.Mesh(new THREE.ShapeGeometry(home), new THREE.MeshBasicMaterial({ color: INK, depthTest: false, fog: false }));
    plate.rotation.x = -Math.PI / 2; plate.position.copy(this.P(bx, by, 0.45)); plate.renderOrder = 5; this.tactical.add(plate);
  }
  // Each target is a survey flag with a ring on the ground and a timer over it.
  buildTargets(world) {
    const r = this.run.cfg.target_radius, pennant = new THREE.BufferGeometry();
    pennant.setAttribute('position', new THREE.BufferAttribute(new Float32Array([0, 0, 0, 0, -0.56, 0, 0.95, -0.28, 0]), 3));
    this.targets = world.targets.map(t => {
      const group = new THREE.Group(); group.position.copy(this.P(t.x, t.y, 0));
      const material = flatMark(AMBER);
      const ring = new THREE.Mesh(new THREE.RingGeometry(r - 0.1, r, 40), material); ring.rotation.x = -Math.PI / 2; ring.position.y = 0.07; group.add(ring);
      const disc = new THREE.Mesh(new THREE.CircleGeometry(r - 0.1, 32), flatMark(AMBER, 0.16)); disc.rotation.x = -Math.PI / 2; disc.position.y = 0.065; group.add(disc);
      const pole = cyl(0.03, 0.03, 2.3, MAT.dark, 0, 1.15, 0, 6); group.add(pole);
      const flag = new THREE.Mesh(pennant, material); flag.position.y = 2.3; group.add(flag);
      const labels = { now: new Label(52), seen: new Label(52) };
      this.scene.add(group, labels.now.sprite, labels.seen.sprite);
      return { ...t, group, ring, disc, pole, flag, material, labels };
    });
  }
  buildDynamic() {
    const scene = this.scene, run = this.run;
    this.rover = makeRover(); scene.add(this.rover);
    this.ghost = makeGhost(); scene.add(this.ghost);
    this.ghostRing = new THREE.Mesh(new THREE.RingGeometry(1.3, 1.42, 40), flatMark(ICE, 0.9)); this.ghostRing.rotation.x = -Math.PI / 2; scene.add(this.ghostRing);
    this.tether = new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(), new THREE.Vector3()]), new THREE.LineDashedMaterial({ color: ICE, dashSize: 0.3, gapSize: 0.24, fog: false })); scene.add(this.tether);
    // wheel tracks: two ribbons revealed as time passes
    this.trackPositions = new Float32Array(run.T * 2 * 18);
    const trackGeometry = new THREE.BufferGeometry(); trackGeometry.setAttribute('position', new THREE.BufferAttribute(this.trackPositions, 3));
    this.tracks = new THREE.Mesh(trackGeometry, new THREE.MeshBasicMaterial({ color: 0x4d2214, transparent: true, opacity: 0.7, depthWrite: false, polygonOffset: true, polygonOffsetFactor: -4, polygonOffsetUnits: -4 }));
    this.tracks.frustumCulled = false; this.tracks.renderOrder = 2; scene.add(this.tracks);
    this.ribbonPositions = new Float32Array(run.T * 18);
    const ribbonGeometry = new THREE.BufferGeometry(); ribbonGeometry.setAttribute('position', new THREE.BufferAttribute(this.ribbonPositions, 3));
    this.ribbon = new THREE.Mesh(ribbonGeometry, new THREE.MeshBasicMaterial({ color: INK, transparent: true, opacity: 0.85, depthWrite: false, depthTest: false, side: THREE.DoubleSide, fog: false }));
    this.ribbon.frustumCulled = false; this.ribbon.renderOrder = 4; this.tactical.add(this.ribbon);
    this.mapRover = new THREE.Mesh(new THREE.ConeGeometry(1.1, 2.6, 3), new THREE.MeshBasicMaterial({ color: INK, depthTest: false, fog: false })); this.mapRover.renderOrder = 7; this.tactical.add(this.mapRover);
    // commands sent but not yet carried out
    this.queuePositions = new Float32Array(64 * 3);
    const queueGeometry = new THREE.BufferGeometry(); queueGeometry.setAttribute('position', new THREE.BufferAttribute(this.queuePositions, 3));
    this.queue = new THREE.Line(queueGeometry, new THREE.LineDashedMaterial({ color: AMBER, dashSize: 0.45, gapSize: 0.28, fog: false })); this.queue.frustumCulled = false; scene.add(this.queue);
    this.queueNodes = Array.from({ length: 8 }, () => { const node = new THREE.Mesh(new THREE.CircleGeometry(0.2, 16), flatMark(AMBER)); node.rotation.x = -Math.PI / 2; scene.add(node); return node; });
    // where a drive was aimed, when the wheels slipped short of it
    this.aim = new THREE.Mesh(new THREE.RingGeometry(0.34, 0.46, 24), flatMark(AMBER)); this.aim.rotation.x = -Math.PI / 2; scene.add(this.aim);
    this.short = new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(), new THREE.Vector3()]), new THREE.LineBasicMaterial({ color: RED, fog: false })); scene.add(this.short);
    this.pulse = new THREE.Mesh(new THREE.RingGeometry(0.95, 1.0, 48), flatMark(LIME)); this.pulse.rotation.x = -Math.PI / 2; scene.add(this.pulse);
    this.dust = Array.from({ length: 10 }, () => { const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: TEX.puff, color: 0xd9a06a, transparent: true, depthWrite: false })); scene.add(s); return s; });
  }
  // Draw the world for one screen. kind: 'live' | 'feed' | 'map' | 'wide'. t: mission time in ticks.
  apply(kind, t, wall) {
    const run = this.run, feed = kind === 'feed', map = kind === 'map';
    const pose = feed ? run.seen(t) : run.sample(t), state = pose.state;
    const tv = pose.tick;                         // the moment this screen shows
    if (feed) wall = tv * 0.83;                   // a still frame does not animate
    this.tactical.visible = map; this.cinematic.visible = !map;
    this.scene.fog.density = map ? 0 : 0.0052;
    // rover
    const p = this.P(pose.x, pose.y, 0), parts = this.rover.userData, slipping = pose.moving && pose.slip > 0.08;
    this.rover.position.copy(p);
    this.rover.rotation.y = rad(pose.heading) + (slipping ? Math.sin(wall * 13) * 0.05 : 0);
    for (const wheel of parts.wheels) wheel.rotation.z = -pose.wheel / 0.39 - (slipping ? wall * 9 : 0);
    parts.body.position.y = pose.moving ? Math.sin(wall * 19) * 0.012 : 0;
    parts.head.rotation.y = state.alive ? Math.sin(wall * 0.7) * 0.5 : 0; parts.head.rotation.z = state.alive ? 0 : -0.6;
    for (const light of parts.lights) light.visible = state.alive;
    this.rover.scale.setScalar(map ? 0.001 : 1.3);
    // the rover as Earth last saw it (not on the delayed feed, which *is* that view)
    const seen = run.seen(t), gp = this.P(seen.x, seen.y, 0), apart = Math.hypot(seen.x - pose.x, seen.y - pose.y), showGhost = !feed && apart > 0.25;
    this.ghost.visible = showGhost && !map && apart > 1.6; this.ghostRing.visible = this.tether.visible = showGhost;
    if (showGhost) {
      this.ghost.position.copy(gp); this.ghost.rotation.y = rad(seen.heading); this.ghost.scale.setScalar(1.3);
      this.ghostRing.position.set(gp.x, map ? 0.5 : 0.08, gp.z); this.ghostRing.scale.setScalar(map ? 1.25 : 1);
      const line = this.tether.geometry.attributes.position; line.setXYZ(0, p.x, 0.4, p.z); line.setXYZ(1, gp.x, 0.4, gp.z); line.needsUpdate = true; this.tether.computeLineDistances();
    }
    // tracks up to the shown moment; on the feed they follow the reported positions
    const src = feed ? run.tele : run.states, moved = feed ? run.teleMoved : run.moved;
    let v = 0, rv = 0; const tp = this.trackPositions, rp = this.ribbonPositions, upto = Math.min(run.T, Math.ceil(tv - 1e-9));
    for (let i = 0; i < upto; i++) {
      if (moved[i + 1] < 1e-6) continue;
      const a = src[i].position, b = i + 1 > tv - 1e-9 ? [pose.x, pose.y] : src[i + 1].position;
      const A = this.P(a[0], a[1]), B = this.P(b[0], b[1]), dx = B.x - A.x, dz = B.z - A.z, len = Math.hypot(dx, dz) || 1, nx = -dz / len, nz = dx / len;
      for (const side of [-0.72, 0.72]) for (const [base, w] of [[A, -1], [B, -1], [B, 1], [A, -1], [B, 1], [A, 1]]) { tp[v++] = base.x + nx * (side + w * 0.11); tp[v++] = 0.035; tp[v++] = base.z + nz * (side + w * 0.11); }
      for (const [base, w] of [[A, -1], [B, -1], [B, 1], [A, -1], [B, 1], [A, 1]]) { rp[rv++] = base.x + nx * w * 0.17; rp[rv++] = 0.2; rp[rv++] = base.z + nz * w * 0.17; }
    }
    this.tracks.geometry.setDrawRange(0, v / 3); this.tracks.geometry.attributes.position.needsUpdate = true;
    this.ribbon.geometry.setDrawRange(0, rv / 3); this.ribbon.geometry.attributes.position.needsUpdate = true;
    this.mapRover.position.set(p.x, 0.6, p.z); this.mapRover.rotation.set(0, rad(pose.heading), -Math.PI / 2, 'YXZ');
    // commands that have been sent but whose effect this screen has not shown yet
    const pending = run.commands.filter(c => c.sent <= t && (feed ? c.exec > tv : tv < c.until));
    const from = feed ? [pose.x, pose.y] : run.stateAt(Math.min(tv, run.T - 1e-3)).position;
    const qp = this.queuePositions; let cursor = this.P(from[0], from[1]), count = 1, nodes = 0; qp[0] = p.x; qp[1] = 0.3; qp[2] = p.z;
    for (const c of pending) if (c.action === 'drive' && count < 63) {
      const a = rad(c.heading_deg); cursor = cursor.clone().add(new THREE.Vector3(Math.cos(a) * c.metres, 0, -Math.sin(a) * c.metres));
      qp[count * 3] = cursor.x; qp[count * 3 + 1] = 0.3; qp[count * 3 + 2] = cursor.z; count++;
      if (nodes < this.queueNodes.length) this.queueNodes[nodes++].position.set(cursor.x, map ? 0.55 : 0.3, cursor.z);
    }
    this.queue.visible = count > 1;
    this.queueNodes.forEach((node, i) => { node.visible = i < nodes; node.scale.setScalar(map ? 2.2 : 1); });
    if (count > 1) { this.queue.geometry.setDrawRange(0, count); this.queue.geometry.attributes.position.needsUpdate = true; this.queue.computeLineDistances(); }
    // a drive that slipped: where it was aimed, and how far short it stopped
    let slid = null, slidTick = 0;
    if (!feed) for (let i = Math.min(run.T, Math.ceil(tv)); i >= 1 && tv - i < 1.6; i--) if (run.drive[i] && run.drive[i].slip > 0.08) { slid = run.drive[i]; slidTick = i; break; }
    this.aim.visible = !!slid; this.short.visible = !!slid && tv >= slidTick;
    if (slid) {
      const a = this.P(slid.aim[0], slid.aim[1]), end = run.states[slidTick].position, b = this.P(end[0], end[1]);
      this.aim.position.set(a.x, map ? 0.55 : 0.1, a.z); this.aim.scale.setScalar(map ? 2 : 1);
      const line = this.short.geometry.attributes.position; line.setXYZ(0, a.x, 0.32, a.z); line.setXYZ(1, b.x, 0.32, b.z); line.needsUpdate = true;
    }
    // targets as known at the shown moment
    const whole = Math.floor(tv + 1e-6);
    for (const target of this.targets) {
      const plan = run.plan[target.id], sample = run.samples[target.id], known = tv >= plan.appear - 1e-6, label = feed ? target.labels.seen : target.labels.now;
      target.group.visible = label.sprite.visible = known; (feed ? target.labels.now : target.labels.seen).sprite.visible = false;
      if (!known) continue;
      const got = state.sampled_targets.includes(target.id), left = plan.deadline === null ? null : plan.deadline - whole, late = !got && left !== null && left < 0;
      const hue = got ? LIME : late ? MUTE : left !== null && left <= 3 ? RED : AMBER, id = target.id.toUpperCase();
      target.material.color.setHex(hue); target.disc.material.color.setHex(hue); target.disc.material.opacity = got ? 0.5 : 0.16;
      const fresh = plan.appear > 0 ? clamp((tv - plan.appear) / 0.5, 0, 1) : 1;      // a discovery pops up
      target.group.scale.set(map ? 1.5 : 1, fresh * (got ? 0.62 : 1), map ? 1.5 : 1);
      target.flag.rotation.y = Math.sin(wall * 2.1 + target.x) * 0.3;
      if (got) label.set(`${id} +${fmt(sample ? sample.credited : target.value)}${sample && !sample.onTime ? ' LATE' : ''}`, css(sample && !sample.onTime ? AMBER : LIME));
      else if (late) label.set(`${id} LATE ${fmt(target.value * run.lateFraction)}PT`, css(MUTE));
      else label.set(`${id} ${target.value}PT`, css(left !== null && left <= 3 ? RED : INK), left === null ? null : (plan.deadline + 1 - tv) / Math.max(1, plan.deadline + 1 - plan.appear), css(hue));
      label.sprite.position.copy(map ? this.P(target.x, target.y + 1.5, 3) : this.P(target.x, target.y, got ? 1.75 : 2.6));
    }
    // one-shot effects, as pure functions of the shown time so scrubbing works
    let pulse = 0, pulseColor = LIME, pulseAge = 0;
    for (const event of run.events) {
      const age = tv - event.tick; if (age < 0 || age > 1.6) continue;
      if (event.type === 'sample_taken') { pulse = 1 - age / 1.6; pulseColor = LIME; pulseAge = age; }
      if (event.type === 'safety_stop' || event.type === 'battery_depleted' || event.type === 'sample_failed') { pulse = 1 - age / 1.6; pulseColor = RED; pulseAge = age; }
    }
    this.pulse.visible = pulse > 0;
    if (pulse > 0) { this.pulse.position.set(p.x, 0.25, p.z); this.pulse.scale.setScalar(1 + pulseAge * 4.5); this.pulse.material.color.setHex(pulseColor); this.pulse.material.opacity = pulse; }
    this.dust.forEach((sprite, i) => {
      const age = i * 0.1 + ((wall * 1.3) % 0.1), then = feed ? pose : run.sample(tv - age * 0.9);
      sprite.visible = then.moving && !map && tv - age * 0.9 > 0;
      if (!sprite.visible) return;
      const d = this.P(then.x, then.y), jitter = hash2(i * 3.7, Math.floor(wall * 1.3 / 0.1) + i), spray = then.slip > 0.08 ? 1.7 : 1;
      sprite.position.set(d.x + (jitter - 0.5) * 1.1, 0.15 + age * 0.9 * spray, d.z + (hash2(jitter, i) - 0.5) * 1.1);
      const size = (0.16 + age * 0.55) * spray; sprite.scale.set(size, size, 1);
      sprite.material.color.setHex(then.sand ? 0xe9bd7c : 0xd08e62); sprite.material.opacity = 0.9 * (1 - age);
    });
    return { pose, state, tv, pending: pending.length, apart, slip: slipping ? pose.slip : 0 };
  }
}

// ---------------------------------------------------------------- screens
const renderer = new THREE.WebGLRenderer({ canvas: $('#gl'), antialias: true, powerPreference: 'high-performance' });
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));   // the scene is flat-shaded; text is DOM and stays sharp
renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFShadowMap;
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.setClearColor(0x0b0807, 1);
const scenes = new Map();
const sceneOf = run => { if (!scenes.has(run)) scenes.set(run, new MarsScene(run)); return scenes.get(run); };

class Screen {
  constructor(kind, run) {
    this.kind = kind; this.run = run; this.scene = sceneOf(run);
    this.camera = kind === 'map' ? new THREE.OrthographicCamera(-1, 1, 1, -1, 1, 400) : new THREE.PerspectiveCamera(kind === 'wide' ? 40 : 52, 1, 0.3, 1600);
    this.eye = null; this.look = new THREE.Vector3(); this.heading = null;
  }
  frame(info, aspect, dt, wall) {
    const camera = this.camera, world = this.run.world, pose = info.pose, p = this.scene.P(pose.x, pose.y, 0);
    if (this.kind === 'map') {
      // frame the part of the map this mission uses
      const b = this.run.bounds, c = this.scene.P((b.x0 + b.x1) / 2, (b.y0 + b.y1) / 2);
      let hy = (b.y1 - b.y0) / 2, hx = (b.x1 - b.x0) / 2;
      if (hx / hy < aspect) hx = hy * aspect; else hy = hx / aspect;
      Object.assign(camera, { left: -hx, right: hx, top: hy, bottom: -hy }); camera.position.set(c.x, 200, c.z); camera.up.set(0, 0, -1); camera.lookAt(c.x, 0, c.z);
    } else if (this.kind === 'wide') {
      // a drone shot that keeps the rover and the base in frame
      const base = this.scene.P(world.base[0], world.base[1]), focus = new THREE.Vector3(lerp(base.x, p.x, 0.62), 0, lerp(base.z, p.z, 0.62));
      if (!this.eye) this.look.copy(focus);
      this.look.lerp(focus, 1 - Math.exp(-dt * 1.4));
      const a = -0.72 + Math.sin(wall * 0.06) * 0.2, r = 27;
      this.eye = new THREE.Vector3(this.look.x + Math.sin(a) * r, 15.5, this.look.z + Math.cos(a) * r);
      camera.position.copy(this.eye); camera.lookAt(this.look);
    } else {
      // chase camera: behind and above. The delayed feed is a still per packet, so its camera does not drift.
      const still = this.kind === 'feed', target = rad(pose.heading);
      if (this.heading === null) this.heading = target;
      this.heading += Math.atan2(Math.sin(target - this.heading), Math.cos(target - this.heading)) * (still ? 1 : 1 - Math.exp(-dt * 1.6));
      const h = this.heading + (still ? 0 : Math.sin(wall * 0.13) * 0.25) + 0.5;
      const want = new THREE.Vector3(p.x - Math.cos(h) * 8.4, 4.1, p.z + Math.sin(h) * 8.4);
      const lander = this.scene.lander.position, away = Math.hypot(want.x - lander.x, want.z - lander.z);
      if (away < 7.5) { const k = 7.5 / Math.max(away, 0.01); want.x = lander.x + (want.x - lander.x) * k; want.z = lander.z + (want.z - lander.z) * k; want.y = 5.6; }
      const at = new THREE.Vector3(p.x, 1.05, p.z);
      if (!this.eye || still) { this.eye = want.clone(); this.look.copy(at); }
      this.eye.lerp(want, 1 - Math.exp(-dt * 2.6)); this.look.lerp(at, 1 - Math.exp(-dt * 5));
      camera.position.copy(this.eye); camera.lookAt(this.look);
    }
    if (camera.isPerspectiveCamera) { camera.aspect = aspect; MAT.ghost.opacity = 0.1 + 0.3 * smooth(4, 11, camera.position.distanceTo(this.scene.ghost.position)); }
    camera.updateProjectionMatrix();
  }
}

// ---------------------------------------------------------------- interface
const stage = $('#stage'), scrub = $('#scrub'), playButton = $('#play'), clock = $('#clock b');
const SPEEDS = [[0.75, '½×'], [1.5, '1×'], [3, '2×'], [6, '4×']];
const state = { t: 0, playing: false, speed: 1, solo: null, mode: 'mission', mission: MISSIONS[0], run: MISSIONS[0].featuredRun, screens: [], wall: 0 };
const TOOLS = [['rules', 'read'], ['map', 'read'], ['telemetry_log', 'read'], ['uplink', 'send ≤5'], ['advance', 'wait ≤5'], ['shell', 'own code']];

function describeCall(call) {
  if (call.kind === 'shell') { const text = (call.arguments.command || JSON.stringify(call.arguments)).replace(/\s+/g, ' '); return ['shell', text.length > 90 ? text.slice(0, 88) + '…' : text]; }
  if (call.kind === 'other') return [call.tool, `tried “${call.arguments.tool || call.tool}”: no such tool`];
  if (call.tool === 'uplink') {
    const list = (call.arguments.commands || []).map(c => c.action === 'drive' ? `drive ${(+c.heading_deg).toFixed(0)}° ${(+c.metres).toFixed(2)}m` : c.action).join(' · ');
    const ticks = call.summary.execute_ticks || [];
    return ['uplink', call.ok ? `${list}  → lands t${ticks[0]}${ticks.length > 1 ? '–' + ticks[ticks.length - 1] : ''}` : `${list}  ✗ ${call.error}`];
  }
  if (call.tool === 'advance') {
    if (!call.ok) return ['advance', `✗ ${call.error}`];
    const packets = call.summary.packet_ticks || [];
    return ['advance', `wait ${call.arguments.ticks ?? 1} → t${call.tick_after}${packets.length ? ` · telemetry t${packets[0]}${packets.length > 1 ? '–' + packets[packets.length - 1] : ''}` : ' · no telemetry yet'}`];
  }
  if (call.tool === 'telemetry_log') return ['telemetry_log', `read ${call.summary.packets ?? 'all'} packets`];
  return [call.tool, call.tool === 'rules' ? 'read the rules' : 'read the map'];
}
function toastFor(run, e) {
  if (e.type === 'sample_taken') { const s = run.samples[e.target_id], late = s && !s.onTime; return [late ? 'warn' : 'good', `SAMPLE ${e.target_id.toUpperCase()} +${fmt(s ? s.credited : run.value[e.target_id])}${late ? ' · LATE' : ''}`]; }
  if (e.type === 'sample_failed') return ['bad', 'SAMPLE MISSED · NOTHING IN RANGE'];
  if (e.type === 'target_discovered') return ['info', `NEW TARGET ${e.target.id.toUpperCase()} · ${e.target.value} PT · DUE T${e.target.deadline_tick}`];
  if (e.type === 'battery_depleted') return ['bad', 'BATTERY EMPTY'];
  if (e.type === 'safety_stop') return ['bad', 'SAFETY STOP · QUEUE CLEARED'];
  if (e.type === 'doomed') return ['bad', 'CANNOT FINISH HOME ALIVE'];
  return null;
}
function verdict(run) {
  const r = run.result, last = run.states[run.T].position, d = Math.hypot(last[0] - run.world.base[0], last[1] - run.world.base[1]);
  if (!r.alive) return ['bad', 'ROVER LOST', `battery empty ${r.at_base ? 'on the base pad' : d.toFixed(1) + ' m from base'} · ${fmt(r.sampled_value)} pt of samples count for nothing`];
  if (!r.at_base) return ['warn', 'STRANDED', `alive ${d.toFixed(1)} m from base · samples count half`];
  return ['good', 'HOME', `${fmt(r.raw_score)} of ${fmt(r.max_available_value)} pt banked`];
}
// The agent's closing words: the first paragraph, and the one where it says what went wrong.
function closingWords(run) {
  const parts = run.report.split(/\n\s*\n/).map(s => s.replace(/\*\*/g, '').replace(/\s+/g, ' ').trim()).filter(Boolean);
  const wrong = parts.slice(1).find(s => /^(what went wrong|what i missed|missed)/i.test(s));
  return [parts[0], wrong].filter(Boolean).map(s => s.length > 330 ? s.slice(0, 328) + '…' : s);
}

function glScreen(kind, run, title, sub) {
  const el = document.createElement('section');
  el.className = `view ${kind}`;
  el.innerHTML = `<div class="name"><b>${title}</b><span>${sub}</span></div>
    ${kind === 'map' ? '' : `<div class="hud"><div class="bat"><div class="row"><span class="cap">battery</span><b></b></div><div class="bar"><i class="fill"></i><i class="need"></i></div></div>
      <div class="carry"><b></b><span>pt carried</span></div></div><div class="slip"></div>`}
    <div class="toast"></div><div class="end"><b></b><em></em><span></span></div>`;
  stage.appendChild(el);
  const screen = new Screen(kind, run); screen.el = el; screen.shown = {};
  return screen;
}
function consolePanel(run) {
  const el = document.createElement('section');
  el.className = 'view panel';
  el.innerHTML = `<div class="console">
    <div class="who"><b>${run.label}</b><span>${run.sub}</span><div class="score">score<b>—</b></div></div>
    <div class="keys">${TOOLS.map(([name, hint]) => `<div class="key${name === 'shell' ? ' own' : ''}" data-tool="${name}"><b>${name}</b><span>${hint}</span><em>0</em></div>`).join('')}</div>
    <canvas class="lane"></canvas><div class="log"></div></div>`;
  stage.appendChild(el);
  return { kind: 'console', run, el, shown: {}, canvas: $('canvas', el) };
}
function build() {
  const mission = state.mission, run = state.run, compare = state.mode === 'compare';
  stage.innerHTML = '';
  scrub.max = mission.T; $('#clock span').textContent = `/${mission.T}`; $('#mname').textContent = mission.name;
  $('#cmp').classList.toggle('on', compare);
  $('#runs').className = compare ? 'all' : '';
  $('#runs').innerHTML = mission.runs.map((r, i) => `<button data-run="${r.id}" class="${!compare && r === run ? 'on' : ''}"><i>${i + 1}</i>${r.short}</button>`).join('');
  for (const button of $('#runs').children) button.onclick = () => { state.run = mission.runs.find(r => r.id === button.dataset.run); state.mode = 'mission'; build(); };
  state.screens = compare
    ? mission.runs.slice(0, 4).map(r => glScreen('wide', r, r.short, r.kind === 'model' ? r.label : 'scripted controller'))
    : [glScreen('live', run, 'Mars', 'now'), glScreen('feed', run, 'Earth', ''), glScreen('map', run, 'Map', 'north up'), consolePanel(run)];
  const solo = compare ? null : state.solo;
  stage.classList.toggle('solo', solo !== null);
  state.screens.forEach((screen, i) => {
    screen.el.classList.toggle('solo', i === solo);
    if (!compare && screen.kind !== 'console') screen.el.ondblclick = () => { state.solo = state.solo === i ? null : i; build(); };
  });
  drawMarks();
}
// Jump to the next or previous thing that happened in this run.
function jumpEvent(direction) {
  const ticks = [...new Set(state.run.events.map(e => e.tick))].sort((x, y) => x - y);
  const next = direction > 0 ? ticks.find(t => t > state.t + 1e-6) : [...ticks].reverse().find(t => t < state.t - 1e-6);
  setPlaying(false); seek(next === undefined ? (direction > 0 ? state.mission.T : 0) : next);
}
function fitUi() { document.documentElement.style.setProperty('--s', clamp(Math.min(window.innerWidth / 1500, window.innerHeight / 820), 0.8, 1.8).toFixed(3)); }
function drawMarks() {
  const canvas = $('#marks'), rect = canvas.getBoundingClientRect(), dpr = window.devicePixelRatio || 1;
  if (canvas.width !== Math.round(rect.width * dpr) || canvas.height !== Math.round(rect.height * dpr)) { canvas.width = Math.round(rect.width * dpr); canvas.height = Math.round(rect.height * dpr); }
  const g = canvas.getContext('2d'); g.setTransform(dpr, 0, 0, dpr, 0, 0); g.clearRect(0, 0, rect.width, rect.height);
  const w = rect.width, mid = rect.height / 2, T = state.mission.T, x = t => 6 + (w - 12) * t / T, t = state.t;
  g.fillStyle = 'rgba(243,234,217,.16)'; g.fillRect(6, mid - 2, w - 12, 4);
  g.fillStyle = css(INK); g.fillRect(6, mid - 2, x(t) - 6, 4);
  if (state.mode === 'mission') {
    const run = state.run;
    for (const c of run.calls) if (c.tool === 'uplink') { g.fillStyle = css(c.ok ? AMBER : RED); g.fillRect(x(c.tick) - 1, mid + 5, 2, 6); }
    for (const e of run.events) {
      if (e.tick > t + 1e-6) continue;                       // the timeline does not give the ending away
      const ex = x(e.tick);
      if (e.type === 'sample_taken') { g.fillStyle = css(run.samples[e.target_id] && !run.samples[e.target_id].onTime ? AMBER : LIME); g.fillRect(ex - 3, mid - 12, 6, 6); }
      else if (e.type === 'sample_failed' || e.type === 'battery_depleted' || e.type === 'safety_stop') { g.strokeStyle = css(RED); g.lineWidth = 2; g.beginPath(); g.moveTo(ex - 3, mid - 12); g.lineTo(ex + 3, mid - 6); g.moveTo(ex + 3, mid - 12); g.lineTo(ex - 3, mid - 6); g.stroke(); }
      else if (e.type === 'doomed') { g.fillStyle = css(RED); g.fillRect(ex - 1, mid - 13, 2, 26); }
    }
  }
  g.fillStyle = css(AMBER); g.fillRect(x(t) - 2, mid - 9, 4, 18);
}
function setText(holder, key, value, node) { if (holder.shown[key] !== value) { holder.shown[key] = value; node.textContent = value; } }
function updateScreen(screen, info, t) {
  const run = screen.run, el = screen.el, tv = info.tv, feed = screen.kind === 'feed';
  if (feed) {
    setText(screen, 'sub', `frame from tick ${Math.floor(tv)} · ${Math.floor(t) - Math.floor(tv)} ticks old`, $('.name span', el));
    if (screen.shown.frame !== Math.floor(tv)) { screen.shown.frame = Math.floor(tv); el.classList.remove('ping'); void el.offsetWidth; if (t > 0.05) el.classList.add('ping'); }
  }
  if (screen.kind !== 'map') {
    const battery = info.pose.battery, need = run.need(tv, info.pose.x, info.pose.y), doomed = info.state.alive && battery < need, max = run.cfg.initial_battery, bat = $('.bat', el);
    setText(screen, 'bat', battery.toFixed(0), $('.row b', bat));
    setText(screen, 'cap', !info.state.alive ? 'battery empty' : doomed ? (feed ? 'low estimated reserve' : 'cannot finish home alive') : 'battery', $('.cap', bat));
    if (screen.shown.doomed !== (doomed || !info.state.alive)) { screen.shown.doomed = doomed || !info.state.alive; bat.classList.toggle('doomed', screen.shown.doomed); }
    $('.fill', bat).style.width = `${clamp(100 * battery / max, 0, 100)}%`;
    $('.need', bat).style.left = `${clamp(100 * need / max, 0, 100)}%`;
    setText(screen, 'carry', fmt(run.carried(tv)), $('.carry b', el));
    const slip = info.slip > 0 ? `wheels slipping ${Math.round(info.slip * 100)}%` : '';
    if (screen.shown.slip !== slip) { screen.shown.slip = slip; const node = $('.slip', el); node.classList.toggle('on', !!slip); if (slip) node.textContent = slip; }
  }
  // the latest news on this screen, for a couple of ticks
  let news = [], newsTick = -1;
  for (const event of run.events) { const age = tv - event.tick; if (age < -1e-6 || age >= 2.4 || (feed && event.type === 'doomed')) continue; const text = toastFor(run, event); if (!text) continue; if (event.tick !== newsTick) { news = []; newsTick = event.tick; } news.push(text); }
  if (screen.kind === 'map' || (t >= run.T - 0.01 && !feed)) news = [];
  const node = $('.toast', el), key = news.map(n => n[1]).join('|');
  if (screen.shown.toast !== key) { screen.shown.toast = key; node.classList.toggle('show', news.length > 0); if (news.length) node.innerHTML = news.map(([tone, text]) => `<div class="${tone}">${esc(text)}</div>`).join(''); }
  const finished = t >= run.T - 0.01 && (screen.kind === 'live' || screen.kind === 'wide');
  if (screen.shown.done !== finished) {
    screen.shown.done = finished;
    const end = $('.end', el), [tone, word, why] = verdict(run);
    end.className = `end ${tone}${finished ? ' show' : ''}`;
    $('b', end).textContent = word; $('em', end).textContent = `score ${run.reward.toFixed(2)}`; $('span', end).textContent = why;
  }
}
function updateConsole(panel, t) {
  const run = panel.run, el = panel.el;
  const made = run.calls.filter(c => c.at <= t), latest = made[made.length - 1], slot = c => c.kind === 'mcp' ? c.tool : 'shell';
  const counts = {}; for (const c of made) counts[slot(c)] = (counts[slot(c)] || 0) + 1;
  for (const node of el.querySelectorAll('.key')) {
    const name = node.dataset.tool, hit = latest && slot(latest) === name && (t - latest.at < 0.5 || (latest.tool === 'advance' && t < latest.tick_after));
    node.classList.toggle('hit', !!hit && latest.ok); node.classList.toggle('fail', !!hit && !latest.ok);
    setText(panel, 'n' + name, String(counts[name] || 0), $('em', node));
  }
  const finished = t >= run.T - 0.01;
  const logKey = made.length + (finished ? 'f' : '');
  if (panel.shown.log !== logKey) {
    panel.shown.log = logKey;
    const lines = [];
    for (const c of made.slice(-14)) {
      if (c.say) lines.push(`<div class="said">“${esc(c.say)}”</div>`);
      const [name, text] = describeCall(c);
      lines.push(`<div class="${c.ok ? '' : 'err'}"><u>t${String(c.tick).padStart(2, '0')}</u><b>${esc(name)}</b>${esc(text)}</div>`);
    }
    const words = finished && run.report ? closingWords(run) : [];
    $('.log', el).innerHTML = words.length ? `<div class="head">${esc(run.label)}, in its own words</div>` + words.map(w => `<div class="said">${esc(w)}</div>`).join('') : lines.join('');
  }
  setText(panel, 'score', finished ? run.reward.toFixed(2) : '—', $('.score b', el));
  $('.score b', el).style.color = finished ? (run.reward >= 0.75 ? 'var(--lime)' : run.reward > 0 ? 'var(--amber)' : 'var(--red)') : '';
  // the signal lane: commands travelling out, telemetry travelling back
  const canvas = panel.canvas, rect = canvas.getBoundingClientRect(), dpr = window.devicePixelRatio || 1;
  if (canvas.width !== Math.round(rect.width * dpr)) { canvas.width = Math.round(rect.width * dpr); canvas.height = Math.round(rect.height * dpr); }
  const g = canvas.getContext('2d'); g.setTransform(dpr, 0, 0, dpr, 0, 0); g.clearRect(0, 0, rect.width, rect.height);
  const w = rect.width, h = rect.height, size = h * 0.34, x0 = size * 3.6, x1 = w - size * 3.2, up = h * 0.27, down = h * 0.73;
  g.font = `700 ${size}px ${FONT}`; g.textBaseline = 'middle'; g.textAlign = 'left';
  g.fillStyle = css(INK); g.fillText('EARTH', 0, h / 2 + 2); g.textAlign = 'right'; g.fillText('MARS', w, h / 2 + 2);
  g.fillStyle = 'rgba(243,234,217,.14)'; g.fillRect(x0, up - 1, x1 - x0, 2); g.fillRect(x0, down - 1, x1 - x0, 2);
  g.font = `700 ${size * 0.74}px ${FONT}`; g.textAlign = 'center';
  g.fillStyle = 'rgba(243,234,217,.5)'; g.fillText(`COMMANDS  →      ${run.K} TICKS EACH WAY      ←  TELEMETRY`, (x0 + x1) / 2, h / 2 + 2);
  g.fillStyle = css(AMBER);
  for (const c of run.commands) { const f = (t - c.sent) / (c.exec - c.sent); if (f < 0 || f > 1 || t >= c.until) continue; const r = c.action === 'sample' ? 6 : 4.5; g.fillRect(lerp(x0, x1, f) - r, up - r, r * 2, r * 2); }
  g.fillStyle = css(ICE);
  for (let s = Math.max(1, Math.floor(t - run.K)); s <= Math.floor(t); s++) { const f = (t - s) / Math.max(run.K, 0.001); if (f < 0 || f > 1) continue; g.fillRect(lerp(x1, x0, f) - 4, down - 4, 8, 8); }
}

// ---------------------------------------------------------------- title screen, loop and input
const title = $('#title');
$('#titleK').textContent = MISSIONS[0].K;
$('#missions').innerHTML = MISSIONS.map((m, i) => `<li data-i="${i}"><i>${i + 1}</i><b>${esc(m.name)}</b><em>${esc(m.profile.replace('_', ' + '))} · seed ${m.seed} · ${m.ticks} ticks</em><p>${esc(m.brief)}</p></li>`).join('');
function markMission() { [...$('#missions').children].forEach((li, i) => li.classList.toggle('on', MISSIONS[i] === state.mission)); }
function showTitle(on) { title.classList.toggle('gone', !on); if (on) { setPlaying(false); markMission(); } }
function setPlaying(on) { state.playing = on; playButton.textContent = on ? '❚❚' : '▶'; }
function seek(t) { state.t = clamp(t, 0, state.mission.T); }
function startMission(mission, run = mission.featuredRun) { state.mission = mission; state.run = run; state.mode = 'mission'; seek(0); build(); showTitle(false); setPlaying(true); }
function setSpeed(i) { state.speed = clamp(i, 0, SPEEDS.length - 1); $('#speed').textContent = SPEEDS[state.speed][1]; }
for (const li of $('#missions').children) li.onclick = () => startMission(MISSIONS[+li.dataset.i]);
playButton.onclick = () => { if (!state.playing && state.t >= state.mission.T - 0.01) seek(0); setPlaying(!state.playing); };
scrub.oninput = () => { setPlaying(false); seek(+scrub.value); };
$('#menu').onclick = () => showTitle(true);
$('#speed').onclick = () => setSpeed((state.speed + 1) % SPEEDS.length);
$('#cmp').onclick = () => { state.mode = state.mode === 'mission' ? 'compare' : 'mission'; build(); };
addEventListener('keydown', e => {
  const onTitle = !title.classList.contains('gone'), n = MISSIONS.length, at = MISSIONS.indexOf(state.mission);
  if (onTitle) {
    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); startMission(state.mission); }
    else if (e.key === 'ArrowDown' || e.key === 'ArrowUp' || e.key === 'n' || e.key === 'N') { state.mission = MISSIONS[(at + (e.key === 'ArrowUp' ? n - 1 : 1)) % n]; state.run = state.mission.featuredRun; seek(0); build(); markMission(); }
    else if (/^[1-9]$/.test(e.key) && MISSIONS[e.key - 1]) startMission(MISSIONS[e.key - 1]);
    else if (e.key === 'Escape') showTitle(false);
    else if (e.key === 'f' || e.key === 'F') toggleFull();
    return;
  }
  if (e.key === ' ') { e.preventDefault(); playButton.click(); }
  else if (e.key === 'ArrowRight') { setPlaying(false); seek(Math.floor(state.t + 1e-6) + 1); }
  else if (e.key === 'ArrowLeft') { setPlaying(false); seek(Math.ceil(state.t - 1e-6) - 1); }
  else if (e.key === 'm' || e.key === 'M') $('#cmp').click();
  else if (e.key === 'n' || e.key === 'N') startMission(MISSIONS[(at + 1) % n]);
  else if (e.key === 'f' || e.key === 'F') toggleFull();
  else if (e.key === 'Escape') showTitle(true);
  else if (e.key === '-' || e.key === '=') setSpeed(state.speed + (e.key === '=' ? 1 : -1));
  else if (e.key === ',' || e.key === '.') jumpEvent(e.key === '.' ? 1 : -1);
  else if (e.key === 'z' || e.key === 'Z') { state.solo = state.solo === null ? 0 : state.solo >= 2 ? null : state.solo + 1; state.mode = 'mission'; build(); }
  else if (/^[1-4]$/.test(e.key) && state.mission.runs[e.key - 1]) { state.run = state.mission.runs[e.key - 1]; state.mode = 'mission'; build(); }
});
function toggleFull() { if (document.fullscreenElement) document.exitFullscreen(); else document.documentElement.requestFullscreen(); }
addEventListener('resize', fitUi);
fitUi(); markMission();
window.LIGHTLAG = { state, seek, setPlaying, build, startMission, showTitle, MISSIONS };   // for checks from the browser console

let last = performance.now();
function frame(now) {
  const dt = Math.min(0.1, (now - last) / 1000), T = state.mission.T; last = now; state.wall += dt;
  if (state.playing) { state.t += dt * SPEEDS[state.speed][0]; if (state.t >= T) { state.t = T; setPlaying(false); if (state.loop) setTimeout(() => { seek(0); setPlaying(true); }, 8000); } }
  const t = state.t, width = window.innerWidth, height = window.innerHeight;
  if (renderer.domElement.width !== Math.round(width * renderer.getPixelRatio()) || renderer.domElement.height !== Math.round(height * renderer.getPixelRatio())) renderer.setSize(width, height, false);
  renderer.setScissorTest(false); renderer.setViewport(0, 0, width, height); renderer.clear();
  renderer.setScissorTest(true);
  for (const screen of state.screens) {
    if (screen.kind === 'console') { updateConsole(screen, t); continue; }
    const rect = screen.el.getBoundingClientRect();
    if (rect.width < 4 || rect.height < 4) continue;
    const info = screen.scene.apply(screen.kind, t, state.wall);
    screen.frame(info, rect.width / rect.height, dt, state.wall);
    screen.scene.fitLabels(screen.camera, rect.height);
    renderer.setViewport(rect.left, height - rect.bottom, rect.width, rect.height);
    renderer.setScissor(rect.left, height - rect.bottom, rect.width, rect.height);
    renderer.render(screen.scene.scene, screen.camera);
    updateScreen(screen, info, t);
  }
  const shownTick = String(Math.floor(t)).padStart(2, '0');
  if (clock.textContent !== shownTick) clock.textContent = shownTick;
  scrub.value = t; drawMarks();
  requestAnimationFrame(frame);
}
build();
if (location.hash === '#auto') { state.loop = true; setTimeout(() => startMission(state.mission), 1800); }
requestAnimationFrame(frame);
