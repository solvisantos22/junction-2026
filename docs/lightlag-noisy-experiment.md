# Matched noisy-profile experiment, seed 500

14 November 2026. Sölvi / Codex orchestration of the delivered team components.
This follows Claude Opus 5.5 scoring **1.0** on the [noiseless rush pilot](lightlag-experiments.md).
The earlier result remains a successful model run, not evidence of a gap.

**Claude also scored 1.0 on this noisy profile**, matching the existing reference.
All six targets were sampled on time and the rover returned home. The two
matched pilots together reported **$0.946363** of API usage. They demonstrate
working evaluation and successful model control, not a model deficit.

## Predeclared comparison

The claim was published as `7c2c98d` before looking at these outcomes. Settings:
`rush_noisy`, seed **500**, delay **3**, horizon **50**, noise level **1**,
bumpiness **0**. Same existing KF + MPC reference, blind plan and whole-leg
waiting policy; no controller tuning or scenario changes in this experiment.

The map geometry matches the noiseless mission exactly. Every source-file hash
also matches that earlier task. The only generated task-file differences are
`task.toml` (the experiment name) and `environment/docker-compose.yaml` (the
profile setting). Both prompts already explain published sensing/drift rules;
the enabled values are returned by `rules()`. This is a fresh model session,
with none of the earlier model's working files or conversation.

The profile enables the team's existing position-fix noise, visual-odometry
noise and heading drift together. This comparison does not isolate those three
effects from one another. Seed 500 is now a development/pilot seed, not unseen
confirmation data. Final project rules remain provisional.

## Container controls

Harbor 0.25.0, MCP 2.3.0, local Harbor interpreter Python 3.12.16, Docker server
29.7.2. The same canonical sidecar, evaluator-only finish and separate verifier
are used. Container base tags remain unpinned, as in the original task.

| Policy | Raw / maximum | Harbor reward | Final state | Evidence |
|---|---:|---:|---|---|
| KF + MPC | 7 / 7 | **1.000000** | Alive, at base | [Run](lightlag-runs/rush-noisy-seed500-delay3-kf-mpc/) |
| Blind plan | 4 / 7 | 0.571429 | Alive, at base | [Run](lightlag-runs/rush-noisy-seed500-delay3-open-loop/) |
| Whole-leg waiting | 1.875 / 7 | 0.267857 | Alive, away from base | [Run](lightlag-runs/rush-noisy-seed500-delay3-leg-and-wait/) |
| No-op | 0 / 7 | 0.000000 | Alive, at base | [Run](lightlag-runs/rush-noisy-seed500-delay3-nop/) |
| Claude Opus 5.5 / OpenCode 1.19.5 | 7 / 7 | **1.000000** | Alive, at base | [Run](lightlag-runs/rush-noisy-seed500-delay3-opus-5-5/) |

All four scripted controls reached tick 50 without execution exceptions and matched direct
public-tool runs to reward-file precision. The waiting policy's raw score
includes the 0.5 multiplier for finishing away from base. The controls show the
mission is solvable by the existing reference, not that a model will fail.
[Machine-readable controls](lightlag-runs/rush-noisy-seed500-summary.json).

## Model attempt

One fresh OpenCode **1.19.5** / `anthropic/claude-opus-5-5` attempt, no retries,
with the inherited 1,800-second agent timeout. Reward **1.0**, raw score **7/7**,
**29 public rover tool calls**, trial **246.31 s**, reported cost **$0.4642194**,
no execution exception. This cost comes from the saved agent usage report, not
an independently checked invoice. The complete run includes its trajectory,
protected replay, verifier outputs, lock/config and exact task manifest.

The sample order was t1 (tick 5), t2 (8), t4 (16), d1 (20), t5 (22), t3 (24),
all on time. The protected replay confirms a return at tick 31, about 0.143 m
from base, and survival there through tick 50. The final battery was 10.12.

The trajectory records direct MCP actions, with no bash tool call in this
attempt. Claude's final report describes estimating slip, allowing for heading
drift and averaging noisy readings; the command/telemetry trace is available
for Manh's independent decision auditor. This is not evidence that the model
implemented the reference's Kalman filter or MPC algorithm.

## Decision and next step

Do not increase noise again just to make this one seed fail. Both time-pressure
and default-noise pilots were solved by Claude. The next useful experiment is a
fixed, predeclared set of additional seeds under unchanged rules, with matched
references, retained successes/failures, and the decision audit where a gap
appears. Seed 500 alone does not establish that the overall environment is easy
or hard. Final mission/profile selection remains a team decision.

## Reproduce

```sh
python3 tools/lightlag_experiments/prepare.py /tmp/lightlag-noisy-500-kf \
  --profile rush_noisy --seed 500 --delay 3 --policy kf_mpc
harbor lint /tmp/lightlag-noisy-500-kf
harbor run -p /tmp/lightlag-noisy-500-kf -a oracle \
  --jobs-dir /tmp/lightlag-noisy-jobs --job-name reference --n-concurrent 1
harbor run -p /tmp/lightlag-noisy-500-kf -a opencode \
  -m anthropic/claude-opus-5-5 --ak version=1.19.5 --env-file .env \
  --jobs-dir /tmp/lightlag-noisy-jobs --job-name opus-first --n-concurrent 1 \
  --n-attempts 1 --max-retries 0
```

Use the actual local credentials-file path in place of `.env`; never commit it.
Choose fresh output/job directories. For the other controls, generate tasks with
`--policy open_loop` and `--policy leg_and_wait`, then run each through `-a oracle`.
Preserve the generated `experiment.json` alongside the sanitized run evidence.
