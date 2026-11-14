# A substantially harder rover expedition

Sölvi explicitly approved closing the challenger-inspection blind spot and then
making the task substantially harder while continuing to test Claude Opus 5.5.
This is authorized development of an experimental task, not selection of the
team's final challenge submission. The previous sixteen successful model trials
remain published. We will retain successes here as well; a gap cannot be assumed.

## Close the small design hole without another paid toy pilot

Two mirrored cases within the unchanged allocation simulator use priors .85/.50
and values 7/10 (and their mirror). The current best route is a, with direct
expected reward .51 versus b .45. Inspecting challenger b is worth .594375;
inspecting leader a is only .492375. This closes the previous coverage hole. The [672 retained branches and exact results](lightlag-runs/expedition-challenger-v1/summary.json) passed, including 54 nearby parameter checks (minimum challenger advantage .045375).
Independent rational enumeration checks all 21 contingent strategies and 16 joint
outcomes, retaining 672 full simulated branches and 54 nearby public-parameter
checks. This makes no new model calls and does not alter the frozen earlier cases.

The calculation also reveals why another one-shot model pilot is not the main
next step: equal probe costs/reliability can make that choice collapse to a
simple payoff comparison. The larger task must make one observation affect
several later commitments and opportunities to learn.

## Compose information with the actual rover

The new `ExpeditionEnvironment` subclasses the existing continuous
`DynamicEnvironment`. Driving, wheel slip, heading drift, noisy telemetry,
hazards, command queues, sampling radius and home-return grading remain in play.
The canonical task and teammates' simulator/controller/viewer files are read-only.

A new, published mission generator supplies six initial targets and two later
discoveries in three geographic science regions. All targets in one region share
one fixed hidden rich/poor quality state. Target base values, region membership,
priors and quality multipliers are public. This gives observations consequences
for an entire itinerary, not just a single terminal route choice.

- Region priors: rich probabilities .90, .35 and .50; independent across regions.
- Science multipliers: poor .2, rich 1. Sampling reveals the region's exact quality
  through ordinary delayed telemetry; learning by acting remains legitimate.
- Two remote inspections for the whole mission, at most one per region. Each
  costs 2 energy and returns a fixed imperfect signal with accuracy .9. Inspections
  share the normal command queue and three-tick telemetry delay.
- Sixty simulated ticks, three-tick command delay, battery 100, idle drain .5,
  sampling cost 3 and normal `rush_noisy` sensing. Model thinking and public reads
  do not advance the simulator. Scripting is allowed.
- Region 1: two nearby value 2 targets, deadlines 18–32. Region 2: two value 3 targets,
  deadlines 26–44, plus a value 3 discovery at tick 10/deadline 26. Region 3: two value 2
  targets, deadlines 22–40, plus a value 3 discovery at tick 22/deadline 44.
- Score is credited science after quality and deadlines, times the existing
  alive/home factor, divided by the public all-rich total 20. Hidden realized
  quality is never used as a secret normalization denominator.

A batch reserves inspections atomically at acceptance, including the shared
budget. Ordinary queue-clearing hazards cannot silently refund that reservation.
Commands already sent must be included when predicting the rover's next state,
its battery and the time an observation can affect a decision.

## Reference and tests before models

The reference extends the frozen KF/MPC controller with public regional beliefs,
exact Bayesian inspection updates, exact physical-sample updates, and delayed
one/two-inspection lookahead over expected-value route plans. It includes all
queued energy costs and a return reserve. Its four-target receding planning
horizon is a strong heuristic, not a claim of globally optimal continuous-POMDP
control. Independent tests and free development runs must substantiate it.

Controls include no remote inspection while still learning from actual samples,
leader-target inspection, entropy-target inspection and quality-blind planning.
A separate public-quality condition discloses the same realized regional states
at launch while preserving physics, seed and grading. That is an information
control, not a mathematical upper bound. Comparing only against a weak or
misconfigured reference would not establish a useful task.

Before paid testing, validate strict tool/state boundaries, paired hidden/public
physics, unchanged all-rich/no-inspection behavior, sampled-quality revelation,
queue timing, replay reconstruction and the protected Harbor evaluator. Use
free development maps to assess reference safety and whether inspection has
practical value; record adjustments and negative results. Freeze the final
source, two fresh map assignments and model settings before the model outcomes.

## Bounded strong-model pilot

Plan four sessions: hidden/public-quality pairs on two fresh maps, same strong
Claude Opus 5.5 model and clear instructions. Increase the old microtask prompt
guard from 12 to 64 responses; do not count budget/timeout truncation as a reasoning
failure. Keep scripting and a fair accounting reminder available in both arms.
No arbitrary wall-clock difficulty or weaker-model substitution is introduced.

Current coordinator usage is $10.8360204; the separate Rocks $1.4873214 may share
the account. The user's historical $15.70 is not a live balance. Target about
$2 for this pilot, stop new launches at $1.50 reported pilot usage or unknown
usage, and monitor in-flight reported usage to interrupt around $2.25 if needed.
These are spending controls with in-flight overshoot possible, not a provider
hard cap. Preserve incomplete/unrun rows and all costs; never turn a censored
attempt into a model-failure claim. No paid call is authorized outside this
bounded pilot by this document.

A development gap is evidence about these sampled missions, not a population
failure rate. Audit missed deadlines, stale-state commitments, return reserves,
quality-belief updates and wasted inspections separately. The public-quality
control helps distinguish the additional information burden from the navigation
and bookkeeping difficulty already present in Lightlag. Further development may
respond to failures, but any claimed validation must use new frozen inputs.

