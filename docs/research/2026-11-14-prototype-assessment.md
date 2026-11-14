# Assessment of the two teammate prototypes

14 November 2026. Sölvi asked to assess the existing prototypes, then discuss the
direction again. This is a read-only assessment of their implementations, with
free local reproductions and one fixed diagnostic. No model/API call, new
environment, fresh check range or final project selection was made.

The initial audit used snapshot `e95f075`. During integration, `81cc154` added a
four-rule-change variant and `c7ebf13` published three teammate-funded Opus runs.
The update below incorporates those new artifacts; their calls were not made
by this assessment. The original audit results are retained as measured.

## Recommendation for the discussion

**Shelve the current sample-chain candidate. Keep ground change as an unproven
adaptation hypothesis, not a demonstrated agent challenge. Neither current
result justifies claiming a frontier-model gap.** The sample-chain owner already
reached the same rejection; our independent reproduction supports it.

| Candidate | What is established | What remains unestablished |
|---|---|---|
| Sample chain | A working exact reference, independently replayed plans and real scheduling constraints | Difficulty for a coding agent: modest generic search already nearly saturates this version |
| Ground change | A disclosed physical change reduces mean scores for all five tested controllers on the retained seeds; the later three-run model pilot is mixed | An effective change-aware reference, a need to choose diagnostic information, or a convincing current-model gap |

The reference/verifier machinery is worth keeping. A lower score after making
the physics worse is not enough to choose a new challenge. Before another build,
the discussion should decide whether our target is adapting a control model,
diagnosing competing causes, or learning a reusable rule across encounters.
Those are different abilities, and neither prototype currently tests all three.

## Sample chain: the negative result reproduces

Assessed the version and retained check at `c9e8374`; its protocol was published
earlier in `465d91e`. Each size has 24 check cases, with no filtered cases.

| Check result | 8 jobs | 12 jobs |
|---|---:|---:|
| Exact reference proves optimum | 24/24 | 24/24 |
| Best-of-four greedy portfolio, mean fraction of optimum | 95.7401% | 90.4141% |
| Beam search with width 64, mean fraction of optimum | 99.3535% | 97.2898% |
| Beam search reaches the exact optimum | 20/24 | 10/24 |

Both sizes fail the owner's declared difficulty gate: portfolio at most 90%,
beam at most 95%, with all references certified. The repeated numeric seed at
two sizes is correlated; these are descriptive results, not independent trials.

The independent audit regenerated all **72 development/check missions**, matched
every retained implementation hash, replayed all **504 policy records**, and
reran all cases. Scores, plans, certification flags, reference node counts and
beam expansion counts reproduce exactly; elapsed times differ. Portfolio rows
reuse a greedy plan. Ten existing tests pass on Python 3.12.16, including a
separate tiny exhaustive oracle and resource-mask/replay checks.

The exact search enumerates each complete chain or skips its job. Its bound
ignores conflicts among remaining jobs, so it is optimistic; exhausting the
search supports its optimality claim. Capped searches remain uncertified. This
is good evidence for the bounded implementation, not a formal proof system.
[Solver](../../tools/certified_challenge_probe/search.py),
[independent verifier](../../tools/certified_challenge_probe/model.py).

The beam control shares the chain compiler and resource representation with the
reference, so it is more than a naive greedy rule. It nevertheless uses only
public inputs and is a credible coding shortcut. Its success is **not evidence
that an evaluated LLM generated that solver**; no model has played this probe.
It is sufficient reason to obey our screening gate instead of spending on a
full replacement environment.

Also, this implementation accepts a complete schedule with all opportunities
known at the start. It has no online partial commitments, new observations,
repair operations or recurring encounters. It tests static coupled scheduling,
not yet the long-horizon learning idea that motivated the discussion.

One reproducibility issue: the README's unspecified `python3` is insufficient
on this machine. Python 3.9.6 produces five test errors because the solver uses
`int.bit_count`; Python 3.12.16 passes. Document Python 3.10+ or a specific tested
interpreter before sharing those commands. This is a runtime requirement, not
task difficulty. Candidate files were not changed.

## Ground change: a real effect, an unresolved comparator

Assessed `lightlag_shift` as introduced in `8fde668`, on its already-used seeds
3100–3139, `rush_noisy`, delay 3, horizon 50. Reproduced all **400 episodes**:
five existing policies, unchanged and shifted physics, forty seeds per cell.
The six existing environment/service tests pass.

