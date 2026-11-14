# Small-policy RL: results and handoff

The first Modal pilot completed and the **declared learning screen failed**.
One trained checkpoint improved its average reward slightly, but missed the
minimum gain and returned home less often. Retain this result; do not promote
the policy or spend more on unchanged training.

This is the user's chosen small-model experiment under the
[fixed protocol](../lightlag-rl.md). It supports AfterQuery's optional learning
stretch. The 256-parameter model learns target selection; the existing Traverse
navigator, state estimator and safeguards remain fixed. This is not language-model
training and establishes no frontier-agent gap.

## Verified preparation

- **30 focused tests pass**: public-observation/action boundaries, full-horizon
  grading, numerical gradient checks, update direction, paired-map learning,
  checkpoints/timeouts/source drift and cloud-launch isolation.
- [Local smoke](local-smoke/training.json): eight actual episodes on already-used
  maps 1 and 2, two updates, completed in about four seconds. Batch mean rewards
  were .0258473 and .0183114. This is execution verification, not evidence of
  learning. The smoke weights are retained for verification only, not used for production training or selection.
- Independent review confirms correct policy-gradient/Adam ascent signs and no
  hidden simulator inputs to the actor. The full mission is graded at tick 420.
- Modal profile `solvi-junction` was configured by the user. Tokens are local,
  excluded from source snapshots and absent from the training subprocess.
- The first real job is one CPU-only run: 512 training episodes, explicit four
  core/8 GiB limits and a one-hour timeout. No GPU, model API or automatic retry.

Training worlds 71000–71127 and check worlds 72000–72039 were reserved before
use. Fresh evaluation remained unopened until the final weights froze. The completed
production run retains its source/configuration freeze and every checkpoint.

Reproduce preparation with Python 3.12, NumPy 2.3.4 and Modal client 1.6.4:

```sh
python -m unittest discover -s tests/lightlag_rl -v
python -m lightlag_rl.train --output /tmp/rl-smoke-new --updates 2 --batch-size 4 --workers 2 --train-seed 17 --max-seconds 120 --smoke
```

Use the pinned production source revision for the full experiment. The protocol
stays unchanged; completed results and decisions are appended here.


The independent evaluator is now verified on the two used smoke maps: all 12
policy/control episodes, their complete 420-tick replays and 428 retained goal
choices reconstruct. Its true do-nothing control sends no commands. This smoke
comparison does not pass the learning screen and is not used for tuning or model
selection. Production weights and all 40 fresh worlds remain separate.

## Completed Modal training

