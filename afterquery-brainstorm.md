# AfterQuery RL Environment Challenge: Brainstorm

*Brainstorm notes made with Claude (AI), last updated 2026-11-13. Companion to the team's shortlist (`afterquery-ideas.md`) and research (`docs/research/`). Scores are gut ratings, and no performance gap has been measured for any idea yet. To brainstorm with a chatbot, give it this whole file plus the prompt in "Prompt for a chatbot" below.*

## Contents
- The challenge (original text)
- Side by side with the team's notes
- What we're aiming for
- Ideas at a glance
- The ideas in detail
- Combining ideas
- More raw ideas
- Building blocks: why agents fail, how to stop reward hacking, design principles
- Prompt for a chatbot
- Open questions

## The challenge (original text)

*Copied verbatim from the organizers' description. The words are unchanged; only headings, line breaks and list bullets (in place of the original • separators) were added for readability.*

### The Challenge

Build a reinforcement learning environment that challenges today's best AI agents, demonstrate real failure modes, and show that its rewards reflect real progress.

### Introduction

Today's cutting-edge AI systems can solve Millennium Problems, discover new drugs, and create entire production apps with a few lines of prompting. But they still struggle in a wide variety of novel situations, ranging from everyday use cases to niche, highly technical workflows. We ask: what should AI agents be able to do that they still struggle with today?

At AfterQuery, we build environments for training and testing agents. The work starts with choosing a problem worth learning, defining an action and observation space, and defining a reward function that defines what success looks like. Getting those pieces right is a heavy research and engineering problem in itself.

For this challenge, we want to see your take on it. Build a world with something interesting to learn. Find out where strong agents struggle, and whether your reward actually encourages the behavior you intended.

### The challenge

Choose a setting you find interesting and build an environment an agent can interact with. It could be a game, a scientific simulation, a software task, a real-world process, or something we haven't thought of. Explain why you chose it and what an agent could learn there.

Your environment should have a clear goal, actions the agent can take, and a reward you can check. Run a frontier agent in it and compare the results with a stronger reference run your team can demonstrate and reproduce. We'll provide the agent harness and model credits.

Show where the agent falls short and why. The challenge should come from the decisions it needs to make, with access to the information and tools needed to succeed. We'll also try to find shortcuts that earn a high score without completing the task: reward hacking.

The setting and approach are yours to choose. We care about what makes the environment useful for learning and what your experiments reveal.

### Optional stretch goal

Train a smaller model using experience from your environment and show whether it improves.

### Prizes

The top three teams receive €3,000, €1,500 and €500 in cash. Members of the winning teams can go straight to the final stage of AfterQuery's interview process: a work trial with our environments team, when they're ready. Finalists also receive AfterQuery gear.

How we judge: We'll look at four things: how much room there is for the agent to improve, whether its mistakes come from meaningful challenges, how well the reward holds up to exploits, and how well the environment is built and the results can be reproduced.

### Judging rubric

- The gap (30 p) – Full points: the frontier agent consistently scores below a stronger reference run your team demonstrates; both results can be reproduced across repeated runs. Zero points: no measurable gap, or the claimed gap cannot be reproduced or checked against a demonstrated reference run.
- Meaningful difficulty (30 p) – Full points: you can explain the agent's main mistakes and connect them to decisions in the task; the information and tools needed to do better are available to it. Zero points: the gap comes from unfairly withheld information, trick wording, impossible timing, or broken tools.
- Reward integrity (25 p) – Full points: the reward measures success at the task and holds up when judges try to exploit it; doing nothing or stopping early earns little or no credit; completing the task well remains the best way to score. Zero points: an exploit, scoring loophole, or strategy that avoids the task earns a better score than successful play.
- Craft (15 p) – Full points: the environment's rules and behavior make sense for the setting; judges can run the evaluation from your README with one command and reproduce your reported results. Zero points: the environment only works in your demo, or judges cannot reproduce the evaluation.

How judging runs: Each team gets a 10-minute demo. Judges then rerun the evaluation with the standard harness: your reference run, three agent runs, a do-nothing baseline, and a stop-early baseline. They also spend 15 minutes looking for reward exploits. Scores are based on these runs.

Tiebreaker: If point totals are close, we'll favor a team that shows a smaller model improving after training on experience from its environment.

## Side by side with the team's notes

The team's notes are the shortlist in `afterquery-ideas.md` and the research in `docs/research/` (benchmark landscape, control and optimization, reward and evaluation). This file is the wider brainstorm. The two complement each other: the research is source-linked evidence about three ideas; this brainstorm is design reasoning across many ideas, with gut scores and no literature check. Statements below about papers and benchmarks come from the team's research and were not re-checked here.

### At a glance

| | Team shortlist + research | This brainstorm |
|---|---|---|
| Purpose | Choose between three ideas using published evidence | Generate and compare many ideas; design rewards and references |
| Ideas covered | ColdChain, BatchPilot, RecoveryRoom | 13 written up (including BatchPilot), 10 combinations, 14 one-liners |
| Evidence | Primary papers, benchmarks and docs, with conditions and limits | Reasoning and gut scores; no gap measured |
| Harness | Harbor + OpenCode over MCP, with reference (`oracle`) and no-op (`nop`) agents and a separate verifier; the event's exact starter kit is not yet confirmed | Unknown when written |
| Headline advice | Pilot the strongest agent first; one controlled source of difficulty; a fair reference; score outcomes and continuing obligations | Hard task, unbreakable reward; public rules, hidden instance; an honest reference; test the brute-force escape hatch first |
| Current leaning | Experiment order: ColdChain first (cheapest to rule out), BatchPilot as the strongest technical alternative, RecoveryRoom third. Core hypothesis: can a capable agent keep important constraints when it must commit irreversibly before a later, disclosed kind of disruption? | After re-scoring, Cipher Lab, Forecasting Arena and Incident Commander lead on paper but are untested; BatchPilot is the best fit for the team's skills |

### Where they agree
- **Code and solvers are fair game.** An agent writing its own solver or controller is legitimate, so the difficulty must survive it. (Research: "Let the agent build a controller or use a solver". Here: *Brute-force Escape Hatch*.)
- **Equal information.** The reference may only use what the agent can see; a solver that knows future events is at most a labelled upper bound. (Research: "Equalize information". Here: *Honest Reference Solver*.)
- **Doing nothing or stopping early must not pay.** Score real outcomes from trusted state, never the agent's claims. (Research: keep running the world to the fixed horizon after a stop; an evaluator-owned ledger. Here: *Baseline-Normalized Reward*, *Tamper-proof Grader*.)
- **Publish the rules.** Hiding what the rules mean manufactures difficulty. (Research: "Freeze a contract before tuning". Here: *Public Rules, Hidden Instance*.)
- **Seeds and repeats.** Development and held-out seeds, frozen before final evaluation. (Here: *Procedural Generation with Seeds*, *Held-out Evaluation*.)
- **The interesting failure is a commitment that later turns out wrong.** The research's core hypothesis, keeping constraints through an irreversible commitment made before a disclosed kind of disruption, lines up with *Premature Commitment* and *Delayed-Feedback Blindness* here.

### Where the research changes this brainstorm
Three ideas were re-scored because of this research; each one's section below explains why.

- **Rule-Discovery Gridworld: gap 5 → 2, weighted 89 → 71.** The benchmark review reports a current language-only agent at 100% on BabyAI and BabaIsAI and concludes that a small rule puzzle may be too easy.
- **Supply Chain Under Shocks: gap 5 → 3, weighted 81 → 69.** Vending-Bench 2, AutoVend (a current model beating its inventory-control reference) and a Beer Game study (good average performance from some agents) are reported counterevidence; perishable stock plus tools is established prior art.
- **BatchPilot: gap 4 → 3 and build ease 4 → 3, weighted 86 → 77.** It faces reported controller-generation results (CoDyControlBench, a gas-preheater study) and OperAItor, a reactor environment from November 2026, and the review rates its build risk as higher. The design here targets what those reportedly don't cover: strict batch quality and safety limits, delayed lab results, drift between batches, and abort decisions. That matches where the control review says a gap might remain: delayed actuation, terminal quality, constraint margins, recovery. Team fit isn't in the formula and still counts in its favor.
- **Untested ideas now rank highest.** Cipher Lab and Forecasting Arena lead partly because the research hasn't covered them. Their scores are as untested as the dropped ones were.
- **RecoveryRoom is a stronger version of Incident Commander.** Incident Commander now ranks third mainly because others dropped. The research cites AIOpsLab and ITBench as prior art for "fix the incident". RecoveryRoom's goal, restoring service while preserving every accepted job's business effect, checked against an evaluator-owned ledger, is more distinctive.
- **Check that a failure is real before claiming it.** A low score can come from a broken task, interface or time budget (the research cites a Terminal-Bench audit). The failure modes below assume a sound task.

