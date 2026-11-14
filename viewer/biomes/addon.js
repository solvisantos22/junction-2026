// Lightlag · biome add-on for the 3D Mars demo. Loaded after viewer/mars/app.js by
// viewer/biomes-demo.html only (see viewer/build_biomes.py); the main demo never loads it.
//
// It changes nothing in the app. It reads what the app already exposes (window.LIGHTLAG, the
// screens' scenes and elements, the title list) and adds on top:
//   * a row of biomes on the title screen, which filters the mission list;
//   * the chosen biome's published areas, drawn in every scene (crust regions, sharp-rock
//     fields and their rough cells, dune faces), and what only Mars knows (soft cells), which
//     is hidden on the delayed Earth picture;
//   * one line of biome status in the top right of each screen, and the relay passes under
//     the timeline;
//   * a slightly different Mars per biome: the same ground, sand, rocks, haze and sun as the
//     main demo, shifted a little after the place the biome is modelled on.
// A mission without biome data (every Main Mars mission) gets none of this.
import * as THREE from 'three';

const L = window.LIGHTLAG, DATA = window.LIGHTLAG_DATA;
const $ = (selector, root = document) => root.querySelector(selector);
const MAIN = 'main_mars';
const SAND = 0xe9bd7c, ROCK = 0xb9aca0, SHADE = 0x5a3212, SOFT = 0xff8a3d, LINE = 0x1b1310;
const hex = n => '#' + n.toString(16).padStart(6, '0');
const FONT = '"DIN Condensed", "Avenir Next Condensed", "Roboto Condensed", "Arial Narrow", sans-serif';
const pct = x => (x === null || x === undefined ? '–' : Math.round(x * 100) + '%');
const esc = text => String(text).replace(/&/g, '&amp;').replace(/</g, '&lt;');
const biomeOf = mission => mission.biome || MAIN;
const BIOMES = (DATA.biomes || []).filter(b => L.MISSIONS.some(m => biomeOf(m) === b.id));

// ---------------------------------------------------------------- styles (this page only)
const style = document.createElement('style');
style.textContent = `
#title h1 { font-size: calc(84px * var(--s)); }
#title .tag { margin-bottom: calc(14px * var(--s)); }
#biomes { display: flex; flex-wrap: wrap; gap: calc(6px * var(--s)); margin: 0 0 calc(10px * var(--s)); }
#biomes button { padding: calc(8px * var(--s)) calc(11px * var(--s)) calc(4px * var(--s)); font-size: calc(17px * var(--s)); letter-spacing: .1em; color: var(--dim); background: var(--panel); border: 2px solid rgba(243, 234, 217, .18); }
#biomes button:hover { border-color: var(--amber); }
#biomes button.on { color: #000; background: var(--amber); border-color: var(--amber); }
#biomeinfo { min-height: calc(74px * var(--s)); margin: 0 0 calc(12px * var(--s)); font-size: calc(16px * var(--s)); line-height: 1.3; letter-spacing: .02em; text-transform: none; color: var(--dim); }
#biomeinfo b { color: var(--ink); font-weight: 700; }
#biomeinfo i { font-style: normal; color: var(--amber); }
#missions li { padding-top: calc(10px * var(--s)); padding-bottom: calc(7px * var(--s)); }
.biome-chip { position: absolute; right: calc(14px * var(--s)); top: calc(50px * var(--s)); max-width: 46%; text-align: right; font-size: calc(17px * var(--s)); line-height: 1.15; letter-spacing: .09em; text-transform: uppercase; color: var(--ink); text-shadow: 0 2px 0 #000, 0 0 12px rgba(0, 0, 0, .6); pointer-events: none; }
.biome-chip b { display: block; font-size: calc(13px * var(--s)); letter-spacing: .14em; color: var(--dim); font-weight: 400; }
.biome-chip.warn { color: var(--amber); } .biome-chip.bad { color: var(--red); } .biome-chip.good { color: var(--lime); }
#passes { position: absolute; left: 6px; right: 6px; bottom: 1px; height: 4px; pointer-events: none; }
`;
document.head.appendChild(style);

