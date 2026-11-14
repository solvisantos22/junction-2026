# Lightlag: direction, realism and morning decisions

Research date: **14 November 2026**. Independent Codex review within the overnight
research claim. This is advice for the team, not a project or rules decision.
The evidence cutoff for recommendations is the completed eight-attempt
[fixed comparison](../lightlag-fixed-seed-comparison.md). The separately running
[overnight repeats](../lightlag-overnight-evaluation.md), stronger-reference
comparison and decision demo are not assumed to have succeeded. No model calls,
new benchmark experiments or code changes were made for this review.

**Recommendation: retain frozen Lightlag as the leading candidate, but test the
strength of its explanation before making it harder.** Finish the repetitions,
compare the newer reference separately, and try a versioned, clarity-only
energy/queue aid if the team has budget. Keep the paused simulation clock. The
best defensible story is a small, auditable test of maintaining commitments and
resource constraints through delayed tools. It is not yet evidence that modern
agents generally fail delayed control, and it is not a Mars digital twin.

The cheapest valuable next result could be that a public resource ledger
eliminates the observed failures. That would identify an effective interface
intervention and invalidate a broad capability claim. It would also be more
informative than finding a new setting on which the agent dies.

## What the delivered evidence supports

| Evidence already delivered | Decision implication |
|---|---|
| Eight predeclared attempts: **3 Claude wins, 2 ties, 3 deficits** against frozen KF + MPC; two deficits end in battery death. | There are real failures worth investigating, but the reference is not uniformly stronger. Do not present a selected death as the typical result. |
| Mean model/reference reward is **0.554808 / 0.724679** on `rush` and **0.544071 / 0.690224** on `rush_noisy`; four maps and one attempt per cell. | The means favor the reference. They are highly affected by the terminal survival multiplier and do not establish repeatability. |
| Every attempt replays exactly; the audits report no infrastructure findings. | Failure attribution can start from concrete decisions, rather than a suspected broken harness. This is unusually useful delivered work. |
| Five of the six surviving model runs match or beat the frozen reference. | The immediate story is inconsistent constraint preservation, not general inability to route, learn slip or use code. Keep the dead runs in the primary result; this conditional observation is only diagnostic. |
| Claude solved both seed-500 pilots and built its own planner. | Weak scripted shortcuts are not reliable stand-ins for a capable coding agent. Their failure does not predict a model gap. |
| Harbor packaging, separate verification, protected replay, controls and an initial viewer exist. | Lightlag now has a large execution advantage over unbuilt alternatives. This is forward-looking reuse value, not a reason to defend a disproven hypothesis. |

