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

Pending.