// ---------------------------------------------------------------- the biome row on the title screen
const title = $('#title'), list = $('#missions'), items = [...list.children];
const row = document.createElement('nav'); row.id = 'biomes';
const info = document.createElement('p'); info.id = 'biomeinfo';
let shown = null;
if (BIOMES.length > 1) {
  list.before(row, info);
  row.innerHTML = BIOMES.map(b => `<button data-biome="${b.id}">${esc(b.name)}</button>`).join('');
  for (const button of row.children) button.onclick = () => showBiome(button.dataset.biome);
  const help = $('#title .help');
  if (help) help.textContent = '← → choose a biome · ' + help.textContent;
}
const missionsOf = id => L.MISSIONS.filter(m => biomeOf(m) === id);
function mark() { items.forEach((li, i) => li.classList.toggle('on', L.MISSIONS[i] === L.state.mission)); }
function select(mission) { L.state.mission = mission; L.state.run = mission.featuredRun; L.seek(0); L.build(); mark(); }
function describe(biome) {
  const t = ((DATA.early_test || {}).by_biome || {})[biome.id];
  const share = (name, value) => (value === null || value === undefined ? '' : `${name} ${pct(value)}`);
  const numbers = t ? ` <i>Early test, scripted controllers: ${[`best is controller ${esc(t.best)} at ${pct(t.best_share)}`,
    biome.id !== MAIN && t.best !== DATA.shown_best ? share(`controller ${esc(DATA.shown_best)}`, t.shown_best_share) : '',
    share('reference', t.reference_share), share('fixed plan', t.fixed_plan_share), share('leg and wait', t.leg_and_wait_share)].filter(Boolean).join(' · ')}.</i>` : '';
  if (biome.id === MAIN) return `<b>Main Mars.</b> ${esc(biome.blurb)}${numbers}`;
  return `<b>${esc(biome.name)}.</b> ${esc(biome.blurb)} Modelled on ${esc(biome.modelled_on)}.${numbers} No model has played this biome: the runs below are scripted controllers, played when this page was built.`;
}
function showBiome(id, keepMission = false) {
  if (BIOMES.length < 2) return;
  shown = id;
  for (const button of row.children) button.classList.toggle('on', button.dataset.biome === id);
  let n = 0;
  items.forEach((li, i) => {
    const inside = biomeOf(L.MISSIONS[i]) === id;
    li.style.display = inside ? '' : 'none';
    if (inside) $('i', li).textContent = String(++n);
  });
  info.innerHTML = describe(BIOMES.find(b => b.id === id));
  if (!keepMission && biomeOf(L.state.mission) !== id) select(missionsOf(id)[0]);
  mark();
}
// Before the app's own key handler: on the title screen the arrows and digits work inside the shown biome.
addEventListener('keydown', e => {
  if (BIOMES.length < 2 || title.classList.contains('gone') || e.metaKey || e.ctrlKey || e.altKey) return;
  const at = BIOMES.findIndex(b => b.id === shown), mine = missionsOf(shown), here = mine.indexOf(L.state.mission);
  let handled = true;
  if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') showBiome(BIOMES[(at + (e.key === 'ArrowRight' ? 1 : BIOMES.length - 1)) % BIOMES.length].id);
  else if (e.key === 'ArrowDown' || e.key === 'ArrowUp' || e.key === 'n' || e.key === 'N') select(mine[(here + (e.key === 'ArrowUp' ? mine.length - 1 : 1)) % mine.length]);
  else if (/^[1-9]$/.test(e.key)) { if (mine[e.key - 1]) L.startMission(mine[e.key - 1]); }
  else handled = false;
  if (handled) { e.preventDefault(); e.stopImmediatePropagation(); }
}, true);

