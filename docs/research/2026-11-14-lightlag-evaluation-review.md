# Lightlag: an independent evaluation review

14 November 2026. Research and experiment recommendations by Codex; final project
and rule choices remain with the team. This review uses the **eight frozen
seed-501–504 attempts**, their published audits, the simulator and agent-facing
contract. The overnight repeats were still a separate prospective experiment
when this review was prepared; no conclusions below depend on their outcomes.
No inference calls, simulator changes or new controller experiments were made
for this review. External sources were opened independently on this date.

**Recommendation: continue Lightlag as a compact diagnostic environment, but
try to remove its current gap before adding difficulty.** Finish the declared
failure repeats, compare the stronger causal references separately, and test an
explicit energy/command ledger with the same capable coding agent. The present
result supports an avoidable terminal-constraint failure in some runs of one
agent system. It does not yet establish a broad inability to handle delay,
noise, control, or long horizons. A gap that survives a useful procedural aid
and fresh instances would make a stronger submission than a larger collection
of mechanics.

**What the present numbers measure.** The evaluated system is OpenCode 1.19.5
with the reported `anthropic/claude-opus-5-5` model, the frozen prompt/tools,
a 1,800-second agent limit, and a turn-based simulation. It is compared against
one specialized, causal KF + MPC policy. Code generation is allowed and was
already used successfully. There are four map seeds, each evaluated once in
each of two profiles; these are eight cells, not eight unrelated worlds or
repeated trials of each condition. Source/task hashes, matched Harbor/direct
references, retained trajectories and exact replay are substantial strengths.
[Protocol and complete results](../lightlag-fixed-seed-comparison.md)

The following decomposition was recomputed from `raw_score / maximum` in the
[saved summary](../lightlag-runs/fixed-seeds501-504-summary.json), rather than
rounded reward strings. Positive differences favor the reference.

| Quantity | Observed value | What it changes |
|---|---:|---|
| Claude mean / reference mean, all eight cells | 0.549439 / 0.707452 | The reference has the higher mean on this set. |
| Mean reference minus Claude | +0.158013 | This is a score difference, not a failure probability. |
| Claude wins / ties / deficits | 3 / 2 / 3 | There is no consistent per-instance reference dominance. |
| Median paired difference | 0 | A typical paired difference and the mean tell different stories here. |
| Contribution of the two deaths to the eight-cell mean difference | +0.191667 | Catastrophic outcomes account for more than the entire net mean deficit. |
| Contribution of the other six cells to that same mean | −0.033654 | The other cells offset part of the reference advantage. |
| Mean difference within those six surviving model runs | −0.044872 | Descriptive decomposition only; excluding deaths from the headline would be outcome selection. |

This is a potentially useful **tail-failure result**: competent planning can
coexist with occasional loss of all reward. It is weaker evidence for generally
poor routing or state estimation. The two seed-500 pilots scored 1.0, and the
new set includes three model wins. Those results belong in the demonstration
alongside the failures. A score below 1.0 is not automatically an error: the
denominator is all generated science value, not a proved attainable optimum.
Neither the reference's 0.615–0.833 range nor a model's imperfect score establishes
how much value was causally attainable on every map.

**The energy mechanism is simpler than a generic control problem.** From the
[public configuration](../../lightlag/model.py) and
[`Environment._step`](../../lightlag/environment.py), every trajectory that
survives to the 50-tick horizon pays exactly `50 × 0.5 = 25` idle energy,
irrespective of when it arrives home. For a surviving episode,

```text
terminal battery = 100 − 25 − total executed drive/sample expenditure
```

Thus the action expenditure must stay below 75, with a numerical/safety margin.
Failed samples also spend energy. Driving cost depends on wheel metres and
terrain; delayed information and uncertain motion still complicate a return
estimate, but the 25-unit background reserve is fixed. Returning earlier does
not reduce it. Empty-queue waiting loses deadline opportunities, not additional
total idle energy relative to another trajectory that survives the same horizon.