[Run ap-e9VDJ99Y3AAjaY30NcNemX](https://modal.com/apps/solvisantos22/main/ap-e9VDJ99Y3AAjaY30NcNemX)
completed all **512 missions and 16 updates** in 466.74 trainer seconds
(468.24 seconds including the function wrapper). The single four-core/8 GiB CPU
job returned successfully, with zero retries and no volume-commit errors.
[Job metadata](modal/pilot-01/modal-job.json), [metrics/checkpoints](modal/pilot-01/training/training.json)
and [stdout](modal/pilot-01/train.stdout.txt) retain the actual run.

Running CPU/memory is estimated at **$0.03285** from the recorded duration and
published $0.252576/hour resource rate. This is not an invoice and excludes
image build, startup, storage and egress. No Claude or other model API was used.

The [training audit](modal/pilot-01/training/audit.json) reconstructs all 16
updates, 512 episodes' recorded rewards and **21,078 sampled choices**, including
Adam and RNG state, against 34 source pins. There were zero retained invalid
calls. Its tolerance is 1e-9 for cross-CPU floating-point differences. This audit
checks the recorded learning calculation; it does not independently replay
training physics or reextract features. The separate fresh evaluation checks
physics and grades.

Initial policy SHA-256: `2ccca99c72e2302330f594ae03958ed1b8699dfa7fd92295675b5d59b94f431b`.
Final policy SHA-256: `3f636cac0bb774db76060004c04666eb41693f15acc766aca43a7e8942b5c33a`.
The final checkpoint was used without selection or tuning. Check maps
**72000–72039 are now consumed**. No further cloud run is queued.

## Frozen fresh comparison

[Full report](check/report.json), [pre-evaluation freeze](check/freeze.json) and
[replay audit](check/audit.json). All 40 new maps ran to tick 420. Initial and
final policies each used two matched action-sampling seeds per map; controls
ran once per map. The score is official `raw_score / max_available_value`.

| Policy | Missions | Mean score | Alive and home |
|---|---:|---:|---:|
| Initial neural scheduler | 80 | 0.016744 (1.67%) | 62/80 (77.5%) |
| Trained neural scheduler | 80 | 0.024835 (2.48%) | 58/80 (72.5%) |
| Same-navigator greedy scheduler | 40 | 0.232840 (23.28%) | 18/40 (45.0%) |
| Do nothing | 40 | 0.000000 | 40/40 (100%) |

There were **no deaths and no invalid calls** in any group. Greedy scores much
higher but returns home less often; it is not universally better on both metrics.

The paired map-average gain is **0.008091**, or **0.81 percentage points**;
95% map-bootstrap interval **[0.004038, 0.012592]** (0.40–1.26 points).
This is 25 map wins, 2 ties and 13 losses after averaging the two action draws
within each map. The declared screen required all three conditions:

- Gain at least 0.03: **fail** (0.008091).
- Positive bootstrap lower bound: **pass** (0.004038).
- At most two fewer alive/home outcomes: **fail** (four fewer).

The positive interval supports a small improvement for this checkpoint on this
check distribution. One training seed does not establish reliable learning
across training runs. The two action draws on each map are not independent maps.
No checkpoint, policy, reward or threshold was changed after opening this check.

The audit independently reconstructs **240 full physics replays and grades**,
plus **8,559 goal choices** from the retained features. Policy feature extraction
is source-pinned but not independently reexecuted. A separate read-only review
recomputed the sample counts, pairing, bootstrap and gates and confirmed source
and weight hashes. All **30 focused tests** pass as one suite.

## Diagnosis and next decision

[Reproducible observational analysis](diagnosis.json) of the existing 512 training
missions identifies a plausible action-interface problem. The scheduler switched
away **16,410 / 17,265 times (95.05%)** when its previous non-home target was still
offered; **99.43%** of these switches occurred before that target's earlier
estimated arrival time. Median replanning interval was 12 ticks, whereas mean
selected-target travel estimate was 48.99 ticks. The actor receives no explicit
previous-goal indicator and gets the terminal reward after many such decisions.

This supports testing target persistence and delayed credit assignment. It does
not prove that switching caused low scores: these are actor intentions, estimates
can be wrong, and the fixed navigator can override a selection. The analysis is
post hoc and uses saved training records only; no new missions or tuning ran.

**Recommended follow-up, not yet implemented:** on already-used training maps,
compare the existing frequent reselection with an option that pursues a selected
target until completion or a public feasibility/safety reason to stop. Keep
navigation and observations matched across initial, learned and greedy controls.
First verify that coherent pursuit collects science before increasing training
budget. Any new training experiment needs its own declared protocol and new
check maps; these 40 maps must not be presented as fresh again.

## Reproduction and team handoff

Training source/configuration was published before launch in
[modal-freeze.json](modal-freeze.json), originating at `9cee829`.
The evaluator and audits ran from detached revision **`896556f`**, which contains
the same 34 pinned training sources and the final auditors. This insulated the
experiment from teammates' concurrent changes to main. To audit existing
artifacts without training or evaluating new maps, from the results checkout:

```sh
artifact_root="$(pwd)/docs/lightlag-rl-results"
git worktree add --detach /tmp/junction-rl-audit-01 896556f
cd /tmp/junction-rl-audit-01
# Python 3.12 with numpy==2.3.4; the auditors need no Modal login.
python -m tools.lightlag_rl.audit_training --training "$artifact_root/modal/pilot-01/training"
python -m tools.lightlag_rl.check --audit "$artifact_root/check/report.json"
```

The diagnosis includes its own standard-library reproduction code and input
hashes. The full compressed training records, weights, checkpoints, fresh
replays and audits are committed. Credentials are absent from the upload and
retained artifacts. The [prize evidence entry R19](../prize-evidence.md) records
Codex's implementation and the actual Modal run without claiming an improvement
large enough to pass the protocol or a prize submission.

This bounded experiment is complete; its file scope is released. Preserve its
protocol and artifacts. No changes were made to teammates' environments,
controllers, Harbor tasks or demos, and no final project/rules choice follows.
