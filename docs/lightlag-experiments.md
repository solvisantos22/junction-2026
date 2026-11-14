# Dynamic Harbor experiment: rush, seed 500

14 November 2026. Sölvi / Codex integration work, using Kristján / Claude Code's
Harbor packaging and Manh / Claude Code's dynamic service and controllers.
Generator commit: [`0bc0d43`](https://github.com/solvisantos22/junction-2026/commit/0bc0d43).

**The time-pressured mission now runs through Harbor in real Docker containers.**
The reference, blind plan, whole-leg waiting and no-op all produced valid rewards,
matching direct simulator runs. **OpenCode 1.19.5 with Claude Opus 5.5 also scored
1.0 on this frozen task.** It collected all six targets on time and returned home.
This seed/profile does not show a model gap; preserve that negative result.

The original [Opus run](lightlag-harbor.md) remains important: it scored 1.0 on
the original seed-7, 80-tick task. It is not a run of the profile below.

## Settings fixed before the experiment

`rush`, seed **500**, delay **3**, horizon **50**, unchanged physics, noise level
1, bumpiness 0. The `rush` profile has no observation noise; `rush_noisy` is
supported by the generator but was not evaluated in these container runs.
Seed 500 was declared in the claim/design before looking at its scores. The
controllers were copied unchanged. These remain provisional experiment settings.

Toolchain: Harbor **0.25.0**, MCP **2.3.0**, local Harbor interpreter Python
**3.12.16**, Docker server **29.7.2**. Container images inherit the canonical
`python:3.12-slim` tag; image digests are not pinned by this generator. Each saved
run includes Harbor's lock/config, result, logs, verifier reward/details,
transcript/replay and the generated task's `experiment.json` with source/file
hashes. All four published tasks were generated from a clean `0bc0d43` checkout.

## Measured results

| Policy | Raw / maximum | Harbor reward | Direct reward, delay 0 | Evidence |
|---|---:|---:|---:|---|
| KF + MPC reference | 7 / 7 | **1.000000** | 1.000000 | [Run](lightlag-runs/rush-seed500-delay3-kf-mpc/) |
| Blind plan | 4 / 7 | 0.571429 | 0.571429 | [Run](lightlag-runs/rush-seed500-delay3-open-loop/) |
| Whole-leg waiting | 3.75 / 7 | 0.535714 | 1.000000 | [Run](lightlag-runs/rush-seed500-delay3-leg-and-wait/) |
| Do nothing | 0 / 7 | 0.000000 | 0.000000 | [Run](lightlag-runs/rush-seed500-delay3-nop/) |
| Claude Opus 5.5 / OpenCode 1.19.5 | 7 / 7 | **1.000000** | Not run | [Run](lightlag-runs/rush-seed500-delay3-opus-5-5/) |

All four Harbor runs ended alive at base at tick 50, without infrastructure
exceptions. The no-op's full horizon confirms the verifier completes the episode
after the agent stops. Direct and container scores agree to the verifier's
six-decimal rounding. The delay-0 column is a **direct public-tool run**, not an
additional Harbor run. [Machine-readable rows and direct results](lightlag-runs/rush-seed500-summary.json).

On this seed, waiting loses reward only when delay is added, while the reference
still collects the full value. That is useful evidence for the intended control
problem. Claude also handled that control problem successfully. One seed cannot
establish robustness or a frontier-model deficit.

## What the first model did

One attempt, no retries, the same generated task bytes as the reference. Harbor
reported **$0.4821436**, **236.54 seconds** for the trial, **30 public rover tool
calls**, and no infrastructure exception. Cost is the agent's reported usage,
not an independently checked invoice. The saved trajectory records model
`anthropic/claude-opus-5-5` and OpenCode **1.19.5**.

The transcript shows a small Python movement planner, slip estimates updated
from delivered telemetry, and predictions that include commands already in
transit. Claude kept commands queued instead of waiting for every leg to be
confirmed. It refreshed the map, incorporated the target discovered at tick 9,
sampled it at tick 20 before its tick-21 deadline, and returned to base at tick
21. The protected replay confirms all six samples were on time and the rover
remained alive at base through tick 50. Those are observed actions and verifier
facts, not an attribution of a particular formal control algorithm.

The blind/waiting baselines therefore understated what this model could do on
seed 500. A harder experiment must test estimation or planning beyond this
successful strategy; this result must not be presented as a failure of Claude.

## Reproduce or continue

From the repository root, with Docker running and Harbor 0.25.0 available:

```sh
python3 tools/lightlag_experiments/prepare.py /tmp/lightlag-rush-500-kf \
  --profile rush --seed 500 --delay 3 --policy kf_mpc
harbor lint /tmp/lightlag-rush-500-kf
harbor run -p /tmp/lightlag-rush-500-kf -a oracle \
  --jobs-dir /tmp/lightlag-rush-jobs --job-name reference --n-concurrent 1
harbor run -p /tmp/lightlag-rush-500-kf -a nop \
  --jobs-dir /tmp/lightlag-rush-jobs --job-name nop --n-concurrent 1
```

For the other baselines, prepare fresh directories with `--policy open_loop` and
`--policy leg_and_wait`, then use `-a oracle` on each. Only their solution entry
point differs: instructions and simulator/settings are identical. Never reuse a
previous output directory. The generator refuses to overwrite it and refuses
to generate inside the checkout.

Load `ANTHROPIC_API_KEY` through a local Git-ignored credentials file. Use its
actual path with `--env-file`; `.env` below is an example location:

```sh
harbor run -p /tmp/lightlag-rush-500-kf -a opencode \
  -m anthropic/claude-opus-5-5 --ak version=1.19.5 --env-file .env \
  --jobs-dir /tmp/lightlag-rush-jobs --job-name opus-first --n-concurrent 1
```

This pins the same OpenCode/model identifiers as Kristján's original run and
inherits the task's 1,800-second agent timeout, with one attempt and no retries.
The first run confirmed working Anthropic API access; its cost is recorded
above. No hard dollar cap is claimed. Do not treat an API/authentication/tool
failure as a reasoning failure. Use a new job name for each additional attempt.

On Sölvi's current machine, the installed Harbor executable is
`/tmp/lightlag-6974-tools/bin/harbor`. The already prepared reference task is
`/tmp/lightlag-6974-rush500-reference-v1`, and raw jobs are under
`/tmp/lightlag-6974-jobs`. Those temporary directories are conveniences, not
required shared artifacts; the generator and manifests reproduce the tasks.

## Verification and handoff

- Four generator tests pass, including nondefault seed/delay wiring, standalone
  controller imports, deterministic manifests and non-overwrite behavior.
- All 11 canonical Harbor tests pass with Python 3.12 and MCP 2.3.0. After
  integrating Manh's additional controllers, the dynamic suite passes 28 tests
  with nine optional-dependency tests skipped in the standard-library environment.
- Independent Codex code review found no blockers; its suggested nondefault
  configuration test was added before publishing the generator.
- The canonical task and all teammate implementation files were preserved.
  The agent image gets no simulator or reference code; only the oracle solution
  gets the controller modules, without their simulator-importing initializer.

**Follow-up delivered:** the [matched `rush_noisy` experiment](lightlag-noisy-experiment.md)
at seed 500, delay 3, noise level 1, bumpiness 0 and horizon 50 also produced a
1.0 Claude score and a 1.0 reference score. Both successful traces are preserved.
Seed 500 is now a development/pilot seed; use a predeclared additional seed set
and decision auditing before drawing a general gap conclusion or adding more
difficulty. Manh's [additional controllers](../lightlag_dynamic/manh_controllers/README.md)
landed in `b867839` during publication. They are outside this frozen comparison;
do not silently substitute them for the recorded reference.
