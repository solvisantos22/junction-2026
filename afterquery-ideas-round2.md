# AfterQuery — more ideas (round 2)

From Kristján / Claude, Friday 13 November, 22:30 Helsinki. This adds to [afterquery-ideas.md](afterquery-ideas.md); nothing here is decided. An independent reviewer agent is scoring these eight plus the original three (ColdChain, BatchPilot, RecoveryRoom). Its verdict goes at the bottom.

## What we are selecting for

- **Difficulty from decisions, not computation.** OpenCode is a coding agent. If it has a shell, anything a script can solve from visible inputs will be solved by a script. The hard part should be hidden information the agent must spend actions to uncover.
- **Reward from the simulator's true end state.** Then doing nothing or stopping early scores near zero and nothing is self-reported.
- **A reference that is an algorithm** using only what the agent can see, so it reproduces on any seed.
- **Short episodes**, about 40–60 tool calls, so six judge reruns are quick.
- **Fun to demo** in ten minutes.

## Ideas

### 1. Lightlag — drive a Mars rover through a signal delay

Every command takes several steps to arrive, and telemetry is equally old. Wheel slip depends on terrain and is not known in advance. Reach the science targets and get back to base before the battery dies.

- **Where agents go wrong:** they treat old telemetry as the present and forget commands still in transit, so they overshoot and over-correct.
- **Reference:** a predictor that replays in-transit commands on a slip estimate it learns from telemetry.
- **Reward:** targets reached, counted only if the rover is alive at the end.
- **Difficulty dial:** the delay length. The gap should widen as the delay grows.
- **Risk:** with fully known physics the agent could code the same predictor; the unknown slip has to carry the difficulty.

### 2. Loop — the same day, six times

A small generated town with a disaster at the end of the day. The world resets each loop, the agent's notes do not. Only the final loop is scored.

- **Where agents go wrong:** they try to win every loop instead of spending early loops on information, and they lose track of who is where and when.
- **Reference:** an explorer that maps the day's timetable in early loops, then a planner for the final loop.
- **Reward:** people saved in the final loop.
- **Risk:** the world generator is the biggest build here. A hand-made day would look like trick design. Episodes are longer than the others.

### 3. Bazaar — haggle with merchants who each have a hidden limit

Rule-based merchants, each with a hidden lowest price, patience and bargaining style. With fixed coins and time, buy everything on a shopping list for as little as possible.

- **Where agents go wrong:** they concede too fast, accept the first counter-offer, never walk away and never probe.
- **Reference:** a policy that estimates each merchant's type from their first responses and holds out accordingly.
- **Reward:** value of items bought minus coins paid, computed from deals the simulator actually executed.
- **Risk:** random merchants add variance, so each run needs many deals. Scripted merchants must feel credible, not arbitrary.

### 4. Brewmaster — BatchPilot with a learning phase

A fermentation tank that reacts to heating and cooling with a delay, and a yeast whose parameters are unknown. A few cheap test batches, then three graded ones.

- **Where agents go wrong:** they skip or waste the test batches, change several settings at once, and react to the current temperature instead of where it is heading.
- **Reference:** fit the process from the test batches, then run a predictive controller.
- **Reward:** graded batches inside the quality spec.
- **Risk:** the process must be a textbook model, or it reads as an arbitrary puzzle. If the dynamics are too simple there is no gap.

### 5. Alchemy — experiments use up the ingredients you need

Ingredients combine by hidden rules, drawn per seed from a documented rule family. Stock is limited and every experiment consumes some. Deliver the target potions.

- **Where agents go wrong:** unsystematic experiments, then either running out of stock or guessing too early.
- **Reference:** an experiment planner that picks the most informative cheap test and keeps enough stock to still make the target.
- **Reward:** target potions delivered, checked by the simulator.
- **Risk:** it reads as a puzzle more than a real workflow.

### 6. Firebreak — contain a wildfire with too few crews

A forest grid with a town. Fire spreads with the wind, and the wind shifts according to a noisy forecast. Crews cut firebreaks but take time to move.

