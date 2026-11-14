// Film dressing for the demo page while it is recorded: a chapter chip, the title over the map,
// one caption at a time, and a fade to black. The page underneath is the real demo, untouched
// apart from hiding its own opening card and banners, which the film replaces.
(() => {
  const s = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--s')) || 1;
  const stage = window.innerWidth - Math.round(340 * s), centre = stage / 2;
  const layer = document.createElement('div');
  layer.id = 'film';
  layer.innerHTML = `<style>
    #title, #banner { display: none !important; }
    #film { position: fixed; inset: 0; pointer-events: none; z-index: 50; text-transform: uppercase; color: #f3ead9;
      font-family: "DIN Condensed", "Avenir Next Condensed", "Roboto Condensed", "Arial Narrow", sans-serif; font-weight: 700; }
    #film .chapter { position: absolute; top: ${Math.round(118 * s)}px; left: ${Math.round(16 * s)}px; padding: 10px 22px 5px; white-space: nowrap;
      background: rgba(11, 8, 7, .84); border-left: 6px solid #ffb224; color: #ffb224; font-size: 30px; letter-spacing: .22em; }
    #film .title { position: absolute; left: 0; top: 0; bottom: 0; width: ${stage}px; display: grid; place-items: center;
      background: radial-gradient(ellipse at center, rgba(11, 8, 7, .84) 0%, rgba(11, 8, 7, .5) 50%, rgba(11, 8, 7, 0) 78%); }
    #film .title h1 { margin: 0; font-size: 210px; letter-spacing: .2em; line-height: .86; text-align: center; text-indent: .2em; }
    #film .title h1 span { display: block; color: #ff4a2f; }
    #film .title p { margin: 26px 0 0; font-size: 36px; letter-spacing: .22em; color: #ffb224; text-align: center; }
    #film .caption { position: absolute; left: ${centre}px; bottom: 168px; transform: translateX(-50%); white-space: nowrap;
      padding: 18px 34px 10px; background: rgba(11, 8, 7, .9); border-left: 7px solid #ffb224; font-size: 54px; letter-spacing: .1em; }
    #film .fade { position: absolute; inset: 0; background: #000; opacity: 0; }
  </style>
  <div class="chapter" style="opacity:0"></div>
  <div class="title" style="opacity:0"><div><h1>LIGHTLAG<span>TRAVERSE</span></h1><p>AN RL ENVIRONMENT · A HARBOR TASK · JUNCTION 2026</p></div></div>
  <div class="caption" style="opacity:0"></div>
  <div class="fade"></div>`;
  document.body.append(layer);
  const chapter = layer.querySelector('.chapter'), title = layer.querySelector('.title'), caption = layer.querySelector('.caption'), fade = layer.querySelector('.fade');
  // a caption with side 'left' sits clear of the mini-map, which the chase camera shows bottom right
  const left = (Math.round(16 * s) + stage - Math.round(14 * s) - Math.round(310 * s) - 30) / 2;
  const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
  const window_ = (ts, cue, edge) => clamp((ts - cue.from) / edge, 0, 1) * clamp((cue.to - ts) / edge, 0, 1);
  window.__overlay = {
    cues: [],
    chapter(text) { chapter.textContent = text || ''; chapter.dataset.on = text ? '1' : ''; },
    // ts: seconds since the cues were set; black: how much of the picture the fade covers; shot: seconds into the shot
    draw(ts, black, shot) {
      let top = 0, line = null, alpha = 0, side = null;
      for (const cue of this.cues) {
        if (cue.kind === 'title') top = Math.max(top, window_(ts, cue, 0.45));
        else if (cue.kind === 'caption') { const a = window_(ts, cue, 0.22); if (a > alpha) { alpha = a; line = cue.text; side = cue.side; } }
      }
      title.style.opacity = top.toFixed(3);
      if (line !== null && caption.textContent !== line) { caption.textContent = line; caption.style.left = (side === 'left' ? left : centre) + 'px'; }
      caption.style.opacity = alpha.toFixed(3);
      chapter.style.opacity = chapter.dataset.on ? (clamp((shot - 0.2) / 0.4, 0, 1) * (1 - top)).toFixed(3) : 0;
      fade.style.opacity = clamp(black, 0, 1).toFixed(3);
    },
  };
})();
