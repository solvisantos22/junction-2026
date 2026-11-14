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