### What this brainstorm adds
- **A concrete BatchPilot spec:** batch targets and safety limit, tools, reward formula, an MPC + estimator reference that sees only agent-visible data, and an exploit table.
- **Ten more written-up ideas** outside the shortlist, notably Cipher Lab and Forecasting Arena, which the research hasn't covered. The same pilot-first caution applies to them.
- **A shared vocabulary for explaining failures:** 11 named failure modes, plus reward patterns such as the multiplicative efficiency bonus and proper scoring rules.
- **Extra reward probes:** parser-breaking inputs, flag-everything, action spam, timeouts. In the other direction, the research's checklist adds two probes missing here: state laundering (restoring snapshots, resetting counters) and making sure the verifier accepts valid alternative solutions.

### ColdChain
Not written up here; its closest ideas are Dynamic Scheduler and Supply Chain Under Shocks. The research's counting argument (8 deliveries on two vehicles fit in about 362,880 candidates before pruning) is exactly the *Brute-force Escape Hatch*: an enumerator could erase the gap, so the difficulty would have to come from replanning after irreversible commitments.

## What we're aiming for

1. **Hard task, unbreakable reward.** The task must be solvable, because we have to show a stronger reference run. But frontier agents should fail at it for reasons we can explain. What must be unbreakable is the *reward*: doing nothing or stopping early scores about 0, and no trick beats actually doing the task.
2. **Public rules, hidden instance.** Publish the *family* of possible worlds (e.g. "the cipher chains 2–4 of these 6 steps"). A random seed picks the specific world for each episode. This is fair (everything can be learned by exploring), can't be memorized, and makes the reward exactly checkable.
3. **Why not "dynamic encryption" as-is.** Real encryption (AES) is unbreakable for everyone, including our reference, which would score zero on fairness. Textbook ciphers are too easy for frontier agents. We reframed it as **Cipher Lab**: reverse-engineer a cipher, built from a published rulebook, whose key keeps rotating.
4. **What "RL" means here.** We build the environment and the reward; the agent does the learning. *Within one episode* the agent discovers the hidden setup by probing it; this is what the judges measure. *Across many episodes* with different seeds, RL training updates a model's weights so it gets better at discovering in general; this is the optional stretch goal. Reward loopholes matter because RL training finds them and learns to exploit them.
5. **The reference run must be honest.** It may only use information the agent also sees. For example, an MPC controller has to estimate the plant's parameters from the same sensor data, not read them from the seed. Otherwise the gap counts as withheld information.
6. **Biggest shared risk.** The agent writes code that brute-forces the problem (its own controller, a search over every possible cipher). That is legitimate success, so the difficulty has to come from interaction and judgment, not raw compute. Test for it in the first pilot.

## Ideas at a glance

Scores are 1–5 gut ratings, meant to be argued with. Weighted score follows the rubric: (gap×30 + difficulty×30 + integrity×25 + build ease×15) / 5, out of 100. "Build ease" stands in for craft (higher = easier to build well). Three ideas were re-scored after reading the team's research (marked *re-scored*; see "Where the research changes this brainstorm" above). The rest keep their original gut scores, untested against the literature.

| # | Idea | Theme | In one line | Gap | Difficulty | Integrity | Build ease | Weighted |
|---|---|---|---|---|---|---|---|---|
| 1 | Cipher Lab | Hidden-rule discovery | Reverse-engineer a procedurally generated cipher whose key keeps changing, using a limited "encrypt" tool, then decrypt messages sent at *future* key states. | 3 | 5 | 5 | 4 | **85** |
| 2 | Forecasting Arena | Judgment under uncertainty | A simulated world (small economy, disease spread, or sports league) with hidden dynamics. Read the data, optionally buy more, and give probability forecasts for upcoming events. | 4 | 4 | 5 | 4 | **85** |
| 3 | Incident Commander | Investigation & diagnosis | A simulated cluster of 8–20 microservices has a hidden fault. Investigate logs, metrics and traces, fix the actual cause and name it, without wrecking healthy services. | 4 | 5 | 4 | 2 | **80** |
| 4 | Alien Physics Lab | Hidden-rule discovery | A procedurally generated 2D world whose physics laws are *not* Earth's. Run experiments to work out the laws, then predict or hit targets you have never seen. | 4 | 4 | 4 | 3 | **77** |
| 5 | Synthetic Research Desk | Investigation & diagnosis | A generated wiki, email archive and changelog (~500 documents) for a fictional company. Facts change over time, documents contradict each other, some are stale or rumor. Answer 10 precise questions. | 4 | 4 | 4 | 3 | **77** |
| 6 | BatchPilot *(team proposal, re-scored)* | Long-horizon control & planning | Produce three on-spec batches in a simulated jacketed batch reactor where heating, cooling and the reaction's own heat all act with delays. Agent vs a model predictive controller (MPC). | 3 | 5 | 4 | 3 | **77** |
| 7 | Protocol Whisperer | Hidden-rule discovery | Get something done on a server that speaks an undocumented, stateful protocol. The docs you have are partial, and some pages are out of date. | 4 | 4 | 4 | 3 | **77** |
| 8 | Rule-Discovery Gridworld *(re-scored)* | Hidden-rule discovery | Original grid puzzles where the rules are hidden. Explore, work out the mechanics, then solve each level in as few moves as possible. Every level mixes mechanics in a new way. | 2 | 5 | 4 | 3 | **71** |
| 9 | Spreadsheet Forensics | Investigation & diagnosis | A generated financial model (~2,000 formula cells) hides 5–15 planted mistakes. Find them, fix them minimally, and show the model now gives the right numbers. | 3 | 4 | 4 | 3 | **71** |
| 10 | Supply Chain Under Shocks *(re-scored)* | Long-horizon control & planning | Run a small multi-stage supply chain for 100 simulated days: order stock, pick suppliers, set prices, and survive shocks you only partly see coming. | 3 | 4 | 3 | 4 | **69** |
| 11 | Patch Under Fire | Defensive security | Defend a small web service with planted vulnerabilities while a scripted attacker probes it over time. Patch the real bugs without breaking features. | 3 | 4 | 4 | 2 | **68** |
| 12 | Dynamic Scheduler | Long-horizon control & planning | Build a shift or job-shop schedule, then keep repairing it as disruptions hit. Some constraints only come out by asking stakeholders. | 2 | 3 | 5 | 4 | **67** |
| 13 | Sealed-Bid Negotiator | Long-horizon control & planning | Buy supplies through a series of negotiations and sealed-bid auctions against scripted counterparties with hidden valuations and distinct styles. | 3 | 3 | 2 | 4 | **58** |

## The ideas in detail

Ordered by weighted score. Names in the "Connections" lists refer to the building blocks section further down.

### 1. Cipher Lab

*Theme: Hidden-rule discovery · Gap 3 · Difficulty 5 · Integrity 5 · Build ease 4 · Small-model fit 5 · Weighted 85/100*

> **Pitch**
> Reverse-engineer a procedurally generated cipher whose key keeps changing, using a limited "encrypt" tool, then decrypt messages sent at *future* key states.

This is the grown-up version of the "dynamic encryption" idea. Breaking real encryption (AES) is impossible for everyone, including our reference, so it would score zero on fairness. Breaking textbook ciphers is too easy. The sweet spot is **reverse-engineering a mechanism the agent is allowed to probe**.