// ---------------------------------------------------------------- drawing helpers
const flatMark = (color, opacity = 1) => new THREE.MeshBasicMaterial({ color, transparent: true, opacity, side: THREE.DoubleSide, depthWrite: false, fog: false });
function plate(ms, r, material, h) {
  const w = r.x2 - r.x1, d = r.y2 - r.y1, mesh = new THREE.Mesh(new THREE.PlaneGeometry(w, d), material);
  mesh.rotation.x = -Math.PI / 2; mesh.position.copy(ms.P(r.x1 + w / 2, r.y1 + d / 2, h));
  return mesh;
}
function outline(ms, r, color, h = 0.09) {
  const points = [[r.x1, r.y1], [r.x2, r.y1], [r.x2, r.y2], [r.x1, r.y2], [r.x1, r.y1]].map(([x, y]) => ms.P(x, y, h));
  const line = new THREE.Line(new THREE.BufferGeometry().setFromPoints(points), new THREE.LineDashedMaterial({ color, dashSize: 0.5, gapSize: 0.3, fog: false }));
  line.computeLineDistances();
  return line;
}
// A line of text that faces the camera. The app sizes every sprite that carries userData.px.
function label(text, color, px = 30) {
  const canvas = document.createElement('canvas'); canvas.width = 512; canvas.height = 128;
  const g = canvas.getContext('2d');
  g.font = `700 60px ${FONT}`; g.textAlign = 'center'; g.textBaseline = 'alphabetic'; g.lineJoin = 'round';
  g.lineWidth = 13; g.strokeStyle = hex(LINE); g.strokeText(text, 256, 112);
  g.fillStyle = color; g.fillText(text, 256, 112);
  const texture = new THREE.CanvasTexture(canvas); texture.colorSpace = THREE.SRGBColorSpace;
  const sprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: texture, transparent: true, depthTest: false, fog: false }));
  sprite.center.set(0.5, 0); sprite.renderOrder = 9; sprite.userData = { px, aspect: 4 };
  return sprite;
}
const hash = (x, y) => { const h = Math.sin(x * 127.1 + y * 311.7) * 43758.5453; return h - Math.floor(h); };

// ---------------------------------------------------------------- a slightly different Mars per biome
// Each biome shifts the main demo's own colours a little, after the place it is modelled on, so
// the screen says which biome is playing. It is still Mars; Main Mars is left exactly as it is.
//   ground, sand, rocks   multipliers on the main demo's colours (1 = unchanged)
//   light                 a multiplier on the colour of the sun and the sky light
//   haze                  a colour laid over the sky and into the distance, and how strongly
//   sun                   the sun's brightness against the main demo's
const PALETTES = {
  relay_pass:        { ground: [0.82, 0.86, 1.02], sand: [0.86, 0.88, 1.00], rocks: [0.84, 0.86, 1.00], light: [0.82, 0.86, 1.00], haze: [0x8892be, 0.38], sun: 0.76 },   // late in the sol, waiting for the orbiter: cooler and dimmer
  hidden_valley:     { ground: [1.08, 0.88, 0.76], sand: [1.06, 0.90, 0.76], rocks: [1.00, 0.88, 0.80], light: [1.00, 0.90, 0.80], haze: [0xd9814f, 0.26], sun: 0.96 },   // a valley floor: deeper rust
  bagnold_dunes:     { ground: [0.84, 0.83, 0.88], sand: [0.50, 0.48, 0.54], rocks: [0.80, 0.80, 0.86], light: [0.97, 0.97, 1.00], haze: [0xc2a898, 0.22], sun: 1.00 },   // the Bagnold sand is dark basalt
  troy_crust:        { ground: [1.20, 1.18, 1.04], sand: [1.10, 1.10, 1.04], rocks: [1.08, 1.06, 1.00], light: [1.00, 1.00, 0.96], haze: [0xf8e6c6, 0.36], sun: 1.10 },   // the pale, bright soil Spirit churned up
  gale_rock_field:   { ground: [0.80, 0.76, 0.90], sand: [0.86, 0.84, 0.92], rocks: [0.60, 0.58, 0.76], light: [0.95, 0.93, 1.00], haze: [0xb89a9e, 0.28], sun: 0.97 },   // grey-purple mudstone and dark rock
  meridiani_ripples: { ground: [0.72, 0.64, 0.64], sand: [0.70, 0.58, 0.52], rocks: [0.72, 0.66, 0.66], light: [1.00, 0.98, 0.96], haze: [0xf9e8c8, 0.38], sun: 1.06 },   // dark plains under a pale, dusty sky
};
const HORIZON = [0.925, 0.735, 0.545];   // the main demo's haze, as its sky and fog write it
const shaded = new Map();                // biome id -> the main demo's materials, copied once and shifted
function recolour(ms, id) {
  const palette = PALETTES[id];
  if (!palette) return;
  const scene = ms.scene, shared = ms.shared;
  if (!shaded.has(id)) shaded.set(id, {});
  const copies = shaded.get(id);
  const shift = (mesh, part) => {
    if (!mesh) return;
    if (!copies[part]) { const [r, g, b] = palette[part]; copies[part] = mesh.material.clone(); copies[part].color.multiply(new THREE.Color().setRGB(r, g, b)); }
    mesh.material = copies[part];
  };
  shift(scene.children.find(o => o.isMesh && o.geometry === shared.ground), 'ground');
  for (const mesh of scene.children.filter(o => o.isMesh && shared.sands.some(sheet => sheet.geometry === o.geometry))) shift(mesh, 'sand');
  shift(scene.children.find(o => o.isInstancedMesh && o.geometry === shared.rockGeometry && o.count === shared.rocks.length), 'rocks');
  // The haze: a thin veil inside the sky dome, and the same mix as the fog colour, so the horizon still meets the ground.
  const [tint, strength] = palette.haze, channel = shift8 => ((tint >> shift8) & 255) / 255;
  const mix = [16, 8, 0].map((shift8, i) => HORIZON[i] * (1 - strength) + channel(shift8) * strength);
  const haze = new THREE.Color().setRGB(mix[0], mix[1], mix[2], THREE.SRGBColorSpace);
  if (scene.fog) scene.fog.color.copy(haze);
  scene.background = haze;
  const veil = new THREE.Mesh(new THREE.SphereGeometry(880, 24, 12), new THREE.MeshBasicMaterial({ color: tint, transparent: true, opacity: strength, side: THREE.BackSide, depthWrite: false, fog: false }));
  veil.renderOrder = -1; scene.add(veil);
  const light = new THREE.Color().setRGB(...palette.light), sky = scene.children.find(o => o.isHemisphereLight);
  if (sky) sky.color.multiply(light);
  if (ms.sun) { ms.sun.color.multiply(light); ms.sun.intensity *= palette.sun; }
}

