// Manh's add-on for the demo page while it is recorded (tools/manh_demo). It draws on top of
// Kristján's page and changes nothing in it:
//
// - in the top-down shots, a tracker over every rover: a frame around it, a line up, and a badge
//   with the logo of the lab whose model is driving (window.__MANH, from makers.py) and its
//   name. The reference, which is a planner and not a model, gets a gold route tile instead;
// - the same logo on the card that explains a failure, in the standings, and beside the page's
//   own name label in the chase camera;
// - a soft vignette, and where a battery runs flat a red pulse and the colour draining away;
// - what the sound track needs, returned from every draw(): how fast the followed rover is
//   moving and on what ground, and what just happened (a sample, a miss, a safety stop, a
//   tracker locking on, a card coming up).
//
// Everything is a function of the page's own state and of the recorder's clock, so a frame
// looks the same however long it took to draw.
(() => {
  const A = window.LIGHTLAG_TRAVERSE_APP, THREE = A.THREE, M = window.__MANH;
  const s = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--s')) || 1;
  const W = window.innerWidth, H = window.innerHeight, barH = Math.round(42 * s), boardW = Math.round(340 * s);
  const vw = Math.max(200, W - boardW), vh = Math.max(200, H - barH);          // the part of the window the ground is drawn in
  const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
  const lerp = (a, b, t) => a + (b - a) * t;
  const smooth = (a, b, x) => { const t = clamp((x - a) / (b - a), 0, 1); return t * t * (3 - 2 * t); };
  const outCubic = x => 1 - Math.pow(1 - clamp(x, 0, 1), 3);
  const INK = '#f3ead9', GOLD = '#ffb224', ICE = '#9fd8ff', RED = '#ff4a2f', LIME = '#b6e35a', DARK = '#0b0807';
  const makerOf = run => run.ref ? 'reference' : (M.makers[run.id] || null);
  const SVG = 'http://www.w3.org/2000/svg';
  const BASE = A.DATA.world.base;                           // the lander: where rovers start and must return to

  const style = document.createElement('style');
  style.textContent = `
    #manh { position: absolute; inset: 0; overflow: hidden; pointer-events: none; font-family: var(--display); font-weight: 700; text-transform: uppercase; }
    #manh .vig { position: absolute; inset: 0; background: radial-gradient(ellipse 78% 74% at 50% 47%, rgba(0,0,0,0) 54%, rgba(8,4,3,.40) 100%); }
    #manh .pulse { position: absolute; inset: 0; opacity: 0; background: radial-gradient(ellipse 72% 68% at 50% 50%, rgba(255,36,18,0) 30%, rgba(255,36,18,.8) 100%); }
    #manh svg { position: absolute; left: 0; top: 0; width: 100%; height: 100%; overflow: visible; }
    #manh svg path, #manh svg line { fill: none; stroke-linecap: square; }
    #manh .bd { position: absolute; left: 0; top: 0; display: flex; align-items: stretch; white-space: nowrap; opacity: 0;
      filter: drop-shadow(0 2px 0 rgba(0,0,0,.65)) drop-shadow(0 0 9px rgba(0,0,0,.4)); }
    #manh .bd img { display: block; height: 100%; aspect-ratio: 1; }
    #manh .bd b { display: flex; align-items: center; margin-left: 3px; padding: 6px 14px 0 12px; background: rgba(11,8,7,.93); border-bottom: 3px solid currentColor; letter-spacing: .09em; }
    #manh .bd u { display: none; align-items: center; text-decoration: none; padding: 6px 11px 0; letter-spacing: .09em; }
    #manh .bd.lost u.st { display: flex; background: ${RED}; color: ${DARK}; }
    #manh .bd u.nt.show { display: flex; background: rgba(11,8,7,.93); }
    #manh .bd.hero { height: 44px; font-size: 27px; }
    #manh .bd.mini { height: 30px; font-size: 18px; }
    #manh .bd.mini b { padding: 4px 9px 0 8px; border-bottom-width: 2px; margin-left: 2px; }
    #manh .bd.mini u { padding: 4px 7px 0; }
    #manh .chip { position: absolute; left: 0; top: 0; opacity: 0; filter: drop-shadow(0 2px 0 rgba(0,0,0,.6)); }
    #moment .mk { position: absolute; left: calc(20px * var(--s)); top: calc(15px * var(--s)); width: calc(50px * var(--s)); height: calc(50px * var(--s)); }
    #moment.mk-on > i, #moment.mk-on > b { margin-left: calc(63px * var(--s)); }
    #moment b small { margin-left: .9em; font-size: .8em; font-weight: 400; letter-spacing: .14em; color: var(--dim); }
    .row .who b img.mk { height: 1.02em; width: 1.02em; margin-right: .42em; vertical-align: -.14em; }
    #film .caption { font-size: 50px !important; letter-spacing: .075em !important; }   /* Barlow Condensed is wider than the DIN Condensed the captions were sized for */
    #tag.mk b::before { content: ''; display: inline-block; width: .8em; height: .8em; margin-right: .3em; vertical-align: -.04em; background: var(--mk) center / contain no-repeat; }
  `;
  document.head.append(style);

  const stage = document.getElementById('stage');
  const layer = document.createElement('div');
  layer.id = 'manh';
  layer.innerHTML = '<div class="vig"></div><div class="pulse"></div>';
  const lines = document.createElementNS(SVG, 'svg');
  layer.append(lines);
  stage.prepend(layer);                                   // under the page's own readouts and its card
  const pulse = layer.querySelector('.pulse'), gl = document.getElementById('gl'), tag = document.getElementById('tag');
  const power = document.getElementById('power'), legend = document.getElementById('legend'), mini = document.getElementById('mini');
  const images = [];
  const img = key => { const node = new Image(); node.src = M.tiles[key].tile; images.push(node); return node; };

  // the standings: a logo in front of every name, once
  for (const run of A.RUNS) {
    const key = makerOf(run); if (!key || !run.row) continue;
    const node = img(key); node.className = 'mk';
    run.row.querySelector('.who b').prepend(node);
  }

  // ---------------------------------------------------------------- the trackers
  const short = run => run.ref ? 'REFERENCE' : run.label.toUpperCase();
  // a name that fits a small badge: "OPUS 5.5 · AGENT 2" -> "OPUS · 2", "SONNET 5.5 · ONE SHOT" -> "SONNET · 1-SHOT"
  const brief = run => {
    const [model, how = ''] = run.label.toUpperCase().split(' · ');
    const number = how.match(/(\d+)\s*$/);
    return model.split(' ')[0] + ' · ' + (number ? number[1] : how.replace('ONE SHOT', '1-SHOT').replace('ONE REQUEST', '1-REQ'));
  };
  const stroke = (node, color, width) => { node.setAttribute('stroke', color); node.setAttribute('stroke-width', width); };
  const tracks = A.ACTORS.filter(actor => makerOf(actor.run)).map(actor => {
    const key = makerOf(actor.run), group = document.createElementNS(SVG, 'g');
    const under = document.createElementNS(SVG, 'path'), frame = document.createElementNS(SVG, 'path');
    const leadUnder = document.createElementNS(SVG, 'line'), lead = document.createElementNS(SVG, 'line');
    group.append(under, leadUnder, frame, lead); lines.append(group);
    const badge = document.createElement('div');
    badge.className = 'bd';
    badge.append(img(key));
    badge.insertAdjacentHTML('beforeend', '<b></b><u class="st">LOST</u><u class="nt"></u>');
    layer.append(badge);
    const chip = img(key); chip.className = 'chip'; layer.append(chip);
    return { actor, run: actor.run, key, group, under, frame, leadUnder, lead, badge, name: badge.querySelector('b'), note: badge.querySelector('u.nt'), chip,
      wanted: false, born: -1, gone: -1, alpha: 0, lift: 0, hero: null, size: null, hidden: false, text: '' };
  });
  window.__manh = { ready: Promise.all(images.map(node => node.decode().catch(() => null))).then(() => true) };

  const v = new THREE.Vector3(), right = new THREE.Vector3(), measure = document.createElement('canvas').getContext('2d');
  const project = point => { v.copy(point).project(A.camera); return { x: (v.x + 1) / 2 * vw, y: (1 - v.y) / 2 * vh, z: v.z }; };
  const overlap = (a, b, pad) => a.x < b.x + b.w + pad && b.x < a.x + a.w + pad && a.y < b.y + b.h + pad && b.y < a.y + a.h + pad;
  const corners = (cx, cy, r) => { const c = r * 0.44;
    return `M${cx - r},${cy - r + c}V${cy - r}H${cx - r + c}M${cx + r - c},${cy - r}H${cx + r}V${cy - r + c}M${cx + r},${cy + r - c}V${cy + r}H${cx + r - c}M${cx - r + c},${cy + r}H${cx - r}V${cy + r - c}`; };

  let last = { t: null, follow: null, card: false, way: false };
  function draw(fx) {
    const now = window.__film.now() / 1000, dt = fx.dt || 1 / 30, state = A.state, story = A.story, t = state.t;
    const chase = smooth(0, 1, A.view.k);
    const title = document.querySelector('#film .title'), titled = title ? parseFloat(title.style.opacity) || 0 : 0;
    // the top-down shots, once the shot has faded in and the title has gone
    const top = fx.trackers === false ? false : chase < 0.35 && titled < 0.06 && (fx.shot === undefined || fx.shot >= 0.35);
    const cardBox = A.card.classList.contains('on') ? A.card.getBoundingClientRect() : null;
    const boxes = [cardBox, power.getBoundingClientRect(), legend.getBoundingClientRect(), mini.classList.contains('on') ? mini.getBoundingClientRect() : null].filter(Boolean);
    const locks = [], events = [];
    right.setFromMatrixColumn(A.camera.matrixWorld, 0);

    // where every tracked rover is on screen, and whether it is one the story is about
    const seen = [];
    for (const track of tracks) {
      const { actor, run } = track, pose = actor.track.at(t);
      const body = actor.rover && actor.rover.visible ? actor.rover : actor.shadow, S = body.scale.x;
      const centre = project(v.copy(body.position).setY(body.position.y + 0.9 * S));
      const edge = project(v.copy(body.position).setY(body.position.y + 0.9 * S).addScaledVector(right, 2.3 * S));
      const r = clamp(Math.hypot(edge.x - centre.x, edge.y - centre.y) * 1.2, 20, 58);
      const told = !!(story.active && story.active.run === run), hero = told || run.ref || run === state.follow;
      const inside = centre.z > -1 && centre.z < 1 && centre.x > -20 && centre.x < vw + 20 && centre.y > -20 && centre.y < vh + 20;
      const covered = boxes.some(box => centre.x > box.left - 6 && centre.x < box.right + 6 && centre.y + barH > box.top - 8 && centre.y + barH < box.bottom + 6);   // under a readout
      const parked = !hero && !pose.moving && Math.hypot(pose.x - BASE[0], pose.y - BASE[1]) < 9;
      Object.assign(track, { pose, centre, r, heroNow: hero, rank: told ? 3 : run === state.follow ? 2 : hero ? 1 : 0, can: top && inside && !covered && !parked });
      seen.push(track);
    }
    // the story's rovers first; a small badge is dropped while its rover sits on another tracked rover, with some give so it does not flicker
    seen.sort((a, b) => (b.rank - a.rank) || (a.run.index - b.run.index));
    const kept = [];
    let fresh = 0;
    for (const track of seen) {
      let show = track.can;
      if (show && !track.heroNow) for (const other of kept) {
        const gap = Math.hypot(track.centre.x - other.centre.x, track.centre.y - other.centre.y), reach = (track.r + other.r) * (track.wanted ? 0.62 : 0.95);
        if (gap < reach) { show = false; break; }
      }
      if (show) kept.push(track);
      if (show && !track.wanted) { track.born = now + 0.09 * fresh++; track.below = false; track.heard = false; }
      if (!show && track.wanted) track.gone = now;
      track.wanted = show;
    }
    // what a badge must keep clear of: the page's own corner readouts, and the badges placed before it
    const placed = [{ x: 0, y: 0, w: 760 * s / 1.28, h: 78 * s / 1.28 }, { x: 0, y: 60 * s / 1.28, w: 470 * s / 1.28, h: 70 * s / 1.28 }, { x: vw - 560 * s / 1.28, y: 0, w: 560 * s / 1.28, h: 64 * s / 1.28 }];
    for (const track of seen) {
      const { centre, r, run, pose } = track, age = now - track.born;
      const target = track.wanted && age >= 0 ? 1 : 0;
      track.alpha = clamp(track.alpha + (target ? dt / 0.16 : -dt / 0.2), 0, 1);
      // while a tracker is up the page's own small name over that rover is not drawn (it comes back with the next frame)
      const mine = track.alpha > 0.4;
      if (track.hidden !== mine) { track.hidden = mine; track.actor.name.sprite.layers.set(mine ? 1 : 0); track.actor.toast.sprite.layers.set(mine ? 1 : 0); }
      if (track.alpha <= 0.003) { track.group.style.opacity = 0; track.badge.style.opacity = 0; track.lift = 0; continue; }
      if (track.wanted && age >= 0 && !track.heard) { track.heard = true; locks.push(track.heroNow ? 'hero' : 'mini'); }
      const hero = track.heroNow, lost = !pose.alive, role = lost ? 'lost' : run.ref ? 'ref' : run === state.follow ? 'on' : 'shade';
      const color = role === 'lost' ? RED : role === 'ref' ? GOLD : role === 'on' ? ICE : INK;
      const key = `${hero}|${role}`;
      if (track.size !== key) { track.size = key; track.badge.className = `bd ${hero ? 'hero' : 'mini'}${lost ? ' lost' : ''}`; track.badge.style.color = color; track.w = 0; }
      const text = hero ? short(run) : brief(run);
      if (track.text !== text) { track.text = text; track.name.textContent = text; track.w = 0; }
      // the page's one-shot notes (+0.25, MISS, STOPPED) ride on the badge instead of over the hidden name
      const toast = track.actor.toast, noted = toast.sprite.visible && toast.key ? toast.key.split('|') : null, noteKey = noted ? noted.join('|') : '';
      if (track.noteKey !== noteKey) {
        track.noteKey = noteKey; track.note.classList.toggle('show', !!noted); track.w = 0;
        if (noted) { track.note.textContent = noted[0]; track.note.style.color = noted[1]; }
      }
      if (!track.w) { track.w = track.badge.offsetWidth; track.h = track.badge.offsetHeight; }
      // the frame closes in on the rover, the line grows, the badge opens
      const lock = outCubic(age / 0.36), grow = clamp((age - 0.16) / 0.2, 0, 1), open = smooth(0, 1, (age - 0.26) / 0.24);
      const breathe = hero ? 1 + 0.035 * Math.sin(now * 5.2 + run.index) : 1, rr = r * lerp(2.5, 1, lock) * breathe;
      const lead = hero ? 26 : 16, w = track.w, h = track.h;
      const bx = clamp(centre.x - w / 2, 10, vw - w - 10), above = centre.y - r - lead - h, under = centre.y + r + lead;
      const free = y => !placed.some(other => overlap({ x: bx, y, w, h }, other, 6));
      // above the rover; if that is taken, below it; a side once chosen is kept while it stays free, so a badge does not hop
      let below = track.below && free(under) && under + h < vh - 8;
      if (!below && (above < 8 || !free(above)) && free(under) && under + h < vh - 8) below = true;
      track.below = below;
      let by = below ? under : above, lift = 0;
      for (let tries = 0; tries < 7; tries++) {
        const box = { x: bx, y: by + (below ? lift : -lift), w, h };
        if (!placed.some(other => overlap(box, other, 6))) break;
        lift += h + 8;
      }
      track.lift += (lift - track.lift) * (1 - Math.exp(-dt * 9));
      by += below ? track.lift : -track.lift;
      placed.push({ x: bx, y: by, w, h });
      const width = hero ? 3 : 2, path = corners(centre.x, centre.y, rr);
      track.group.style.opacity = (track.alpha * Math.min(1, lock * 2.2) * (hero ? 1 : 0.82)).toFixed(3);
      track.under.setAttribute('d', path); stroke(track.under, 'rgba(0,0,0,.7)', width + 3);
      track.frame.setAttribute('d', path); stroke(track.frame, color, width);
      const y0 = below ? centre.y + rr : centre.y - rr, y1 = below ? by : by + h, x1 = clamp(centre.x, bx + 6, bx + w - 6);
      for (const node of [track.leadUnder, track.lead]) {
        node.setAttribute('x1', centre.x); node.setAttribute('y1', y0);
        node.setAttribute('x2', lerp(centre.x, x1, grow)); node.setAttribute('y2', lerp(y0, y1, grow));
      }
      stroke(track.leadUnder, 'rgba(0,0,0,.7)', width + 3); stroke(track.lead, color, width);
      track.badge.style.opacity = (track.alpha * open * (hero ? 1 : 0.92)).toFixed(3);
      track.badge.style.transform = `translate(${bx.toFixed(1)}px, ${(by + (1 - open) * (below ? -7 : 7)).toFixed(1)}px)`;
    }

    // the chase camera keeps the page's own name label: the logo sits to its left
    const kpx = 2 * Math.tan(THREE.MathUtils.degToRad(A.camera.fov) / 2) / vh;
    for (const track of tracks) {
      const sprite = track.actor.name.sprite, label = track.actor.name;
      let alpha = 0;
      if (chase > 0.65 && sprite.visible && !track.hidden && label.key && sprite.scale.y > 0) {
        const at = project(sprite.position), far = Math.max(0.5, A.camera.position.distanceTo(sprite.position));
        const tall = sprite.scale.y / (kpx * far);                    // the label's height on screen, in pixels
        if (at.z > -1 && at.z < 1 && tall > 14) {
          const text = label.key.split('|')[0], canvas = label.canvas;
          measure.font = `700 ${Math.round(canvas.height * 0.48)}px ${getComputedStyle(document.body).fontFamily}`;
          const wide = measure.measureText(text).width * tall / canvas.height, size = Math.round(tall * 0.74);
          const x = at.x - wide / 2 - size - tall * 0.2, y = at.y + sprite.center.y * tall - tall * 0.325 - size / 2;
          if (x > 4 && x < vw - size && y > 4 && y < vh - size) {
            alpha = smooth(0.65, 0.95, chase) * sprite.material.opacity;
            track.chip.style.width = track.chip.style.height = size + 'px';
            track.chip.style.transform = `translate(${x.toFixed(1)}px, ${y.toFixed(1)}px)`;
          }
        }
      }
      track.chip.style.opacity = alpha.toFixed(3);
    }

    // the top-left tag in the chase camera names the followed run: its logo goes in front
    const followed = state.follow, tagKey = state.cam === 'chase' && followed ? makerOf(followed) : null;
    tag.classList.toggle('mk', !!tagKey);
    if (tagKey && tag.dataset.mk !== tagKey) { tag.dataset.mk = tagKey; tag.style.setProperty('--mk', `url("${M.tiles[tagKey].tile}")`); }

    // the card that explains a moment: whose rover it was, at a glance
    const moment = story.active, cardOn = !!cardBox && !!moment;
    if (cardOn && !A.card.querySelector('.mk')) {
      const key = makerOf(moment.run);
      if (key) {
        const node = img(key); node.className = 'mk'; A.card.prepend(node); A.card.classList.add('mk-on');
        const by = moment.run.ref ? 'A PLANNER, NOT A MODEL' : `${M.tiles[key].family} · ${M.tiles[key].name}`;
        A.card.querySelector('b').insertAdjacentHTML('beforeend', `<small>${by}</small>`);
      }
    }
    if (cardOn && !last.card) events.push({ k: 'card', tone: moment.kind.startsWith('ref') ? 'gold' : 'bad' });
    const held = moment ? (A.HOLD[moment.kind] || 5) - story.hold : 0, way = !!(moment && moment.path && held > 0.2);
    if (way && !last.way) events.push({ k: 'way', open: !!moment.open });
    last.card = cardOn; last.way = way;

    // a battery has just run flat: the picture drops dark for a moment, as if the power had gone, red closes in
    // from the edges, and the ground comes back with some of its colour drained
    const since = fx.since === undefined || fx.since === null ? -1 : fx.since;
    const cut = since >= 0 ? Math.exp(-since / 0.17) : 0, drained = smooth(0, 1.5, since);
    pulse.style.opacity = since >= 0 ? Math.exp(-since / 0.42).toFixed(3) : '0';
    gl.style.filter = since >= 0 ? `saturate(${lerp(1, 0.76, drained).toFixed(3)}) brightness(${(lerp(1, 0.95, drained) * (1 - 0.52 * cut)).toFixed(3)})` : '';

    // for the sound: what the followed rover is doing, and what happened since the last frame
    const run = followed || A.REF, pose = run.track.at(t);
    if (last.t !== null && last.follow === run.id && t > last.t && t - last.t < 1.5) {
      for (const [who, one] of [['on', run], ['ref', A.REF]]) {
        if (who === 'ref' && one === run) continue;
        for (const sample of one.track.samples) if (sample.t > last.t && sample.t <= t) events.push({ k: sample.ok ? 'sample' : 'late', who });
        for (const event of one.track.raw.events) if (event.t > last.t && event.t <= t) events.push({ k: event.k, who });
      }
    }
    last.t = t; last.follow = run.id;
    return { t: +t.toFixed(3), playing: state.playing, chase: +chase.toFixed(3), weight: +story.weight.toFixed(3), follow: run.id,
      x: +pose.x.toFixed(2), y: +pose.y.toFixed(2), alive: pose.alive, moving: pose.moving, ground: A.classAt(pose.x, pose.y),
      slope: +A.slopeAt(pose.x, pose.y).toFixed(3), battery: +(pose.battery / A.CFG.battery).toFixed(4), shown: kept.length, locks, events };
  }
  window.__manh.draw = draw;
})();
