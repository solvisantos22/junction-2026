// The four floating-icon drafts over the real environment, so they can be judged where they would be used
// (Manh, 15 November: "show me the real environment in the background so that I can create a fair assessment").
//
// The same two moments of the real demo page are played once for each kind of icon: a few seconds from the chase
// camera behind a driving rover, then a few seconds from the top-down view with every rover on the map. Each
// rover carries the mark of the lab whose model drives it (all Claude in these runs: three pips for Opus, two for
// Sonnet, one for Haiku); the reference, which is a planner, carries a gold route. The page's own name labels and
// the trackers of the first cut are off, so the icon is the only thing that says who is who.
//
// An icon is drawn life-size with the rover when the camera is close, and never smaller than SMALLEST pixels on
// screen, so it stays readable from far above. It is a separate file from the studio drafts (icons.js) on purpose:
// that file is being changed by another session tonight; the icon builders here are the ones Manh saw and liked.
(() => {
  const A = window.LIGHTLAG_TRAVERSE_APP, T = A.THREE, P = window.__PIECE;
  const SVGLoader = new Function('THREE', P.loader)(T);
  const s = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--s')) || 1;
  const W = window.innerWidth, H = window.innerHeight, barH = Math.round(42 * s), boardW = Math.round(340 * s), vw = W - boardW, vh = H - barH;
  const SHOW = P.show || 6.4, SMALLEST = 44, LARGEST = 110;
  const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
  const smooth = (a, b, x) => { const t = clamp((x - a) / (b - a), 0, 1); return t * t * (3 - 2 * t); };
  const back = x => { x = clamp(x, 0, 1); const c = 1.7; return 1 + (c + 1) * Math.pow(x - 1, 3) + c * Math.pow(x - 1, 2); };
  const KINDS = [['TOKEN', 'A COIN THAT TURNS'], ['TILE', 'FACES YOU · PIPS FOR THE TIER'], ['MARK', 'THE MARK AS A SOLID OBJECT'], ['BEACON', 'A HAIRLINE AND A RING ON THE GROUND']];

  // ---------------------------------------------------------------- the parts an icon is made of (as in the studio drafts)
  const solid = (color, { outline, ...more } = {}) => new T.MeshStandardMaterial({ color, roughness: 0.42, metalness: 0.04, fog: false, ...more });
  function mark(spec, across, depth, color, more) {
    if (spec.route) {                                                 // the reference's route: a bent line between two points
      const group = new T.Group(), material = solid(color, more), u = across / 2;
      const line = new T.CatmullRomCurve3([[-0.78, -0.72], [-0.3, 0.3], [0.22, -0.28], [0.78, 0.72]].map(([x, y]) => new T.Vector3(x * u, y * u, 0)), false, 'catmullrom', 0.05);
      group.add(new T.Mesh(new T.TubeGeometry(line, 40, across * 0.07, 10), material));
      for (const [x, y] of [[-0.78, -0.72], [0.78, 0.72]]) { const dot = new T.Mesh(new T.SphereGeometry(across * 0.13, 18, 12), material); dot.position.set(x * u, y * u, 0); group.add(dot); }
      group.scale.z = clamp(depth / (across * 0.14), 0.35, 1.4);
      return group;
    }
    const data = new SVGLoader().parse(`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="${spec.path}"/></svg>`), shapes = [];
    for (const path of data.paths) shapes.push(...SVGLoader.createShapes(path));
    const geometry = new T.ExtrudeGeometry(shapes, { depth: depth * 24 / across, bevelEnabled: true, bevelThickness: 0.2, bevelSize: 0.14, bevelSegments: 2, curveSegments: 8 });
    geometry.center(); geometry.scale(across / 24, across / 24, across / 24); geometry.rotateX(Math.PI);
    const mesh = new T.Mesh(geometry, solid(color, more));
    if (more && more.outline) {                                       // a hair of dark around it, so it parts from ground of its own colour
      const grown = new T.ExtrudeGeometry(shapes, { depth: depth * 24 / across, bevelEnabled: true, bevelThickness: 0.2, bevelSize: 0.14, bevelOffset: more.outline, bevelSegments: 2, curveSegments: 8 });
      grown.center(); grown.scale(across / 24, across / 24, across / 24); grown.rotateX(Math.PI);
      mesh.add(new T.Mesh(grown, new T.MeshBasicMaterial({ color: 0x1b1310, side: T.BackSide, fog: false })));
    }
    return mesh;
  }
  function rounded(w, h, r) {
    const p = new T.Shape(), x = -w / 2, y = -h / 2;
    p.moveTo(x + r, y); p.lineTo(x + w - r, y); p.quadraticCurveTo(x + w, y, x + w, y + r); p.lineTo(x + w, y + h - r); p.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
    p.lineTo(x + r, y + h); p.quadraticCurveTo(x, y + h, x, y + h - r); p.lineTo(x, y + r); p.quadraticCurveTo(x, y, x + r, y);
    return p;
  }
  function slab(spec, size) {
    const group = new T.Group(), thick = size * 0.13;
    group.add(new T.Mesh(new T.ExtrudeGeometry(rounded(size, size, size * 0.22), { depth: thick, bevelEnabled: true, bevelThickness: size * 0.025, bevelSize: size * 0.025, bevelSegments: 3, curveSegments: 12 }).translate(0, 0, -thick / 2),
      solid(spec.tile, { emissive: spec.tile, emissiveIntensity: 0.18 })));
    const front = mark(spec, size * 0.62, size * 0.05, spec.ink, { emissive: spec.ink, emissiveIntensity: 0.12 }); front.position.z = thick / 2 + size * 0.045; group.add(front);
    return group;
  }
  function pips(spec, tier, group) {                                   // one pip for the fast model, three for the flagship; none for the reference
    for (let i = 0; i < 3 && tier; i++) {
      const lit = i < tier, pip = new T.Mesh(new T.SphereGeometry(0.062, 20, 14), solid(lit ? spec.text : 0x3a2f2a, lit ? { emissive: spec.text, emissiveIntensity: 0.7 } : {}));
      pip.position.set((i - 1) * 0.2, -0.66, 0); group.add(pip);
    }
  }
  const BUILD = {
    TOKEN(spec) {
      const group = new T.Group(), turning = new T.Group(); group.add(turning);
      turning.add(new T.Mesh(new T.CylinderGeometry(0.5, 0.5, 0.12, 64).rotateX(Math.PI / 2), solid(spec.tile, { emissive: spec.tile, emissiveIntensity: 0.18 })));
      turning.add(new T.Mesh(new T.TorusGeometry(0.5, 0.045, 14, 72), solid(spec.text, { emissive: spec.text, emissiveIntensity: 0.4 })));
      for (const side of [1, -1]) { const face = mark(spec, 0.6, 0.035, spec.ink, { emissive: spec.ink, emissiveIntensity: 0.12 }); face.position.z = side * 0.085; if (side < 0) face.rotation.y = Math.PI; turning.add(face); }
      group.userData = { turning };
      return group;
    },
    TILE(spec, tier) {
      const group = new T.Group(), facing = new T.Group(); group.add(facing);
      facing.add(slab(spec, 0.92)); pips(spec, tier, facing);
      group.userData = { facing };
      return group;
    },
    MARK(spec) {
      const group = new T.Group(), turning = new T.Group(); group.add(turning);
      turning.add(mark(spec, 0.98, 0.2, spec.text, { emissive: spec.text, emissiveIntensity: 0.55, roughness: 0.3, outline: 0.45 }));
      group.userData = { turning, sways: true, smallest: 29 };       // Manh, 15 November: smaller from overhead (twice), and a tiny outline
      return group;
    },
    BEACON(spec, tier) {
      const group = BUILD.TILE(spec, tier);
      const line = new T.Mesh(new T.CylinderGeometry(0.5, 0.5, 1, 8), new T.MeshBasicMaterial({ color: spec.text, transparent: true, opacity: 0.9, fog: false, depthTest: false }));
      const ring = new T.Mesh(new T.RingGeometry(0.93, 1, 72).rotateX(-Math.PI / 2), new T.MeshBasicMaterial({ color: spec.text, transparent: true, opacity: 0.9, fog: false, depthTest: false, side: T.DoubleSide }));
      line.renderOrder = ring.renderOrder = 8;
      group.userData = { ...group.userData, line, ring };
      return group;
    },
  };

  // one icon of each kind for every rover that has a maker, and for the reference
  const tierOf = run => (/opus|sol|carbon/i.test(run.label) ? 3 : /sonnet|terra|argon/i.test(run.label) ? 2 : 1);
  const riders = A.ACTORS.map(actor => {
    const key = actor.run.ref ? 'reference' : P.makers[actor.run.id], spec = key && P.marks[key];
    if (!spec) return null;
    actor.name.sprite.layers.set(1); actor.toast.sprite.layers.set(1);              // the icon stands in for the page's name label
    const icons = KINDS.map(([kind]) => {
      const icon = BUILD[kind](spec, actor.run.ref ? 0 : tierOf(actor.run));
      icon.visible = false; A.scene.add(icon);
      if (icon.userData.line) { icon.userData.line.visible = icon.userData.ring.visible = false; A.scene.add(icon.userData.line, icon.userData.ring); }
      return icon;
    });
    return { actor, icons, phase: actor.run.index * 1.7 };
  }).filter(Boolean);

  // the first cut's logo chip beside the page's name label would float on its own now that the label is off
  document.head.insertAdjacentHTML('beforeend', '<style>#manh .chip { display: none !important; }</style>');

  // ---------------------------------------------------------------- which kind is on, written on a flat layer
  const sheet = document.createElement('canvas');
  sheet.width = W; sheet.height = H;
  sheet.style.cssText = 'position:fixed;inset:0;width:100vw;height:100vh;z-index:40;pointer-events:none';
  document.body.append(sheet);
  const g = sheet.getContext('2d'), FONT = getComputedStyle(document.body).fontFamily;

  function draw(t) {
    const which = Math.min(KINDS.length - 1, Math.floor(t / SHOW)), into = t - which * SHOW, out = clamp((SHOW - into) / 0.25, 0, 1), arrive = Math.max(0.001, back(into / 0.5) * out);
    const camera = A.camera, kpx = 2 * Math.tan(T.MathUtils.degToRad(camera.fov) / 2) / vh;
    for (const rider of riders) {
      const { actor } = rider, body = actor.rover && actor.rover.visible ? actor.rover : actor.shadow, S = body.scale.x;
      const far = Math.max(1, camera.position.distanceTo(body.position));
      rider.icons.forEach((icon, k) => {
        const on = k === which, data = icon.userData;
        const size = clamp(S, (data.smallest || SMALLEST) * kpx * far / 0.92, LARGEST * kpx * far / 0.92);     // life-size up close, never lost from far above
        icon.visible = on;
        if (data.line) data.line.visible = data.ring.visible = on;
        if (!on) return;
        const top = body.position.y + 2.2 * S, bob = 0.05 * size * Math.sin(t * 2.1 + rider.phase), gap = data.line ? 0.75 : 0.35;
        icon.position.set(body.position.x, top + (gap + 0.6) * size + bob, body.position.z);
        icon.scale.setScalar(size * arrive);
        if (data.turning) data.turning.rotation.y = data.sways ? Math.atan2(camera.position.x - icon.position.x, camera.position.z - icon.position.z) + 0.6 * Math.sin(t * 1.5 + rider.phase) : t * 1.15 + rider.phase;
        if (data.facing) data.facing.quaternion.copy(camera.quaternion);
        if (data.line) {
          const low = top, high = icon.position.y - 0.78 * size, wide = 1.4 * kpx * far;      // a line 1.4 pixels wide whatever the distance
          data.line.position.set(body.position.x, (low + high) / 2, body.position.z); data.line.scale.set(wide, Math.max(0.01, (high - low) * arrive), wide);
          data.ring.position.set(body.position.x, body.position.y + 0.25 * S, body.position.z); data.ring.scale.setScalar(Math.max(1.7 * S, 20 * kpx * far) * arrive);
        }
      });
    }
    A.renderer.render(A.scene, A.camera);                             // again, with the icons where the rovers are in this frame
    g.clearRect(0, 0, W, H);
    const shown = smooth(0.1, 0.45, into) * out;
    if (shown > 0.003) {
      // low in the middle of the stage: clear of the page's readouts at the top, its battery gauges on the left and its mini-map on the right
      const title = `${'ABCD'[which]} · ${KINDS[which][0]}`, x = Math.round(vw * 0.54), y = H - 150, wide = 470;
      g.save(); g.globalAlpha = shown; g.textAlign = 'center';
      g.fillStyle = 'rgba(11,8,7,.88)'; g.fillRect(x - wide / 2, y - 52, wide, 98); g.fillStyle = '#ffb224'; g.fillRect(x - wide / 2, y - 52, wide, 4);
      g.font = `700 46px ${FONT}`; g.letterSpacing = '7px'; g.fillText(title, x + 3, y);
      g.font = `700 19px ${FONT}`; g.letterSpacing = '3.4px'; g.fillStyle = 'rgba(243,234,217,.8)'; g.fillText(KINDS[which][1], x + 2, y + 30);
      g.restore();
    }
    return { kind: KINDS[which][0] };
  }
  window.__piece = { draw, kinds: KINDS.map(k => k[0]), show: SHOW };
})();
