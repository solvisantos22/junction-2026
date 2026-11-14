// Lightlag Traverse · every recorded run of one long mission, on the ground it was driven on.
// One file, no build step; three.js is the only dependency. The runs and the height grid are
// window.LIGHTLAG_TRAVERSE (see viewer/build_traverse.py). The rover, the lander, the colours and
// the controls are the ghost demo's (viewer/ghosts/app.js), so the pages share one look.
import * as THREE from 'three';

if (document.readyState === 'loading') await new Promise(resolve => document.addEventListener('DOMContentLoaded', resolve, { once: true }));

const DATA = window.LIGHTLAG_TRAVERSE, WORLD = DATA.world, CFG = DATA.config, T = CFG.ticks;
const $ = (selector, root = document) => root.querySelector(selector);
const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
const lerp = (a, b, t) => a + (b - a) * t;
const smooth = (a, b, x) => { const t = clamp((x - a) / (b - a), 0, 1); return t * t * (3 - 2 * t); };
const TAU = Math.PI * 2, rad = THREE.MathUtils.degToRad;
const fmt = n => String(+(+n).toFixed(2));
const two = n => (+n).toFixed(2);
const esc = text => String(text).replace(/&/g, '&amp;').replace(/</g, '&lt;');
// Gold is the reference, ice is the run being followed, shade is every other run.
const INK = 0xf3ead9, GOLD = 0xffb224, ICE = 0x9fd8ff, RED = 0xff4a2f, LIME = 0xb6e35a, MUTE = 0x8a7466, LINE = 0x1b1310, SHADE = 0x1a100c;
const css = n => '#' + n.toString(16).padStart(6, '0');
const FONT = '"DIN Condensed", "Avenir Next Condensed", "Roboto Condensed", "Arial Narrow", sans-serif';

// ---------------------------------------------------------------- noise
const ih = (a, b) => { let h = Math.imul(a, 374761393) + Math.imul(b, 668265263) | 0; h = Math.imul(h ^ (h >>> 13), 1274126177); return ((h ^ (h >>> 16)) >>> 0) / 4294967296; };
function vnoise(x, y) {
  const xi = Math.floor(x), yi = Math.floor(y), xf = x - xi, yf = y - yi;
  const u = xf * xf * (3 - 2 * xf), v = yf * yf * (3 - 2 * yf);
  return lerp(lerp(ih(xi, yi), ih(xi + 1, yi), u), lerp(ih(xi, yi + 1), ih(xi + 1, yi + 1), u), v);
}
function fbm(x, y, octaves = 4) {
  let sum = 0, amp = 0.5, norm = 0;
  for (let i = 0; i < octaves; i++) { sum += amp * vnoise(x, y); norm += amp; x *= 2.03; y *= 2.03; amp *= 0.5; }
  return sum / norm;
}

// ---------------------------------------------------------------- the ground
// The simulator's height grid: H[j * NX + i] is the height in metres at x = i * CELL (east), y = j * CELL (north).
const NX = WORLD.nx, NY = WORLD.ny, CELL = WORLD.cell, WIDTH = (NX - 1) * CELL, DEPTH = (NY - 1) * CELL;
const H = Float32Array.from(WORLD.elevation_cm, v => v / 100);
const EXAG = 2.75;                     // heights are drawn this many times too tall, or the relief would not read
const CLASS = new Uint8Array((NX - 1) * (NY - 1));     // per grid cell: 0 regolith, 1 sand, 2 rocks, 3 bedrock
WORLD.terrain.forEach((row, j) => { for (let i = 0; i < NX - 1; i++) CLASS[j * (NX - 1) + i] = Math.max(0, 'rskb'.indexOf(row[i])); });
const GROUND_NAMES = ['regolith', 'sand', 'a rock field', 'bedrock'];
// Markers (rovers, flags, the lander) are drawn bigger than life from above, or they would be specks; life-size when chasing.
const S_MAP = Math.max(WIDTH, DEPTH * 1.45) / 92, S_CHASE = 1;

// The drawn ground: each grid cell is two flat triangles, split along its flatter diagonal.
function drawnHeight(x, y) {
  const fx = clamp(x / CELL, 0, NX - 1), fy = clamp(y / CELL, 0, NY - 1);
  const i = Math.min(NX - 2, Math.floor(fx)), j = Math.min(NY - 2, Math.floor(fy)), tx = fx - i, ty = fy - j, v = j * NX + i;
  const a = H[v], b = H[v + 1], d = H[v + NX], c = H[v + NX + 1];
  if (Math.abs(a - c) <= Math.abs(b - d)) return tx >= ty ? a + (b - a) * tx + (c - b) * ty : a + (c - d) * tx + (d - a) * ty;
  return tx + ty <= 1 ? a + (b - a) * tx + (d - a) * ty : c + (d - c) * (1 - tx) + (b - c) * (1 - ty);
}
// The slope the simulator reads at a point: the gradient of the bilinear surface (lightlag_traverse/surface.py).
function slopeAt(x, y) {
  const fx = x / CELL, fy = y / CELL, i = clamp(Math.floor(fx), 0, NX - 2), j = clamp(Math.floor(fy), 0, NY - 2), tx = fx - i, ty = fy - j, v = j * NX + i;
  const a = H[v], b = H[v + 1], d = H[v + NX], c = H[v + NX + 1];
  return Math.hypot(((b - a) * (1 - ty) + (c - d) * ty) / CELL, ((d - a) * (1 - tx) + (c - b) * tx) / CELL);
}
const classAt = (x, y) => CLASS[clamp(Math.floor(y / CELL), 0, NY - 2) * (NX - 1) + clamp(Math.floor(x / CELL), 0, NX - 2)];
// Beyond the map there is no data: rolling ground and far mesas for the eye, grown out of the map's own edge.
function groundHeight(x, y) {
  const cx = clamp(x, 0, WIDTH), cy = clamp(y, 0, DEPTH), away = Math.hypot(x - cx, y - cy);
  if (away < 1e-9) return drawnHeight(x, y);
  // the edge's own height, taken over a longer stretch of it the further out, so its bumps do not run on as ridges
  const tx = -(y - cy) * 0.5, ty = (x - cx) * 0.5;                    // along the edge, half as far as the point is from it
  let edge = 0;
  for (const [step, share] of [[-2, 1], [-1, 2], [0, 3], [1, 2], [2, 1]]) edge += share / 9 * drawnHeight(clamp(cx + tx * step, 0, WIDTH), clamp(cy + ty * step, 0, DEPTH));
  const dunes = (fbm(x * 0.006 + 40, y * 0.006 + 7, 3) - 0.5) * 12;
  const mesas = smooth(380, 1100, away) * (4 + 46 * Math.pow(fbm(x * 0.0017 + 3, y * 0.0017 + 9, 3), 1.6));
  return lerp(edge, dunes + mesas, smooth(0, 110, away));
}
// Map metres to the scene: x east, y north, standing on the drawn ground.
const P = (x, y, lift = 0) => new THREE.Vector3(x - WIDTH / 2, drawnHeight(x, y) * EXAG + lift, DEPTH / 2 - y);