- **Where agents go wrong:** they chase the flame front instead of cutting ahead of it, and ignore the forecast.
- **Reference:** a lookahead planner that simulates spread before committing crews.
- **Reward:** land and town left unburned, measured against doing nothing.
- **Risk:** the rules are fully known, so the agent could code the same lookahead. Random spread adds variance.

### 7. Summit — climb with a closing weather window

Camps, limited food and oxygen, acclimatisation delays, and a forecast whose reliability the agent has to judge from how it has performed so far. Height counts only if the team gets down alive.

- **Where agents go wrong:** they push on because the goal is close, or retreat far too early, and never check how reliable the forecast has been.
- **Reference:** an optimal turn-back policy from the documented weather model plus a running estimate of forecast accuracy.
- **Reward:** altitude reached, counted only on a safe return.
- **Risk:** one lucky storm can decide a climb, so each run needs several climbs.

### 8. Deep Dive — map a flooded cave on one tank of air

An unknown cave, noisy sonar, samples to collect, and a surface to get back to before the air runs out.

- **Where agents go wrong:** weak spatial memory and misjudging the point of no return.
- **Reference:** explore the nearest unknown area while always keeping enough air for the shortest known route home.
- **Reward:** samples brought back to the surface; nothing if the diver does not return.
- **Risk:** the agent can keep a map in a file and compute routes in code, which may close the gap.

## Reviewer verdict

