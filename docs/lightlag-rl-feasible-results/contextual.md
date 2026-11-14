# Planner-initialized contextual learning

This is the local, bounded [three-seed protocol](../lightlag-rl-contextual.md).
It follows the [verified charging-aware interface](README.md). Sölvi separately
owns scratch PPO/replay learning on Modal; his map ranges and results are separate.
The original full-route planner remains the project reference.

## Implementation verification

The 1,984-parameter model receives 60 public features, including charging
estimates, onward opportunities and pooled candidate context. It learns a next
goal above the unchanged navigator. Teacher search runs only while generating
demonstrations. Imitation and RL checkpoints are saved separately; overridden
proposals remain in the trace but receive no policy gradient.

Six focused tests pass, including numerical differentiation, context dependence,
public-only feature extraction, synthetic imitation, excluded overridden draws,
full-horizon student inference with teacher calls forbidden, and complete paired
evaluation bookkeeping. Sölvi's tested gradient/Adam implementation is reused.

The [smoke run](contextual-smoke/report.json) uses only already-used maps 1/2,
two imitation epochs and one four-mission RL update per initialization. Its
[audit](contextual-smoke/audit.json) reconstructs all three optimizer updates,
six imitation epochs and 536 training draws. All 54 saved physical trajectories
replay; all 42 teacher/evaluation policy scaffolds re-execute, including candidate
features, choices and commands. Smoke outcomes are not learning conclusions.

```sh
python3 -m unittest discover -s tests/rl_contextual -v
python3 -m tools.rl_contextual.run --output docs/lightlag-rl-feasible-results/contextual
python3 -m tools.rl_contextual.audit docs/lightlag-rl-feasible-results/contextual/report.json --output docs/lightlag-rl-feasible-results/contextual/audit.json
```

The production runner requires the completed feasibility audit, freezes sources
and maps before teacher data, saves every update, and freezes all nine checkpoints
before opening any fresh evaluation map. Directories are immutable. A failure
is retained and does not silently trigger a retry. Audit from the source version
in the freeze; later unrelated experiments must preserve these source files.

## Completed production result

Protocol published at `bddfd56`; implementation and audited smoke published at
`55654bb` before production. The fixed local run completed in 748.3 seconds:
20 teacher missions, 200 imitation epochs for each of three initializations,
384 RL missions / 24 updates, and all 320 final-check missions. Check worlds
**74000–74015 are now consumed**. No cloud job or model API call was used.

| Policy on the same 16 fresh worlds | Mean official score | Alive/home |
|---|---:|---:|
| Untrained contextual scorer | .092619 | 96/96 |
| Planner imitation | .282207 | 96/96 |
| Imitation + 128 RL missions per seed | .279219 | 96/96 |
| Charging-aware persistent greedy | .326323 | 16/16 |
| Unchanged full-route reference | .509094 | 16/16 |

Neural rows average all three initialization seeds and two action draws per map;
controls are deterministic, one mission per map. There are no evaluation deaths
or invalid calls. The primary RL-minus-imitation gain is **−.002988**, with the
predeclared paired-map 95% interval **[−.014367, .006583]**. The RL screen fails its
gain and interval criteria; return/death/validity criteria pass. Imitation is a
large improvement over random initialization, while this short RL phase gives
no clear extra benefit. Neither learned stage reaches greedy or the reference.
**Keep the existing full-route planner as the project reference.**

| Initialization | Imitation score | After RL | Paired mean change |
|---|---:|---:|---:|
| 17 | .286778 | .283004 | −.003774 |
| 29 | .279091 | .278337 | −.000754 |
| 43 | .280752 | .276316 | −.004436 |

The 16 training teacher missions supplied 354 new-goal labels; four separate
teacher-label validation missions supplied 98. Exact-label agreement after
imitation is 85.6%/88.1%/88.7% on training and 64.3%/67.3%/68.4% on validation
(for seeds 17/29/43). Validation here is a diagnostic before RL; those worlds
belong to the training pool, and are separate from the fresh check above.
The adapted one-goal teacher's scores were .3534 on training and .3818 on
validation; these are different maps, not paired against the table's reference.

