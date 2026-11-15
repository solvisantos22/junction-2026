// Drafts of a floating 3D icon over a rover, for Manh to pick from (15 November). He asked for an icon that floats
// precisely on top of the rover, in place of the frame and badge of the first cut, shown over a rover in empty space.
//
// A small studio: three of the film's own rovers (the page's roverParts), side by side on a dark floor, one for each
// lab, and over each the same kind of icon carrying that lab's mark in that lab's colour. The camera drifts around
// them. Four kinds, one after the other, each on screen for SHOW seconds:
//
//   TOKEN   a coin with the mark raised on both faces, turning slowly
//   TILE    a rounded slab that always faces the viewer, with one to three pips under it for the model's tier
//   MARK    the mark alone as a solid object, turning, lit from inside
//   BEACON  the tile on a hair-thin line up from the rover, and a ring on the ground: found from far above
//
// The marks are cut out of their SVG paths by three.js's own loader (window.__PIECE.loader, see pages.svg_loader).
// window.__piece.draw(seconds) draws one frame; the recorder calls it after the page has drawn its own.
(() => {
  const A = window.LIGHTLAG_TRAVERSE_APP, T = A.THREE, P = window.__PIECE;
  const SVGLoader = new Function('THREE', P.loader)(T);
  const W = window.innerWidth, H = window.innerHeight, SHOW = P.show || 5.0;
  const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
  const lerp = (a, b, t) => a + (b - a) * t;
  const smooth = (a, b, x) => { const t = clamp((x - a) / (b - a), 0, 1); return t * t * (3 - 2 * t); };
  const back = x => { x = clamp(x, 0, 1); const c = 1.7; return 1 + (c + 1) * Math.pow(x - 1, 3) + c * Math.pow(x - 1, 2); };     // arrives a little past, then settles
  const KINDS = [['TOKEN', 'A COIN WITH THE MARK ON BOTH FACES, TURNING SLOWLY'], ['TILE', 'ALWAYS FACES THE VIEWER · ONE TO THREE PIPS FOR THE TIER'],
    ['MARK', 'THE MARK ALONE AS A SOLID OBJECT, LIT FROM INSIDE'], ['BEACON', 'A HAIRLINE UP FROM THE ROVER AND A RING ON THE GROUND']];

  // ---------------------------------------------------------------- the studio
  const lab = new T.Scene(), eye = new T.PerspectiveCamera(27, W / H, 0.1, 400);
  lab.add(new T.HemisphereLight(0xfff0e0, 0x2a1810, 1.15));
  const key = new T.DirectionalLight(0xfff3e2, 3.1);
  key.position.set(7, 12, 9); key.castShadow = true; key.shadow.mapSize.set(2048, 2048); key.shadow.bias = -0.0004; key.shadow.normalBias = 0.04;
  Object.assign(key.shadow.camera, { left: -11, right: 11, top: 9, bottom: -9, near: 1, far: 50 });
  lab.add(key);
  const rim = new T.DirectionalLight(0xffb48a, 1.3); rim.position.set(-8, 5, -9); lab.add(rim);
  const floor = new T.Mesh(new T.CircleGeometry(60, 72).rotateX(-Math.PI / 2), new T.MeshStandardMaterial({ color: 0x1b1411, roughness: 1 }));
  floor.receiveShadow = true; lab.add(floor);
  {                                                                   // a pool of light on the floor under the rovers
    const canvas = document.createElement('canvas'); canvas.width = canvas.height = 256;
    const g = canvas.getContext('2d'), glow = g.createRadialGradient(128, 128, 0, 128, 128, 128);
    glow.addColorStop(0, 'rgba(150,80,48,.5)'); glow.addColorStop(0.55, 'rgba(110,52,30,.2)'); glow.addColorStop(1, 'rgba(110,52,30,0)');
    g.fillStyle = glow; g.fillRect(0, 0, 256, 256);
    const pool = new T.Mesh(new T.PlaneGeometry(34, 22).rotateX(-Math.PI / 2), new T.MeshBasicMaterial({ map: new T.CanvasTexture(canvas), transparent: true, depthWrite: false }));
    pool.position.y = 0.01; lab.add(pool);
  }

  // ---------------------------------------------------------------- the parts an icon is made of
  const solid = (color, more = {}) => new T.MeshStandardMaterial({ color, roughness: 0.42, metalness: 0.04, ...more });
  function markShape(lab_) {                                          // the lab's mark as flat shapes, one unit across, centred
    const data = new SVGLoader().parse(`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="${lab_.path}"/></svg>`), shapes = [];
    for (const path of data.paths) shapes.push(...SVGLoader.createShapes(path));
    return shapes;
  }
  function mark(lab_, across, depth, color, more) {
    const geometry = new T.ExtrudeGeometry(markShape(lab_), { depth: depth * 24 / across, bevelEnabled: true, bevelThickness: 0.2, bevelSize: 0.14, bevelSegments: 2, curveSegments: 8 });
    geometry.center(); geometry.scale(across / 24, across / 24, across / 24); geometry.rotateX(Math.PI);      // an SVG's y runs down
    const mesh = new T.Mesh(geometry, solid(color, more)); mesh.castShadow = true;
    return mesh;
  }
  function rounded(w, h, r) {
    const s = new T.Shape(), x = -w / 2, y = -h / 2;
    s.moveTo(x + r, y); s.lineTo(x + w - r, y); s.quadraticCurveTo(x + w, y, x + w, y + r); s.lineTo(x + w, y + h - r); s.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
    s.lineTo(x + r, y + h); s.quadraticCurveTo(x, y + h, x, y + h - r); s.lineTo(x, y + r); s.quadraticCurveTo(x, y, x + r, y);
    return s;
  }
  function slab(lab_, size) {                                         // the logo tile of the film, as an object
    const group = new T.Group(), thick = size * 0.13;
    const body = new T.Mesh(new T.ExtrudeGeometry(rounded(size, size, size * 0.22), { depth: thick, bevelEnabled: true, bevelThickness: size * 0.025, bevelSize: size * 0.025, bevelSegments: 3, curveSegments: 12 }).translate(0, 0, -thick / 2),
      solid(lab_.tile));
    body.castShadow = true; group.add(body);
    const front = mark(lab_, size * 0.62, size * 0.05, lab_.ink, { emissive: lab_.ink, emissiveIntensity: 0.12 }); front.position.z = thick / 2 + size * 0.045; group.add(front);
    return group;
  }
  const BUILD = {
    TOKEN(lab_) {
      const group = new T.Group(), turning = new T.Group(); group.add(turning);
      const disc = new T.Mesh(new T.CylinderGeometry(0.5, 0.5, 0.12, 64).rotateX(Math.PI / 2), solid(lab_.tile)); disc.castShadow = true; turning.add(disc);
      const edge = new T.Mesh(new T.TorusGeometry(0.5, 0.045, 14, 72), solid(lab_.text, { emissive: lab_.text, emissiveIntensity: 0.25 })); edge.castShadow = true; turning.add(edge);
      for (const side of [1, -1]) { const face = mark(lab_, 0.6, 0.035, lab_.ink, { emissive: lab_.ink, emissiveIntensity: 0.12 }); face.position.z = side * 0.085; if (side < 0) face.rotation.y = Math.PI; turning.add(face); }
      group.userData = { turning, height: 3.25 };
      return group;
    },
    TILE(lab_, tier) {
      const group = new T.Group(), facing = new T.Group(); group.add(facing);
      facing.add(slab(lab_, 0.92));
      for (let i = 0; i < 3; i++) {                                   // the tier: one pip for the fast model, three for the flagship
        const lit = i < tier, pip = new T.Mesh(new T.SphereGeometry(0.062, 20, 14), solid(lit ? lab_.text : 0x5b4a42, lit ? { emissive: lab_.text, emissiveIntensity: 0.55 } : {}));
        pip.position.set((i - 1) * 0.2, -0.66, 0); facing.add(pip);
      }
      group.userData = { facing, height: 3.35 };
      return group;
    },
    MARK(lab_) {
      const group = new T.Group(), turning = new T.Group(); group.add(turning);
      turning.add(mark(lab_, 0.98, 0.2, lab_.text, { emissive: lab_.text, emissiveIntensity: 0.45, roughness: 0.3 }));
      group.userData = { turning, height: 3.3 };
      return group;
    },
    BEACON(lab_, tier) {
      const group = BUILD.TILE(lab_, tier), top = 3.7;
      const line = new T.Mesh(new T.CylinderGeometry(0.012, 0.012, 1, 8), new T.MeshBasicMaterial({ color: lab_.text, transparent: true, opacity: 0.85 }));
      const ring = new T.Mesh(new T.RingGeometry(1.5, 1.58, 72).rotateX(-Math.PI / 2), new T.MeshBasicMaterial({ color: lab_.text, transparent: true, opacity: 0.8 }));
      ring.position.y = 0.03;
      group.userData = { ...group.userData, height: top, line, ring };
      return group;
    },
  };

  // three rovers, three labs; the tiers shown are one of each, to show the pips
  const stands = P.labs.map((lab_, i) => {
    const x = (i - 1) * 4.1, rover = A.roverParts(0xf3ead9);
    rover.position.set(x, 0, 0); rover.rotation.y = -0.55 + i * 0.12; lab.add(rover);
    const icons = KINDS.map(([kind]) => {
      const icon = BUILD[kind](lab_, 3 - i);
      icon.visible = false; lab.add(icon);
      if (icon.userData.line) { icon.userData.line.visible = icon.userData.ring.visible = false; lab.add(icon.userData.line, icon.userData.ring); }
      return icon;
    });
    return { lab: lab_, x, icons };
  });

  // ---------------------------------------------------------------- the words, on a flat layer
  const sheet = document.createElement('canvas');
  sheet.width = W; sheet.height = H;
  sheet.style.cssText = 'position:fixed;inset:0;width:100vw;height:100vh;z-index:40;pointer-events:none';
  document.body.append(sheet);
  const g = sheet.getContext('2d'), ui = document.getElementById('ui'), FONT = getComputedStyle(document.body).fontFamily, at = new T.Vector3();
  function words(line, x, y, size, alpha, color = '#f3ead9', spacing = 0.18, align = 'left') {
    if (alpha <= 0.003) return;
    g.save(); g.globalAlpha = alpha; g.fillStyle = color; g.textAlign = align; g.font = `700 ${size}px ${FONT}`; g.letterSpacing = `${(size * spacing).toFixed(1)}px`;
    g.fillText(line, x, y); g.restore();
  }

  function draw(t) {
    const which = Math.min(KINDS.length - 1, Math.floor(t / SHOW)), into = t - which * SHOW, out = clamp((SHOW - into) / 0.3, 0, 1), arrive = back(into / 0.55) * out;
    const around = lerp(-0.42, 0.42, smooth(0, KINDS.length * SHOW, t)) + 0.05 * Math.sin(t * 0.5);
    eye.position.set(Math.sin(around) * 21, 5.4, Math.cos(around) * 21); eye.lookAt(0, 1.9, 0);
    for (const stand of stands) stand.icons.forEach((icon, k) => {
      const on = k === which, data = icon.userData;
      icon.visible = on;
      if (data.line) data.line.visible = data.ring.visible = on;
      if (!on) return;
      const bob = 0.045 * Math.sin(t * 2.1 + stand.x);
      icon.position.set(stand.x, data.height + bob, 0); icon.scale.setScalar(Math.max(0.001, arrive));
      if (data.turning) data.turning.rotation.y = t * 1.15 + stand.x;
      if (data.facing) data.facing.quaternion.copy(eye.quaternion);       // always toward the viewer
      if (data.line) {
        const low = 2.15, high = data.height + bob - 0.62;
        data.line.position.set(stand.x + 0.46 * Math.cos(-0.55), (low + high) / 2, 0.3); data.line.scale.set(1, Math.max(0.01, (high - low) * arrive), 1);
        data.ring.position.x = stand.x; data.ring.scale.setScalar(arrive * (1 + 0.04 * Math.sin(t * 2.6)));
      }
    });
    const R = A.renderer;
    R.setScissorTest(false); R.setViewport(0, 0, W, H); R.shadowMap.needsUpdate = true;
    R.render(lab, eye);
    ui.style.opacity = '0';
    g.clearRect(0, 0, W, H);
    words('FLOATING ICON · DRAFTS', 96, 112, 30, 1, 'rgba(243,234,217,.62)', 0.26);
    const shown = smooth(0.15, 0.6, into) * out;
    words(`${'ABCD'[which]} · ${KINDS[which][0]}`, 96, H - 150, 84, shown, '#ffb224', 0.16);
    words(KINDS[which][1], 100, H - 96, 28, shown, 'rgba(243,234,217,.8)', 0.18);
    for (const stand of stands) {                                     // which lab each rover stands for, under it
      at.set(stand.x, -0.25, 1.6).project(eye);
      words(stand.lab.name, (at.x + 1) / 2 * W, (1 - at.y) / 2 * H, 30, 0.9, stand.lab.text, 0.24, 'center');
    }
    return { kind: KINDS[which][0] };
  }
  window.__piece = { draw, kinds: KINDS.map(k => k[0]), show: SHOW };
})();
