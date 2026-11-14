# Lightlag morning brief

**Working recommendation: keep Lightlag as the leading provisional project,
and focus the day on a fair, frozen task and a convincing judge rehearsal.**
We have a working environment, real model failures, recoveries, protected
grading and clear explanations. We do not yet have evidence for a broad or
unavoidable frontier-model control deficit. More physics is not the immediate
priority.

**Overnight work is recovered, published and closed.** All nine repeats and
all twelve accounting-aid attempts are complete. The aid improves selected-case
performance substantially, but does not pass the stricter gap-removal threshold.
The separate controller-generation request exhausted its output budget before
producing code, so it provides no transfer result. Coordinated usage totals
**$9.9394628**, combining reported online costs and calculated generation cost.
No paid calls remain running. This handoff includes teammate changes through
`62ac788` and the independent Rocks review at `21c890e`.

## What the team has built

- **Kristján:** the actual Docker/Harbor model path, protected simulator
  artifacts, separate verifier and early-stop collection. The original core
  task is demonstrably runnable; the model solved its seed-7 example. His
  [3D demo](../viewer/mars-demo.html) now presents **Deadlines, Sand and Rocks**,
  each with three model attempts and the frozen reference. The latest layout
  (`852827a`) restores four full-screen views at his request; preserve that
  choice. All 29 viewer tests pass after sync. His new Rocks runs score
  **0.846154, 0.519231, 0.692308** versus reference **0.769231**, all alive/home.
  The [independent audit](lightlag-audits/overnight/team-rocks/README.md)
  verifies all four replays and retains the limits of the missing installer
  records and reported map-selection procedure.