// ---------------------------------------------------------------- one scene's biome features
function decorate(ms) {
  const biome = ms.run.replay.biome;
  ms.biomeAddon = { truth: [] };
  if (!biome) return;
  recolour(ms, biome.ids[0]);
  const scene = ms.scene, truth = ms.biomeAddon.truth, has = id => biome.ids.includes(id);
  // a text label in both the map and the 3D views, placed for each
  const tag = (text, color, r, px) => {
    const onMap = label(text, color, px - 4), in3d = label(text, color, px);
    onMap.position.copy(ms.P((r.x1 + r.x2) / 2, r.y2 + 0.2, 3)); in3d.position.copy(ms.P((r.x1 + r.x2) / 2, (r.y1 + r.y2) / 2, 0.5));
    ms.tactical.add(onMap); ms.cinematic.add(in3d);
  };
  if (has('troy_crust')) {
    const rate = biome.settings.troy_crust.soft_rate;
    for (const r of biome.crust_regions) {
      scene.add(outline(ms, r, SAND));
      ms.tactical.add(plate(ms, r, flatMark(SAND, 0.16), 0.06));
      ms.cinematic.add(plate(ms, r, flatMark(SAND, 0.07), 0.025));
      tag(`CRUST · ${Math.round(rate * 100)}% SOFT`, hex(SAND), r, 30);
    }
    // Soft cells are the hidden instance: Mars and the map show them, the delayed Earth picture does not.
    for (const [ix, iy] of biome.soft_cells) {
      const cell = { x1: ix + 0.06, y1: iy + 0.06, x2: ix + 0.94, y2: iy + 0.94 };
      for (const [group, opacity, h] of [[ms.tactical, 0.75, 0.08], [ms.cinematic, 0.5, 0.03]]) { const mesh = plate(ms, cell, flatMark(SOFT, opacity), h); group.add(mesh); truth.push(mesh); }
    }
  }
  if (has('gale_rock_field')) {
    for (const r of biome.rock_fields) {
      scene.add(outline(ms, r, ROCK));
      ms.tactical.add(plate(ms, r, flatMark(ROCK, 0.12), 0.06));
      tag('SHARP ROCKS', hex(ROCK), r, 30);
    }
    const cells = biome.rough_cells, per = 4;
    const shards = new THREE.InstancedMesh(new THREE.TetrahedronGeometry(1, 0), new THREE.MeshStandardMaterial({ color: 0x3b2f2a, roughness: 0.9, flatShading: true }), Math.max(1, cells.length * per));
    const m = new THREE.Matrix4(), q = new THREE.Quaternion(), e = new THREE.Euler();
    cells.forEach(([ix, iy], i) => {
      for (let k = 0; k < per; k++) {
        const s = 0.09 + hash(ix * 3.1 + k, iy * 1.7) * 0.1; e.set(hash(ix, iy + k) * 6.28, hash(ix + k, iy) * 6.28, 0); q.setFromEuler(e);
        m.compose(ms.P(ix + 0.15 + hash(ix + k * 7.3, iy) * 0.7, iy + 0.15 + hash(ix, iy + k * 5.1) * 0.7, s * 0.45), q, new THREE.Vector3(s, s * 1.3, s));
        shards.setMatrixAt(i * per + k, m);
      }
      ms.tactical.add(plate(ms, { x1: ix + 0.12, y1: iy + 0.12, x2: ix + 0.88, y2: iy + 0.88 }, flatMark(ROCK, 0.55), 0.08));
    });
    shards.count = cells.length * per; shards.castShadow = shards.receiveShadow = true; ms.cinematic.add(shards);
  }
  if (has('bagnold_dunes')) {
    const top = biome.settings.bagnold_dunes.slope_deg[1] || 1;
    for (const f of biome.dune_faces) {
      const steep = f.slope_deg / top;
      ms.cinematic.add(plate(ms, f, flatMark(SHADE, 0.04 + 0.42 * steep), 0.03));
      ms.tactical.add(plate(ms, f, flatMark(SHADE, 0.08 + 0.6 * steep), 0.07));
      ms.tactical.add(outline(ms, f, SAND, 0.075));
      if (f.slope_deg >= 8) {
        const color = hex(f.slope_deg >= 14 ? 0xff4a2f : SAND), text = `${Math.round(f.slope_deg)}°`;
        const onMap = label(text, color, 22), in3d = label(text, color, 26);
        onMap.position.copy(ms.P((f.x1 + f.x2) / 2, (f.y1 + f.y2) / 2 - 0.4, 3)); in3d.position.copy(ms.P((f.x1 + f.x2) / 2, (f.y1 + f.y2) / 2, 0.35));
        ms.tactical.add(onMap); ms.cinematic.add(in3d);
      }
    }
  }
  // The same scene is drawn on several screens; the camera says which one is being drawn.
  scene.onBeforeRender = (renderer, drawn, camera) => { const visible = camera.userData.biomeKind !== 'feed'; for (const mesh of truth) mesh.visible = visible; };
}

