# After the survey: which failure should we test next?

Research checked **14 November 2026**, after the six-region study. This is a
primary-source review and a proposed experiment order, not a project decision.
No external benchmark was reproduced, no new environment was implemented and
no paid model call was made. Findings below are source-reported unless labelled
as our own retained evidence or our judgment.

## Decision

**Do not commit to a long campaign yet. Stop enlarging the same routing/inspection
family. First test whether an agent distinguishes bad measurements from changed
dynamics and revises a previously successful controller.** This is our preferred
next hypothesis because it connects a specific failure mechanism to existing
teammate code. The literature does not establish an Opus 5.5 gap on our version.

Keep two alternatives: delayed, irreversible operational consequences; and
reconciliation of several obligations after a partially completed workflow.
Both deserve a compact falsification test before a substantial build. Pure
duration, ordinary memory recall, static parameter fitting and generic retry
handling have important current counterevidence.

Our own evidence matters more than a broad claim that agents struggle to plan.
The information prototypes were solved by the strong model; the survey's
adaptive policy failed its advantage gate; and a Claude-written autopilot tied
the reference in teammates' fresh-map study. These are different results, but
none supports adding more regions as the next major bet.
[Survey handoff](../lightlag-survey-handoff.md), [allocation results](../lightlag-allocation-experiment.md),
[Live results](../lightlag-live.md).

## The user's idea has several distinct meanings

- **Retention:** an earlier fact remains available when it is needed later.
- **Learning from feedback:** a previous outcome changes a reusable decision rule.
- **Delayed causal diagnosis:** the agent connects a later loss to the action
  that caused it, rather than the most recent visible event.
- **Revision:** the agent stops trusting a previously useful rule when evidence
  shows the situation has changed, without treating every noisy reading as change.

Hundreds of turns can contain any of these, or merely repeat an easy operation.
We should specify the dependency and measure its effect. A persistent file is
not evidence that an agent learns; a low final score is not evidence it forgot.

## Evidence closest to the question

### Memory and long horizons: substantial prior art, substantial progress