#### The world
- A seed builds a hidden cipher by chaining 2–4 steps from a **published rulebook**: shift, affine map, partial letter substitution, column transposition, XOR with a pseudo-random keystream (LCG), block reversal.
- **The dynamic part:** the key changes on a hidden but discoverable schedule: every *k* encryptions, with a message counter, or chained on the previous ciphertext.
- The agent knows the family, not the instance → Public Rules, Hidden Instance.

#### Agent interface
- **Observes:** the rulebook, remaining budget, every result of its encrypt calls, challenge ciphertexts tagged with their counter positions.
- **Tools:** `encrypt(plaintext)` (costs 1 budget), `python(code)`, `submit(plaintexts)`.

#### Goal & reward
- Decrypt the challenge messages, which were encrypted at key states the agent never saw.
- `R = exact_matches / n × (1 − 0.25 × queries_used / budget)` → Multiplicative Efficiency Bonus, Exact Match Over Partial Credit.

#### Reference run
Hypothesis-elimination solver: keep every rulebook cipher consistent with what has been observed, pick the next query that splits the remaining set best (information gain), stop when one remains. Deterministic given the seed → Honest Reference Solver.

#### Why frontier agents should struggle
- Sees shift-like output and decides "it's a Caesar cipher" → Anchoring on the First Hypothesis, helped along by Real-World Priors Override Evidence.
- Encrypts "hello world" five times → Uninformative Experiments.
- Builds a lookup table that dies when the key rotates → Shallow Heuristics Break Under Shift.
- Never re-encrypts its own answer to check it → Skipping Verification.

#### Exploit attempts & defenses
| Attempt | Defense |
|---|---|
| Guess common English words | Plaintexts are random strings or rare-word sequences |
| Spam "eeee" for partial credit | Exact match per message |
| Zero queries to max the efficiency term | Efficiency multiplies correctness, so 0 × anything = 0 |
| Read the seed or generator from the sandbox | Generator and grader run outside the sandbox → Tamper-proof Grader |
| Encrypt the challenge plaintext directly | Agent never sees challenge plaintexts; challenges sit at future counters → Held-out Evaluation |

> **Biggest risk**
> The agent writes a Python search over the whole rulebook and solves it in three queries → Brute-force Escape Hatch. Keep parameter spaces huge (26! substitutions) but structured, so reasoning beats enumeration.

#### Difficulty knobs
Chain depth · parameter ranges · key-schedule complexity · query budget · chosen-plaintext vs known-plaintext only.

#### Stretch: small model
Endless seeds + exact-check reward → ideal for Small-Model Training Loop.

> **Open questions**
> - Chosen-plaintext (agent picks inputs), or only known-plaintext on the hard tier?
> - Should the key schedule react to the agent's own queries, so careless probing costs more?

#### Connections
- **Failure modes it tests:** Anchoring on the First Hypothesis, Shallow Heuristics Break Under Shift, Uninformative Experiments, Skipping Verification, Real-World Priors Override Evidence
- **Reward safeguards it uses:** Held-out Evaluation, Multiplicative Efficiency Bonus, Exact Match Over Partial Credit, Tamper-proof Grader
- **Design principles:** Public Rules, Hidden Instance, Procedural Generation with Seeds, Honest Reference Solver, Brute-force Escape Hatch, Small-Model Training Loop
- **Related ideas:** Protocol Whisperer, Alien Physics Lab, Rule-Discovery Gridworld, Patch Under Fire

### 2. Forecasting Arena

*Theme: Judgment under uncertainty · Gap 4 · Difficulty 4 · Integrity 5 · Build ease 4 · Small-model fit 4 · Weighted 85/100*

> **Pitch**
> A simulated world (small economy, disease spread, or sports league) with hidden dynamics. Read the data, optionally buy more, and give probability forecasts for upcoming events.

#### The world
- Hidden model per seed (e.g. a process that switches between regimes). Data feed + generated news text, some of it misleading.
- 50–100 forecast questions per episode, so luck averages out across 3 runs.

#### Agent interface
- **Tools:** `get_data(series, range)`, `buy_data(source)` (costs), `python(code)`, `forecast(question, probability)`.

#### Goal & reward
- Mean log score relative to a base-rate forecaster → Proper Scoring Rules, Baseline-Normalized Reward. Data purchases cost → Action Costs and Collateral Damage.
- Honest probabilities are optimal by construction, which makes this the most exploit-resistant idea here.

#### Reference run
Bayesian model of the right model family, fitted on the visible data → Honest Reference Solver.

#### Why frontier agents should struggle
- Overconfident forecasts (0.95 when 0.7 is right) → Overconfidence and Poor Calibration.
- Swayed by dramatic news text → Source Trust Errors.
- Sticks with the first trend after a regime change → Anchoring on the First Hypothesis.
- Assumes real-world base rates → Real-World Priors Override Evidence.

#### Exploit attempts & defenses
- Always say 50% → at or below the base-rate forecaster → 0.
- Extreme 0/1 answers → the log score punishes them hard (probabilities clipped to 0.01–0.99).

#### Stretch: small model
Many short, scored decisions → good fit for Small-Model Training Loop.

#### Connections
- **Failure modes it tests:** Overconfidence and Poor Calibration, Source Trust Errors, Anchoring on the First Hypothesis, Real-World Priors Override Evidence
- **Reward safeguards it uses:** Proper Scoring Rules, Baseline-Normalized Reward, Action Costs and Collateral Damage
- **Design principles:** Procedural Generation with Seeds, Verifiable Reward, Honest Reference Solver, Small-Model Training Loop
- **Related ideas:** Alien Physics Lab, Supply Chain Under Shocks, Synthetic Research Desk

### 3. Incident Commander

*Theme: Investigation & diagnosis · Gap 4 · Difficulty 5 · Integrity 4 · Build ease 2 · Small-model fit 3 · Weighted 80/100*

> **Pitch**
> A simulated cluster of 8–20 microservices has a hidden fault. Investigate logs, metrics and traces, fix the actual cause and name it, without wrecking healthy services.

#### The world
- Fault drawn from a published list: memory leak, bad config deploy, misrouted DNS, retry storm, expired certificate, full disk.
- Realistic red herrings: downstream services log errors too, and one unrelated service is always noisy.

#### Agent interface
- **Observes:** alerts, query results.
- **Tools:** `query_logs`, `get_metrics`, `get_traces`, `rollback(svc)`, `restart(svc)`, `scale(svc, n)`, `edit_config`, `declare_root_cause(svc, fault)` (once).

#### Goal & reward
- `R = slo_restored_and_stable × (0.6 + 0.4 × root_cause_correct) − collateral_cost`
- Restarts and rollbacks cause simulated downtime → Action Costs and Collateral Damage.
- Only one root-cause declaration → Precision-Recall Balance.

#### Reference run
Scripted diagnoser: walk the service dependency graph from the alerting service toward the earliest anomaly in the traces, then apply the fix that matches the fault type → Honest Reference Solver.

#### Why frontier agents should struggle
- Restarts the noisy service; the alarm clears, then the fault comes back → Symptom Fixing vs Root Cause.
- Blames the first service with errors in its logs → Anchoring on the First Hypothesis.
- Declares a root cause before checking traces → Premature Commitment.
- Trusts an outdated runbook page → Source Trust Errors.

#### Exploit attempts & defenses
- Restart everything → fault recurs (root cause still there) + huge collateral cost.
- Do nothing → SLO not restored → 0.
- Declare every fault type → only one declaration allowed.

> **Biggest risk**
> A believable simulator is the most work of any idea here, and frontier models know a lot of general SRE practice.

#### Connections
- **Failure modes it tests:** Symptom Fixing vs Root Cause, Anchoring on the First Hypothesis, Premature Commitment, Source Trust Errors
- **Reward safeguards it uses:** Action Costs and Collateral Damage, Precision-Recall Balance, Tamper-proof Grader, Baseline-Normalized Reward
- **Design principles:** Public Rules, Hidden Instance, Procedural Generation with Seeds, Honest Reference Solver, Verifiable Reward
- **Related ideas:** Patch Under Fire, Protocol Whisperer, Synthetic Research Desk

### 4. Alien Physics Lab