| Existing controller | Unchanged mean score | Shifted mean score | Shifted alive/home |
|---|---:|---:|---:|
| Frozen `kf_mpc` | .678298 | .575818 | 40/37 of 40 |
| Manh 36 | .699514 | .529824 | 40/28 of 40 |
| Manh 27 | .660227 | .515544 | 40/31 of 40 |
| Fixed plan | .518424 | .451688 | 40/26 of 40 |
| Leg and wait | .388400 | .302013 | 38/27 of 40 |

These means normalize each raw score by the sum of available target values,
**not a proven achievable optimum**. They are not comparable to the sample-chain
optimality ratios and do not express model failure rates. Final outcomes and
replay hashes are retained in the assessment evidence.

Slower travel can cost more battery and miss deadlines even with perfect
knowledge of the change. The before/after score drop combines that physical
cost with detection and recovery; it does not isolate an adaptation failure.
An announced-change diagnostic, or a separately labelled privileged bound, would
help distinguish those effects. Neither was run here.

Under the tested default horizon, the new environment applies its declared
change once and publishes its window and post-change bounds. The old frozen
filter, however, reads only the original
`slip_ranges`: its `slip()` accessor still limits bedrock to .05 and sand to .45.
The new physical values lie in .10–.25 and .45–.70. Setting its estimated means
to .20/.60 therefore still yields effective predictions of .05/.45. The fading
controllers adjust position covariance but do not remove this limit. None of
the compared controllers consumes `ground_change`.
[Filter](../../lightlag_dynamic/kf_mpc.py),
[fading implementation](../../lightlag_dynamic/manh_controllers/controllers.py),
[published change contract](../../lightlag_shift/environment.py).

This establishes a mismatch in the comparator's assumptions. It does not show
that the mismatch explains the entire performance loss, or that fixing it
solves the mission.

### A simple range adjustment did not rescue it

We tried exactly one exploratory adjustment on the same consumed seeds: expose
the union of the initial and publicly declared post-change slip bounds to the
unmodified `kf_mpc`. No hidden change time or realized coefficient was supplied.
Use the same broader bounds in the unchanged control. No parameter sweep or
selection of successful seeds followed.

| Fixed diagnostic | Stock `kf_mpc` | Broader-range `kf_mpc` |
|---|---:|---:|
| Unchanged mean score | .678298 | .601905 |
| Shifted mean score | .575818 | .466103 |
| Shifted alive/home | 40/37 of 40 | 39/35 of 40 |

The adjustment makes both settings worse. It changes initial means, uncertainty
and planning as well as the clipping bounds, so it is **not a clean causal
ablation of the clamp**. It rules out treating this particular range widening
as a ready reference. It proves neither that adaptation is impossible nor that
an LLM will struggle. A reference that maintains the useful initial calibration
and updates it from evidence remains untested here.

### What the current mechanism does and does not ask

The change is guaranteed, only makes the ground worse, and has no alternative
sensor-fault or unchanged cases in its distribution. Ordinary mission drives
already produce wheel and visual odometry. There is no demonstrated need to
choose a separate diagnostic experiment. This is presently a single change in
physical dynamics, not evidence of repeated mistakes across distant encounters.

A small contract edge also needs attention before broader serving: a custom
horizon of 10 is accepted even though the earliest possible change is tick 12.
For seed 3100 the drawn tick is 13; that episode ends without the promised
change. The tested default horizon of 50 is unaffected. Pin the supported
configuration or validate the window against the horizon.

## Updates that landed during integration

### Three actual Opus runs on the ground-change mission

The owner published three Opus 5.5 attempts through OpenCode 1.19.5 and Harbor,
one on each previously designated seed, alongside matched frozen-reference runs.
The table reports raw science divided by available target value.

| Seed | Opus 5.5 | Frozen reference | Opus outcome |
|---|---:|---:|---|
| 3100 | 6/13 = .461538 | 8/13 = .615385 | Alive/home |
| 3101 | 9/13 = .692308 | 8.5/13 = .653846 | Alive/home |
| 3102 | 8/9 = .888889 | 8/9 = .888889 | Alive/home |
| Mean of the three per-seed shares | .680912 | .719373 | All three alive/home |

