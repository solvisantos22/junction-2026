# AfterQuery: what the research changes for our project

**Decision brief — 13 November 2026.** We reviewed primary papers, author repositories and official evaluation documentation across agent benchmarks, routing, process control and service recovery. This is a focused review, not an exhaustive survey. **No project has been implemented, no candidate has a measured frontier-agent gap, and the team has not selected a direction.** The [three detailed reviews](README.md) contain methods, model versions, results and limitations.

## Our judgment

**Keep ColdChain as the cheapest first experiment; treat BatchPilot as the strongest technical alternative; put RecoveryRoom third unless we find a sharper distinction from existing recovery tasks.** This orders the experiments, not the final project choice. For a convincing demo and a competitive result, the deciding evidence must be an actual fair performance gap, not a paper saying an older agent failed.

The most important finding is counterevidence. Recent models can operate businesses, generate optimization code and synthesize feedback controllers. AutoVend reports one frontier model beating its inventory reference while four others trail it. CoDyControlBench reports strong controller-generation performance under its particular success criteria. “LLMs cannot plan” or “continuous control is hard” would therefore be weak starting claims. [AutoVend](https://arxiv.org/html/2610.36980v2), [CoDyControlBench](https://arxiv.org/html/2608.07004v1)

**Our proposed research question:** can a capable agent preserve important constraints when it must make an irreversible commitment before a later, disclosed type of disruption? A useful result would show the same pattern on fresh instances, with code/solvers allowed, and explain the avoidable loss from the action trace. This is a hypothesis derived from the review, not a claim of a new research field or an established model weakness.

All three themes have substantial prior art. That does not disqualify them from the challenge; it changes what we should claim as our contribution. The literature also cannot tell us how many Junction teams are choosing a theme. Research saturation and local competition are different unknowns.

## Comparing our three options

These are our assessments, not published measurements of our proposed environments.

| Direction | Real problem and plausible mechanism | Why this team could execute it | Smallest convincing demo | Main risk and rejection condition |
|---|---|---|---|---|
| **ColdChain — quickest to falsify** | Deliver perishable goods under capacity and deadline constraints. A locally attractive dispatch can consume the only vehicle/time margin needed after a disruption. | Sölvi and Kristján can build typed tools and an exact small-instance planner; Manh can strengthen the simulation and causal replanning comparison. | Two vehicles, eight deliveries, one public nominal case and one disruption family. Map and timeline show agent/reference dispatches, delivered value and expired goods. | An agent-generated enumerator may solve the small problem. Drop the generic routing version if competent code-assisted replanning consistently matches the reference. |
| **BatchPilot — strongest combined technical fit** | Finish useful batches despite thermal inertia, actuator limits and cumulative quality damage. An acceptable temperature now may hide an already unavoidable future violation. | Manh supplies control/model judgement; Sölvi and Kristján supply the agent harness, verification and visual replay. Math connects all three roles. | One small validated thermal process, three batches, a tuned simple controller and a causal predictive reference. Show temperature, delayed response, quality and completed valid batches. | A contrived plant or weak controller would invalidate the story; a generated controller may close the gap. Drop it if we cannot quickly validate the model/reference or the capable agent reliably matches it. |
| **RecoveryRoom — strongest backend fit, closest overlap** | Restore processing while preserving every accepted job's business effect. Clearing a queue or restarting a service can restore appearances while silently losing or duplicating work. | Sölvi and Kristján know automation, services and data integrity; Manh can contribute state modelling and controlled fault injection. | A bounded simulated worker/queue/store, one interrupted-operation scenario, and an effect ledger showing unique completed jobs alongside service health. | Existing tasks already test recovery, offsets, crashes and duplicates. Drop a broad incident-response dashboard; proceed only with a distinct, feasible recovery invariant and a small auditable environment. |

ColdChain has established dynamic/stochastic routing references, and its eight-delivery core is small enough to enumerate under simple assumptions. BatchPilot overlaps recent process-operation work, including OperAItor; ordinary heating-to-a-target is not a sufficient differentiator. RecoveryRoom overlaps AIOpsLab/ITBench and a particularly close Terminal-Bench payments-recovery task. The [control review](control-and-optimization.md) and [recovery review](reward-and-evaluation.md) explain these comparisons.

A public hackathon repository also describes a multi-truck routing environment with deadlines, roadblocks and fuel. Its README is evidence that the theme exists, **not** evidence of a validated implementation or measured frontier/reference gap. We should not pitch generic dynamic routing as unprecedented. [Prototype README](https://github.com/SANTHSIM22/META_HACKATHON_R1)

## What has worked, and what has failed

The lesson column is our interpretation. Results from different tasks are not a common leaderboard.

| Approach tried in prior work | What the evidence supports | Lesson for us |
|---|---|---|
| **Executable code and feedback** | REPL-Plan improves over a comparison with the same shopping search breadth; generated controllers succeed on many CoDy plants. Broader search and best-of-several trials must be counted explicitly. [Planning/control evidence](control-and-optimization.md) | Compare against the full coding agent. Solving our environment with a script is a valid success. |
| **Better procedures, memory and state visibility** | Project Vend reports useful tool/procedure changes, but model and scaffold changed together; τ²-bench's ablations separate some planning and communication effects. [Benchmark evidence](benchmark-landscape.md) | Supply readable state, documented operations and persistent scratch space. Include a competent-scaffold check before attributing failure to reasoning. |
| **Causal classical references** | Dynamic routing embeds a static solver in repeated dispatch decisions; process control repeatedly optimizes using current state. [Control evidence](control-and-optimization.md) | A specialized algorithm is legitimate. It must not secretly know future disturbances. |
| **Optimizing visible scores or surface appearance** | Reward-hacking studies demonstrate answer leakage, timing manipulation and evaluator attacks under specific research conditions; availability alone also misses business effects. [Reward evidence](reward-and-evaluation.md) | Verify useful outcomes and obligations from authoritative state. A convincing explanation or healthy-service flag is insufficient. |
| **Declaring capability failure from one score** | Terminal-Bench task repairs and budget changes materially change results; old failures do not establish current frontier weakness. [Audit](https://arxiv.org/html/2611.08417v1) | Classify failures: decision, tool/infrastructure, resource limit, invalid task or verifier defect. Preserve all runs and denominators. |
| **Treating substeps as completion** | Workflow benchmarks distinguish partial progress from binary completion, and final-state checks can miss path violations. [Benchmark review](benchmark-landscape.md), [evaluation review](reward-and-evaluation.md) | Show progress diagnostically, but reward completed deliveries, valid batches or reconciled job effects. Preserve irreversible violations. |

The right response to an agent finding a legitimate shortcut is to improve our understanding of the task. It is not to ban arithmetic, hide relevant state or restrict tools until the desired failure appears.

## Additional findings that affect the design

**Latent consequences are interesting; published effect sizes need care.** SIMMER studies symbolic kitchen plans where actions can succeed immediately but create later problems. It motivates separating invalid actions from delayed damage. However, its counterfactual-foresight comparison changes GPT-5.4 reasoning from low to high, and changes Claude's thinking/sampling configuration. Its March 2026 experiments are not a controlled test of today's complete coding agents. We can borrow the diagnostic distinction, not claim a prompt-only causal improvement or a proven BatchPilot gap. [SIMMER, Table 5 and Appendix C.2](https://arxiv.org/html/2606.14574v2)

**A good average can conceal an unreliable policy.** A May 2026 Beer Game study reports good mean performance from some agents compared with student teams, alongside substantial run-to-run variation. Its human comparison is not an expert operations baseline, and repeated trials share the environment. Our implication is to report score distributions and concrete bad outcomes as well as the mean; one attractive rollout is weak evidence. [Supply-chain agent study](https://arxiv.org/html/2605.17036v1)

**Missing procedures can resemble deep planning difficulty.** SupChain-Bench combines supply-chain questions with long tool workflows and reports substantial benefits from SOP guidance. Its tool-retrieval metrics do not establish successful physical execution, and its model roster is older than the current frontier. This supports publishing operational rules clearly and trying a scaffolded baseline. [SupChain-Bench, ACL Findings 2026](https://aclanthology.org/2026.findings-acl.371/)

**An error trace is descriptive until we intervene.** “Locating Hidden Failures” analyses trajectories from mixed, often older coding/science agents, then evaluates selecting among completed attempts. That is not demonstrated online repair. For our own causal claim, replay a matched state with and without the proposed correction and compare downstream outcomes; merely highlighting the first visible mistake is not enough. [Paper, §§2–4](https://arxiv.org/html/2609.17930v1)

**Do not manufacture difficulty with a slow API.** “Late but Valuable” measures real inference latency in synthetic decision tasks; a main analysis replays answers against a tighter deadline than the one used to prompt them. Its local fast-versus-thinking comparison changes sampling and token caps too; load experiments use constructed request bursts. It supports explicitly studying latency, not importing an arbitrary deadline. Start with a paused simulation clock; add real-time pressure only as a separately justified condition with a fallback policy and budget sensitivity analysis. [Paper](https://arxiv.org/html/2611.11910v1)

## The first experiment, once we choose to implement

This is a proposed internal gate, not an organizer requirement or work already performed.

1. **Establish feasibility first.** Hand-check one nominal and one disrupted instance. Run a simple policy and the proposed reference; inspect every transition and demonstrate useful completion. For BatchPilot, validate units, dynamics and integration. For RecoveryRoom, make the destination capable of idempotent or transactional effects: queue acknowledgements alone cannot promise exactly-once business outcomes.
2. **Try hard to erase the gap.** Run the organizer's strongest permitted agent with code, useful errors, persistent state and an explicit invitation to use a solver/controller. Start with three repetitions on each public instance if budget allows. Record model, harness, effort, budgets, prompt and seed. Include a separately labelled run with an algorithm-family hint. This is internal screening, not a requirement for “three runs per seed.”
3. **Diagnose a mechanism.** Compare feedback versus a fixed initial plan; nominal versus disrupted instances; and a trace with versus without a specified correction. Change one factor where practical. Distinguish decisions from unavailable tools, invalid actions, timeouts and reward defects. Do not silently remove infrastructure failures from the report.
4. **Continue only if the result survives.** Agree an operationally meaningful margin in advance—additional valid completed jobs/batches/deliveries, for example—rather than choosing a favorable percentage afterward. If the gap disappears, record it and reshape or drop the candidate. Do not select final test instances because the model already failed them.
5. **Freeze and evaluate.** If the gate passes, freeze the generator, constraints, reward and reference, then use an affordable held-out seed set with repeated agent runs. Keep this optional grid separate from the prescribed reference, three agent runs, do-nothing and stop-early reruns. Save the complete manifest and traces; three runs are not a precise reliability estimate.

For a fast decision, first ask whether **ColdChain survives its obvious solver escape**. If it does not, and Manh can validate the small BatchPilot plant/reference promptly, switch the experiment to BatchPilot. If neither yields a fair, explainable gap, revisit the mechanism before building the presentation. This is a provisional recommendation, not a commitment on the team's behalf.

## Fairness and reward rules to settle before implementation

- **Same causal information:** disclose equations, units, constraints, measured state and disturbance assumptions. Neither competitive policy receives future event seeds. A hindsight optimizer may be shown only as a labelled upper bound.
- **Same operational opportunities:** reference and agent use the same observation/transition APIs, action durations, intervention limits and simulated horizons. A reference cannot take extra actions between the agent's decision points.
- **Separate three roles:** a purpose-built reference chooses actions; an agent chooses actions with its permitted tools; the verifier may inspect protected ground truth. Verifier privilege must not leak into the reference.
- **Explicit time:** simulation advances through defined action durations/events. Model deliberation need not advance it. On stopping or timing out, evaluate outstanding obligations at the same terminal horizon so leaving early cannot erase losses.
- **Actual outcomes:** tie the primary objective to delivered value, valid output or unique business effects. Display costs, violations and partial progress separately. Audit whether deleting backlog, resetting state or fabricating logs improves reward without useful work.
- **Honest compute accounting:** disclose reference development assumptions, solver runtime, agent inference budgets and retries. Allow the agent to write its own policy; we need not hand it a ready-made optimal-policy tool.

These recommendations derive from the review. The [challenge brief](https://hackjunction.app/participate/45/challenges/328) remains authoritative for judging. The [evaluation deep dive](reward-and-evaluation.md) contains exploit probes and recovery semantics.

## How the evidence maps to judging

The [challenge rubric](https://hackjunction.app/participate/45/challenges/328) gives gap 30%, meaningful/fair difficulty 30%, reward integrity 25%, and craft/reproducibility 15%. Our proposed evidence package follows those priorities:

| Criterion | What we would need to show |
|---|---|
| Performance gap | Reference and capable agent on the same instances, complete traces, repeated runs and honest treatment of errors. A literature score is not our result. |
| Meaningful, fair difficulty | A real operational objective and a specific diagnosed failure, surviving fair information, useful tools and sensible budgets. |
| Reward integrity | Outcome-based scoring; do-nothing and stop-early checks; adversarial attempts to delete obligations, fabricate evidence or exploit the verifier. |
| Craft and reproducibility | One documented rerun command, pinned configuration and seeds, and a short replay that explains the decisive event. |

The judging format includes a ten-minute demo, prescribed reruns and an exploit hunt. That favors a compact environment whose state and score a judge can inspect quickly. Small-model training is an optional tiebreaker; our judgment is to defer it until the core gap and reward are credible.

## What Harbor already supplies

The challenge names Harbor and OpenCode over MCP. Upstream documentation establishes these capabilities, **not** the exact version/configuration of the event's starter kit.

| Component | Verified upstream capability | Consequence |
|---|---|---|
| Task package | Instructions, environment, reference solution and verifier are separate components. [Overview](https://docs.harborframework.com/tasks/overview) | Build a small task package, not a new evaluation platform. |
| Tools | MCP services can accompany container environments; agents can use code and files. [Environment](https://docs.harborframework.com/tasks/environment) | Agent-written routing/control programs are valid. |
| Agents | OpenCode, reference (`oracle`) and no-op (`nop`) integrations exist; capabilities vary. [Integrations](https://docs.harborframework.com/agents/pre-integrated-agents) | Pin and exercise the organizer configuration; listing support does not prove connectivity. |
| Rewards | Verifiers write numeric rewards, including structured metrics. [Verifier](https://docs.harborframework.com/tasks/verifier) | Keep primary score and diagnostics distinct. |
| Isolation | Separate verifier environments are supported; omitting the relevant settings retains shared verification. [Separate verifier](https://docs.harborframework.com/tasks/separate-verifier) | Inspect the boundary. A separate container does not make agent-written evidence authoritative. |

Our proposed boundary is a simulator-owned state/action ledger, agent-owned scratch space/policy code, and checks derived from authoritative state. This is not an implemented security guarantee. A missing verifier reward is an execution problem to investigate, not automatically model failure. The environment catalogue also distinguishes tasksets from runtimes; compatibility labels do not convert frameworks. [Hugging Face environment announcement](https://huggingface.co/blog/rl-environments)

## Before we commit to a build

Resolve the official starter-kit revision and agent/model budget; select the smallest credible plant/world and reference; agree the primary metric and continuation gate; then run the fair pilot. None of those choices is settled by a published score.

Suggested reading order: this brief, the [control comparison](control-and-optimization.md), the [reward/evaluation proposal](reward-and-evaluation.md), then the broader [benchmark landscape](benchmark-landscape.md). All are research artifacts; no external repository or model was executed as a project experiment during this review.
