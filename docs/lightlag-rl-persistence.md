# Persistent goals: fixed development diagnostic

Sölvi approved testing goal persistence after the first small-policy RL pilot.
Its saved traces show frequent target changes; they do not prove the cause of
low reward. This experiment tests a concrete intervention before more training.
It changes no environment, navigator, policy weights, reward or canonical task.

## Intervention

Wrap the frozen `lightlag_rl.adapter.run_episode` chooser. At every ordinary
planning invocation, call and validate the underlying chooser and record its
proposal. In the frequent arm, return that proposal unchanged. In the persistent
arm, retain the previous non-base target while its ID remains in the unchanged
public candidate list. Otherwise release it and accept the new proposal. Never
lock base; a home choice can be reconsidered on the next ordinary replan.

Candidates already exclude sampled, pending, unreachable and return-time-
infeasible targets. Pending sampling can therefore release a goal before its
acknowledgement; a rapid failure can allow retrying the same goal. Discoveries,
solar-estimate updates and slip-field rebuilds do not independently cancel a
still-available target. There is no new patience timeout, battery reserve,
deadline-value rule, reward shaping or early episode stop.

The existing navigator still updates estimates, chooses drive commands, waits
for energy and forces return when its time rule requires it. This wrapper never
modifies a route or overrides navigation. A retained intention does not prove
continued physical pursuit. The candidate mask checks return time, not a new
battery feasibility rule. Holding a science target also overrides a newly
proposed voluntary return home: this tests a commitment/termination rule, not
memory alone.

## Cases and frozen policies

- Policies: initial neural weights, final neural weights and the same greedy
  chooser from the completed `pilot-01`; initial/final hashes must match its
  training metadata. No weight update or model selection occurs.
- Modes: frequent and persistent for every policy, same candidates and navigator.
- Development worlds: **71000–71005 and 71007–71024**, the first 24 sorted IDs
  actually visited in saved training batches. Only 109 of the 128 reserved
  training IDs were visited; 71006 is deliberately absent.
- Each neural policy: two action draws per world; greedy: one. This is
  **24 × (2 + 2 + 1) × 2 = 240 missions**, each graded at tick 420.
- Action RNG: `1000003 * map_seed + draw`, shared by modes and neural policies.
  Both modes consume a proposal on every planning invocation. Different
  trajectories can still produce different planning times and states.
- Local smoke and integration verification use only already-used worlds 1/2.
  No fresh check worlds, API calls, cloud jobs or additional training are used.

Publish this protocol before production diagnostic cases. Before the first case,
freeze source hashes, this protocol, weights, configuration and case list.
Verify the old training source closure and copied policy hashes. Retain complete
compressed replays, grades, proposal/effective-choice traces and partial progress;
fail on input drift, invalid chooser proposals or incomplete cases.

## Primary decision and interpretation

The primary contrast is **persistent minus frequent for the initial policy**.
Average its two action draws within each map, then compute the mean difference
and a 10,000-draw paired-map bootstrap interval (seed 17, percentile 95%).
The development screen requires all of:

1. Mean reward gain at least **0.03**.
2. Bootstrap lower bound greater than zero.
3. Persistent alive/home count no more than **two below** frequent across 48
   episodes, with no increase in deaths or invalid calls.

Report the final-weight and greedy contrasts regardless of their outcomes;
neither can replace a failed primary endpoint. Their trajectories, sampling and
return outcomes provide context. Final weights were trained with frequent
reselection, so applying them to persistence is a distribution change, not a
measurement of learning under the new interface.

The maps are reused training data selected by ID, not unseen evaluation data.
The interval describes variation across these development maps and does not
establish generalization. A pass supports a separate training experiment; a
failure is retained without retuning this screen. Audit complete physics replays
and grades, proposal sampling, wrapper transitions and summary calculations.
Record the remaining limit if public feature extraction is only source-pinned.

## Rainbow and the next training budget

Sölvi suggested Rainbow and reports **$300 total team Modal credit**, not a
verified current balance or a budget for this diagnostic. No cloud spend occurs
here. A later approved training protocol should use bounded stages, multiple
training seeds and new evaluation maps, sharing credit with teammates.

[Rainbow](https://arxiv.org/abs/1710.02298) combines Double DQN, prioritized replay,
dueling networks, multi-step targets, distributional values and noisy exploration.
Replay and multi-step targets make it a plausible next learner, but its Atari
results do not establish an advantage on Traverse. A future comparison should
separate the action interface from the learning method, mask unavailable targets
and record transitions/duration at actual goal decisions rather than treating
forced holds as newly sampled actions. Persistent goals resemble
[options](https://www.sciencedirect.com/science/article/pii/S0004370299000521),
actions that extend over time; any discounting must account for that timing and
the actual mission objective. No Rainbow implementation or training is claimed.

This protocol is frozen once production cases start. Results, decisions and
handoff belong in `docs/lightlag-rl-persistence-results/README.md`.