const mix4 = (field, v, tx, ty) => (field[v] * (1 - tx) + field[v + 1] * tx) * (1 - ty) + (field[v + NX] * (1 - tx) + field[v + NX + 1] * tx) * ty;
const RUST = [[143, 65, 38], [163, 75, 43], [179, 86, 49], [194, 99, 58]];
// The ground's colours, painted once: regolith rust, sand paler with ripples, rock fields darker and strewn with
// stones, bedrock lighter and in slabs, and ground too steep to drive as dark, layered cliff.
function paintGround() {
  const cols = NX - 1, rows = NY - 1, ppc = clamp(Math.floor(2048 / Math.max(cols, rows)), 4, 16), w = cols * ppc, h = rows * ppc;
  const canvas = document.createElement('canvas'); canvas.width = w; canvas.height = h;
  const g = canvas.getContext('2d'), image = g.createImageData(w, h), out = image.data;
  const safe = CFG.safe_share * CFG.max_tilt, weight = [0, 0, 0, 0];
  let low = Infinity, high = -Infinity; for (const v of H) { low = Math.min(low, v); high = Math.max(high, v); }
  // slow tones, worked out once per grid vertex and blended between
  const tone = new Float32Array(NX * NY), bend = new Float32Array(NX * NY);
  for (let j = 0, v = 0; j < NY; j++) for (let i = 0; i < NX; i++, v++) { tone[v] = fbm(i * CELL * 0.02 + 5, j * CELL * 0.02 + 2, 3); bend[v] = fbm(i * CELL * 0.03 + 9, j * CELL * 0.03 + 4, 2) * 9; }
  // the simulator's slope at the middle of each cell; between the middles it is blended, so that cliffs have ground's outline and not the grid's
  const east = new Float32Array(cols * rows), north = new Float32Array(cols * rows);
  for (let j = 0, n = 0; j < rows; j++) for (let i = 0; i < cols; i++, n++) {
    const v = j * NX + i, a = H[v], b = H[v + 1], d = H[v + NX], c = H[v + NX + 1];
    east[n] = (b - a + c - d) / (2 * CELL); north[n] = (d - a + c - b) / (2 * CELL);
  }
  for (let py = 0, o = 0; py < h; py++) {
    const y = (1 - (py + 0.5) / h) * DEPTH, fy = y / CELL, j = Math.min(rows - 1, Math.floor(fy)), ty = fy - j;
    const j0 = Math.floor(fy - 0.5), fv = fy - 0.5 - j0, ja = clamp(j0, 0, rows - 1) * cols, jb = clamp(j0 + 1, 0, rows - 1) * cols;
    for (let px = 0; px < w; px++, o += 4) {
      const x = (px + 0.5) / w * WIDTH, fx = x / CELL, i = Math.min(cols - 1, Math.floor(fx)), tx = fx - i, v = j * NX + i;
      const a = H[v], b = H[v + 1], d = H[v + NX], c = H[v + NX + 1];
      const height = (a * (1 - tx) + b * tx) * (1 - ty) + (d * (1 - tx) + c * tx) * ty;
      const i0 = Math.floor(fx - 0.5), fu = fx - 0.5 - i0, ia = clamp(i0, 0, cols - 1), ib = clamp(i0 + 1, 0, cols - 1);
      const slope = Math.hypot((east[ja + ia] * (1 - fu) + east[ja + ib] * fu) * (1 - fv) + (east[jb + ia] * (1 - fu) + east[jb + ib] * fu) * fv,
        (north[ja + ia] * (1 - fu) + north[ja + ib] * fu) * (1 - fv) + (north[jb + ia] * (1 - fu) + north[jb + ib] * fu) * fv);
      // the class of the nearest cells, with a wobble so that borders run like ground and not like a grid
      const c00 = CLASS[ja + ia], c10 = CLASS[ja + ib], c01 = CLASS[jb + ia], c11 = CLASS[jb + ib];
      let cls = c00;
      if (c00 !== c10 || c00 !== c01 || c00 !== c11) {
        weight[0] = weight[1] = weight[2] = weight[3] = 0;
        weight[c00] += (1 - fu) * (1 - fv); weight[c10] += fu * (1 - fv); weight[c01] += (1 - fu) * fv; weight[c11] += fu * fv;
        let best = -9;
        for (let k = 0; k < 4; k++) { if (!weight[k]) continue; const score = weight[k] + (vnoise(x * 0.4 + 31 * k, y * 0.4 + 17 * k) - 0.5) * 0.4; if (score > best) { best = score; cls = k; } }
      }
      const grain = ih(px, py), wide = mix4(tone, v, tx, ty);
      let r, gg, bb;
      if (cls === 0) {                                             // regolith: bands of rust
        const n = wide + (grain - 0.5) * 0.05, band = RUST[n < 0.42 ? 0 : n < 0.5 ? 1 : n < 0.58 ? 2 : 3];
        r = band[0]; gg = band[1]; bb = band[2];
      } else if (cls === 1) {                                      // sand: paler, with a hint of ripple crests that comes and goes
        const ripple = Math.sin((x * 0.5 + y * 0.87) * (TAU / 3.1) + mix4(bend, v, tx, ty)) * smooth(0.3, 0.62, vnoise(x * 0.035 + 3, y * 0.035 + 8)), k = 0.95 + 0.1 * wide;
        const crest = ripple > 0.45 ? 1 : ripple < -0.45 ? -1 : 0;
        r = (219 + crest * 11) * k; gg = (162 + crest * 15) * k; bb = (91 + crest * 15) * k;
      } else if (cls === 2) {                                      // rock field: darker ground strewn with stones
        r = 126; gg = 63; bb = 41;
        const q = 1.7, qx = x / q, qy = y / q, ix = Math.floor(qx), iy = Math.floor(qy);
        for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) {
          const sx = ix + dx, sy = iy + dy, size = ih(sx + 71, sy + 13);
          if (size < 0.3) continue;
          const ox = sx + ih(sx, sy) - qx, oy = sy + ih(sy + 37, sx) - qy, reach = 0.12 + 0.34 * size;
          if (ox * ox + oy * oy < reach * reach) { r = size > 0.75 ? 62 : 45; gg = size > 0.75 ? 43 : 32; bb = size > 0.75 ? 36 : 28; }
        }
      } else {                                                     // bedrock: lighter, cracked into slabs
        const q = 8.5, qx = x / q, qy = y / q, ix = Math.floor(qx), iy = Math.floor(qy);
        let near = 9, next = 9, slab = 0;
        for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) {
          const sx = ix + dx, sy = iy + dy, ox = sx + ih(sx, sy) - qx, oy = sy + ih(sy + 37, sx) - qy, d2 = ox * ox + oy * oy;
          if (d2 < near) { next = near; near = d2; slab = ih(sx + 5, sy + 9); } else if (d2 < next) next = d2;
        }
        const k = Math.sqrt(next) - Math.sqrt(near) < 0.045 ? 0.72 : 0.92 + 0.14 * slab;
        r = 205 * k; gg = 171 * k; bb = 142 * k;
      }
      if (slope > safe - 0.03) {                                   // too steep: a rover is stopped above max_tilt
        const k = smooth(safe - 0.03, safe + 0.02, slope), layer = ((height * 0.9 + grain * 0.12) % 1 + 1) % 1 < 0.5, wall = slope > CFG.max_tilt ? 0.7 : 1;
        r = lerp(r, (layer ? 68 : 49) * wall, k); gg = lerp(gg, (layer ? 37 : 26) * wall, k); bb = lerp(bb, (layer ? 28 : 20) * wall, k);
      }
      const shade = (0.9 + 0.2 * (height - low) / (high - low + 1e-9)) * (0.97 + 0.06 * grain);
      out[o] = r * shade; out[o + 1] = gg * shade; out[o + 2] = bb * shade; out[o + 3] = 255;
    }
  }
  g.putImageData(image, 0, 0);
  return canvas;
}
function mapGeometry() {
  const position = new Float32Array(NX * NY * 3), uv = new Float32Array(NX * NY * 2), index = new Uint32Array((NX - 1) * (NY - 1) * 6);
  for (let j = 0, v = 0; j < NY; j++) for (let i = 0; i < NX; i++, v++) {
    position[v * 3] = i * CELL - WIDTH / 2; position[v * 3 + 1] = H[v] * EXAG; position[v * 3 + 2] = DEPTH / 2 - j * CELL;
    uv[v * 2] = i / (NX - 1); uv[v * 2 + 1] = j / (NY - 1);
  }
  for (let j = 0, o = 0; j < NY - 1; j++) for (let i = 0; i < NX - 1; i++, o += 6) {
    const A = j * NX + i, B = A + 1, D = A + NX, C = D + 1;
    index.set(Math.abs(H[A] - H[C]) <= Math.abs(H[B] - H[D]) ? [A, B, C, A, C, D] : [A, B, D, B, C, D], o);
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.BufferAttribute(position, 3)); geometry.setAttribute('uv', new THREE.BufferAttribute(uv, 2));
  geometry.setIndex(new THREE.BufferAttribute(index, 1)); geometry.computeVertexNormals();
  return geometry;
}
const BANDS = [0x8f4126, 0xa34b2b, 0xb35631, 0xc2633a].map(c => new THREE.Color(c)), HILL = new THREE.Color(0x6f3322);
// Everything outside the map: rings of square cells that double in size with distance. The first ring starts on the
// map's own edge vertices and each ring's outer edge is laid on the next ring's coarser one, so nothing gaps.
function outsideGeometry() {
  const position = [], colors = [], color = new THREE.Color();
  let i0 = 0, i1 = NX - 1, j0 = 0, j1 = NY - 1;                             // the hole so far, in grid cells
  for (let n = 1; (i1 - i0) * CELL < WIDTH + 3600; n *= 2) {                // n: this ring's cell size, in grid cells
    const m = 2 * n, I0 = Math.floor((i0 - 6 * n) / m) * m, I1 = Math.ceil((i1 + 6 * n) / m) * m, J0 = Math.floor((j0 - 6 * n) / m) * m, J1 = Math.ceil((j1 + 6 * n) / m) * m;
    const height = (i, j) => {
      const onI = i === I0 || i === I1, onJ = j === J0 || j === J1;
      if (onI && !onJ && (j / n) % 2) return (groundHeight(i * CELL, (j - n) * CELL) + groundHeight(i * CELL, (j + n) * CELL)) / 2;
      if (onJ && !onI && (i / n) % 2) return (groundHeight((i - n) * CELL, j * CELL) + groundHeight((i + n) * CELL, j * CELL)) / 2;
      return groundHeight(i * CELL, j * CELL);
    };
    for (let j = J0; j < J1; j += n) for (let i = I0; i < I1; i += n) {
      if (i >= i0 && i + n <= i1 && j >= j0 && j + n <= j1) continue;       // the map itself, or the rings already laid
      const q = [[i, j], [i + n, j], [i + n, j + n], [i, j + n]].map(([a, b]) => [a * CELL - WIDTH / 2, height(a, b) * EXAG, DEPTH / 2 - b * CELL]);
      for (const [a, b, c] of [[0, 1, 2], [0, 2, 3]]) {
        const x = (q[a][0] + q[b][0] + q[c][0]) / 3, z = (q[a][2] + q[b][2] + q[c][2]) / 3, h = (q[a][1] + q[b][1] + q[c][1]) / 3;
        const tone = fbm(x * 0.012 + 5, z * 0.012 + 2, 3) + (ih(i * 2 + b, j) - 0.5) * 0.06;
        color.copy(BANDS[tone < 0.42 ? 0 : tone < 0.5 ? 1 : tone < 0.58 ? 2 : 3]);
        if (h > 14) color.lerp(HILL, smooth(14, 120, h) * 0.6);
        color.multiplyScalar(0.8);                                           // a shade darker than the map, so the map reads as the field of play
        for (const k of [a, b, c]) { position.push(...q[k]); colors.push(color.r, color.g, color.b); }
      }
    }
    i0 = I0; i1 = I1; j0 = J0; j1 = J1;
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(position, 3)); geometry.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3));
  geometry.computeVertexNormals();
  return geometry;
}

// A line of text that faces the camera and keeps its size on screen; `paint` draws anything else.
const LABELS = [];
class Label {
  constructor(px = 40, width = 512, height = 128) {
    this.canvas = document.createElement('canvas'); this.canvas.width = width; this.canvas.height = height;
    this.texture = new THREE.CanvasTexture(this.canvas); this.texture.colorSpace = THREE.SRGBColorSpace;
    this.sprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: this.texture, transparent: true, depthTest: false, fog: false }));
    this.sprite.center.set(0.5, 0); this.sprite.renderOrder = 10;
    this.sprite.userData = { px, aspect: width / height, reach: 6 };
    this.key = null; LABELS.push(this.sprite);
  }
  paint(key, draw) {
    if (key === this.key) return this;
    this.key = key;
    const g = this.canvas.getContext('2d');
    g.clearRect(0, 0, this.canvas.width, this.canvas.height);
    g.textAlign = 'center'; g.textBaseline = 'alphabetic'; g.lineJoin = 'round';
    draw(g, this.canvas.width, this.canvas.height);
    this.texture.needsUpdate = true;
    return this;
  }
  set(text, color = css(INK)) {
    return this.paint(`${text}|${color}`, (g, w, h) => {
      g.font = `700 ${Math.round(h * 0.48)}px ${FONT}`;
      g.lineWidth = h * 0.1; g.strokeStyle = css(LINE); g.strokeText(text, w / 2, h * 0.875);
      g.fillStyle = color; g.fillText(text, w / 2, h * 0.875);
    });
  }
}

// ---------------------------------------------------------------- the recorded runs
// One rover's mission: where it really was at every tick.
class Track {
  constructor(raw) {
    this.raw = raw; const p = raw.p;
    this.moved = [0]; this.driven = [0];
    for (let i = 1; i <= T; i++) { const d = Math.hypot(p[2 * i] - p[2 * i - 2], p[2 * i + 1] - p[2 * i - 1]); this.moved.push(d); this.driven.push(this.driven[i - 1] + d); }
    // the way the rover faced as it reached each tick: the way it really travelled, kept while it stands
    this.facing = [null]; let last = null;
    for (let i = 1; i <= T; i++) { if (this.moved[i] > 0.05) last = Math.atan2(p[2 * i + 1] - p[2 * i - 1], p[2 * i] - p[2 * i - 2]); this.facing.push(last); }
    const first = this.facing.find(angle => angle !== null) || 0;
    for (let i = 0; i <= T; i++) if (this.facing[i] === null) this.facing[i] = first;
    const dead = raw.events.find(e => e.k === 'dead');
    this.deadTick = dead ? dead.t : null;
    this.samples = raw.samples.slice().sort((a, b) => a.t - b.t);
    this.stops = raw.events.filter(e => e.k === 'stop');
    // the places it was stopped: a rover that keeps running at the same wall is marked there once, not fifty times
    this.walls = [];
    for (const e of this.stops) { const x = p[2 * e.t], y = p[2 * e.t + 1]; if (!this.walls.some(w => Math.hypot(w.x - x, w.y - y) < 4)) this.walls.push({ t: e.t, x, y, why: e.why }); }
  }
  at(t) {
    t = clamp(t, 0, T);
    const i = Math.min(T - 1, Math.floor(t)), f = t - i, p = this.raw.p;
    const turn = ((this.facing[i + 1] - this.facing[i] + 3 * Math.PI) % TAU) - Math.PI;
    return {
      x: lerp(p[2 * i], p[2 * i + 2], f), y: lerp(p[2 * i + 1], p[2 * i + 3], f),
      heading: this.facing[i] + turn * smooth(0, 0.35, f), moving: this.moved[i + 1] > 0.05,
      battery: lerp(this.raw.b[i], this.raw.b[i + 1], f), driven: lerp(this.driven[i], this.driven[i + 1], f),
      alive: this.deadTick === null || t < this.deadTick,
    };
  }
  // the way the rover is heading over the next few ticks, for a camera that should not twitch
  course(t) {
    const a = this.at(t - 2.5), b = this.at(t + 2.5), dx = b.x - a.x, dy = b.y - a.y;
    return Math.hypot(dx, dy) > 1.5 ? Math.atan2(dy, dx) : this.at(t).heading;
  }
  carried(t) { let sum = 0; for (const s of this.samples) if (s.t <= t + 1e-6) sum += s.v; return sum; }
}
const count = (list, t) => { let n = 0; for (const item of list) if (item.t <= t + 1e-6) n++; return n; };
const RUNS = DATA.runs.map((raw, index) => ({ ...raw, index, track: new Track(raw), ref: raw.kind === 'reference' }));
const REF = RUNS.find(r => r.ref), OTHERS = RUNS.filter(r => !r.ref), CLAUDE = OTHERS.filter(r => r.kind === 'claude');
const SPEEDS = [1, 2, 3, 6, 12, 24];                                  // ticks a second
const state = { t: 0, playing: false, speed: 0, cam: 'map', follow: OTHERS.find(r => r.id === DATA.best) || OTHERS[0] || null };
const short = run => run.ref ? 'REFERENCE' : run.label.toUpperCase();
const chased = () => state.follow || REF;
// The score a run shows at tick t: the value it carries over all the value on the map. A rover whose battery ran
// out scores nothing from then on; the half for finishing away from the lander is only known at the end.
function standing(run, t) {
  const dead = run.track.deadTick !== null && t >= run.track.deadTick;
  return { dead, live: t >= T ? run.reward : dead ? 0 : run.track.carried(t) / run.max };
}
const sunAngle = t => Math.PI * (t + CFG.sun_margin) / (T + 2 * CFG.sun_margin);
const sunShare = t => Math.sin(sunAngle(t));                           // the simulator's share of peak sunlight