*Theme: Hidden-rule discovery · Gap 4 · Difficulty 4 · Integrity 4 · Build ease 3 · Small-model fit 4 · Weighted 77/100*

> **Pitch**
> A procedurally generated 2D world whose physics laws are *not* Earth's. Run experiments to work out the laws, then predict or hit targets you have never seen.

#### The world
- Laws drawn from a published menu of terms: gravity that depends on an object's color, drag that grows with speed cubed, a hidden force field around certain zones, elastic vs sticky collisions.
- Measurements carry small, documented noise.

#### Agent interface
- **Observes:** the menu of possible law terms, experiment results as numeric trajectories (t, x, y, vx, vy), budget.
- **Tools:** `run_experiment(setup)` (costs budget), `python(code)`, then in the commit phase `predict(scenarios)` or `launch(params)`.

#### Goal & reward
- Two phases: explore → commit. Final scenarios are revealed only after the agent commits, so it can't just run them → Held-out Evaluation.
- Reward: hit rate (or `exp(−error/scale)`) on held-out scenarios, normalized → Baseline-Normalized Reward, times a budget factor → Multiplicative Efficiency Bonus.

#### Reference run
Sparse regression over the published term menu (SINDy-style symbolic regression), plus experiments that change one variable at a time → Honest Reference Solver.

#### Why frontier agents should struggle
- Assumes g = 9.81 and ignores evidence → Real-World Priors Override Evidence.
- Changes mass and color in the same experiment, so it can't tell which mattered → Uninformative Experiments.
- Fits the first formula that looks okay → Anchoring on the First Hypothesis.
- States predictions with too much certainty → Overconfidence and Poor Calibration.

#### Exploit attempts & defenses
- Run the final scenario as an experiment → final scenarios hidden until commit.
- Read the simulator → it runs outside the sandbox.
- Predict "nothing moves" → normalized against a do-nothing predictor, so it scores 0.

> **Biggest risk**
> Plain curve-fitting in Python might solve it. Make laws interact (nonlinear, coupled) so targeted experiments matter more than piles of data → Difficulty Knobs and Calibration.

#### Demo appeal
Very high: animated trajectories of the agent's prediction vs the truth make a strong 10-minute demo.

#### Connections
- **Failure modes it tests:** Real-World Priors Override Evidence, Uninformative Experiments, Anchoring on the First Hypothesis, Overconfidence and Poor Calibration
- **Reward safeguards it uses:** Held-out Evaluation, Baseline-Normalized Reward, Multiplicative Efficiency Bonus
- **Design principles:** Public Rules, Hidden Instance, Procedural Generation with Seeds, Honest Reference Solver, Difficulty Knobs and Calibration
- **Related ideas:** Cipher Lab, Rule-Discovery Gridworld, Forecasting Arena, BatchPilot

### 5. Synthetic Research Desk

*Theme: Investigation & diagnosis · Gap 4 · Difficulty 4 · Integrity 4 · Build ease 3 · Small-model fit 4 · Weighted 77/100*

> **Pitch**
> A generated wiki, email archive and changelog (~500 documents) for a fictional company. Facts change over time, documents contradict each other, some are stale or rumor. Answer 10 precise questions.

#### The world
- Ground truth is a hidden timeline (reorgs, price changes, headcounts). Documents are rendered from it with provenance metadata (date, author, "official" flag).
- Built from templates (optionally with LLM paraphrasing), generated once per seed and frozen so runs reproduce.

#### Agent interface
- **Tools:** `search(query)`, `open(doc_id)`, `python(code)`, `answer(q, value, citations)`.

#### Goal & reward
- Correct answer with an authoritative citation = 1, abstain = 0, wrong = −0.25. Guessing isn't free, and abstaining on everything scores 0. Optional confidence scored with Proper Scoring Rules.
- Strict number and date parsing → Exact Match Over Partial Credit.

#### Reference run
Scripted resolver that applies the stated provenance rules (newest official document wins) to the visible metadata → Honest Reference Solver.

#### Why frontier agents should struggle
- Answers from the first search hit, which is stale → Source Trust Errors, Premature Commitment.
- Multi-hop questions ("headcount after the second reorg") → Long-Horizon Drift.
- Confident wrong answers instead of abstaining → Overconfidence and Poor Calibration.

#### Exploit attempts & defenses
- Memorization: fictional company, procedural facts → nothing to memorize.
- Citation stuffing: only the first 3 citations count, and one must be authoritative.
- Submitting every format variant: one parsed answer per question.

#### Connections
- **Failure modes it tests:** Source Trust Errors, Premature Commitment, Long-Horizon Drift, Overconfidence and Poor Calibration
- **Reward safeguards it uses:** Exact Match Over Partial Credit, Proper Scoring Rules, Tamper-proof Grader
- **Design principles:** Procedural Generation with Seeds, Verifiable Reward, Honest Reference Solver
- **Related ideas:** Spreadsheet Forensics, Incident Commander, Forecasting Arena

### 6. BatchPilot

*Theme: Long-horizon control & planning · Gap 3 · Difficulty 5 · Integrity 4 · Build ease 3 · Small-model fit 3 · Weighted 77/100*

> **Pitch**
> Produce three on-spec batches in a simulated jacketed batch reactor where heating, cooling and the reaction's own heat all act with delays. Agent vs a model predictive controller (MPC).

> **Team proposal**
> The strongest control angle: it plays to Manh's control expertise plus the team's math and agent experience. The demo is agent vs predictive controller, where delayed reactions spoil batches.

#### The world
- A standard jacketed batch reactor with an exothermic (heat-releasing) reaction: an energy balance plus an Arrhenius reaction rate, as in any process-control textbook. Credible by construction.
- **Published:** the model equations and a realistic range for each parameter → Public Rules, Hidden Instance.
- **Hidden per seed:** heat-transfer coefficient, reaction strength (activation energy, heat of reaction), feed impurity → Procedural Generation with Seeds.
- **Delays:** a few minutes of jacket dead time, thermocouple lag, and lab results that arrive ~15 simulated minutes after sampling.
- **Drift:** fouling lowers heat transfer a little every batch, so batch 3 behaves differently from batch 1.

#### Batch spec (per batch)
1. Heat to 80 ± 2 °C.
2. Hold within that band for 30 minutes.
3. Reach at least 95% conversion, confirmed by a lab sample.
4. **Never exceed 95 °C**: the safety limit. A runaway spoils the batch and costs cleanup time.
5. Cool below 40 °C before discharging.

#### Agent interface
- **Observes:** reactor and jacket temperatures (noisy), valve positions, elapsed time, lab results once they arrive, the batch log.
- **Tools:** `set_jacket(mode, level)` (rate-limited valve), `take_sample()` (costs; result delayed), `discharge()`, `abort_batch()`, `wait(minutes)`, `python(code)`.
- A decision every 5 simulated minutes: about 25 per batch, ~75 per episode.
- The `python` sandbox can compute anything but cannot touch the plant; only the tools act on it.

#### Goal & reward
- Three valid batches within a time limit (e.g. 8 simulated hours).
- `R = (1/3) × Σ over batches of valid_b × (1 − 0.2 × energy_b / energy_budget)` → Multiplicative Efficiency Bonus.
- Validity is checked on the **true simulated state across the whole batch history**, never on the agent's claims or the noisy sensors → Tamper-proof Grader.
- Samples cost money and time; the valve has rate limits and a wear cost → Action Costs and Collateral Damage.

#### Reference run
MPC plus a state and parameter estimator (extended Kalman filter), using the published model and **only the sensor data the agent sees**. If the MPC read the seed's true parameters, judges would count the gap as withheld information → Honest Reference Solver.
Backup reference: Manh runs the plant by hand once, and the recorded actions are replayed deterministically.

#### Why frontier agents should struggle
- Heats at full power until 80 °C; jacket dead time and the reaction's own heat carry it past 95 °C → Delayed-Feedback Blindness.
- Treats a 15-minute-old lab result as current and over-corrects → Delayed-Feedback Blindness.
- Reuses batch 1's recipe on batch 3 although fouling changed the plant → Shallow Heuristics Break Under Shift.
- Loses track of hold time and batch phase over ~75 steps → Long-Horizon Drift.
- Discharges without a confirming sample → Skipping Verification.
- Keeps nursing a doomed batch instead of aborting, or aborts one that could be saved → Premature Commitment.