## Free development gate — 14 November

[All 1,536 episodes](lightlag-runs/expedition-development-v1/summary.json)
enumerate every combination of three qualities and three signals on four maps
(0–3), with one fixed physics seed per map (100–103). The public prior and signal
likelihood weight each world. This integrates discrete science uncertainty only;
it is not an exact continuous-noise or unseen-map expectation. All source hashes
remained unchanged during the 133-second study. Every episode finished alive at
base. No paid model calls were made.

| Policy | Weighted normalized score |
|---|---:|
| Selective reference | .453166 |
| Highest-uncertainty inspection | .447593 |
| Public-quality reference | .425028 |
| No inspection (physical samples still teach) | .412250 |
| Inspect current leader | .398719 |
| Ignore quality | .374750 |

Selective inspection improves 4.09 percentage points over no inspection and
5.44 over leader inspection, but only .56 over the entropy strategy. It loses
to no inspection on map 2. The first reference inspection targets a challenger
on three maps and the leader on one. These results justify testing the composed
mission; they do not establish that sophisticated acquisition is essential.

The public-quality heuristic underperforms the hidden reference. Knowing quality
changes its routes and departure timing, while inspection waits also change
which discoveries and telemetry are available. This is direct evidence that the
reference is not an optimal upper bound. Its heuristic quality limits any model
comparison; a model beating it will be retained as a successful result.

[Actual Harbor preflight](lightlag-runs/expedition-harbor-preflight-v1/summary.json)
completed both no-op (0) and public-tools reference (.28) on fixed development
map/physics 0/0. Live main-container checks found no simulator source, hidden
seed/token, evaluator files or oracle; unauthenticated finish returned 404.
The preflight predates the accounting aid: both exact saved task instructions
use the old text, and the oracle preparer hash reflects an on-disk edit after
its Python module was imported. Simulator/reference/grader sources match; the
manifest records the actual task bytes. Model tasks will be generated in a
fresh process after the final source commit, with the common aid included.

## Strong-model pilot outcome and decision

[Protocol, all four assignments and usage](lightlag-runs/expedition-claude-pilot-v1/summary.json)
retain three completed `anthropic/claude-opus-5-5` / OpenCode 1.19.5 sessions and
one unrun assignment. Consumed task sources match commit `c9ceb52`; protocol
`3bff0ec` froze the tasks, common accounting aid, model settings and salted seed
commitments before model outcomes. All task source bytes are retained, regardless
of the manifest's directory-wide dirty flag during evidence preparation.

| Assignment | Opus score | Protected reference | No inspection |
|---|---:|---:|---:|
| A, hidden | .5500 | .4600 | .4600 |
| A, public quality | .5575 | .4600 | .4600 |
| B, public quality | .2900 | .3100 | .3100 |
| B, hidden | **Unrun** | .2700 | .3100 |

Every attempted model session finished normally, alive at base: no retries,
invalid calls, provider errors or observed output/step truncation. Reported cost
is **$1.5588192** (.6094926 + .4937166 + .4556100). That crosses the predeclared
$1.50 new-launch guard, so B hidden was never started; it is not a model failure.
The $2.25 in-flight guard did not fire. Historical coordinator usage plus this
pilot is $12.3948396; with the possibly shared Rocks usage, known total is
$13.882161. Neither amount is a verified live balance or provider invoice.

The runner copies logs after completion, which prevented its initial host-only
monitor from seeing live usage. A scalar-only container monitor covered the
first run from response six onward; subsequent runs used that approach from
startup. [The monitoring amendment](lightlag-runs/expedition-claude-pilot-v1/monitor-amendment.json)
records this blind interval and the unchanged model-facing experiment. Every
completed response's reported usage is retained; no spend threshold was crossed
in flight and no attempt was restarted or omitted.

Seven protected runs (three models, four references) reconstruct exactly from
frozen task sources; all four no-inspection controls also reconstruct. All four
seed commitments verify. The three model sessions used 58 completed responses
and 79 public tool calls. Full task inventories, public actions, evaluator replays,
grades and usage are retained; private provider messages/state are not published.

**This still does not establish a convincing strong-model gap.** Opus wins both
A conditions. It pipelines two inspections with useful movement and sampling,
then collects a valuable discovery; the reference waits before driving and
forecasts neither future discoveries nor sample-information branches. Those
are comparator limitations. Two inspections plus an initial sample also provide
evidence about all three regions early, weakening the intended acquisition
bottleneck. Inspection signals remain imperfect; observing every region does
not disclose every quality with certainty.

B public has a small observed .02 normalized shortfall: one omitted poor target
worth .4 raw science. Two failed samples consume six energy, and the rover
finishes with only .65 battery. The model collects 5.8 of that world's 7.2
all-on-time science upper total; the reference collects 6.2. These totals are not
proven achievable optima. This is physical control/resource evidence, not an
information-selection failure. With one incomplete pair, do not infer a
population failure rate or a causal effect of hiding quality.

[Decision and handoff](lightlag-expedition-handoff.md): improve the reference's
inspection/travel overlap in a separate version, then develop **six regions with
two inspections** and require a free advantage over fixed-two, entropy and
no-inspection controls. Keep the same strong model. More regions or a lower score
from a larger denominator alone will not count as success. Weak-GPS fusion remains
a separate teammate direction. No follow-up implementation, new paid pilot or
canonical-task promotion is claimed here.
