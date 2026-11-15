// The opening of the film, as Manh asked for it (15 November): start in space, orbiting Mars, dive down through
// the dust, and land on our own map, where the title comes up. A draft piece, recorded on its own.
//
// Three parts on one clock (seconds into the shot):
//   orbit   a low-poly Mars turning under a low sun, stars behind it, the camera drifting closer;
//   dive    the camera falls at the planet; streaks, then dust, fill the frame;
//   land    the dust clears on the real demo page: the camera comes straight down onto the spot where the rovers
//           start and ends low beside the reference rover; the page's own bars and standings fade in around it;
//   rise    up and back to the page's usual overview, where the title comes up.
// The planet is made here from noise (no picture of Mars is used), in the flat-shaded style of the page.
// window.__piece.draw(seconds) draws one frame; the recorder calls it after the page has drawn its own.
(() => {
  const A = window.LIGHTLAG_TRAVERSE_APP, T = A.THREE, P = window.__PIECE || {};
  const ORBIT = P.orbit === undefined ? 9.0 : P.orbit, DIVE = P.dive === undefined ? 2.6 : P.dive, LAND = P.land === undefined ? 3.2 : P.land, RISE = P.rise === undefined ? 2.4 : P.rise;
  const W = window.innerWidth, H = window.innerHeight;
  const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
  const lerp = (a, b, t) => a + (b - a) * t;
  const smooth = (a, b, x) => { const t = clamp((x - a) / (b - a), 0, 1); return t * t * (3 - 2 * t); };
  const outCubic = x => 1 - Math.pow(1 - clamp(x, 0, 1), 3);

  // ---------------------------------------------------------------- noise, the same every time
  const hash = (x, y, z) => { let h = Math.imul(x, 374761393) + Math.imul(y, 668265263) + Math.imul(z, 1274126177) | 0; h = Math.imul(h ^ (h >>> 13), 1274126177); return ((h ^ (h >>> 16)) >>> 0) / 4294967296; };
  function noise(x, y, z) {
    const xi = Math.floor(x), yi = Math.floor(y), zi = Math.floor(z), xf = x - xi, yf = y - yi, zf = z - zi;
    const u = xf * xf * (3 - 2 * xf), v = yf * yf * (3 - 2 * yf), w = zf * zf * (3 - 2 * zf);
    const at = (i, j, k) => hash(xi + i, yi + j, zi + k);
    return lerp(lerp(lerp(at(0, 0, 0), at(1, 0, 0), u), lerp(at(0, 1, 0), at(1, 1, 0), u), v),
      lerp(lerp(at(0, 0, 1), at(1, 0, 1), u), lerp(at(0, 1, 1), at(1, 1, 1), u), v), w);
  }
  function fbm(x, y, z, octaves = 5) { let sum = 0, amp = 0.5, norm = 0; for (let i = 0; i < octaves; i++) { sum += amp * noise(x, y, z); norm += amp; x *= 2.07; y *= 2.07; z *= 2.07; amp *= 0.5; } return sum / norm; }
  let seed = 20261115;
  const random = () => { seed = Math.imul(seed ^ (seed >>> 15), 2246822507) + 0x9e3779b9 | 0; return ((seed ^ (seed >>> 13)) >>> 0) / 4294967296; };

  // ---------------------------------------------------------------- space
  const space = new T.Scene(), eye = new T.PerspectiveCamera(36, W / H, 0.05, 4000);
  const light = new T.DirectionalLight(0xfff1df, 3.6); light.position.set(3.4, 1.25, 2.3); space.add(light);       // from the side: half the planet is night
  space.add(new T.AmbientLight(0x5a2c20, 0.09));
  {
    const count = 2600, at = new Float32Array(count * 3), tint = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      const u = random() * 2 - 1, a = random() * Math.PI * 2, r = Math.sqrt(1 - u * u), far = 1800;
      at.set([r * Math.cos(a) * far, u * far, r * Math.sin(a) * far], i * 3);
      const bright = Math.pow(random(), 2.2) * 0.8 + 0.2, warm = random();
      tint.set([bright, bright * lerp(0.86, 1, warm), bright * lerp(0.72, 1, warm)], i * 3);
    }
    const stars = new T.BufferGeometry();
    stars.setAttribute('position', new T.BufferAttribute(at, 3)); stars.setAttribute('color', new T.BufferAttribute(tint, 3));
    space.add(new T.Points(stars, new T.PointsMaterial({ size: 2.1, sizeAttenuation: false, vertexColors: true, fog: false })));
  }
  // Mars: an icosphere pushed in and out by noise and by craters, every face one flat colour
  const mars = new T.Group(); space.add(mars);
  {
    const craters = [];
    for (let i = 0; i < 230; i++) {
      const u = random() * 2 - 1, a = random() * Math.PI * 2, r = Math.sqrt(1 - u * u);
      craters.push({ x: r * Math.cos(a), y: u, z: r * Math.sin(a), size: 0.014 + Math.pow(random(), 3.2) * 0.085 });
    }
    const bowl = (x, y, z) => {                                       // how deep a point sits in the nearest crater, and how close to its rim
      let dip = 0, rim = 0;
      for (const c of craters) {
        const d = Math.acos(clamp(x * c.x + y * c.y + z * c.z, -1, 1)) / c.size;
        if (d < 1.25) { dip = Math.max(dip, (1 - smooth(0, 1, d)) * c.size); rim = Math.max(rim, smooth(0.75, 1, d) * (1 - smooth(1, 1.25, d)) * c.size); }
      }
      return [dip, rim];
    };
    const ball = new T.IcosahedronGeometry(1, 64), at = ball.attributes.position, tint = new Float32Array(at.count * 3);
    const v = new T.Vector3(), rust = new T.Color(0xb1562f), pale = new T.Color(0xd9955f), dark = new T.Color(0x4f261c), ice = new T.Color(0xf1e7dc), mix = new T.Color();
    for (let i = 0; i < at.count; i++) {
      v.fromBufferAttribute(at, i).normalize();
      const [dip, rim] = bowl(v.x, v.y, v.z), rough = fbm(v.x * 3.1 + 7, v.y * 3.1 + 3, v.z * 3.1 + 5, 5);
      at.setXYZ(i, ...v.clone().multiplyScalar(1 + (rough - 0.5) * 0.03 - dip * 0.3 + rim * 0.16).toArray());
    }
    for (let face = 0; face < at.count; face += 3) {                  // one colour for the three corners of a face
      v.set(0, 0, 0);
      for (let k = 0; k < 3; k++) v.x += at.getX(face + k), v.y += at.getY(face + k), v.z += at.getZ(face + k);
      v.normalize();
      const [dip, rim] = bowl(v.x, v.y, v.z);
      const light = fbm(v.x * 1.7 + 11, v.y * 1.7 + 2, v.z * 1.7 + 9, 4), basalt = smooth(0.52, 0.66, fbm(v.x * 1.25 + 31, v.y * 2.0 + 17, v.z * 1.25 + 4, 4));
      mix.copy(rust).lerp(pale, smooth(0.38, 0.7, light)).lerp(dark, basalt * 0.82).lerp(dark, clamp(dip * 9, 0, 0.55)).lerp(pale, clamp(rim * 14, 0, 0.5));
      const cap = Math.abs(v.y) - (0.9 - 0.06 * fbm(v.x * 6, v.y * 6, v.z * 6, 3));
      if (cap > 0) mix.lerp(ice, smooth(0, 0.03, cap));
      for (let k = 0; k < 3; k++) tint.set([mix.r, mix.g, mix.b], (face + k) * 3);
    }
    ball.setAttribute('color', new T.BufferAttribute(tint, 3));
    mars.add(new T.Mesh(ball, new T.MeshStandardMaterial({ vertexColors: true, flatShading: true, roughness: 0.95, metalness: 0 })));
    // its thin, dusty air: a glow on the limb, brighter toward the sun
    mars.add(new T.Mesh(new T.IcosahedronGeometry(1.045, 24), new T.ShaderMaterial({
      transparent: true, depthWrite: false, blending: T.AdditiveBlending, uniforms: { sun: { value: light.position.clone().normalize() } },
      vertexShader: 'varying vec3 n; varying vec3 e; varying vec3 w; void main(){ vec4 p = modelViewMatrix * vec4(position, 1.0); n = normalize(normalMatrix * normal); e = normalize(-p.xyz); w = normalize(mat3(modelMatrix) * normal); gl_Position = projectionMatrix * p; }',
      fragmentShader: 'uniform vec3 sun; varying vec3 n; varying vec3 e; varying vec3 w; void main(){ float rim = pow(1.0 - max(dot(normalize(n), normalize(e)), 0.0), 3.0); float day = 0.12 + 0.88 * smoothstep(-0.25, 0.5, dot(normalize(w), sun)); gl_FragColor = vec4(vec3(1.0, 0.6, 0.4) * rim * day * 0.9, rim * day); }',
    })));
  }

  // ---------------------------------------------------------------- the dive's streaks and dust, and the words, on a flat layer
  const sheet = document.createElement('canvas');
  sheet.width = W; sheet.height = H;
  sheet.style.cssText = 'position:fixed;inset:0;width:100vw;height:100vh;z-index:40;pointer-events:none';
  document.body.append(sheet);
  const g = sheet.getContext('2d'), ui = document.getElementById('ui');
  const FONT = getComputedStyle(document.body).fontFamily;
  const streaks = Array.from({ length: 150 }, () => ({ a: random() * Math.PI * 2, r: 0.1 + random() * 0.9, len: 0.25 + random() * 0.75, w: 1 + random() * 2.4 }));
  const puffs = Array.from({ length: 16 }, (_, i) => ({ a: random() * Math.PI * 2, r: random() * 0.5, at: 0.3 + i * 0.04 + random() * 0.05, size: 0.5 + random() * 0.8, shade: 0.75 + random() * 0.25 }));
  function words(line, x, y, size, alpha, color = '#f3ead9', spacing = 0.2) {
    if (alpha <= 0.003) return;
    g.save(); g.globalAlpha = alpha; g.fillStyle = color; g.font = `700 ${size}px ${FONT}`; g.letterSpacing = `${(size * spacing).toFixed(1)}px`;
    g.shadowColor = 'rgba(0,0,0,.85)'; g.shadowBlur = 18; g.fillText(line, x, y); g.restore();
  }
  const fade = (t, from, to, edge = 0.5) => clamp((t - from) / edge, 0, 1) * clamp((to - t) / edge, 0, 1);

  const far = new T.Vector3(), aim = new T.Vector3();
  function draw(t) {
    g.clearRect(0, 0, W, H);
    const inSpace = t < ORBIT + DIVE, fall = clamp((t - ORBIT) / DIVE, 0, 1), down = clamp((t - ORBIT - DIVE) / LAND, 0, 1);
    if (inSpace) {
      // the camera circles slowly and drifts in; in the dive it drops at the ground it has been looking at
      const turn = -0.62 + t * 0.03, plunge = fall * fall * fall, reach = lerp(lerp(5.3, 4.3, smooth(0, ORBIT, t)), 1.07, plunge);
      eye.position.set(Math.sin(turn) * reach, lerp(0.5, 0.2, smooth(0, ORBIT + DIVE, t)), Math.cos(turn) * reach);
      const aside = lerp(1.05, 0, smooth(0.05, 0.75, fall));          // looking past the planet's left puts it on the right of the frame
      eye.lookAt(-Math.cos(turn) * aside, lerp(0.05, 0, fall), Math.sin(turn) * aside);
      eye.fov = lerp(36, 62, plunge); eye.updateProjectionMatrix();
      mars.rotation.y = 0.5 + t * 0.021;
      const R = A.renderer;
      R.setScissorTest(false); R.setViewport(0, 0, W, H); R.setClearColor(0x030304, 1);
      R.render(space, eye);
      R.setClearColor(0x0b0807, 1);
      ui.style.opacity = '0';
      // two quiet lines while it turns: where this is, and why it is hard
      words('MARS', 120, H * 0.5 - 6, 92, fade(t, 1.0, ORBIT - 0.4, 0.8), '#f3ead9', 0.36);
      words('A SIGNAL FROM EARTH TAKES', 124, H * 0.5 + 58, 30, fade(t, 3.2, ORBIT - 0.4, 0.8), '#ffb224', 0.2);
      words('3 TO 22 MINUTES TO ARRIVE', 124, H * 0.5 + 100, 30, fade(t, 3.5, ORBIT - 0.4, 0.8), '#ffb224', 0.2);
      // falling: streaks from the middle of the frame, then dust closing over everything
      if (fall > 0) {
        const cx = W / 2, cy = H / 2, speed = fall * fall;
        g.save(); g.lineCap = 'round';
        for (const s of streaks) {
          const from = (s.r * 0.25 + speed * s.r * 0.9) * W * 0.62, to = from + s.len * speed * W * 0.34;
          g.globalAlpha = clamp(speed * 1.5 - s.r * 0.3, 0, 0.7); g.strokeStyle = 'rgba(255,222,196,1)'; g.lineWidth = s.w * (0.6 + speed * 1.6);
          g.beginPath(); g.moveTo(cx + Math.cos(s.a) * from, cy + Math.sin(s.a) * from); g.lineTo(cx + Math.cos(s.a) * to, cy + Math.sin(s.a) * to); g.stroke();
        }
        g.restore();
      }
    } else {
      // landing: the page has drawn its map from its usual place; draw it again. First straight down out of the dust
      // onto the spot where the rovers start, ending low beside the reference rover; then up and back to the
      // page's own overview, so the next shot carries on from where the page left it.
      const view = A.view, k = 1 - Math.pow(1 - down, 3), up = smooth(0, 1, (t - ORBIT - DIVE - LAND) / RISE);
      const pose = A.REF.track.at(0), spot = A.P(pose.x, pose.y);
      const home = view.eye.distanceTo(view.look), high = lerp(1.15, 0.13, k) * home;  // from a little above the overview's height down to a few rover lengths
      const lean = lerp(0.04, 0.62, smooth(0.35, 1, down));             // from looking straight down to looking in from the south
      far.set(spot.x, spot.y + Math.cos(lean) * high, spot.z + Math.sin(lean) * high);
      far.lerp(view.eye, up); aim.copy(spot).lerp(view.look, up);
      A.camera.position.copy(far); A.camera.up.set(0, 1, 0); A.camera.lookAt(aim); A.camera.updateProjectionMatrix();
      // the page sized its names and flags for its own camera; shrink them with the distance so they keep their size on screen
      const shrink = far.distanceTo(aim) / home, sprites = [];
      A.scene.traverse(o => { if (o.isSprite) { sprites.push([o, o.scale.clone()]); o.scale.multiplyScalar(shrink); } });
      A.renderer.render(A.scene, A.camera);
      for (const [o, scale] of sprites) o.scale.copy(scale);
      ui.style.opacity = smooth(0.0, 0.12, down).toFixed(3);          // the page's bars and standings are there before the dust thins, so no bare margins show
    }
    // the dust: thick at the end of the dive, thinning as the map comes up under it
    const dust = t < ORBIT + DIVE ? smooth(0.45, 0.98, fall) : 1 - smooth(0.0, 0.3, down);
    if (dust > 0.003) {
      g.save();
      for (const p of puffs) {
        const grown = t < ORBIT + DIVE ? smooth(p.at, p.at + 0.5, fall) : 1 + down * 1.5, x = W / 2 + Math.cos(p.a) * p.r * W * 0.5 * (1 + grown), y = H / 2 + Math.sin(p.a) * p.r * H * 0.5 * (1 + grown);
        const size = p.size * W * (0.25 + grown * 0.75), paint = g.createRadialGradient(x, y, 0, x, y, size);
        paint.addColorStop(0, `rgba(${Math.round(226 * p.shade)},${Math.round(150 * p.shade)},${Math.round(100 * p.shade)},${(0.5 * dust * dust * Math.min(grown, 1.4)).toFixed(3)})`);
        paint.addColorStop(1, 'rgba(214,138,90,0)');
        g.fillStyle = paint; g.fillRect(0, 0, W, H);
      }
      g.globalAlpha = smooth(0.55, 1, dust); g.fillStyle = '#d78c5c'; g.fillRect(0, 0, W, H);
      g.restore();
    }
    return { part: t < ORBIT ? 'orbit' : t < ORBIT + DIVE ? 'dive' : down < 1 ? 'land' : t < ORBIT + DIVE + LAND + RISE ? 'rise' : 'map' };
  }
  window.__piece = { draw, parts: { orbit: ORBIT, dive: DIVE, land: LAND, rise: RISE } };
})();