[Full run](contextual/report.json), [source/data freeze](contextual/freeze.json),
[nine-checkpoint freeze before evaluation](contextual/evaluation-freeze.json),
all teacher/training/evaluation trajectories and all checkpoints are retained.
The [completed audit](contextual/audit.json) reconstructs all 600 imitation epochs,
24 RL optimizer updates and 18,380 training draws. All **724 physical trajectories**
replay. All **340 teacher/evaluation controllers** re-execute, including their
candidate features, held goals, choices and commands. Training choices replay
from recorded features; training feature extraction remains source-pinned.
The [main-push watcher publication check](publication-verification.json) also
independently verifies artifact hashes, matrices, paired statistics and all 724
physics replays. It preserves the original freezes and does not claim another
optimizer reconstruction or new training run.

This is one fixed, small pilot: a 1,984-parameter selector, sixteen demonstration
worlds, and eight RL updates per initialization. Neural policies sample from
softmax; deterministic argmax deployment was not tested. The bootstrap reflects
map variation for these three fixed initializations. The negative RL result
rejects promotion of this run, not the possibility that larger training or a
different learner could work. No task rule, reward, training budget or checkpoint
selection was changed after seeing the check results.

## Version handoff after the team's freeze

The team subsequently merged the frozen normal-Traverse rules, the task 0.1.1
reference's `home_floor` return behavior, and the three-mission campaign candidate
([owner's readiness answer](../lightlag-traverse-readiness.md)). The simulator
rules are unchanged, but the navigator now permits a smaller reserve and shorter
drives when returning home. Identical reference scores on the owner's tested
worlds do not prove identical commands or outcomes for every learned policy.

This study's code, complete artifacts and original navigator are preserved at
**`5557935`**, on branch `codex/rl-feasible-results`. Its actual production source
freeze is `55654bb`. Run the audit from that result commit, not from a newer
checkout with changed source pins:

```sh
git worktree add /tmp/junction-contextual-reproduce 5557935
cd /tmp/junction-contextual-reproduce
python3 -m tools.rl_contextual.audit docs/lightlag-rl-feasible-results/contextual/report.json --output /tmp/junction-contextual-audit.json
```

The [integration check](integration-verification.json) confirms unchanged
simulator/terrain/surface/planning files and all 13 focused adapter tests pass
with the updated navigator. The immutable original-training guard correctly
rejects the changed source set on current main; that is a request to reproduce
from the pinned commit, not a reason to rewrite historical hashes. These are
API/component checks, not a new evaluation of the trained checkpoints.

This preserves the experiment rather than re-pinning old results after the
fact. A current-version compatibility check should use already-used development
worlds before a separately frozen new training/evaluation run. The campaign's
2027–2029 worlds are submission cases, not training data. Its aggregate score
weights missions by available value; the single-mission means above are not
directly comparable to that campaign score. No learned campaign result is claimed.

Sölvi's independent [scratch-learning campaign](../learning-campaign-results/README.md)
supplies separate learning evidence. His published early 512-mission PPO
validation mean rose .0874→.3440, with 96/96 home, while greedy and beam reached
.3806/.5143 on those validation maps (snapshot `a637cf6`). Those are different
maps and budgets; they are not a head-to-head comparison with this pilot. His
final check remains separate from this completed study. The later shared status
records his larger stages paused at his request pending final-version coordination;
existing 2048-mission pilot jobs may finish. This handoff does not restart them.

## Next model confirmation

Charging time and return budgeting are now a supported intervention lead on the
reused development maps. The 300-world farm also finds failures in saved Claude
programs, but a supervising coding agent could repair or interrupt those programs.
A fresh full-agent comparison is still needed before calling this a robust
frontier-agent failure. The Traverse/Harbor owner retains that scope.

Freeze the chosen mission version and reference first, then run ordinary and
strategy-hinted full-agent attempts on the same newly allocated worlds. Give
both arms the same public rules, physics/code access, coding tools and resource
budget. The hint should explicitly ask for charging waits in the return budget
and for comparing target sequences; it should supply no hidden state, seed,
reference route or reference implementation. Retain all attempts and distinguish
finished missions, process failures and token/time exhaustion. Report matched
score gaps, collected science and terminal penalties, including every successful
Claude attempt. Do not treat the best single failure as the project result.

This branch does not modify the task's rules or launch that overlapping agent
experiment. Its frozen training uses the original mission; it makes no transfer
claim for the proposed harsher day or teammates' MAX-map variant.
