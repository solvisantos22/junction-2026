# Dynamic Harbor experiment: rush, seed 500

14 November 2026. Sölvi / Codex integration work, using Kristján / Claude Code's
Harbor packaging and Manh / Claude Code's dynamic service and controllers.
Generator commit: [`0bc0d43`](https://github.com/solvisantos22/junction-2026/commit/0bc0d43).

**The time-pressured mission now runs through Harbor in real Docker containers.**
The reference, blind plan, whole-leg waiting and no-op all produced valid rewards,
matching direct simulator runs. **No model has played this experimental task in
this session yet:** the local `.env` placeholder is awaiting the user's Claude
API key. This is a scripted comparison and integration check, not a model gap.

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

All four Harbor runs ended alive at base at tick 50, without infrastructure
exceptions. The no-op's full horizon confirms the verifier completes the episode
after the agent stops. Direct and container scores agree to the verifier's
six-decimal rounding. The delay-0 column is a **direct public-tool run**, not an
additional Harbor run. [Machine-readable rows and direct results](lightlag-runs/rush-seed500-summary.json).

On this seed, waiting loses reward only when delay is added, while the reference
still collects the full value. That is useful evidence for the intended control
problem. One seed cannot establish robustness or a frontier-model deficit.

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

After saving `ANTHROPIC_API_KEY` in the Git-ignored `.env`, the next command is:

```sh
harbor run -p /tmp/lightlag-rush-500-kf -a opencode \
  -m anthropic/claude-opus-5-5 --ak version=1.19.5 --env-file .env \
  --jobs-dir /tmp/lightlag-rush-jobs --job-name opus-first --n-concurrent 1
```

This pins the same OpenCode/model identifiers as Kristján's original run and
inherits the task's 1,800-second agent timeout, with one attempt and no retries.
API access and cost for this new run are unverified; no hard dollar cap is
claimed. Do not treat an API/authentication/tool failure as a reasoning failure.

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

**Next:** run the model on this frozen task, save its actual cost/trajectory and
score, and compare decisions with the waiting/blind baselines. If it exposes a
gap, use a delay-0 model control and predeclared additional seeds before drawing
a benchmark conclusion. If it ties the reference, preserve that result and
consider a separate `rush_noisy` experiment. Manh's [additional controllers](../lightlag_dynamic/manh_controllers/README.md)
landed in `b867839` during publication. They are outside this frozen comparison;
do not silently substitute them for the recorded reference.