**Anthropic, 6 November 2026.** On its CL-Bench database task, Opus 5.5's mean
reward rises from **.655 without memory to .838 with persistent memory**. Each
question starts a fresh session with a shared memory directory; the report
describes tested rules and corrections carried forward. This directly weakens
our proposed general repeated-mistake premise. It is one task and a vendor
report, not proof of reliable learning in all environments. Telling older Opus
models to record only failures reduced their memory benefit; that intervention
was not reported as an Opus 5.5 result.
[Official report](https://www.anthropic.com/research/components-of-agent-memory).

**Vending-Bench 2, current author page.** A simulated business runs for a year
with notes, reminders and context trimming. Andon reports sustained tool use
without degradation among leading models. This is strong counterevidence to
duration alone, although profit is not optimality or compliance with every
obligation. The page establishes business tools, not a general shell. Its live
leaderboard changes, so this review does not use it as a permanent ranking.
[Benchmark and system prompt](https://andonlabs.com/evals/vending-bench-2).

**Continual-ARC, v2, 11 November 2026.** Recurring tasks are interleaved with
other work; persistence is compared with the same harness wiped. GPT-6 Luna
at several effort levels did not measurably reduce feedback cost with default
persistence relative to the same harness wiped. Instructions to write, test,
save and reuse programs improved all tested harnesses. This motivates a procedural-memory control. Limits include a fixed
stream seed, no Opus 5.5 result, and a disclosed Python-skill import defect in
one harness. It does not prove that memory-enabled coding agents cannot learn.
[Paper, especially appendices D–F and I](https://arxiv.org/html/2611.14505v2).

**Continual Learning Exam, 25 October 2026.** Seventeen configurations include
full coding harnesses and persistent workspaces. The best system, Claude Code
with Opus 5, completes **47.7% of 600 levels** and all five levels in **23.3% of
120 tasks**.
However, unreached levels count as failed, later assignments have more criteria,
and feedback comes with an extra submission. There is no matched fresh-context
control establishing that these scores measure forgetting or repeated errors.
Useful prior art for dependencies and professional workflows; weak causal
evidence for the exact failure we want.
[Paper, sections 3–4 and appendix F](https://arxiv.org/html/2610.33956v1).

### Experimentation and revising a model: promising, not automatically hard

**DiscoverPhysics, paper 25 May; author results updated 7 November.** Agents
design experiments, inspect trajectories, fit candidates and submit Python laws.
The updated author data report Opus 5.5 **48.6% pass@1 and 72.7% pass@5**.
Crucially, passing requires both trajectory accuracy and an LLM-judged
explanation. This is not a 51.4% rover-control failure rate. The prescribed
experiment/fitting interface is also not an unrestricted coding-agent workspace.
Hidden structure and discriminating experiments are relevant; exotic force laws
are broader than our public rover parameter family.
[Paper](https://arxiv.org/html/2605.26087v1),
[author leaderboard and metric](https://sampsonml.github.io/DiscoverPhysicsLeaderboard/),
[dated result data](https://sampsonml.github.io/DiscoverPhysicsLeaderboard/data/results.json).

**ASPIRE, 9 November 2026.** GPT-6.1 Sol with medium reasoning, coding, numerical
libraries and other tools delivered valid models in **30/30 runs** across three
measured physical systems. This is important counterevidence against ordinary
system identification as our new challenge. The datasets were supplied and
states measured; active collection, hidden-state estimation and unexpected
mid-mission changes were not tested. Validity also does not mean perfect
prediction or truthful documentation. One model and three systems limit scope.
[Paper, sections 4.4, 5.7, 6 and 7.4](https://arxiv.org/html/2611.13114v1).

**CausaLab, 25 May 2026.** GPT-5.2-high reaches **92% prediction accuracy but
.471 graph-edge F1** in an observational six-node setting; mixed evidence gives
**80% accuracy and .80 F1**. A verification step helps a smaller model. The useful
lesson is to test whether chosen experiments distinguish hypotheses. Do not
penalize a useful controller solely because its explanation differs from ours:
prediction and mechanism scores diverge. These are small synthetic graphs and
specified laboratory tools, not a demonstrated unrestricted Opus 5.5 comparison.
[Paper, sections 3 and 5](https://arxiv.org/html/2605.26029v1).

**CoRAL, 4 May 2026.** GPT-4o generates executable objectives and refines
parameters above an MPPI controller. Across six tasks, full-system success is
**50/60**, versus **25/60 without refinement** and **57/60 for the expert
finite-state-machine baseline**.
This shows that a hybrid can learn from physical feedback. It uses a supplied
controller and precise tracking; it does not isolate unexpected changes in our
delayed, noisy observation setting.
[Paper, table I and appendix S3](https://arxiv.org/html/2605.02600v1).

### Delayed effects and recovery: distinguish model errors from impossible contracts

**SIMMER, v2, 9 August 2026; experiments from March.** Symbolic kitchen plans
can satisfy immediate preconditions while producing later contamination or
irreversible damage. This closely matches delayed consequences. But evaluated
headline models include Opus 4.6 and GPT-5.4 generating open-loop plans. It also
reports interactive GPT-5.4 baselines, none equivalent to our current coding
agent. The mitigation comparison also changes GPT reasoning effort and
Claude thinking/sampling settings. Borrow its failure distinction; do not import
its headline failure rate or call the improvement a controlled prompt-only effect.
[Paper, tables 3, 5 and 9](https://arxiv.org/html/2606.14574v2).

**LIMBO, 24 September 2026.** Includes current frontier models and production
MCP harnesses. Where read-back resolves a lost acknowledgement, frontier agents
duplicate effects in only **0.5%** of episodes. Large failures under late commits
and redelivery mostly reflect inadequate contracts; some guarantees are
impossible without additional primitives. This weakens generic timeout/retry
recovery as a pivot. A fair task must supply operation status, stable keys and
repair capabilities when its reference needs them.
[Paper, sections 5–6](https://arxiv.org/html/2609.29095v1).

**UndoBench, 4 October 2026.** Studies composite mutations and recovery stages.
Its hosted-model lost-acknowledgement extension improves conditional recovery
from **33.20% to 97.24%** with universal server-side idempotency. Hosted models
are Gemini 3.8 Flash and GLM-5.2; the primary study uses smaller Llamas and
prescribed retry policies. This motivates testing several interacting obligations,
but does not establish an Opus gap. Missing repair actions must not be mistaken
for reasoning difficulty.
[Paper](https://arxiv.org/html/2610.05622v1).

## Other directions screened

| Direction | Evidence and decision |
|---|---|
| Context compaction | Microsoft's October CompactionBench reports GPT-5.6 Sol accuracy **69.29→77.95%** when the compaction mechanism changes, using eight release transitions across four repositories. Relevant to persistent work, but it changes the harness and uses expensive multi-turn sessions. Poor fit for our remaining pilot budget; do not force context overflow. [Preprint, table 3 and appendix A](https://www.microsoft.com/en-us/research/wp-content/uploads/2026/10/CompactionBench_preprint.pdf) |
| Multi-agent coordination | November 11 MAMUBench work reports coordinator advantages over per-user teams; message-reading barriers rescue failures. Different deployment formations are the intervention. Interesting, but a costly change from our single judged agent and no basis for disabling coordination aids. [Author report](https://alignment.anthropic.com/2026/worse-together/) |
| Irreversible resource investment | AllocBench reports a commitment difference between abstract choices and writing scripts. Its restricted script slots, disabled GPT reasoning and hindsight normalization prevent transferring the gap to unrestricted coding. Keep the operational mechanism, not those restrictions. [July revision](https://arxiv.org/html/2607.23332v2) |
| Generic long-horizon headlines | METR's horizon is human task duration at a given success probability, not how long an agent stays coherent or the number of turns we should impose. [Official methodology](https://metr.org/time-horizons/) |

MemoryArena and MemoryBench were also checked. Their older/smaller model and
task-specific scaffold results are useful for control design, not direct evidence
about our Opus 5.5 coding setup. [MemoryArena](https://arxiv.org/html/2602.16313v2),
[MemoryBench](https://arxiv.org/html/2510.17281v7).

## Proposed experiment order — our judgment, not published results

This ranking combines engineering reuse, identifiable failure mechanisms and
cheap falsification. It is not an estimate of which candidate has the largest
model gap; no reviewed source measures our proposed environment.

| Priority | Candidate | Concrete ability | Main reason to reject it early |
|---|---|---|---|
| 1 | Diagnose stale calibration versus faulty sensing | A previously successful policy becomes unreliable; choose evidence that identifies whether motion or sensing changed, update the correct state and recover | Ordinary residual monitoring, sensor fusion or a generated calibration script may solve it |
| 2 | Consequences that survive later actions | Manage wear, contamination or commitments whose effects surface later; retain the causal state and meet future obligations | A simple explicit state ledger may erase the apparent difficulty |
| 3 | Reconcile a partial workflow | Finish accepted obligations across inventory, fulfillment and settlement after some effects commit and others fail | Correct idempotency/status tools plus a generic recovery program may solve it; rebuilding the domain costs time |
| Park | A very long campaign by itself | Continued coherent operation | Current memory/tool systems already sustain long runs; added inference cost can create a budget failure instead of a capability result |

### Preferred compact test

Keep the existing rover and a short mission. An initial calibration is useful.
Later, a disclosed family permits either changed drive gain/slip or transient
position-sensor corruption. A discrepant fix initially admits both explanations.
Other sensors or a short, informative movement can distinguish them. Include
unchanged and sham-event episodes, and measure false alarms, so always
recalibrating cannot exploit a guaranteed change. The agent must decide whether
to recalibrate, discount the measurement, or gather evidence.

This is a specific extension of Manh's existing work, not an implementation
decision. His current many-sensor variant supports wheel-scale overshoot, and
his controller work records costs after a real slip jump. Those are scripted
controller findings, not measured model failures.
[Biome evidence](../lightlag-biomes.md),
[controller evidence](../../lightlag_dynamic/manh_controllers/README.md).

The public contract must specify possible change families, parameter bounds,
sensor laws and action costs. Hide realized parameters and event draws, not
rules needed to understand the task. Establish that the explanations can be
distinguished through the same delayed public information available to both
reference and agent, with enough remaining resources to recover.

Before model calls, compare a causal adaptive reference, stale calibration and
ordinary fusion. An announced-change diagnostic can show whether detection is
the difficulty; a truth-informed oracle must be separately labelled. A useful
reference must estimate the change rather than read hidden simulator state.

For a later model screen, preserve code, files, logs and adequate deliberation.
Use the strong model, and include an explicit calibration/residual-checking
instruction condition to try to eliminate the gap. The task should reward
science and safe return; repeated avoidable losses after relevant evidence are
diagnostics. Do not grade private reasoning or insist on our preferred algorithm.

### If the specific aim is learning across distant attempts

Use a short sequence such as A–B–A′–B′ before buying a hundred-turn campaign.
First encounters provide usable feedback; returning instances change numbers
but preserve the rule. Add a separately labelled changed-rule case so that
retention and revision are not conflated. Compare ordinary persistence with
explicit tested-program reuse, and use a matched fresh-state control. Optional
diagnostic controls can add a correct event ledger or feedback; these receive
extra help and cannot be presented as the fair competitive reference.

The primary question is whether earlier experience improves later outcome on
fresh instances. Count what the model could know at each decision. An initial
unavoidable error is different from repeating an error after sufficient evidence.
If explicit memory retrieval or a small reusable program closes the gap, retire
the memory mechanism. Length should follow a demonstrated dependency.

## Handoff and decision boundary

### Teammate work that landed during this review

Kristján / Claude Code has now published a [ground-change prototype](../lightlag-shift.md)
(`8fde668`). It guarantees one lasting slip increase in a disclosed time window.
Its forty-seed scripted comparison has no model run and no reference written
specifically to detect the change. It is a useful starting point for the first
hypothesis, not yet the proposed diagnosis test: guaranteed worsening, transient
sensor faults and unchanged/sham cases need to be distinguished. Coordinate with
that owner before extending it; do not start a duplicate environment. The claim
reserves model spending for Kristján's approval.

Kristján / Codex has also published [certified-challenge research](2026-11-14-certified-challenges.md)
(`3df0807`) and claimed a free collection → processing → transmission probe with
shared resources and an exactly checked reference. This gives the delayed
commitment alternative a concrete local test: a pickup is useful only if its
later stages can finish. Let that claimed probe test its planning tradeoff before
building another domain. A winning reference establishes solvability, not a
model gap; generic search and solver-hinted coding remain essential controls.

Neither effort selects the final challenge. The immediate handoff is to compare
these two existing efforts against their rejection criteria, not launch both as
large builds or add more unrelated variants.

### Decision boundary

No proposed candidate is proven hard for our current model. Existing task/demo,
frozen experiments and teammates' work stay intact. The next decision is which
mechanism to test; the preferred diagnosis screen can reuse the most engineering.
A recovery pivot remains a separate small experiment, not a new platform build.

For whichever candidate is selected: publish a new claim and protocol, establish
feasibility with public-only controls, freeze fresh instances and spending limits,
then run a bounded strong-agent pilot. Keep counterexamples and harness failures.
Do not silently weaken tooling, use a weaker model, pick failure seeds or enlarge
the task until the desired score appears. No paid follow-up is launched by this
research task, and historical credit accounting is not a live balance.

This review changes the next experiment recommendation; it does not retroactively
change the previous studies or select the team's final challenge.

Three independent domain reviews checked the synthesis. Corrections distinguish
controlled feedback-cost improvement from generic learning, identify the exact
CLE model and ladder denominator, label CoRAL's expert baseline, retain SIMMER's
interactive baselines and add unchanged/sham cases to the proposed diagnosis
screen. Source distinctions and local document links were verified before push.
