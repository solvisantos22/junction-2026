# The ghost demo

Every recorded run on the same ground at the same time: the reference in gold, the Claude run you follow in blue, every other Claude run as a dark shadow. One file per page, no server, no network. Chrome; **Enter** to start, **F** for full screen.

| Page | Shows |
|---|---|
| [`../ghosts-demo.html`](../ghosts-demo.html) | [Lightlag Live](../../docs/lightlag-live.md): six missions in a row on a real-time clock, every Claude model's autopilot against the reference |
| [`../ghosts-rush-501.html`](../ghosts-rush-501.html) | The team's saved turn-based runs on `rush` seed 501: six attempts by Claude Opus 5.5 driving by hand, four of which lose the rover, against the reference |
| [`../ghosts-rush-501-control.html`](../ghosts-rush-501-control.html) | The same six attempts beside an autopilot the same model wrote in one reply. Four by-hand rovers are ahead of the reference at tick 24; three of them are lost in the last two ticks and the fourth is stranded. The autopilot ties the reference at 0.83 |

## What is on screen

- **Gold** is the reference controller.
- **Ice blue** is the Claude run you are following. It starts on the best Claude run; click a name in the standings, or press **Tab**, to follow another.
- **Dark shadows** are every other Claude run. A shadow turns red where its battery ran out.
- In Lightlag Live a shadow that stops and stands still is not always a driving mistake: two programs were stopped by their agent's shell tool, and one by its agent ending the session. The opening card says which ([what happened](../../docs/lightlag-live.md#the-launch-trap-in-011-and-its-fix)).
- The **ring on a thin line** behind the blue rover is the last position its operator or program was told: three ticks old, and noisy in Lightlag Live. The gap between the ring and the rover is what has to be worked out.
- Under each flag, one **dot per rover** that sampled it, in that rover's colour.
- **Standings** on the right: the score so far, counting the mission under way at what the rover is carrying. A bar is one mission; `½` means the rover finished away from base, `LOST` that its battery ran out. Rows reorder as the scores change, so a rover can lead until the moment it is lost.
- In Lightlag Live, each mission ends with a card: the reference's score against the best Claude score in that mission.

Nothing is simulated in the page: every path is what that rover really drove in a saved run under `docs/lightlag-runs/`.

## Controls

| Key | Does |
|---|---|
| Enter / space | start, play / pause |
| ← → | step one tick |
| 1–6 | jump to that mission |
| Tab, or click a name | follow another Claude run |
| - = | slower, faster (1× is one tick per second) |
| F | full screen |
| Esc | back to the opening card |

Adding `#auto` to the address starts it by itself. `#t=137.5` opens it paused at campaign tick 137.5, which is mission 3, tick 37.5, so a moment can be linked.

## Rebuild

```sh
python3 viewer/build_ghosts.py                                         # viewer/ghosts-demo.html and viewer/ghosts/data.json
python3 viewer/build_ghosts.py --set viewer/ghosts/sets/rush-501.json  # viewer/ghosts-rush-501.html
python3 viewer/build_ghosts.py --set viewer/ghosts/sets/rush-501-control.json
```

Without `--set` the page shows every folder `docs/lightlag-runs/live-*/` that has a `run.json` (who played and how). A set file lists run folders and names them, for runs that carry no `run.json`; it can also replace the page's words. Either way the build refuses runs that did not play the reference's missions. For development, serve `viewer/` with any static server and open `ghosts/index.html`.

The terrain, rover and lander are the Mars demo's, copied from `viewer/mars/app.js`, so the pages look alike; three.js comes from `viewer/mars/vendor/`.

## Limits

- **Checked in Chrome only**, on one laptop.
- **Rovers glide between ticks.** A rover turns, then drives, within each tick; the saved runs hold one position per tick.
- **The seed-501 pages show the six original-prompt attempts only.** With a one-page accounting aid the same model scored 0.92 and 0.88 on that map; the first page says so and neither shows them.
- **The autopilot on the control page was not written for that map.** It is one reply to one request for a mission autopilot at the standard noise level, replayed on seed 501 in a sandbox ([request, reply and scores](../../docs/lightlag-runs/explore-standard-noise/README.md)). The build checks that it played the reference's mission.
- **A replay holds the true rover states**, so the pages are evaluator-side material.
