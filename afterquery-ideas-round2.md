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

## Recommendation from Claude (Kristján's session)

Kristján has not signed off on this yet; it is the agent's reading of the review and the research.

**Lightlag for tonight's draft, with Bazaar as the fallback.**

- **It combines the two ideas already on the table.** It has ColdChain's map and route choices and BatchPilot's delayed reactions, so Sölvi's optimization work and Manh's control background both apply.
- **It has one controlled source of difficulty**, which is what the [benchmark research](docs/research/benchmark-landscape.md) asks for: the same maps with and without the delay.
- **It is the most fun to demo:** a rover driving off a ridge because it trusted a stale reading, next to one that didn't.
- **The risk is real:** the research note says agents write good controllers when they have code access. So the first job is a bare Lightlag loop and three real agent runs. If the agent closes the gap, switch to Bazaar, which is the cheapest to build and has the best published support.

The draft saved tonight is preliminary, so this choice can still change after that first test.