- **Manh:** dynamic missions, state estimation/control references, the decision
  auditor and additional scenario/controller experiments. The real-time and
  Mars-operation additions remain separate proposals. Their scenario-specific
  gains should not be assumed to transfer to the plain profiles. His `2b2f6fa`
  [ablation](../lightlag_dynamic/manh_controllers/README.md#plain-profile-check-the-guarded-moves-are-the-whole-cost-saturday-about-1100-helsinki)
  reports that controller 27's guarded moves explain the plain-profile cost.
  His new **controller 34** (`62ac788`) probes only when the delay costs no
  planned value. On his fresh seeds 5000–5259 he reports a plain-profile tie
  with 24 (+0.2 points), +1.8 points over 27, and +3.2 points over original KF
  across scenario suites. It is not better in every cell. These new reports
  have been read, not independently rerun by this coordinator; our frozen
  comparisons and canonical reference remain unchanged. Selectable biomes
  are claimed sandbox work, not delivered or adopted at this checkpoint.
- **Sölvi with Codex:** frozen model comparisons, repeated runs, independent
  research, an instruction-aid test, isolated reference comparisons and a
  decision demo. Contributions and actual provider use are recorded in the
  [prize evidence log](prize-evidence.md); existing teammate authorship remains.

Start with the [62-second silent clip](lightlag-demo-media/README.md) or the
[offline decision page](../viewer/decisions.html). They show one selected
failure and a checked post-hoc continuation, clearly labelled, alongside the
original mixed results. The continuation is not a newly successful model run.

## Evidence that changes our interpretation

| Question | Delivered evidence | What it supports |
|---|---|---|
| Does the model always fail? | Original eight attempts: **3 wins, 2 ties, 3 deficits** against frozen KF + MPC. Both earlier seed-500 pilots scored 1.0. | Keep model wins visible. Two terminal battery deaths drive much of the original mean deficit. |
| Do failures recur? | Nine new attempts on three failure-selected cases: **2 wins, 2 ties, 5 deficits; 3 deaths**. All exact replays, no infrastructure findings. | Energy failures recur conditionally, but recovery also occurs without changing the prompt. This is not a random-map failure rate. |
| Does clearer accounting help? | All twelve declared attempts complete: **five paired improvements, one tie; mean C 0.406571 / T 0.732265**. Aid survives and returns home in 6/6. | The improvement threshold passes, but gap-removal fails on noisy 504. Combined energy/queue advice does not isolate a mechanism; selected cases do not measure map-wide reliability. |
| Is the reference simply too weak? | Candidate 24: fresh rush mean gain **0.007898**, noisy scores all tie. Candidate 27 has lower inspected-set means than either earlier policy. | Preserve capable alternatives and negative results; do not silently substitute a different reference per map. |
| Can the model generate a transferable controller? | The one response hit its 24,000-token cap during thinking and produced no code. All forty fresh cells remain unrun/null; no retry. | The question remains unanswered. An incomplete response under this budget is not zero episode performance or evidence of general model incapability. |

The [overnight protocol/results](lightlag-overnight-evaluation.md),
[original comparison](lightlag-fixed-seed-comparison.md),
[reference-24 study](lightlag-runs/overnight-reference-study/README.md),
[candidate-27 supplement](lightlag-runs/overnight-reference27-study/README.md)
and [synthesis outcome](lightlag-runs/overnight-synthesis/README.md) retain all rows,
selection rules, costs, failures and reproduction instructions.

## The story worth testing

The defensible construct is **tracking delayed observations, accepted commands
and future resource commitments**. The rover is a compact, inspectable way to
test it. We should call this a stylized remote-operations simulation, not a
Mars digital twin. Real spacecraft have onboard autonomy, scheduling, sleep
and power-generation behavior that this toy contract omits. The
[direction review](research/2026-11-14-lightlag-direction-review.md) checks
spacecraft, underwater vehicles and asynchronous software queues separately.

Novelty cannot be “the first asynchronous agent benchmark”:
[Gaia2 already studies dynamic asynchronous agents](https://arxiv.org/html/2602.11964v1).
Our potential contribution is a small reproducible environment whose accepted
commands, delayed measurements and protected trajectories make failures
inspectable. The [evaluation review](research/2026-11-14-lightlag-evaluation-review.md)
explains why repeated attempts, explicit resource budgets and frozen versions
matter. A reference-relative audit is not a proof of optimal regret or of a
model's internal intent.

The additional synthesis test was designed to challenge our explanation.
Controller-design literature makes code generation a serious comparison, but
its methods and numbers are not Lightlag evidence. For example,
[CoDyControlBench](https://arxiv.org/html/2608.07004v1) uses feedback and up to
three iterations under its main protocols. Our one-response transfer check is
narrower. Its incomplete generation did not reach any transfer evaluation;
improvement with more generation budget or feedback remains untested.

## What to attack when everyone is awake

These are proposed owners and acceptance checks, not new assignments imposed
on teammates or a final project choice.

| Order | Focus | Suggested owner | Done when |
|---|---|---|---|
| 1 | Choose one objective, mission profile and reference from the complete evidence. | Whole team; short decision meeting | A written versioned contract states exactly what the task measures and what result would falsify our claim. |
| 2 | Make the judge entry point match that choice. | Kristján, with experiment owner | A clean checkout runs the selected Harbor package; exact package/source hashes match a real model log, reference and no-op, including early-stop grading. |
| 3 | Validate the explanation on fresh data after any material change. | Manh + Sölvi | A fixed protocol retains every model attempt, including wins and errors, and distinguishes selected diagnostics from new-map evidence. |
| 4 | Rehearse the short story and prepare the final submission/prize evidence. | Sölvi, reviewed by team | One objective, one decisive moment, one protected reward, mixed-results context and a reproducible command; current track/prize requirements checked. |

The largest known packaging gap is concrete: **canonical `harbor/lightlag`
still runs the solved original core seed 7**. Generated dynamic experiment
folders are not automatically the final judge task. Source synchronization
alone does not choose or promote a mission.

An independent readiness audit found one interface-clarity defect: shared MCP
descriptions promise a full map and exact visual odometry, whereas dynamic
rules correctly describe discoveries and noise. A description-only correction
is now integrated after B finished and passed independent review. All 29 MCP
and Harbor tests pass. It changes no simulator or grader behavior; no evidence
shows that it caused a historical failure. Old task manifests remain authoritative.

Do not turn up drain, remove scripting or add real-time penalties just to
defeat saved traces. If a reusable policy closes the gap, narrow the story to
online reliability/controller construction or reconsider the task. If failures
remain, verify that they are fair decisions under the public contract before
adding mechanics. Real-time speed, Mars relay/slip rules and training can be
separate later experiments when they answer a defined question.

## Wider options, without a reflexive pivot

My current ranking is **Lightlag, ColdChain, BatchPilot, then the saved Bazaar
design**. This is a feasibility judgment under the recorded challenge rubric,
not a measured leaderboard across projects.

- **ColdChain** is the best emergency hedge: small discrete instances could
  make an exact causal reference and grading easier to defend. It still needs
  a code-assisted model failure after real commitments, not merely a routing
  puzzle. The [EURO dynamic-routing benchmark](https://github.com/ortec/euro-neurips-vrp-2022-quickstart)
  provides a useful precedent and a strong HGS-based starting point.
- **BatchPilot** has credible quality and safety consequences, but hidden
  parameters plus delayed lab measurements create substantial validation work.
  The [do-mpc polymerization example](https://www.do-mpc.com/en/latest/example_gallery/industrial_poly.html)
  is useful starting material; its estimator assumes all states are measured.
  Promote this only if a working plant and fair reference already exist.
- **Bazaar** has no established rescue gap. Its saved independent merchant
  curves may mostly test inference and allocation. Existing negotiation
  benchmark deficits do not establish failure for a tool-using OpenCode agent.

No unbuilt alternative currently has stronger local evidence than Lightlag.
The useful move is to challenge its strongest claim before spending the day
building a replacement.

## Budget, prizes and unresolved event details

The user reported $15.70 at the start of this overnight work. Earlier
$4.2977204 runs are separate. Block A reports **$3.9709816** and all twelve B
attempts **$5.4645252**. The single synthesis response reports 5,989 input and
24,000 output tokens, for **$0.503956 calculated cost** at standard pricing.
The coordinated total is **$9.9394628**; the $12 launch guard and $15.70 ceiling
were respected. No retries or replacement outcomes were purchased.

Kristján separately approved about $1.50 for Rocks; its three saved trials
report **$1.4873214**. Whether these calls share the same billing account is
unverified, so neither ledger establishes an available balance. Codex credit
consumption is not separately metered here. The Codex usage interruption
delayed publication/review; the completed online run artifacts were recovered.

Keep the Codex evidence alongside real work. Modal's compute grant and the
Gemini application do not mean those tools have been used; do not claim their
prizes on that basis. Training is optional under the recorded AfterQuery
announcement. Confirm any additional-prize forms and final platform selections
before submitting; no submission or external message is performed here.

Exact judging model/version/effort and token/time limits remain unknown in the
saved organizer record. The last successful authenticated watcher read was
**04:29 Helsinki on 14 November**; subsequent observed checks were blocked by
unavailable native browser surfaces. Timer activity does not establish fresh
source coverage. Recheck the official channel/platform when accessible. The
last verified final deadline was **Sunday 15 November at 10:00 Helsinki**;
the saved Lightlag entry remained a draft, separate from a closed entry-form
view. See [readiness](afterquery-readiness.md) for the submission contract.

## Handoff

The overnight evaluation, bounded synthesis, wording correction, reserve fix,
decision demo/clip and research scopes are complete and released. Their verified
increments are on `origin/main`; current teammate ownership is in
[TEAM_STATUS.md](../TEAM_STATUS.md). The next useful work is the four-step judge
package and confirmation sequence above. No final project, mission, reference,
deployment or prize choice has been made on behalf of the team.

Reproduction notes: retain the old experiment manifests; B exports use the
pre-wording-fix checkout `6fb112f`. Do not rerun the single synthesis request or
fill its unrun rows with invented scores. The forty reserved cells were never
constructed. The main Desktop checkout was left untouched; this work was
integrated from the separate `6974` worktree.