The [agent instruction](../../harbor/lightlag/instruction.md) already says that
stopping early leaves the battery draining. This is evidence against calling
the two deaths an undisclosed-rule trick. It is also a reason to test whether
an explicit budget invariant removes them. “Follow the available rule reliably”
is a meaningful capability; demonstrating a delay-specific limitation requires
more than observing this accounting failure. Also, `rush` has per-drive slip
noise even without the extra sensing noise and heading drift of `rush_noisy`.
The latter profile changes several effects together. Its mixed results do not
isolate the causal effect of observation noise.

**Three competing explanations to keep alive.** These can coexist; the question
is which one accounts for the useful part of the gap.

| Explanation | Prediction that would support it | Observation that would weaken it |
|---|---|---|
| **Procedural constraint tracking is the main weakness.** The agent plans well but sometimes fails to preserve terminal energy or the command timeline. | The same public rules expressed as a persistent budget/acknowledgement checklist remove deaths and queue gaps, without changing physics or giving a route. | Comparable losses persist after the agent correctly maintains those records. |
| **Delayed commitment under uncertainty is the main weakness.** Known pending actions, uncertain motion and new opportunities create planning errors beyond bookkeeping. | A ledger-equipped agent still commits to avoidably poor actions; a separately matched delay-zero condition reduces its reference-relative deficit. | Remaining differences disappear with a rule reminder, or are equally common without delay. |
| **Small-sample variation plus an imperfect reference explains most of the apparent gap.** | Failure-selected repeats are mixed, fresh maps often favor Claude, and rankings depend strongly on the chosen causal reference. | Similar material deficits recur on multiple fresh maps with a frozen competent agent and more than one credible reference. |

