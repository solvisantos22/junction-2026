# The ghost demo

**Open [`../ghosts-demo.html`](../ghosts-demo.html) by double-clicking it.** One file, no server, no network. Chrome; **Enter** to start, **F** for full screen.

It replays the [Lightlag Live](../../docs/lightlag-live.md) campaign: six missions in a row, with every recorded run on the same ground at the same time.

- **Gold** is the reference controller.
- **Ice blue** is the Claude run you are following. It starts on the best Claude run; click a name in the standings, or press **Tab**, to follow another.
- **Dark shadows** are every other Claude run. A shadow turns red where its battery ran out.
- The **ring on a thin line** behind the blue rover is the last position its program was told: three ticks old and noisy. The gap between the ring and the rover is what the program has to work out for itself.
- Under each flag, one **dot per rover** that sampled it, in that rover's colour.
- **Standings** on the right: the mean over the missions so far, counting the mission under way at what the rover is carrying. A bar is one mission; `½` means the rover finished away from base, `LOST` that its battery ran out. Rows reorder as the scores change.

Nothing is simulated in the page: every path is what that rover really drove in a saved run under `docs/lightlag-runs/live-*/`.

## Controls

| Key | Does |
|---|---|
| Enter / space | start, play / pause |
| ← → | step one tick |
| 1–6 | jump to that mission |
| Tab, or click a name | follow another Claude run |
| - = | slower, faster (1× is real time: one tick per second) |
| F | full screen |
| Esc | back to the opening card |

Adding `#auto` to the address starts it by itself. `#t=137.5` opens it paused at campaign tick 137.5, which is mission 3, tick 37.5, so a moment can be linked.

## Rebuild it

```sh
python3 viewer/build_ghosts.py     # refreshes viewer/ghosts/data.json and viewer/ghosts-demo.html
```

It shows every folder `docs/lightlag-runs/live-*/` that has a `run.json` (who played and how) and refuses runs that did not play the reference's missions. For development, serve `viewer/` with any static server and open `ghosts/index.html`.

The terrain, rover and lander are the Mars demo's, copied from `viewer/mars/app.js`, so both pages look alike; three.js comes from `viewer/mars/vendor/`.

## Limits

- **Checked in Chrome only**, on one laptop.
- **Rovers glide between ticks.** A rover turns, then drives, within each tick; the saved runs hold one position per tick.
- **A replay holds the true rover states**, so the page is evaluator-side material.
