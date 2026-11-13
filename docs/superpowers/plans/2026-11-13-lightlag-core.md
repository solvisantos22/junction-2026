# Lightlag Core Implementation Plan

> Execute task by task in the existing isolated worktree. Use the executing-plans workflow, test-driven development, and code review before integration. The user already requested execution and small verified pushes to `main`.

**Goal:** A runnable deterministic Lightlag simulator with delayed public observations, true-state scoring and evaluator replay.

**Architecture:** Immutable configuration/world types support a stateful simulation with five public tools. Only explicit tick advances mutate physical time. The local JSON-lines runner limits dispatch to those tools and keeps evaluator artifacts separate.

**Tech Stack:** Python 3.9+, dataclasses, random, json, argparse, unittest; no dependencies.

Design: [first simulator slice](../specs/2026-11-13-lightlag-core-design.md).

## 1. Delay and movement core

Files: `lightlag/__init__.py`, `lightlag/model.py`, `lightlag/environment.py`, `tests/lightlag/test_environment.py`, `.gitignore`.

- [x] Write timeline, energy, read-isolation and invalid-input tests first. Use a flat world and this public contract:

  ```python
  from lightlag import Environment, Config
  env = Environment(seed=7, config=Config(delay_ticks=3))
  ack = env.uplink([{"action": "drive", "heading_deg": 0, "metres": 2}])
  assert ack[0]["execute_tick"] == 4
  assert env.advance(3)["packets"] == []  # tick 0 is the initial briefing
  env.advance(3)
  assert env.telemetry_log()[-1]["tick"] == 3
  assert env.advance(1)["packets"][-1]["tick"] == 4
  ```

- [x] Run `python3 -m unittest discover -s tests/lightlag -v`; confirm absent behavior fails.
- [x] Implement validated frozen configuration/world types and command decoding. Build the fixed map and seeded terrain parameters, then atomic command scheduling, tick integration, delayed packets and copy-safe reads. Keep random noise independent of read calls.
- [x] Run the same tests, inspect the diff, obtain code review, then commit and push this working core after fetching/integrating `origin/main`. Fifteen tests pass; independent review reproduced a cardinal-direction rounding issue, fixed with a four-edge regression. Existing watcher: 26 tests pass.

## 2. Mission, safety and score

Files: `lightlag/model.py`, `lightlag/environment.py`, `tests/lightlag/test_mission.py`.

- [ ] Add failing behavior tests using tiny explicit maps: sampling succeeds only near a target and never twice; final score applies base/alive/dead multipliers; a thin hazard blocks a drive and drops queued work; battery death does not leak through early public termination or acknowledgements.
- [ ] Run `python3 -m unittest discover -s tests/lightlag -v` and confirm the new failures.
- [ ] Implement segment/rectangle collision checks, sampling events and trusted `evaluate()`. Only evaluate after the horizon. Preserve the reserved command schedule when safety drops the actual queue.
- [ ] Verify the mission with a stationary target fixture:

  ```python
  from lightlag import Environment, Config, World, Target
  env = Environment(seed=0, config=Config(delay_ticks=0, max_ticks=2),
                    world=World(targets=(Target("home", 20, 20, 2),)))
  env.uplink([{"action": "sample"}])
  env.advance(2)
  assert env.evaluate()["raw_score"] == 2
  ```

- [ ] Run the full simulator suite, review and push this increment before starting the runner.

## 3. Runner, replay and handoff

Files: `lightlag/__main__.py`, `lightlag/README.md`, `lightlag/examples/return_to_base.jsonl`, `tests/lightlag/test_cli.py`, README entry, `docs/lightlag-handoff.md`, this plan and `TEAM_STATUS.md`.

- [ ] Add failing subprocess tests for JSON-lines dispatch, recoverable malformed input, rejection of private/evaluator method names, completion-only artifact export, and identical replay files from the same script/seed.
- [ ] Run `python3 -m unittest discover -s tests/lightlag -v` and confirm the new failures.
- [ ] Implement an allowlisted JSON-lines CLI, evaluator replay with initial/per-tick truth and sent commands, and a runnable sample script. Reject nonfinite JSON numbers and invalid argument types without terminating the session. Do not export a partial episode as a final result.
- [ ] Smoke test the documented command:

  ```sh
  python3 -m lightlag --seed 7 --delay 3 --ticks 20 --replay /tmp/lightlag-replay.json --result /tmp/lightlag-result.json < lightlag/examples/return_to_base.jsonl
  python3 -m unittest discover -s tests/lightlag -v
  python3 -m unittest discover -s tools/junction_watch -v
  git diff --check
  ```

- [ ] Review the final API and artifacts; document verified results, simplifications and next task scopes. Mark the claim complete for this slice, fetch/integrate, push, and confirm `HEAD` equals `origin/main`.

No model benchmark, reference quality, security isolation or final project selection is claimed by completion of this plan.