// ---------------------------------------------------------------- one line of status per screen
function status(run, pose, feed) {
  const biome = run.replay.biome;
  if (!biome) return null;
  const lines = [], state = pose.state, has = id => biome.ids.includes(id);
  let tone = '';
  if (has('relay_pass')) {
    const [period, open] = biome.relay_passes, now = Math.floor(L.state.t + 1e-6), isOpen = now % period < open;
    lines.push(isOpen ? `relay pass open · closes t${Math.floor(now / period) * period + open}` : `no link · next pass t${(Math.floor(now / period) + 1) * period}`);
    tone = isOpen ? 'good' : 'warn';
  }
  if (has('hidden_valley')) {
    const set = biome.settings.hidden_valley, limit = run.cfg.max_ticks >= set.long_mission_ticks ? set.limit_long_missions : set.limit;
    const tripped = run.events.some(e => e.type === 'safety_stop' && e.reason === 'slip_limit' && pose.tick - e.tick >= 0 && pose.tick - e.tick < 2.4);
    lines.push(tripped ? 'slip limit tripped · queue dropped' : `onboard slip limit ${Math.round(limit * 100)}%`);
    if (tripped) tone = 'bad';
  }
  if (has('troy_crust')) {
    const soft = biome.soft_cells.some(c => c[0] === Math.floor(pose.x) && c[1] === Math.floor(pose.y));
    const inside = biome.crust_regions.some(r => pose.x >= r.x1 && pose.x <= r.x2 && pose.y >= r.y1 && pose.y <= r.y2);
    if (soft && !feed) { lines.push('soft ground under the crust'); tone = 'bad'; }
    else if (feed && inside && state.terrain === 'sand' && !run.world.sand.some(r => pose.x >= r.x1 && pose.x <= r.x2 && pose.y >= r.y1 && pose.y <= r.y2)) { lines.push('telemetry: terrain reads sand'); tone = 'bad'; }
    else lines.push(inside ? 'on the crust' : 'crust regions: mapped firm');
  }
  if (has('gale_rock_field')) {
    const wear = state.wheel_wear ?? 0, set = biome.settings.gale_rock_field;
    if (wear > set.budget_cells) { lines.push(`wheels worn ${wear}/${set.budget_cells} · drives cut to ${set.worn_max_metres} m`); tone = 'bad'; }
    else { lines.push(`wheel wear ${wear}/${set.budget_cells}`); if (wear >= set.budget_cells) tone = 'warn'; }
  }
  if (has('bagnold_dunes')) {
    const face = biome.dune_faces.filter(f => pose.x >= f.x1 && pose.x <= f.x2 && pose.y >= f.y1 && pose.y <= f.y2).sort((a, b) => b.slope_deg - a.slope_deg)[0];
    if (face) { lines.push(`dune face ${Math.round(face.slope_deg)}°`); tone = face.slope_deg >= 14 ? 'bad' : face.slope_deg >= 8 ? 'warn' : tone; }
    else lines.push('dunes: slip grows with slope');
  }
  if (has('meridiani_ripples')) {
    const noise = biome.settings.meridiani_ripples.visual_odometry_noise_by_terrain, on = state.terrain === 'sand';
    lines.push(`odometry ±${Math.round((on ? noise.sand : noise.bedrock) * 100)}% on ${on ? 'sand' : 'bedrock'}`);
    if (on) tone = 'warn';
  }
  return { head: biome.names.join(' + '), text: lines.join(' · '), tone };
}
function chip(screen) {
  if (!screen.biomeChip || !screen.biomeChip.isConnected) {
    screen.biomeChip = document.createElement('div'); screen.biomeChip.className = 'biome-chip';
    screen.biomeChip.innerHTML = '<b></b><span></span>'; screen.el.appendChild(screen.biomeChip); screen.biomeShown = null;
  }
  return screen.biomeChip;
}
const passes = document.createElement('div'); passes.id = 'passes';
const timeline = $('.timeline'); if (timeline) timeline.appendChild(passes);
let passesKey = null;
function drawPasses() {
  const mission = L.state.mission, biome = mission.runs[0].replay.biome, relay = biome && biome.relay_passes;
  const key = relay ? `${relay}|${mission.T}` : '';
  if (key === passesKey) return;
  passesKey = key;
  if (!relay) { passes.style.background = 'none'; return; }
  const [period, open] = relay, stops = [];
  for (let start = 0; start < mission.T; start += period) {
    const a = 100 * start / mission.T, b = 100 * Math.min(mission.T, start + open) / mission.T, c = 100 * Math.min(mission.T, start + period) / mission.T;
    stops.push(`var(--lime) ${a}%`, `var(--lime) ${b}%`, `rgba(243,234,217,.12) ${b}%`, `rgba(243,234,217,.12) ${c}%`);
  }
  passes.style.background = `linear-gradient(90deg, ${stops.join(', ')})`;
}