// ---------------------------------------------------------------- shared scene pieces (the ghost demo's)
const flat = (color, extra = {}) => new THREE.MeshStandardMaterial({ color, roughness: 0.9, metalness: 0, flatShading: true, ...extra });
const MAT = {
  basalt: flat(0x2c211d),
  white: flat(0xefe6d6), dark: flat(0x2a2421), metal: flat(0x8c8782, { roughness: 0.7 }), solar: flat(0x24407e), tan: flat(0xc59a55),
  lamp: new THREE.MeshBasicMaterial({ color: 0xfff2c8 }),
  shell: new THREE.MeshBasicMaterial({ color: LINE, side: THREE.BackSide }),
  ghostDepth: new THREE.MeshBasicMaterial({ colorWrite: false }),
};
const ROCK = (() => {
  const g = new THREE.IcosahedronGeometry(1, 0), p = g.attributes.position;
  for (let i = 0; i < p.count; i++) { const k = 0.74 + 0.5 * ih(Math.round(p.getX(i) * 31 + p.getY(i) * 17), Math.round(p.getZ(i) * 23)); p.setXYZ(i, p.getX(i) * k, p.getY(i) * k, p.getZ(i) * k); }
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
  let total = 0; for (const g of list) total += g.attributes.position.count;
  const position = new Float32Array(total * 3), normal = new Float32Array(total * 3);
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
// The Mars demo's six-wheeled rover facing +x, 2.6 m long. `paint` is its livery: gold for the reference, ice for the run followed.
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
const flatMark = (color, opacity = 1) => new THREE.MeshBasicMaterial({ color, transparent: true, opacity, side: THREE.DoubleSide, depthWrite: false, fog: false, polygonOffset: true, polygonOffsetFactor: -4, polygonOffsetUnits: -4 });

// ---------------------------------------------------------------- the scene: sky, sun, ground
const scene = new THREE.Scene(), HAZE = new THREE.Color();
scene.fog = new THREE.FogExp2(HAZE, 0.0003); scene.background = HAZE;
const SKY = new THREE.Mesh(new THREE.SphereGeometry(6000, 24, 12), new THREE.ShaderMaterial({
  side: THREE.BackSide, depthWrite: false, fog: false,
  uniforms: { sun: { value: new THREE.Vector3(0, 1, 0) }, low: { value: new THREE.Vector3() }, top: { value: new THREE.Vector3() } },
  vertexShader: 'varying vec3 d; void main(){ d = normalize(position); gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }',
  fragmentShader: `varying vec3 d; uniform vec3 sun; uniform vec3 low; uniform vec3 top;
    void main(){ vec3 n = normalize(d); float h = max(n.y, 0.0);
      vec3 col = mix(low, top, pow(h, 0.55));
      float s = max(dot(n, sun), 0.0);
      col = mix(col, vec3(0.86, 0.93, 1.0), smoothstep(0.99962, 0.99972, s));
      col += vec3(0.70, 0.80, 0.95) * pow(s, 60.0) * 0.16;
      if (n.y < 0.0) col = low;
      gl_FragColor = vec4(col, 1.0); }`,
}));
SKY.frustumCulled = false; scene.add(SKY);
const hemi = new THREE.HemisphereLight(0xffe1c2, 0x7a3d27, 1.2), sun = new THREE.DirectionalLight(0xfff1dd, 2.7);
const SPAN = Math.hypot(WIDTH, DEPTH) / 2 + 40;                       // the sun's shadows cover the whole map
sun.castShadow = true; sun.shadow.mapSize.set(4096, 4096); sun.shadow.bias = -0.0004; sun.shadow.normalBias = 0.6;
Object.assign(sun.shadow.camera, { left: -SPAN, right: SPAN, top: SPAN, bottom: -SPAN, near: 10, far: 2 * SPAN + 700 });
scene.add(hemi, sun, sun.target);
// The sun climbs from the east, stands highest at mid-mission and sinks in the west, as the simulator's solar formula has
// it. Its path leans north so that noon still throws shadows and craters read as hollows from a camera in the south.
const LEAN = rad(28), WARM = new THREE.Color(0xffb37a), NOON = new THREE.Color(0xfff1dd), SUN_DIR = new THREE.Vector3();
function setDaylight(t) {
  const angle = sunAngle(t), first = sunShare(0), k = clamp((Math.sin(angle) - first) / Math.max(1e-6, 1 - first), 0, 1);
  SUN_DIR.set(Math.cos(angle), Math.sin(angle) * Math.cos(LEAN), -Math.sin(angle) * Math.sin(LEAN));
  sun.position.copy(SUN_DIR).multiplyScalar(SPAN + 300);
  sun.color.lerpColors(WARM, NOON, Math.pow(k, 0.6)); sun.intensity = lerp(3.5, 3.0, k); hemi.intensity = lerp(1.0, 1.2, k);   // a low sun lights flat ground weakly already
  const low = SKY.material.uniforms.low.value.set(lerp(0.9, 0.925, k), lerp(0.63, 0.735, k), lerp(0.45, 0.545, k));
  SKY.material.uniforms.top.value.set(lerp(0.44, 0.6, k), lerp(0.28, 0.4, k), lerp(0.26, 0.345, k));
  SKY.material.uniforms.sun.value.copy(SUN_DIR);
  HAZE.setRGB(low.x, low.y, low.z, THREE.SRGBColorSpace); scene.fog.color.copy(HAZE);
}

const GROUND_ART = paintGround();
const groundTexture = new THREE.CanvasTexture(GROUND_ART); groundTexture.colorSpace = THREE.SRGBColorSpace; groundTexture.anisotropy = 8;
const ground = new THREE.Mesh(mapGeometry(), new THREE.MeshStandardMaterial({ map: groundTexture, roughness: 1, metalness: 0, flatShading: true }));
ground.castShadow = ground.receiveShadow = true; scene.add(ground);
const beyond = new THREE.Mesh(outsideGeometry(), flat(0xffffff, { vertexColors: true, roughness: 1 }));
beyond.receiveShadow = true; scene.add(beyond);
{
  // the edge of the map, a scale bar south of it, and the stones of the rock fields
  const edge = [];
  for (let i = 0; i < NX; i++) edge.push(P(i * CELL, 0, 0.5));
  for (let j = 0; j < NY; j++) edge.push(P(WIDTH, j * CELL, 0.5));
  for (let i = NX - 1; i >= 0; i--) edge.push(P(i * CELL, DEPTH, 0.5));
  for (let j = NY - 1; j >= 0; j--) edge.push(P(0, j * CELL, 0.5));
  scene.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(edge), new THREE.LineBasicMaterial({ color: INK, transparent: true, opacity: 0.45, fog: false })));
  const length = [1000, 500, 200, 100, 50, 20, 10].find(m => m <= WIDTH / 5) || 10, south = -Math.max(8, DEPTH * 0.035), bar = [];
  const out = (x, y) => new THREE.Vector3(x - WIDTH / 2, groundHeight(x, y) * EXAG + 0.8, DEPTH / 2 - y);
  bar.push(out(0, south + 5), out(0, south - 5));
  for (let x = 0; x <= length; x += CELL) bar.push(out(x, south));
  bar.push(out(length, south - 5), out(length, south + 5));
  scene.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(bar), new THREE.LineBasicMaterial({ color: INK, transparent: true, opacity: 0.8, fog: false })));
  const rule = new Label(24).set(`${length} M`, 'rgba(243,234,217,.8)'); rule.sprite.position.copy(out(length / 2, south - 2)); rule.sprite.userData.fades = true; scene.add(rule.sprite);
  const rocky = []; for (let c = 0; c < CLASS.length; c++) if (CLASS[c] === 2) rocky.push(c);
  const stones = new THREE.InstancedMesh(ROCK, MAT.basalt, Math.min(3600, Math.round(rocky.length * 2.6)));
  const rng = (() => { let s = 12345; return () => (s = (s * 16807) % 2147483647) / 2147483647; })(), m = new THREE.Matrix4(), q = new THREE.Quaternion(), e = new THREE.Euler();
  for (let n = 0; n < stones.count; n++) {
    const cell = rocky[Math.floor(rng() * rocky.length)], x = (cell % (NX - 1) + rng()) * CELL, y = (Math.floor(cell / (NX - 1)) + rng()) * CELL, size = 0.14 + Math.pow(rng(), 2.4) * 0.42;
    e.set(rng() * TAU, rng() * TAU, 0); q.setFromEuler(e);
    m.compose(P(x, y, size * 0.25), q, new THREE.Vector3(size, size * (0.55 + rng() * 0.5), size)); stones.setMatrixAt(n, m);
  }
  stones.castShadow = stones.receiveShadow = true; scene.add(stones);
  for (const [x, y] of WORLD.passes) { const pass = new Label(22).set('PASS', 'rgba(243,234,217,.75)'); pass.sprite.position.copy(P(x, y, 2)); pass.sprite.userData.fades = true; scene.add(pass.sprite); }
}