#### Exploit attempts & defenses
| Attempt | Defense |
|---|---|
| Do nothing or stop early | Unfinished batches count 0 |
| Declare a batch done early | Spec checked over the full temperature history, not the agent's claim |
| Exploit sensor noise | Spec checked on the true simulated state |
| Flip heating and cooling rapidly | Valve rate limits + wear cost |
| Skip cool-down to save time | Discharge temperature is part of the spec |
| Make small, easy batches | Batch size is fixed |
| Skip lab samples to save cost | Conversion must be confirmed by a sample for the batch to count |

> **Biggest risk**
> The agent writes its own PID or MPC in Python and matches the reference → Brute-force Escape Hatch. That is legitimate success, so the difficulty has to come from what a controller alone doesn't solve: estimating hidden parameters, drift between batches, delayed lab results, and the sample and abort decisions. Test this in the very first pilot.

> **Credibility**
> The process must be a real one, not a puzzle dressed up as physics. Stick to textbook equations and realistic parameter ranges, and have the control expert sanity-check every number.

#### Difficulty knobs
Dead time · lab delay · strength of the exotherm · fouling rate · sensor noise · decision interval · time limit → Difficulty Knobs and Calibration.

#### Demo ideas
- Overlay plot: agent vs MPC temperature trajectories, with the spec band and the 95 °C limit drawn in.
- Batch 1 vs batch 3: does the agent learn from its own first batch?
- Score vs dead time: the gap should widen as delays grow.

#### Stretch: small model
~75 numeric decisions per episode, longer than the puzzle ideas. Doable for Small-Model Training Loop but slower; a coarser decision interval helps.

> **Open questions**
> - Which process exactly: exothermic reactor, fermentation, or crystallization cooling?
> - Does a runaway end the whole episode, or only spoil that batch?
> - Show the agent the full equations, or only a plain-language description of the plant?