// ---------------------------------------------------------------- every frame, after the app has built its screens
function frame() {
  for (const screen of L.state.screens) {
    if (!screen.scene) continue;
    if (!screen.scene.biomeAddon) decorate(screen.scene);
    screen.camera.userData.biomeKind = screen.kind;
    if (screen.kind === 'map') continue;
    const feed = screen.kind === 'feed', pose = feed ? screen.run.seen(L.state.t) : screen.run.sample(L.state.t), now = status(screen.run, pose, feed);
    const node = chip(screen), key = now ? `${now.head}|${now.text}|${now.tone}` : '';
    if (screen.biomeShown !== key) {
      screen.biomeShown = key;
      node.style.display = now ? '' : 'none';
      if (now) { node.className = `biome-chip ${now.tone}`; $('b', node).textContent = now.head; $('span', node).textContent = now.text; }
    }
  }
  drawPasses();
  if (BIOMES.length > 1 && !title.classList.contains('gone') && biomeOf(L.state.mission) !== shown) showBiome(biomeOf(L.state.mission), true);
  requestAnimationFrame(frame);
}
if (BIOMES.length > 1) showBiome(biomeOf(L.state.mission), true);
window.LIGHTLAG_BIOMES = { showBiome, BIOMES, PALETTES, shown: () => shown };   // for checks from the browser console
requestAnimationFrame(frame);