// ---------------------------------------------------------------- the lander, the targets, the rovers
const UP = new THREE.Vector3(0, 1, 0);
// Lay a flat marker on the ground at a map point, tilted with the slope there.
function tilt(mesh, x, y, reach) {
  const gx = (drawnHeight(x + reach, y) - drawnHeight(x - reach, y)) / (2 * reach) * EXAG, gy = (drawnHeight(x, y + reach) - drawnHeight(x, y - reach)) / (2 * reach) * EXAG;
  const normal = new THREE.Vector3(-gx, 1, gy).normalize();
  mesh.quaternion.setFromUnitVectors(UP, normal); mesh.position.copy(P(x, y)).addScaledVector(normal, 0.3);
}
function lay(mesh, x, y, reach) {
  tilt(mesh, x, y, reach); mesh.renderOrder = 2; scene.add(mesh);
  return mesh;
}
// Stand a body on the drawn ground at a map point, facing `heading` (radians, east 0, north a quarter turn) and tilted with the slope.
const BASIS = new THREE.Matrix4(), AHEAD = new THREE.Vector3(), ABOVE = new THREE.Vector3(), ASIDE = new THREE.Vector3();
function seat(body, x, y, heading, scale) {
  const c = Math.cos(heading), s = Math.sin(heading), a = Math.max(1.1 * scale, 2.2), b = Math.max(0.6 * scale, 1.4);   // never less than a stride, or a life-size rover twitches over every facet
  const front = drawnHeight(x + c * a, y + s * a), back = drawnHeight(x - c * a, y - s * a), left = drawnHeight(x - s * b, y + c * b), right = drawnHeight(x + s * b, y - c * b);
  AHEAD.set(c * 2 * a, (front - back) * EXAG, -s * 2 * a).normalize();
  ASIDE.set(s * 2 * b, (right - left) * EXAG, c * 2 * b).normalize();        // to the body's right
  ABOVE.crossVectors(ASIDE, AHEAD).normalize(); ASIDE.crossVectors(AHEAD, ABOVE);
  body.quaternion.setFromRotationMatrix(BASIS.makeBasis(AHEAD, ABOVE, ASIDE));
  body.position.set(x - WIDTH / 2, Math.max(drawnHeight(x, y), (front + back + left + right) / 4) * EXAG, DEPTH / 2 - y);
  body.scale.setScalar(scale);
}
const [BX, BY] = WORLD.base;
lay(new THREE.Mesh(new THREE.RingGeometry(CFG.base_radius * 0.8, CFG.base_radius, 40).rotateX(-Math.PI / 2), flatMark(INK, 0.9)), BX, BY, CFG.base_radius);
const lander = makeLander(); scene.add(lander);
const baseLabel = new Label(30).set('BASE'); scene.add(baseLabel.sprite);
baseLabel.sprite.position.copy(P(BX, BY)); baseLabel.sprite.center.set(0.5, 1.9);      // under the ring on screen, clear of the names of rovers standing at base

// Each target is a survey flag: its value over it, a bar that runs down to its deadline, and a dot per rover that sampled it.
const CLOSE = Math.max(5, Math.round(T * 0.06)), FRESH = Math.max(6, Math.round(T * 0.035));
const PENNANT = new THREE.BufferGeometry();
PENNANT.setAttribute('position', new THREE.BufferAttribute(new Float32Array([0, 0, 0, 0, -0.7, 0, 1.15, -0.35, 0]), 3));
const TARGETS = WORLD.targets.map(t => {
  const tint = flatMark(INK, 0.95), r = CFG.target_radius;
  const zone = lay(new THREE.Mesh(new THREE.RingGeometry(r * 0.72, r, 36).rotateX(-Math.PI / 2), tint), t.x, t.y, r);
  const staff = new THREE.Group(); staff.position.copy(P(t.x, t.y));
  const pole = cyl(0.045, 0.045, 2.6, MAT.white, 0, 1.3, 0, 6), flag = new THREE.Mesh(PENNANT, tint); flag.position.y = 2.6;
  staff.add(pole, flag); scene.add(staff);
  const label = new Label(30, 256, 128), pips = new Label(18, 256, 64); pips.sprite.center.set(0.5, 1.3);
  pips.sprite.position.copy(staff.position); label.sprite.userData.fades = pips.sprite.userData.fades = true;
  const ping = lay(new THREE.Mesh(new THREE.RingGeometry(0.88, 1, 48).rotateX(-Math.PI / 2), flatMark(LIME, 0)), t.x, t.y, r);
  scene.add(label.sprite, pips.sprite);
  const takers = RUNS.map(run => ({ run, sample: run.track.samples.find(s => s.id === t.id) })).filter(k => k.sample);
  return { ...t, tint, zone, staff, flag, label, pips, ping, takers };
});
function targetArt(g, text, color, bar) {
  g.font = `700 78px ${FONT}`;
  const y = bar === null ? 118 : 92;
  g.lineWidth = 14; g.strokeStyle = css(LINE); g.strokeText(text, 128, y); g.fillStyle = color; g.fillText(text, 128, y);
  if (bar === null) return;
  g.fillStyle = css(LINE); g.fillRect(64, 102, 128, 22);
  g.fillStyle = 'rgba(243,234,217,.25)'; g.fillRect(69, 107, 118, 12);
  g.fillStyle = color; g.fillRect(69, 107, 118 * clamp(bar, 0, 1), 12);
}
function pipArt(g, key) {
  [...key].slice(0, 16).forEach((who, n) => {
    const row = Math.floor(n / 8), inRow = Math.min(8, key.length - row * 8), x = 128 + (n % 8 - (inRow - 1) / 2) * 30, y = 17 + row * 30;
    g.beginPath(); g.arc(x, y, 10.5, 0, TAU);
    g.fillStyle = css(who === 'g' ? GOLD : who === 'i' ? ICE : SHADE); g.fill();
    g.lineWidth = 3.5; g.strokeStyle = who === 's' ? 'rgba(243,234,217,.6)' : css(LINE); g.stroke();
  });
}

const SUB = 5;                                                         // steps of trail per tick, so a trail follows the ground
// The whole path as one ribbon on the drawn ground; how much of it shows is a draw range. `side` leans each edge with the slope.
function trailGeometry(track) {
  const p = track.raw.p, n = T * SUB + 1, xs = new Float32Array(n), ys = new Float32Array(n), dx = new Float32Array(n), dy = new Float32Array(n);
  for (let k = 0; k < n; k++) { const i = Math.min(T - 1, Math.floor(k / SUB)), f = k / SUB - i; xs[k] = lerp(p[2 * i], p[2 * i + 2], f); ys[k] = lerp(p[2 * i + 1], p[2 * i + 3], f); }
  let ux = 1, uy = 0, begun = false;                                   // the direction of each step; a rover standing still keeps the last one
  for (let k = 0; k < n; k++) {
    const ax = k < n - 1 ? xs[k + 1] - xs[k] : 0, ay = k < n - 1 ? ys[k + 1] - ys[k] : 0, len = Math.hypot(ax, ay);
    if (len > 1e-4) { ux = ax / len; uy = ay / len; if (!begun) { dx.fill(ux, 0, k); dy.fill(uy, 0, k); begun = true; } }
    dx[k] = ux; dy[k] = uy;
  }
  const position = new Float32Array(n * 6), side = new Float32Array(n * 6), index = new Uint32Array((n - 1) * 6);
  for (let k = 0; k < n; k++) {
    const ax = dx[Math.max(0, k - 1)], ay = dy[Math.max(0, k - 1)], bx = dx[k], by = dy[k];
    let mx = ax + bx, my = ay + by, grow = 1; const len = Math.hypot(mx, my);
    if (len < 0.3) { mx = bx; my = by; } else { mx /= len; my /= len; grow = Math.min(2.2, 1 / Math.max(0.45, mx * bx + my * by)); }   // a mitre at each bend
    const sx = -my * grow, sy = mx * grow, at = P(xs[k], ys[k]);        // to the left of travel
    const rise = (drawnHeight(xs[k] + sx, ys[k] + sy) - drawnHeight(xs[k] - sx, ys[k] - sy)) / 2 * EXAG;
    for (const [o, w] of [[k * 6, 1], [k * 6 + 3, -1]]) { position[o] = at.x; position[o + 1] = at.y; position[o + 2] = at.z; side[o] = sx * w; side[o + 1] = rise * w; side[o + 2] = -sy * w; }
    if (k < n - 1) index.set([2 * k, 2 * k + 1, 2 * k + 2, 2 * k + 1, 2 * k + 3, 2 * k + 2], k * 6);
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.BufferAttribute(position, 3)); geometry.setAttribute('side', new THREE.BufferAttribute(side, 3));
  geometry.setIndex(new THREE.BufferAttribute(index, 1));
  return geometry;
}
const trailMaterial = () => new THREE.ShaderMaterial({
  uniforms: { color: { value: new THREE.Color(SHADE) }, opacity: { value: 0.4 }, width: { value: 1 } },
  vertexShader: 'attribute vec3 side; uniform float width; void main(){ vec3 p = position + side * width; p.y += 0.3; gl_Position = projectionMatrix * modelViewMatrix * vec4(p, 1.0); }',
  fragmentShader: 'uniform vec3 color; uniform float opacity;\nvoid main(){ gl_FragColor = vec4(color, opacity);\n#include <colorspace_fragment>\n}',
  transparent: true, depthWrite: false, side: THREE.DoubleSide, polygonOffset: true, polygonOffsetFactor: -4, polygonOffsetUnits: -4,
});
// A red cross where a rover was stopped: it had driven onto ground too steep for it, or to the map's edge.
const CROSS = (() => {
  const canvas = document.createElement('canvas'); canvas.width = canvas.height = 64;
  const g = canvas.getContext('2d'); g.lineCap = 'round';
  for (const [width, color] of [[17, css(LINE)], [8, css(RED)]]) { g.lineWidth = width; g.strokeStyle = color; g.beginPath(); g.moveTo(15, 15); g.lineTo(49, 49); g.moveTo(49, 15); g.lineTo(15, 49); g.stroke(); }
  const texture = new THREE.CanvasTexture(canvas); texture.colorSpace = THREE.SRGBColorSpace;
  return new THREE.SpriteMaterial({ map: texture, transparent: true, depthTest: false, fog: false });
})();
const ACTORS = RUNS.map(run => {
  const track = run.track, actor = { run, track, rover: null, paint: null };
  actor.shadow = makeShadow(); scene.add(actor.shadow);
  actor.trail = new THREE.Mesh(trailGeometry(track), trailMaterial()); actor.trail.frustumCulled = false; scene.add(actor.trail);
  actor.name = new Label(34); actor.toast = new Label(44); scene.add(actor.name.sprite, actor.toast.sprite);
  actor.fix = new THREE.Mesh(new THREE.RingGeometry(0.5, 0.62, 28).rotateX(-Math.PI / 2), flatMark(ICE, 0.9)); actor.fix.renderOrder = 2; scene.add(actor.fix);
  actor.tether = new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(), new THREE.Vector3()]), new THREE.LineBasicMaterial({ color: ICE, transparent: true, opacity: 0.7, fog: false }));
  actor.tether.frustumCulled = false; scene.add(actor.tether);
  actor.marks = track.walls.map(wall => {
    const sprite = new THREE.Sprite(CROSS); sprite.center.set(0.5, 0.5); sprite.renderOrder = 9;
    sprite.position.copy(P(wall.x, wall.y, 1.5)); sprite.userData = { px: 16, aspect: 1, reach: 6, fades: true };
    LABELS.push(sprite); scene.add(sprite);
    return { t: wall.t, sprite };
  });
  return actor;
});

