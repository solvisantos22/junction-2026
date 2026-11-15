#!/usr/bin/env python3
"""One request, one traverse pilot: ask a Claude model once for a controller and keep everything.

    python3 -m lightlag_traverse.oneshot request <out.md>
    uv run --env-file .env --with 'anthropic>=2.8' python -m lightlag_live.oneshot ask \\
        <request.md> <new-folder> --model claude-opus-5-5 --effort medium
    python3 -m lightlag_traverse.oneshot play <folder> <run-name> --label "Opus 5.5 · one shot"

`request` writes the exact text a model is sent. Everything in it is public: the task's
instruction, the published rules, the tool outputs of one example world (seed 99991, never
evaluated) and the published ground model's source. Sending it is `lightlag_live.oneshot ask`,
unchanged: once, no retries, no fallback model. `play` runs the reply's module through the
task's mission inside the sandbox and stores the result as `docs/lightlag-runs/<run-name>/`
next to the request and the reply it came from. `request` and `play` need only the standard
library (and Docker for `play`).
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from .environment import TraverseEnvironment
from .make_task import SEED

REPO = Path(__file__).resolve().parent.parent
RUNS = REPO / "docs" / "lightlag-runs"
EXAMPLE_SEED = 99991

REQUEST = """\
You are preparing the autopilot for a rover that is operated through a signal delay on Mars-like ground. Write one Python module that plays a whole mission on its own.

## The mission

- One long traverse: `max_ticks` ticks (MAX_TICKS) over a map of WIDTH m by HEIGHT m, with TARGETS science targets known at launch and more appearing on the way. There is not enough time to visit them all. Which ones to go for, in what order and by which way over the ground is the task.
- Sample science targets and have the rover back at the lander when the mission ends.
- The score is the value earned from the sampled targets, multiplied by 1.0 if the rover ends within `base_radius` of the lander, 0.5 if it ends alive anywhere else and 0 if its battery reached zero, and divided by the total value of every target of the mission, including those that only appear later. Nobody can reach every target, so a good score is well below 1.
- A target sampled at or before its `deadline_tick` earns its full `value`; after that it earns `late_value`. What counts is the tick at which the sample command executes.

## Why this has to be a program

The mission needs several hundred commands on a map you have not seen. Your program gets the rules and the map when it starts and has to work the first time: there is one mission, no reset and no practice run, and nobody can fix the program afterwards. It will be run on a world other than the example below.

## What makes it hard

- **Commands arrive late.** A command sent at tick `t` executes at tick `t + delay_ticks + 1` at the earliest. Commands execute one per tick, in the order sent.
- **Telemetry is old.** A packet describes the rover at `packet.tick` and reaches you `delay_ticks` later. Commands you have already sent may not show in it yet.
- **The ground is not flat.** `map()` gives a height grid and a terrain class for every cell. Slip grows with the slope the rover is climbing and depends on the terrain; on a cross slope the rover slides downhill; energy is spent per wheel metre and per metre climbed. The rules give the formulas under `physics`, `drive` and `ground`. Each terrain's base slip is hidden inside a published range.
- **Steep ground stops the rover.** Where the slope exceeds `max_tilt`, the rover stops at the last safe position and every command still queued is cleared. Crater walls and the scarp are that steep. They have breaches and passes.
- **Energy comes from the sun.** The battery is charged every tick by a sun that is low at the start, highest in the middle and low again at the end, through panels whose efficiency is hidden inside a published range. A battery that reaches zero ends the rover for good.
- **Sensing is noisy and the rover drifts.** Every reported position after the tick-0 briefing carries noise, reported visual odometry carries noise, and each drive goes off the commanded heading by a hidden, slowly changing bias. Sampling, the return to the lander and safety stops are decided by the rover's true position.
- **Targets have deadlines and new ones appear.** A `target_discovered` event travels in delayed telemetry; `map()` lists the target once that packet has arrived.

## What you write

One Python module, standard library only, Python 3.12, that defines

```python
def play(tools):
    ...
```

`play` is called once, at tick 0, and should return when the mission is complete. `tools` offers exactly five calls:

- `tools.rules()`: the rules, the dictionary printed below. Free.
- `tools.map()`: the map as described below. Free.
- `tools.telemetry_log()`: every packet received so far, oldest first. Free.
- `tools.uplink(commands)`: queue 1 to 5 commands, each `{"action": "drive", "heading_deg": H, "metres": M}` (0 degrees is east, 90 is north, `M` in (0, 5]), `{"action": "sample"}` or `{"action": "wait"}`. Returns one acknowledgement per command with its `execute_tick`. A request with any invalid command raises `ValueError`, is rejected whole and changes nothing.
- `tools.advance(n)`: let `n` ticks pass, `n` from 1 to 5. The only call that moves the clock. Returns `current_tick`, `episode_complete` and the packets that arrived.

The clock does not run while your program thinks. It may take up to 20 minutes of real time in all, and no more than 2 minutes between two calls. The module may `import lightlag_surface`, the published ground model whose source is at the end of this message; it will be importable. Anything printed is ignored.

## The rules: the output of `rules()`

```json
RULES_JSON
```

## The map: the output of `map()`

