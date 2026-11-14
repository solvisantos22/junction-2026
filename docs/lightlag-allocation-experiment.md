# Choosing which uncertainty to inspect

Sölvi approved this next bounded experiment after Claude made the optimal
information and route choice in all four first-pilot cases. This adds a choice
between two information sources while keeping a single inspection budget.
The continuous rover and canonical task are unchanged; final project rules
remain provisional.

Routes a and b have independent hidden firm/soft terrain. One imperfect soil
inspection can target either route, or be skipped. The agent then commits to a,
b, or a known detour. Both risky routes cost four energy on firm ground and
twelve on soft; they take two ticks. The detour costs eight, takes six ticks,
and reaches a six-point target. Initial energy is ten; inspection costs one,
with accuracy 0.9. Command delay, delayed telemetry and irreversible commitment
are preserved. Reward is realized target value minus 0.25 per completion tick,
divided by ten. A trip includes return home; failure scores zero.

All priors, independence, values, costs and timing are public. No hidden rule,
wall-clock pressure or restriction on model thinking is added. Model scripting
is allowed. The scarce inspection is an environment resource with opportunity
cost, rather than an arbitrary API-call allowance.

## Cases fixed before model outcomes

The development cases are deliberately constructed, with mirrored route labels:

| Context | P(a firm) | P(b firm) | Value a | Value b | Exact best acquisition |
|---|---:|---:|---:|---:|---|
| case_1 | .50 | .20 | 10 | 10 | Inspect a |
| case_2 | .20 | .50 | 10 | 10 | Inspect b |
| case_3 | .65 | .55 | 10 | 9 | Inspect a |
| case_4 | .55 | .65 | 9 | 10 | Inspect b |
| case_5 | .95 | .60 | 10 | 10 | Skip |
| case_6 | .60 | .95 | 10 | 10 | Skip |

In cases 3/4 the most uncertain route is the wrong inspection target. Both
unknowns matter: an unfavorable observation can make the other, uninspected
route best. In cases 5/6 neither possible signal from either sensor changes the
best route; information has no decision value and inspection only costs reward.

An independent rational-arithmetic calculation predicts selective mean reward
0.6743 versus no inspection 0.63, always inspect a or b 0.63245 each, always
inspect the most uncertain route 0.6410166667, and always choose the less useful
inspection 0.61435. A control following the selective acquisition choice and
timing but ignoring its signal scores 0.60125. These are exact expectations,
not model scores or a representative distribution. Forced-inspection controls
also pay for unnecessary inspection in cases 5/6. Matching the selective
probe/skip choice gives 0.6647666667 for the most-uncertain target and 0.6381 for
the less-useful target. The clean target-selection gap in each of cases 3/4 is
0.0286. Only cases 5/6 contain truly irrelevant inspections.

## Evaluation frozen before testing

First enumerate every combination of two terrains and two sensor signals (16
weighted branches per context and policy), retain separate seeded smoke runs,
and verify the reference using only public tools. The gate requires acquisition
choices a/b/none, agreement of exact expectation and realized branch weighting,
and a selective aggregate above skipping and either fixed inspection target.
The blind control matches acquisition, energy and timing to isolate signal use.

Only after that structural gate and protected Harbor preflight pass: two fresh
Claude sessions per context, twelve planned attempts, no retries or replacements.
Generate independent hidden seeds and publish salted commitments before the
first model call. Use the same Claude/OpenCode settings as the first pilot,
serial launches, a soft $1.50 spending target and stop new calls at $1.00 reported
pilot usage or unknown usage. There is no hard provider dollar cap. Retain all
failures, incomplete and unrun rows. Do not select favorable signal outcomes or
quietly change the cases after observing model performance.

Compare initial acquisition, posterior route choice and timing with the exact
public-information reference separately from realized reward on the same seed.
Two sessions per context remain diagnostic; disclose uncovered signal branches.
If Claude succeeds, retain that finding. Any further expansion requires a new
decision based on the evidence. No difficulty gap is claimed in advance.

The [twelve-trial protocol and seed commitments](lightlag-runs/information-allocation-pilot-v1/protocol.json) are published before model execution.