// Draw the mission at tick t. `S` is how much bigger than life markers are drawn, `chase` how far the camera has swung to the chase view.
const TOAST = Math.max(3, T / 70);                                     // ticks a note stays over a rover: about a second at the opening speed
function apply(t, wall, S, chase) {
  const whole = Math.floor(t + 1e-6), steps = Math.floor(clamp(t, 0, T) * SUB + 1e-6), width = lerp(S_MAP * 0.2, 0.22, chase);
  const lead = REF.track.at(t), mine = state.follow ? state.follow.track.at(t) : null;
  const crowded = mine && Math.hypot(lead.x - mine.x, lead.y - mine.y) < 5 * S;       // the two names would sit on each other
  for (const actor of ACTORS) {
    const { run, track } = actor, pose = track.at(t);
    const role = run.ref ? 'ref' : run === state.follow ? 'on' : 'shade', paint = role === 'ref' ? GOLD : ICE, full = role !== 'shade' && pose.alive;
    if (full && (!actor.rover || actor.paint !== paint)) {             // the full rover is built the first time this run is shown in colour
      if (actor.rover) scene.remove(actor.rover);
      actor.rover = roverParts(paint); actor.paint = paint; scene.add(actor.rover);
    }
    if (actor.rover) actor.rover.visible = full;
    actor.shadow.visible = !full;
    const body = full ? actor.rover : actor.shadow;
    seat(body, pose.x, pose.y, pose.heading, S);
    if (full) {
      actor.rover.userData.body.position.y = pose.moving && state.playing ? Math.sin(wall * 19 + run.index) * 0.012 : 0;
    } else {
      // a lost rover turns red where it died, and slumps
      actor.shadow.userData.fill.color.setHex(pose.alive ? SHADE : RED);
      actor.shadow.userData.fill.opacity = pose.alive ? 0.6 : role === 'shade' ? 0.75 : 0.9;
      if (!pose.alive) body.rotateX(0.2);
    }
    const uniforms = actor.trail.material.uniforms;
    actor.trail.geometry.setDrawRange(0, steps * 6);
    uniforms.color.value.setHex(role === 'ref' ? GOLD : role === 'on' ? ICE : SHADE);
    uniforms.opacity.value = role === 'shade' ? 0.45 : 0.95; uniforms.width.value = role === 'shade' ? width * 0.55 : width;
    actor.trail.renderOrder = role === 'shade' ? 2 : 3;
    // a name over the two rovers in colour; a lost shadow keeps a red word so the spot stays readable
    const name = short(run), top = body.position;
    actor.name.sprite.visible = role !== 'shade' || !pose.alive;
    if (role !== 'shade') actor.name.set(pose.alive ? name : name + ' LOST', css(pose.alive ? paint : RED));
    else if (!pose.alive) actor.name.set('LOST', css(RED));
    const raised = role === 'on' && crowded ? 1.05 : 0;              // in label heights: the followed run's name goes above the reference's
    actor.name.sprite.position.set(top.x, top.y + S * (role === 'shade' ? 2.6 : 3.3), top.z);
    actor.name.sprite.center.set(0.5, -raised);
    actor.name.sprite.userData.px = role === 'shade' ? 24 : 34; actor.name.sprite.userData.fades = role === 'shade';
    actor.name.sprite.material.opacity = 1;
    // one-shot notes for the rovers in colour, as pure functions of time so scrubbing works
    let note = null;
    if (role !== 'shade') {
      for (const s of track.samples) { const age = t - s.t; if (age >= 0 && age < TOAST) note = { age, text: `+${fmt(s.v)}${s.ok ? '' : ' LATE'}`, color: s.ok ? LIME : GOLD }; }
      for (const e of track.raw.events) { const age = t - e.t; if (age >= 0 && age < TOAST && e.k !== 'dead') note = { age, text: e.k === 'miss' ? 'MISS' : 'STOPPED', color: RED }; }
    }
    actor.toast.sprite.visible = !!note;
    if (note) {                                                        // the note sits on the name and drifts up, measured on screen so it reads the same from any camera
      actor.toast.set(note.text, css(note.color)); actor.toast.sprite.position.copy(actor.name.sprite.position);
      actor.toast.sprite.center.set(0.5, -(0.8 + raised * 0.78 + 0.5 * note.age / TOAST)); actor.toast.sprite.material.opacity = clamp(1.6 - 1.6 * note.age / TOAST, 0, 1);
    }
    // what this rover's operator was last told: a position fix that is `delay` ticks old and noisy
    const told = whole - CFG.delay, showFix = role === 'on' && pose.alive && told >= 1 && 2 * told + 1 < track.raw.seen.length;
    actor.fix.visible = actor.tether.visible = showFix;
    if (showFix) {
      const f = actor.fix.position, line = actor.tether.geometry.attributes.position;
      tilt(actor.fix, track.raw.seen[2 * told], track.raw.seen[2 * told + 1], 0.8 * S); actor.fix.scale.setScalar(S);
      line.setXYZ(0, top.x, top.y + 0.5 * S, top.z); line.setXYZ(1, f.x, f.y, f.z); line.needsUpdate = true;
    }
    for (const mark of actor.marks) { mark.sprite.visible = t >= mark.t - 1e-6; mark.sprite.userData.px = role === 'shade' ? 13 : 18; }
  }
  seat(lander, BX, BY + 4.2 * S, 2.4, S);                              // beside the base point, where the rovers start and must return to
  for (const target of TARGETS) {
    const known = t >= target.appear - 1e-6;
    target.zone.visible = target.staff.visible = target.label.sprite.visible = known;
    target.ping.visible = target.pips.sprite.visible = false;
    if (!known) continue;
    const left = target.deadline === null ? null : target.deadline - whole, late = left !== null && left < 0;
    const fresh = target.appear > 0 && t - target.appear < FRESH, hue = late ? MUTE : left !== null && left <= CLOSE ? RED : fresh ? LIME : INK;
    target.tint.color.setHex(hue);
    target.staff.scale.set(S, S * (target.appear > 0 ? smooth(0, 1.5, t - target.appear) : 1), S);
    target.flag.position.y = late ? 1.5 : 2.6;                         // a flag whose deadline has passed hangs at half-mast
    target.flag.rotation.y = Math.sin(wall * 2.1 + target.x) * 0.3;
    const bar = left === null || late ? null : (target.deadline + 1 - t) / Math.max(1, target.deadline + 1 - target.appear);
    const text = (fresh && !late ? 'NEW ' : '') + fmt(late ? target.late : target.value);
    target.label.paint(`${text}|${hue}|${bar === null ? '' : Math.round(bar * 40)}`, g => targetArt(g, text, css(hue), bar));
    target.label.sprite.position.copy(target.staff.position).y += 2.75 * S;
    if (fresh) {                                                       // a ring spreads from a target that has just been found
      const age = (t - target.appear) / FRESH;
      target.ping.visible = true; target.ping.scale.setScalar(lerp(1, 7, age) * S); target.ping.material.opacity = 1 - age;
    }
    const key = target.takers.filter(k => k.sample.t <= t + 1e-6).map(k => k.run.ref ? 'g' : k.run === state.follow ? 'i' : 's').sort().join('');
    target.pips.sprite.visible = key.length > 0;
    if (key) target.pips.paint(key, g => pipArt(g, key));
  }
}
function fitLabels(viewHeight, S, chase) {
  const k = 2 * Math.tan(rad(camera.fov) / 2) / viewHeight;
  for (const sprite of LABELS) {
    if (!sprite.visible) continue;
    const data = sprite.userData, far = Math.max(0.5, camera.position.distanceTo(sprite.position));
    if (data.fades) {                                                  // from the chase camera the far labels fade, or the horizon is all numbers
      const show = 1 - chase * smooth(150, 280, far);
      if (show < 0.03) { sprite.scale.set(0, 0, 1); continue; }
      if (sprite.material !== CROSS) sprite.material.opacity = show;
    }
    const h = Math.min(k * far * data.px, data.reach * S);
    sprite.scale.set(h * data.aspect, h, 1);
  }
}

// ---------------------------------------------------------------- renderer and cameras
const renderer = new THREE.WebGLRenderer({ canvas: $('#gl'), antialias: true, powerPreference: 'high-performance' });
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFShadowMap; renderer.shadowMap.autoUpdate = false;
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.setClearColor(0x0b0807, 1);
const MAP_FOV = 34, CHASE_FOV = 52, TILT = rad(52);
const camera = new THREE.PerspectiveCamera(MAP_FOV, 1, 4, 9000);
const view = { k: 0, eye: new THREE.Vector3(), look: new THREE.Vector3(), yaw: null, snap: true, drawn: '' };
// The overview: from the south, north up, swaying a little, the whole map inside the part of the stage that the readouts leave free.
const FRAME = { x: 0.95, top: 0.9, bottom: -0.78 }, SWAY = 0.05, fits = new Map();
function overview(aspect) {
  const key = aspect.toFixed(3);
  if (fits.has(key)) return fits.get(key);
  const probe = new THREE.PerspectiveCamera(MAP_FOV, aspect, 4, 9000), v = new THREE.Vector3();
  const corners = [[0, 0], [WIDTH, 0], [WIDTH, DEPTH], [0, DEPTH]].map(([x, y]) => P(x, y));
  let distance = 3 * Math.max(WIDTH, DEPTH), shift = 0;
  for (let pass = 0; pass < 40; pass++) {                              // home in on the distance and the aim that fit the map at either end of the sway
    let x = 0, top = -9, bottom = 9;
    for (const sway of [-SWAY, 0, SWAY]) {
      probe.position.set(Math.sin(sway) * Math.cos(TILT) * distance, Math.sin(TILT) * distance, shift + Math.cos(sway) * Math.cos(TILT) * distance); probe.lookAt(0, 0, shift); probe.updateMatrixWorld();
      for (const corner of corners) { v.copy(corner).project(probe); x = Math.max(x, Math.abs(v.x)); top = Math.max(top, v.y); bottom = Math.min(bottom, v.y); }
    }
    distance *= lerp(1, Math.max(x / FRAME.x, (top - bottom) / (FRAME.top - FRAME.bottom)), 0.7);
    shift -= ((top + bottom) / 2 - (FRAME.top + FRAME.bottom) / 2) * distance * Math.tan(rad(MAP_FOV) / 2) / Math.sin(TILT) * 0.7;
  }
  fits.set(key, { distance, shift });
  return fits.get(key);
}
const mapEye = new THREE.Vector3(), mapLook = new THREE.Vector3(), chaseEye = new THREE.Vector3(), chaseLook = new THREE.Vector3();
function aim(aspect, wall, t, dt) {
  if (aspect !== view.aspect) { view.aspect = aspect; view.snap = true; }   // a resized window is framed afresh at once
  const { distance, shift } = overview(aspect), sway = Math.sin(wall * 0.09) * SWAY;
  mapEye.set(Math.sin(sway) * Math.cos(TILT) * distance, Math.sin(TILT) * distance, shift + Math.cos(sway) * Math.cos(TILT) * distance); mapLook.set(0, 0, shift);
  // the chase camera rides behind and above the rover being followed, looking where it is heading
  const run = chased(), pose = run.track.at(t), course = run.track.course(t);
  if (view.yaw === null || view.snap) view.yaw = course;
  view.yaw += (((course - view.yaw + 3 * Math.PI) % TAU) - Math.PI) * (1 - Math.exp(-dt * 2.6));
  const cx = Math.cos(view.yaw), cy = Math.sin(view.yaw), back = 17 * S_CHASE, ahead = 7 * S_CHASE, floor = drawnHeight(pose.x, pose.y) * EXAG;
  const ex = pose.x - cx * back, ey = pose.y - cy * back, chest = floor + 1.5 * S_CHASE;
  // high enough to see the rover over whatever ground lies between: a crater's rim, the lip of the scarp
  let high = Math.max(floor + 7.2 * S_CHASE, groundHeight(ex, ey) * EXAG + 3);
  for (const f of [0.2, 0.4, 0.6, 0.8]) high = Math.max(high, (groundHeight(lerp(ex, pose.x, f), lerp(ey, pose.y, f)) * EXAG + 1.2 - chest * f) / (1 - f));
  chaseEye.set(ex - WIDTH / 2, high, DEPTH / 2 - ey);
  chaseLook.set(pose.x + cx * ahead - WIDTH / 2, chest, DEPTH / 2 - (pose.y + cy * ahead));
  const k = smooth(0, 1, view.k), w = story.frame ? smooth(0, 1, story.weight) : 0;
  const pull = view.snap ? 1 : w > 1e-3 ? 1 - Math.exp(-dt * 2.4) : 1 - Math.exp(-dt * lerp(5, 8, k));
  const eye = mapEye.lerp(chaseEye, k), look = mapLook.lerp(chaseLook, k);
  if (w > 1e-3) { eye.lerp(story.frame.eye, w); look.lerp(story.frame.look, w); }   // story mode: the moment's own frame
  view.eye.lerp(eye, pull); view.look.lerp(look, pull);
  view.snap = false;
  camera.fov = lerp(lerp(MAP_FOV, CHASE_FOV, k), MAP_FOV, w); camera.near = lerp(lerp(4, 0.8, k), 1, w); camera.aspect = aspect;
  camera.position.copy(view.eye); camera.lookAt(view.look); camera.updateProjectionMatrix();
  scene.fog.density = lerp(lerp(0.00022, 0.0011, k), 0.0005, w);
  SKY.position.copy(camera.position);
}

