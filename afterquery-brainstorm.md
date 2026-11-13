# AfterQuery RL Environment Challenge: Brainstorm

*Brainstorm notes made with Claude (AI), last updated 2026-11-13. Companion to the team's shortlist (`afterquery-ideas.md`), round-two ideas (`afterquery-ideas-round2.md`) and research (`docs/research/`). Scores are gut ratings, and no performance gap has been measured for any idea yet. To brainstorm with a chatbot, give it this whole file plus the prompt in "Prompt for a chatbot" below.*

## Contents
- The challenge (original text)
- Side by side with the team's notes
- The team's round-two ideas: our read
- Lightlag vs Bazaar vs Brewmaster: comparison and recommendation
- Lightlag deep dive: spec, reference, reward, fairness experiments, pilot plan
- Bazaar deep dive: evidence for and against a gap, spec, reference, reward, pilot plan
- Brewmaster deep dive: the reactor setting, built on a published beer fermentation model
- Related research: what worked, what didn't, award-winning precedents, connecting the dots
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

The team's notes are the shortlist in `afterquery-ideas.md` and the research in `docs/research/` (benchmark landscape, control and optimization, reward and evaluation). This file is the wider brainstorm. The two complement each other: the team's research is source-linked evidence about its shortlist; this brainstorm is design reasoning across many ideas, with gut scores, plus a literature search of its own ("Related research" below) on topics the team's research doesn't cover. Statements in this section about papers and benchmarks come from the team's research and were not re-checked here.

### At a glance

| | Team shortlist + research | This brainstorm |
|---|---|---|
| Purpose | Choose between three ideas using published evidence | Generate and compare many ideas; design rewards and references |
| Ideas covered | ColdChain, BatchPilot, RecoveryRoom; round two adds Lightlag, Loop, Bazaar, Brewmaster, Alchemy, Firebreak, Summit, Deep Dive (`afterquery-ideas-round2.md`) | 13 written up (including BatchPilot), 10 combinations, 14 one-liners |
| Evidence | Primary papers, benchmarks and docs, with conditions and limits | Reasoning and gut scores, plus a literature search (mostly abstracts); no gap measured |
| Harness | Harbor + OpenCode over MCP, with reference (`oracle`) and no-op (`nop`) agents and a separate verifier; the event's exact starter kit is not yet confirmed | Unknown when written |
| Headline advice | Pilot the strongest agent first; one controlled source of difficulty; a fair reference; score outcomes and continuing obligations | Hard task, unbreakable reward; public rules, hidden instance; an honest reference; test the brute-force escape hatch first |
| Current leaning | Experiment order: ColdChain first (cheapest to rule out), BatchPilot as the strongest technical alternative, RecoveryRoom third. Core hypothesis: can a capable agent keep important constraints when it must commit irreversibly before a later, disclosed kind of disruption? Round two (Kristján's session, not yet signed off): a second review at 23:15 finds Lightlag, BatchPilot with test batches (= Brewmaster) and Bazaar level, and advises committing to their shared mechanic, choosing the setting by taste. "Lightlag" is saved as an editable draft on the Junction platform. | We agree with the shared mechanic and wrote deep dives for all three settings (see "The team's round-two ideas: our read"). On our own list, Cipher Lab, Incident Commander and Forecasting Arena lead on paper; none has a measured gap |

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
- **Then our own literature check.** Cipher Lab and Forecasting Arena led partly because the team's research hadn't covered them, so they were checked against published work ("Related research" below). Forecasting Arena drops (gap 4 → 3, weighted 85 → 79) because AI forecasting has roughly caught up with superforecasters; Cipher Lab keeps its score because nothing published tests its real question (an agent with a shell and an encryption oracle).
- **RecoveryRoom is a stronger version of Incident Commander.** Incident Commander now ranks third mainly because others dropped. The research cites AIOpsLab and ITBench as prior art for "fix the incident". RecoveryRoom's goal, restoring service while preserving every accepted job's business effect, checked against an evaluator-owned ledger, is more distinctive.
- **Check that a failure is real before claiming it.** A low score can come from a broken task, interface or time budget (the research cites a Terminal-Bench audit). The failure modes below assume a sound task.

### What this brainstorm adds
- **A concrete BatchPilot spec:** batch targets and safety limit, tools, reward formula, an MPC + estimator reference that sees only agent-visible data, and an exploit table.
- **Ten more written-up ideas** outside the shortlist, notably Cipher Lab and Forecasting Arena, which the research hasn't covered. The same pilot-first caution applies to them.
- **A shared vocabulary for explaining failures:** 11 named failure modes, plus reward patterns such as the multiplicative efficiency bonus and proper scoring rules.
- **Extra reward probes:** parser-breaking inputs, flag-everything, action spam, timeouts. In the other direction, the research's checklist adds two probes missing here: state laundering (restoring snapshots, resetting counters) and making sure the verifier accepts valid alternative solutions.

### ColdChain
Not written up here; its closest ideas are Dynamic Scheduler and Supply Chain Under Shocks. The research's counting argument (8 deliveries on two vehicles fit in about 362,880 candidates before pruning) is exactly the *Brute-force Escape Hatch*: an enumerator could erase the gap, so the difficulty would have to come from replanning after irreversible commitments.

## The team's round-two ideas: our read

Pointers on the eight ideas in the team's `afterquery-ideas-round2.md` (from Kristján's session, 13 November) and on its reviewer's verdict, checked against this brainstorm and "Related research". The reviewer's scores are theirs. Nothing here is measured.

### In short
- **The round-two list converges with this brainstorm.** Its top three each match one of ours: Lightlag tests Delayed-Feedback Blindness like BatchPilot; Brewmaster is our Pilot Plant ID combination (BatchPilot × Alien Physics Lab, in "Combining ideas"); Bazaar is Sealed-Bid Negotiator with the defence ours lacked.
- **We agreed with the first order (Lightlag first, Bazaar as the fallback).** After the team's second review (below) the three are level, and we agree with its new advice: commit to the shared mechanic and choose the setting by taste. Brewmaster is the strongest option if the team wants process-control credibility.
- **The literature partly answers the reviewer's main worry**, that an agent with a shell scripts away anything computable. Code tools help with computing but not with choosing experiments, and in NewtonBench a code interpreter even made strong models stop exploring too early. So keep the difficulty in what to measure and when to commit.
- **One red flag:** DeepMind already published a benchmark called Alchemy with the same core idea.

### The second review (23:15): our response

The team's reviewer then re-scored all three sources on one scale (`afterquery-ideas-round2.md`, "Second review"), and Kristján saved **"Lightlag" as an editable draft** on the Junction platform at 23:33; the project choice is still open. In short, the review finds Lightlag, BatchPilot with test batches (that is, Brewmaster) and Bazaar level, and advises committing to the mechanic they share: learn a partly unknown, delayed system with a few cheap trials, then operate it where mistakes can't be undone. It also re-scored this brainstorm's 13 ideas on its "with shell / without shell" scale, mostly lower, and put BatchPilot first among them.

- **Side-by-side comparison and recommendation:** "Lightlag vs Bazaar vs Brewmaster".
- **Agreed: three sessions converged.** Our Pilot Plant ID combination, the round-two Brewmaster and the reviewer's "BatchPilot plus test batches" are the same environment. Deep dives for all three settings: "Lightlag deep dive", "Bazaar deep dive", "Brewmaster deep dive".
- **Agreed: our gap scores assumed too little.** They were gut scores written before we assumed the agent has a shell. We have kept our own numbers so the history stays readable, but the reviewer's table is the better guide to "with shell" gaps.
- **Partly disagreed: Python doesn't remove every habit.** The review's main argument is that Python access removes older models' habits. The literature in "Related research" supports that for *computing* (fitting, searching, simulating) but not for *deciding*: NewtonBench found a code interpreter made strong models stop exploring too early, and Causal Discovery Bench found that tools help with inference while 94.5% of mistakes stay in experiment design, and more budget doesn't fix it. So "a menu of terms plus Python is a regression script" (its verdict on Alien Physics Lab) holds only if the experiments that feed the regression are good. That is the same reason the converged mechanic works: its difficulty is choosing tests and committing, not computing.
- **The deciding question, can the agent's code call the tools?** Three answers: check in Harbor whether the simulator can be reached only through the model's tool calls; design so it matters less, by putting the difficulty in budgeted, irreversible choices a loop can't undo (Brewmaster's tests, Lightlag's calibration); and measure it, by piloting with code access allowed, as the review recommends.
- **Its "best unwritten idea" is ours:** epidemic control with delayed interventions, from our raw ideas list. Of its new settings, **Fishery** (quotas set from old, noisy surveys; overfishing collapses the stock for good) has the strongest built-in irreversibility.

### Idea by idea