**Why more identical runs are not the whole answer.** *On Randomness in Agentic
Evals*, v3, 25 March 2026, evaluates Qwen3-32B, DeepSWE-preview and
Devstral-2-123B with nano-agent and R2E-Gym, two sampling settings and ten runs
per task on 500 SWE-bench Verified tasks. Its reported single-run score ranges
span 2.2–6.0 percentage points; variability remains at temperature zero. These
are coding agents, not our Claude rover system, so the numerical variance must
not be imported. The relevant lesson is that a deterministic simulator does
not make the complete agent deterministic.
[Paper, §§2.1–2.4 and Appendix C](https://arxiv.org/html/2602.07150v3)

The September 2026 *Agent Evaluation Reliability* preprint makes a separate
point: reliability depends on whether the object being ranked is a fixed
model–scaffold system or the underlying model averaged over scaffolds. It
analyses sparse leaderboard data, including 29,923 HAL rollouts across 54
models and 13 scaffolds; its estimated reliability ranges and task-scaling
ceilings are conditional on that coverage and competitor pool. This is not a
randomized intervention on Lightlag. It does explain why additional maps using
only OpenCode cannot establish a model-only limitation.
[Paper, §§4–5 and limitations](https://arxiv.org/html/2610.00651v1)

For the hackathon, a precise fixed-system claim is sufficient: name the model,
harness, prompt and budgets. A second model or scaffold is valuable if available,
but is not required to report a truthful result about the system already run.
The saved configuration pins OpenCode and the requested model identifier; it
does not itself specify an explicit temperature or reasoning-effort override.
Retain resolved provider settings when available and label missing details as
defaults or unrecorded. Do not infer them from a model's marketing name.

**Failure selection changes the estimand, not the value of the experiment.**
The nine declared overnight trials are a sensible diagnostic: three new
attempts on each previously failing cell. They estimate repeatability on those
three selected cases. The triggering failures must remain separate from the
new repetitions when estimating a case's repeat rate; pooling the selected
original failures with the repeats as if all were an unbiased sample would
inflate that estimate. The combined set cannot estimate failure prevalence
across the generator.

Dwork and colleagues' NIPS 2015 paper formalizes how adapting hypotheses to
holdout feedback can invalidate ordinary generalization arguments. Its
privacy-based reusable-holdout construction is unnecessary for this weekend;
the applicable practical response is to reserve fresh instances after changing
the task, prompt, reference or selection rule.
[Primary paper, §§1–2](https://proceedings.neurips.cc/paper_files/paper/2015/file/bad5f33780c42f2588878a9d07405083-Paper.pdf)

The original eight-cell comparison remains a legitimate predeclared historical
comparison. Using its traces to design a new prompt makes those cells
development evidence for **that new prompt**; it does not erase the original
protocol. Label datasets by their role: pilot, original fixed comparison,
failure-selected repeats, intervention diagnostics, and fresh confirmation.
Do not merge their means. Three repeats also cannot justify a low failure-rate
guarantee: under independent identical Bernoulli trials, zero failures in three
attempts still has a one-sided 95% upper bound of about 63% for that fixed case.
Counts are more informative than an impressive-looking reliability percentage
at this budget.

**What the audit establishes—and what it does not.** The published audits
reconstruct all eight trajectories exactly and report no infrastructure
findings. They locate public information and feasible reference continuations.
This removes several common explanations for low scores. It does not prove
that the simulator is physically realistic, that the written contract is the
right objective, or that an auditor tag reveals the model's internal reason.
[Audit method](../lightlag-audit.md)

The quantity `V(k) − V(k+1)` is a **reference-dependent value decomposition**.
Its terms telescope to the total reference gap by construction. A large term
means the chosen reference's continuation value changed greatly across the
agent action; it does not prove the action made failure inevitable, identify
the unique root cause, or measure regret against an optimal policy. Negative
terms matter. Changing the continuation policy can move the attribution even
when the saved trajectory stays identical.

Seed 501 illustrates this distinction well: the d1 detour receives the large
reference-relative loss, yet the saved salvage check still recovers positive
reward by remaining away from base after that call. A later homeward commitment
removes that salvage option. Seed 504's “stop adding commands after call 20”
counterfactual is more direct: it is a fully specified alternative continuation
that preserves 0.6 reward. Show both the alternative action and its remaining
policy; avoid implying that a highlighted first error alone proves causal
irreversibility. These counterfactuals establish avoidability under the
simulator, not that a fresh language-model rollout would choose the repair.
[Original analysis and linked checks](../lightlag-fixed-seed-comparison.md)

The November 5, 2026 *Benchmarks as Software* preprint independently audits
Terminal-Bench 2.0 and releases 28 repaired tasks in 2.1. Its GPT-5.4
Codex/Terminus-2 comparison uses `xhigh` reasoning in both harnesses; a timeout
sweep up to 32× largely closes the roughly 20-point default-budget gap.
This demonstrates a possible measurement confound, not an explanation of our
eight completed runs. Lightlag's recorded absence of timeouts and turn-based
clock makes that particular explanation less plausible here. Keep versioned
task artifacts and verify the specification as well as replay consistency.
[Paper, §§5–6 and Appendix B](https://arxiv.org/html/2611.08417v1)

**Capable baselines should explain the gap.** Preserve the original KF + MPC
scores and audit labels. Run a preselected newer causal reference as a separate
comparison, with its own development provenance. Selecting whichever policy
wins each seed after inspection is a hindsight portfolio, not one deployable
reference. The existing KF controller was tuned on development seeds and
implements prediction, uncertainty margins and route search; beating an
untuned blind or whole-leg-waiting policy does not establish that all those
components are necessary. [Reference implementation](../../lightlag_dynamic/kf_mpc.py)

The most informative additional baseline may be a much simpler
**queue-aware, energy-safe policy**, not a more elaborate filter. It should
reserve full-horizon energy, account for acknowledged commands, take feasible
known targets and return conservatively through the public tools. If it closes
most of the gap, the task diagnoses maintaining invariants more than advanced
estimation. If it loses substantially while KF + MPC succeeds, that supports
the value of predictive control. This is a proposed baseline, not an
implementation or result.

The 2022 *safe-control-gym* paper supplies a useful methodological precedent:
it exposes symbolic dynamics and constraints, supports disturbances, and
compares classical control, learning-based control, RL and safety certification
on shared cart-pole/quadrotor tasks. It reports control performance, learning
data and constraint violations separately. These are neither LLM evaluations
nor validated rover dynamics. Our application is to separate science value,
survival, estimation quality and computation, while allowing algorithms that
use the disclosed model.
[Paper, §§III–V](https://arxiv.org/html/2109.06325v4) ·
[Official repository, inspected 14 November 2026](https://github.com/learnsyslab/safe-control-gym)

Counterevidence to a broad “models cannot control” claim remains strong.
CoDyControlBench's August 7, 2026 preprint reports **94.8% ± 0.8%** controller
design success for GPT-5.5 with high reasoning across 132 configurations. That
is mean ± SD over three runs under **Fixed-3**, which selects the best
successful controller from three feedback-guided attempts. The supplied
template/equations and success criterion—including up to 100% overshoot—matter.
It is controller synthesis, not online rover operation. Nonetheless, an agent
writing and executing a conventional controller is a legitimate route to
success and must remain available here.
[Paper, §§II-B–D and Table I](https://arxiv.org/html/2608.07004v1)

**What is distinctive, and what is established prior art.** Constant-delay
decision processes, action-history augmentation and model-based prediction
are old research topics. Walsh et al.'s journal paper appeared in 2009
(online July 4, 2008), explicitly motivates delayed feedback with Mars rovers,
compares acting through delay with waiting, and studies model-based simulation.
Its general hardness result coexists with positive results for constrained or
deterministic cases. That theorem does not establish hardness of our small
mission.
[Primary paper, §§1–4](https://thomasjwalsh.net/pub/jaamas09Delayed.pdf)

Gaia2, arXiv v1 of February 12, 2026, presented at
[ICLR 2026](https://iclr.cc/media/iclr-2026/Slides/10011092_UgAc1Rr.pdf), already evaluates
asynchronous event-driven environments with temporal constraints and
write-action verification. Its ReAct evaluation uses older models than our
current system. Removing generation latency raises GPT-5 (high)'s Time result
from 0.0% to 34.4%; a separate parallel-tool-call ablation yields much smaller,
mixed changes. These are different interventions. The result supports
distinguishing planning from service latency; it does not predict an Opus 5.5
score. Lightlag's frozen clock advances only through `advance`, so its current
experiment does not measure responsiveness to events during model deliberation.
[Paper, §§3, 5.2 and Appendix B.3](https://arxiv.org/html/2602.11964v1)

The credible contribution is therefore the **particular small combination**:
continuous position, delayed observations and command commitments, a terminal
resource contract, evolving science opportunities, public-tool references,
protected outcome scoring and inspectable counterfactuals. Present that as an
engineering benchmark and a measured case study. Avoid claims of the first
dynamic/asynchronous agent benchmark, novel delayed-control theory, proven
real-Mars autonomy, or an intrinsic model-level planning barrier. A real-time
variant would be a new experiment with a different construct and compute
fairness requirements, not a stronger rerun of the frozen task.

**Meaningful and learnable are separate tests.** A terminal resource constraint
can be meaningful even when one arithmetic oversight causes a discontinuous
score. The team should explain why rover survival is the mission contract,
especially why dying at base erases collected value. Correct implementation
does not itself justify that choice physically. Keep the present reward for
comparability and show collected science, on-time science, alive/home status,
remaining battery and final reward separately. Do not silently replace the
primary score with a smoother one after seeing deaths.

*Towards a Science of AI Agent Reliability*, v3 of June 2, 2026 (ICML 2026),
separates consistency, robustness, predictability and safety, and keeps safety
outside its overall reliability average to avoid hiding tail risk. Its study
uses 15 models, two benchmarks and five runs per task; reasoning models retain
provider sampling defaults. The paper itself notes limited scaffold diversity
and LLM-based safety judging. Borrow the separation of failure frequency and
severity, not its model rankings or an assumed universal reliability plateau.
[Paper, §§3.4–4.1 and limitations](https://arxiv.org/html/2602.16666v3)

A hand-engineered controller proves useful solvability; it does not prove
sample-efficient learnability for a small model. Liotet et al.'s ICML 2022 DIDA
work learns delayed policies from an efficient **undelayed** expert and analyses
smoothness conditions. It motivates imitation as one possible future route,
but neither the privileged training access nor its guarantees transfer
automatically to Lightlag's hard deadlines and zero-survival multiplier.
[Primary paper, §§3, 5–7](https://proceedings.mlr.press/v162/liotet22a/liotet22a.pdf)

A cheap first learning signal is whether a general procedural explanation
improves fresh attempts and transfers to fresh maps. This would show adaptation
to an operational method, not RL training or successful distillation. If later
training is attempted, separate controller demonstrations and development
seeds from evaluation maps, measure learning curves, and keep the evaluation
reward fixed. Large controller-search campaigns and hypothetical trainability
are not substitutes for those measurements.

**Minimum next tests, in order.** These are proposals, not additional completed
experiments or retrospective preregistration. Publish any selected paid block
before launching it and stay within the overnight spending guard.

| Test | Minimum useful design | Decision it resolves |
|---|---|---|
| Finish conditional repeatability | The already declared three new attempts per failing cell; keep all nine and distinguish original triggers. Report reward and survival separately. | Whether each illustrated failure is reproducible under unchanged conditions. |
| Reference and accounting check | On the unchanged eight cells, compare the frozen reference with the preselected newer causal reference; independently reconcile energy and queue timing in the decisive traces. No model inference required. | Whether the gap or its attribution depends strongly on a weak reference or a bookkeeping error. |
| Rule-equivalent procedural aid | Six new attempts: one unmodified and one aided attempt on each of the three diagnostic cells. Randomize/interleave the pair order before launching. Use one fixed aid for all cells and give no previous transcript or seed-specific route. | A low-cost mechanism screen separating an unaided rollout problem from difficulty that persists with explicit accounting. One pair per case is not a precise treatment-effect estimate. |
| Fresh confirmation, only if still useful | Freeze the chosen task profile, agent condition and reference. Reserve four genuinely unused maps, two fresh attempts per map. If both profiles are part of the final claim, cover both and budget accordingly. | Whether the selected mechanism and a material gap extend beyond the cases that inspired the aid. |

The procedural aid can be short: before each commitment, track the latest
packet's state tick, the current tick, acknowledged execution ticks, commands
not yet observed, terminal idle reserve, committed expenditure, return reserve
and remaining margin. Give the energy identity above as a worked rule
derivation. All values must come from public observations and acknowledgements;
do not inject true current position, actual hidden slip, future discoveries or
the reference's route. Let the agent implement its own ledger. A stronger
automatic safety filter would be a separately labelled agent system.

For the aid screen, score both **survival** and **reference-relative value**.
If it eliminates deaths by abandoning most targets, it has not closed the task
gap. An offline trace checker that flags a bad command also has not demonstrated
online recovery: after blocking it, subsequent model decisions must be generated
afresh, or the complete alternative continuation must be specified.

Recommended development stop rules are deliberately modest:

- If the selected catastrophic outcome does not recur in its three prospective
  repeats, stop describing that case as a demonstrated repeatable catastrophe.
  Retain the original failure and all repetitions; three successes do not prove
  reliability.
- If the ledger aid preserves survival and brings the diagnostic runs close to
  the reference, prioritize confirming that improvement. Do not make the rules
  harder merely to restore a losing model score. The result may become a useful
  story about a repairable failure, with a weaker performance-gap claim.
- For a future confirmation block, a reasonable **engineering** continuation
  gate is a predeclared mean deficit of at least 0.10 reward, supported by
  avoidable deficits on at least two fresh maps. This proposed threshold is
  roughly one low-value science target on these maps, not a statistical significance
  test. If it fails, keep the mixed result and stop selecting more seeds to
  search for a favorable headline. If it passes, still call it a small pilot.
- Claim a delay-specific mechanism only after a matched delay-zero/positive
  experiment with the same agent condition. Compare the change in the agent's
  deficit relative to the reference, since delay can reduce attainable value
  for both. Do not treat a different reference or added real-time clock as that
  ablation.

**Morning direction.** Keep the current implementation stable long enough to
learn from it. Lead the demo with an avoidable commitment and its public
evidence, include the model wins, and say precisely which system was measured.
The strongest next result could be either a surviving deficit or a successful
repair. Both are more informative than adding another source of difficulty
before determining which part of the existing task the agent actually fails.

**Review limits.** This is a targeted primary-source review and code/record
inspection, not an exhaustive literature search or independent re-execution of
all Harbor trials. Arithmetic above was recomputed; exact-replay and no-infra
claims refer to the saved audits. Publication/version dates are separate from
the 14 November access date. None of the cited studies directly evaluates our
frozen Lightlag task or establishes transfer to it. No published numerical
result was used as a prediction of its failure rate.
