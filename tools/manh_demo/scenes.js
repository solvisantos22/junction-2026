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
  // Modal ran the 300-world replay and the training. Wherever a scene writes its name, the name is in Modal's
  // green with Modal's mark in front of it, and the line is measured with the mark in it.
  const MODAL = /\bMODAL\b/, modalTall = o => (o.size || 40) * 0.76, modalMark = o => modalTall(o) * 24 / 13.4, modalGap = o => (o.size || 40) * 0.26;
  const withModal = (label, o) => typeof label === 'string' && narrow(o) && MODAL.test(label);
  window.measure = (label, o = {}) => baseMeasure(label, o) * (narrow(o) ? SQUEEZE : 1) + (withModal(label, o) ? modalMark(o) + modalGap(o) : 0);
  window.__onset = at => { if (Number.isFinite(at)) onsets.add(Math.round(at * 1000)); };     // called by the page's appear(), see pages.py
  // one run of text as the page draws it, narrowed if it is the display face; returns its width on screen
  function run(label, x, y, o) {
    const tight = narrow(o);
    if (tight) { g.save(); g.translate(x, 0); g.scale(SQUEEZE, 1); g.translate(-x, 0); }
    const width = baseText(label, x, y, o) * (tight ? SQUEEZE : 1);
    if (tight) g.restore();
    return width;
  }
  window.text = function (label, x, y, o = {}) {
    const shown = o.alpha === undefined || o.alpha > 0.003;
    if (shown && withModal(label, o) && images.modal.complete && images.modal.naturalWidth) {
      const at = label.search(MODAL), before = label.slice(0, at), after = label.slice(at + 5), part = { ...o, align: 'left' };
      const size = o.size || 40, mark = modalMark(o), gap = modalGap(o), plain = { ...o, font: o.font || DIN };
      const widths = [before ? baseMeasure(before, plain) * SQUEEZE : 0, mark + gap, baseMeasure('MODAL', plain) * SQUEEZE, after ? baseMeasure(after, plain) * SQUEEZE : 0];
      const total = widths[0] + widths[1] + widths[2] + widths[3];
      let left = o.align === 'right' ? x - total : o.align === 'center' ? x - total / 2 : x;
      if (before) run(before, left, y, part);
      left += widths[0];
      g.save(); g.globalAlpha *= o.alpha === undefined ? 1 : o.alpha;
      g.drawImage(images.modal, left, y - size * 0.36 - modalTall(o) / 2, mark, modalTall(o));
      g.restore();
      run('MODAL', left + widths[1], y, { ...part, color: M.tiles.modal.text });
      if (after) run(after, left + widths[1] + widths[2], y, part);
      return total;
    }
    const width = run(label, x, y, o);
    const key = typeof label === 'string' && (o.align || 'left') === 'left' && shown && !o.bare ? makerFor(label) : null;
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

  // ---------------------------------------------------------------- scenes this cut adds to Kristján's
  const tile = (key, x, y, size, alpha = 1) => { if (alpha <= 0.003 || !images[key].naturalWidth) return; g.save(); g.globalAlpha *= alpha; g.drawImage(images[key], x, y, size, size); g.restore(); };
  const frame = (x, y, w, h, color, alpha = 1, width = 2) => { if (alpha <= 0.003) return; g.save(); g.globalAlpha *= alpha; g.strokeStyle = color; g.lineWidth = width; g.strokeRect(x + width / 2, y + width / 2, w - width, h - width); g.restore(); };

  // The lineup: three labs, three tiers each, rolled out from the fastest tier up to the flagships. Every lab's
  // name, borders and bars are in that lab's own colour.
  const LINEUP = { left: 372, wide: 462, between: 36, top: 440, row: 152, card: 122, heads: 0.45, first: 1.15, step: 0.65, foot: 3.3 };     // quicker since Manh's note: "a little bit too long"
  SCENES.lineup = (t, D) => {
    backdrop('THE AGENTS');
    heading(t, 'THREE LABS · NINE MODELS', 'EVERY MODEL GETS THE SAME TASK AND THE SAME TOOLS');
    const L = LINEUP, labs = M.lineup.labs, tiers = M.lineup.tiers, notes = ['FASTEST · CHEAPEST', 'THE EVERYDAY MODEL', 'THE MOST CAPABLE'];
    labs.forEach((lab, c) => {
      const x = L.left + c * (L.wide + L.between), color = M.tiles[lab.key].text, at = L.heads + c * 0.25, k = appear(t, at, 0.4);
      if (k <= 0.003) return;
      const pop = 0.8 + 0.2 * out((t - at) / 0.45);
      g.save(); g.globalAlpha = k;
      g.save(); g.translate(x + 44, 300 + 44); g.scale(pop, pop); tile(lab.key, -44, -44, 88); g.restore();
      text(lab.name, x + 110, 338, { size: 58, color, spacing: 0.1, bare: true });
      text(M.tiles[lab.key].family.toUpperCase(), x + 112, 374, { size: 24, color: C.dim, spacing: 0.2, bare: true });
      rect(x, 404, L.wide * out((t - at - 0.15) / 0.6), 3, color);
      g.restore();
    });
    tiers.forEach((name, tier) => {                                        // tier 0 is the fastest, and is the bottom row
      const y = L.top + (2 - tier) * L.row, at = L.first + tier * L.step;
      rise(t, at, () => {
        text(name, 120, y + 56, { size: 38, color: C.ink, spacing: 0.14 });
        text(notes[tier], 120, y + 88, { size: 20, color: C.faint, spacing: 0.14 });
      }, 14, 0.4);
      labs.forEach((lab, c) => {
        const x = L.left + c * (L.wide + L.between), color = M.tiles[lab.key].text, start = at + 0.12 + c * 0.13, k = appear(t, start, 0.35);
        if (k <= 0.003) return;
        const slide = (1 - out((t - start) / 0.5)) * 46;
        g.save(); g.globalAlpha = k; g.translate(0, slide);
        rect(x, y, L.wide, L.card, C.key); rect(x, y, 8, L.card, color); frame(x, y, L.wide, L.card, color, 0.85);
        text(lab.models[tier], x + 34, y + 76, { size: 42, color: C.ink, spacing: 0.07, bare: true });
        tile(lab.key, x + L.wide - 82, y + (L.card - 54) / 2, 54);
        g.restore();
      });
    });
    rise(t, L.foot, () => {
      rect(120, 952, 1680, 2, C.line);
      text('ALL NINE DRIVE THE SAME THREE MAPS', 120, 1004, { size: 30, color: C.gold, spacing: 0.13 });
    });
  };

  // What the AI models are measured against: the reference, which is a model-based planner, and the team's own
  // trained agent, as a reference point for what learning reaches today. Numbers: window.__MANH.facts.
  const DRIVERS = { panels: [0.7, 1.05], lines: 1.9, scores: 3.6, note: 5.2 };
  SCENES.drivers = (t, D) => {
    backdrop('THE REFERENCE');
    heading(t, 'WHAT THE AI IS MEASURED AGAINST', 'TWO DRIVERS WE BUILT OURSELVES · THE SAME MAPS, THE SAME FIVE TOOLS, NOTHING HIDDEN FROM THE MODELS');
    const F = M.facts, P = DRIVERS;
    const panels = [
      { key: 'reference', color: C.gold, title: 'THE REFERENCE', kind: 'A MODEL-BASED PLANNER', sub: 'NOT AN AI · NOTHING IS LEARNED',
        lines: ['Carries its own model of rover, ground and sun', 'Knows where the rover really is, despite the lag', 'Plans the whole day before the wheels turn'],
        score: F.reference, claim: 'NEVER LOST A ROVER, HERE OR ON 300 MORE WORLDS' },
      { key: 'rl', color: C.lime, title: 'OUR RL AGENT', kind: 'TRAINED FROM SCRATCH ON MODAL', sub: `${F.rl_runs} TRAINING RUNS · ${F.rl_missions.toLocaleString('en-US')} PRACTICE MISSIONS EACH`,
        lines: ['Learns by trial and error which rock to go for', 'A hand-written navigator steers underneath it', 'A reference point: what learning reaches today'],
        score: F.rl, claim: F.below_rl === undefined ? 'ABOVE EVERY CLAUDE RUN · BELOW THE PLANNER' : `AHEAD OF ${F.below_rl} OF THE ${F.models} MODELS · BEHIND THE PLANNER` },
    ];
    panels.forEach((panel, i) => {
      const x = 120 + i * 870, y = 262, wide = 810, tall = 616, at = P.panels[i], k = appear(t, at, 0.45);
      if (k <= 0.003) return;
      g.save(); g.globalAlpha = k; g.translate(0, (1 - out((t - at) / 0.55)) * 26);
      rect(x, y, wide, tall, C.key); rect(x, y, wide, 6, panel.color); frame(x, y, wide, tall, panel.color, 0.35);
      tile(panel.key, x + 36, y + 40, 96);
      text(panel.title, x + 160, y + 92, { size: 62, color: panel.color, spacing: 0.1, bare: true });
      text(panel.kind, x + 162, y + 134, { size: 30, color: C.ink, spacing: 0.14 });
      text(panel.sub, x + 36, y + 190, { size: 22, color: C.faint, spacing: 0.16 });
      panel.lines.forEach((line, n) => {
        const show = appear(t, P.lines + i * 0.2 + n * 0.32, 0.4), ly = y + 262 + n * 64;
        rect(x + 36, ly - 20, 12, 12, panel.color, show);
        text(line, x + 66, ly, { size: 29, font: SANS, weight: 500, color: C.ink, spacing: 0, alpha: show });
      });
      const grow = out((t - P.scores - i * 0.3) / 0.9), shown = appear(t, P.scores + i * 0.3, 0.35);
      rect(x + 36, y + tall - 150, wide - 72, 2, C.line, shown);
      const number = text(three(panel.score * grow), x + 36, y + tall - 44, { size: 104, color: panel.color, spacing: 0.03, alpha: shown });
      text(`${Math.round(panel.score * 100)}% OF EVERYTHING ON THE MAPS, BROUGHT HOME`, x + 60 + number, y + tall - 88, { size: 22, color: C.ink, spacing: 0.11, alpha: shown });
      text(panel.claim, x + 60 + number, y + tall - 54, { size: 22, color: C.dim, spacing: 0.11, alpha: shown });
      g.restore();
    });
    rise(t, P.note, () => text(F.best_model
      ? `ON AVERAGE OVER ITS RUNS · THE BEST MODEL, ${F.best_model.name}: ${three(F.best_model.score)} · A SIMPLE GREEDY RULE ON THE SAME NAVIGATOR: ${three(F.greedy)}`
      : `FOR SCALE · A SIMPLE GREEDY RULE ON THE SAME NAVIGATOR: ${three(F.greedy)} · THE BEST CLAUDE RUN: ${three(F.best_claude)}`,
      120, 946, { size: 24, color: C.dim, spacing: 0.13 }));
  };

  // Every campaign run of all nine models beside the planner (window.__MANH.tiers, from makers.tier_table): a row per
  // model, best average first; a dot for each run, a bar for the average; the planner's score as a gold line down
  // through all of them. cues[0] rings the best single run, cues[1] names the planner.
  const TIERS = { line: 0.6, rows: 0.9, step: 0.13, foot: 3.4, top: 268, row: 68, x0: 740, x1: 1540 };
  SCENES.tiers = (t, D, data, cues) => {
    backdrop('THE RESULTS');
    const T = M.tiers, R = T.rows, L = TIERS, X = v => L.x0 + (L.x1 - L.x0) * v / 0.5, bottom = L.top + R.length * L.row;
    heading(t, 'NINE MODELS · THREE MAPS IN A ROW', `${T.count} LIVE RUNS · THE SCORE IS THE SHARE OF EVERYTHING ON THE MAPS THAT A ROVER BROUGHT HOME`);
    rise(t, 0.5, () => {
      for (const v of [0, 0.1, 0.2, 0.3, 0.4, 0.5]) {
        rect(X(v), L.top - 4, 1, bottom - L.top + 8, 'rgba(243,234,217,.10)');
        text(v.toFixed(1), X(v), bottom + 34, { size: 22, color: C.faint, align: 'center', spacing: 0.05 });
      }
    });
    const best = T.best_run, ring = cues[0] !== undefined ? appear(t, cues[0], 0.35) : 0, ours = cues[1] !== undefined ? appear(t, cues[1], 0.35) : 0;
    R.forEach((r, i) => {
      const y = L.top + i * L.row, at = L.rows + i * L.step, k = appear(t, at, 0.35);
      if (k <= 0.003) return;
      const color = M.tiles[r.maker].text, grow = out((t - at - 0.1) / 0.7);
      g.save(); g.globalAlpha = k; g.translate((1 - out((t - at) / 0.45)) * -26, 0);
      tile(r.maker, 120, y + 10, 46);
      text(r.name, 184, y + 46, { size: 37, color, spacing: 0.08, bare: true });
      text(r.tier, 500, y + 44, { size: 20, color: C.faint, spacing: 0.16 });
      text(three(r.mean * grow), 706, y + 47, { size: 38, color: C.ink, spacing: 0.04, align: 'right' });
      rect(L.x0, y + 33, L.x1 - L.x0, 2, 'rgba(243,234,217,.12)');
      rect(L.x0, y + 23, Math.max(0, X(r.mean) - L.x0) * grow, 22, color, 0.3);
      r.runs.forEach((score, n) => {
        const show = appear(t, at + 0.25 + n * 0.08, 0.25);
        if (show <= 0.003) return;
        const same = r.runs.slice(0, n).filter(other => Math.abs(other - score) < 0.006).length, dy = same ? (same % 2 ? -12 : 12) * Math.ceil(same / 2) : 0;
        g.save(); g.globalAlpha *= show; g.fillStyle = color; g.beginPath(); g.arc(X(score), y + 34 + dy, 9, 0, Math.PI * 2); g.fill();
        g.strokeStyle = '#140d0b'; g.lineWidth = 2.5; g.stroke(); g.restore();
      });
      if (r.name === best.name && ring > 0.003) {            // the best single run of all: a ring, and what it scored
        const pulse = 1 + 0.5 * (1 - out((t - cues[0]) / 0.6));
        g.save(); g.globalAlpha *= ring; g.strokeStyle = C.ink; g.lineWidth = 3; g.beginPath(); g.arc(X(best.score), y + 34, 17 * pulse, 0, Math.PI * 2); g.stroke(); g.restore();
        text(`${three(best.score)} · BEST SINGLE RUN`, X(T.reference) + 34, y + 44, { size: 25, color: C.ink, spacing: 0.12, alpha: ring });
      }
      g.restore();
    });
    // the planner: a gold line down through every row
    const drawn = out((t - L.line) / 0.9), shown = appear(t, L.line, 0.3);
    rect(X(T.reference) - 2, L.top - 30, 4, (bottom - L.top + 38) * drawn, C.gold, shown);
    text('OUR PLANNER', X(T.reference) + 34, L.top + 34, { size: 30, color: C.gold, spacing: 0.14, alpha: shown * (0.55 + 0.45 * ours) });
    text(three(T.reference), X(T.reference) + 34, L.top + 34 + L.row, { size: 58, color: C.gold, spacing: 0.04, alpha: shown * (0.55 + 0.45 * ours) });
    text('NEVER LOST', X(T.reference) + 34 + 148, L.top + 10 + L.row, { size: 22, color: C.gold, spacing: 0.14, alpha: ours });
    text('A ROVER', X(T.reference) + 34 + 148, L.top + 38 + L.row, { size: 22, color: C.gold, spacing: 0.14, alpha: ours });
    rise(t, L.foot, () => {
      rect(120, 966, 1680, 2, C.line);
      text('THE SAME TASK, THE SAME FIVE TOOLS AND 45 MINUTES FOR ALL · A DOT IS ONE RUN · THE BAR IS THE AVERAGE', 120, 1012, { size: 26, color: C.dim, spacing: 0.13 });
    });
  };

  // What the planner is, with each block's method named (Manh, 15 November: "each block diagram should have the name of
  // the method + the text explaining what it is"). Kristján's planner scene is drawn as it is; the name of the method
  // behind each of its four links goes on a tab above the link, and lights with it. The names are what
  // lightlag_traverse/pilot.py and planning.py do: a three-state extended Kalman filter (position and heading bias)
  // with the commands still on their way played forward; a running estimate of each terrain's slip from wheel against
  // visual odometry; Dijkstra cost-to-go fields over the height grid, priced in ticks and energy against the sun's
  // curve; and for the route an orienteering search, a beam first and then iterated local search, replanned on the way.
  const METHODS = ['EKF · EXTENDED KALMAN FILTER', 'ONLINE SLIP ESTIMATE', 'DIJKSTRA FIELDS · SUN MODEL', 'BEAM + ITERATED LOCAL SEARCH'];
  SCENES.planner = (t, D, data, cues) => {
    SCENES.reference(t, D, data, cues);
    const left = 120, between = 58, wide = (1680 - 3 * between) / 4, top = 262;                  // his chain's geometry
    METHODS.forEach((name, i) => {
      const x = left + i * (wide + between), shown = appear(t, 0.5 + i * 0.12, 0.4);
      const lit = appear(t, cues[i] !== undefined ? cues[i] : i === 3 ? D - 2.2 : 1.0 + i * 1.6, 0.4);
      if (shown <= 0.003) return;
      g.save(); g.globalAlpha = shown;
      rect(x, top - 40, wide, 34, C.key); rect(x, top - 40, 6, 34, lit > 0.5 ? C.gold : C.faint);
      text(name, x + 22, top - 15, { size: 23, color: C.dim, spacing: 0.12, alpha: 1 - lit });
      text(name, x + 22, top - 15, { size: 23, color: C.gold, spacing: 0.12, alpha: lit });
      g.restore();
    });
  };

  // Was it luck? Kristján's 300-world chart, with every model in it instead of Claude's six programs (Manh, 15 November:
  // "it's only Claude? ... such that it includes all the models"). A row per model: its best program, world by world
  // against the planner on the same world (window.__MANH.worlds, from makers.worlds_table). The timing follows his
  // scene: the worlds sweep in, each row's count lands, cues[0] brings the totals, cues[1] the note.
  const WORLDS = { top: 286, row: 52, tall: 28, x0: 566, cell: 3.38, won: 1612, lost: 1782, rows: 0.7, sweep: 1.0 };       // the strips were 38 tall: "perhaps it was too thick"
  const sweepOf = D => Math.min(3.4, D * 0.3);
  SCENES.worlds = (t, D, data, cues) => {
    backdrop('AT SCALE · MODAL');
    const F = M.worlds, L = WORLDS, n = F.worlds, sweep = sweepOf(D), bottom = L.top + F.rows.length * L.row, count = v => v.toLocaleString('en-US');
    heading(t, `WAS IT LUCK? ${n} FRESH WORLDS`, `EVERY MODEL'S BEST PROGRAM REPLAYED ON MODAL · ${count(F.pairs)} MATCH-UPS · WORLDS NO MODEL HAD SEEN`);
    rise(t, 0.9, () => {
      text('PLANNER HIGHER', L.won, L.top - 16, { size: 20, color: C.faint, spacing: 0.12 });
      text('ROVERS LOST', L.lost, L.top - 16, { size: 20, color: C.faint, spacing: 0.12 });
    });
    F.rows.forEach((row, r) => {
      const y = L.top + r * L.row, k = appear(t, L.rows + r * 0.08, 0.3);
      if (k <= 0.003) return;
      g.save(); g.globalAlpha = k;
      tile(row.maker, 120, y - 5, 38);
      text(row.name, 174, y + 25, { size: 29, color: M.tiles[row.maker].text, spacing: 0.08, bare: true });
      text(row.tier, L.x0 - 18, y + 22, { size: 18, color: C.faint, spacing: 0.14, align: 'right' });
      const done = clamp((t - L.sweep - r * 0.12) / sweep, 0, 1), upto = Math.round(done * n);
      rect(L.x0, y, n * L.cell, L.tall, 'rgba(243,234,217,.045)');
      for (let i = 0; i < upto; i++) {
        const cell = row.cells[i];
        g.fillStyle = cell === 'x' ? C.red : cell === 'c' ? C.ice : cell === '=' ? C.shade : C.gold;
        g.globalAlpha = k * (cell === 'r' ? 0.82 : 1);
        g.fillRect(L.x0 + i * L.cell, y, L.cell - 0.8, L.tall);
      }
      g.globalAlpha = k * appear(t, L.sweep + r * 0.12 + sweep, 0.4);     // the row's counts, once its worlds are all in
      const ahead = text(`${row.reference_higher}`, L.won, y + 27, { size: 34, color: C.gold, spacing: 0.04 });
      text(`/ ${n}`, L.won + ahead + 10, y + 27, { size: 21, color: C.faint, spacing: 0.08 });
      text(`${row.lost}`, L.lost, y + 27, { size: 34, color: row.lost ? C.red : C.faint, spacing: 0.04 });
      g.restore();
    });
    rise(t, 1.2, () => {
      let x = L.x0; const y = bottom + 28;
      for (const [color, label] of [[C.gold, 'THE PLANNER SCORED HIGHER'], [C.red, "THE MODEL'S ROVER RAN ITS BATTERY FLAT"], [C.ice, "THE MODEL'S PROGRAM SCORED HIGHER"]]) {
        rect(x, y - 18, 20, 20, color); x += 32; x += text(label, x, y, { size: 22, color: C.dim, spacing: 0.12 }) + 40;
      }
    });
    const at = cues && cues[0] !== undefined ? cues[0] : 1.4 + sweep, note = cues && cues[1] !== undefined ? cues[1] : at + 3;
    const stats = [[`${count(F.reference_higher)} / ${count(F.pairs)}`, 'MATCH-UPS IN WHICH THE PLANNER SCORED HIGHER', C.gold, 122, 640],
      [`${F.reference_lost}`, `PLANNER ROVERS LOST ON ${n} WORLDS`, C.gold, 900, 360], [`${F.lost}`, "ROVERS LOST BY THE MODELS' PROGRAMS", C.red, 1330, 470]];
    stats.forEach(([big, label, color, x, wide], i) => rise(t, at + i * 0.35, () => {
      text(big, x, 956, { size: 96, color, spacing: 0.03 });
      paragraph(label, x, 996, wide, 30, { size: 25, color: C.dim, spacing: 0.12 });
    }));
    rise(t, note, () => {
      const y = bottom + 72;
      rect(L.x0, y - 24, 6, 58, C.ice);
      text(`A MODEL AHEAD IN ${F.wins} OF ${count(F.pairs)}, NEVER BY MORE THAN ${two(F.widest_win)} · ${F.ties} TIES`, L.x0 + 22, y, { size: 24, color: C.ink, spacing: 0.12 });
      text(`COUNTING ALL ${F.all.programs} PROGRAMS THE MODELS LEFT: ${count(F.all.reference_higher)} OF ${count(F.all.pairs)} FOR THE PLANNER`, L.x0 + 22, y + 32, { size: 24, color: C.dim, spacing: 0.12 });
    });
  };

  // ---------------------------------------------------------------- the long film's own slides
  // The game: the five tools every driver gets, then the six catches, each lit when the voice gets to it (cues).
  const RULES = { tools: 0.7, rows: 1.6, step: 0.14 };
  SCENES.rules = (t, D, data, cues) => {
    backdrop('THE GAME');
    const G = M.game;
    heading(t, 'ONE ROVER · ONE DAY · FIVE TOOLS', `${G.ticks} STEPS OF DAYLIGHT · ${G.width} × ${G.height} M OF GROUND · ${G.targets_at_launch} TARGETS AT SUNRISE, MORE ON THE WAY · ${G.sites} SITES IN A ROW`);
    const notes = ['WHAT IS FIXED', 'THE GROUND', 'WHAT THE ROVER REPORTS', 'SEND COMMANDS', 'LET TIME PASS'], wide = 312, gap = 30;
    G.tools.forEach((name, i) => {
      const x = 120 + i * (wide + gap), k = appear(t, RULES.tools + i * 0.1, 0.35);
      if (k <= 0.003) return;
      g.save(); g.globalAlpha = k; g.translate(0, (1 - out((t - RULES.tools - i * 0.1) / 0.5)) * 18);
      rect(x, 262, wide, 96, C.key); rect(x, 262, wide, 4, C.ice);
      text(name + '()', x + 24, 308, { size: 30, font: MONO, weight: 500, color: C.ink, spacing: 0 });
      text(notes[i], x + 24, 342, { size: 20, color: C.dim, spacing: 0.14 });
      g.restore();
    });
    const rows = [
      ['COMMANDS LAND LATE', `SENT NOW, CARRIED OUT ${G.delay + 1} STEPS LATER, ONE PER STEP`],
      ['THE NEWS IS OLD', `EVERY REPORT SHOWS THE ROVER WHERE IT WAS ${G.delay} STEPS AGO, WITH NOISE`],
      ['WHEELS SLIP', 'DIFFERENTLY ON SAND, REGOLITH, ROCK FIELD AND BEDROCK · HOW MUCH IS HIDDEN'],
      ['TOO STEEP MEANS STOP', `ABOVE A ${G.tilt_percent}% SLOPE THE ROVER STOPS AND EVERY QUEUED ORDER IS WIPED`],
      ['THE ONLY FUEL IS THE SUN', 'LOW AT DAWN AND DUSK, HIGH AT NOON · A BATTERY AT ZERO ENDS THE ROVER'],
      ['HOME, OR HALF, OR NOTHING', 'AT THE LANDER: EVERYTHING · ANYWHERE ELSE: HALF · BATTERY FLAT: NOTHING'],
    ];
    rows.forEach(([title, line], i) => {
      const y = 426 + i * 92, k = appear(t, RULES.rows + i * RULES.step, 0.35);
      if (k <= 0.003) return;
      const lit = cues[i] !== undefined ? appear(t, cues[i], 0.4) : 1, last = i === rows.length - 1;
      g.save(); g.globalAlpha = k;
      rect(120, y, 1680, 78, C.key); rect(120, y, 8, 78, lit > 0.5 ? (last ? C.red : C.gold) : C.faint);
      text(String(i + 1), 156, y + 52, { size: 40, color: C.faint, spacing: 0.02 });
      text(title, 214, y + 50, { size: 36, color: C.faint, spacing: 0.1, alpha: 1 - lit });
      text(title, 214, y + 50, { size: 36, color: last ? C.red : C.gold, spacing: 0.1, alpha: lit });
      text(line, 760, y + 49, { size: 24, color: C.dim, spacing: 0.11, alpha: 0.45 + 0.55 * lit });
      g.restore();
    });
  };

  // How every site of every campaign run ended, model by model (window.__MANH.outcomes, from makers.outcomes_table):
  // a square per site, three per run, in the order of the average. The cues turn the light on one lab after another
  // (Google, OpenAI, Anthropic), then on the fast model with the best average, then on everything with what a run cost.
  const OUTCOMES = { rows: 0.8, step: 0.11, top: 300, row: 66, x0: 610, box: 30, legend: 0.6,
    colour: { home: '#9fd8ff', away: '#ffd27a', lost: '#ff4a2f', idle: '#4a3a33' },
    label: { home: 'HOME', away: 'HALF', lost: 'LOST', idle: 'NEVER LEFT' } };
  SCENES.outcomes = (t, D, data, cues) => {
    backdrop('THE RESULTS');
    const O = M.outcomes, L = OUTCOMES, focus = [['google'], ['openai'], ['anthropic'], ['GEMINI 4 HYDROGEN'], null];
    heading(t, 'EVERY LAB FAILS IN ITS OWN WAY', 'A SQUARE IS ONE SITE OF ONE RUN · THREE SITES TO A RUN · BEST RUN FIRST');
    rise(t, L.legend, () => {
      let x = 120;
      for (const [kind, words] of [['home', 'HOME: KEEPS EVERYTHING'], ['away', 'ALIVE, NOT HOME: KEEPS HALF'], ['lost', 'BATTERY FLAT: KEEPS NOTHING'], ['idle', 'NEVER LEFT THE LANDER']]) {
        rect(x, 244, 22, 22, L.colour[kind]); x += 34; x += text(words, x, 263, { size: 22, color: C.dim, spacing: 0.12 }) + 44;
      }
    });
    let stage = -1;
    cues.forEach((cue, i) => { if (cue !== undefined && t >= cue) stage = i; });
    const turn = stage >= 0 ? appear(t, cues[stage], 0.45) : 0;
    const lit = (row, which) => which < 0 || !focus[which] ? 1 : (focus[which].includes(row.maker) || focus[which].includes(row.name) ? 1 : 0.24);
    O.rows.forEach((row, r) => {
      const y = L.top + r * L.row, at = L.rows + r * L.step, k = appear(t, at, 0.35);
      if (k <= 0.003) return;
      const colour = M.tiles[row.maker].text, bright = lerp(lit(row, stage - 1), lit(row, stage), turn);
      g.save(); g.globalAlpha = k * bright; g.translate((1 - out((t - at) / 0.45)) * -24, 0);
      tile(row.maker, 120, y + 2, 44);
      text(row.name, 180, y + 37, { size: 33, color: colour, spacing: 0.08, bare: true });
      text(row.tier, L.x0 - 24, y + 34, { size: 18, color: C.faint, spacing: 0.14, align: 'right' });
      row.runs.forEach((run, n) => {
        const x = L.x0 + n * 134, show = appear(t, at + 0.2 + n * 0.07, 0.3);
        run.sites.forEach((kind, site) => rect(x + site * (L.box + 6), y + 2, L.box, L.box, L.colour[kind], show));
        text(two(run.score), x, y + 54, { size: 19, color: C.dim, spacing: 0.08, alpha: show });
      });
      text(three(row.mean), 1242, y + 38, { size: 38, color: C.ink, spacing: 0.04, align: 'right', alpha: appear(t, at + 0.3, 0.3) });
      const parts = ['home', 'away', 'lost', 'idle'].filter(kind => row.count[kind]).map(kind => `${row.count[kind]} ${L.label[kind]}`);
      text(parts.join(' · '), 1290, y + 35, { size: 23, color: C.dim, spacing: 0.11, alpha: appear(t, at + 0.35, 0.3) });
      g.restore();
    });
    rise(t, 0.9, () => text('AVERAGE', 1242, L.top - 14, { size: 19, color: C.faint, spacing: 0.14, align: 'right' }));
    if (cues[4] !== undefined) rise(t, cues[4], () => {
      const c = O.costs, dollars = v => '$' + v.toFixed(2);
      rect(120, 918, 1680, 2, C.line);
      text(`WHAT AN AGENT RUN COST, ON AVERAGE: FROM ${dollars(c['GPT-6 LUNA'])} (GPT-6 LUNA) TO ${dollars(c['GEMINI 4 ARGON'])} (GEMINI 4 ARGON) · THE BEST AVERAGE SCORE, GEMINI 4 HYDROGEN: ${dollars(c['GEMINI 4 HYDROGEN'])} A RUN`,
        120, 968, { size: 25, color: C.gold, spacing: 0.12 });
      text(`CLAUDE OPUS 5.5 ${dollars(c['CLAUDE OPUS 5.5'])} · CLAUDE SONNET 5.5 ${dollars(c['CLAUDE SONNET 5.5'])} · GPT-6.1 SOL ${dollars(c['GPT-6.1 SOL'])} · GEMINI 4 CARBON ${dollars(c['GEMINI 4 CARBON'])} · AS THE AGENT TOOL COUNTED IT`,
        120, 1006, { size: 22, color: C.dim, spacing: 0.12 });
    });
  };

  // Why the planner is a fair thing to measure against: five reasons with the number behind each (window.__MANH.game,
  // .tiers, .worlds), one lit per cue.
  SCENES.why = (t, D, data, cues) => {
    backdrop('THE REFERENCE');
    const G = M.game, T = M.tiers, F = M.worlds, count = v => v.toLocaleString('en-US');
    heading(t, 'WHY MEASURE AGAINST THIS ONE?', 'A YARDSTICK HAS TO BE OPEN, REPEATABLE, SAFE AND BEATABLE');
    const rows = [
      [`${G.tools.length} TOOLS`, 'IT PLAYS THROUGH THE SAME FIVE TOOLS AS EVERY AGENT', 'NO HIDDEN INFORMATION · WHAT IT KNOWS, IT LEARNED FROM THE MAP AND THE TELEMETRY'],
      [`${count(G.reference_lines)} LINES`, 'PLAIN PYTHON, STANDARD LIBRARY ONLY', 'READ IT, RUN IT, CHANGE IT · NO MODEL, NO WEIGHTS, NO GPU'],
      [three(T.reference), 'THE SAME SCORE EVERY TIME', 'ON A LAPTOP, ON MODAL AND THROUGH HARBOR · ONE COMMAND, ABOUT TWO MINUTES'],
      [`${F.reference_lost} LOST`, 'IT HAS NEVER LOST A ROVER', `${G.sites} CAMPAIGN SITES AND ${F.worlds} FRESH WORLDS · IT WAITS FOR THE SUN INSTEAD`],
      [`${100 - T.reference_percent}%`, 'IT CAN BE BEATEN', `IT LEAVES ${100 - T.reference_percent}% OF THE VALUE ON THE GROUND · A MODEL'S PROGRAM SCORED HIGHER IN ${F.wins} OF ${count(F.pairs)} MATCH-UPS`],
    ];
    rows.forEach(([big, title, line], i) => {
      const y = 262 + i * 144, k = appear(t, 0.7 + i * 0.13, 0.35);
      if (k <= 0.003) return;
      const lit = cues[i] !== undefined ? appear(t, cues[i], 0.4) : 1;
      g.save(); g.globalAlpha = k;
      rect(120, y, 1680, 124, C.key); rect(120, y, 8, 124, lit > 0.5 ? C.gold : C.faint);
      text(big, 160, y + 84, { size: 70, color: C.faint, spacing: 0.03, alpha: 1 - lit });
      text(big, 160, y + 84, { size: 70, color: C.gold, spacing: 0.03, alpha: lit });
      text(title, 560, y + 56, { size: 38, color: C.ink, spacing: 0.1, alpha: 0.5 + 0.5 * lit });
      text(line, 560, y + 96, { size: 23, color: C.dim, spacing: 0.12, alpha: 0.5 + 0.5 * lit });
      g.restore();
    });
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
    lineup() {
      const L = LINEUP, list = [];
      for (let c = 0; c < 3; c++) list.push({ at: L.heads + c * 0.25, kind: 'chime_soft', step: c * 2, check: true });
      for (let tier = 0; tier < 3; tier++) {
        list.push({ at: L.first + tier * L.step, kind: 'swell', check: true });
        for (let c = 0; c < 3; c++) list.push({ at: L.first + tier * L.step + 0.12 + c * 0.13, kind: 'tick', step: tier * 2 + c, check: true });
      }
      list.push({ at: L.foot, kind: 'hit_soft', check: true });
      return list;
    },
    drivers() {
      const P = DRIVERS, list = [];
      P.panels.forEach((at, i) => list.push({ at, kind: 'swell', check: true }));
      for (let i = 0; i < 2; i++) for (let n = 0; n < 3; n++) list.push({ at: P.lines + i * 0.2 + n * 0.32, kind: 'tick', step: n + i, check: true });
      list.push({ at: P.scores, kind: 'bar', score: 0.476, gold: true, check: true }, { at: P.scores + 0.3, kind: 'bar', score: 0.366, check: true });
      list.push({ at: P.note, kind: 'chime_soft', step: 1, check: true });
      return list;
    },
    rules(D, data, cues) {
      const list = [];
      for (let i = 0; i < 5; i++) list.push({ at: RULES.tools + i * 0.1, kind: 'tick', step: i, check: true });
      for (let i = 0; i < 6; i++) if (cues[i] !== undefined) list.push({ at: cues[i], kind: i === 5 ? 'hit_soft' : 'chime_soft', step: i, check: true });
      return list;
    },
    outcomes(D, data, cues) {
      const L = OUTCOMES, list = [{ at: L.legend, kind: 'chime_soft', check: true }];
      M.outcomes.rows.forEach((row, r) => list.push({ at: L.rows + r * L.step, kind: 'tick', step: r % 6, check: true }));
      cues.forEach((cue, i) => { if (cue !== undefined) list.push({ at: cue, kind: i === 4 ? 'hit_soft' : 'swell', check: true }); });
      return list;
    },
    why(D, data, cues) {
      const list = [];
      for (let i = 0; i < 5; i++) list.push({ at: 0.7 + i * 0.13, kind: 'tick', step: i, check: true });
      for (let i = 0; i < 5; i++) if (cues[i] !== undefined) list.push({ at: cues[i], kind: i === 4 ? 'hit_soft' : 'chime_soft', step: i, check: true });
      return list;
    },
    planner(D, data, cues) { return SFX.reference(D, data, cues); },      // his scene's sounds: the tabs light with his links
    learning3(D, data, cues) {                                // Kristján's "and models that learn": five bars, the percentages, then his two panels
      const F = data.final.fresh, list = [];
      [[F.initial, 0.9], [F.ppo, 1.4], [F.replay, 1.7], [F.greedy, 2.0], [F.reference, 2.3]].forEach(([score, at], i) => list.push({ at, kind: 'bar', score, gold: i === 4, step: i, check: true }));
      list.push({ at: 2.6, kind: 'chime', step: 2, check: true });
      const camp = cues && cues[0] !== undefined ? cues[0] : 3.4, plan = cues && cues[1] !== undefined ? cues[1] : camp + 3;
      list.push({ at: camp, kind: 'swell', check: true }, { at: plan, kind: 'hit_soft', check: true });
      return list;
    },
    worlds(D, data, cues) {
      const L = WORLDS, sweep = sweepOf(D), rows = M.worlds.rows.length, list = [{ at: L.sweep, kind: 'flow', len: sweep + 0.9, rise: 1 }];   // the worlds sweep in
      for (let r = 0; r < rows; r++) list.push({ at: L.sweep + r * 0.12 + sweep, kind: 'tick', step: r % 6, check: true });               // each row's count
      const at = cues && cues[0] !== undefined ? cues[0] : 1.4 + sweep, note = cues && cues[1] !== undefined ? cues[1] : at + 3;
      list.push({ at, kind: 'hit_soft', check: true }, { at: at + 0.35, kind: 'tick', step: 1, check: true }, { at: at + 0.7, kind: 'tick', step: 3, check: true });
      list.push({ at: note, kind: 'chime_soft', check: true });
      return list;
    },
    tiers(D, data, cues) {
      const L = TIERS, list = [{ at: L.line, kind: 'flow', len: 0.9, rise: -1, check: true }];
      M.tiers.rows.forEach((row, i) => list.push({ at: L.rows + i * L.step, kind: 'bar', score: row.mean, step: i, check: true }));
      if (cues[0] !== undefined) list.push({ at: cues[0], kind: 'tick', step: 2, check: true });
      if (cues[1] !== undefined) list.push({ at: cues[1], kind: 'hit_soft', check: true });
      list.push({ at: L.foot, kind: 'chime_soft', check: true });
      return list;
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
