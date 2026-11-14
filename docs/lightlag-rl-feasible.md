# Charging-aware RL follow-up: fixed first comparison

14 November 2026. Kristján approved implementing the next steps in the
[independent RL review](research/2026-11-14-rl-reference-and-failures.md).
Sölvi's persistence work is complete and preserved. This new scope first tests
its charging-time hypothesis, then conditionally develops and trains a contextual
scheduler. The existing mission, pilot, reward, frozen policies and studies are
read-only. No canonical task change follows automatically.

## Stage 1: one visit and return, including charging

Both arms use Sölvi's existing persistent goal wrapper, original fourteen actor
features, identical fixed initial/final neural weights and greedy chooser, and
the original navigator. The control keeps the original travel-time candidate
mask. The intervention additionally offers a science goal only when the
reference's `RouteProblem.score([goal])` predicts a feasible visit, sample and
return, including its modeled charging waits. Use the reference's existing
slack, battery floor, sample cost and return margin without tuning them.

Home is always available. A held goal is released when it disappears from the
filtered candidate list. No extra home lock, deadline preference, battery bonus,
earlier grading or new reward is added. The chooser is invoked and consumes a
proposal at every original planning invocation in both arms. Masks and ensuing
trajectories can differ; pairing the random seeds does not make actions identical.
The filter uses only published data and the pilot's beliefs. Its aggregate
per-leg model is an approximation, not a physical safety certificate.

Cases are Sölvi's same 24 visited development maps: **71000–71005 and
71007–71024**. Two action draws for initial and final weights, one for greedy,
in both arms: **240 complete 420-tick missions**. Action seed is
`1000003 * map_seed + draw`. These maps are reused development data, not a fresh
generalization check. Smoke tests use already-used maps 1 and 2 only.

Before the production comparison, publish this protocol and code, freeze source
and input hashes and retain all cases, complete replays, goal proposals/effective
choices and feasibility records. The control must reproduce the corresponding
saved persistence replay and grade exactly. Auditing reconstructs physics and
also reruns the trusted policy scaffold to compare extracted candidates,
features, decisions and issued commands. It never executes generated model code.

The primary comparison is **charge-aware minus time-only for final weights**.
Average the two action draws within each map, report the mean and a 10,000-draw
paired-map bootstrap interval (seed 17), and retain initial/greedy contrasts.
Report raw score, alive/home, deaths, invalid calls and rejected candidates.

An engineering screen for proceeding with this interface requires the final
policy's mean official score to be no more than 0.01 below the old interface,
at least as many alive/home outcomes, and no increase in deaths or invalid calls.
This is a permissive development screen, not an official judging requirement
or a claim of improved generalization. Report whether the score interval excludes
zero separately. A failure calls for diagnosis and a separate declared experiment;
do not silently tune this comparison or omit an unsuccessful arm.

## Subsequent stages, conditional and not yet frozen

If the interface is verified and passes the development screen, add candidate-set
or route context and demonstrate planner imitation on training data before RL.
Keep an imitation-only checkpoint. Run a bounded initial RL comparison with
three fixed training seeds, and compare untrained, imitation-only, RL, greedy
and the original planner on matched new evaluation maps. Publish the exact
architecture, data, training budget, promotion rule, map allocations and source
freeze before training/evaluation. No fresh map range is consumed or reserved
by this stage-1 protocol; no cloud or model API request is necessary for stage 1.

Claude confirmation should use a separately frozen full-agent test on new maps,
including fair code access and a strategy-hinted control, retaining process and
resource errors. Existing farm/Traverse scopes remain with their owners. A new
learning result is not evidence of a frontier-agent gap by itself.

Results and handoff: `docs/lightlag-rl-feasible-results/README.md`.