The grid is the same size in every world. In the example world:

```
MAP_TEXT
```

## Telemetry

`tools.telemetry_log()` at tick 0 holds one packet, the exact launch state:

```json
FIRST_PACKET
```

After `tools.uplink([{"action": "drive", "heading_deg": 90, "metres": 5}])`, which returned

```json
ACK_JSON
```

the fifth `tools.advance(1)` returned

```json
ADVANCE_JSON
```

## `lightlag_surface.py`

```python
SURFACE_SOURCE
```

## Your reply

Reply with the complete module in one fenced `python` block. It is run as it is.
"""


def build_request() -> str:
    env = TraverseEnvironment(EXAMPLE_SEED)
    rules, world = env.rules(), env.map()
    first = env.telemetry_log()[0]
    acks = env.uplink([{"action": "drive", "heading_deg": 90, "metres": 5}])
    out = None
    for _ in range(5):
        out = env.advance(1)
    rows = world["elevation_cm"]
    shown = dict(world)
    shown["elevation_cm"] = "[{} rows of {} integers; row j is y = j * cell_m, column i is x = i * cell_m; first row begins {} ...]".format(
        len(rows), len(rows[0]), rows[0][:8])
    shown["terrain"] = "[{} strings of {} codes; string j covers y from j * cell_m to (j + 1) * cell_m; first string begins {!r} ...]".format(
        len(world["terrain"]), len(world["terrain"][0]), world["terrain"][0][:24])
    shown["targets"] = world["targets"][:3] + ["... {} targets in all at launch".format(len(world["targets"]))]
    text = REQUEST
    for token, value in (
        ("MAX_TICKS", str(rules["max_ticks"])), ("WIDTH", str(int(world["width"]))), ("HEIGHT", str(int(world["height"]))),
        ("TARGETS", str(len(world["targets"]))),
        ("RULES_JSON", json.dumps(rules, indent=1)),
        ("MAP_TEXT", json.dumps(shown, indent=1)),
        ("FIRST_PACKET", json.dumps(first)),
        ("ACK_JSON", json.dumps(acks)),
        ("ADVANCE_JSON", json.dumps(out)),
        ("SURFACE_SOURCE", Path(__file__).with_name("surface.py").read_text(encoding="utf-8").rstrip()),
    ):
        text = text.replace(token, value)
    return text


def play(folder: Path, name: str, label: str, seed: int) -> int:
    from .sandbox import run

    meta = json.loads((folder / "meta.json").read_text(encoding="utf-8"))
    out = RUNS / name
    if out.exists():
        print("{} already exists; results are never overwritten".format(out), file=sys.stderr)
        return 1
    out.mkdir(parents=True)
    summary = run(folder / "policy.py", out, seed)
    (out / "sandbox.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    for item in ("request.md", "response.md", "policy.py", "meta.json"):
        if (folder / item).exists():
            shutil.copyfile(folder / item, out / item)
    names = {"claude-fable-5-2": "Claude Fable 5.2", "claude-opus-5-5": "Claude Opus 5.5",
             "claude-sonnet-5-5": "Claude Sonnet 5.5", "claude-haiku-5-5": "Claude Haiku 5.5",
             "gpt-6.1-sol": "GPT-6.1 Sol", "gpt-6.1-terra": "GPT-6.1 Terra", "gpt-6-luna": "GPT-6 Luna",
             "gemini-4-carbon": "Gemini 4 Carbon", "gemini-4-argon": "Gemini 4 Argon",
             "gemini-4-hydrogen": "Gemini 4 Hydrogen"}
    # A GPT or Gemini reply comes from tools/tier_agents/oneshot_ask.py, which records its API in meta.json.
    model_id = meta.get("model", "")
    kind = "gpt" if model_id.startswith("gpt") else "gemini" if model_id.startswith("gemini") else "claude"
    api = meta.get("api", "Messages API")
    run_meta = {"kind": kind, "label": label, "model": names.get(model_id, model_id),
                "how": "one request, one program",
                "source": "one {} request at effort {}; the reply's module run once by "
                          "lightlag_traverse.sandbox on seed {}".format(api, meta.get("effort"), seed),
                "cost_usd": meta.get("cost_usd"), "sandbox_status": summary["status"]}
    (out / "run.json").write_text(json.dumps(run_meta, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print("{}: reward {:.3f}, {} samples, alive {}, at base {}, status {}{}".format(
        name, summary["reward"], summary["samples"], summary["alive"], summary["at_base"], summary["status"],
        ", errors {}".format(summary["errors"]) if summary["errors"] else ""))
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    requesting = commands.add_parser("request", help="write the request text")
    requesting.add_argument("out", type=Path)
    playing = commands.add_parser("play", help="run a saved reply through the task's mission and store the run")
    playing.add_argument("folder", type=Path)
    playing.add_argument("name")
    playing.add_argument("--label", required=True)
    playing.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args(argv)
    if args.command == "request":
        text = build_request()
        args.out.write_text(text, encoding="utf-8")
        print("wrote {} ({} characters)".format(args.out, len(text)))
        return 0
    return play(args.folder, args.name, args.label, args.seed)


if __name__ == "__main__":
    sys.exit(main())