// ---------------------------------------------------------------- interface
const scrub = $('#scrub'), marks = $('#marks'), board = $('#board'), banner = $('#banner'), title = $('#title'), mini = $('#mini'), feed = $('#feed');
scrub.max = T;
function fitUi() { document.documentElement.style.setProperty('--s', clamp(Math.min(window.innerWidth / 1500, window.innerHeight / 820), 0.75, 1.8).toFixed(3)); }
const kind = run => run.kind === 'scripted' ? '<i class="kind">SCRIPTED</i>' : '';
const plural = (n, word) => `${n} ${word}${n === 1 ? '' : 's'}`;
function setText(node, value) { if (node.textContent !== value) node.textContent = value; }
function setHtml(node, value) { if (node.dataset.html !== value) { node.dataset.html = value; node.innerHTML = value; } }
function buildBoard() {
  document.title = DATA.title;
  for (const node of document.querySelectorAll('.brand2')) node.textContent = DATA.brand;
  $('#pitch').innerHTML = DATA.pitch;                       // written by viewer/build_traverse.py from the runs shown
  $('#src').textContent = `Recorded runs, not a simulation in this page: every path is what that rover really drove. Heights are drawn ${EXAG} times too tall so the relief reads; the ground beyond the map's edge line is scenery.`;
  $('#cast').innerHTML = RUNS.map(run => `<li class="${run.ref ? 'ref' : ''}"><span>${esc(short(run))}${kind(run)}</span><small>${esc(run.how || run.who)}</small></li>`).join('');
  $('#cast').classList.toggle('many', RUNS.length > 8);    // a long cast drops the small print so the card still fits
  if (MOMENTS.length) {
    $('#storybtn').hidden = false;
    $('#storybtn').onclick = event => { event.stopPropagation(); startStory(); };
    $('#title .help').textContent += ' · S story mode · N next moment';
  }
  if (DATA.sites) {                                         // a campaign: one page per site, all in this file
    $('#sites').innerHTML = DATA.sites.map(site => `<a href="?site=${site.n}" class="${site.n === DATA.site ? 'on' : ''}">${esc(site.label)}<small>${esc(site.note)}</small></a>`).join('');
    $('#sites').onclick = event => event.stopPropagation();  // choosing a site is not starting the replay
    $('#title .help').textContent += ` · ${DATA.sites.map(site => site.n).join(' ')} site`;
  }
  board.innerHTML = `<h2>STANDINGS<span id="after"></span></h2><div id="rows"></div>
    <p id="foot">The bar is the score so far: the value of the samples a rover carries, over all the value on the map. It settles at the end: ½ means the rover finished away from the lander, LOST that its battery ran out.</p>`;
  const rows = $('#rows');
  for (const run of RUNS) {
    const row = document.createElement('div');
    row.className = 'row' + (run.ref ? ' ref' : '');
    row.innerHTML = `<div class="who"><b>${esc(short(run))}${kind(run)}</b><em>0.00</em></div><div class="cells"><div class="cell"><u></u></div><span class="facts"></span></div>`;
    if (!run.ref) row.onclick = () => { state.follow = run; };
    rows.append(row); run.row = row; run.cell = $('.cell', row); run.score = $('em', row); run.facts = $('.facts', row);
  }
  $('#legend').innerHTML = `<span><i style="background:${css(GOLD)}"></i>Reference controller</span>`
    + (OTHERS.length ? `<span><i style="background:${css(ICE)}"></i><span id="who"></span></span>` : '')
    + (OTHERS.length > 1 ? '<span><i style="background:#6f5a50"></i>Every other run</span>' : '')
    + '<span><i class="cliff" style="background:#2e1812"></i>Too steep to drive</span>';
  $('#power').innerHTML = '<h3>BATTERY</h3>' + [['ref', REF], ['on', state.follow]].filter(([, run]) => run).map(([role]) => `<span class="name ${role}"></span><div class="gauge ${role}"><u></u></div><em class="${role}"></em>`).join('');
  mini.style.aspectRatio = `${WIDTH} / ${DEPTH}`;
}
// The timeline: daylight behind it, the reference's samples above the line, the followed run's below, every loss in red.
function drawMarks() {
  const w = marks.clientWidth, h = marks.clientHeight, ratio = window.devicePixelRatio || 1;
  if (marks.width !== Math.round(w * ratio)) { marks.width = Math.round(w * ratio); marks.height = Math.round(h * ratio); }
  const g = marks.getContext('2d'); g.setTransform(ratio, 0, 0, ratio, 0, 0); g.clearRect(0, 0, w, h);
  const x = t => t / T * w, mid = h / 2;
  g.fillStyle = 'rgba(255,178,36,.13)'; g.beginPath(); g.moveTo(0, h);
  for (let px = 0; px <= w; px += 4) g.lineTo(px, h - 2 - sunShare(px / w * T) * (h - 6));
  g.lineTo(w, h); g.fill();
  g.fillStyle = 'rgba(243,234,217,.22)'; g.fillRect(0, mid - 1.5, w, 3);
  g.fillStyle = css(GOLD); for (const s of REF.track.samples) g.fillRect(x(s.t) - 1, mid - 8, 2, s.ok ? 6 : 3);
  if (state.follow) {
    g.fillStyle = css(ICE); for (const s of state.follow.track.samples) g.fillRect(x(s.t) - 1, mid + 2 + (s.ok ? 0 : 3), 2, s.ok ? 6 : 3);
    g.fillStyle = css(RED); for (const wall of state.follow.track.walls) g.fillRect(x(wall.t) - 1.5, mid + 9, 3, 3);
  }
  g.fillStyle = css(RED); for (const run of RUNS) if (run.track.deadTick !== null) g.fillRect(x(run.track.deadTick) - 1.5, mid - 11, 3, 22);
  for (const m of MOMENTS) {                                          // story mode's moments: small diamonds above the line
    const cx = x(m.t), on = m === story.active;
    g.fillStyle = tone(m) === 'gold' ? css(GOLD) : tone(m) === 'warn' ? '#ffd27a' : css(RED); g.globalAlpha = on ? 1 : 0.75;
    g.beginPath(); g.moveTo(cx, 1); g.lineTo(cx + (on ? 5 : 3.5), mid - 13); g.lineTo(cx, mid - 9); g.lineTo(cx - (on ? 5 : 3.5), mid - 13); g.closePath(); g.fill();
  }
  g.globalAlpha = 1;
  g.fillStyle = css(INK); g.fillRect(0, mid - 1.5, x(state.t), 3);
  g.fillRect(x(state.t) - 1.5, mid - 10, 3, 20);
}
// The sun on its arc as the camera sees it from the south: up in the east on the right, down in the west on the left.
function drawSun(t) {
  const canvas = $('#sun'), w = canvas.clientWidth, h = canvas.clientHeight, ratio = window.devicePixelRatio || 1;
  if (canvas.width !== Math.round(w * ratio)) { canvas.width = Math.round(w * ratio); canvas.height = Math.round(h * ratio); }
  const g = canvas.getContext('2d'); g.setTransform(ratio, 0, 0, ratio, 0, 0); g.clearRect(0, 0, w, h);
  const angle = sunAngle(t), base = h - 3, r = Math.min(w / 2 - 5, h - 8);
  g.strokeStyle = 'rgba(243,234,217,.3)'; g.lineWidth = 2; g.beginPath(); g.arc(w / 2, base, r, Math.PI, TAU); g.stroke();
  g.fillStyle = 'rgba(243,234,217,.55)'; g.fillRect(0, base, w, 2);
  g.fillStyle = css(GOLD); g.beginPath(); g.arc(w / 2 + Math.cos(angle) * r, base - Math.sin(angle) * r, 4.2, 0, TAU); g.fill();
}
// The mini-map: the same ground from straight above, north up, with every trail so far.
let miniGround = null;
function drawMini(t) {
  const w = mini.clientWidth, h = mini.clientHeight, ratio = window.devicePixelRatio || 1;
  if (!w || !h) return;
  if (!miniGround || mini.width !== Math.round(w * ratio)) {
    mini.width = Math.round(w * ratio); mini.height = Math.round(h * ratio);
    miniGround = document.createElement('canvas'); miniGround.width = mini.width; miniGround.height = mini.height;
    const b = miniGround.getContext('2d'); b.drawImage(GROUND_ART, 0, 0, mini.width, mini.height); b.fillStyle = 'rgba(11,8,7,.3)'; b.fillRect(0, 0, mini.width, mini.height);
  }
  const g = mini.getContext('2d'); g.setTransform(1, 0, 0, 1, 0, 0); g.drawImage(miniGround, 0, 0); g.setTransform(ratio, 0, 0, ratio, 0, 0);
  const X = x => x / WIDTH * w, Y = y => (1 - y / DEPTH) * h, whole = Math.floor(t + 1e-6);
  for (const target of TARGETS) {
    if (t < target.appear - 1e-6) continue;
    const left = target.deadline === null ? null : target.deadline - whole, mine = state.follow && target.takers.some(k => k.run === state.follow && k.sample.t <= t + 1e-6);
    g.fillStyle = mine ? css(ICE) : left !== null && left < 0 ? css(MUTE) : left !== null && left <= CLOSE ? css(RED) : css(INK);
    g.fillRect(X(target.x) - 2, Y(target.y) - 2, 4, 4);
  }
  const order = [...RUNS.filter(r => !r.ref && r !== state.follow), REF, ...(state.follow ? [state.follow] : [])];
  for (const run of order) {
    const p = run.p, pose = run.track.at(t), role = run.ref ? 'ref' : run === state.follow ? 'on' : 'shade';
    g.strokeStyle = role === 'ref' ? css(GOLD) : role === 'on' ? css(ICE) : 'rgba(26,16,12,.75)'; g.lineWidth = role === 'shade' ? 1 : 1.8; g.lineJoin = 'round';
    g.beginPath(); g.moveTo(X(p[0]), Y(p[1]));
    for (let i = 1; i <= whole && i <= T; i++) g.lineTo(X(p[2 * i]), Y(p[2 * i + 1]));
    g.lineTo(X(pose.x), Y(pose.y)); g.stroke();
    g.fillStyle = !pose.alive ? css(RED) : role === 'ref' ? css(GOLD) : role === 'on' ? css(ICE) : css(SHADE);
    g.strokeStyle = role === 'shade' ? 'rgba(243,234,217,.6)' : css(LINE); g.lineWidth = 1.2;
    g.beginPath();
    if (run === chased()) { const a = -pose.heading, cx = X(pose.x), cy = Y(pose.y); g.moveTo(cx + Math.cos(a) * 7, cy + Math.sin(a) * 7); g.lineTo(cx + Math.cos(a + 2.5) * 5.5, cy + Math.sin(a + 2.5) * 5.5); g.lineTo(cx + Math.cos(a - 2.5) * 5.5, cy + Math.sin(a - 2.5) * 5.5); g.closePath(); }
    else g.arc(X(pose.x), Y(pose.y), role === 'shade' ? 2.6 : 3.6, 0, TAU);
    g.fill(); g.stroke();
  }
  g.strokeStyle = css(INK); g.lineWidth = 1.5; g.strokeRect(X(BX) - 4, Y(BY) - 4, 8, 8);
}
// What went wrong and when, for every rover. The newest lines show for a while and then fade.
const fromBase = run => Math.hypot(run.p[2 * T] - BX, run.p[2 * T + 1] - BY).toFixed(1);
const FEED = [];
for (const run of RUNS) {
  for (const e of run.events) if (e.k !== 'stop') FEED.push({ t: e.t, run, text: e.k === 'dead' ? 'lost · battery ran out' : 'sample missed' });
  for (const wall of run.track.walls) FEED.push({ t: wall.t, run, text: wall.why === 'map_boundary' ? 'stopped at the map edge' : 'stopped · ground too steep' });
  if (run.alive && !run.home) FEED.push({ t: T, run, text: `ended ${fromBase(run)} m from the lander · half score` });
}
FEED.sort((a, b) => a.t - b.t || a.run.index - b.run.index);
const LINGER = Math.max(12, T * 0.1);
function updateFeed(t) {
  const lines = FEED.filter(e => e.t <= t + 1e-6 && t - e.t < LINGER).slice(-4).reverse();
  setHtml(feed, lines.map(e => `<div style="opacity:${(Math.ceil(clamp(1.3 - (t - e.t) / LINGER, 0, 1) * 8) / 8).toFixed(2)}"><b class="${e.run.ref ? 'ref' : e.run === state.follow ? 'on' : ''}">${esc(short(e.run))}</b> <u>${e.text}</u><span>T${e.t}</span></div>`).join(''));
}
// ---------------------------------------------------------------- story mode
// The page plays itself and stops at the moments that decided the scores (viewer/traverse_story.py computes them
// from the replays): what a rover did, and what would have saved it or what the reference did instead.
const MOMENTS = (DATA.moments || []).map(m => ({ ...m, run: RUNS.find(r => r.id === m.run) })).filter(m => m.run);
const KIND = { lost: 'BATTERY FLAT', no_return: 'POINT OF NO RETURN', away: 'STRANDED', close: 'CLOSE CALL', steep: 'TOO STEEP',
  misses: 'MISSED SAMPLE', ref_wait: 'THE REFERENCE PACES ITSELF', ref_home: 'THE REFERENCE HEADS HOME' };
