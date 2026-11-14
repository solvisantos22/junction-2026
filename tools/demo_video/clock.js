// A virtual clock for frame-exact recording. Installed before the page's own scripts run, it
// replaces the animation clock: time moves only when the recorder calls __film.step(ms). Each
// step runs the page's animation-frame callbacks once with the new time, and moves every CSS
// transition and animation by the same amount, so a frame looks the same however long the
// machine took to draw it.
(() => {
  let now = 0, nextId = 1;
  const queue = [], started = new Map();
  const epoch = Date.now();
  performance.now = () => now;
  Date.now = () => epoch + Math.round(now);
  window.requestAnimationFrame = callback => { const id = nextId++; queue.push({ id, callback }); return id; };
  window.cancelAnimationFrame = id => { const i = queue.findIndex(item => item.id === id); if (i >= 0) queue.splice(i, 1); };

  function moveAnimations() {
    const live = new Set(document.getAnimations());
    for (const animation of started.keys()) if (!live.has(animation)) started.delete(animation);
    for (const animation of live) {
      if (!started.has(animation)) { started.set(animation, now); try { animation.pause(); } catch (error) { continue; } }
      const timing = animation.effect && animation.effect.getComputedTiming ? animation.effect.getComputedTiming() : null;
      const end = timing ? timing.endTime : Infinity, t = now - started.get(animation);
      try {
        if (Number.isFinite(end) && t >= end) { animation.finish(); started.delete(animation); }
        else animation.currentTime = t;
      } catch (error) { /* an animation that went away mid-step */ }
    }
  }

  window.__film = {
    now: () => now,
    step(ms) {
      now += ms;
      for (const { callback } of queue.splice(0, queue.length)) callback(now);
      void document.body.offsetHeight;          // style changes made by the callbacks start their transitions now
      moveAnimations();
      return now;
    },
  };
})();
