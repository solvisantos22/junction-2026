#!/usr/bin/env python3
"""One request, one autopilot: ask a Claude model once for a mission controller and keep everything.

    python3 -m lightlag_live.oneshot request <out.md> [--noise-level 2]
    uv run --env-file .env --with 'anthropic>=2.8' python -m lightlag_live.oneshot ask \\
        <request.md> <new-folder> --model claude-opus-5-5 --effort medium
    python3 -m lightlag_live.oneshot play <folder> <run-name> --label "Opus 5.5 · one shot"

`request` writes the exact text a model is sent. Everything in it is public: the mission's
published rules and the tool outputs of one example episode (seed 7999, never evaluated).
`ask` sends it once, with no retries and no fallback model, and saves the reply, the module
taken from its single fenced block, the usage and the cost. `play` runs that module through
the task's campaign inside the sandbox (`lightlag_live.sandbox`) and stores the result as
`docs/lightlag-runs/<run-name>/`, next to the request and the reply it came from.

The key is read from the environment by the SDK; nothing here prints or stores it.
`request` and `play` need only the standard library (and Docker for `play`).
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
RUNS = REPO / "docs" / "lightlag-runs"
EXAMPLE_SEED = 7999
PRICES = {  # USD per million tokens (input, output); thinking is billed as output
    "claude-fable-5-2": (8.00, 40.00),
    "claude-opus-5-5": (4.00, 20.00),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-haiku-5-5": (0.10, 0.50),
}
NAMES = {"claude-fable-5-2": "Claude Fable 5.2", "claude-opus-5-5": "Claude Opus 5.5",
         "claude-sonnet-5-5": "Claude Sonnet 5.5", "claude-haiku-5-5": "Claude Haiku 5.5"}

REQUEST = """\
You are preparing the autopilot for a rover that is operated through a signal delay. Write one Python module that plays a whole mission on its own.

## The mission

- The rover starts at base on a 40 m x 40 m map. Science targets are scattered around it. Sample as many as you can and have the rover back at base when the mission ends.
- A mission lasts exactly `max_ticks` ticks (50). It is scored from the rover's true state at the end:
  score = (value earned from sampled targets) x multiplier / (total value of every target generated for the mission, including targets that only appear later).
  The multiplier is 1.0 if the rover ends within `base_radius` of base, 0.5 if it ends alive anywhere else, and 0 if its battery reached zero.
- A target sampled at or before its `deadline_tick` earns its full `value`; after that it earns `late_value`. What counts is the tick at which the sample command executes.
- New targets appear during the mission. A `target_discovered` event travels in the telemetry packet of the tick it appears, so you learn of it `delay_ticks` later; from then on `map()` lists it. It cannot be sampled before its `appear_tick`.
- The battery drains `idle_cost` every tick until the mission ends, whether or not the rover moves and whether or not your program is still running. Driving costs `drive_cost` per wheel metre, times the terrain multiplier. A sample costs `sample_cost` even when it fails.

## Why this has to be a program

The mission runs in real time, one tick per second, with nobody at the controls: once it starts, your program is the only thing driving. It will be run on missions you have not seen (other maps, other hidden wheel slip, other heading bias), several in a row, and it has to work the first time. There is no practice run and no chance to fix it afterwards.

## What makes it hard

- Commands arrive late. A command sent at tick `t` executes at tick `t + delay_ticks + 1` at the earliest. Commands execute one per tick, in the order sent.
- Telemetry is old. A packet describes the rover at `packet["tick"]` and reaches you `delay_ticks` later. Commands you have already sent may not show in it yet.
- Wheel slip is unknown. A drive of `M` wheel metres moves the rover `M x (1 - slip)` over the ground. `rules()` gives only a range per terrain; each drive also has a little noise. Telemetry reports `wheel_odometry` and `visual_odometry` for each tick, so slip can be estimated.
- Sensing is noisy and the rover drifts; `rules()["sensing"]` gives the numbers. Every reported position after the tick-0 briefing carries noise, reported visual odometry carries noise, and each drive goes off the commanded heading by a hidden, slowly changing bias plus a little independent noise.
- Sampling, returning to base and safety stops are all decided by the rover's true position, not the reported one.
- A drive that would enter a hazard rectangle or leave the map stops the rover at the last safe position and cancels every command queued at that moment (their execution ticks stay reserved, so new commands queue behind them).

## Interface

Your module must define `play(tools)`. `tools` has exactly these five methods. All values are plain JSON-style Python objects.

