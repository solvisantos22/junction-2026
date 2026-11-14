// Manh's add-on for Kristján's chart scenes (tools/demo_video/film.html) while they are recorded.
// The scenes themselves are untouched; this file
//
// - draws the maker's logo tile in front of a model's name wherever a scene writes one
//   (a results row, a row of the 300-world chart, the heading over Claude's own words), by
//   wrapping the page's text() helper, so the tiles follow his layout without copying it;
// - says when each thing on a chart starts to move (window.__manh.sfx), so the sound track can
//   lay a quiet sound under it. Those times are the scene's own formulas written out again, so
//   the recorder checks every one against the times the page really used (window.__manh.onsets,
//   collected by the page's appear() helper) and stops if they have drifted apart.
(() => {
  const M = window.__MANH, images = {}, onsets = new Set();
  for (const [key, spec] of Object.entries(M.tiles)) { const node = new Image(); node.src = spec.tile; images[key] = node; }
  const words = label => new Set(label.toLowerCase().match(/[a-z]+\d*/g) || []);
  // a model's name standing alone ("OPUS 5.5", "SONNET · ONE REQUEST"), not a sentence that mentions one
  function makerFor(label) {
    if (label === 'REFERENCE') return 'reference';
    if (label === "IN CLAUDE'S OWN WORDS") return 'anthropic';
    if (label.length > 24 || /[,:]|\.(\s|$)/.test(label)) return null;
    const first = (label.toLowerCase().match(/^[a-z]+\d*/) || [''])[0];
    for (const [key, spec] of Object.entries(M.tiles)) if (spec.words.includes(first)) return key;
    return null;
  }
  const baseText = window.text, baseMeasure = window.measure;
  // The scenes were laid out for DIN Condensed; Barlow Condensed, which stands in for it, is a little wider.
  // Its text is drawn 7% narrower, and measured so, and every column and line break falls where it did.
  const SQUEEZE = 0.93, narrow = o => o.font === undefined || o.font === DIN;
  window.measure = (label, o = {}) => baseMeasure(label, o) * (narrow(o) ? SQUEEZE : 1);
  window.__onset = at => { if (Number.isFinite(at)) onsets.add(Math.round(at * 1000)); };     // called by the page's appear(), see pages.py
  window.text = function (label, x, y, o = {}) {
    const tight = narrow(o);
    if (tight) { g.save(); g.translate(x, 0); g.scale(SQUEEZE, 1); g.translate(-x, 0); }
    const width = baseText(label, x, y, o) * (tight ? SQUEEZE : 1);
    if (tight) g.restore();
    const key = typeof label === 'string' && (o.align || 'left') === 'left' && (o.alpha === undefined || o.alpha > 0.003) ? makerFor(label) : null;
    if (key && images[key].complete && images[key].naturalWidth) {
      const size = (o.size || 40) * (o.size > 60 ? 0.78 : 0.9), gap = (o.size || 40) * 0.3;
      g.save(); g.globalAlpha *= o.alpha === undefined ? 1 : o.alpha;
      g.drawImage(images[key], x - gap - size, y - (o.size || 40) * 0.37 - size / 2, size, size);
      g.restore();
    }
    return width;
  };

  // A little life behind the charts: a warm light that drifts slowly across the backdrop, and darker corners
  // to match the ground shots. Drawn right after the page's own backdrop, so nothing on a chart is touched.
  const baseBackdrop = window.backdrop;
  window.backdrop = function (chapter) {
    baseBackdrop(chapter);
    const t = window.__film ? window.__film.now() / 1000 : 0, top = 56;
    const cx = W * (0.5 + 0.2 * Math.sin(t * 0.21 + 1.0)), cy = H * (0.6 + 0.07 * Math.cos(t * 0.17));
    const light = g.createRadialGradient(cx, cy, 40, cx, cy, 780);
    light.addColorStop(0, 'rgba(255,150,80,.075)'); light.addColorStop(1, 'rgba(255,150,80,0)');
    g.save(); g.fillStyle = light; g.fillRect(0, top, W, H - top);
    const corners = g.createRadialGradient(W / 2, H * 0.52, H * 0.42, W / 2, H * 0.52, W * 0.66);
    corners.addColorStop(0, 'rgba(0,0,0,0)'); corners.addColorStop(1, 'rgba(0,0,0,.5)');
    g.fillStyle = corners; g.fillRect(0, top, W, H - top); g.restore();
  };

  // When each thing on a chart starts to move, in seconds from the start of the scene. `check` marks a time
  // the page's own appear() must have used; the kinds are the sounds of tools/manh_demo/sound.py.
  const SFX = {
    quote(D, data, cues) {
      const cue = (i, otherwise) => (cues && cues[i] !== undefined ? cues[i] : otherwise);
      const first = cue(0, 0.7), second = cue(1, Math.max(3.2, D * 0.4)), verdict = cue(2, D - 3.2), list = [];
      list.push({ at: first, kind: 'swell', check: true }, { at: second, kind: 'swell', check: true });
      for (let i = 0; i < 3; i++) list.push({ at: second + 0.9 + i * 0.25, kind: 'tick', step: i, check: true });   // how the three sites ended
      list.push({ at: verdict, kind: 'hit_soft', check: true }, { at: verdict + 1.5, kind: 'hit', check: true });     // the verdict, then its second half in gold
      return list;
    },
    reference(D, data, cues) {
      const B = data.battery, T = B.ticks, span = Math.max(3, D - 3.2), list = [];
      for (let i = 0; i < 4; i++) list.push({ at: cues[i] !== undefined ? cues[i] : i === 3 ? D - 2.2 : 1.0 + i * 1.6, kind: 'chime', step: i, check: true });   // the chain lights up
      list.push({ at: 1.2, kind: 'flow', len: span, rise: 0.35 });                                                    // the battery lines draw across the day
      for (const id of Object.keys(B.series)) { const dead = B.series[id].dead; if (dead !== null) list.push({ at: 1.2 + (dead / T) * span, kind: 'tock', check: true }); }
      const home = B.series['campaign-reference'];
      let low = 1; for (let tick = 2; tick <= T / 2; tick++) if (home.battery[tick] < home.battery[low]) low = tick;
      list.push({ at: 1.2 + (low / T) * span + 0.2, kind: 'chime_soft', check: true });                              // "waits for the sun"
      return list;
    },
    results(D, data, cues) {
      const c = data.campaign, list = [{ at: 0.7, kind: 'bar', score: c.reference.score, gold: true, check: true }];
      c.claude.forEach((run, i) => list.push({ at: 1.7 + i * 0.32, kind: 'bar', score: run.score, step: i, check: true }));
      for (const [at, word] of [[4.6, 'stop'], [4.9, 'nothing']]) list.push({ at, kind: 'bar', score: c.baselines.find(r => r.id.includes(word)).score, check: true });
      list.push({ at: 3.9, kind: 'flow', len: 0.9, rise: -1, check: true });                                           // the reference's score carried down past every run
      list.push({ at: 4.5, kind: 'tick', step: 2, check: true }, { at: 4.9, kind: 'hit_soft', check: true });           // the gap, then the claim
      if (cues && cues[0] !== undefined) list.push({ at: cues[0], kind: 'tock', check: true });                        // "doing nothing scores zero"
      return list;
    },
    farm(D, data, cues) {
      const sweep = Math.min(3.4, D * 0.3), list = [{ at: 1.0, kind: 'flow', len: sweep + 0.6, rise: 1 }];             // 1,800 worlds sweep in
      for (let r = 0; r < 6; r++) list.push({ at: 1.0 + r * 0.12 + sweep, kind: 'tick', step: r, check: true });       // each row's count
      const at = cues && cues[0] !== undefined ? cues[0] : 1.4 + sweep, note = cues && cues[1] !== undefined ? cues[1] : at + 3;
      list.push({ at, kind: 'hit_soft', check: true }, { at: at + 0.35, kind: 'tick', step: 1, check: true }, { at: at + 0.7, kind: 'tick', step: 3, check: true });
      list.push({ at: note, kind: 'chime_soft', check: true });
      return list;
    },
    learning(D) {
      const span = Math.max(2.5, D - 4);
      return [{ at: 0.9, kind: 'flow', len: 0.8, rise: 0, check: true }, { at: 1.2, kind: 'tick', step: 0, check: true },
        { at: 1.5, kind: 'flow', len: span, rise: 1, check: true }, { at: 1.5 + span, kind: 'chime', step: 3, check: true }];
    },
    end(D, data, cues) {
      const live = cues && cues[0] !== undefined ? cues[0] : 2.6, ask = cues && cues[1] !== undefined ? cues[1] : live + 1.6;
      return [{ at: 0.1, kind: 'hit', check: true }, { at: 0.7, kind: 'typing', len: 1.3 }, { at: 2.1, kind: 'chime_soft', check: true },
        { at: live, kind: 'swell', check: true }, { at: Math.max(live + 0.1, ask - 1.2), kind: 'riser', len: Math.min(1.2, ask - live - 0.1) }, { at: ask, kind: 'hit', check: true }];
    },
  };
  window.__manh = {
    ready: Promise.all(Object.values(images).map(node => node.decode().catch(() => null))).then(() => true),
    onsets: () => [...onsets].sort((a, b) => a - b),
    sfx: (name, D, cues) => (SFX[name] ? SFX[name](D, window.FILM_DATA, cues || []) : []),
  };
})();