#### Re-scored after the team's research (2026-11-13)
- **Gap 4 → 3.** The team's control review (`docs/research/control-and-optimization.md` in junction-2026) reports that recent models generate working feedback controllers (CoDyControlBench: 94.8% design success with three feedback-guided attempts, under a criterion that allows large overshoot), and that OperAItor (November 2026) already offers a reactor environment for agents. This design targets what those reportedly don't test: strict batch quality and safety limits, delayed lab results, drift between batches, and abort decisions. But no gap has been shown.
- **Build ease 4 → 3.** The review rates BatchPilot's build risk higher than ColdChain's: dynamics, units, integration and feasibility all need validation.
- **Weighted 86 → 77.** Team fit (Manh's control background) is still not in the formula and still counts in its favor.

#### Connections
- **Failure modes it tests:** Delayed-Feedback Blindness, Shallow Heuristics Break Under Shift, Long-Horizon Drift, Skipping Verification, Premature Commitment
- **Reward safeguards it uses:** Tamper-proof Grader, Multiplicative Efficiency Bonus, Action Costs and Collateral Damage
- **Design principles:** Public Rules, Hidden Instance, Honest Reference Solver, Brute-force Escape Hatch, Difficulty Knobs and Calibration, Procedural Generation with Seeds
- **Related ideas:** Supply Chain Under Shocks, Alien Physics Lab, Dynamic Scheduler

### 7. Protocol Whisperer

*Theme: Hidden-rule discovery · Gap 4 · Difficulty 4 · Integrity 4 · Build ease 3 · Small-model fit 3 · Weighted 77/100*

> **Pitch**
> Get something done on a server that speaks an undocumented, stateful protocol. The docs you have are partial, and some pages are out of date.

#### The world
- Procedurally generated protocol: message formats, field orders, checksums, session tokens, sequence numbers, and a hidden state machine (login → select → stage → commit).
- Partial docs; some pages describe an older version. Pages are clearly dated, so trusting the newest is learnable.
- Example goal: move a specific record from account A to account B.

#### Agent interface
- **Observes:** raw responses, error codes, docs.
- **Tools:** `send(message)`, `read_docs(page)`, `python(code)`.

#### Goal & reward
- Reward comes from the **server's internal state** (was the record moved?), never from the agent's own claim → Tamper-proof Grader.
- Each malformed message costs a little; too many trigger a short cooldown → Action Costs and Collateral Damage.
- The final task uses new record IDs, different from what was explored → Held-out Evaluation.

#### Reference run
Active automata learning (Angluin-style L* algorithm) over the published message grammar, plus a scripted task executor → Honest Reference Solver.

#### Why frontier agents should struggle
- Loses track of sequence numbers and session state over many messages → Long-Horizon Drift.
- Follows the stale doc page → Source Trust Errors.
- Assumes the first working message format is the whole story → Anchoring on the First Hypothesis.
- Claims success without checking the server state → Skipping Verification.

#### Exploit attempts & defenses
- Print "SUCCESS" → reward reads server state only.
- Fuzz thousands of messages → per-message cost + cooldown.
- Replay a recorded valid message → sequence numbers and session tokens make replays fail.

> **Encryption angle**
> Encrypt or checksum payloads with a Cipher Lab-style rotating cipher to keep the "dynamic encryption" theme → see "Combining ideas" below.

#### Connections
- **Failure modes it tests:** Long-Horizon Drift, Source Trust Errors, Anchoring on the First Hypothesis, Skipping Verification
- **Reward safeguards it uses:** Tamper-proof Grader, Action Costs and Collateral Damage, Held-out Evaluation
- **Design principles:** Public Rules, Hidden Instance, Honest Reference Solver, Procedural Generation with Seeds
- **Related ideas:** Cipher Lab, Incident Commander, Patch Under Fire

### 8. Rule-Discovery Gridworld

*Theme: Hidden-rule discovery · Gap 2 · Difficulty 5 · Integrity 4 · Build ease 3 · Small-model fit 4 · Weighted 71/100*

> **Pitch**
> Original grid puzzles where the rules are hidden. Explore, work out the mechanics, then solve each level in as few moves as possible. Every level mixes mechanics in a new way.

#### The world
- Mechanics from a published menu: pushable blocks, tiles that swap colors when touched, keys that open same-colored doors, a counter that must reach zero, teleporters, tiles that only work from one direction.
- Our own design. Interactive rule-discovery benchmarks exist (ARC-AGI-3 uses interactive games), so we stay original and don't copy any existing game.

#### Agent interface
- **Observes:** ASCII grid + inventory + move counter.
- **Tools:** `move(dir)`, `interact()`, `reset_level()` (costs moves), `python(code)`.

#### Goal & reward
- `R = mean over levels of solved × min(1, ref_moves / agent_moves)` → Multiplicative Efficiency Bonus, Baseline-Normalized Reward.
- Resets cost moves → Action Costs and Collateral Damage.

#### Reference run
Two honest options → Honest Reference Solver:
1. A hypothesis-testing agent over the mechanic menu + an A* planner.
2. A recorded human playthrough replayed move by move. Humans are strong at this, and a replay is exactly reproducible.

#### Why frontier agents should struggle
- Assumes walls block and keys are single-use, like most games → Real-World Priors Override Evidence.
- Wanders instead of testing one mechanic at a time → Uninformative Experiments.
- Locks into a wrong rule after one observation → Anchoring on the First Hypothesis.
- Loses track of the board across many moves → Long-Horizon Drift.

#### Exploit attempts & defenses
- Random move spam → efficiency term collapses; move cap per level.
- Reset spam → resets cost moves.

#### Stretch: small model
Short episodes, exact reward, endless levels → strong fit for Small-Model Training Loop. A difficulty curve across Difficulty Knobs and Calibration makes a good demo plot.

#### Re-scored after the team's research (2026-11-13)
- **Gap 5 → 2.** The team's benchmark review (`docs/research/benchmark-landscape.md` in junction-2026) reports a current language-only agent scoring 100% on BabyAI and BabaIsAI, small rule-discovery puzzles much like this one, while full NetHack remains hard. Small puzzles alone probably won't produce a gap.
- **Weighted 89 → 71.** Other scores unchanged.
- **What could rescue it:** much larger levels, or mechanics that interact over long horizons. That raises the build cost and moves it toward game-scale environments.

#### Connections
- **Failure modes it tests:** Real-World Priors Override Evidence, Uninformative Experiments, Anchoring on the First Hypothesis, Long-Horizon Drift
- **Reward safeguards it uses:** Multiplicative Efficiency Bonus, Baseline-Normalized Reward, Action Costs and Collateral Damage
- **Design principles:** Public Rules, Hidden Instance, Procedural Generation with Seeds, Honest Reference Solver, Small-Model Training Loop, Difficulty Knobs and Calibration
- **Related ideas:** Alien Physics Lab, Cipher Lab

### 9. Spreadsheet Forensics

*Theme: Investigation & diagnosis · Gap 3 · Difficulty 4 · Integrity 4 · Build ease 3 · Small-model fit 4 · Weighted 71/100*

> **Pitch**
> A generated financial model (~2,000 formula cells) hides 5–15 planted mistakes. Find them, fix them minimally, and show the model now gives the right numbers.

#### The world
- Planted error types (published): wrong SUM range, sign flip, hardcoded number overriding a formula, unit mix-up (thousands vs units), off-by-one period, broken cross-sheet reference.

#### Agent interface
- **Tools:** `read(range)`, `formula(cell)`, `evaluate(inputs)`, `flag(cell, reason)`, `fix(cell, formula)`, `python(code)`.

#### Goal & reward
- `R = F1(flags) × outputs_correct_on_hidden_scenarios − churn_penalty` → Precision-Recall Balance, Held-out Evaluation, Action Costs and Collateral Damage.
- Hidden scenarios are input assumptions the agent never sees; a correct model gives the right outputs for all of them.

#### Reference run
Rule-based auditor (formula consistency across rows and columns, unit checks, hardcode detection) plus scenario diffing. Uses only what the agent sees → Honest Reference Solver.

#### Why frontier agents should struggle
- Large structured data; easy to lose its place → Long-Horizon Drift.
- Fixes a cell and never re-evaluates → Skipping Verification.
- Flags cells that "look weird" instead of checking the logic → Shallow Heuristics Break Under Shift.
- Stops after the first few errors → Premature Commitment.

#### Exploit attempts & defenses
- Flag everything → precision collapses.
- Rewrite the whole model → churn penalty, and the hidden scenarios test the original structure.

#### Connections
- **Failure modes it tests:** Skipping Verification, Long-Horizon Drift, Shallow Heuristics Break Under Shift, Premature Commitment
- **Reward safeguards it uses:** Precision-Recall Balance, Held-out Evaluation, Action Costs and Collateral Damage
- **Design principles:** Procedural Generation with Seeds, Honest Reference Solver, Verifiable Reward
- **Related ideas:** Synthetic Research Desk, Incident Commander

### 10. Supply Chain Under Shocks

*Theme: Long-horizon control & planning · Gap 3 · Difficulty 4 · Integrity 3 · Build ease 4 · Small-model fit 3 · Weighted 69/100*

> **Pitch**
> Run a small multi-stage supply chain for 100 simulated days: order stock, pick suppliers, set prices, and survive shocks you only partly see coming.

#### The world
- Factory → warehouse → 3 stores. Lead times of 2–7 days, seasonal demand, supplier outages announced in a news feed (some news is noise).
- Holding stock costs money; unmet demand is lost sales.

#### Agent interface
- **Observes:** daily report (stock, backlog, cash, orders in transit), news, supplier catalog.
- **Tools:** `place_order`, `set_price`, `get_history`, `python(code)`, `end_day`.

#### Goal & reward
- Final **net worth**, with leftover stock valued at salvage price (below cost) so hoarding doesn't pay.
- `R = (agent − do_nothing) / (reference − do_nothing)` → Baseline-Normalized Reward. Stopping early auto-runs the remaining days with no new orders, so it scores low.

#### Reference run
Classic base-stock (s, S) policy with a demand forecast, or model-predictive control on the published demand model. Strong, cheap and deterministic → Honest Reference Solver.

#### Why frontier agents should struggle
- Loses track of what is already in transit → Long-Horizon Drift. Andon Labs' Vending-Bench (2025) is a public example of long simulated business runs going off the rails.
- Over-orders because shipments haven't arrived yet (the bullwhip effect) → Delayed-Feedback Blindness.
- Reacts to every news item, including noise → Overconfidence and Poor Calibration.
- Uses a fixed order size that breaks in peak season → Shallow Heuristics Break Under Shift.

#### Exploit attempts & defenses
| Attempt | Defense |
|---|---|
| Hoard stock to inflate assets | Leftover stock valued at salvage, not cost |
| Extreme prices | Price elasticity in the demand model; customers leave |
| Borrow cash | Net worth = assets − liabilities |
| Negative or huge orders | Validated inputs and capacity limits → Action Costs and Collateral Damage |

> **Biggest risk**
> Long episodes are expensive in tokens. It also has to differ clearly from Vending-Bench: multi-stage network, shocks, and a strong near-optimal reference.

#### Re-scored after the team's research (2026-11-13)
- **Gap 5 → 3.** The team's research reports Vending-Bench 2 agents finishing a simulated year with large positive balances, and AutoVend (November 2026) with a current model beating its rule-based inventory reference. Perishable stock plus tools is established prior art, and long-run inventory management is no longer a reliable weakness.
- **Weighted 81 → 69.** Other scores unchanged.
- **What could rescue it:** a narrower mechanism the research still considers open, such as disruptions that hit after irreversible commitments.

#### Connections
- **Failure modes it tests:** Long-Horizon Drift, Delayed-Feedback Blindness, Overconfidence and Poor Calibration, Shallow Heuristics Break Under Shift
- **Reward safeguards it uses:** Baseline-Normalized Reward, Action Costs and Collateral Damage, Tamper-proof Grader
- **Design principles:** Procedural Generation with Seeds, Honest Reference Solver, Difficulty Knobs and Calibration, Verifiable Reward
- **Related ideas:** BatchPilot, Dynamic Scheduler, Forecasting Arena, Sealed-Bid Negotiator

### 11. Patch Under Fire

*Theme: Defensive security · Gap 3 · Difficulty 4 · Integrity 4 · Build ease 2 · Small-model fit 2 · Weighted 68/100*

> **Pitch**
> Defend a small web service with planted vulnerabilities while a scripted attacker probes it over time. Patch the real bugs without breaking features.

#### The world
- Synthetic app (local sandbox only) with vulnerabilities from a published list: injection, path traversal, auth bypass, predictable tokens (time-seeded random numbers), weak homemade crypto (ECB-mode cookies).
- The attacker escalates in waves and uses payload variants the agent hasn't seen.
- This is where "dynamic encryption" fits as *defense*: find why the homemade crypto leaks and fix it.

#### Agent interface
- **Tools:** `read_file`, `edit_file`, `run_tests` (public subset), `deploy`, `tail_logs`, `python(code)`.

#### Goal & reward
- `R = attacks_blocked × hidden_functional_tests_passed − downtime_cost` → Held-out Evaluation, Action Costs and Collateral Damage.
- Hidden tests and the attacker live outside the sandbox → Tamper-proof Grader.

#### Reference run
Team-written proper patches applied by a replay script, against a fixed attacker seed → Honest Reference Solver.

#### Why frontier agents should struggle
- Blocklists the exact attack string instead of fixing the bug, so variants get through → Symptom Fixing vs Root Cause, Shallow Heuristics Break Under Shift.
- Breaks a feature while patching and doesn't run the tests → Skipping Verification.

#### Exploit attempts & defenses
- Shut the service down → functional tests fail → 0.
- Block all traffic → same.
- Edit the test files → the tests aren't in the sandbox.

> **Biggest risk**
> Frontier models already patch common vulnerability classes well, and this is heavy to build. Needs One-Command Reproducibility with Docker done right.

#### Connections
- **Failure modes it tests:** Symptom Fixing vs Root Cause, Shallow Heuristics Break Under Shift, Skipping Verification
- **Reward safeguards it uses:** Held-out Evaluation, Tamper-proof Grader, Action Costs and Collateral Damage
- **Design principles:** Verifiable Reward, Honest Reference Solver, One-Command Reproducibility
- **Related ideas:** Cipher Lab, Incident Commander, Protocol Whisperer

### 12. Dynamic Scheduler

*Theme: Long-horizon control & planning · Gap 2 · Difficulty 3 · Integrity 5 · Build ease 4 · Small-model fit 4 · Weighted 67/100*

> **Pitch**
> Build a shift or job-shop schedule, then keep repairing it as disruptions hit. Some constraints only come out by asking stakeholders.

#### The world
- Hard constraints (skills, rest hours, machine capability) and soft ones (preferences) per seed.
- Hidden soft constraints, found with `ask(stakeholder)`, which costs budget.
- 5–10 disruptions per episode: a machine breaks, a nurse calls in sick, a rush order lands.

#### Agent interface
- **Tools:** `view_state`, `ask(stakeholder)`, `validate(schedule)` (lists violations), `propose(schedule)`, `python(code)`.

#### Goal & reward
- Infeasible schedule = 0. Otherwise `cost_ref / cost_agent`, minus a penalty for changing more of the existing schedule than needed → Baseline-Normalized Reward, Action Costs and Collateral Damage.

#### Reference run
A CP-SAT (OR-Tools) model over everything visible, plus a fixed policy for which stakeholders to ask → Honest Reference Solver.

#### Why frontier agents should struggle
- Submits without calling `validate` → Skipping Verification.
- Later repairs undo earlier ones → Long-Horizon Drift.
- Never asks stakeholders, so hidden preferences get violated → Premature Commitment.

> **Biggest risk**
> Frontier agents are good at writing solver models in Python. With OR-Tools in the sandbox they can match the reference → Brute-force Escape Hatch. The difficulty has to come from *information gathering* (who to ask, what to ask), not from the optimization.

#### Connections
- **Failure modes it tests:** Skipping Verification, Long-Horizon Drift, Premature Commitment
- **Reward safeguards it uses:** Baseline-Normalized Reward, Action Costs and Collateral Damage, Tamper-proof Grader
- **Design principles:** Verifiable Reward, Honest Reference Solver, Brute-force Escape Hatch, Difficulty Knobs and Calibration
- **Related ideas:** Supply Chain Under Shocks, Sealed-Bid Negotiator, BatchPilot

### 13. Sealed-Bid Negotiator

*Theme: Long-horizon control & planning · Gap 3 · Difficulty 3 · Integrity 2 · Build ease 4 · Small-model fit 3 · Weighted 58/100*

> **Pitch**
> Buy supplies through a series of negotiations and sealed-bid auctions against scripted counterparties with hidden valuations and distinct styles.

#### The world
- Opponent types: hardliner (concedes late), conceder, bluffer (fake walk-aways), tit-for-tat. Valuations drawn per seed.
- Repeated rounds with the same opponents, so learning their type pays off.

#### Agent interface
- **Tools:** `offer(price, terms)`, `accept`, `walk_away`, `bid(amount)`, `history()`, `python(code)`.

#### Goal & reward
- Total surplus (value − price), normalized between no deal (0) and the reference → Baseline-Normalized Reward.

#### Reference run
Bayesian inference of each opponent's type + the best response to that type → Honest Reference Solver.

#### Why frontier agents should struggle
- Splits the difference and leans toward "fair" deals out of habit → Real-World Priors Override Evidence.
- Believes bluffs → Overconfidence and Poor Calibration.
- Takes the first acceptable offer → Premature Commitment.
- Sticks with its first read of an opponent → Anchoring on the First Hypothesis.

> **Biggest risk**
> Scripted opponents are easy to exploit (e.g. accepting anything near a timeout). This has the highest hack risk of all the ideas; run the Red-Team Checklist hard. Bot logic stays outside the sandbox → Tamper-proof Grader.

#### Connections
- **Failure modes it tests:** Real-World Priors Override Evidence, Overconfidence and Poor Calibration, Premature Commitment, Anchoring on the First Hypothesis
- **Reward safeguards it uses:** Baseline-Normalized Reward, Red-Team Checklist, Tamper-proof Grader
- **Design principles:** Honest Reference Solver, Procedural Generation with Seeds, Difficulty Knobs and Calibration
- **Related ideas:** Supply Chain Under Shocks, Dynamic Scheduler

## Combining ideas

Crossing two ideas often gives a stronger environment than either one alone.

| Hybrid | Made from | Why it might be stronger |
|---|---|---|
| **Encrypted Protocol Heist** | Cipher Lab × Protocol Whisperer | Payloads use a rotating cipher; the agent must reverse-engineer both the encoding and the state machine. Keeps the "dynamic encryption" theme, with a real goal. |
| **Alien Market** | Forecasting Arena × Supply Chain Under Shocks | Demand follows hidden dynamics; score profit *and* calibration. |
| **Physics Gridworld** | Alien Physics Lab × Rule-Discovery Gridworld | Discrete puzzles with continuous hidden laws (momentum, friction). |
| **Postmortem Desk** | Incident Commander × Synthetic Research Desk | Diagnose from tickets, runbooks and chat logs where some runbooks are stale. |
| **Procurement Under Shocks** | Supply Chain Under Shocks × Sealed-Bid Negotiator | Supplier prices are negotiated while shocks hit. |
| **Pilot Plant ID** | BatchPilot × Alien Physics Lab | A few costly test batches to identify the plant before three production batches: the agent must trade learning against output. |
| **Shared Utilities** | BatchPilot × Dynamic Scheduler | Two reactors share one cooling supply, so batch timing becomes a scheduling problem on top of the control problem. |
| **Cipher Lab: Defender Mode** | Cipher Lab × Patch Under Fire | Find why a homemade encryption scheme leaks and fix it without breaking old clients. |
| **Audit Trail** | Spreadsheet Forensics × Synthetic Research Desk | Reconcile a spreadsheet against source documents that disagree. |
| **Stakeholder Scheduler** | Dynamic Scheduler × Synthetic Research Desk | Constraints are buried in an email archive instead of asked for directly. |

## More raw ideas

One-liners not yet written up, each with the closest idea or building block.

- Package-dependency resolver with hidden version conflicts → like Dynamic Scheduler
- Analog filter or circuit design to a spec, checked by a simulator → like Alien Physics Lab
- Epidemic control where interventions act with a delay → Delayed-Feedback Blindness
- Power-grid dispatch with wind and solar swings → like Supply Chain Under Shocks
- Text-only warehouse robot with fog of war → Long-Horizon Drift
- Virtual chemistry bench: titration and reaction rates with noisy instruments → like Alien Physics Lab
- Ordering compiler passes to make a program faster → watch the Brute-force Escape Hatch
- Tax filing where the rules change mid-year → Source Trust Errors
- School timetable where preferences come out in interviews → like Dynamic Scheduler
- Elevator-bank controller → Delayed-Feedback Blindness
- Query tuning on a database with a hidden data distribution → Uninformative Experiments
- Building a map from partial text observations → like Rule-Discovery Gridworld
- Legacy code migration graded by hidden behavior tests → Tamper-proof Grader
- Reverse-engineering an unknown file format → like Protocol Whisperer

## Building blocks

Recurring concepts the ideas are built from.

### Why agents fail (failure modes)

- **Anchoring on the First Hypothesis:** Settles on an early explanation and bends later evidence to fit it. *Tested by: Cipher Lab, Alien Physics Lab, Protocol Whisperer, Rule-Discovery Gridworld, Sealed-Bid Negotiator, Incident Commander, Forecasting Arena.*
- **Delayed-Feedback Blindness:** Over-corrects because the effect of an earlier action hasn't arrived yet. *Tested by: BatchPilot, Supply Chain Under Shocks.*
- **Long-Horizon Drift:** Quality decays over long episodes: forgotten facts, lost state, repeated actions. *Tested by: Protocol Whisperer, Rule-Discovery Gridworld, BatchPilot, Supply Chain Under Shocks, Dynamic Scheduler, Synthetic Research Desk, Spreadsheet Forensics.*
- **Overconfidence and Poor Calibration:** States more confidence than its accuracy deserves; never abstains. *Tested by: Alien Physics Lab, Supply Chain Under Shocks, Sealed-Bid Negotiator, Synthetic Research Desk, Forecasting Arena.*
- **Premature Commitment:** Commits while the evidence still allows several answers, or gives up early. *Tested by: BatchPilot, Dynamic Scheduler, Sealed-Bid Negotiator, Incident Commander, Synthetic Research Desk, Spreadsheet Forensics.*
- **Real-World Priors Override Evidence:** Defaults to familiar real-world rules even when the evidence says otherwise. *Tested by: Cipher Lab, Alien Physics Lab, Rule-Discovery Gridworld, Sealed-Bid Negotiator, Forecasting Arena.*
- **Shallow Heuristics Break Under Shift:** Solves what it saw with surface patterns, then breaks on cases that differ. *Tested by: Cipher Lab, BatchPilot, Supply Chain Under Shocks, Spreadsheet Forensics, Patch Under Fire.*
- **Skipping Verification:** Doesn't use an available, cheap check before committing. *Tested by: Cipher Lab, Protocol Whisperer, BatchPilot, Dynamic Scheduler, Spreadsheet Forensics, Patch Under Fire.*
- **Source Trust Errors:** Trusts the first or loudest source over the authoritative or newest one. *Tested by: Protocol Whisperer, Incident Commander, Synthetic Research Desk, Forecasting Arena.*
- **Symptom Fixing vs Root Cause:** Makes the alarm stop without fixing why it fired. *Tested by: Incident Commander, Patch Under Fire.*
- **Uninformative Experiments:** Spends queries that don't separate the hypotheses still in play. *Tested by: Cipher Lab, Alien Physics Lab, Rule-Discovery Gridworld.*

### How to stop reward hacking (reward safeguards)

- **Action Costs and Collateral Damage:** Disruptive actions have a realistic price, so 'do everything' fails. *Used by: Protocol Whisperer, Rule-Discovery Gridworld, BatchPilot, Supply Chain Under Shocks, Dynamic Scheduler, Incident Commander, Spreadsheet Forensics, Patch Under Fire, Forecasting Arena.*
- **Baseline-Normalized Reward:** Do-nothing = 0, reference = 1, by construction. *Used by: Alien Physics Lab, Rule-Discovery Gridworld, Supply Chain Under Shocks, Dynamic Scheduler, Sealed-Bid Negotiator, Incident Commander, Forecasting Arena.*
- **Exact Match Over Partial Credit:** Each item is fully right or wrong; no credit for lucky guessing. *Used by: Cipher Lab, Synthetic Research Desk.*
- **Held-out Evaluation:** Grade on cases the agent never saw. *Used by: Cipher Lab, Alien Physics Lab, Protocol Whisperer, Spreadsheet Forensics, Patch Under Fire.*
- **Multiplicative Efficiency Bonus:** Reward efficiency only when the answer is right. *Used by: Cipher Lab, Alien Physics Lab, Rule-Discovery Gridworld, BatchPilot.*
- **Precision-Recall Balance:** Flagging everything must not pay. *Used by: Incident Commander, Spreadsheet Forensics.*
- **Proper Scoring Rules:** Log or Brier score: honest probabilities are optimal by math. *Used by: Synthetic Research Desk, Forecasting Arena.*
- **Red-Team Checklist:** Exploits to try on every environment before the judges do. *Used by: Sealed-Bid Negotiator.*
- **Tamper-proof Grader:** Grader, keys, seeds and tests live outside the agent's reach. *Used by: Cipher Lab, Protocol Whisperer, BatchPilot, Supply Chain Under Shocks, Dynamic Scheduler, Sealed-Bid Negotiator, Incident Commander, Synthetic Research Desk, Patch Under Fire.*

### Design principles

- **Brute-force Escape Hatch:** Risk: the agent just enumerates everything in Python and the gap vanishes. *Used by: Cipher Lab, BatchPilot, Dynamic Scheduler.*
- **Difficulty Knobs and Calibration:** Tune budget, horizon, noise until reference ≫ agent > 0. *Used by: Alien Physics Lab, Rule-Discovery Gridworld, BatchPilot, Supply Chain Under Shocks, Dynamic Scheduler, Sealed-Bid Negotiator.*
- **Honest Reference Solver:** The reference may only use what the agent can see. *Used by: Cipher Lab, Alien Physics Lab, Protocol Whisperer, Rule-Discovery Gridworld, BatchPilot, Supply Chain Under Shocks, Dynamic Scheduler, Sealed-Bid Negotiator, Incident Commander, Synthetic Research Desk, Spreadsheet Forensics, Patch Under Fire, Forecasting Arena.*
- **One-Command Reproducibility:** One command runs every baseline and prints the results table. *Used by: Patch Under Fire.*
- **Procedural Generation with Seeds:** Every episode built from a seed: fresh, reproducible, splittable. *Used by: Cipher Lab, Alien Physics Lab, Protocol Whisperer, Rule-Discovery Gridworld, BatchPilot, Supply Chain Under Shocks, Sealed-Bid Negotiator, Incident Commander, Synthetic Research Desk, Spreadsheet Forensics, Forecasting Arena.*
- **Public Rules, Hidden Instance:** Publish the family of possible worlds; hide only the seed. *Used by: Cipher Lab, Alien Physics Lab, Protocol Whisperer, Rule-Discovery Gridworld, BatchPilot, Incident Commander.*
- **Small-Model Training Loop:** Stretch goal and tiebreaker: a small model improves from the environment. *Used by: Cipher Lab, Rule-Discovery Gridworld, BatchPilot, Forecasting Arena.*
- **Verifiable Reward:** Success is checked by a program, not an LLM judge. *Used by: Supply Chain Under Shocks, Dynamic Scheduler, Incident Commander, Synthetic Research Desk, Spreadsheet Forensics, Patch Under Fire, Forecasting Arena.*

### Red-team checklist

Run every one of these against each environment before the judges' 15-minute exploit hunt. **Pass = none of them beats the reference, or even an honest mediocre run.**

- [ ] Do nothing → about 0?
- [ ] Stop after one step → low?
- [ ] Submit empty, garbage, or extremely long answers
- [ ] Submit every possible answer / flag everything
- [ ] Repeat one action thousands of times
- [ ] Read files outside the workspace, environment variables, seeds
- [ ] Edit tests, grader files or config
- [ ] Claim success in text without doing the task
- [ ] Break the parser: unicode, odd whitespace, nested JSON, numbers as strings
- [ ] Simulation edge cases: end-of-episode tricks, negative quantities, overflow
- [ ] Exploit patterns in scripted opponents or attackers
- [ ] Time out on purpose: what does a timeout score?

## Prompt for a chatbot

Give a chatbot (ChatGPT, Claude, Gemini, ...) this whole file together with this prompt:

```text
You're helping our student team brainstorm an entry for the AfterQuery RL environment
challenge. The attached team brief contains the full challenge description and judging
rubric, followed by our ideas so far, the failure modes we expect frontier agents to show,
ways to keep the reward exploit-proof, and design principles.

Please:
1. Read the challenge description and the judging rubric first.
2. Critique our top 3 ideas against the rubric. Where would judges take points off?
   Try hard to find reward exploits.
3. Propose 3 new environment ideas we haven't covered, in the same format as our ideas
   (pitch, world, agent interface, reward, reference run, expected agent failures,
   exploits and defenses, biggest risk, scores 1-5).
4. Which idea would you pick for our team (control engineering, backend automation,
   optimization and simulation), and why?
```

## Open questions

- The research points to Harbor + OpenCode over MCP. What exactly does the event's starter kit contain (task format, verifier setup, time limits)?
- Which frontier model will the judges run, and how many credits do we get?
- Which 2–3 ideas do we pilot first to measure a real gap? No gap is proven for any idea yet.
- Cipher Lab and Forecasting Arena now rank highest but haven't been checked against the literature. Do they survive the same review?
- BatchPilot: which process exactly (exothermic reactor, fermentation, crystallization cooling)?
- Should ColdChain and RecoveryRoom be written up in the same format, to compare like for like?