**Partly superseded:** the [second review](#second-review-2315-teammates-ideas-on-the-same-scale) below lowered Lightlag's gap score and raised BatchPilot's after reading the team's research.

An independent reviewer agent scored all eleven ideas on Friday at 22:45. It did not know which ideas anyone preferred. **No idea has a demonstrated gap**: every score below is the reviewer's judgment, not a measurement. The reviewer found its sources through search snippets and did not open the papers, so treat the links at the bottom as leads to check.

Scores are 1–5. Gap is shown as "agent has a shell / agent has no shell".

| Idea | Gap | Difficulty | Integrity | Buildable | Fun | Verdict |
|---|---|---|---|---|---|---|
| **Lightlag** | 3 / 4 | 4 | 4 | 4 | 5 | Best overall, but only if waiting costs battery and slip is random |
| **Brewmaster** | 2 / 4 | 5 | 4 | 4 | 3 | Most credible physics; with a shell, fit-then-simulate is routine for a coding agent |
| **Bazaar** | 3 / 4 | 4 | 3 | 5 | 4 | Cheapest build, with published support, but the largest exploit surface |
| Alchemy | 2 / 4 | 3 | 4 | 4 | 3 | Eliminating hypotheses is a short script; reads as an arbitrary puzzle |
| Summit | 2 / 3 | 3 | 2 | 4 | 4 | Storm luck decides three runs; going to camp one and back rewards stopping early |
| Deep Dive | 1 / 3 | 3 | 4 | 4 | 4 | A map file plus shortest-path code closes the gap |
| Firebreak | 1 / 3 | 3 | 3 | 4 | 5 | Rules are fully known, so the agent codes the same lookahead |
| Loop | 2 / 3 | 3 | 4 | 1 | 5 | Best story, but the world generator and long episodes do not fit 36 hours |
| BatchPilot | 1 / 3 | 4 | 4 | 4 | 3 | Brewmaster without the hidden parameters |
| ColdChain | 1 / 2 | 3 | 4 | 5 | 3 | Eight stops can be brute-forced in a script |
| RecoveryRoom | 1 / 2 | 3 | 3 | 2 | 2 | Home turf for coding agents, the heaviest build, and doing nothing loses no jobs |

### The reviewer's top three, with the changes that make each defensible

**1. Lightlag, with Brewmaster's learning phase** (a short calibration drive before the graded traverse)

- Make waiting cost battery, and make slip random per terrain type. Then "send one command and wait for it to land" does not work, and neither does a one-off script.
- Document the rule family and hide only the parameters, so nothing is unfairly withheld.
- Ship a delay ablation: at zero delay the agent should match the reference, and the gap should grow with the delay. That is the fairness proof.
- Require a return to base, and score several fixed-seed maps per run to control variance.

**2. Brewmaster**

- Reactive control must fail for a documented physical reason: yeast heat release, jacket dead time and batch-to-batch disturbance.
- Publish a plain thermostat baseline that scores well below the reference. If a thermostat passes, the agent will too.
- Use a continuous quality score. Graded batches are final, exactly three, with a fixed test budget.
- Weakness: the reviewer puts it at about even odds that an agent with a shell fits a model from the test data and closes the gap.

**3. Bazaar**

- Numeric offers only; free text invites prompt injection.
- Walking away is final, and creeping up by minimum increments burns the merchant's patience.
- Publish the merchant rule family and hide only the parameters. Run 15 or more deals per run on fixed seeds, scored as a share of the available surplus.

### Points that apply to whichever idea we pick

- **Assume the agent has a shell.** Harbor runs OpenCode inside the task container. Sölvi's [research note](docs/research/afterquery-research.md) reaches the same conclusion from the Harbor docs.
- **Run the simulator in a separate container.** The seed, hidden parameters and true state must live where the agent cannot read them, and the verifier must read the reward from there.
- **Test the gap before polishing.** Build a bare loop and run the real agent three times first.

### Leads the reviewer found (not opened, not verified)

- **Bargaining:** [PrefBench](https://arxiv.org/pdf/2605.22855) reportedly finds LLM sellers bargain weakly against simple heuristics; ["Used Car Salesbots?"](https://arxiv.org/pdf/2605.31445) reportedly finds agents concede. [AgenticPay](https://www.arxiv.org/pdf/2602.06008) is a similar existing benchmark, which supports Bazaar's gap and reduces its novelty.
- **Knowing but not acting:** [STOCKTAKE](https://arxiv.org/pdf/2607.13618) reportedly compares agents with a reference that sees the same observations; a useful template for ours.
- **Delay:** no benchmark of control under a signal delay turned up, so the Lightlag and Brewmaster gap is unproven in the literature. That also means it is less crowded.

## Second review, 23:15: teammates' ideas on the same scale

The same reviewer then read Manh's [brainstorm](afterquery-brainstorm.md) and Sölvi's finished [research](docs/research/afterquery-research.md), and was told to be especially hard on Lightlag because this session proposed it. It could not open any paper, so its source checks are search-snippet level. Still no measured gap for anything.

**Verdict: none of Manh's 13 ideas beats Lightlag, but Lightlag's lead is gone.** After re-scoring it is level with BatchPilot (Manh's spec) and Bazaar. It leads only on demo appeal and on having one clean difficulty dial.

### Changes to the first-round scores

| Idea | Change | Reason |
|---|---|---|
| **Lightlag** | Gap 3/4 → **2/4**, Buildable 4 → 3 | The control review reports current models producing working controllers on 94.8% of plants; a delay predictor is easier. The reviewer's own amendments added build scope. |
| **BatchPilot** | Gap 1/3 → **2/4**, Difficulty 4 → 5, Buildable 4 → 3 | Manh's spec adds hidden parameters, drift between batches and delayed lab results. |
| **Brewmaster** | Buildable 4 → 3 | Units and dynamics need validating; close prior art exists. |
| **RecoveryRoom** | Integrity 3 → 4, Buildable 2 → 3 | The reward review's evaluator-owned ledger and fixed horizon fix the do-nothing leak. Gap unchanged. |
| Bazaar, ColdChain | No change | The research does not cover negotiation; its own counting argument confirms ColdChain is brute-forceable. |

### Manh's 13 ideas on the reviewer's scale

Gap is "with shell / without"; Manh's own gap score is in brackets.

| Idea | Gap | Diff. | Integ. | Build | Fun | Verdict |
|---|---|---|---|---|---|---|
| **BatchPilot** | 2/4 (3) | 5 | 4 | 3 | 3 | Best of the 13, with the most build-ready spec |
| Sealed-Bid Negotiator | 3/4 (3) | 3 | 2 | 4 | 4 | Bazaar with more exploit surface; merge it in |
| Alien Physics Lab | 2/4 (4) | 4 | 4 | 3 | 5 | Best demo, but a menu of terms plus Python is a regression script |
| Forecasting Arena | 2/4 (4) | 3 | 4 | 4 | 2 | Sound reward; the agent fits the published model family |
| Cipher Lab | 1/3 (3) | 3 | 5 | 4 | 3 | Probing textbook cipher layers is easy for a coding agent |
| Supply Chain Under Shocks | 2/3 (3) | 3 | 3 | 3 | 3 | Crowded field and long episodes |
| Spreadsheet Forensics | 2/3 (3) | 3 | 3 | 3 | 2 | The agent writes the same consistency auditor |
| Protocol Whisperer | 2/3 (4) | 3 | 4 | 2 | 3 | Home turf for a coding agent |
| Synthetic Research Desk | 2/2 (4) | 3 | 4 | 3 | 2 | Document lookup; ten questions is too coarse a score |
| Incident Commander | 2/2 (4) | 3 | 3 | 2 | 3 | If a graph walk solves it, so does the agent |
| Dynamic Scheduler | 1/3 (2) | 3 | 4 | 4 | 2 | The agent writes the solver |
| Rule-Discovery Gridworld | 1/2 (2) | 3 | 4 | 3 | 4 | Agrees with Manh's downgrade |
| Patch Under Fire | 1/1 (3) | 3 | 3 | 1 | 4 | A coding task whose reference is an answer key |

The reviewer's main disagreement with Manh's gap scores: they assume habits of older models, while almost every idea hands the agent Python, which removes those habits.

### Combined top five across all three sources

Ranks 1–3 are within the reviewer's uncertainty; 4 and 5 are clearly behind.

1. **Lightlag, with the amendments above.** Narrowly first: nothing published contradicts it, and the zero-delay comparison is the cleanest fairness proof.
2. **BatchPilot plus test batches.** This is the same idea as Brewmaster and as Manh's "Pilot Plant ID" hybrid, reached independently in two sessions. Equal gap, better difficulty, a control expert on the team, but direct prior art.
3. **Bazaar.** Better gap and the only idea with published support, but the weakest reward integrity, which is where judges attack.
4. **Forecasting Arena.** Dull demo, and mistakes only show in aggregate.
5. **Alien Physics Lab.** A matching demo with a heavier build.

**The deciding design question for every control idea:** can the agent's own code call the environment tools directly? If it can, the reviewer expects the gap to close, because the agent runs its controller in a loop without the model in it.

**Best unwritten idea in Manh's file:** "epidemic control where interventions act with a delay". It is Lightlag's mechanic with the simplest simulator.

## Same mechanic, other settings (not reviewed)

Lightlag's mechanic is "actions land late, information is old, and part of the system must be learned by trying". Kristján asked for non-Mars versions. None of these has been scored.

- **Floodgate:** run a chain of dams before a storm. Released water takes hours to reach the town, and how much rain runs off has to be learned. Holding water earns power revenue, releasing it prevents a flood.
- **Balloon:** fly a hot-air balloon to a target. The burner acts slowly and you steer only by choosing a wind layer, so the winds have to be explored.
- **Fishery:** set yearly catch quotas from old, noisy stock surveys. Over-fishing collapses the stock for good.
- **Harbour pilot**, **central banker**, **outbreak** and **line cook** are further variants; the first two are pure control and the most likely to be solved by a script.

## Recommendation from Claude (Kristján's session), updated 23:15

Kristján has not signed off on this; it is the agent's reading of both reviews and the research.

**Commit tonight to the mechanic, and treat the setting as a taste choice.** All three sessions arrived at the same thing: learn a partly unknown, delayed system with a few cheap trials, then operate it where mistakes cannot be undone.

- **Reactor (BatchPilot plus test batches):** Manh's spec is the most build-ready, and Manh can validate the physics.
- **Rover, dams or balloon:** the same build with a more visual demo and less prior art.
- **First test, whichever setting:** a bare version and three real agent runs, with the agent allowed to write code. If the gap closes, fall back to Bazaar.

The draft saved tonight can be edited later, so the setting does not have to be final by 23:59.