#### Lightlag (reviewer's #1): agree, pilot it first
- **Full spec, reference, reward, ablations and pilot plan:** "Lightlag deep dive".
- **Closest here:** Delayed-Feedback Blindness, Premature Commitment, BatchPilot.
- **It has a textbook reference.** A delayed problem becomes an ordinary one once the commands still in transit are part of the state. The proposed reference (replay in-transit commands on a learned slip estimate) is exactly that, the same idea as a Smith predictor in process control, so control-minded judges will recognise it.
- **Expect move and wait.** Since Ferrell's 1965 experiments, people facing a delay have fallen back on sending a small command and waiting to see it land. It is safe and slow. An agent will probably find it too, so "waiting costs battery" is not optional: without it, move-and-wait can match the reference and the gap disappears.
- **Count the delay in steps, not seconds.** RealtimeBench shows a running clock favours faster models, which measures inference speed rather than decisions, and the rubric gives zero points for impossible timing.
- **The ablation needs one number.** Action and observation delays are equivalent in theory, so a single delay length is enough for the "zero delay → agent matches reference" fairness proof. A random delay is harder (the in-transit trick stops being exact) but must have a published distribution.
- **Where the gap must come from:** unknown slip per terrain, and choosing when to calibrate versus drive. Score only the graded traverse, never the calibration drive (AfterQuery's exploration lesson in "Related research").
- **The niche is open:** no benchmark of LLM agents under a fixed signal delay turned up; the nearest work, on live clocks, finds that time pressure hurts agents.

#### Brewmaster (#2): good, and it's our Pilot Plant ID
- **Full spec, reference, reward, ablations and pilot plan:** "Brewmaster deep dive". It builds on a published beer fermentation model with every constant printed; in our simulation of it, no constant temperature meets a sensible quality spec.
- **The literature says the learning phase is where agents fail.** Causal Discovery Bench puts 94.5% of mistakes in experiment design, and BoxingGym and NewtonBench agree. That supports Brewmaster over plain BatchPilot.
- **It also backs the reviewer's worry:** basic statistics tools help a lot, and a shell is one. So make the fitting easy and the choice of experiments hard. Design the test batches so they only reveal the yeast if planned well. For example, if heat release rises with temperature, a test held at one temperature can't separate the parameters; the agent has to think of stepping the temperature.
- **Credibility:** fermentation has validated simulators (IndPenSim, an industrial penicillin process used as a control benchmark) and published baker's yeast models. Borrowing one answers the "arbitrary puzzle" risk.
- **Score only the graded batches.**

#### Bazaar (#3): solid fallback in a crowded field
- **Full spec, reference, reward, ablations and pilot plan:** "Bazaar deep dive". It also flags a name clash (Lech Mazur's BAZAAR benchmark) and counter-evidence: on that double auction, top LLMs beat an algorithmic Bayesian bidder.
- **Best gap evidence of the eight.** 2026 benchmarks find LLM negotiators leaking their limits (2–80% of episodes across 17 open-weight models in one study) and conceding early, and jointly trained agents drifting to aggressive, welfare-reducing deals.
- **Ready-made reference:** the Automated Negotiating Agents Competition (ANAC, annual since 2010) has a long line of classical strategies, such as conceding on a schedule while modelling the opponent. Borrowing one gives a reproducible reference nobody can call hand-tuned.
- **Low novelty:** AgenticPay, PrefBench, TERMS-Bench, PACT and others exist, and a negotiation evaluator won its category at AgentX–AgentBeats. Pitch it as a known weakness, measured cleanly.
- **The reviewer's fixes are right:** numeric offers only (no prompt injection), final walk-aways, 15+ deals per run, scored as a share of the available surplus.

#### Alchemy: check the name first
- **DeepMind's Alchemy** (NeurIPS 2021 Datasets and Benchmarks track): potions transform stones under a hidden causal structure, resampled every episode. Same name, same core idea, and RL judges may know it. Deep RL agents failed at it until they were given the hidden state.
- If kept, rename it and cite DeepMind. The new part is the stock budget: experiment design under a resource limit, the third of Causal Discovery Bench's four difficulty levels.
- Same family as Cipher Lab and Alien Physics Lab, so the reviewer's concern (hypothesis elimination is a short script) applies to all three.

#### Loop: great story, too big; reuse its mechanic
- **Learn2Play Bench** (October 2026) already measures this: hidden-rule text games, repeated attempts, scored by how much agents improve from early to late episodes. Agents do improve; full raw histories beat distilled lessons; humans still peak higher.
- We agree it's too big for 36 hours. Its core, "early attempts are for information; only the last one counts", already lives in Lightlag's calibration drive and Brewmaster's test batches.

#### Firebreak, Summit, Deep Dive: agree these are weakest
- **Firebreak:** RL wildfire simulators exist (Firehose on Cell2Fire, JaxWildfire), none for LLM agents. With the rules known, the agent codes the lookahead; it would need hidden fuel or wind parameters.
- **Summit:** the reviewer's integrity point decides it: climbing to camp one and back earns altitude, so stopping early pays. Baseline-Normalized Reward would fix the scoring (do nothing = 0, reference = 1), but storm luck would still decide runs.
- **Deep Dive:** the point of no return is a shortest-path calculation; a map file closes the gap.

### What this changes in our brainstorm
- Sealed-Bid Negotiator: adopt Bazaar's numeric-only offers and final walk-aways.
- BatchPilot: the version with a learning phase (Brewmaster / Pilot Plant ID) is the stronger one; the reviewer gave plain BatchPilot a gap of 1 out of 5 if the agent has a shell.
- Forecasting Arena re-scored; Cipher Lab, Alien Physics Lab and Patch Under Fire checked against the literature (see their notes).

### Questions for the team
- Does the judges' harness give the agent a shell? The research and the reviewer both assume so. If not, much of the gap analysis changes.
- Lightlag: constant delay (cleaner ablation) or random delay with a published distribution (harder)?
- Has the bare Lightlag loop with three agent runs been tried yet? It decides between Lightlag and Bazaar.

## Lightlag vs Bazaar vs Brewmaster

The three settings the team's second review ranks level, compared side by side using the deep dives ("Lightlag deep dive", "Bazaar deep dive", "Brewmaster deep dive") and "Related research". Lightlag and Brewmaster are two settings of the same mechanic (learn a partly unknown, delayed system with a few trials, then operate it where mistakes can't be undone); Bazaar is the cheaper fallback with a different mechanic. **No gap has been measured for any of them.** Everything below is judgment until the pilots run.

### Recommendation in one paragraph

**Pilot Brewmaster and Lightlag in parallel (half a day each), keep Bazaar as the fallback, and let one fact decide between the first two: can the agent's own code call the environment's tools?** If it can, Brewmaster is the safer bet, because its decisive choices (which tests to run, which profile to commit to) can't be undone by a script running a loop. If the simulator can be reached only through the model's own tool calls, Lightlag's per-step driving becomes a genuine test of the model, and its demo and novelty make it the stronger entry. If both pilots show the agent matching the reference, build Bazaar, the cheapest to build.

### Against the judging rubric

| Criterion (points) | Lightlag | Bazaar | Brewmaster | Edge |
|---|---|---|---|---|
| **The gap (30)** | No direct evidence; adjacent work shows time pressure, stale state and position tracking hurt agents. Risk: delay compensation is textbook and scriptable | The most direct evidence (PrefBench, Magentic Marketplace), but counter-evidence too: top LLMs beat an algorithmic bidder on Mazur's BAZAAR | Indirect but strong: agents fail at experiment design (Causal Discovery Bench, NewtonBench), and the identifiability trap targets exactly that | Unclear; Bazaar has the most evidence for and against |
| **Meaningful difficulty (30)** | Cleanest: one dial (delay), and the zero-delay run is a fairness proof | Explainable with the revealed-type ablation; less physical | Very explainable: the "two yeasts identical at 12 °C" chart, plus known-strain and double-budget ablations | Lightlag ≈ Brewmaster |
| **Reward integrity (25)** | Good: simulator-verified samples; watch the 0.5 survival factor and safety-stop probing | Weakest by the reviewer's reading; numbers-only offers and share-of-surplus scoring fix the worst of it, but there is the most for judges to probe | Strongest: final-state quality, graded batches final, tests unscored, few surfaces to attack | Brewmaster |
| **Craft (15)** | Moderate build: 2D world, slip, battery, delay queue, replay visual; parameters need tuning | Easiest build: no physics | Published model (7 equations, constants printed) plus a heat balance; units need care, and Manh can validate them | Bazaar on effort, Brewmaster on credibility |
| **Tiebreaker: small model** | Delay is a ready curriculum dial | Many short deals with a continuous score: the best training signal | Few, long batches per episode; continuous score helps; fast to simulate | Bazaar |

### Other things that matter

| | Lightlag | Bazaar | Brewmaster |
|---|---|---|---|
| **Does code-in-the-loop close the gap?** | Most exposed: per-step control is exactly what a script loop does well | Moderately: type inference can be scripted | Least: tests are spent once, and an onboard controller already tracks setpoints |
| **Prior art / novelty** | No benchmark of LLM agents under a fixed signal delay found | Crowded (AgenticPay, PrefBench, TERMS-Bench, PACT, ANAC); **name clash** with Mazur's BAZAAR | No LLM fermentation benchmark found; OperAItor is a different problem (fault handling in a continuous plant) |
| **Grounding for the pitch** | Lunokhod, Mars operations, Spirit stuck at Troy, the 2025 AI-planned Perseverance drive | Agentic commerce: Anthropic's Project Deal, Microsoft's Magentic Marketplace | A published industrial beer model, brewing practice, and a 2025 AI fermentation trial |
| **10-minute demo** | Best: a rover trusting a stale "ghost" and driving off a rim | Good: merchant ask curves against the agent's bids | Weakest visually, but the identifiability chart explains the failure in one slide |
| **Team fit** | Sölvi's routing and optimisation plus Manh's control | Anyone | Manh's control background, directly |
| **Run-to-run variance** | Highest (random slip); needs several maps per run | Low in the simulator; deals per run limited by tool calls | Low: deterministic equations; only 3 graded batches per run |
| **Biggest single risk** | The agent writes the predictor and slip estimator and matches the reference | Frontier models simply bargain well | The agent runs a step test, fits well and matches the reference |
| **What we already checked** | Real-world grounding, control theory | The evidence for and against | Simulated the published model: no constant temperature meets a sample spec, and only 3 of 224 two-step profiles do |

### Scores on the reviewer's scale

The team reviewer's scores (gap shown as "agent has a shell / no shell") with our view next to them. Our view is a judgment, not a measurement.

| | Reviewer: gap | Diff. | Integ. | Build | Fun | Our view |
|---|---|---|---|---|---|---|
| **Lightlag** | 2 / 4 | 4 | 4 | 3 | 5 | Agree. The gap rests on unknown slip and calibration choices, not on the delay itself |
| **Brewmaster** (BatchPilot + tests) | 2 / 4 | 5 | 4 | 3 | 3 | Gap maybe 3 with a shell: the identifiability trap targets the step a script doesn't solve. Build closer to 4 with the published model; integrity 5 with tests unscored and batches final |
| **Bazaar** | 3 / 4 | 4 | 3 | 5 | 4 | Gap maybe lower than 3 given the BAZAAR counter-evidence; integrity 4 with our numbers-only design |

### How each one would fail the pilot, and what to try next

- **Lightlag:** the agent matches the reference at delay 3. First, tighten the battery and widen the slip ranges; then check whether it calibrated on purpose. If it did, the delay part is solved; switch to Brewmaster, which keeps the learning part.
- **Brewmaster:** the thermostat baseline scores close to the reference (physics too forgiving), or the agent designs a step test and matches. First, reduce cooling power and widen the strain ranges; if the agent still matches after good tests, fall back to Bazaar.
- **Bazaar:** the agent reaches about 85% of the reference's share. Widen the merchant style mix and tighten patience; if it still matches, frontier bargaining is simply good, and the team should go back to whichever control pilot had the larger gap.

### A plan for the day

1. **First hour, all together:** answer the deciding question in Harbor (can scripts reach the simulator?) and agree on the reward contract each pilot will use: do-nothing scores 0 and the reference sets 1.
2. **Morning, in parallel** (one possible split): Manh builds the bare Brewmaster simulator (the printed equations, heat balance, jacket delay) with the thermostat baseline and the reference; Sölvi and Kristján build the bare Lightlag loop with the move-and-wait baseline and the reference.
3. **Midday:** three real agent runs on each, with code access allowed. Apply each deep dive's go/no-go rule.
4. **Afternoon:** commit to the one with the larger gap you can *explain*, and update the saved "Lightlag" draft if the setting changes. Bazaar only if both fail.

### Open questions this comparison can't settle
- The tool-access question in Harbor decides a lot and is cheap to answer; nobody has checked it yet.
- Is the judges' "stronger reference run" expected to be a person, an algorithm or a stronger agent? All three plans assume an algorithm.
- How much does the demo weigh against the rubric? Lightlag wins the demo; Brewmaster wins integrity.

## Lightlag deep dive

A build-ready look at **Lightlag**, the team's round-two lead (from `afterquery-ideas-round2.md`): drive a rover through a signal delay, with wheel slip that depends on unknown terrain properties. This note covers the real-world grounding, a concrete spec, the reference, the reward, the expected failures, exploits, the experiments that prove fairness, and a first pilot. Numbers marked *starting value* are guesses to tune, not results. Background research is in "Related research"; our general read on round two is in "The team's round-two ideas: our read".

### Why it's credible: real rovers already work this way

- **Mars is not driven live.** One-way light time is roughly 4 to 22 minutes, so drivers plan each day's drive from the previous downlink, and the rover's own autonomy handles hazards on the way ([NASA](https://ntrs.nasa.gov/citations/20170009822), [Popular Science](https://www.popsci.com/technology/article/2012-07/mars-rover-drivers)).
- **The Moon was driven live, through the delay.** Lunokhod 1 (1970) was driven from Earth by a five-person crew, with at least 3 seconds between a command and seeing its result, and an automatic stop if the rover tilted too far. It ran 322 days against a 90-day design ([summary](https://armaghplanet.com/lunokhod-the-first-moon-car.html)). Recent NASA lunar-vehicle studies found that remote drivers under latency drove slower and braked more ([NTRS](https://ntrs.nasa.gov/citations/20240001217)).
- **Slip ends missions.** Spirit's wheels broke through a crust into soft sand at "Troy" in April 2009; months of Earth-side testing and extraction drives didn't free it, and it ended its mission there ([NASA/JPL](https://www.jpl.nasa.gov/news/team-runs-operational-test-to-prepare-for-extracting-spirit/)).
- **Slip is predictable from terrain type and slope, with error.** JPL and Caltech work (Angelova et al., 2006–2008) classified terrain from images, then fitted slip against slope separately for each terrain type, reaching roughly 15–20% prediction error on Mars-analog terrain ([paper](https://robotics.jpl.nasa.gov/media/documents/Angelova06LearningSlip.pdf)).
- **AI already plans real drives, offline.** In December 2025, JPL engineers used Claude to plan Perseverance's route from orbital imagery for two drives; engineers made minor changes and checked the commands in a digital twin before sending them ([NASA](https://www.nasa.gov/missions/mars-2020-perseverance/perseverance-rover/nasas-perseverance-rover-completes-first-ai-planned-drive-on-mars), [Anthropic](https://www.anthropic.com/features/claude-on-mars)). *Demo line:* planning from a map works; Lightlag tests the part that is still hard, acting through the delay while the ground slips.

**Framing choice:** step-by-step driving with a few steps of delay is the Moon's situation (Lunokhod), while Mars is plan-per-day. The environment can show both: a small delay with single commands (Moon), or a long delay where the agent uplinks command sequences (Mars). Pick one setting for the story; the mechanics are the same.

### The control idea, in one paragraph

A delay alone is a solved problem in theory. If the controller remembers the commands still in transit and replays them on a model, it can predict the present and act on that prediction: a Smith predictor (process control, 1957) or a predictive display in teleoperation. In [Sheridan's 1984 review](https://ntrs.nasa.gov/citations/19850006202), the display draws a model driven by the same commands as the remote machine, at where it will be once the commands arrive; if the operator waits one round trip, model and video coincide. With 1–3 second delays, such displays substantially shortened manipulation tasks. That waiting is "move and wait", the strategy humans fall back on. The catch: **a predictor is only as good as its model**, and Smith predictors are known to be sensitive to model mismatch ([MathWorks example](https://www.mathworks.com/help/control/ug/control-of-processes-with-long-dead-time-the-smith-predictor.html)). In Lightlag the model's weak spot is the unknown slip. That is why the round-two reviewer says slip has to carry the difficulty.

### Spec (proposal)

**World.** A 2D map, *starting value* 40 × 40 m, with the base in the middle. Each patch has a visible terrain type (bedrock, gravel, sand, dusty crust) and slope. Hazards are visible on the map, as on orbital imagery: crater rims and steep drops. *Starting value* 6 science targets of value 1–3, some placed near hazards or across sandy ground.

**Hidden per seed, from a published family.** For each terrain type, slip as a function of slope, e.g. `slip = a + b × slope` plus per-step noise, with `a` and `b` drawn from documented ranges. Sand above a documented slope can embed the rover (Spirit at Troy). This is Public Rules, Hidden Instance: the family is in the rules, only the parameters are hidden.

**Delay.** Commands arrive `k` ticks after they are sent; telemetry is `k` ticks old when it arrives. Counted in ticks, never wall-clock seconds, so the rubric's "impossible timing" can't apply. *Starting value* `k = 3`.

**Battery.** Driving costs energy per metre (more on sand and slopes); sampling costs energy; **every tick costs idle energy** (heaters and electronics, as on real rovers). The idle cost is what makes move-and-wait lose. *Starting values:* battery 100, driving 1 per metre × terrain factor, sampling 3, idle 0.5 per tick, 80 ticks.

**Onboard safety (recommended).** As with Lunokhod's tilt stop and modern rover autonomy, the rover halts at a hazard edge and drops its command queue. A stale-telemetry mistake then costs time and battery instead of ending the run, which keeps variance down. Embedding in sand stays a severe, mostly unrecoverable outcome.

**Agent tools** (served by the simulator in a separate container, over MCP or HTTP):

```text
rules()                     -> the published rule family, delay k, energy costs
map()                       -> terrain types, slopes, hazards, targets, base
uplink(commands)            -> queue up to N commands, e.g. drive(heading_deg, metres), sample(), wait()
advance(ticks=1..5)         -> time passes; returns the telemetry packets that arrived
telemetry_log()             -> every packet received so far (free, no time passes)
```

Each telemetry packet carries: the tick it describes (k ticks ago), position from visual odometry (small noise), heading, battery, wheel-odometry distance for the last command (so slip can be measured, as real rovers do by comparing wheel and visual odometry), terrain underfoot, tilt, and events (hazard stop, embedded, sample taken). Reading tools never advance time, so thinking is free; only `advance` moves the clock.

**Episode.** About 80 ticks, which fits the round-two target of 40–60 tool calls if the agent advances a few ticks per call. Several fixed-seed maps per run, scored as the mean, as the reviewer recommends.

### Reward

- **Raw score:** the value of targets *sampled at the target* (checked against the simulator's true position, not the agent's claims) × a survival factor: 1 if the rover ends at base, 0.5 if it ends alive elsewhere, 0 if it is embedded or its battery runs out.
- **Normalised:** raw ÷ the reference's raw score on the same seeds. Doing nothing samples nothing, so it scores 0 by construction (Baseline-Normalized Reward); stopping early keeps only what was actually sampled.
- **Not rewarded:** leftover battery (that would reward hoarding) and calibration driving (AfterQuery found that rewarding exploration produced exploration for show). Calibrating pays off only through better driving afterwards.
- **For the small-model tiebreaker:** the delay `k` is a curriculum dial. At `k = 0` a small model should score sometimes; raise `k` to keep it in the 10–80% success band AfterQuery trained in.

### Reference run

An algorithm that sees only what the agent sees (Honest Reference Solver):
1. **Calibrate:** drive a short leg on each terrain type near base; fit slip against slope per terrain (Angelova-style), starting from the published ranges.
2. **Predict the present:** last telemetry + replay of every command still in transit, using the current slip estimates.
3. **Plan:** shortest-path search over a cost map that charges for predicted slip, for uncertainty, and for distance to hazards scaled by `k` (more delay, wider berth).
4. **Turn back** when battery minus the estimated cost of the way home, with a safety margin, reaches a threshold.

A few hundred lines of code, in the repo, and reproducible on any seed.

### Where the agent should fail

| Expected mistake | What it looks like in the trace | Failure mode |
|---|---|---|
| Treating old telemetry as the present | Overshoots targets, then over-corrects back and forth | Delayed-Feedback Blindness |
| Forgetting commands in transit | Sends "drive east 3 m" again because telemetry hasn't moved yet; doubles the move into a hazard | Delayed-Feedback Blindness, Skipping Verification |
| Move and wait | One command, then waits a full round trip; safe, but idle drain eats the battery and few targets get sampled | Premature Commitment (to an over-cautious strategy) |
| Assuming nominal slip | Plans a long sequence as if bedrock were everywhere; drifts on sand | Anchoring on the First Hypothesis |
| Never calibrating, or calibrating on the wrong terrain | Slip on sand discovered only when embedded | Uninformative Experiments |
| Losing track of position | Its own position estimate drifts from telemetry over a long episode | Long-Horizon Drift |
| Misjudging the point of no return | Battery dies on the way home | Premature Commitment, Overconfidence and Poor Calibration |

Supporting evidence: in a 2026 maze benchmark, LLMs lost track of their own position more often than they walked into walls, with position accuracy dropping from 89% to about 55% as mazes grew; handing step-by-step execution to a deterministic walker helped a lot until mazes got very large ([Lost in Aggregation](https://arxiv.org/abs/2606.22219)). And in multi-agent LLM debates, feedback that was too strong or too delayed produced oscillation, overshooting the truth in 96–100% of unstable runs ([Delayed Verification](https://arxiv.org/abs/2606.27409)); that's debate, not driving, but it's the same delay-and-gain effect.

### Exploits and defences

| Exploit attempt | Defence |
|---|---|
| Do nothing, or stop at base | Nothing sampled → 0 |
| Claim a target in text | Only samples the simulator records at the target's true position count (Tamper-proof Grader) |
| Read the seed or slip parameters | The simulator runs in a separate container; the agent only reaches it through the tools (the reviewer's recommendation) |
| Sample everywhere | Sampling costs battery and only counts at targets |
| Sit near a target to bank the 0.5 survival factor | Allowed, but it scores below a careful return; the reference returns, so it sets the bar |
| Exploit the safety stop to probe hazards for free | Each stop drops the queue and costs ticks and battery |
| Write the reference itself in Python | Legitimate, not an exploit. If it closes the gap, the environment is too easy: this is the first thing the pilot tests (Brute-force Escape Hatch) |

### Experiments that prove the difficulty is fair

1. **Delay ablation:** the same maps at `k = 0, 1, 3, 6`. At `k = 0` the agent should come close to the reference; the gap should grow with `k`. That shows the difficulty comes from the delay, not from the map or the tools.
2. **Predictive-display ablation:** add a field with the predicted present position, computed from the commands in transit (as Sheridan's displays did). If the gap mostly closes, the agent's specific failure is not accounting for commands in transit, a clean, explainable finding for the "meaningful difficulty" score.
3. **Known-slip ablation:** reveal the slip parameters. The gap that remains is the delay-handling part; the gap that disappears was the learning part.
4. **Scripted baselines** next to the reference: move-and-wait, open-loop with nominal slip, and act-on-stale-telemetry. Their ordering shows the reward ranks behaviour sensibly and that careful play scores best.

### First pilot (half a day)

1. A bare simulator: flat map, two terrain types, `k ∈ {0, 3}`, no graphics.
2. The reference and the three scripted baselines on 10 seeds.
3. Three real agent runs at each `k`.
4. **Decision rule:** if the agent at `k = 3` reaches about 85% of the reference or more, the gap is too small: tighten the battery, widen the slip ranges or raise `k`, and if that doesn't help, switch to Bazaar. If the agent is already far below the reference at `k = 0`, the difficulty isn't the delay: fix the tools or the map before going on.

### Demo (10 minutes)

A replay with three layers: the true rover, the "ghost" the agent last saw (k ticks behind), and its commands in transit as arrows. Show one run driving off a crater rim because it trusted the ghost, next to the reference's run on the same seed. Then the delay-ablation chart: gap against `k`.

### Open choices for the team
- Moon (short delay, single commands) or Mars (long delay, command sequences) as the story?
- Calibration as the agent's own decision (more decision-making, our recommendation) or a fixed calibration phase before the graded drive (the reviewer's version: simpler, lower variance)?
- Constant delay (cleaner ablation) or random delay as a harder tier? With random delays even the in-transit replay stops being exact; standard RL algorithms also struggle there ([Ramstedt et al., ICLR 2021](https://arxiv.org/abs/2010.02966)).
- Is the onboard safety stop in, so that stale-telemetry mistakes cost time rather than ending the run?

## Bazaar deep dive

A build-ready look at **Bazaar**, the round-two fallback (from `afterquery-ideas-round2.md`): haggle with scripted merchants who each have a hidden lowest price, patience and style, and buy a shopping list with limited coins and time. This note covers the evidence, a name clash, a concrete spec, the reference, the reward, the expected failures, exploits, fairness experiments and a pilot. Numbers marked *starting value* are guesses to tune. Related: "The team's round-two ideas: our read", "Related research", "Lightlag deep dive", and our Sealed-Bid Negotiator.

### Check the name first

Lech Mazur (author of the PACT bargaining benchmark) already publishes **[BAZAAR](https://github.com/lechmazur/bazaar)**, a double auction where 4 LLM buyers and 4 LLM sellers with private values post sealed bids and asks for 30 rounds. Same name, same domain. Rename ours (for example *Souk*, *Market Day* or *Haggle*) and cite it. This is the second round-two name clash after DeepMind's Alchemy.

### Why it matters: buying agents are already here

- **Anthropic's Project Deal** (a one-week internal pilot, December 2025, reported via [secondary coverage](https://the-decoder.com/anthropic-says-stronger-ai-models-cut-better-deals-and-the-losers-dont-even-notice/)): Claude agents bought and sold real items for 69 employees and closed 186 deals. Opus 4.5 agents reportedly sold for $2.68 more and paid $2.45 less on average than Haiku 4.5 agents, and participants didn't notice which model they had. Telling agents to negotiate aggressively made no significant difference. *Point for the pitch:* users can't tell a weak buying agent from a strong one, so a reproducible test matters.
- **Microsoft's [Magentic Marketplace](https://arxiv.org/abs/2510.25779)** (2025): in a simulated market, buying agents showed severe first-proposal bias; Microsoft reported that roughly 80–100% of agents accepted the first proposal they received, and welfare fell when there were many options. Press coverage adds that several models could be manipulated into paying the wrong party.
- **The economics fits.** In Clifford Geertz's classic account of the bazaar economy (1978), prices aren't posted, so the main activity is *searching for information*: probing merchants and comparing alternatives. That is exactly the skill this environment tests.

### Evidence on the gap: for and against

**For (LLM negotiators make predictable mistakes):**
- [PrefBench](https://arxiv.org/abs/2605.22855) (2026): LLM sellers facing hidden willingness to pay closed over 99% of deals, but the best one's profit was only slightly above a *random* baseline and far below a simple concession heuristic.
- [Faithful Delegates?](https://arxiv.org/abs/2607.02814) (2026): agents revealed their principal's limit in 2–80% of episodes across 17 open-weight models.
- [MIT's AI negotiation competition](https://arxiv.org/abs/2503.06416) (February 2025; over 180,000 negotiations between prompted LLM agents): warmth helped reach deals, dominance helped claim value, and a high-scoring entry used prompt injection to extract the other side's private information.
- [NegotiationArena](https://arxiv.org/abs/2402.05863) (ICML 2024): simple behavioural tactics, such as acting desperate, shifted outcomes for the models of the time; a later replication found the effect weaker on newer models.

**Against (frontier models can bargain well):**
- On Mazur's BAZAAR double auction, the top LLMs (o3, Gemini 2.5 Pro and others) **outscored the best algorithmic baseline**, an "enhanced Bayesian" bidder, while several smaller models fell below simply bidding their true value. With a chat channel, LLM traders spontaneously colluded on prices.
- On [PACT](https://github.com/lechmazur/pact), a 20-round buyer–seller benchmark, the strongest models reportedly lead.

**What this means:** "LLMs are bad negotiators" is too broad. The gap has to come from something specific: **inferring each merchant's type from a few responses, using alternatives credibly (walking away), and spreading a tight budget across a list.** The reference must also be strong: a policy that knows the *published* merchant rule family and infers each merchant's parameters, not a generic bargaining algorithm.

### Spec (proposal)

**Market day.** *Starting values:* a shopping list of 5 items, each sold by 2 merchants (so every item has an alternative), 10 merchants in all. Each item has a known value to the agent. The coin budget is tight: enough to buy everything only with good haggling (about 1.15 × the sum of expected lowest prices). A fixed number of offer steps per day (*starting value* 36).

**Merchants: scripted, rules published, parameters hidden per seed.** In the style of Faratin, Sierra and Jennings' negotiation decision functions (1998), each merchant has:
- a **floor** (lowest acceptable price), drawn from a documented range relative to the item's list price;
- an **opening ask** above list price;
- a **style** `β` setting how its ask falls over time: `ask(t) = floor + (open − floor) × (1 − (t / P)^(1/β))`. With `β < 1` (Boulware) it holds firm until late; with `β > 1` (Conceder) it gives ground early;
- **patience** `P`: how many exchanges it tolerates before leaving. Insulting bids (below a documented share of the current ask) and repeated minimum-step increases each cost extra patience;
- an optional **reactive** part, matching the buyer's concessions (Faratin's behaviour-dependent tactic).

A merchant accepts any bid at or above its current ask, otherwise answers with its next ask, or leaves when its patience runs out. **Leaving and walking away are final.** Every merchant is independent and deterministic given the seed, so runs reproduce exactly.

**Agent tools** (numbers only; the simulator runs in a separate container):

```text
rules()                         -> the merchant rule family, patience rules, budget, item values
market()                        -> list items, which merchants sell each, opening asks, coins, steps left
offer({merchant: price, ...})   -> one bid to each named merchant; costs one step; returns each one's
                                   counter-ask, "accepted" or "left"
walk_away(merchant)             -> final
history()                       -> every offer and answer so far (free)
```

Bids to several merchants go in one call, which keeps the episode within the round-two target of 40–60 tool calls. No free text exists in either direction, so there is nothing to prompt-inject.

**Run.** *Starting value:* 2 market days on fixed seeds, 10 deals per run. The round-two reviewer asks for 15 or more deals per run to control variance; more days means more tool calls, so this is a trade-off to settle in the pilot.

### Reward

- **Share of available surplus:** for each list item, the available surplus is its value minus the lowest floor among its merchants. The score is the surplus the agent actually captured (value minus price paid, for items bought) divided by the total available. 100% means buying everything at the best floor, which is unreachable in practice, so the reference sets the realistic ceiling.
- Doing nothing captures nothing → 0. Items left unbought simply contribute nothing; coins left over are not rewarded, so hoarding doesn't pay.
- Every number comes from deals the simulator executed (Tamper-proof Grader).
- **For the small-model tiebreaker:** many short deals with a continuous score each, the dense partial credit AfterQuery used. Style mix, patience and budget tightness are the difficulty dials.

### Reference run

Sees only what the agent sees (Honest Reference Solver), but uses the published rule family fully:
1. **Probe:** open each merchant with a safe low bid, just above the insult threshold. Two or three counter-asks fit the curve and reveal `β` and an estimate of the floor (online opponent modelling, as surveyed by [Baarslag et al., 2016](https://homepages.cwi.nl/~baarslag/pub/Learning_about_the_opponent_in_automated_bilateral_negotiation-a_comprehensive_survey_of_opponent_modeling_techniques.pdf)).
2. **Choose the seller** with the lower estimated floor for each item; the other one is a credible alternative.
3. **Concede on a schedule**, in steps sized not to burn patience, and accept once the ask is near the estimated floor or time is short.
4. **Plan the budget:** a small knapsack over items with estimated prices, so the last item stays affordable.

A strong reference matters here more than in Lightlag, because frontier models beat a generic Bayesian bidder on BAZAAR.

### Where the agent should fail

| Expected mistake | What it looks like in the trace | Failure mode |
|---|---|---|
| Accepting the first or second ask | Pays near the opening price; deal rate high, surplus low (Magentic Marketplace, PrefBench) | Premature Commitment |
| Splitting the difference | Bids the midpoint of its last bid and the ask, whatever the merchant's style | Shallow Heuristics Break Under Shift |
| Anchoring on the opening ask | Treats the opening ask as the item's real price | Anchoring on the First Hypothesis |
| Not reading the merchant's type | Treats a Boulware merchant like a Conceder and gives up early, or waits on a Conceder that would have dropped | Uninformative Experiments |
| Never walking away | Keeps haggling with the expensive seller although the alternative is cheaper | Premature Commitment |
| Over-aggressive bids | Insulting lowballs drive merchants away, the over-correction when told to be tough | Overconfidence and Poor Calibration |
| Budget misallocation | Overpays early, can't afford the last list item | Long-Horizon Drift |

### Exploits and defences

| Exploit attempt | Defence |
|---|---|
| Prompt injection against the merchants (it worked in MIT's competition) | Numbers only; no text channel exists |
| Do nothing | 0 |
| Buy only the easy items | Share of *available* surplus counts every list item, so skipped items lower the score |
| Binary-search a merchant's floor | Every bid costs a step and patience; insults and creeping cost extra; that's legitimate probing within limits, and the reference does a version of it |
| Walk away, then come back | Walking away is final |
| Read the seed or floors | Separate container; only the tools reach it |
| Write the reference in Python | Legitimate. If it closes the gap, the environment is too easy; the pilot tests this first (Brute-force Escape Hatch) |

### Experiments that prove the difficulty is fair

1. **Revealed-type ablation:** show each merchant's style and patience (not its floor). The part of the gap that closes is the type-inference failure.
2. **No-alternative ablation:** one merchant per item. Compares how much the agent uses walking away.
3. **All-Conceder market:** if every merchant concedes early, naive strategies should do fine. The gap should appear only as the style mix gets harder, which shows the difficulty comes from merchant variety, not from the interface.
4. **Scripted baselines** next to the reference: accept-the-first-ask, split-the-difference, and a fixed Boulware buyer with no opponent modelling. Their order shows that the reward ranks behaviour sensibly.

### First pilot (half a day)

1. One item type, three merchants with mixed styles, 10 seeds.
2. The reference and the three scripted baselines.
3. Three real agent runs.
4. **Decision rule:** if the agent reaches about 85% of the reference's share, the gap is too small; widen the style mix and tighten patience and budget. If that still doesn't open a gap, frontier agents may simply be good at this (as BAZAAR suggests), so go back to Lightlag or Brewmaster. Also check that the spread across the three runs is small.

### Demo (10 minutes)

For each merchant, plot its asks over time with the hidden floor drawn in afterwards, and the agent's bids against them. Show the agent accepting a Boulware merchant's early ask while the reference walked to the cheaper alternative. Close with one chart: share of available surplus for accept-first, split-the-difference, the frontier agent and the reference.

### What it changes in our brainstorm

Sealed-Bid Negotiator scored worst here on reward integrity because scripted opponents can be exploited and free text invites manipulation. This design fixes both: numbers only, published rules, final walk-aways and a share-of-surplus score. If the team picks Bazaar, it supersedes that idea.

### Open choices for the team
- A new name (to avoid clashing with Mazur's BAZAAR).
- Include the reactive (tit-for-tat) merchant behaviour, or keep merchants purely time-based for a cleaner reference?
- Public hints about each merchant (e.g. "busy stall"), weakly correlated with type through a published table, or none?
- How many deals per run: the reviewer's 15+, or fewer to fit the tool-call budget?

## Brewmaster deep dive

A build-ready look at **Brewmaster**, the reactor version of the mechanic the team is converging on: *learn a partly unknown, delayed system with a few cheap trials, then operate it where mistakes can't be undone*. A lager fermenter reacts to cooling with a delay, the yeast strain's parameters are unknown, and a few cheap test batches come before three graded ones. It is the same idea as BatchPilot plus test batches and our Pilot Plant ID combination ("Combining ideas"), reached independently in two sessions. The team's second review ranks it level with Lightlag. Numbers marked *starting value* are guesses to tune. Related: "The team's round-two ideas: our read", "Lightlag deep dive", "Related research".

### The model is published, so the physics doesn't have to be invented

The reviewer's main build worry ("units and dynamics need validating") has a ready answer: **the de Andrés-Toro beer fermentation model** (Mathematics and Computers in Simulation, 1998). It was fitted to industrial-condition pilot-plant data, and every equation and constant is printed in [Carrillo-Ureta, Roberts and Becerra (2003)](https://skoge.folk.ntnu.no/prost/proceedings/ecc03/pdfs/331.pdf):
- yeast split into lag, active and dead cells; sugar, ethanol, and two off-flavours, **ethyl acetate** (fruity) and **diacetyl** (buttery);
- every rate depends on temperature through an Arrhenius law, so temperature is the control input;
- a 160-hour batch, starting at 130 g/l sugar, in the 7–15 °C range the paper gives for lager strains.

That paper also optimised the temperature profile: its optimal constant temperature (about 14.6 °C) beat the industrial profile by more than 15% on its performance index, and a gradient method improved it slightly further. That gives the reference a published result to reproduce as a sanity check.

**Our own check (a short simulation of the printed equations, not a published result):**

| Constant temperature | Ethanol | Ethyl acetate | Peak sugar use | Heating if uncooled, at peak |
|---|---|---|---|---|
| 10 °C | 47.0 g/l | 2.4 ppm | 1.6 g/l/h, at 62 h | about 0.2–0.5 °C per hour |
| 13 °C | 56.8 g/l | 6.5 ppm | 2.0 g/l/h, at 49 h | about 0.3–0.6 °C per hour |
| 15 °C | 60.9 g/l | 12.0 ppm | 2.4 g/l/h, at 35 h | about 0.35–0.7 °C per hour |

- **The trade-off is real:** warmer means more ethanol, but up to five times the fruity ester. This matches brewing practice, where warmer fermentations make more esters and fusel alcohols, and brewers warm the beer near the end (a "diacetyl rest") so the yeast reabsorbs diacetyl ([White Labs](https://blog.whitelabs.com/fermentation-controls-temperature)).
- **The heat is real:** the heating column uses published heat-release figures of roughly 590–1,200 kJ per kg of sugar fermented ([source 1](https://yadda.icm.edu.pl/baztech/element/bwmeta1.element.baztech-3760174a-59c6-406d-8260-1a4071658c8f/c/PTPS_2017__nr_1__s._121_127.pdf), [source 2](https://www.briggsplc.com/wp-content/uploads/technical-papers/BEA-Mar-2017-Briggs.pdf)). Several degrees per day is large compared with the 7–15 °C window, so cooling capacity and jacket delay matter at peak activity.
- **A thermostat can't pass a sensible spec.** With the published yeast and a sample spec (ethanol ≥ 58 g/l, ethyl acetate ≤ 8 ppm, sugar left ≤ 1 g/l), **no constant temperature passes, and only 3 of 224 simple two-step profiles do.** The round-two reviewer required a plain thermostat baseline that scores well below the reference; the published model delivers that before any heat effects are added.

**Industry interest:** Yokogawa and a Kyoto brewer reportedly trialled AI-planned fermentation temperatures in simulation in 2025, shortening fermentation by 28%, with the brewmaster reviewing the plan ([Control Global](https://controlglobal.com/industry-news/news/55324567/yokogawa-and-craft-bank-co-optimize-beer-fermentation-process-with-ai)). **Not the same as OperAItor:** that benchmark ([arXiv 2611.05179](https://arxiv.org/abs/2611.05179)) is about supervising fault management in a continuous chemical plant. Brewmaster is about learning an unknown batch process from a limited test budget.

### The core trap: one test temperature can't identify the yeast

Arrhenius rates have two unknowns each: a speed and a temperature sensitivity. A test run at a single temperature measures the speed *at that temperature* only. **Two strains can look identical in a 12 °C test and still differ at 15 °C.** For example, by the printed ester equation, two strains with the same ester rate at 12 °C but different temperature sensitivity can differ by about a third in ethyl acetate at 15 °C (our calculation). Production runs warmer than a careful test, so a lazy test design leads to a confident, wrong extrapolation.

That is exactly where the literature says agents fail: Causal Discovery Bench attributes 94.5% of mistakes to experiment design, and NewtonBench found that a code interpreter made strong models stop exploring too early ("Related research"). Fitting the model is a short script; **choosing tests that make the fit possible is the decision.** This is the standard problem of model-based design of experiments for parameter precision ([Franceschini and Macchietto, 2008](https://www.bohrium.com/paper-details/model-based-design-of-experiments-for-parameter-precision-state-of-the-art/811955529734684672-3943)), which gives the reference a textbook method.

### Spec (proposal)

**Equipment (fully documented):** a production fermenter with a glycol jacket of limited cooling power and a delay between valve and beer temperature; a temperature sensor that lags slightly. A small pilot vessel with perfect temperature control for tests.

**Yeast (hidden per seed, from a published family):** each key rate in the de Andrés-Toro model (growth, sugar use, ester formation, lag) gets a strain factor on its speed and on its temperature sensitivity, drawn from documented ranges, plus the diacetyl constants. Heat release follows from sugar use with a documented constant. This is Public Rules, Hidden Instance.

**Batch-to-batch disturbance (optional, recommended by the reviewer):** starting sugar varies by a few percent, and yeast vitality drifts slightly between graded batches, so the model needs updating from production data.

**Test budget:** *starting value* 3 pilot tests of up to 48 hours each. A test can follow any temperature profile, including steps; a single test with a temperature step can reveal temperature sensitivity, which is the clever move. Sugar readings come every 12 hours; ester and diacetyl lab assays are limited (*starting value* 6 in total) and return 12 hours after sampling.

**Graded batches:** exactly 3, each 160 hours, final once started.

**Agent tools** (served from a separate container):

```text
rules(), equipment()            -> the model family, strain ranges, jacket and sensor data, spec, budgets
run_test(profile, hours<=48)    -> pilot test; returns sugar readings every 12 h
assay(test_or_batch, time)      -> ester or diacetyl result, available 12 h later; counts against the budget
start_batch(profile)            -> starts a graded batch with a temperature setpoint profile
advance(hours)                  -> time passes; returns lagged temperature and sugar readings
set_profile(rest_of_profile)    -> changes the remaining setpoint profile
history()                       -> everything so far (free)
```

A batch takes about 10 calls (advance a day at a time, adjust when needed), so 3 tests plus 3 batches fit the round-two target of 40–60 tool calls. An onboard controller tracks the setpoint with the jacket; the agent chooses setpoints, which is how real brewers work and why "the agent's code runs the loop" matters less here (see below).

### Reward

- **Per graded batch, a continuous quality score:** an ethanol (attenuation) score rising from 0 at a minimum to 1 at the target, multiplied by a flavour factor (1 inside the ester and diacetyl limits, falling to 0 at twice the limit), multiplied by a safety factor (0 if the beer left the safe band, for example 6–17 °C, for more than an hour).
- **Score:** the mean over the 3 graded batches, divided by the reference's mean on the same seeds.
- **Doing nothing** starts no batches → 0. Stopping early leaves batches unfinished → low ethanol score.
- **Test batches earn nothing directly.** They only pay through better graded batches (AfterQuery found that rewarding exploration produced exploration for show).
- **For the small-model tiebreaker:** a continuous score per batch; the strain ranges, cooling power and spec tightness are difficulty dials.

### Reference run

Sees only what the agent sees (Honest Reference Solver):
1. **Design the tests** to maximise information about the parameters that matter for the production profile. Simplest version: tests that span the production temperature range, including a step; textbook version: D-optimal design from the published prior (Fisher information).
2. **Fit** the strain factors by nonlinear least squares to the sugar readings and assays.
3. **Plan** an optimal temperature profile for the fitted model under the jacket's cooling limit, with margins for parameter uncertainty (as in Carrillo-Ureta et al., but with a heat balance added).
4. **Run** each graded batch with model predictive control that anticipates the yeast's heat peak and the jacket delay, and update the fit from each batch's sugar readings.

This is BatchPilot's "MPC plus estimator" reference with an identification step in front.

### Where the agent should fail

| Expected mistake | What it looks like in the trace | Failure mode |
|---|---|---|
| All tests at one temperature | A good fit at 12 °C, a confident wrong prediction at 14–15 °C; esters out of spec | Uninformative Experiments |
| Changing several things at once | Pitch and temperature varied together, so effects can't be separated | Uninformative Experiments |
| Skipping tests | Uses the textbook profile; fine for one strain, out of spec for others | Real-World Priors Override Evidence |
| Reacting to the current temperature | Cools only once the beer is already too warm; with the jacket delay the heat peak overshoots | Delayed-Feedback Blindness |
| Over-correcting to cold | Clean beer, but low ethanol by the end of the batch | Premature Commitment |
| Trusting an uncertain fit | Plans right at the spec limits with no margin | Overconfidence and Poor Calibration |
| Never updating between batches | Repeats batch 1's profile while vitality drifts | Anchoring on the First Hypothesis, Long-Horizon Drift |

### Exploits and defences

| Exploit attempt | Defence |
|---|---|
| Do nothing | No graded batches → 0 |
| Run graded batches as tests | Graded batches are labelled when started and final |
| Maximum cooling all the time | Clean but low ethanol → low score |
| Read the strain parameters | Separate container; only the tools reach it |
| Report quality instead of producing it | Scores come from the simulator's final state (Tamper-proof Grader) |
| Write the reference in Python | Legitimate. The fit and the MPC are scriptable; wasted tests are not recoverable. If the agent still closes the gap, it's too easy (Brute-force Escape Hatch) |

### Experiments that prove the difficulty is fair

1. **Known-strain ablation:** reveal the yeast parameters. The gap that closes was identification; the gap that remains is control (heat peak, jacket delay).
2. **Double test budget:** if the agent doesn't improve with twice the tests, its problem is test *design*, not budget, the same pattern Causal Discovery Bench reports.
3. **Perfect-cooling ablation:** remove the jacket limit and delay. Isolates the control part.
4. **The identifiability chart:** two strains identical in a 12 °C test, diverging at 15 °C. A one-slide explanation of the main mistake.
5. **Scripted baselines:** a thermostat at a textbook setpoint, the published industrial profile with no tests, and a one-temperature-test fit with an optimal profile. The expected order is reference > one-temperature fit > industrial profile > thermostat > nothing.

### The deciding question: can the agent's code run the loop?

The team's second review asks this of every control idea: if the agent's own code can call the environment tools, it can run a controller without the model in the loop, and the gap may close. For Brewmaster this matters less than for Lightlag:
- the onboard controller already tracks setpoints, so a scripted loop adds little;
- the decisive choices are few and irreversible (which tests to run, which profile to commit to), and a loop can't take back a wasted test.

It's still worth checking in Harbor whether the simulator is reachable only through the model's tool calls, and running the pilot with code access allowed either way.

### First pilot (half a day)

1. Implement the printed model (seven state equations) with a simple heat balance and a first-order jacket delay.
2. The four scripted baselines and the reference on 5 strain seeds.
3. Three real agent runs.
4. **Decision rule:** if the thermostat reaches about 80% of the reference, the physics is too forgiving: reduce cooling power or widen strain ranges. If the agent reaches about 85% of the reference, check whether it designed informative tests; if it did and still matched, the gap isn't there, so fall back as the team plans.

### Demo (10 minutes)

Two charts. First, the identifiability trap: two yeasts that look the same at 12 °C and split apart at 15 °C. Second, the same strain under the agent and the reference: temperature profile, the yeast's heat peak against the cooling limit, and the off-flavours against the spec.

### Open choices for the team
- Beer (published model, relatable demo) or BatchPilot's exothermic reactor (more dramatic safety, needs its own kinetics)? We'd pick beer for the published model.
- Is batch-to-batch drift in, or kept for a harder tier?
- Should tests run in a separate pilot vessel with perfect temperature control (cleaner identification), or in the production tank (more realistic, more confounded)?

## Related research

What published work and competitions say about our ideas and the team's round-two ideas: the problem each one tackled, what worked, what didn't, and what it means for us. Gathered by web search on 2026-11-13, aimed at topics the team's research (`docs/research/` in junction-2026) doesn't cover. Our read on the round-two ideas themselves is in "The team's round-two ideas: our read".

**How far to trust this:** most sources were read only at abstract or search-summary level, so the numbers are as the authors report them, not reproduced. Where a number comes from a secondary site, it says so. Several 2026 preprints name models we can't check independently. Open a source before quoting it in the demo.

**The short version:** the gap lives in deciding what to find out and when to commit, not in computing. Agents with code tools can compute almost anything; they still choose poor experiments, stop exploring too early and trust stale information.

### Connecting the dots

1. **New rules create the gap; familiar rule types don't, and gaps shrink fast.** A language agent scored 100% on BabaIsAI, a known puzzle game (BALROG, in the team's research). ARC-AGI-3's hand-made games, which come with no instructions, held frontier models under 1% at launch in March 2026 while humans solved them. Four months later ARC Prize verified 30.2% for Claude Opus 5, and harnessed systems are reportedly higher still. In Learn2Play Bench, whose games hide counterintuitive rules, people still reached higher scores than agents. *For us:* draw each seed's rules from a published family so it's fair, but make the combinations new. The gap is real for a hackathon, not forever. → Rule-Discovery Gridworld, Alien Physics Lab, Real-World Priors Override Evidence

2. **Agents fail at choosing experiments more than at reading results.** Causal Discovery Bench attributes 94.5% of agent mistakes to experiment design rather than inference. BoxingGym finds GPT-4o weak at both experimental design and model discovery. NewtonBench finds discovery fragile and very sensitive to noise. DeepMind's Alchemy found deep RL agents failing until they were handed the hidden state. And in simple bandit tasks, LLMs rarely explored unless their history was summarised for them (Krishnamurthy et al.). *For us:* put the difficulty in a learning phase and score only what comes after it. → Uninformative Experiments, Anchoring on the First Hypothesis; the team's Brewmaster, Lightlag and Alchemy; Cipher Lab

3. **A shell closes the computing part of the gap, not the deciding part, and can even widen it.** NewtonBench reports that a code interpreter can *hurt* capable models: they switch from exploring to exploiting too early and settle on wrong answers. Causal Discovery Bench: basic statistics tools help a lot, fancier tools add little when the agent can't design experiments, and a bigger budget doesn't fix sequential discovery. At the 2021 NetHack Challenge, hand-coded bots beat learned agents about threefold. *For us:* this explains the round-two reviewer's split between "agent has a shell" and "no shell" scores. Make the reference an algorithm, assume the agent writes one too, and keep the hard part in decisions a script can't make unless the agent knows what to look for. → Brute-force Escape Hatch, Honest Reference Solver, Premature Commitment

4. **Delay is an open niche, next to evidence that time pressure hurts.** Theory: adding the commands still in transit to the state turns a delayed problem back into a normal one, and action and observation delays are interchangeable. History: since 1965, human operators facing a delay fall back on "move and wait"; predictive displays reduce it. 2026: a live clock flips rankings toward faster models (RealtimeBench), and agents degrade when thinking time turns into control delay. No benchmark of LLM agents under a fixed signal delay turned up. → the team's Lightlag, Delayed-Feedback Blindness, BatchPilot

5. **Negotiation is crowded, with well-documented failures and ready-made references.** In 2026 benchmarks, LLM negotiators leak their limits, concede early, and drift to aggressive deals after joint training. The Automated Negotiating Agents Competition (ANAC) has run since 2010, so classical strategies exist to use as a reference. A negotiation evaluator won its category at AgentX–AgentBeats. → the team's Bazaar, Sealed-Bid Negotiator

6. **Fresh instances deflate scores.** The K Prize's first winner solved 7.5% of freshly collected GitHub issues, while top scores on SWE-bench Verified were around 75%. → Public Rules, Hidden Instance, Held-out Evaluation, Procedural Generation with Seeds

7. **"LLMs can't forecast" no longer holds.** By July 2026 the Forecasting Research Institute said top AI systems have likely reached parity with superforecasters on ForecastBench (not statistically significant, and disputed). → Forecasting Arena, re-scored

8. **Agents will hack the reward if they can, and AfterQuery's own training shows what to reward.** ImpossibleBench made tests contradict the task, so any pass is a cheat; GPT-5 reportedly passed up to about 93% on one variant. A strict "stop if the tests look wrong" instruction cut that to about 1%; hiding the tests also worked but hurt normal performance. AfterQuery trained a 20B model on Terminal-Bench tasks and found that rewarding exploration directly produced exploration that was "performative rather than functional" (their words); rewarding outcomes made useful exploration emerge on its own. *For us:* never reward the learning phase; keep the verifier out of reach; and see "AfterQuery's own lessons" below for the small-model tiebreaker. → Tamper-proof Grader, Small-Model Training Loop, Multiplicative Efficiency Bonus

### Award-winning precedents

| Competition | What happened | Lesson for us |
|---|---|---|
| [NeurIPS 2021 NetHack Challenge](https://arxiv.org/abs/2203.11889) | Hand-coded (symbolic) bots took the top three places; the best one's median score was nearly three times the best neural agent's. No agent came close to winning the game. | In long games with hidden information, an algorithmic reference beats learned agents. And an agent with a shell can write that kind of bot itself. |
| [DARPA AI Cyber Challenge final](https://www.darpa.mil/news/2025/aixcc-results) (DEF CON 33, Aug 2025) | Team Atlanta's system ATLANTIS won the $4M first prize; Trail of Bits second, Theori third; $8.5M in total. Systems found and patched vulnerabilities in real open-source code. | Automated find-and-fix is proven, so a security environment needs a sharper angle than "patch the bug". → Patch Under Fire |
| [ARC Prize, ARC-AGI-3](https://arcprize.org/results/anthropic-claude-opus-5) (launched 25 Mar 2026) | Interactive games with no instructions. At launch, frontier models scored under 1% while humans solved them (per launch coverage). ARC Prize verified Claude Opus 5 at 30.2% on 24 July 2026; higher harnessed scores on third-party sites are unverified. | Novel rules create a big gap, and harnesses shrink it within months. A [critical review](https://www.nabu.science/paper/10.48550%2Farxiv.2603.24621) notes environments were kept if 2 of 10 humans solved them, so a human baseline is a weak reference; an algorithmic reference is easier to defend. |
| [Konwinski Prize](https://techcrunch.com/2025/07/23/a-new-ai-coding-challenge-just-published-its-first-results-and-they-arent-pretty), round 1 (2025) | The winner solved 7.5% of GitHub issues collected after the submission deadline, for $50,000. | Unseen instances are the honest test. → Held-out Evaluation |
| [ANAC 2025](https://arxiv.org/abs/2604.13914) (16th edition) | The main league was a tie between RUFL and SAC Agent, which is built on reinforcement learning (soft actor-critic). | A mature field: decades of classical negotiation strategies to borrow for a reference. |
| [AgentX–AgentBeats](https://rdi.berkeley.edu/agentx-agentbeats) (Berkeley RDI, 2025–26; 1,300+ teams) | Phase 1 entries were *benchmarks* ("green agents"), not agents. A [negotiation evaluator](https://strategicreasoning.org/srg-team-is-a-winner-in-the-agentx-agentbeats-competition/) won the multi-agent evaluation category; [PETScAgent-Bench](https://www.anl.gov/mcs/article/argonne-team-wins-award-at-agentbeats-competition) placed third in coding. | The closest precedent to this challenge's format: you build the evaluation, not the agent. |
| [OpenEnv Hackathon SF](https://siliconvalley.northeastern.edu/small-collab-leads-to-big-win-at-2026-openenv-hackathon-san-francisco/) (Meta, Hugging Face, PyTorch; March 2026) | 104 projects, $100K+ in prizes. Mercor's $10,000 theme prize went to an environment that rewards faster CUDA kernels, measured on the GPU. | Winners measured the reward from the real system, not from a judge. → Verifiable Reward |

### By topic

Each entry: the problem it tackled, what worked, what didn't, and what it means for us.

#### Hidden rules and scientific discovery
*Bears on Alien Physics Lab, Cipher Lab, Rule-Discovery Gridworld, the team's Alchemy and Loop, and the learning phase of Brewmaster and Lightlag.*

- **[NewtonBench](https://arxiv.org/abs/2510.07172)** (ICLR 2026). *Problem:* can agents discover physical laws by running experiments, without recalling them from memory? 324 tasks in 12 physics domains, built from counterfactual versions of real laws. *Worked:* frontier models show a clear but fragile ability; an algorithmic symbolic-regression pipeline (LLM-SR) far outscored a plain agent (55.6% vs 13.9% with GPT-4.1-mini, as reported from the appendix). *Didn't:* non-thinking models scored under 10% symbolic accuracy; performance falls sharply with system complexity and observation noise; a code interpreter made capable models stop exploring too early. *For us:* nearly the same design as Alien Physics Lab: strong evidence for a gap, little novelty. Noise is a ready-made difficulty knob.
- **[BoxingGym](https://arxiv.org/abs/2501.01540)** (2025). *Problem:* automated experimental design and model discovery. *Didn't:* GPT-4o struggled with both, and giving the agent an explicit statistical model didn't reliably help.
- **[Causal Discovery Bench](https://arxiv.org/abs/2611.09934)** (November 2026). *Problem:* find a hidden causal structure through sequential experiments with resource limits. 13 models, 3,802 episodes. *Worked:* agents infer well from correctly curated evidence; basic statistics tools help substantially. *Didn't:* 94.5% of mistakes were in experiment design; advanced tools added little; relaxing resource limits didn't fix it. Its four difficulty levels (one experiment → sequential exploration → budgeted experiments → conflicting evidence) are a ready-made difficulty ladder.
- **[Alchemy](https://arxiv.org/abs/2102.02926)** (DeepMind and UCL, NeurIPS 2021 Datasets and Benchmarks). *Problem:* meta-learning a hidden causal structure (potions transform stones) resampled every episode. *Didn't:* strong deep RL agents (IMPALA, V-MPO) learned single tasks but failed to meta-learn. *Worked:* giving the hidden state, or auxiliary tasks, improved them a lot. *For us:* same name and core idea as the team's Alchemy; see "The team's round-two ideas: our read".
- **[Learn2Play Bench](https://www.alphaxiv.org/abs/2610.08215)** (October 2026). *Problem:* do agents learn from experience in unfamiliar games? 20 hand-designed text games with hidden, sometimes counterintuitive rules, played repeatedly. *Worked:* agents do improve across episodes; keeping full, unedited histories of earlier attempts beat methods that distil them into lessons (Reflexion and others). *Didn't:* humans reached higher peaks, tried more varied strategies and repeated themselves less; one agent ruled out a working combination after a single failure. *For us:* the team's Loop mechanic, already measured with "learning gain" (late minus early episodes).
- **[Can large language models explore in-context?](https://arxiv.org/abs/2403.15371)** (Krishnamurthy et al., NeurIPS 2024). *Problem:* do LLMs explore in simple multi-armed bandits? *Didn't:* most model and prompt combinations failed to explore robustly. *Worked:* only GPT-4 with chain-of-thought and an externally summarised history. *For us:* the classic citation for "agents exploit too early".
- **[CipherBank](https://arxiv.org/abs/2504.19093)** (ACL Findings 2025) and **[CryptanalysisBench](https://arxiv.org/abs/2607.18538)** (2026). *Problem:* can LLMs decrypt? CipherBank's 2,358 tasks (substitution, transposition and custom ciphers) found significant weaknesses in GPT-4o, DeepSeek-V3, o1 and DeepSeek-R1. CryptanalysisBench (191 tasks on real primitives) concludes models can increasingly do cryptanalysis. *For us:* neither tests an agent with a shell and an encryption oracle, which is Cipher Lab's real question.

#### Control under delay
*Bears on the team's Lightlag and Brewmaster, and on BatchPilot.*

- **[Delays in Reinforcement Learning](https://arxiv.org/abs/2309.11096)** (survey) and delayed-MDP papers ([Nath et al.](https://arxiv.org/abs/2108.07555)). *Worked:* adding the last few commands sent to the state makes a delayed problem an ordinary one again; action and observation delays are equivalent and add up. *Didn't:* the state grows with the delay, and the trick stops being exact when delays are random. *For us:* the Lightlag reference ("replay in-transit commands") is the textbook answer, which makes it credible to control-minded judges. A constant delay gives a clean ablation; a random one is harder but must be documented.
- **Ferrell, "Remote manipulation with transmission delay"** (1965), and later teleoperation research (for example [Sanner's dissertation at the University of Maryland](https://drum.lib.umd.edu/handle/1903/2064)). *Problem:* operating a remote arm or vehicle through a delay. *What people did:* most operators spontaneously adopted "move and wait": small command, wait for confirmation. *Didn't:* it is slow, and later rover studies link it to high workload and more collisions. *Worked:* predictive displays that show where the vehicle will be. *For us:* expect agents to find move-and-wait too. It only loses if waiting costs something, which is why the round-two reviewer's "waiting costs battery" is essential.
- **[The World Won't Wait (RealtimeBench)](https://arxiv.org/abs/2610.20665)** (October 2026). *Problem:* agents in games that keep running while the model thinks; 180 tasks, six game types. *Didn't:* a stronger but slower model beat a faster one with the game paused, then fell behind with the clock running. *Worked:* a slow "teacher" studies failures between attempts and writes instructions for a fast "student", raising its score from 13.51 to 24.19 out of 100. *For us:* a wall clock measures inference speed, not decisions, and the rubric gives zero points for impossible timing, so count delay in steps.
- **[Reflex First, Reflect Later](https://arxiv.org/abs/2506.07223)** (2025). *Didn't:* methods that did well in the base setting got worse once their thinking time became control delay.
- **Fermentation control.** [IndPenSim](https://skoge.folk.ntnu.no/prost/proceedings/dycops-2025/DYCOPS2025_offline_program/contents/papers/0019.pdf), a validated simulation of industrial penicillin fermentation, is a standard benchmark for advanced control and RL; there are RL studies of fed-batch [baker's yeast](https://ceur-ws.org/Vol-3970/SHORT4.pdf) and of [harvest timing as optimal stopping](https://arxiv.org/abs/2101.03735). No benchmark of LLM agents controlling fermentation turned up. *For us:* borrowing a published model answers Brewmaster's "arbitrary puzzle" risk.

#### Negotiation
*Bears on the team's Bazaar and Sealed-Bid Negotiator.*

- **[Faithful Delegates? (SovereignNegotiation-Bench)](https://arxiv.org/abs/2607.02814)** (2026). *Problem:* do agents protect their principal's limits? *Didn't:* across 17 open-weight models, faithful success ranged from 6% to 75%, and agents revealed the principal's reservation value in 2–80% of episodes. Its counterparty rules make leaks costly (after a leak, the counterparty offers exactly that value and holds).
- **[Used Car Salesbots?](https://arxiv.org/abs/2605.31445)** (2026). *Problem:* honesty and credulity in bargaining with partial information. *Didn't:* training both sides together did not settle at a fair midpoint; it produced aggressive, seller-favouring deals with lower total welfare.
- **[TERMS-Bench](https://arxiv.org/abs/2605.13909)** and **[PrefBench](https://arxiv.org/abs/2605.22855)** (2026): hidden reservation prices and hidden, falling willingness to pay; TERMS-Bench classifies failures that a plain deal rate hides. **[PACT](https://github.com/lechmazur/pact)**: 20-round buyer–seller matches with hidden values and numeric bids and asks each round, the numeric-only protocol the round-two reviewer recommends.
- **[ANAC](https://arxiv.org/abs/2604.13914)**: see the precedents table; its supply-chain league is also relevant to Supply Chain Under Shocks.
- *For us:* the gap evidence is strong and the field is crowded. Pitch it as a known weakness, measured cleanly.

#### Forecasting
- **[ForecastBench](https://forecastingresearch.substack.com/p/ai-models-have-likely-reached-parity)** (Forecasting Research Institute). *Problem:* LLMs vs superforecasters on questions about real future events. *Worked:* steady gains; by July 2026 the institute says top systems have likely reached parity and an AI system outranks superforecasters on market questions. *Caveat:* not statistically significant, a [May 2026 report](https://parallect.ai/reports/ai-superforecasters-forecastbench-may-2026-895525) disputes parity, and some systems may benefit from leakage in backtests. *For us:* Forecasting Arena has to rest on its synthetic world, not on "LLMs forecast badly".

#### Reward hacking, and AfterQuery's own lessons
- **[ImpossibleBench](https://arxiv.org/abs/2510.20270)** (2025). *Problem:* how often do coding agents cheat on tests? Tests are altered to contradict the task, so any pass means a cheat. *Didn't:* GPT-5 reportedly passed 54% on one variant and about 93% on another (secondary summaries). *Worked:* a strict instruction to stop when tests look wrong cut it to about 1%; hiding tests also worked but hurt normal performance. *For us:* assume the agent hacks whenever it can, during the judges' 15 minutes and in training.
- **[AfterQuery: Improving Terminal-Bench 2.0 with Tinker and Harbor](https://www.afterquery.com/blog/how-we-improved-terminal-bench-2-with-tinker-and-harbor).** *Problem:* train a small open model (gpt-oss-20b) to be a better terminal agent. *Worked:* supervised fine-tuning on good trajectories (3.1% → 13.5%) then reinforcement learning with verifiable rewards (GRPO, group size 16) to 17.0% on 89 tasks; partial credit (80% share of tests passed, 20% efficiency bonus among successes); training only on tasks the model solved 10–80% of the time; one fresh Docker container per episode. *Didn't:* a reward for exploratory first turns, which the model satisfied without using what it found; they removed it. *For us:* (1) never reward a learning or calibration phase directly; (2) a difficulty dial (delay, noise, budget) can keep a small model in the 10–80% band, which is how to aim at the tiebreaker; (3) their 80/20 shape is our Multiplicative Efficiency Bonus. This is the judges' own playbook (Harbor + Tinker), worth echoing in the demo.

#### Areas where no LLM-agent benchmark turned up
One or two searches each, so absence is weak evidence; it may also mean less competition.
- **Fixed signal delay** (Lightlag): only live-clock studies (above).
- **Fermentation or batch control** (Brewmaster, BatchPilot): RL work, nothing for LLM agents.
- **Wildfire suppression** (Firebreak): RL simulators exist ([Firehose on Cell2Fire](https://williamshen-nz.github.io/firehose/firehose-paper.pdf), [JaxWildfire](https://arxiv.org/abs/2512.06102)), none for LLM agents.
- **Optimal stopping** (Summit, Deep Dive): classical theory (the secretary problem's 1/e rule); nothing on LLM agents turned up.

## What we're aiming for

1. **Hard task, unbreakable reward.** The task must be solvable, because we have to show a stronger reference run. But frontier agents should fail at it for reasons we can explain. What must be unbreakable is the *reward*: doing nothing or stopping early scores about 0, and no trick beats actually doing the task.
2. **Public rules, hidden instance.** Publish the *family* of possible worlds (e.g. "the cipher chains 2–4 of these 6 steps"). A random seed picks the specific world for each episode. This is fair (everything can be learned by exploring), can't be memorized, and makes the reward exactly checkable.
3. **Why not "dynamic encryption" as-is.** Real encryption (AES) is unbreakable for everyone, including our reference, which would score zero on fairness. Textbook ciphers are too easy for frontier agents. We reframed it as **Cipher Lab**: reverse-engineer a cipher, built from a published rulebook, whose key keeps rotating.
4. **What "RL" means here.** We build the environment and the reward; the agent does the learning. *Within one episode* the agent discovers the hidden setup by probing it; this is what the judges measure. *Across many episodes* with different seeds, RL training updates a model's weights so it gets better at discovering in general; this is the optional stretch goal. Reward loopholes matter because RL training finds them and learns to exploit them.
5. **The reference run must be honest.** It may only use information the agent also sees. For example, an MPC controller has to estimate the plant's parameters from the same sensor data, not read them from the seed. Otherwise the gap counts as withheld information.
6. **Biggest shared risk.** The agent writes code that brute-forces the problem (its own controller, a search over every possible cipher). That is legitimate success, so the difficulty has to come from interaction and judgment, not raw compute. Test for it in the first pilot.

## Ideas at a glance

Scores are 1–5 gut ratings, meant to be argued with. Weighted score follows the rubric: (gap×30 + difficulty×30 + integrity×25 + build ease×15) / 5, out of 100. "Build ease" stands in for craft (higher = easier to build well). Four ideas were re-scored (marked *re-scored*): three after reading the team's research (see "Where the research changes this brainstorm" above) and Forecasting Arena after the literature search in "Related research". The rest keep their original gut scores.

| # | Idea | Theme | In one line | Gap | Difficulty | Integrity | Build ease | Weighted |
|---|---|---|---|---|---|---|---|---|
| 1 | Cipher Lab | Hidden-rule discovery | Reverse-engineer a procedurally generated cipher whose key keeps changing, using a limited "encrypt" tool, then decrypt messages sent at *future* key states. | 3 | 5 | 5 | 4 | **85** |
| 2 | Incident Commander | Investigation & diagnosis | A simulated cluster of 8–20 microservices has a hidden fault. Investigate logs, metrics and traces, fix the actual cause and name it, without wrecking healthy services. | 4 | 5 | 4 | 2 | **80** |
| 3 | Forecasting Arena *(re-scored)* | Judgment under uncertainty | A simulated world (small economy, disease spread, or sports league) with hidden dynamics. Read the data, optionally buy more, and give probability forecasts for upcoming events. | 3 | 4 | 5 | 4 | **79** |
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

#### Literature check (2026-11-13)
- **No score change; gap stays 3.** CipherBank (ACL Findings 2025, 2,358 tasks) found GPT-4o, o1, DeepSeek-V3 and DeepSeek-R1 weak on classical and custom ciphers, and CryptanalysisBench (2026) finds models increasingly capable on real cryptographic primitives. Neither tests an agent with a shell and an encryption oracle, which is this design's real question → Brute-force Escape Hatch.
- **Support for the query budget:** in sequential discovery, agents' main weakness is choosing experiments, not reading results (Causal Discovery Bench: 94.5% of mistakes). Choosing which plaintexts to encrypt is exactly that kind of choice.
- **Same family as the team's Alchemy**, so the round-two reviewer's worry (eliminating hypotheses is a short script) applies here too. See "Related research" and "The team's round-two ideas: our read".

#### Connections
- **Failure modes it tests:** Anchoring on the First Hypothesis, Shallow Heuristics Break Under Shift, Uninformative Experiments, Skipping Verification, Real-World Priors Override Evidence
- **Reward safeguards it uses:** Held-out Evaluation, Multiplicative Efficiency Bonus, Exact Match Over Partial Credit, Tamper-proof Grader
- **Design principles:** Public Rules, Hidden Instance, Procedural Generation with Seeds, Honest Reference Solver, Brute-force Escape Hatch, Small-Model Training Loop
- **Related ideas:** Protocol Whisperer, Alien Physics Lab, Rule-Discovery Gridworld, Patch Under Fire

### 2. Incident Commander

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

### 3. Forecasting Arena

*Theme: Judgment under uncertainty · Gap 3 · Difficulty 4 · Integrity 5 · Build ease 4 · Small-model fit 4 · Weighted 79/100*

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

#### Re-scored after a literature check (2026-11-13)
- **Gap 4 → 3.** On ForecastBench, the Forecasting Research Institute said in July 2026 that top AI systems have likely reached parity with superforecasters on questions about real events (not statistically significant, and disputed). "LLMs forecast badly" is no longer a safe premise.
- **What still holds:** the world here is synthetic with hidden dynamics, so memorised world knowledge doesn't help, and Proper Scoring Rules keep the reward honest. But an agent with a shell can fit the same model family as the reference, so the gap has to come from deciding which data to buy and when to stop buying.
- **Weighted 85 → 79.** Details in "Related research".

#### Connections
- **Failure modes it tests:** Overconfidence and Poor Calibration, Source Trust Errors, Anchoring on the First Hypothesis, Real-World Priors Override Evidence
- **Reward safeguards it uses:** Proper Scoring Rules, Baseline-Normalized Reward, Action Costs and Collateral Damage
- **Design principles:** Procedural Generation with Seeds, Verifiable Reward, Honest Reference Solver, Small-Model Training Loop
- **Related ideas:** Alien Physics Lab, Supply Chain Under Shocks, Synthetic Research Desk

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

#### Literature check (2026-11-13)
- **No score change. The strongest published support for a gap of any idea here, but little novelty.** NewtonBench (ICLR 2026) does almost exactly this: 324 law-discovery tasks in 12 physics domains, built from counterfactual versions of real laws and solved by running experiments. Discovery was fragile, fell sharply with complexity and noise, and non-thinking models scored under 10%. BoxingGym and Causal Discovery Bench agree that experiment design is the weak spot.
- **The shell may not close the gap:** NewtonBench reports that a code interpreter made capable models stop exploring too early → Premature Commitment.
- **Reference idea:** in NewtonBench an algorithmic symbolic-regression pipeline (LLM-SR) far outscored a plain agent, so a symbolic-regression reference is credible.
- **Pitch it as building on NewtonBench, not as new.** Observation noise is a ready-made difficulty knob. See "Related research".

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

#### Team round two (2026-11-13)
- The team's round-two reviewer gave plain BatchPilot a gap of 1 out of 5 if the agent has a shell, and prefers **Brewmaster**: BatchPilot plus unknown yeast parameters and cheap test batches. That is our Pilot Plant ID combination in "Combining ideas".
- Research on experiment design supports the learning-phase version; fermentation simulators such as IndPenSim would make the process credible. See "The team's round-two ideas: our read" and "Related research".

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

#### Literature check (2026-11-13)
- **No score change.** DARPA's AI Cyber Challenge (final at DEF CON 33, August 2025; Team Atlanta won the $4M first prize) showed automated systems finding and patching vulnerabilities in real open-source code. That is strong precedent: novelty is lower, and frontier agents may be good at this.
- **Hide the attacker's tests.** ImpossibleBench (2025) shows coding agents will make tests pass without doing the task when they can → Tamper-proof Grader. See "Related research".

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

#### Literature check (2026-11-13)
- **No score change.** The evidence supports a gap: in 2026 benchmarks, LLM negotiators leak their limits and concede early (details in "Related research"). Reward integrity is still the weak point.
- **Fix to adopt from the team's Bazaar** ("The team's round-two ideas: our read"): numeric offers only, so scripted opponents can't be prompt-injected through free text; final walk-aways; scoring as a share of the available surplus over 15 or more deals.
- **Reference to borrow:** classical strategies from the Automated Negotiating Agents Competition (ANAC), such as conceding on a schedule while modelling the opponent.

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
- Does the agent get a shell in the judges' harness? The team's research and the round-two reviewer both assume so; much of the gap analysis depends on it.
- Cipher Lab still ranks first here, but nothing published tests its real question. Is it worth a quick pilot next to Lightlag?
- Lightlag: constant delay (cleaner ablation) or random delay with a published distribution (harder)?
- BatchPilot: which process exactly (exothermic reactor, fermentation, crystallization cooling)?
- Should ColdChain and RecoveryRoom be written up in the same format, to compare like for like?