const HOLD = { lost: 9, no_return: 9, away: 7.5, close: 6.5, steep: 7, misses: 6.5, ref_wait: 8, ref_home: 7 };   // seconds on screen
const NEAR = 14;                                                       // ticks before a moment at which the story slows and turns to it
const story = { on: false, i: 0, hold: 0, active: null, weight: 0, frame: null, end: 0 };
const DOTS = 700, dotSpacing = 2.4;
const dots = new THREE.InstancedMesh(new THREE.CircleGeometry(0.5, 14).rotateX(-Math.PI / 2), flatMark(LIME, 0.95), DOTS);
dots.material.depthTest = false; dots.renderOrder = 11; dots.count = 0; dots.frustumCulled = false; scene.add(dots);
const wayLabel = new Label(36, 720); wayLabel.sprite.visible = false; scene.add(wayLabel.sprite);
const pulse = new THREE.Mesh(new THREE.RingGeometry(0.9, 1.25, 40).rotateX(-Math.PI / 2), flatMark(RED, 0.9));
pulse.material.depthTest = false; pulse.renderOrder = 11; pulse.visible = false; scene.add(pulse);
const card = document.createElement('div'); card.id = 'moment'; $('#stage').append(card);
function dotted(path) {                                                // points every couple of metres along a path of grid steps
  const out = [];
  for (let i = 0; i < path.length - 1; i++) {
    const [ax, ay] = path[i], [bx, by] = path[i + 1], n = Math.max(1, Math.round(Math.hypot(bx - ax, by - ay) / dotSpacing));
    for (let k = 0; k < n; k++) out.push([lerp(ax, bx, k / n), lerp(ay, by, k / n)]);
  }
  out.push(path[path.length - 1]);
  return out.slice(0, DOTS);
}
for (const m of MOMENTS) if (m.path) m.dots = dotted(m.path);
const nextMoment = () => MOMENTS[story.i] || null;
const tone = m => m.kind.startsWith('ref') ? 'gold' : m.kind === 'close' ? 'warn' : 'bad';
function showCard(m) {
  card.className = 'on ' + tone(m);
  card.innerHTML = `<i>${KIND[m.kind]}<span>TICK ${m.t}</span></i><b class="${m.run.ref ? 'ref' : 'on'}">${esc(short(m.run))}</b><p>${esc(m.did)}</p>`
    + (m.better ? `<p class="better"><u>${esc(m.better_title)}</u>${esc(m.better)}</p>` : '');
}
function hideCard() { card.className = card.className.replace(/\bon\b/, '').trim(); }
// a frame for the camera that holds the rover and, when there is one, its way home
function frameFor(m) {
  const points = [m.focus, ...(m.path || [])];
  let x0 = Infinity, x1 = -Infinity, y0 = Infinity, y1 = -Infinity;
  for (const [x, y] of points) { x0 = Math.min(x0, x); x1 = Math.max(x1, x); y0 = Math.min(y0, y); y1 = Math.max(y1, y); }
  const cx = (x0 + x1) / 2, cy = (y0 + y1) / 2, radius = Math.max(30, Math.hypot(x1 - x0, y1 - y0) / 2 + 14);
  const distance = radius / Math.tan(rad(MAP_FOV) / 2) * 1.1, look = P(cx, cy), lean = rad(50);
  return { distance, look, eye: new THREE.Vector3(look.x, look.y + Math.sin(lean) * distance, look.z + Math.cos(lean) * distance) };
}
function startStory() {
  story.on = true; story.active = null; story.end = 0;
  story.i = MOMENTS.findIndex(m => m.t >= state.t - 1e-6); if (story.i < 0) story.i = MOMENTS.length;
  if (state.t >= T) { seek(0); story.i = 0; }
  showTitle(false); setCam('map'); setPlaying(true);
}
function stopStory() { story.on = false; story.active = null; hideCard(); }
// before time moves: hold on a moment, or slow down and turn toward the next one
function storyTick(dt) {
  if (!story.on) return;
  if (story.active) {
    story.hold -= dt;
    if (story.hold <= 0) { story.active = null; hideCard(); story.i++; setPlaying(true); }
    return;
  }
  const m = nextMoment();
  if (!m) {
    setSpeed(4);
    if (state.t >= T) {                                                // the result, then the next site of a campaign
      story.end += dt;
      if (story.end > 7 && DATA.sites && DATA.site < DATA.sites.length) location.href = `?site=${DATA.site + 1}#story`;
    }
    return;
  }
  const ahead = m.t - state.t;
  if (ahead <= 1e-6) {
    seek(m.t); setPlaying(false); story.active = m; story.hold = HOLD[m.kind] || 5; story.frame = frameFor(m);
    if (!m.run.ref) state.follow = m.run;
    showCard(m);
    return;
  }
  if (!state.playing) setPlaying(true);
  setSpeed(ahead < 4 ? 1 : ahead < NEAR ? 2 : 4);
  if (ahead < NEAR) { story.frame = frameFor(m); if (!m.run.ref) state.follow = m.run; }
}
// the way home drawing itself while a moment holds, and a ring where it happened
function drawStory(t, S, wall) {
  const m = story.active, held = m ? (HOLD[m.kind] || 5) - story.hold : 0;
  const show = m && m.dots ? m.dots.length : 0, drawn = Math.min(show, Math.ceil(show * smooth(0.2, 1.8, held)));
  dots.count = drawn;
  if (drawn) {
    dots.material.color.setHex(m.open ? LIME : RED);
    const matrix = new THREE.Matrix4(), size = new THREE.Vector3(S * 0.85, 1, S * 0.85), turn = new THREE.Quaternion();
    for (let k = 0; k < drawn; k++) { const [x, y] = m.dots[k]; matrix.compose(P(x, y, 0.6), turn, size); dots.setMatrixAt(k, matrix); }
    dots.instanceMatrix.needsUpdate = true;
  }
  wayLabel.sprite.visible = !!(m && m.dots && held > 1.2);
  if (wayLabel.sprite.visible) {
    const metres = Math.round(Math.hypot(m.focus[0] - BX, m.focus[1] - BY));
    wayLabel.set(`WAY HOME ${m.open ? 'OPEN' : 'CLOSED'} · ${metres} M`, css(m.open ? LIME : RED));
    const [mx, my] = m.dots[Math.floor(m.dots.length * 0.55)];
    wayLabel.sprite.position.copy(P(mx, my, 2.5 * S));
  }
  pulse.visible = !!m;
  if (m) {
    const pose = m.run.track.at(t), beat = (wall * 1.4) % 1;
    pulse.position.copy(P(pose.x, pose.y, 0.5)); pulse.scale.setScalar(S * lerp(1.2, 3.4, beat));
    pulse.material.color.setHex(tone(m) === 'gold' ? GOLD : tone(m) === 'warn' ? GOLD : RED); pulse.material.opacity = 0.9 * (1 - beat);
  }
}
const START_CARD = Math.max(6, T * 0.028);
// The end card: the reference's score against the best other run's, and why that run's score is what it is.
function finalCard() {
  const best = CLAUDE[0] || OTHERS[0], gold = `<em style="color:${css(GOLD)}">${two(REF.reward)}</em>`;
  if (!best) return `<b>${gold}</b><span>The reference alone: no other run has been recorded on this ground</span>`;
  const who = CLAUDE.length > 1 ? `the best of ${CLAUDE.length} Claude runs` : CLAUDE.length ? 'the Claude run' : OTHERS.length > 1 ? 'the best scripted stand-in' : 'the scripted stand-in';
  const end = !best.alive ? `, lost when its battery ran out at tick ${best.track.deadTick}`
    : !best.home ? `, which stopped ${fromBase(best)} m from the lander, outside its ${fmt(CFG.base_radius)} m ring, and kept half of ${two(best.track.carried(T) / best.max)}` : '';
  const lost = CLAUDE.filter(r => !r.alive).length, away = CLAUDE.filter(r => r.alive && !r.home).length;
  const rest = CLAUDE.length > 1 ? ` · ${lost} of the ${CLAUDE.length} Claude rovers lost, ${away} ended away from the lander` : CLAUDE.length ? '' : ' · no model has driven this ground yet';
  return `<b>${gold} · <em style="color:${css(ICE)}">${two(best.reward)}</em></b><span>Reference against ${who} (${esc(best.label)})${end}${rest}</span>`;
}
function updateBoard() {
  const t = state.t, over = t >= T, whole = Math.min(T, Math.floor(t + 1e-6));
  const order = RUNS.map(run => ({ run, s: standing(run, t) })).sort((a, b) => b.s.live - a.s.live || a.run.index - b.run.index);
  // every run fits: rows shrink when there are many or the window is short
  const scale = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--s')) || 1, list = $('#rows');
  const height = Math.max(30, Math.min(62 * scale, list.clientHeight / RUNS.length));
  if (list.dataset.rh !== height.toFixed(1)) { list.dataset.rh = height.toFixed(1); list.style.setProperty('--rh', height.toFixed(1) + 'px'); list.classList.toggle('tight', height < 46); }
  order.forEach(({ run, s }, place) => {
    run.row.style.top = place * height + 'px';
    run.row.classList.toggle('on', run === state.follow);
    run.row.classList.toggle('shade', !run.ref && run !== state.follow);
    setText(run.score, two(s.live));
    run.cell.classList.toggle('lost', s.dead); run.cell.classList.toggle('now', !over && !s.dead);
    run.cell.classList.toggle('away', over && run.alive && !run.home);
    run.cell.firstChild.style.width = s.live * 100 + '%';
    const stops = count(run.track.stops, t);
    setText(run.facts, plural(count(run.track.samples, t), 'sample') + (stops ? ' · ' + plural(stops, 'stop') : ''));
  });
  setText($('#after'), over ? 'final' : t < 1e-6 ? 'before the start' : `tick ${whole} of ${T}`);
  setText($('#clock b'), String(whole).padStart(String(T).length, '0')); setText($('#clock span'), `/${T}`);
  // the hour is the sun's place on its arc read as a twelve-hour day, sunrise at six
  const hour = 6 + 12 * sunAngle(t) / Math.PI, minutes = Math.floor(hour % 1 * 60);
  setText($('#day b'), `${String(Math.floor(hour)).padStart(2, '0')}:${String(minutes).padStart(2, '0')}`);
  setText($('#day span'), `sun ${Math.round(sunShare(t) * 100)}%`);
  for (const [role, run] of [['ref', REF], ['on', state.follow]]) {
    if (!run || !$(`#power .name.${role}`)) continue;
    const pose = run.track.at(t), share = clamp(pose.battery / CFG.battery, 0, 1);
    setText($(`#power .name.${role}`), short(run));
    $(`#power .gauge.${role} u`).style.width = (share * 100).toFixed(1) + '%';
    $(`#power .gauge.${role}`).classList.toggle('low', share < 0.15);
    setText($(`#power em.${role}`), pose.alive ? Math.round(share * 100) + '%' : 'LOST'); $(`#power em.${role}`).classList.toggle('lost', !pose.alive);
  }
  if ($('#who')) setText($('#who'), state.follow.kind === 'claude' ? 'Claude run you follow' : 'Scripted stand-in you follow');
  if (state.cam === 'chase') {
    const run = chased(), pose = run.track.at(t);
    setHtml($('#tag'), `<b>${esc(short(run))}</b><span>${pose.alive ? `on ${GROUND_NAMES[classAt(pose.x, pose.y)]} · slope ${Math.round(slopeAt(pose.x, pose.y) * 100)}%, stopped above ${Math.round(CFG.max_tilt * 100)}%` : 'lost: the battery ran out'} · ${(pose.driven / 1000).toFixed(2)} km driven</span>`);
  } else setHtml($('#tag'), `<b>${fmt(WIDTH)} × ${fmt(DEPTH)} M</b><span>heights drawn ${EXAG}× · dark ground is too steep to drive · every position fix is ${CFG.delay} ticks old</span>`);
  setText($('#cam'), state.cam === 'chase' ? 'MAP' : 'CHASE');
  // banner: what is on the map for the first ticks, the result at the very end
  let text = '', alpha = 0;
  if (over) { text = finalCard(); alpha = 1; }
  else if (t < START_CARD) {
    const later = TARGETS.filter(target => target.appear > 0).length;
    text = `<b>${esc(DATA.brand)}</b><span>${plural(TARGETS.length - later, 'target')} on the map${later ? ` · ${later} more will appear` : ''}</span>`;
    alpha = t <= 1e-6 ? 0 : clamp(Math.min(t / (START_CARD * 0.12), (START_CARD - t) / (START_CARD * 0.3)), 0, 1);
  }
  setHtml(banner, text);
  banner.classList.toggle('final', over);
  banner.style.opacity = alpha;
  updateFeed(t);
}