This is one loss, one win and one tie. Three attempts do not establish a stable
performance deficit, and the reference still has the limitations above. The
missed samples on 3100 are useful traces to inspect, not grounds to choose only
earlier changes or that map for a new benchmark. The owner's reported $1.72
spend was approved by Kristján; it is separate from this assessment's zero spend.
[Teammate report](../lightlag-shift.md).

Our read-only audit reconstructed all six public transcripts and full evaluator
replays exactly with `ShiftEnvironment`; results, verifier details and rounded
reward files agree. All six runs end alive/home, with no invalid public calls or
recorded trial exception. Each paired task digest and experiment configuration
matches, and all three model instructions disclose the ground change. Their
trajectories contain shell calls, so coding access was used. Reported model cost
is $1.7150246 in the saved records.

**Provenance limit:** `experiment.json` explicitly records hand edits after task
generation and stale task hashes. All 29 listed source hashes match, but the
added shift/scenario modules are missing from that manifest. We verified the
recorded behavior and grades, not the completeness of a frozen task build.
Treat this as exploratory pilot evidence and repair the packaging record before
claiming a fully frozen experiment.

### The newer four-rule variant

`RuleChangeEnvironment` publishes four possible changes: worse slip, an energy
cost for turning, lost telemetry packets, or relay transmission windows. Exactly
one occurs in the published tick window. This adds alternative causes, although
they have distinct telemetry signatures and no unchanged/sham case is part of
the random distribution. No model run on this variant has been published in the
reviewed update.

Its prepared reference is an existing controller with a public-rules wrapper
that budgets for the largest possible turning cost from the start. It does
**not diagnose which change happened**. Therefore its success cannot establish
that diagnosis is required; it supplies a useful conservative strategy that a
coding agent may also adopt. Our reproduction confirms zero deaths and 158/160
returns home over the four forced changes. All **800 episodes** in the full
four-controller table match its published rounded scores and counts, and all
**18 current shift tests** pass. Prepared-reference mean shares are .625895
(ground), .655286 (turning), .636440 (link) and .661816 (relay). These are useful
safe outcomes, not proven optima. The corresponding no-change row receives no
change menu, so it is not a sham control with the same uncertainty.
[Variant](../../lightlag_shift/rule_change.py),
[prepared reference](../../lightlag_shift/reference.py).

Relay also has a direct interface cue: after that change, every acknowledgement
gains a `transmit_tick` field. On used seed 3200 at public tick 32, even during an
open relay pass, only relay returns that field; all four cases have identical
sent and execution ticks. Thus the relay mode is identifiable without waiting
for a delayed transmission. This is a specific shortcut in the proposed
diagnosis mechanism, not evidence of a model failure. The broad claim that no
tool says which change occurred should be narrowed or its interface normalized.

Do not repeat the reference docstring's claim that controller 36 bridges gaps:
the explicit gap-bridging mixin belongs to controllers 35/37. The measured
survival is valid; that particular explanation is not established by its code.

## Handoff

- **Sample-chain owner:** retain the exact planner/verifier and negative result;
  do not promote this version. Record the Python runtime requirement.
- **Ground-change owner:** the stock comparisons are reproducible. A new
  comparison needs a public-information reference that handles the declared
  change, alongside the current controls. Do not interpret our failed range
  adjustment as proof that a sophisticated reference is necessary. For the
  newer rule variant, retain the prepared strategy as a serious control and
  test whether identifying the change actually improves decisions enough to
  matter. The new three-run ground pilot does not establish a stable gap.
- **Next discussion:** if we choose diagnosis, distinguish changed dynamics from
  faulty sensing and unchanged conditions, with evidence sufficient to tell them
  apart. If we choose learning, use recurring related encounters and compare
  persistent memory/program reuse with fresh state. These remain proposals;
  this assessment implements neither.

No new paid experiment follows automatically. Ground-change model spending
remains under its owner's existing approval condition. Current environments,
demos, canonical Harbor task and teammates' claims were preserved.

## Reproduction evidence

[Assessment scripts and artifacts](../prototype-assessment/README.md) retain the
commands, runtime versions, per-case outcomes and source/artifact hashes. This
assessment reruns existing consumed seeds; it is not a new held-out evaluation.
Two parallel domain reviews informed the synthesis. No external literature was
added or external benchmark reproduced in this slice.
