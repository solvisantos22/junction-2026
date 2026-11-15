// Manh's add-on for the demo page while it is recorded (tools/manh_demo). It draws on top of
// Kristján's page and changes nothing in it:
//
// - over every rover, the mark of the lab whose model is driving it, as a small solid object
//   that floats just above the rover and sways toward the camera (window.__MANH.icons, from
//   makers.py). This is design C of the icon drafts, the one Manh picked on 15 November: the
//   bare mark, a hair-thin dark outline, life-size beside the rover up close and never smaller
//   than OVERHEAD pixels from above. It replaces the frame, line and badge of the first cut.
//   The reference, which is a planner and not a model, carries a gold route instead. A rover
//   whose battery has run out loses its mark: the light goes out, and the page's own red LOST
//   label takes its place;
// - the same logo on the card that explains a failure, in the standings and in the top-left tag; and, when the
//   replay carries models of several tiers (window.__MANH.tiers), each one's tier beside its name;
// - with window.__MANH.cards = 'score', that card as a score-card instead of two paragraphs: the headline,
//   three large numbers with a small label each, and a second later one line with what would have saved
//   the rover or why the reference's way works. The numbers are read out of the page's own sentences;
//   the sentences themselves are left to the narrator. A kind of card this file does not know keeps
//   the page's text;
// - a soft vignette, and where a battery runs flat the picture dropping dark for a moment, red
//   closing in from the edges and the colour draining away;
// - what the sound track needs, returned from every draw(): how fast the followed rover is
//   moving and on what ground, and what just happened (a sample, a miss, a safety stop, a
//   mark arriving over a rover in a top-down shot, a card coming up).
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
  const back = x => { x = clamp(x, 0, 1); const c = 1.7; return 1 + (c + 1) * Math.pow(x - 1, 3) + c * Math.pow(x - 1, 2); };     // arrives a little past, then settles
  const makerOf = run => run.ref ? 'reference' : (M.makers[run.id] || null);
  const BASE = A.DATA.world.base;                           // the lander: where rovers start and must return to

  const style = document.createElement('style');
  style.textContent = `
    #manh { position: absolute; inset: 0; overflow: hidden; pointer-events: none; }
    #manh .vig { position: absolute; inset: 0; background: radial-gradient(ellipse 78% 74% at 50% 47%, rgba(0,0,0,0) 54%, rgba(8,4,3,.40) 100%); }
    #manh .pulse { position: absolute; inset: 0; opacity: 0; background: radial-gradient(ellipse 72% 68% at 50% 50%, rgba(255,36,18,0) 30%, rgba(255,36,18,.8) 100%); }
    #moment .mk { position: absolute; left: calc(20px * var(--s)); top: calc(15px * var(--s)); width: calc(50px * var(--s)); height: calc(50px * var(--s)); }
    #moment.mk-on > i, #moment.mk-on > b { margin-left: calc(63px * var(--s)); }
    #moment b small { margin-left: .9em; font-size: .8em; font-weight: 400; letter-spacing: .14em; color: var(--dim); }
    .row .who b img.mk { height: 1.02em; width: 1.02em; margin-right: .42em; vertical-align: -.14em; }
    #rows.tiers .cell { flex-basis: 36%; }                 /* the bar gives up some width to the tier beside it */
    .cells .tier { flex: 0 0 auto; font-size: calc(var(--rh) * .2); letter-spacing: .15em; color: var(--dim); white-space: nowrap; }
    #film .caption { font-size: 50px !important; letter-spacing: .075em !important; }   /* Barlow Condensed is wider than the DIN Condensed the captions were sized for */
    #moment.sc { width: min(calc(700px * var(--s)), 88%); padding-bottom: calc(15px * var(--s)); }
    #moment.sc > p, #moment.sc > i span { display: none; }
    #moment .sc-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: calc(16px * var(--s)); margin-top: calc(11px * var(--s)); padding-top: calc(13px * var(--s)); border-top: 1px solid rgba(243, 234, 217, .16); }
    #moment .sc-row b { display: block; margin: 0; font-size: calc(48px * var(--s)); letter-spacing: .03em; line-height: .95; color: var(--ink); white-space: nowrap; }
    #moment .sc-row b.bad { color: var(--red); }
    #moment.gold .sc-row b { color: var(--gold); }
    #moment .sc-row b small { margin-left: .1em; font-size: .46em; font-weight: 700; letter-spacing: .08em; color: inherit; }
    #moment .sc-row span { display: block; margin-top: calc(5px * var(--s)); font-size: calc(14px * var(--s)); letter-spacing: .15em; color: var(--dim); white-space: nowrap; }
    #moment .sc-then { margin-top: calc(13px * var(--s)); padding-top: calc(10px * var(--s)); border-top: 1px solid rgba(243, 234, 217, .16); font-size: calc(19px * var(--s)); letter-spacing: .12em; color: var(--lime); white-space: nowrap; }
    #moment.gold .sc-then { color: var(--gold); }
    #moment .skip { display: none !important; }            /* the page's own "Skip" button on a story card is for a viewer at the page, not for the film */
    #tag.mk b::before { content: ''; display: inline-block; width: .8em; height: .8em; margin-right: .3em; vertical-align: -.04em; background: var(--mk) center / contain no-repeat; }
  `;
  document.head.append(style);

  const stage = document.getElementById('stage');
  const layer = document.createElement('div');
  layer.id = 'manh';
  layer.innerHTML = '<div class="vig"></div><div class="pulse"></div>';
  stage.prepend(layer);                                   // under the page's own readouts and its card
  const pulse = layer.querySelector('.pulse'), gl = document.getElementById('gl'), tag = document.getElementById('tag');
  const images = [];
  const img = key => { const node = new Image(); node.src = M.tiles[key].tile; images.push(node); return node; };

  // the standings: a logo in front of every name, once
  for (const run of A.RUNS) {
    const key = makerOf(run); if (!key || !run.row) continue;
    const node = img(key), name = run.row.querySelector('.who b'); node.className = 'mk';
    name.prepend(node);
    if (M.tiers && M.tiers[run.id]) {                       // FAST, BALANCED or FLAGSHIP, between the bar and the small print
      run.cell.insertAdjacentHTML('afterend', `<span class="tier">${M.tiers[run.id]}</span>`);
      document.getElementById('rows').classList.add('tiers');
    }
  }
  window.__manh = { ready: Promise.all(images.map(node => node.decode().catch(() => null))).then(() => true) };

  // ---------------------------------------------------------------- the floating marks
  const OVERHEAD = 29, CLOSE = 110, TOLD = 1.3;            // pixels: the smallest from above (Manh's second note on size), the largest up close; and how much the story's own rover gains
  const SVGLoader = M.icons ? new Function('THREE', M.icons.loader)(THREE) : null;
  const solid = (color, more = {}) => new THREE.MeshStandardMaterial({ color, roughness: 0.3, metalness: 0.04, fog: false, emissive: color, emissiveIntensity: 0.55, ...more });
  function build(spec) {                                    // one unit across, centred, facing +z
    const turning = new THREE.Group(), icon = new THREE.Group(); icon.add(turning);
    if (spec.route) {                                       // the reference's route: a bent line between two points
      const u = 0.49, line = new THREE.CatmullRomCurve3([[-0.78, -0.72], [-0.3, 0.3], [0.22, -0.28], [0.78, 0.72]].map(([x, y]) => new THREE.Vector3(x * u, y * u, 0)), false, 'catmullrom', 0.05);
      turning.add(new THREE.Mesh(new THREE.TubeGeometry(line, 40, 0.07, 10), solid(spec.text)));
      for (const [x, y] of [[-0.78, -0.72], [0.78, 0.72]]) { const dot = new THREE.Mesh(new THREE.SphereGeometry(0.13, 18, 12), solid(spec.text)); dot.position.set(x * u, y * u, 0); turning.add(dot); }
    } else {
      const shapes = [], across = 0.98, deep = 0.2;
      for (const path of new SVGLoader().parse(`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="${spec.path}"/></svg>`).paths) shapes.push(...SVGLoader.createShapes(path));
      const cut = offset => { const g = new THREE.ExtrudeGeometry(shapes, { depth: deep * 24 / across, bevelEnabled: true, bevelThickness: 0.2, bevelSize: 0.14, bevelOffset: offset, bevelSegments: 2, curveSegments: 8 });
        g.center(); g.scale(across / 24, across / 24, across / 24); g.rotateX(Math.PI); return g; };                 // an SVG's y runs down
      const mark = new THREE.Mesh(cut(0), solid(spec.text));
      mark.add(new THREE.Mesh(cut(0.45), new THREE.MeshBasicMaterial({ color: 0x1b1310, side: THREE.BackSide, fog: false })));   // the outline: the same shape grown a hair, seen only where it sticks out
      turning.add(mark);
    }
    icon.userData = { turning };
    return icon;
  }
  const riders = !M.icons ? [] : A.ACTORS.map(actor => {
    const key = makerOf(actor.run), spec = key && M.icons.marks[key];
    if (!spec) return null;
    const icon = build(spec); icon.visible = false; A.scene.add(icon);
    return { actor, run: actor.run, icon, k: 0, born: -1, shown: false, hidden: false, heard: true, phase: actor.run.index * 1.7 };
  }).filter(Boolean);

  // ---------------------------------------------------------------- the card as a score-card
  // For each kind of moment: a headline, three numbers with their labels, and the line that follows. The numbers
  // come out of the page's own sentences (viewer/traverse_story.py writes them); null when a sentence has changed.
  const found = (text, pattern) => { const hit = (text || '').match(pattern); return hit ? hit.slice(1) : null; };
  const SCORE = {
    lost(m) {
      const far = found(m.did, /(\d+) m from the lander/), carried = found(m.did, /(\d+) samples/), floor = found(m.better, /below ([\d.]+)%/);
      if (!far || !carried) return null;
      return { head: 'BATTERY FLAT', stats: [[far[0], 'M', 'FROM HOME'], [carried[0], '', carried[0] === '1' ? 'SAMPLE LOST' : 'SAMPLES LOST'], ['0', '', 'POINTS HERE', 'bad']],
        then: m.wait ? 'A SHORT WAIT FOR THE SUN WOULD HAVE SAVED IT' : floor ? `THE REFERENCE NEVER WENT BELOW ${Math.floor(floor[0])}% HERE` : null };
    },
    ref_wait(m) {
      const charge = found(m.did, /Battery ([\d.]+)%/), stops = found(m.did, /(\d+) times/);
      if (!charge || !stops) return null;
      const lowest = Math.min(...m.run.track.raw.b) / A.CFG.battery * 100;
      return { head: 'WAITS FOR THE SUN', stats: [[String(Math.round(charge[0])), '%', 'BATTERY LEFT'], [stops[0], '', 'STOPS TO CHARGE'], [String(Math.floor(lowest)), '%', 'ITS LOWEST ALL DAY']],
        then: 'IT CHECKS THE BATTERY BEFORE EVERY LEG' };
    },
    misses(m) {
      const reach = found(m.did, /Sampled ([\d.]+) m from the nearest target; it must be within ([\d.]+) m/), count = found(m.did, /(\d+) missed samples/), ours = found(m.better, /reference missed (\d+)/);
      if (!reach || !count || !ours) return null;
      return { head: 'MISSED SAMPLE', stats: [[String(Math.round((reach[0] - reach[1]) * 100)), 'CM', 'TOO FAR'], [count[0], '', 'MISSES HERE', 'bad'], [ours[0], '', 'FOR THE REFERENCE']],
        then: 'THE REFERENCE AIMS WHERE THE ROVER WILL BE' };
    },
    steep(m) {
      const limit = found(m.did, /([\d.]+)% tilt limit/), stops = found(m.did, /(\d+) safety stops/), ours = found(m.better, /reference stopped (\d+) times/);
      if (!limit || !stops || !ours) return null;
      return { head: 'TOO STEEP', stats: [[limit[0], '%', 'TILT LIMIT'], [stops[0], '', 'SAFETY STOPS HERE', 'bad'], [ours[0], '', 'FOR THE REFERENCE']],
        then: "EVERY STOP WIPES THE ROVER'S ORDERS" };
    },
  };
  function scoreCard(m, now) {                                // rebuild the page's card once, when it has just come up
    const made = SCORE[m.kind] ? SCORE[m.kind](m) : null;
    if (!made) return false;
    const card = A.card, head = card.querySelector('i');
    if (head && head.firstChild && head.firstChild.nodeType === 3) head.firstChild.textContent = made.head;
    card.insertAdjacentHTML('beforeend', `<div class="sc-row">${made.stats.map(([big, unit, label, tone]) =>
      `<div style="opacity:0"><b${tone ? ` class="${tone}"` : ''}>${big}${unit ? `<small>${unit}</small>` : ''}</b><span>${label}</span></div>`).join('')}</div>`
      + (made.then ? `<div class="sc-then" style="opacity:0">${made.then}</div>` : ''));
    card.classList.add('sc'); card.dataset.sc = String(now);
    return true;
  }

  let last = { t: null, follow: null, card: false, way: false, then: false };
  function draw(fx) {
    const now = window.__film.now() / 1000, dt = fx.dt || 1 / 30, state = A.state, story = A.story, t = state.t;
    const chase = smooth(0, 1, A.view.k), overhead = chase < 0.35;
    const title = document.querySelector('#film .title'), titled = title ? parseFloat(title.style.opacity) || 0 : 0;
    // marks are up once the shot has faded in; from above they wait for the title to go. A piece that brings icons of its own switches them off.
    const off = fx.trackers === false, ready = !off && (fx.shot === undefined || fx.shot >= 0.35) && !(overhead && titled >= 0.06);
    const cardOn = A.card.classList.contains('on') && !!story.active;
    const locks = [], events = [], camera = A.camera, kpx = 2 * Math.tan(THREE.MathUtils.degToRad(camera.fov) / 2) / vh;
    let fresh = 0, shown = 0;
    for (const rider of riders) {
      const { actor, run, icon } = rider, pose = actor.track.at(t);
      const body = actor.rover && actor.rover.visible ? actor.rover : actor.shadow, S = body.scale.x;
      const told = !!(story.active && story.active.run === run), hero = told || run.ref || run === state.follow;
      const parked = !hero && !pose.moving && Math.hypot(pose.x - BASE[0], pose.y - BASE[1]) < 9;       // the pile of rovers standing at the lander stays bare
      const want = ready && pose.alive && !parked;
      // from above the marks arrive one after another and each is heard once; behind a rover they are simply there
      if (want && !rider.shown) { rider.born = now + (overhead ? 0.09 * fresh++ : 0); rider.heard = !overhead; }
      rider.shown = want;
      const age = now - rider.born;
      rider.k = clamp(rider.k + (want && age >= 0 ? dt / 0.3 : -dt / 0.22), 0, 1);
      if (want && age >= 0 && !rider.heard) { rider.heard = true; locks.push(hero ? 'hero' : 'mini'); }
      const hide = rider.k > 0.4;                           // the page's own name over a rover is not drawn while the rover carries its mark
      if (rider.hidden !== hide) { rider.hidden = hide; actor.name.sprite.layers.set(hide ? 1 : 0); }
      icon.visible = rider.k > 0.003;
      if (!icon.visible) continue;
      shown++;
      const far = Math.max(1, camera.position.distanceTo(body.position));
      const size = clamp(S, OVERHEAD * kpx * far / 0.98, CLOSE * kpx * far / 0.98) * (told ? TOLD : 1);   // life-size up close, never lost from far above
      const top = body.position.y + 2.2 * S, bob = 0.05 * size * Math.sin(now * 2.1 + rider.phase), sink = want ? 0 : (1 - rider.k) * 0.5 * size;
      icon.position.set(body.position.x, top + 0.95 * size + bob - sink, body.position.z);
      icon.scale.setScalar(Math.max(0.001, size * (want ? back(rider.k) : rider.k)));
      icon.userData.turning.rotation.y = Math.atan2(camera.position.x - icon.position.x, camera.position.z - icon.position.z) + 0.6 * Math.sin(now * 1.5 + rider.phase);
      const toast = actor.toast.sprite;                     // the page's one-shot notes (+0.25, MISS, STOPPED) sit on top of the mark
      if (toast.visible) toast.position.set(icon.position.x, icon.position.y + 0.62 * size, icon.position.z);
    }
    if (riders.length && !off) A.renderer.render(A.scene, A.camera);       // once more, with the marks where the rovers are in this frame

    // the top-left tag in the chase camera names the followed run: its logo goes in front
    const followed = state.follow, tagKey = state.cam === 'chase' && followed ? makerOf(followed) : null;
    tag.classList.toggle('mk', !!tagKey);
    if (tagKey && tag.dataset.mk !== tagKey) { tag.dataset.mk = tagKey; tag.style.setProperty('--mk', `url("${M.tiles[tagKey].tile}")`); }

    // the card that explains a moment: whose rover it was, at a glance
    const moment = story.active;
    if (cardOn && !A.card.querySelector('.mk')) {
      const key = makerOf(moment.run);
      if (key) {
        const node = img(key); node.className = 'mk'; A.card.prepend(node); A.card.classList.add('mk-on');
        const tier = M.tiers && M.tiers[moment.run.id];
        const by = moment.run.ref ? 'A PLANNER, NOT A MODEL' : `${tier || M.tiles[key].family} · ${M.tiles[key].name}`.toUpperCase();
        A.card.querySelector('b').insertAdjacentHTML('beforeend', `<small>${by}</small>`);
      }
    }
    // as a score-card: the numbers come up one after another, and a moment later the line that follows them
    let then = false;
    if (cardOn && M.cards === 'score') {
      if (!A.card.querySelector('.sc-row') && !A.card.dataset.plain && !scoreCard(moment, now)) A.card.dataset.plain = '1';
      const since = now - parseFloat(A.card.dataset.sc || now), tiles = A.card.querySelectorAll('.sc-row > div'), line = A.card.querySelector('.sc-then');
      tiles.forEach((node, i) => { const k = smooth(0, 1, (since - 0.25 - i * 0.16) / 0.32); node.style.opacity = k.toFixed(3); node.style.transform = `translateY(${((1 - k) * 12).toFixed(1)}px)`; });
      if (line) { const k = smooth(0, 1, (since - 1.3) / 0.4); line.style.opacity = k.toFixed(3); then = since >= 1.3; }
    }
    if (!cardOn) { delete A.card.dataset.plain; delete A.card.dataset.sc; }      // the dress stays on while the card fades out: the page's paragraphs must not show through (Manh saw them at 1:04)
    if (then && !last.then) events.push({ k: 'then' });
    last.then = then;
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
      slope: +A.slopeAt(pose.x, pose.y).toFixed(3), battery: +(pose.battery / A.CFG.battery).toFixed(4), shown, locks, events };
  }
  window.__manh.draw = draw;
})();
