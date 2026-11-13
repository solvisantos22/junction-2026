# Lightlag Reference Implementation Plan

> Execute with subagent-driven-development: one implementation task at a time, specification review followed by code-quality review, and a verified push before the next increment. The user authorized execution and frequent pushes to main.

**Goal:** An honest reference and reproducible six-policy comparison over shared seeds and delays.

**Architecture:** Controllers receive five public callbacks. The evaluator alone owns episode construction, horizon completion, grading and replay. Controllers model only documented physics and update estimates from received observations.

**Tech stack:** Existing Python 3.9+ standard library and unittest; no dependency installation, remote model calls or simulator changes.

**Design:** [Reference and evaluation slice](../specs/2026-11-14-lightlag-reference-design.md).

## Task 1 — Public tools and episode runner

Files: `lightlag/controllers/__init__.py`, `lightlag/controllers/api.py`, `lightlag/controllers/baselines.py`, `lightlag/evaluation.py`, `tests/lightlag/test_evaluation.py`.

- [ ] Write failing tests for public-only policy access, fresh isolated episodes, early return still consuming the full horizon, visible policy failures, transcript copy isolation and deterministic output.
- [ ] Implement the five-callback `PublicTools` object, `do_nothing`, and evaluator-owned `run_episode`. The intended usage is:

  ```python
  from lightlag import Config
  from lightlag.controllers.baselines import do_nothing
  from lightlag.evaluation import run_episode
  run = run_episode(do_nothing, seed=7, config=Config(delay_ticks=3),
                    policy_name="do_nothing")
  assert run["result"]["tick"] == 80
  assert run["result"]["raw_score"] == 0
  assert len(run["replay"]["states"]) == 81
  ```

- [ ] Confirm red then green with `python3 -m unittest discover -s tests/lightlag -v`. Self-review, then independent spec and quality reviews. Root agent commits/pushes after fetching/integrating teammates' work; implementation agents do not change Git state.

## Task 2 — Reference and diagnostic controllers

Files: `lightlag/controllers/geometry.py` (public-map geometry/path routing), `lightlag/controllers/predictor.py` (slip estimates and queued-state prediction), `lightlag/controllers/reference.py` (mission policy), existing `baselines.py`/`__init__.py`, `tests/lightlag/test_controllers.py`.

- [ ] Add failing tests using small public observations/maps for slip estimation, pending-command replay and safety-stop cancellation. Add integration cases for target acquisition/return at delays 0 and 3, no targets, low battery, short horizons and a visible obstacle. Verify imports/private access with a narrow API test or source audit.
- [ ] Implement the reference described in the design. Use rules/map inputs for geometry, timing, slip bounds and costs. Weighted observed slip, latest-packet anchoring, acknowledged command replay, safe route waypoints and full-horizon return budgeting are the required behaviors. Never infer seed from noise or inspect true state.
- [ ] Add `move_and_wait`, `nominal_open_loop`, `stale_telemetry`, and `stop_early` with behavior matching the design table. Export a policy registry with these and `reference`/`do_nothing`. A policy is a callable taking `PublicTools`; stop-early returns after the first quarter horizon while the evaluator handles the rest.
- [ ] Run representative checks with the public runner:

  ```python
  from lightlag import Config
  from lightlag.controllers import POLICIES
  from lightlag.evaluation import run_episode
  for delay in (0, 3):
      run = run_episode(POLICIES["reference"], seed=7,
                        config=Config(delay_ticks=delay), policy_name="reference")
      assert run["result"]["raw_score"] > 0
      assert run["result"]["at_base"] and run["result"]["alive"]
  ```

- [ ] Execute all simulator/controller tests, spec review and quality review, then publish the working policies before batch/report work. Poor seed scores are findings to investigate, not a reason to modify physics or hide runs.

## Task 3 — Batch comparison, artifacts and evidence

Files: `lightlag/evaluation.py`, `tests/lightlag/test_evaluation.py`, `lightlag/README.md`, `docs/lightlag-reference-results.md`, `docs/lightlag-handoff.md`, README entry, this plan and `TEAM_STATUS.md`.

- [ ] Write failing tests for matrix coverage/order, independent seeds, aggregation, positive/zero/missing reference normalization, repeatable JSON/CSV output, no-overwrite artifact exports and invalid CLI selections. Test a small full CLI matrix through subprocesses.
- [ ] Implement `run_comparison` and a CLI accepting `--seeds` (default 0–9), `--delays` (default 0 3), `--ticks` (default 80), `--policies` (default all six), and `--output-dir` (optional new directory). Preserve raw per-run data; reference ratios are null if unavailable or denominator zero. Write summary, CSV and unchanged evaluator replay schema for viewer use. Fail visibly on policy errors.
- [ ] Run the full tests, obtain spec/quality review, and verify this concrete invocation with a fresh directory:

  ```sh
  python3 -m lightlag.evaluation --seeds 0 1 2 3 4 5 6 7 8 9 --delays 0 3 --output-dir /tmp/lightlag-reference-development
  ```

- [ ] Freeze the controller, then run seeds 100–109 separately. Inspect scores, failures, return rates and replay traces. Record all results with configuration, exact commands and limitations; never claim a real-agent gap from scripted policies.
- [ ] Complete the handoff with controller callable and artifact contracts for teammates. Update/release the claim, run `git diff --check`, fetch/integrate, push and confirm this worktree matches `origin/main`.