## Structural result

The gate passes. All 864 probability-weighted branches match the exact
reference; all 1,080 separate seeded smoke episodes are retained. Root
reconstructed all 1,944 complete replays and checked 13 source hashes.
Independent review separately simulated all 21 relevant direct/conditional
strategies over all 16 joint outcomes in each context (2,016 episodes), confirming
the acquisition optima. Extra waiting adds no information and cannot improve
reward here. Both-soft terrain, wrong signals and zero-reward failures remain
in the evidence.

All 38 environment/reference/service tests and three packaging tests pass.
The protected Harbor reference preflight scores 0.825 on case_3, seed0; matched
local policy behavior and separate grading agree. The no-op scores zero. A live
agent-container check confirms simulator source, evaluator result/token and
oracle policy are absent, and unauthenticated evaluator finish returns 404.
All four free preflight jobs (reference and three no-ops, including isolation
checks) are retained separately; they are not model attempts or replacements.
The smoke task predates the clean code freeze and truthfully records dirty
source provenance. Paid tasks will be generated from the clean committed code.

[Structural summary](lightlag-runs/information-allocation-v1/summary.json),
[weighted rows](lightlag-runs/information-allocation-v1/exact_rows.jsonl),
[seeded rows](lightlag-runs/information-allocation-v1/seeded_rows.jsonl) and
[all replays, gzip](lightlag-runs/information-allocation-v1/replays.jsonl.gz) are
retained. The [archive manifest](lightlag-runs/information-allocation-v1/replay-archive.json)
records compressed and uncompressed hashes. `python3 -m
lightlag_information_allocation.study --output /tmp/new-allocation-study`
reproduces the study into a new directory (with uncompressed JSON-lines replays).

## Model pilot in progress

Round one is independently audited: all six acquisitions, posterior route
choices and commitment timings are optimal and every reward equals the protected
reference. Scores are 0.325, 0.325, 0.825, 0.825, 0.9 and 0.9. Both mirrored
value-versus-uncertainty cases are solved and both irrelevant-inspection cases
are skipped. Round-one reported cost is $0.3669134. The six predeclared fresh
second repetitions are still in progress; no difficulty gap is established.

The [round-one ledger](lightlag-runs/information-allocation-pilot-v1/progress-round1.json)
retains the other six assignments as not yet exported. Observed signal coverage
is soft in cases1/2 and firm in cases3/4; the reverse branches remain untested by
models at this checkpoint.

The [exact reference outcome distribution](lightlag-runs/information-allocation-pilot-v1/reference-distribution.json)
predicts 1.224 failed trips across twelve independent sessions even under the
optimal policy. Realized failure counts alone therefore cannot establish bad
reasoning; acquisition, conditional route and timing are audited separately.

**Spend coordination:** this round's $0.3669134 brings this coordinator's recorded
usage to $10.5329876, including the earlier calculated synthesis charge. The
separate Rocks $1.4873214 may or may not share the same provider balance. The
historical user-reported $15.70 and old morning-brief headroom are not a live
balance; reconcile the account before funding the separate nine-attempt task
contract proposal. The current twelve-trial pilot keeps its frozen serial
$1.00 stop-new-launches guard and $1.50 soft target.

## Coverage limitation found during the pilot

A [post-hoc check using only the public rules](lightlag-runs/information-allocation-pilot-v1/coverage-limitation.json)
shows that every optimal inspection in this matrix targets the route with the
highest prior expected reward. The matrix distinguishes inspection value from
entropy, but it cannot distinguish optimal information-value targeting from a
current-leader heuristic given the same probe/skip decision. Correct actions do
not reveal the model's internal reasoning algorithm. A case where inspecting a
less promising challenger is best remains untested. This finding does not change
the frozen cases, reference, model settings or paid-run count.

At the eight-session checkpoint, both second repetitions of cases1/2 again
receive soft signals and correctly choose the detour. Their firm-signal branch
remains uncovered by actual models. All eight observed decisions and timings
match the reference; the remaining repeats continue under the original protocol.