- `tools.rules()` -> dict. The published rules. Costs no time.
- `tools.map()` -> dict. Map size, base, sand rectangles, hazard rectangles and the targets known so far. Costs no time.
- `tools.telemetry_log()` -> list of every packet received so far, oldest first. Costs no time.
- `tools.uplink(commands)` -> list of acknowledgements. `commands` is a list of 1 to 5 commands:
  `{"action": "drive", "heading_deg": H, "metres": M}` (0 degrees is east, 90 is north; `M` is wheel metres, 0 < M <= 5),
  `{"action": "sample"}` (collects the nearest unsampled target within `target_radius` of the rover's true position), or `{"action": "wait"}`.
  The first command executes at `current_tick + delay_ticks + 1`, or one tick after the last command already queued, whichever is later; the rest follow one per tick. A request with any invalid command, or one whose commands would execute after the last tick of the mission, raises `ValueError` and changes nothing. Costs no time.
- `tools.advance(ticks=1)` -> dict. Lets 1 to 5 ticks pass and returns `current_tick`, `episode_complete` and the telemetry packets that arrived in those ticks. It is the only call that moves time forward.

`play` should return once `episode_complete` is true (or earlier if there is nothing left to do; the remaining ticks then pass by themselves). If `play` raises, your control ends there: commands already accepted still execute and the rest of the mission passes with the rover as it is.

### Real outputs from one example mission

`tools.map()` at the start:

```json
<<example_map>>
```

`tools.telemetry_log()` at the start (the tick-0 briefing is always exact):

```json
<<example_log>>
```

`tools.uplink([{"action": "drive", "heading_deg": 30, "metres": 2}, {"action": "sample"}])` at tick 0:

```json
<<example_ack>>
```

`tools.advance(5)` right after that, then `tools.advance(3)`:

```json
<<example_adv_1>>
```

```json
<<example_adv_2>>
```

## The published rules

`tools.rules()`:

```json
<<rules>>
```

## Requirements

- Python 3.12, standard library only, one module, no input or output other than `tools`, no sleeping, no randomness.
- Keep your own computation between calls short: well under a second.
- Read everything you need from `rules()` and `map()` at run time; do not hard-code the example mission.

Reply with the complete module in a single ```python fenced block.
"""


def build_request(noise_level: float) -> str:
    sys.path.insert(0, str(REPO))
    from lightlag import Config
    from lightlag_dynamic.environment import DynamicEnvironment

    env = DynamicEnvironment(seed=EXAMPLE_SEED, config=Config(delay_ticks=3, max_ticks=50),
                             profile="rush_noisy", noise_level=noise_level)
    values = {"rules": json.dumps(env.rules(), indent=1), "example_map": json.dumps(env.map()),
              "example_log": json.dumps(env.telemetry_log())}
    values["example_ack"] = json.dumps(env.uplink([{"action": "drive", "heading_deg": 30, "metres": 2},
                                                   {"action": "sample"}]))
    values["example_adv_1"] = json.dumps(env.advance(5))
    values["example_adv_2"] = json.dumps(env.advance(3))
    text = REQUEST
    for key, value in values.items():
        token = "<<" + key + ">>"
        if text.count(token) != 1:
            raise SystemExit("placeholder {} appears {} times".format(key, text.count(token)))
        text = text.replace(token, value)
    return text


def ask(request: Path, out: Path, model: str, effort: str, max_tokens: int) -> int:
    import anthropic

    out.mkdir(parents=True, exist_ok=False)
    prompt = request.read_text(encoding="utf-8")
    (out / "request.md").write_text(prompt, encoding="utf-8")
    meta = {"model": model, "effort": effort, "max_tokens": max_tokens, "thinking": "adaptive",
            "retries": 0, "fallback_model": None}
    client = anthropic.Anthropic(max_retries=0)
    started = time.time()
    try:
        with client.messages.stream(model=model, max_tokens=max_tokens, thinking={"type": "adaptive"},
                                    output_config={"effort": effort},
                                    messages=[{"role": "user", "content": prompt}]) as stream:
            message = stream.get_final_message()
    except anthropic.NotFoundError as error:
        meta["error"] = "not found: {}".format(error.message)
    except anthropic.RateLimitError as error:
        meta["error"] = "rate limited: {}".format(error.message)
    except anthropic.APIStatusError as error:
        meta["error"] = "api status {}: {}".format(error.status_code, error.message)
    except anthropic.APIConnectionError as error:
        meta["error"] = "connection: {}".format(error)
    meta["seconds"] = round(time.time() - started, 1)
    if "error" in meta:
        (out / "meta.json").write_text(json.dumps(meta, indent=1) + "\n", encoding="utf-8")
        print("{} failed: {}".format(out.name, meta["error"]))
        return 1
    text = "".join(block.text for block in message.content if block.type == "text")
    (out / "response.md").write_text(text, encoding="utf-8")  # keep the paid reply before anything can fail
    blocks = re.findall(r"```python\n(.*?)```", text, flags=re.S)
    code = max(blocks, key=len) if blocks else ""
    (out / "policy.py").write_text(code, encoding="utf-8")
    price_in, price_out = PRICES[model]
    usage = message.usage
    meta.update({"served_model": message.model, "stop_reason": message.stop_reason,
                 "message_id": getattr(message, "id", None),
                 "input_tokens": usage.input_tokens, "output_tokens": usage.output_tokens,
                 "cost_usd": round((usage.input_tokens * price_in + usage.output_tokens * price_out) / 1e6, 5),
                 "code_lines": code.count("\n"), "has_play": "def play(" in code})
    (out / "meta.json").write_text(json.dumps(meta, indent=1) + "\n", encoding="utf-8")
    print("{}: stop={} out={} tokens cost=${:.4f} {}s code_lines={} has_play={}".format(
        out.name, message.stop_reason, usage.output_tokens, meta["cost_usd"], meta["seconds"],
        meta["code_lines"], meta["has_play"]))
    return 0


def play(folder: Path, name: str, label: str) -> int:
    from . import sandbox
    from .make_task import MISSIONS, SETTINGS

    if not re.fullmatch(r"live-[a-z0-9][a-z0-9\-]*", name):
        raise SystemExit("run names look like live-oneshot-opus-1")
    destination = RUNS / name
    if destination.exists():
        raise SystemExit("{} already exists; results are never overwritten".format(destination))
    meta = json.loads((folder / "meta.json").read_text(encoding="utf-8"))
    policy = folder / "policy.py"
    if not meta.get("has_play") or not policy.stat().st_size:
        raise SystemExit("{} holds no autopilot (stop reason: {})".format(folder, meta.get("stop_reason")))
    destination.mkdir(parents=True)
    summary = sandbox.run_policy(policy, destination, MISSIONS, SETTINGS["noise_level"])
    result = summary.pop("result")
    summary.update(reward=result["reward"], missions=[round(m["reward"], 6) for m in result["missions"]],
                   rovers_lost=sum(not m["alive"] for m in result["missions"]),
                   settings={"missions": "the task's (lightlag_live.make_task.MISSIONS)",
                             "noise_level": SETTINGS["noise_level"], "clock": "simulated"})
    (destination / "sandbox.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    for item in ("request.md", "response.md", "policy.py", "meta.json"):
        shutil.copyfile(folder / item, destination / item)
    run = {"kind": "claude", "label": label, "model": NAMES.get(meta["model"], meta["model"]),
           "how": "one request, one program",
           "source": "one Messages API request at effort {}; the reply's module run once per mission by "
                     "lightlag_live.sandbox on a simulated clock".format(meta["effort"]),
           "cost_usd": meta["cost_usd"]}
    (destination / "run.json").write_text(json.dumps(run, indent=1) + "\n", encoding="utf-8")
    print("{}: reward {:.3f} missions {} lost {} status {}".format(
        name, summary["reward"], " ".join("{:.2f}".format(m) for m in summary["missions"]),
        summary["rovers_lost"], summary["status"]))
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    request = commands.add_parser("request", help="write the request text")
    request.add_argument("out", type=Path)
    request.add_argument("--noise-level", type=float, default=2.0)
    asking = commands.add_parser("ask", help="send the request once")
    asking.add_argument("request", type=Path)
    asking.add_argument("out", type=Path)
    asking.add_argument("--model", required=True, choices=sorted(PRICES))
    asking.add_argument("--effort", default="medium")
    asking.add_argument("--max-tokens", type=int, default=64000)
    playing = commands.add_parser("play", help="run a saved reply through the task's campaign")
    playing.add_argument("folder", type=Path)
    playing.add_argument("name")
    playing.add_argument("--label", required=True)
    args = parser.parse_args(argv)
    if args.command == "request":
        text = build_request(args.noise_level)
        args.out.write_text(text, encoding="utf-8")
        print("wrote {} ({} characters)".format(args.out, len(text)))
        return 0
    if args.command == "ask":
        return ask(args.request, args.out, args.model, args.effort, args.max_tokens)
    return play(args.folder, args.name, args.label)


if __name__ == "__main__":
    sys.exit(main())
