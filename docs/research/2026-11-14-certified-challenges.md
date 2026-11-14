# A challenge the reference can reliably solve

Research date: **14 November 2026**. Kristján asked for recent research, a cooler challenge, and a reference that reliably wins. This is a research proposal and a free feasibility probe, not a project decision or evidence of a new model failure. It complements Sölvi's separately claimed mechanism review; existing environments and the demo are unchanged.

**Delivered result:** the exact reference solves all 48 fresh check missions optimally, but a generic beam search obtains 97.29–99.35% of the optimum. The simple sample-chain prototype fails its difficulty gate and should **not** replace Lightlag. Recent research makes compatible science products a plausible next hypothesis; it does not justify a larger full environment yet.

## Recommendation

**Investigate missions where observations must fit together to produce useful science.** Merely scheduling collection, processing and transmission is insufficient in the probe below. A stronger candidate is stereo surveying: images from different positions must jointly satisfy overlap and viewing-angle requirements, then fit power, storage and relay constraints. An attractive local action can prevent several later products. The interesting failure is doing plenty of work but returning little usable science.

The tested **Mars Sample Return** concept can reuse the Mars presentation, but its small deterministic scheduling model is too easy for generic search. Keep its exact-reference machinery as a research tool. Test compatible observations or a factory's interdependent recipes separately before building either candidate. A bigger map would then be a presentation or scaling choice, not the mechanism responsible for the gap.

The strongest defensible promise is: **every scored instance has an independently checked winning reference plan**. That is achievable. “A current coding agent always loses” is an empirical hypothesis, not something research or an optimal reference can guarantee. An agent that writes an equivalent solver deserves to win.

## What our results already rule out

- **A larger rover mission alone.** The six-region survey's held-out adaptive reference scored raw science 9.96250 versus 10.09687 for an entropy heuristic. All 128 check episodes returned home alive. No model was run because the acquisition gate failed. [Survey handoff](../lightlag-survey-handoff.md).
- **Treating turn-by-turn mistakes as a robust coding-agent limitation.** On 200 fresh maps, a one-request Opus autopilot scored 0.515 versus 0.518 for the reference. The mean paired lead was approximately 0.002, with a 95% interval crossing zero. On `rush` 501, saved model-written autopilots avoided the rover deaths seen in the direct-action runs. [Live experiment](../lightlag-live.md).
- **Adding another simple information choice.** All twelve competing-information Opus sessions chose acquisition, route and timing optimally and matched their references. [Allocation experiment](../lightlag-allocation-experiment.md).

These are different experiments, not a pooled benchmark. They support changing the structure of the task, rather than claiming that the agents failed at the existing extensions.

## Recent primary research that changes the design

### Space missions: useful results must survive the entire chain

