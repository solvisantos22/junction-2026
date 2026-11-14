# The traverse demo

Every recorded run of one [Lightlag Traverse](../../lightlag_traverse/environment.py) mission, on the ground it was driven on: a 600 m by 400 m height map with craters, a scarp, sand, rock fields and bedrock, one day of sun, about 46 science targets. The reference in gold, the run you follow in blue, every other run as a dark shadow. One file, no server, no network: [`../traverse-demo.html`](../traverse-demo.html). Chrome; **Enter** to start, **C** for the chase camera, **F** for full screen.

## What is on screen

- **The ground** is the simulator's height grid, drawn 2.75 times too tall so that 20 m of relief over 600 m can be read. Rust is regolith, pale and rippled is sand, dark and stony is a rock field, light slabs are bedrock.
- **Dark, layered ground is too steep to drive**: steeper than 0.85 of the tilt at which a rover is stopped. It is why rovers go around crater walls, in through a crater's worn side, and through the scarp at the two places marked `PASS`.
- **The sun** rises in the east, on the right, and sets in the west. Its height over the mission is the simulator's solar formula, so the shadows are long at both ends of the day. The arc in the top strip shows where it stands, with the hour and the share of full sunlight that charges the batteries.
- **Gold** is the reference controller. **Ice blue** is the run you follow: the best Claude run, or the best scripted stand-in while no model has driven. **Dark shadows** are every other run. A run driven by a script carries a `SCRIPTED` tag wherever it is named.
- A rover whose battery ran out **turns red where it died**. A **red cross** marks a place where a rover was stopped because it drove onto ground too steep for it, or to the map's edge. Both are also announced at the top right.
- **Flags** are the targets, with their value over them. The bar under a value runs down to the deadline and turns red near it; after the deadline the flag hangs at half-mast and shows what a late sample is worth. A target found during the mission appears at its tick, in green, with a ring spreading from it. Under a flag, one **dot per rover** that sampled it.
- The **ring on a thin line** behind the blue rover is the last position its operator was told: three ticks old and off by about a metre.
- **Standings** on the right: the value a rover carries over all the value on the map. A lost rover drops to zero at once. At the last tick the scores settle: `½` means the rover finished outside the 4 m ring at the lander. The end card gives the reference's score against the best other run's, and says how that run ended.
- **Battery** of the reference and of the run you follow, at the bottom left. The **timeline** has the day's sunlight behind it, the reference's samples above the line, the followed run's samples and stops below, and every loss in red.
- The **chase camera** rides behind the followed rover with everything life-size, and a mini-map of the whole ground. From above, rovers, flags and the lander are drawn several times larger than life, or they would be specks.

Nothing is simulated in the page: every path is what that rover really drove in a saved run.

## Controls

| Key | Does |
|---|---|
| Enter / space | start, play / pause |
| ← → | step one tick (with shift, ten) |
| C | switch between the overview and the chase camera |
| Tab, or click a name | follow another run |
| - = | slower, faster (1× is one tick a second; it opens at the speed that plays the mission in about 70 seconds) |
| F | full screen |
| Esc | back to the opening card |

Adding `#auto` to the address starts it by itself. `#t=137` opens it paused at tick 137, so a moment can be linked; `#t=137&chase` opens it in the chase camera and `&follow=<run folder or label>` picks the run to follow.

## Rebuild

```sh
python3 viewer/build_traverse.py                  # viewer/traverse-demo.html and viewer/traverse/data.json
python3 viewer/build_traverse.py --runs a/folder  # from the traverse-* run folders somewhere else
python3 -m unittest discover -s tests/viewer -p "test_build_traverse.py" -v
```

The page shows every folder `docs/lightlag-runs/traverse-*/` that has a `run.json` (`kind`: `reference`, `claude` or `scripted`; `label`; `how`) and the evaluator's `artifacts/evaluator/replay.json` and `result.json`. Exactly one run must be the reference. The build refuses a run that did not play the reference's world (seed, ground, targets, mission settings, physics), a replay that is not one state per tick, and a `result.json` that disagrees with its replay. No count or size is written into the builder or the page: they come from the replay. For development, serve `viewer/` with any static server and open `traverse/index.html`.

The rover, lander, colours and controls are the [ghost demo](../ghosts/README.md)'s; three.js comes from `viewer/mars/vendor/`.

## Limits

- **Checked in Chrome only**, on one laptop.
- **Heights are exaggerated 2.75 times**, and with them every slope and every tilt of a rover. Distances on the ground are true.
- **The ground beyond the map's edge line is scenery**, grown out of the map's edge so there is a horizon. Only the map is data.
- **Terrain borders and cliff outlines are smoothed for drawing.** The simulator works per 5 m cell; the page blends class and slope between cell centres, so a border or a cliff edge can be drawn a metre or two from where the simulator has it.
- **The sun's path leans 28° to the north**, so that noon still throws shadows. The sunlight figure in the top strip is the simulator's exact formula; the hour reads the sun's place on its arc as a twelve-hour day with sunrise at six.
- **Rovers glide between ticks and face the way they travelled.** The saved runs hold one position per tick.
- **The lander stands beside the base point**, not on it, so that a rover at base can be seen. The white ring is the rule: 4 m around the base point.
- **A replay holds the true rover states**, so the page is evaluator-side material.