The specific queue failure is especially legible: on noisy seed 502, waiting
from tick 12 to 17 lets the queue empty at 14 and pushes a new command's earliest
execution to 21. Sending the sample at 12 could execute it at 16 under the
reference continuation. This is a commitment/timing mistake with available
rules. The two energy cases demonstrate a different mechanism: an attractive
extra excursion consumes the reserve needed to remain alive through tick 50.
The [comparison and continuation checks](../lightlag-fixed-seed-comparison.md#decision-audit-observations)
separate these facts from stronger claims about when loss became unavoidable.

Neither battery failure, by itself, shows that delay caused the error. The same
terminal reserve rule exists at delay zero. A paired delay ablation could test
that hypothesis later, but a zero-delay scripted baseline is not a zero-delay
model result. Until then, describe an error **in a delayed environment**, rather
than an error proved to be **caused by delay**.

## Real analogues, with the missing pieces made explicit

The causal structure is useful even when the physical details are simplified.
The table distinguishes what primary sources establish from our interpretation.

| Analogue and verified source | What transfers to Lightlag | What does not transfer automatically |
|---|---|---|
| **Spacecraft supervision.** ESA distinguishes spacecraft event time from Earth receive time, describes minutes of one-way delay, and explains why commands and autonomy must be prepared ahead of time. [ESA operations account, 5 August 2012](https://blogs.esa.int/mex/2012/08/05/time-delay-between-mars-and-earth/) | A report describes a past state; a new action takes effect later still. Displaying state time, observation time and scheduled execution separately is meaningful. | A fixed three-tick delay has no established conversion to actual Mars operations. Light time is only one constraint; communications availability and onboard autonomy also matter. |
| **Mars activity scheduling.** JPL describes plans covering one or more sols, uncertain activity duration/energy use, and onboard scheduling as Perseverance's primary operations method since October 2023; the page's status is January 2025. [JPL M2020 scheduler project](https://superintelligence.jpl.nasa.gov/public/projects/m2020-scheduler/) | Resource reservations and unused opportunities matter after a plan is committed. Replanning as execution differs from prediction is a real engineering problem. | NASA does not rely on an Earth-side conversational model to choose every wheel movement. A stronger real-world comparison is a supervisory agent using capable local control. |
| **Energy across a planning horizon.** JPL's scheduler paper tracks activity resource impacts over time, and jointly schedules heating, wake/sleep and energy. [Rabideau et al., i-SAIRAS 2020, §§2.1–2.2](https://superintelligence.jpl.nasa.gov/public/documents/papers/M2020-OBP-i-SAIRAS2020-camera.pdf) | “Enough energy to get there” is insufficient when future obligations also consume energy. The whole resource trajectory matters. | Real sleep and power generation change the budget. Constant drain with no sleep action is a deliberate simplification, not an accurate Perseverance energy model. |
| **Underwater science missions.** WHOI's Sentry uses battery power underwater, communicates acoustically while submerged and differently at the surface, and carries science sensors/samplers. [WHOI Sentry specification](https://www.whoi.edu/home/interactive/sentry/sentry.html) | Finite-energy sampling away from a recovery point is a closer structural analogy for a bounded sortie than an indefinitely operating Mars rover. | This source does not validate our delay, noise, return multiplier or energy coefficients. An ocean reskin would not create such validation. |
| **Asynchronous software work.** RabbitMQ cancellation stops future dispatches but leaves in-flight deliveries outstanding. AWS Batch's `CancelJob` may succeed as an API call without cancelling a job already starting/running; a different termination operation is needed. [RabbitMQ 4.1 consumer cancellation](https://www.rabbitmq.com/docs/4.1/consumers#cancelling-a-consumer-unsubscribing), [AWS CancelJob](https://docs.aws.amazon.com/batch/latest/APIReference/API_CancelJob.html) | Stopping the caller or receiving an acknowledgement does not erase work already accepted. An explicit ledger of submitted, outstanding and completed actions is broadly useful for agents. | These systems offer cancellation/recovery semantics. Lightlag's absence of a voluntary cancellation tool is a stronger, task-specific restriction, not a universal property of queues. |

There is also a genuine short-delay teleoperation analogue: NASA's 2024 lunar
terrain-vehicle study tested human operators under 0/4-second and 6/8-second
delays. All navigated the test scenarios; latency reduced speed and increased
workload. The later study also changed training and added aids, so it is not a
clean single-factor delay curve. It supports studying delay and helpful
interfaces, not asserting that delay necessarily makes a competent controller
fail. [NASA technical memorandum 20240001217](https://ntrs.nasa.gov/citations/20240001217)

Two contemporary counterexamples should shape the pitch. NASA reports that
Claude models helped generate waypoint routes for two December 2025 drives;
engineers checked the commands in a digital twin before uplink. That was a
validated planning workflow, not this benchmark's per-call control loop.
[NASA, 30 January 2026](https://www.nasa.gov/missions/mars-2020-perseverance/perseverance-rover/nasas-perseverance-rover-completes-first-ai-planned-drive-on-mars/)
JPL also reports regular operational use of onboard global localization in
February 2026, reducing reliance on Earth to correct accumulated position
uncertainty. [JPL, 18 February 2026](https://www.jpl.nasa.gov/news/nasas-perseverance-now-autonomously-pinpoints-its-location-on-mars/)
Our inference is that useful AI deployment combines reasoning with estimation,
automation and validation. An agent that constructs that combination has solved
our task legitimately.

## Useful abstraction or artificial trap?

**The energy accounting is useful; its current narrative needs correction.** In
the frozen simulator, idle drain occurs on every tick, including at base, and
the evaluator always reaches the common horizon. For a trajectory that remains
alive, with `H = 50`, initial energy 100 and idle cost 0.5:

```text
terminal energy = 100 − 50 × 0.5 − actual drive costs − actual sample costs
                = 75 − actual drive costs − actual sample costs
```

This follows directly from [`Config`](../../lightlag/model.py) and
[`Environment._step`](../../lightlag/environment.py); the dynamic profiles
inherit those costs. **Waiting does not add more total idle energy than another
surviving 50-tick trajectory.** It consumes deadline slack and action
opportunities. Delays can indirectly cause extra driving or failed samples,
but that is a different effect. The old intuition “waiting costs battery, so
move-and-wait must lose” is incomplete for this fixed-horizon implementation.

At tick 25, the first failed rover was already at base with 11.521 energy, but
the remaining idle obligation alone was 12.5. This is a transparent reserve
calculation, not evidence of a new difficult control phenomenon. The rule is
published, so the failure is valid under the task contract. Nevertheless, a
judge could reasonably ask why a home rover cannot shut down or recharge.
Perseverance's actual MMRTG supplies ongoing electricity and charges batteries;
its power system is not our one-use energy tank.
[JPL mission power specification](https://www.jpl.nasa.gov/news/press_kits/mars_2020/landing/mission/spacecraft/power/)

Four other design limits matter:

- **Irreversibility is bounded in real systems.** Physical execution and spent
  energy cannot be undone. Our API also makes all voluntarily queued future
  commands uncancellable, apart from automatic safety stops. Those are different
  restrictions. Explain which one a demonstration tests; do not call every
  future queue entry physically irreversible.
- **Deadlines are generated mission values.** They can stand for observation
  windows or changing priorities, but the current generator does not derive
  them from illumination, orbital geometry or physical sample degradation. A
  rock does not lose three quarters of its scientific value because an arbitrary
  tick passes. Call them synthetic science windows.
- **The reward cliff is a preference, not a conservation law.** Zeroing all
  sampled value when the rover dies encodes strong survival priority. It is
  defensible for this benchmark, but it does not establish that all prior real
  science would be lost. Report collected value, timely value, survival and base
  status alongside the scalar. Do not quietly soften the reward after failures;
  any alternative reward requires its own version and comparison.
- **Noise is not automatically meaningful difficulty.** The noisy profile has
  three model wins/deficits mixed across seeds, and the frozen reference is
  imperfect. More heading noise can make estimation harder, make targets
  unreachable in time, or merely increase variance. Those explanations require
  different controls. A lower score is insufficient to choose between them.

A truthful description would be: **“Lightlag is a compact remote-operations
simulation. Agents can write code, but their commands arrive later and their
observations describe the past. We test whether their plans preserve a finite
energy budget and still exploit time-limited opportunities. The simulator is
stylized; every scored action is replayable.”** Add the actual mixed results,
rather than claiming universal failure or flight-system realism.

## The strongest argument against continuing

We may have built an elaborate demonstration of a small bookkeeping omission.
The initial map and two dynamic pilots were solved. In the next eight attempts,
five match or beat the reference and two of the three deficits collapse to zero
through a published terminal-energy rule. A competent coding agent can reserve
25 energy at the start and track accepted commands. If a clear ledger or a short
invariant reminder makes the failures disappear, the broad story becomes
“an agent occasionally omitted a constraint in one interface,” not “frontier
agents cannot operate delayed systems.” Adding noise, a faster clock or
favorable seeds after that would risk preserving a desired headline rather than
finding a useful learning problem.

This objection is serious but not yet decisive. Constraint omissions can matter
operationally, and a deterministic environment that identifies them and measures
their repair can be valuable. The question is whether the remaining deficiency
is reproducible and whether the team can explain what can be learned. Repeated
failures on failure-selected cases establish conditional repeatability, not a
population failure rate. Repeated recoveries must remain in the account.

## Real time: a separate question, not a difficulty upgrade

Manh's [clock and latency-aware controller](../lightlag-dynamic-pilot.md#real-time-clock-thinking-costs-ticks)
are proposals. They change the object being evaluated from decisions under
known simulated delay to an entire deployed system under provider, network,
harness and local-compute latency. Neither object is inherently wrong; they
answer different questions.

RealtimeBench explicitly studies this distinction: its paused/live comparison
changes model ordering, and its limitations say actors receive structured state
rather than raw perception. Its response-time appendix shows very different
latency profiles across systems. This is prior art for a systems benchmark, not
evidence that our chosen tick rate is operationally meaningful.
[Pan et al., 14 October 2026, §§3.4, limitations, Appendix B.2](https://arxiv.org/html/2610.20665v1)
“Late but Valuable” likewise separates evidence-onset and request-dispatch clocks
and scores the action that actually executes, including the fallback. Its
synthetic, primarily single-decision experiments do not validate Lightlag's
clock. [Barazandeh et al., 9 November 2026, §§2, 5, 10](https://arxiv.org/html/2611.11910v1)

**Do not adopt real time for the main comparison now.** Choosing 3.5–5 seconds
per tick because it lies near observed model pauses tunes the task to a provider
latency distribution. An instant Python reference then has an architectural
advantage unrelated to stale-state reasoning. Artificially charging that
reference the same fixed delay is useful sensitivity analysis, but does not
recreate the model's variable latency, batching or observations during inference.

If the team later studies real time, it needs a separately declared deployment
question, clock scale and fallback; paused results alongside it; complete
observation/request/response/action timestamps; repeated collection windows;
and results over several tick rates rather than one chosen crossover point.
Allow an agent-generated fast executor and an adequately provisioned local
reference. Distinguish policy error, late good decisions and provider failure.
The existing audit would also need the clock-record replay support documented
in Manh's handoff. This is substantial new evaluation scope.

The optional Mars slip-stop and relay-pass sandbox deserves the same discipline.
Both have plausible operational analogues, but the reported keep rule preserves
controller score and its gap over shortcuts. That is an engineering regression
criterion, not evidence of physical calibration or frontier-agent difficulty.
The seed finder selects against scripted policies, not actual model outcomes;
its selected cases can be labelled stress tests, never substituted silently for
the original sample. None of these proposals is adopted by this review.

## Fit to the challenge and what is still unverified

The rubric below comes from the team's saved
[organizer text](../../afterquery-brainstorm.md#the-challenge-original-text),
not a fresh authenticated read. An attempt to open the
[official challenge URL](https://hackjunction.app/participate/45/challenges/328)
with the web tool failed, and public search did not recover its current text.
The later Harbor/reward/run-log requirements come from the team's direct record
of [Ved's 01:35 announcement](../afterquery-update-2026-11-14.md). That announcement
also supersedes the earlier inference-credit promise. A minimum of one logged
model run does not imply the earlier three-run judging process was cancelled.

| Saved criterion | Current fit | Morning evidence needed |
|---|---|---|
| Gap, 30 points | Measured mean gap with three auditable deficits, but three wins/two ties and no repeated attempts in the frozen set. | Present all repeats and the matched reference. Establish which frozen task the judges will actually rerun. |
| Meaningful difficulty, 30 points | Public rules and code access; concrete energy and queue mistakes. The terminal-base story and possible interface dependence are vulnerabilities. | Show the packet, outstanding commitment and reserve at the decisive action; try to erase the failure with better bookkeeping support. |
| Reward integrity, 25 points | Protected state, common terminal horizon, no-op zero and exact replay are strong foundations. | Demonstrate the prescribed stop-early behavior, preserve outstanding work, and inspect plausible alternate strategies rather than only parser attacks. Explain the survival cliff. |
| Craft, 15 points | Executable Harbor path and replay artifacts already exist. Canonical task versus experimental profile remains unresolved. | One final version, one documented rerun path, its source/task hashes, and a concise playthrough that links the complete mixed comparison. |

Upstream Harbor documentation currently confirms numeric reward files, with
JSON preferred if both formats exist. It does not set Junction's scoring rules;
the team's recorded challenge-specific single-number `reward.txt` requirement
should control the package. [Harbor verifier documentation, accessed 14 November](https://docs.harborframework.com/tasks/verifier)
The public Junction site currently lists final submission at **10:00 Sunday
15 November**, but labels its schedule preliminary. It also states that partner
tracks use their own criteria. [Junction public schedule and judging](https://2026.hackjunction.com/)

Still unresolved here: later logged-in announcements; the exact judging model,
effort, time/token budget and harness configuration; final task-selection and
prize-entry details. Neither this review nor an upstream framework page fills
those gaps. Rechecking them is a high-priority morning task.

## Decision matrix

These are qualitative judgments based on delivered assets and remaining work,
not predicted scores or measured development-time estimates.

| Option | What supports it now | Principal risk | Remaining work and recommendation |
|---|---|---|---|
| **A. Continue frozen Lightlag with an honest narrower claim** | Actual model/reference runs, exact audits, container path, controls and viewer. | Repeats or a basic scaffold may erase the apparent gap; literal Mars framing overstates fidelity. | Lowest new scope. **Keep as the candidate and evidence anchor** while testing the claim. |
| **B. Keep dynamics/reward, add a separately versioned public ledger or explicit invariant prompt** | Targets the two observed mechanisms using only already available information. Can reuse all infrastructure. | May reveal that the task largely measures avoidable interface/bookkeeping friction. | Small, reversible diagnostic. **Best next experiment after existing repeats/reference work**, with a fixed new protocol and all outcomes retained. |
| **C. Change the task to grounded supervisory operations**: e.g. explicit sleep/dock semantics or a narrow onboard safety helper | Better correspondence to real systems and potentially clearer decisions about allocation versus local control. | Changes the task that produced the failures, requires reference/control updates and fresh model evidence, and may eliminate the gap. | Medium-to-high scope. Consider only after B and a team rules decision; never combine several mechanics in one unexplained jump. |
| **D. Adopt a real-time clock or harder noise/relay/slip settings** | Code and scripted pilot studies exist as proposals. | Introduces latency/variance/selection effects before the present mechanism is established; current evidence does not predict a model deficit. | High evaluation cost relative to information gained. **Defer for the submission candidate.** |
| **E. Switch to saved Bazaar concept, under a new name** | Numeric-only bargaining has a small discrete simulator and an understandable surplus objective; a first-pilot spec is already written. | No team implementation or frontier result; requires a causal reference, grading, task package, repeatability and a new demo. Existing negotiation results cut both ways. | **Conditional fallback only.** A bounded pilot is feasible; a competitive replacement is unproven. Do not discard delivered Lightlag assets first. |

### Why Bazaar is a hedge, not a rescue guarantee

The saved [Bazaar pilot](../../afterquery-brainstorm.md#bazaar-deep-dive) starts
with one item and three merchants. That is a narrower fallback than constructing
a credible chemical plant or live incident stack. Reuse the Harbor boundary,
not Lightlag's claimed model results. Use numeric bids and a documented finite
merchant family, retain every completed purchase in an evaluator-owned ledger,
and compare a public-information inference policy with simple accept-first and
concession policies. Do not give the reference hidden reservation prices.
Finite types would also make the reference's belief state inspectable; the
saved suggestion that two or three asks reveal several continuous hidden
parameters has not been established.

Freshly opened primary sources weaken any claim that negotiation is a sure gap.
PrefBench's May 2026 result uses zero-shot, structured-state seller policies;
its discussion explicitly leaves tool-augmented and session-based agents for
future evaluation. It therefore does not establish failure by our full coding
agent. [PrefBench, §§5–8](https://arxiv.org/html/2605.22855v1)
The author-maintained BAZAAR repository already uses that name and shows several
LLMs above its enhanced Bayesian baseline in a different double-auction setup.
[BAZAAR methods and leaderboard](https://github.com/lechmazur/bazaar)

Our practical fallback gate should be a fixed, small pilot on preselected cases
with unrestricted code, a demonstrated same-information reference and a clear
failure trace. If an agent writes the inference policy and closes the gap,
record that and stop; tightening patience solely to reverse the result repeats
the problem we are trying to avoid. This review does not authorize or initiate
that build.

## Keep, narrow or stop conditions

No new numeric gate is retroactively imposed on the overnight block. The team
should interpret its full outcome, then declare the next gate before further
model results.

- **Keep pursuing Lightlag** if the repeats expose a recurring, available-
  information decision error; a capable reference handles the same cases; and
  the task remains valuable when explained without a Mars-realism or universal
  reasoning claim. A clear correction should recover useful reward in a replay
  or fresh intervention, with causal claims limited to what was tested.
- **Narrow the claim** if a public ledger removes battery/queue failures. Then
  the result is an interface/scaffold intervention or controller-construction
  test. Preserve the successful intervention; do not remove it to retain a gap.
- **Stop seeking a gap in this version** if capable fresh agent runs reliably
  match the best feasible reference under the clear interface, or if the only
  remaining deficit requires implausible timing or arbitrary withheld tools.
  It can remain a useful simulator and negative result while the team decides
  whether another task is worth the remaining effort.
- **Reject a final benchmark claim** if it requires presenting selected seeds
  as representative, replacing the earlier reference without disclosure,
  omitting recoveries, or treating reference-relative audit losses as optimal
  causal regret. Those are evidence failures, not reasons to tune a simulator.

## Ranked morning plan

1. **Read the overnight results and recheck the live challenge requirements.**
   Combine all original and repeat scores with their costs and exceptions;
   keep failure-selected repeats distinct. Confirm the judging configuration
   and final submission requirements before choosing additional experiments.
2. **Decide what claim the existing evidence can sustain.** Start from energy
   commitments and queue timing. Review the stronger-reference study without
   rewriting the frozen table. Choose one candidate profile explicitly; a
   mixture of unrelated experimental features is not a final task.
3. **Try the smallest intervention that could disprove the story.** Version an
   instruction-only energy invariant first, or a public ledger if that is the
   chosen hypothesis. It should show the last packet's state time, accepted
   command execution slots and remaining idle obligation. Derived drive costs
   or predictions must be labelled estimates/bounds, never hidden simulator
   truth. Run a small fixed diagnostic budget only after its protocol is saved.
4. **Make the demo explain one decision and its repair.** Show the actual
   observation, queue, energy-to-horizon obligation and terminal outcome. Label
   counterfactual continuations. Keep a visible link to all wins, ties and
   deficits. Include a successful agent run to demonstrate that the task is
   solvable with the permitted tools.
5. **Freeze and rehearse the final package.** Coordinate the canonical Harbor
   task with its owner, retain source hashes, run the reference/model/baseline
   commands that judges will use, and check the verifier on stop/no-op cases.
   Confirm repository/submission/license details already flagged in readiness.
6. **Use the fallback only after a conscious stop decision.** If Lightlag no
   longer supports a competitive claim, timebox the saved bargaining pilot
   before building a presentation. BatchPilot/Brewmaster would require new
   physics validation; ColdChain still needs evidence beyond a route solver;
   RecoveryRoom still needs its own effect invariants. None is an already
   demonstrated escape from the current uncertainty.

The minimum reversible work is a claim correction, a documented energy
invariant and a predeclared aid comparison. None requires changing the simulator,
spending on training or adopting the optional real-time/Mars proposals.

## Source and review limitations

All linked external sources used for substantive claims above were opened in
this review on 14 November 2026. NASA/ESA and WHOI are operational/specification
sources; the two latency papers and PrefBench are author preprints; BAZAAR is an
author repository. They establish relevant mechanisms and counterexamples, not
Lightlag's external validity or future model scores. Public-source access does
not constitute authenticated verification of current event rules.

The full text of a newly found October 2026 Science Robotics OnBoard Planner
article was inaccessible (publisher 403), so its reported effect size is not
used. The accessible JPL project page and 2020 engineering paper support the
planning/energy claims instead. No conclusions rely only on search snippets.

Local evidence reviewed: `AGENTS.md`, `TEAM_STATUS.md`, the team-workflow skill,
overnight protocol, fixed comparison, readiness and organizer-update notes,
saved shortlist/round-two ideas and relevant deep dives, earlier research,
dynamic-pilot/controller notes, public task instructions, and the core energy,
queue and mission-generator implementation. The current working tree was clean
when inspected before this document was added. This reviewer did not rerun the
model/reference experiments or independently reproduce every local reported
number. Git integration, claim updates and final morning synthesis belong to
the root overnight task.