[AstroAgentBench, AACL, 6–10 November 2026](https://aclanthology.org/2026.aacl-long.72.pdf), Table 3 and Appendix K, is the closest match. Five systems received code execution, scientific/optimization libraries and two hours per case. Across five cases per family, the best agent's Stereo Imaging score was 68.91 versus 96.05 for the best solver baseline; Regional Coverage was 73.15 versus 86.44. Agents beat the references in four other families. The authors identify failures to turn valid observations into useful products, but also document ambiguous coordinate conventions. The strongest models tested were older than our current Opus runs, and the reference row selects the best available solver per case. These results motivate complete-product constraints; they do not establish a clean current-model gap or a single universally winning reference.

**Application:** make science depend on completing a visible, precisely specified chain. Publish units, interval boundaries, worked examples and a verifier. Avoid ambiguous geometry as a source of difficulty.

### Factory scheduling: coupled resources are more interesting than extra jobs

[Agentic AI-Assisted Modeling for Production Scheduling, 7 October 2026](https://arxiv.org/html/2610.10184v1), §4 and Tables 6–7, compares six production/warehouse problems. The hardest combines two vehicles, limited buffer space and two picking robots. The multi-agent workflow produced runnable correct scripts in 59.3% of runs overall; all three tested models failed that hardest problem's execution checks. However, models included GPT-5 and Gemini 2.5 Pro, and the setup is generated-model evaluation rather than our latest full coding-agent pilot. Only the first four reference objectives were proven optimal; the two hardest were best-known solutions.

**Application:** shared capacity, no-wait processing, perishable samples and relay deadlines are plausible mechanisms. Start small enough to prove optimality; do not import the paper's hardest case and call its reference infallible.

### Counterevidence: coding agents can implement the obvious solver

[Coding Agents for Generalized Task and Motion Planning, 24 September 2026](https://arxiv.org/abs/2609.30233) evaluates frozen generated programs on unseen instances. Its three coding-agent configurations outperform the hand-engineered planners on average on the 16 environments with a planner comparator: reported success spans 56–95% for agents versus 47% for planners. More objects did not automatically restore the planner's advantage.

[DecompGym, 28 October 2026](https://arxiv.org/abs/2610.38175) tests 81 optimization instances with actual coding tools. Two models solve every instance on their first attempt; seven exceed 90%. Its prescribed-method audit is a separate requirement from achieving the optimization objective.

**Application:** allow Python, persistent programs, optimization libraries and simulation. Test a solver-hinted agent early. A standard routing puzzle, ordinary job shop or larger grid is a weak bet unless a full coding agent actually fails it.

### Attractive low scores can come from a different test

[ConstraintBench, February 2026](https://arxiv.org/abs/2602.22465) explicitly tests direct optimization **without solver access**. Its low joint feasibility/optimality rates should not be used to predict our coding-agent results.

[Long-Horizon-Terminal-Bench, revised 9 October 2026](https://arxiv.org/html/2607.08964v3) does allow terminal agents, reports a best 15.2% pass rate at its 0.95 threshold, and supplies executable reference solutions. Its roughly 85-minute average episodes and expensive long workflows are a poor starting point for a cheap hackathon probe. Borrow verifiable intermediate outcomes and dependent stages, not sheer episode length.

## Three concrete candidates

| Candidate | Interesting decision | Reliable reference | Cost and weakness |
|---|---|---|---|
| **Mars Sample Return — tested, reject this size** | Reserve collection, processing, storage, power and a downlink together; a locally profitable pickup can block a better complete campaign. | Exact search on a bounded deterministic mission; independently replay its schedule. | Reuses the theme, but generic beam search nearly saturates the ceiling. No model run justified by this result. |
| **Orbital Stereo Survey — next research hypothesis** | Two images must jointly meet geometry, timing and overlap requirements, then reach Earth. More photographs need not produce more useful maps. | Enumerate valid observation pairs, then exactly optimize compatible products on small cases. | Closest research precedent, but requires trustworthy geometry. Publish executable geometry helpers so convention errors cannot create the gap. |
| **Blackout Factory — larger environment pivot** | Restart a production network with shared transport, limited buffers and batches that spoil if the next machine is unavailable. | CP-SAT or exhaustive search for small instances; retain only publicly specified instances with verified certificates. | Strong visual consequences and coupled decisions. A bigger implementation, and the latest coding agents may still solve it. |

These are proposed designs, not descriptions of benchmarks that already defeat Opus 5.5. There is no need to train a neural reference first: a specialized exact planner gives a clearer ceiling.

## Free probe contract

The isolated [probe](../../tools/certified_challenge_probe/README.md) tests whether a small collection → lab → downlink model contains a real planning tradeoff. All times, values and resource limits are public. There is no stochastic noise, privileged hidden state, API latency or model call. The exact reference and every baseline get identical inputs.

The probe must report absolute delivered value, value relative to the computed optimum, full-optimum frequency, reference search effort and independent replay validity. Compare value-first, deadline-first, density-first, a portfolio of those policies and a bounded beam search. A weak greedy baseline is not a substitute for a coding agent.

Development instances may guide implementation. Freeze the generator and algorithms before a separate check range; retain every check result, including zero-value and failed-reference cases. Cross-check exact search against an independent brute-force method on tiny instances. Record hashes and replayable plans so the findings can be reproduced.

The small model is a feasibility check, not a new Harbor task. If short generic search reaches almost the entire ceiling, report that and reject this size as a difficulty claim. Do not keep enlarging it until a chosen agent loses.

## Free probe outcome

The generator, algorithms and fresh-check protocol were published in [`465d91e`](https://github.com/solvisantos22/junction-2026/commit/465d91e) before opening check seeds 30000–30023. Development was 24 cases, check was 48: 24 cases each at eight and twelve jobs. No cases were filtered or dropped. The same seed across sizes is correlated, so these are descriptive comparisons, not independent statistical replications.

| Fresh check | 8 jobs | 12 jobs |
|---|---:|---:|
| Exact reference optimal, independently replayed | 24/24 | 24/24 |
| Reference mean delivered value | 65.25 | 95.4583 |
| Value-first greedy, mean fraction of optimum | 87.44% | 82.96% |
| Best-of-four greedy portfolio | 95.74% | 90.41% |
| Generic beam search, width 64 | **99.35%** | **97.29%** |
| Beam search reaches exact optimum | 20/24 | 10/24 |
| Largest exact search, nodes | 16,768 | 832,012 |

The reference proved every optimum within the declared one-million-node limit; the slowest check solve took 4.37 seconds on this machine. Beam search took about 0.67 seconds for all 48 check cases combined, excluding compilation. Absolute values and per-policy timings are retained in [check.json](../../tools/certified_challenge_probe/results/check.json); [development.json](../../tools/certified_challenge_probe/results/development.json) is retained separately. The full theoretical maximum of all listed samples is not used as a misleading denominator: normalized scores use each case's proved achievable optimum.

The predeclared pilot gate required the greedy portfolio to average at most 90% and beam search at most 95%, with every reference certified. Both sizes fail the difficulty requirements. Enlarging from eight to twelve jobs makes greedy performance look much worse, while a small generic search remains close to optimal. A full coding agent may implement this search or the exact reference itself. **Do not describe these controls as agent failures, and do not replace the current environment with this prototype.**

Ten focused tests pass, including a separate brute-force optimum check on eight tiny instances and tests for power, cold storage, memory, temporal boundaries and invalid submissions. A post-write audit regenerated all 72 missions, matched every frozen source hash, replayed all 504 saved policy records and reconstructed every summary. The portfolio records reuse a winning greedy plan; they are not additional independent trials. These checks establish this implementation's internal evidence, not an externally certified production solver.

No actual coding model has played this new prototype. No API spend was incurred. The check seeds are now development data for any future version. The existing rover, demos and canonical Harbor task were not edited.

## What a meaningful next model experiment must establish

1. Freeze one precise public ruleset, reference implementation, generator, model configuration and total budget. Reference preparation and online computation must be disclosed.
2. Offer code, solver libraries, a practice case, a local validator and a complete worked example. Include a run explicitly suggesting constraint programming. Keep simulation time paused during reasoning.
3. Evaluate fresh missions from the declared distribution. Compare a frozen general solver across missions as well as per-instance coding, if both are relevant to the judging contract. Do not choose maps after seeing model scores.
4. Require valid reference replays on every scored case, and distinguish exact optimum from a feasible target. A stored feasible plan proves solvability; it alone does not prove optimality.
5. Retain raw scores, failures, runtimes and costs. If the best agent is within five percentage points of the reference, or a simple solver hint removes the deficit, stop this candidate before building a full replacement environment. A small pilot is screening evidence, not proof of reliability.

No new paid model run is included in this research. The next useful deliverable is a defensible candidate and a falsifiable test, not another claim based on direct-action failures or weak baselines.
