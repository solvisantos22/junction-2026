# Choosing which uncertainty to inspect

**Result: Claude made optimal acquisition, route and timing decisions in all
twelve frozen trials.** All scores match the same-seed reference. Reported
model cost is **$0.6699462**. The added mechanic is valid, but this pilot exposes
no difficulty gap.

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
source provenance. Paid tasks were generated from clean source `0854b48` before model execution.

[Structural summary](lightlag-runs/information-allocation-v1/summary.json),
[weighted rows](lightlag-runs/information-allocation-v1/exact_rows.jsonl),
[seeded rows](lightlag-runs/information-allocation-v1/seeded_rows.jsonl) and
[all replays, gzip](lightlag-runs/information-allocation-v1/replays.jsonl.gz) are
retained. The [archive manifest](lightlag-runs/information-allocation-v1/replay-archive.json)
records compressed and uncompressed hashes. `python3 -m
lightlag_information_allocation.study --output /tmp/new-allocation-study`
reproduces the study into a new directory (with uncompressed JSON-lines replays).

## Completed model pilot

All twelve planned Claude Opus 5.5 sessions completed through OpenCode 1.19.5 and
Harbor 0.25: two fresh sessions per context, no retries, replacements, unrun cases,
infrastructure failures, invalid tool calls or observed budget truncations.
Every initial inspection choice, conditional route and earliest commitment time
is optimal under the public information. Model and reference mean realized
reward are both 0.675; exact expected mean is 0.6743. This numerical closeness in
a small sample is not a population-reliability result.

| Context | Inspection in both runs | Delivered signals | Claude rewards | Reference rewards |
|---|---|---|---|---|
| case_1 | a | soft, soft | .325, .325 | .325, .325 |
| case_2 | b | soft, soft | .325, .325 | .325, .325 |
| case_3 | a | firm, soft | .825, .725 | .825, .725 |
| case_4 | b | firm, firm | .825, .825 | .825, .825 |
| case_5 | skipped | — | .900, .900 | .900, .900 |
| case_6 | skipped | — | .900, .900 | .900, .900 |

The second case_3 run exercises the useful switch: inspect a, observe soft,
then commit to uninspected b. The observation changes a's firm probability to
0.171053; b remains 0.55. Conditional expected rewards are b 0.39875, detour
0.325 and a 0.141118. Claude chooses b immediately, completes at tick 7, and earns
0.725 because b happens to be firm. This is an optimal decision under available
information, not evidence that the agent knew b's hidden terrain.

Independent review reconstructed all 24 model/reference service transcripts and
protected replays, checked source/task hashes, grades and all twelve salted
seed commitments. The offline auditor confirms all 24. Each provider response's
reported cost sums to Harbor's recorded usage. All sessions end normally after
4–7 model responses; actual tool calls match the protected service transcripts
and use only public allocation tools. No model fetched the published reference
policy, used a shell, accessed hidden files or called the evaluator in these
observed traces. Cost is reported usage, not an independently checked invoice.

- [Complete decision/usage ledger](lightlag-runs/information-allocation-pilot-v1/summary.json)
- [Replay, hash and commitment audit](lightlag-runs/information-allocation-pilot-v1/audit-summary.json)
- [Revealed assignments](lightlag-runs/information-allocation-pilot-v1/assignments-reveal.json)
- [Public model traces and protected artifacts](lightlag-runs/information-allocation-pilot-v1/runs/)
- [Exact generated tasks](lightlag-runs/information-allocation-pilot-v1/tasks/)

Rerun the read-only checks from this checkout; output files are optional and must
be new paths:

```sh
python3 -m tools.information_allocation_experiments.audit_pilot \
  docs/lightlag-runs/information-allocation-pilot-v1
python3 -m tools.information_allocation_experiments.analyze_pilot \
  docs/lightlag-runs/information-allocation-pilot-v1
```

The [round-one snapshot](lightlag-runs/information-allocation-pilot-v1/progress-round1.json)
is retained as historical evidence. Its pending rows refer to that checkpoint;
the complete ledger above supersedes it. Raw provider working state, logs and
trajectory message fields remain private. Public actions, observations and
usage are retained with export hashes; no credentials are published.

## Limits, decision and handoff

Five of eight possible context/signal branches across the four probing contexts
were observed. Case_1-firm, case_2-firm and case_4-soft remain uncovered by actual
models. All eight sampled inspection signals happened to match the inspected
terrain; the exhaustive structural study includes incorrect signals, but this
pilot does not sample their realized reward consequences. Signal truthfulness
is hidden, so this does not by itself imply an additional policy response.

A [post-hoc check using public rules](lightlag-runs/information-allocation-pilot-v1/coverage-limitation.json)
shows every optimal inspection here also targets the route with the highest
prior expected reward. The matrix distinguishes inspection value from entropy,
but cannot distinguish optimal information-value targeting from a current-leader
heuristic supplied with the same probe/skip decision. Correct actions do not
reveal a model's internal reasoning algorithm. Inspection of a less promising
challenger being optimal remains untested. Cases and settings were not changed
after seeing outcomes.

The [exact reference outcome distribution](lightlag-runs/information-allocation-pilot-v1/reference-distribution.json)
predicts 1.224 failed trips per twelve independent sessions even under the
optimal policy. No failed trip occurred in this particular model sample.
Realized failure alone would not establish bad reasoning; acquisition,
conditional route and timing must still be assessed separately.

**Decision:** retain this as a verified diagnostic mechanic and protected harness.
Do not present it as a standalone model-breaking benchmark. No further paid
experiment or automatic difficulty expansion has been started. The useful next
design question is how information allocation interacts with the existing rover's
state estimates, route commitments and resource planning. Any follow-up should
include simple current-leader controls and cases where inspecting a challenger
is best, with inputs frozen before model testing. Existing battery, odometry
and movement observations must remain legitimate information sources.

The team still needs to choose its task. [Manh's task-contract proposal](lightlag-task-contract-proposal.md)
is a separate provisional shipping candidate; this experiment does not replace
it or alter the canonical Harbor task, continuous rover, controllers or viewer.
The implementation scope is released; all twelve assignments and successes are
retained, including the limits above.

**Spend handoff:** this pilot's $0.6699462 brings this coordinator's recorded
usage to $10.8360204, including the earlier calculated synthesis charge. The
separate Rocks $1.4873214 may or may not share the provider balance. The
historical user-reported $15.70 and old morning-brief headroom are not a live
balance; reconcile the account before funding the separate proposed paid study.
The pilot stayed below its $1.00 stop-new-launches guard and $1.50 soft target.
No paid calls remain running.
