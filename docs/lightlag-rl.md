# Small-policy RL on Traverse: fixed first experiment

Sölvi chose a small rover-control model after confirming that the teammate had
not begun training. This is a **learned mission scheduler with a fixed
navigator**, on the existing Traverse environment. It is a provisional training
experiment, not a new environment or the team's final task choice.

## Challenge fit

The [saved original AfterQuery brief](../afterquery-brainstorm.md) explicitly
offers training a smaller model on environment experience as an optional stretch
and a tiebreaker. [Ved's later clarification](afterquery-judging-clarifications-2026-11-14.md)
asks for comparison against its baseline; it does not make training compulsory.
The brief does not specify a language model for the stretch. Our interpretation
is that a small learned controller demonstrates trainability; it does not
replace the main frontier-agent/reference comparison or establish a model gap.
The authenticated challenge page could not be reopened in this session.

## What learns, and what is fixed

The policy is a shared 14-input, 16-tanh-unit neural scorer: **256 learned
parameters**. For each available science target and the home option it predicts
a score; a softmax samples the next goal. The same network scores all candidates.
No target-ID embeddings or map memorization are supplied.

Only `Pilot._plan` is replaced in a new subclass. The existing public-data
position filter, terrain routing, pending-command prediction, driving, sampling,
energy floor and return-time safeguards remain fixed. Choices occur at the
pilot's normal replanning points. Choosing home does not end grading or stop the
mission clock. Every episode runs the full **420 ticks** with the existing reward.

Features are derived solely from the public map/rules and the pilot's beliefs:
home flag, remaining time, estimated battery, position uncertainty, outbound and
return time/energy estimates, full and arrival-adjusted target value, deadline
slack, relative position and open-target count. Candidates exclude sampled,
pending, unreachable or time-infeasible targets using public estimates; home is
always offered. No true position, slip parameters, future discoveries, seed or
evaluator state enters the chooser. The evaluator's terminal scalar reward is
the learning signal, as expected in RL.

Random, initial-network, learned-network and value-per-travel-time controls all
use this same navigator and feature/action interface. Therefore improvements
measure target-selection learning on top of the navigator, not learned steering,
new state estimation or better hand-written safety rules.

## Training declared before any training-range mission

- Training worlds: **71000–71127**, reserved here. No test map is used to train,
  select hyperparameters or choose a checkpoint.
- One training seed: **17**. NumPy 2.3.4, Python 3.12; CPU-only.
- **16 updates × 32 episodes = 512 missions.** Each batch samples 16 training
  maps without replacement, with two independent action-sampling draws per map.
- REINFORCE policy gradients use terminal official reward only, normalized as
  `raw_score / max_available_value`. No shaping bonus or imitation pretraining.
  Within-map paired reward centering reduces map-difficulty variance; batch
  advantage scale has a .01 floor. Entropy coefficient .01, Adam ascent learning
  rate .02, global gradient norm cap 5. Sum decision gradients per trajectory
  and average over episodes.
- Save initial weights, every batch's decisions/features/outcomes, every update's
  checkpoint including optimizer/RNG state, final weights, source hashes and
  metrics. Use the final update; no best-checkpoint selection.
- Internal wall-clock bound 3,000 seconds; an interrupted run is incomplete and
  retains its checkpoints. No automatic restarts or replacement training runs.
- Local preflight uses already-consumed worlds **1 and 2** only, two updates of
  four episodes. Its weights are discarded; no tuning against fresh maps.

## Modal execution and credit scope

Use Sölvi's explicitly configured `solvi-junction` profile, independent of
Kristján's separately claimed Traverse rollout farm. Launch one bounded CPU job:
four cores and 8 GiB with explicit reservation **and limits**, one container,
zero retries, 3,600-second function timeout and 120-second startup timeout.
Volume storage retains checkpoints/results. Validate a source/config freeze
before creating the cloud app, and revalidate the uploaded source remotely.

At the [checked published rates](https://modal.com/pricing), four physical cores
plus 8 GiB cost approximately **$0.252576 per running hour**, excluding builds,
startup, storage and egress. The one-hour job bound is a compute restriction,
not an account-wide invoice cap. Do not change shared workspace budgets, add
payment methods or launch extra jobs. This experiment makes no Claude API calls.
Modal's [resource documentation](https://modal.com/docs/guide/resources) explains
why a CPU reservation alone is insufficient to constrain actual usage.

## Fresh comparison after final weights freeze

Reserve **72000–72039** now, before generating any of these worlds. Only a fully
completed 16-update run qualifies. Freeze its final and initial weights and the
environment/navigator source before opening the check.

Evaluate initial and final policies on every map with two fixed action-sampling
seeds per map, using the same sampling procedure for both. Also evaluate the
same-scaffold greedy controller and do-nothing baseline once per map: **240
episodes total**. Record reward, alive/home, invalid calls, samples and complete
replays. Scalar rewards alone are insufficient: verify replay and grade integrity.
Do not change a policy after seeing check outcomes.

The first-pilot learning screen requires mean paired final-minus-initial reward
at least **.03**, a positive lower bound of a paired map-bootstrap 95% interval
(10,000 draws, seed 17), and final alive/home count no more than two below the
initial count across 80 stochastic episodes. Treat the 40 maps as the sampling
units; two action draws are not 80 independent maps. Greedy is a contextual
comparison, not a threshold selected after results. One training seed supports
only a claim about this particular trained checkpoint; no general training
reliability or frontier-model superiority claim follows.

If the screen fails or the job is incomplete, retain that result. A different
training budget, reward or policy needs a separately recorded follow-up and new
check maps. No automatic environment expansion or canonical Harbor promotion.

This protocol remains unchanged after training starts. Results, decisions and
handoff belong in `docs/lightlag-rl-results/README.md`.