// ---------------------------------------------------------------- loop and input
function setPlaying(on) { state.playing = on; $('#play').textContent = on ? '❚❚' : '▶'; }
function seek(t) { state.t = clamp(t, 0, T); }
function setSpeed(i) { state.speed = clamp(i, 0, SPEEDS.length - 1); $('#speed').textContent = SPEEDS[state.speed] + '×'; }
function setCam(name) { state.cam = name === 'chase' ? 'chase' : 'map'; }
function showTitle(on) { title.classList.toggle('gone', !on); if (on) setPlaying(false); }
function toggleFull() { if (document.fullscreenElement) document.exitFullscreen(); else document.documentElement.requestFullscreen(); }
$('#play').onclick = event => { event.currentTarget.blur(); if (state.t >= T) seek(0); setPlaying(!state.playing); };
$('#speed').onclick = event => { event.currentTarget.blur(); setSpeed((state.speed + 1) % SPEEDS.length); };
$('#cam').onclick = event => { event.currentTarget.blur(); setCam(state.cam === 'chase' ? 'map' : 'chase'); };
scrub.oninput = () => { seek(+scrub.value); setPlaying(false); };
scrub.onchange = () => scrub.blur();
title.onclick = () => { showTitle(false); setPlaying(true); };
window.addEventListener('keydown', event => {
  if (event.metaKey || event.ctrlKey || event.altKey) return;
  const key = event.key, step = event.shiftKey ? 10 : 1;
  if (DATA.sites && DATA.sites.some(site => String(site.n) === key) && +key !== DATA.site) { location.search = `?site=${key}`; return; }
  if ((key === 's' || key === 'S') && MOMENTS.length) { if (story.on) stopStory(); else startStory(); return; }
  if (!title.classList.contains('gone')) { if (key === 'Enter' || key === ' ') { event.preventDefault(); showTitle(false); setPlaying(true); } else if (key === 'f' || key === 'F') toggleFull(); return; }
  if (key === 'n' || key === 'N') {
    if (story.on && story.active) { story.hold = 0; return; }
    const m = MOMENTS.find(item => item.t > state.t + 1e-6);
    if (m) { seek(Math.max(0, m.t - NEAR)); if (story.on) story.i = MOMENTS.indexOf(m); }
    return;
  }
  if (key === ' ' || key === 'Enter') { event.preventDefault(); if (story.on) { stopStory(); setPlaying(false); return; } if (state.t >= T) seek(0); setPlaying(!state.playing); }
  else if (key === 'ArrowRight') { event.preventDefault(); setPlaying(false); seek(Math.floor(state.t + 1e-6) + step); }
  else if (key === 'ArrowLeft') { event.preventDefault(); setPlaying(false); seek(Math.ceil(state.t - 1e-6) - step); }
  else if (key === '-' || key === '_') setSpeed(state.speed - 1);
  else if (key === '=' || key === '+') setSpeed(state.speed + 1);
  else if (key === 'f' || key === 'F') toggleFull();
  else if (key === 'c' || key === 'C') setCam(state.cam === 'chase' ? 'map' : 'chase');
  else if (key === 'Escape') showTitle(true);
  else if (key === 'Tab' && OTHERS.length) { event.preventDefault(); state.follow = OTHERS[(OTHERS.indexOf(state.follow) + (event.shiftKey ? OTHERS.length - 1 : 1)) % OTHERS.length]; }
});
window.addEventListener('resize', fitUi);

let last = performance.now(), shown = -1;
function frame(now) {
  const dt = Math.min(0.1, (now - last) / 1000), wall = now / 1000; last = now;
  storyTick(dt);
  if (state.playing) {
    let next = state.t + dt * SPEEDS[state.speed];
    const coming = story.on && !story.active ? nextMoment() : null;
    if (coming && next > coming.t) next = coming.t;
    if (next >= T) { next = T; setPlaying(false); }
    state.t = next;
  }
  const near = story.on && (story.active || (nextMoment() && nextMoment().t - state.t < NEAR));
  story.weight = clamp(story.weight + (near ? dt / 1.1 : -dt / 1.4), 0, 1);
  const t = state.t, want = state.cam === 'chase' ? 1 : 0;
  if (Math.abs(t - shown) > 3) view.snap = true;                        // a jump in time: the camera cuts instead of flying
  shown = t;
  view.k = clamp(view.k + Math.sign(want - view.k) * dt / 1.1, Math.min(view.k, want), Math.max(view.k, want));
  const chase = smooth(0, 1, view.k);
  let S = lerp(S_MAP, S_CHASE, chase);
  if (story.frame && story.weight > 0) S = lerp(S, Math.max(S_CHASE, S_MAP * story.frame.distance / overview(view.aspect || 1.6).distance), smooth(0, 1, story.weight));
  setDaylight(t); apply(t, wall, S, chase); drawStory(t, S, wall);
  // viewport: everything left of the standings and under the top strip
  const s = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--s')) || 1;
  const W = window.innerWidth, Hh = window.innerHeight, barH = Math.round(42 * s), boardW = Math.round(340 * s);
  const vw = Math.max(200, W - boardW), vh = Math.max(200, Hh - barH);
  if (renderer.domElement.width !== Math.round(W * renderer.getPixelRatio()) || renderer.domElement.height !== Math.round(Hh * renderer.getPixelRatio())) renderer.setSize(W, Hh, false);
  aim(vw / vh, wall, t, dt);
  fitLabels(vh, S, chase);
  // the sun's shadows are redrawn only when something that throws one has moved
  const drawn = `${t.toFixed(3)}|${S.toFixed(3)}|${state.follow ? state.follow.index : ''}`;
  if (drawn !== view.drawn) { view.drawn = drawn; renderer.shadowMap.needsUpdate = true; }
  renderer.setViewport(0, 0, vw, vh); renderer.setScissor(0, 0, vw, vh); renderer.setScissorTest(true);
  renderer.render(scene, camera);
  if (document.activeElement !== scrub) scrub.value = t;
  updateBoard(); drawMarks(); drawSun(t);
  mini.classList.toggle('on', view.k > 0.5);
  if (view.k > 0.05) drawMini(t);
  requestAnimationFrame(frame);
}

// #auto starts by itself; #t=137 opens paused at that tick, so a moment can be linked.
// #t=137&chase opens it in the chase camera, and &follow=<run folder or label> picks the run to follow.
function readHash() {
  const hash = decodeURIComponent(location.hash.slice(1)), words = hash.split(/[&,]/);
  const value = name => { const word = words.find(w => w.startsWith(name + '=')); return word === undefined ? null : word.slice(name.length + 1); };
  const who = value('follow'), run = who && OTHERS.find(r => r.id === who || r.label.toLowerCase() === who.toLowerCase());
  if (run) state.follow = run;
  if (words.includes('chase')) { setCam('chase'); view.k = 1; view.snap = true; }
  if (words.includes('map')) { setCam('map'); view.k = 0; view.snap = true; }
  if (value('t') !== null) { showTitle(false); setPlaying(false); seek(parseFloat(value('t')) || 0); }
  if (words.includes('auto')) { showTitle(false); setPlaying(true); }
  if (words.includes('story') && MOMENTS.length) startStory();
}
window.addEventListener('hashchange', readHash);
// The page's own controls, for a script that records it frame by frame (tools/demo_video) and for tests.
window.LIGHTLAG_TRAVERSE_APP = { state, story, view, HOLD, MOMENTS, RUNS, T, seek, setPlaying, setSpeed, setCam, showTitle, startStory, stopStory,
  follow(id) { const run = OTHERS.find(r => r.id === id); if (run) state.follow = run; return !!run; } };
fitUi(); buildBoard();
setSpeed(SPEEDS.reduce((best, speed, i) => Math.abs(speed - T / 70) < Math.abs(SPEEDS[best] - T / 70) ? i : best, 0));   // the mission plays in about 70 seconds
readHash();
requestAnimationFrame(frame);
