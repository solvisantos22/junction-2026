# Lightlag demo

## The 3D Mars demo

**Open [`mars-demo.html`](mars-demo.html) by double-clicking it.** It is one file with everything inside, so it needs no server and no network. Use Chrome, press **F** for full screen, then **space**.

It replays recorded runs. Nothing is simulated in the page and nothing is invented: every tool call it shows was made by the agent in that run.

### Mission view (four screens, one run)

| Screen | What it shows |
|---|---|
| **Mars · what is really happening** | The rover right now, with a hologram where the operator last saw it |
| **Earth · what the operator sees** | The same scene as it arrives on Earth, 3 ticks late |
| **Mission map** | Top-down: the real path, the last seen position, commands still in transit |
| **Agent console** | The five MCP tools as buttons that light up when the agent calls them, the call being made, commands and telemetry travelling between Earth and Mars, and the log of every call |

The default run is **Claude Opus 5.5 playing through Harbor** (the saved run in `docs/lightlag-runs/opencode-opus-5-5-seed7-delay3`). Its rejected command at tick 9 is in the log in red, and its final report appears in its own words at the end.

### Compare view (four runs at once)

Claude Opus 5.5, our reference controller, a controller that forgets its queued commands, and one that waits for every command to land. Same map, same seed, same clock.

### Controls

| Key | Does |
|---|---|
| space | play / pause |
| ← → | step one tick |
| M | switch between Mission and Compare |
| 1 2 3 4 | show that run in Mission view |
| F | full screen |

Adding `#auto` to the address starts it automatically and loops, for an unattended screen.

### What to say while it plays (Claude's run)

- **Tick 0:** Claude reads the rules and the map, then sends three commands at once. Watch the yellow dots leave Earth in the signal lane; the rover does not move until they arrive.
- **Tick 4–6:** the left picture moves first. The right picture, what Claude can see, follows three ticks later.
- **Tick 9:** Claude asks for a 5.25 m drive. The limit is 5 m, so the server rejects it and says why. Claude corrects it on the next call.
- **Tick 19:** Claude uses its own shell to compute a heading. That button is dashed because it is not one of our tools.
- **Throughout:** after each leg Claude advances time until telemetry catches up, then decides. That is why it succeeds here: waiting costs nothing in an 80-tick episode.
- **Then press 3:** the controller that forgets its queued commands. At tick 8 it believes the rover is at base (the ✕ on the map) while the rover is 11 m away with commands still arriving. It hits the edge of the operating zone and drains the battery.
- **Then press M:** all four runs side by side.

### Rebuild it

```sh
python3 viewer/build_mars.py     # refreshes viewer/mars/data.json and viewer/mars-demo.html
```

The runs it shows are listed at the top of `build_mars.py`. For development, serve `viewer/mars/` with any static server (`python3 -m http.server` in that folder) and open `index.html`; it loads `app.js`, `style.css` and `data.json` separately. A test fails if the committed `mars-demo.html` is stale.

three.js (r187, MIT licence, in `viewer/mars/vendor/`) is the only dependency. The terrain, rover, lander and textures are generated in code; there are no image or model files.

### Limits

- **It shows a run where the model succeeded.** Under the current rules Claude scores 1.0, so this demo shows the environment and the delay, not yet a gap. A run under harder rules drops in by changing one path in `build_mars.py`.
- **Checked in Chrome only,** on this laptop (about 54 frames a second in Mission view), and opened from disk in headless Chrome.
- **Queued commands are drawn as if the wheels did not slip.** The dashed line is where commands aim, not where they land.
- **The hologram and the delayed picture move smoothly between packets.** Real telemetry arrives once per tick.
- A replay contains the true rover states and the hidden slip values, so the page is evaluator-side material.

## The simple 2D page

[`demo.html`](demo.html) is the earlier flat version: four runs side by side on a top-down map with a chart of how wrong each operator's view is. Build it with `python3 viewer/build.py` (see `--help`). `template.html` opened alone accepts replay files by drag and drop.
