# PPO + ICM baseline tester

A generic reinforcement-learning agent that plays the Lightlag environments through the five public tools, as a learned baseline beside the scripted players. It is PPO (a standard policy-gradient method) with an Intrinsic Curiosity Module (a second reward for reaching states the agent cannot yet predict), written in NumPy with no other dependency. Built for the max env (`lightlag_dynamic/biomes/maxenv.py`); it also runs on every `lightlag_dynamic` profile and biome and on the traverse's MAX map. On Kristján's Lightlag Traverse, the map of the team's campaign, it has a second mode in which it picks the targets and Kristján's pilot steers ("On Kristján's campaign: the target mode").

**A sandbox baseline, not a rules or reference decision.** No model or API call is involved. On 40 fresh missions of the max env the trained agent scores 11.0% of the available value: level with three of the scripted players, above the frozen `kf_mpc` (6.2%), below a hand rule of a few lines on its own observation (15.3%) and well below `max_navigator` (28.2%). The curiosity module made no measurable difference. The agent's main fault is that it spends its energy by mid-mission and never comes home. An optional home guard, added afterwards, keeps the energy and the time for the way home in hand: with it the learned agents come home in 34 to 36 of 40 fresh missions and score 15.7 to 16.9%, 3 to 4 points above the old policy without it (12.8% on the same missions). Training with the guard did no better than switching it on for the old policy, and the agent still leaves the pacing to the guard.

**On Kristján's campaign** (the target mode, trained on Modal) the agent picks targets and Kristján's frozen pilot drives. On 300 fresh worlds it scores 38.0% and loses no rover: 2.3 points above always taking the nearest target (95% interval +1.5 to +3.1), 1.6 below a hand rule that weighs value against travel, and 12.6 below Kristján's reference pilot (50.5%). On the campaign's three worlds, played once, it scores 0.375 against the reference's 0.476. Its first training runs settled on the nearest rule and stayed there; a larger entropy bonus, falling over the run, got it past.

It sits beside the team's learning work on the traverse, which is a different experiment in different files: Sölvi's `lightlag_rl/` (a 256-weight scorer trained with REINFORCE that picks the next target for Kristján's pilot, which does the driving) and its follow-ups. In its first mode the agent chooses every command itself. Its target mode makes the split Sölvi's learner makes (the agent picks the next target, Kristján's pilot drives), with this agent's own observation, mask, network and PPO training. It reads the frozen traverse and changes none of it.

## Run

From the repository root, Python 3.9+ with numpy (checked on 3.14 with numpy 2.5 and on 3.12 with numpy 1.26):

```sh
python3 -m unittest discover -s tests/lightlag_ppo_icm        # 74 tests, about a minute and a half
python3 -m lightlag_ppo_icm.check --policy lightlag_ppo_icm/policies/max.npz --seeds 2700-2739   # beside the scripted players
python3 -m lightlag_ppo_icm.habits --policy lightlag_ppo_icm/policies/max.npz                    # what it does with its commands
python3 -m lightlag_ppo_icm.train --env max --out lightlag_ppo_icm/runs/max                      # train a new one, about half an hour
python3 -m lightlag_ppo_icm.train --env max --int-coef 0 --out lightlag_ppo_icm/runs/max-alone   # PPO without curiosity
python3 -m lightlag_ppo_icm.train --env max --home-guard --out lightlag_ppo_icm/runs/max-guard   # with the home guard
```

The target mode on Kristján's traverse:

```sh
python3 -m lightlag_ppo_icm.campaign --policy lightlag_ppo_icm/policies/traverse-targets-ent10.npz   # Kristján's campaign, scored as the task scores it
python3 -m lightlag_ppo_icm.check --policy lightlag_ppo_icm/policies/traverse-targets-ent10.npz --seeds 420000-420031
python3 -m lightlag_ppo_icm.habits --policy lightlag_ppo_icm/policies/traverse-targets-ent10.npz --seeds 420000-420031
PYTHONPATH=. modal run --detach lightlag_ppo_icm/modal_train.py::fit --out traverse-targets-ent10 --int-coef 0 --ent-coef 0.1 --ent-final 0.1   # train on Modal
python3 -m lightlag_ppo_icm.train --env traverse --targets --updates 200 --eval-every 10 --gamma 0.999 --int-coef 0 --ent-coef 0.1 --ent-final 0.1 --out lightlag_ppo_icm/runs/targets   # the same run locally
```

`--env` takes `max`, `max_rocks`, a profile (`rush`, `rush_noisy`, `noisy`, ...), a profile in a biome (`rush_noisy@troy_crust+relay_pass`), `traverse` or `traverse_max`; `--targets` (on `traverse` only) trains the target mode. A run writes `log.jsonl` (one line per update), `best.npz` (the full agent at its best development score) and `policy.npz` (its actor alone, the file a player needs). `runs/` is ignored by git; the policies kept in the repository are in `policies/`.

A trained policy is a player like any other, a callable that gets the five tools:

```python
from lightlag_dynamic.biomes.maxenv import make_max_env
from lightlag_dynamic.tools import PublicTools
from lightlag_ppo_icm.player import load_player

env = make_max_env(seed=7, delay=3)
load_player("lightlag_ppo_icm/policies/max.npz")(PublicTools(env))
```

## What is learned and what is fixed

The policy network is the learned part. Everything in the table is fixed, hand-written, and uses only `rules()`, `map()`, telemetry and the agent's own acknowledged commands.

| Fixed part | What it does | File |
|---|---|---|
| Slot scheduling | One decision fills one execution slot. On an open link that is one command per tick; on the last tick before a relay pass closes it is every slot up to the next pass. No slot is left empty or filled twice (tested) | `task.py` |
| Belief | A four-number Kalman filter: position, and one gain (a scale and a rotation) that stands for wheels of a hidden size, slip and the heading bias. It uses position fixes, visual odometry and the sun compass when telemetry has them, holds back wild fixes, and replays acknowledged drives across lost packets. Far plainer than the particle filter of `max_navigator` | `belief.py` |
| Expected state | The observation describes the rover where it is expected to be when the slot runs, with the commands still on their way applied on the published numbers. That is how the signal delay is handled | `task.py`, `ground.py` |
| Battery guard | A command that could empty the battery before the horizon, with every unconfirmed drive priced at the dearest published rate, is replaced by a wait. See "What building it showed" | `task.py` |
| Home guard (optional, `--home-guard`; off by default) | Before a command is sent, it looks at where the command leaves the rover. If the way home from there would no longer fit in the energy or the time left, it sends its own command instead: the next drive of the way home, or a wait at the base. The way home goes around hazards, and around sand where the published slip range can trip the onboard slip check (or once a stop by the check has been seen). Energy is priced as the battery guard prices it; time is the drives home plus two slots, plus the slots a stop can cost when the command can be stopped where the map does not expect it. With the guard on, the observation's two margins for getting home are the guard's own. Flat 40 m family only | `home.py`, `task.py` |
| Observation | 138 numbers: clock, battery, belief, the value sampled so far, the base with time and energy margins for getting home, the six nearest open targets (direction, distance, in range, value, slack to the deadline), and for 16 headings the distance to a stop, to soft ground and to risky ground | `task.py` |
| Actions | 50: wait, sample, or drive at one of 16 headings for one of three lengths (2/3, 4/3 and 8/3 of the sampling radius, capped at the longest drive allowed: 0.5, 1 and 2 m on the max env) | `task.py`, `train.py` |
| Reward | The official score, cut up so that an episode's rewards add up to `raw_score / max_available_value` exactly (tested): half of a sample's credited value when it is taken, the rest at the last decision | `task.py` |

Because the adapter does this much, `check` always prints two players that use the same adapter without a network: `random` (random actions) and `plain` (a rule of a few lines: drive at the nearest open target, sample in range, go home when the margins run low). The difference between `ppo_icm` and those two is what the learning added. For a policy trained with the home guard it also prints `plain_home`, the same rule with the guard on; `random_home` and `ppo_icm_home` (any policy with the guard switched on) can be named, and `--also-home NAME=POLICY` adds another policy with the guard on.

## The learner

- **PPO**: clipped objective (0.2), generalised advantage estimation (gamma 0.995, lambda 0.95), 128 missions per update, four epochs of eight minibatches, Adam at 3e-4 falling to 30%, gradient norm capped at 0.5, entropy bonus 0.005, early stop of an update when the policy has moved too far. Actor and critic are separate networks of two tanh layers of 128.
- **ICM** (Pathak et al. 2017): an encoder to 64 features, an inverse model that predicts the action from the features of two consecutive observations (this trains the encoder), and a forward model that predicts the next features from the current ones and the action. The curiosity reward is half the squared error of the forward model, divided by a running standard deviation of its discounted return. The policy is trained on `10 x extrinsic + int_coef x curiosity`, with `int_coef` 0.5 falling to 0.05 over the run.
- **Training data**: every episode is a new map (seeds 200000-299999), so a mission cannot be memorised. The development seeds 300000-300063 pick the checkpoint that is kept. The fresh check seeds are played once, afterwards.
- Every gradient is written by hand and checked against finite differences in the tests.

## Results

One training run per row, on a laptop CPU. Checked once on fresh seeds 2700-2739 (40 missions, delay 3). "Home" counts missions that end alive at base. The last column is the PPO + ICM policy minus that player, in points, with a 95% bootstrap interval over the seeds.

**The max env** (`python3 -m lightlag_ppo_icm.check --policy lightlag_ppo_icm/policies/max.npz --also ppo_alone=lightlag_ppo_icm/policies/max-ppo-alone.npz --players ppo_icm,ppo_icm_sampled,plain,random,nothing,max_navigator,fused,c37,kf_mpc,blind`; rows in `policies/max.check-2700-2739.json`):

| Player | Share | Dead | Home | PPO + ICM minus it |
|---|---|---|---|---|
| `max_navigator` (the max env's scripted controller) | 28.2% | 0 | 33 | -17.2 (-21.8 to -12.6) |
| `plain` (a hand rule on this adapter) | 15.3% | 0 | 17 | -4.3 (-7.8 to -0.9) |
| `blind` (plans once, never reads telemetry) | 12.3% | 0 | 21 | -1.3 (-7.0 to +3.9) |
| `fused` (the fusing reference) | 11.5% | 0 | 8 | -0.4 (-4.1 to +3.2) |
| **`ppo_icm`** (PPO + ICM, 3.6 million decisions) | **11.0%** | 0 | 0 | |
| `ppo_alone` (the same without curiosity, 3.0 million) | 10.7% | 0 | 1 | +0.3 (-2.5 to +2.8) |
| `c37` (Manh controller 37) | 9.8% | 0 | 29 | +1.2 (-1.8 to +4.4) |
| `ppo_icm_sampled` (actions drawn as in training) | 9.3% | 0 | 0 | +1.7 (-0.4 to +4.0) |
| `kf_mpc` (the frozen reference) | 6.2% | 0 | 14 | +4.9 (+2.0 to +7.5) |
| `random` (random actions on this adapter) | 0.1% | 0 | 0 | +10.9 (+8.8 to +13.0) |
| `nothing` | 0.0% | 0 | 40 | +11.0 (+8.9 to +13.1) |

What this says:

- **The agent learns the mission from nothing**: 11 points above random actions on the same adapter. It ends level with three of the scripted players (`fused`, `blind`, `c37`), ahead of the frozen `kf_mpc`, and 17 points below `max_navigator`.
- **It is below a rule of a few lines on its own observation** (`plain`, 15.3%). The adapter carries a good part of the result, and the learning has not caught up with what the observation allows.
- **It never comes home**: 0 of 40 missions, against 17 for the rule. A rover that is alive but away from base keeps half of what it sampled, so this alone costs up to half the score. The reason is how it spends its energy (`python3 -m lightlag_ppo_icm.habits`, development seeds 300000-300031): 40 of its 47 decisions are drives and it almost never waits; in 25 of 32 missions the battery guard starts replacing its commands by waits, at decision 22 on average (14 commands a mission over all 32); it ends 6 m from base. It has learned to find and sample targets, not to pace itself.
- **Curiosity made no measurable difference** on the check (+0.3, interval -2.5 to +2.8). During training the run without it was ahead for the first two million decisions and the two were level at three million:

| Decisions | PPO + ICM, development score | PPO alone, development score |
|---|---|---|
| 0.6 million | 6.9% | 9.2% |
| 1.2 million | 8.7% | 10.4% |
| 1.8 million | 10.0% | 11.5% |
| 2.4 million | 9.9% | 11.5% |
| 3.0 million | 11.4% | 11.6% |

One run each, so this shows no benefit; it does not show harm.

**Paying the bonus for being home along the way did not bring it home.** `--home-pull K` adds a potential (K times half the value sampled so far, growing as the rover nears the base), so that driving home is rewarded step by step instead of once at the end; the rewards still add up to the official score (tested). Three runs on the max env, development seeds only:

| Run | Decisions | Best development score | Home, last 50 updates of training |
|---|---|---|---|
| PPO + ICM, no pull (the `max.npz` above) | 3.61 million | 11.4% | 0.2% |
| PPO alone, no pull (`max-ppo-alone.npz`) | 3.04 million | 12.1% | 0.2% |
| PPO + ICM, pull 1 | 3.61 million | 12.9% | 0.1% |
| PPO alone, pull 1 | 3.57 million | 13.3% | 0.1% |
| PPO alone, pull 4 | 2.02 million | 12.1% | 0.2% |

No run comes home, which fits the habits above: by the time going home would pay, the guard is holding the rover still. The development scores with the pull are a point or two higher; with one run each and the best of thirty checkpoints taken on 64 seeds that is not a measured gain (the training scores over the last 50 updates are 10.4 to 11.0% in all five). These three policies were not kept and not played on the fresh seeds; their logs are in `policies/`.

**The home guard.** Two runs with the settings of `max.npz` and the guard on (`--home-guard`), with and without curiosity, checked once on fresh seeds 2800-2839 beside `max.npz` with the guard switched off and on (`python3 -m lightlag_ppo_icm.check --policy lightlag_ppo_icm/policies/max-home-guard.npz --seeds 2800-2839 --also ppo_alone_guard=lightlag_ppo_icm/policies/max-ppo-alone-home-guard.npz --also max_npz=lightlag_ppo_icm/policies/max.npz --also-home max_npz_guard=lightlag_ppo_icm/policies/max.npz --players ppo_icm,plain,plain_home,random,max_navigator`; rows in `policies/max-home-guard.check-2800-2839.json`):

| Player | Share | Dead | Home | PPO + ICM with the guard minus it |
|---|---|---|---|---|
| `max_navigator` | 32.6% | 0 | 34 | -16.4 (-20.8 to -12.1) |
| `plain` (the hand rule, no home guard) | 18.2% | 0 | 19 | -2.0 (-7.5 to +3.0) |
| `max_npz_guard` (`max.npz` as trained, the home guard switched on) | 16.9% | 0 | 36 | -0.8 (-4.9 to +3.2) |
| **`ppo_icm`** (PPO + ICM trained with the home guard, 3.6 million decisions) | **16.2%** | 0 | 34 | |
| `ppo_alone_guard` (PPO alone trained with the home guard, 3.6 million) | 15.7% | 0 | 36 | +0.4 (-3.7 to +4.5) |
| `max_npz` (`max.npz`, no home guard) | 12.8% | 0 | 0 | +3.4 (-0.2 to +7.0) |
| `plain_home` (the hand rule with the home guard) | 10.5% | 0 | 29 | +5.6 (+2.0 to +9.3) |
| `random` | 0.1% | 0 | 0 | +16.1 (+12.3 to +20.0) |

More pairs from the same rows, with the same bootstrap: switching the guard on adds 4.1 points to `max.npz` (+1.7 to +6.6) and takes 7.6 from `plain` (-11.3 to -4.2); PPO alone with the guard minus `max.npz` with it switched on is -1.2 (-6.4 to +3.8).

What this says:

- **The guard brings the learned agents home**: 34 to 36 of 40 missions, against none for `max.npz` without it. Switched on for `max.npz` with no retraining, it adds 4.1 points: fewer samples, but most of them now count in full instead of half.
- **Training with the guard added nothing measurable over switching it on.** Both policies trained with it are level with `max.npz` with the guard switched on. On the development seeds PPO alone looked ahead (about 17% from 1.2 million decisions on, best checkpoint 19.0%, against 15.1% for `max.npz` with the guard; table below); that did not hold on the fresh seeds. Curiosity again made no measurable difference (+0.4, -3.7 to +4.5).
- **The agents still do not pace themselves; the guard does it for them.** On development seeds 300000-300031 (`habits`) both command a drive at 42 of their 47 slots. The guard takes over from decision 15 (PPO + ICM) or 23 (PPO alone) on average and sends 25 and 18 of the 47 commands, and the battery guard no longer has to step in. They end 1.1 and 0.4 m from the base on average, with 18 and 15 battery units left. `max.npz` without the guard, for comparison: the battery guard from decision 22, 14 commands replaced by waits, 6.1 m from the base.
- **The hand rule does better without the guard.** It turns for home when the observation's two margins fall below its own thresholds; with the guard on those margins are the guard's own, which already hold back the way home, so the thresholds come on top of that reserve. On the development seeds (64 missions) it samples 1.0 targets a mission with the guard against 1.8 without and comes home 54 times against 22, and its score falls from 15.7% to 12.5%. Without the guard it stays level with the learned agents with it (+2.0 over PPO + ICM, -3.0 to +7.5).
- **`max_navigator` is still 16 points ahead.**

Development score during the two runs (greedy, the 64 development seeds; `max.npz` with the guard switched on scores 15.1% there):

| Decisions | PPO + ICM with the guard | PPO alone with the guard |
|---|---|---|
| 0.6 million | 4.4% | 6.1% |
| 1.2 million | 8.3% | 16.4% |
| 1.8 million | 11.9% | 17.1% |
| 2.4 million | 10.0% | 17.0% |
| 3.0 million | 13.0% | 17.2% |
| 3.6 million | 14.1% | 16.8% |

**The plain `rush` profile**, as a check that the learner learns where sensing is exact (`policies/rush.npz`, 2.65 million decisions, 17 minutes; rows in `policies/rush.check-2700-2739.json`):

| Player | Share | Dead | Home | PPO + ICM minus it |
|---|---|---|---|---|
| `kf_mpc` | 82.3% | 0 | 40 | -54.3 (-59.2 to -49.2) |
| `reference` | 82.2% | 0 | 40 | -54.2 (-58.8 to -49.4) |
| `blind` | 60.2% | 0 | 38 | -32.1 (-36.2 to -27.5) |
| `plain` | 56.1% | 0 | 31 | -28.0 (-34.5 to -21.4) |
| **`ppo_icm`** | **28.1%** | 0 | 1 | |
| `ppo_icm_sampled` | 26.2% | 0 | 0 | +1.8 (-0.6 to +5.1) |
| `random` | 0.0% | 0 | 0 | +28.1 (+25.3 to +31.4) |

It samples about five targets a mission and, again, does not come home. On this profile the scripted players are far ahead: with exact position fixes the mission is a planning problem, and they plan.

## On Kristján's campaign: the target mode

The team submits Kristján's Lightlag Traverse campaign (`harbor/lightlag-traverse-campaign/`: worlds 2027, 2028 and 2029, three 420-tick missions one after another on the normal map). Learning every wheel command there was out of reach in the time the hackathon left, so the agent has a second mode (`--targets`, `targets.py`) in which it chooses which target to go for next and Kristján's frozen pilot does the rest.

- **What the agent chooses:** one of up to 12 open targets, or home. It chooses when the rover has no target, when a target is discovered, and when a check every 12 ticks finds the current target no longer fits: about 30 choices a mission. Home is final.
- **What is borrowed:** Kristján's pilot (`lightlag_traverse.pilot.Pilot`) does the belief, the driving, the sampling, the charging, the way home and its own rule for when to turn for home. `TargetPilot` subclasses it and replaces only its route planning: the pilot's beam search never runs, and the route is the one target the agent chose. Nothing in `lightlag_traverse/` or the campaign task changes.
- **The home guard is a mask:** a target is offered only when the pilot's own route model says the rover can get there, sample and still get home in time, with every leg 15% dearer in energy and 4 more battery units kept than the pilot keeps. When nothing fits, the rover goes home without asking. The policy cannot pick a masked target: masked logits are set to -1e9 when acting and in the loss (tested, with the gradients checked against finite differences).
- **Observation:** 156 numbers. 12 describe the mission: clock, battery, the sun still to come, the time and energy home, the value sampled and still open, how many targets are on offer, the solar-efficiency estimate and the position uncertainty. 12 more describe each candidate: ticks and energy to get there, what a sample there would credit and its value, the slack to its deadline, the way home from it, the open value within 25 ticks of it, whether it appeared during the mission and whether it is the current target. Candidates are sorted nearest first.
- **Reward:** the official score, as in the first mode: half of each sample's credited value goes to the choice in force when it was taken, the other half at the last choice, or is taken back if the rover died. A mission's rewards add up to `raw_score / max_available_value` (tested).
- **Learner:** the same PPO, curiosity optional, with a discount of 0.999 per choice and home starting at a logit of -4. `--ent-final` lets the entropy bonus fall during a run, as the learning rate does.
- **On Modal** (`modal_train.py`, on Manh's own Modal workspace): the learner runs in one container and each update's 128 missions are played in one-core containers, one mission per call. A 200-update run took 44 to 83 minutes.

Three players use the same adapter without a network, so that what the learning adds can be told apart: `random_targets`, `nearest_targets` (always the first slot) and `cluster_targets`, a hand rule picked on development worlds 420000-420031 among six: the allowed target with the most (what a sample there credits + a quarter of the open value within 25 ticks of it) / (ticks to get there + 5).

**Training.** Four runs of 200 updates of 128 missions (25,600 missions, 0.65 to 0.73 million choices each), greedy development score on worlds 420000-420063, where the nearest rule scores 37.1%:

| Run | Settings | Best development score | At update 50 / 100 / 150 / 200 |
|---|---|---|---|
| `traverse-targets-ppo` (round 1) | PPO alone, entropy bonus 0.01 | 37.1% (update 20) | 37.1 / 37.1 / 37.1 / 37.1 |
| `traverse-targets-icm` (round 1) | PPO + ICM (curiosity 0.5), entropy bonus 0.01 | 37.1% (update 10) | 37.1 / 37.1 / 37.1 / 37.1 |
| `traverse-targets-ent05` (round 2) | PPO alone, entropy bonus 0.05 | 39.4% (update 190) | 37.4 / 37.5 / 37.6 / 38.5 |
| **`traverse-targets-ent10`** (round 2, kept) | PPO alone, entropy bonus 0.1 falling to 0.01 | **39.9% (update 150)** | 36.8 / 38.2 / 39.9 / 38.6 |

- **Round 1 learned the nearest rule and stopped there.** Within 20 updates both runs took the first slot at every choice (all of them, on development worlds 420000-420031, `habits`), the entropy was down to 0.01, and the development score stayed at the nearest rule's own 37.1% for the remaining 180 updates. Curiosity changed nothing. See "What building it showed", item 7.
- **A larger entropy bonus got past it.** Round 2 kept trying other slots (entropy 0.47 and 0.38 at the end, against 0.01) and the development score climbed slowly past the nearest rule's. Both runs were still rising at 200 updates; longer runs were not tried. The kept policy, chosen by its development score before any fresh world was played, skips the nearest target in 9% of its choices (mean slot 0.42; development worlds 420000-420031) and spends more of its battery (52 units left at the end, against 65 for the nearest rule). It never chose home itself: the pilot's home rule turns it home.

**Fresh check**, paired, once, on worlds 430000-430299 (`PYTHONPATH=. modal run lightlag_ppo_icm/modal_train.py::check --policy traverse-targets-ent10/policy.npz --also ent05=traverse-targets-ent05/policy.npz,round1=traverse-targets-ppo/policy.npz --seeds 430000-430299 --players ppo_icm,pilot,greedy,nearest_targets,cluster_targets,random_targets`; rows in `policies/traverse-targets.check-430000-430299.json`):

| Player | Share | Dead | Home | The kept policy minus it |
|---|---|---|---|---|
| `pilot` (Kristján's reference pilot) | 50.5% | 0 | 300 | -12.6 (-13.3 to -11.8) |
| `cluster_targets` (the hand rule) | 39.6% | 0 | 300 | -1.6 (-2.3 to -0.9) |
| `ent05` (round 2, entropy bonus 0.05) | 38.4% | 1 | 299 | -0.4 (-1.3 to +0.4) |
| **`ppo_icm`** (`traverse-targets-ent10.npz`, 0.47 million choices) | **38.0%** | 0 | 300 | |
| `nearest_targets` | 35.7% | 0 | 300 | +2.3 (+1.5 to +3.1) |
| `round1` (`traverse-targets-ppo.npz`) | 35.7% | 0 | 300 | +2.3 (+1.5 to +3.1) |
| `greedy` (the pilot with greedy routes) | 31.8% | 0 | 165 | +6.1 (+4.9 to +7.4) |
| `random_targets` | 14.0% | 0 | 300 | +23.9 (+23.1 to +24.8) |

- **The learning adds a little over the adapter:** 2.3 points over always taking the nearest target, ahead on 176 of the 300 worlds, level on 14, behind on 110.
- **A hand rule does better still.** `cluster_targets` is 1.6 points ahead and wins on 166 of the 300 worlds. On the development worlds where it was picked it led the nearest rule by 3.6 points, and by 1.5 on the other 32 development worlds; here by 3.9. The learned policy has found part of what weighing value against travel is worth, not all of it.
- **Kristján's pilot is 12.6 points ahead.** It plans a whole route with a beam search; this agent picks one target at a time.
- Round 1 plays exactly as the nearest rule on all 300 worlds. The two round-2 runs are level.

**The campaign**, played once after every policy here was frozen, never used to choose (`python3 -m lightlag_ppo_icm.campaign --policy lightlag_ppo_icm/policies/traverse-targets-ent10.npz --also ent05=lightlag_ppo_icm/policies/traverse-targets-ent05.npz --also round1=lightlag_ppo_icm/policies/traverse-targets-ppo.npz --players ppo_icm,pilot,greedy,nearest_targets,cluster_targets,random_targets`; rows in `policies/traverse-targets.campaign-2027-2029.json`). The score is the task's: the value earned in all three missions over the value available in all three.

| Player | Campaign | 2027 | 2028 | 2029 |
|---|---|---|---|---|
| `pilot` (the reference; Harbor gives it 0.476257) | 0.476 | 0.459 | 0.508 | 0.460 |
| `ent05` | 0.399 | 0.407 | 0.441 | 0.347 |
| **`ppo_icm`** (the kept policy) | **0.375** | 0.397 | 0.364 | 0.366 |
| `cluster_targets` | 0.355 | 0.371 | 0.400 | 0.292 |
| `nearest_targets`, and `round1` with the same scores | 0.329 | 0.358 | 0.303 | 0.328 |
| `greedy` | 0.270 | 0.224, away | 0.388 | 0.191, away |
| `random_targets` | 0.135 | 0.084 | 0.195 | 0.124 |

Every rover came home but two of `greedy`'s. Three worlds are a small sample: on the fresh worlds `ent05` and the kept policy are level and the hand rule is ahead of both. The seven recorded Claude agent runs on this campaign scored 0.000 to 0.293 ([write-up](../docs/lightlag-traverse-campaign.md)); they choose every command themselves, while this agent leaves the steering to Kristján's pilot, so that compares whole players, not the learning.

## What building it showed

Things that went wrong on the way. Each says something about the environment as a learning problem.

1. **A dead rover scores 0 whatever it sampled, so an untrained agent has nothing to learn from.** Random commands drive the battery flat in almost every episode. Half a sample's value is paid when it is taken and taken back at the end if the rover died, so the two cancel: in the first test runs on `rush` the score stayed at or below 0.2% for 450,000 decisions, with or without curiosity, with 1 to 7% of the rovers alive at the end. With the battery guard every rover survived and the same settings were at 1.4% and 2.2% after 250,000 decisions and rising. What to spend the energy on is still learned. (Those test runs were not kept; the numbers are from their printed logs.)
2. **Curiosity found a hazard to bump.** The first curious agent parked against a hazard and sent drive after drive into it. Each one was stopped at once and cost almost nothing, and the observation's "previous command" entries kept changing, which the curiosity module took for novelty. The module now sees only the entries that say where the rover is and what is around it, not the echo of the agent's own last action. A test holds that.
3. **Curiosity and energy pull in opposite directions.** The curiosity reward grows with how much the observation changes, so it favours long drives; before the guard that meant an earlier death.
4. **The shortest drive has to fit inside the sampling disc.** With a quarter, a half and a full drive, `rush` (drives up to 5 m, a disc 1.5 m across) reached 4.2% on the development seeds after 1.2 million decisions (`policies/rush-quarter-half-full.log.jsonl`). With 0.5, 1 and 2 m, the lengths the max env's 2 m limit gives anyway, the same learner passed 25% within 0.6 million. Drive lengths are now set from the sampling radius by default (`--metres auto`).
5. **Energy has no price until it is gone.** Nothing in the score charges for a drive, so the agent drives at every turn, and the cost arrives twenty decisions later as a rover that cannot move. That gap is too long for this learner to bridge in three million decisions, with or without the pull toward home. The home guard (Results) now keeps the energy and the time for the way home in hand instead of waiting for the agent to learn it. The team's learning work on the traverse met the same fault: Sölvi's persistence study found that every rover that ended away from base had under 10 battery left, and Kristján's charging-aware follow-up reports that a visit-and-return feasibility check took returns home from 28 of 48 to 48 of 48 (their rows in `TEAM_STATUS.md`).
6. **Sand that trips the slip check is a trap under relay passes.** On the max env the slip check stops a drive at the first step that slips more than its limit and clears the queue. On sand that trips at every step each command moves the rover one 0.1 m wheel step, about 6 cm of ground, and with relay passes the next command arrives only at the next pass: two drives into such sand can cost the rest of the mission. The first version of the home guard priced sand as ground where one stop can happen, and on the development seeds 15 of the 64 `max.npz` missions with it still ended away, 13 of them after two to six slip-check stops on sand (read from the simulator, for diagnosis only). Learning from the first stop helped little (50 of 64 home, against 49), because by then the rover is in the sand. Keeping it off sand from the start wherever the published slip range reaches over the check brought 55 of 64 home at the same score.
7. **Sorting the candidates hands the learner a shortcut.** In the target mode the candidates come nearest first, so "always the first slot" needs no feature at all, and it beats random choices by more than 20 points. Both first runs put all their weight on it within 20 updates, with an entropy bonus of 0.01 beside advantages normalised to unit spread, and then never tried another slot: their development score sat at the nearest rule's own 37.1% for 180 updates, and they play exactly as the rule does on all 300 fresh worlds. Six hand rules on the development worlds showed that choosing beyond the nearest can pay (one led it by 3.6 points), so the fault was the learning, not the observation. An entropy bonus five or ten times larger kept the policy trying other slots, and both runs then climbed past the rule.

## Limits

- One training run per setting, one seed of the network weights. The numbers describe these checkpoints, not how reliably training gets there.
- The belief, the scheduling and the guard are hand-written. This is a learned policy on a hand-written adapter, and the `plain` row shows how much the adapter alone is worth.
- The guard is cautious: on the max env it leaves about 19 of the 100 battery units unspent, because up to a dozen commands can be unconfirmed and each is priced at the dearest rate.
- The belief does not use the beacons or the gyroscope, and one gain cannot hold both bedrock and sand slip.
- The home guard works on the flat 40 m family only (it refuses the traverse). It trusts the belief: it takes the rover to be home within half the base radius of where the belief puts it, and at the end of a mission the belief can be off by more than the radius. It keeps the rover off sand wherever the published slip range can trip the check, which also keeps it from targets on sand. Crust, which hides soft cells under ground mapped as bedrock, is only priced at twice its cost. On the development seeds, of the 9 `max.npz` missions that still ended away with the guard on, 6 had a belief more than 0.75 m off at the end, and their slip-check stops were in crust (35 of 36; read from the simulator, for diagnosis only). Keeping off a crust cell once it has stopped the rover is the obvious next step; reading the beacon ranges would help the end of the way home.
- The home guard is cautious in the way the battery guard is: it prices the way home at the dearest rate with the biggest wheels, and counts a whole stop for any command that can be stopped where the map does not expect it. The guarded rovers end with 15 to 20 battery units left.
- On the traverse and its MAX map the first mode's adapter is tested to run (417 decisions, one per slot, bounded observations, rewards adding up to the score, the MAX map's relay passes, wheel scale and wild fixes read from its rules). No policy of that mode was trained there: a mission is 420 ticks and takes about a second to play, some twenty times a max env mission.
- **The target mode** was trained once per setting, with one seed of the network weights, and the best of 20 development checks was kept, which flatters its development score (39.9%, against 38.0% on the fresh worlds). The steering, the charging and the turn for home are Kristján's pilot's: in the 32 development missions of `habits` the agent never chose home itself. The mask is not airtight. Each training run lost 19 to 25 of its 25,600 rovers, and on fresh world 430019 the `ent05` policy ran its battery flat at tick 390, back at the lander, after driving and sampling late in the day (36 units left at tick 320): the route model's margins did not cover those last legs. The kept policy lost none of its 300 fresh missions. One target at a time, chosen from the 12 nearest that fit, is less than the pilot's whole-route plan.
- The comparison of training with the guard against switching it on is one run each, on 40 missions.
- The check seeds are fresh for these policies. The scripted players were tuned on other seeds (0-59, 1100-1299) and measured on 2600-2639.

## Seeds

Training maps 200000-299999, development 300000-300063, fresh checks 2700-2739 (the first policies) and 2800-2839 (the home guard), each used once and now used. The target mode: training 410000-419999, development 420000-420063 (420000-420127 claimed), fresh check 430000-430299, used once and now used; the campaign's worlds 2027-2029 were played once, after the policies were frozen. `targets.check_worlds` refuses the team's reserved worlds. Reserved in `TEAM_STATUS.md` before any run.

## Files

| File | Contents |
|---|---|
| `nn.py` | Fully connected networks with hand-written backpropagation, Adam |
| `agent.py` | PPO and ICM: losses, gradients, the update, saving and loading |
| `belief.py` | The Kalman filter on position and gain |
| `ground.py` | What the published map says about the ground: expected drives, the view, energy. One class for the flat 40 m family, one for the traverse's height grid |
| `home.py` | The way home for the home guard: a cost-to-go field on a half-metre grid of the published map, around hazards and around sand that can trip the slip check |
| `task.py` | The adapter: slots, observation, actions, the two guards, reward |
| `envs.py` | Environments by name, one episode through the five tools |
| `targets.py` | The target mode: Kristján's pilot with its targets chosen by the agent, the mask, the observation, the rewards |
| `train.py`, `check.py`, `habits.py`, `player.py` | The commands, and a policy as a player |
| `campaign.py` | Players on Kristján's three-mission campaign, scored as the task scores it |
| `modal_train.py` | Training and the check on Modal |
| `policies/` | Trained policies, the logs of every run reported here, the rows of the four checks and of the campaign |

How the runs in `policies/` were started (`python3 -m lightlag_ppo_icm.train ...`; the defaults are 600 updates of 128 missions, and a run with a time limit stops at the update that passes it):

| Files | Options | Ran |
|---|---|---|
| `max.npz`, `max.log.jsonl` | `--env max` | 600 updates, 29.5 minutes |
| `max-ppo-alone.npz`, `.log.jsonl` | `--env max --int-coef 0 --max-minutes 28` | 505 updates |
| `rush.npz`, `rush.log.jsonl` | `--env rush --metres 0.1,0.2,0.4 --updates 500 --max-minutes 17` (what `--metres auto` now gives) | 440 updates |
| `rush-quarter-half-full.log.jsonl` | `--env rush --metres 0.25,0.5,1 --updates 500`, stopped by hand | 205 updates |
| `max-home-pull.log.jsonl` | `--env max --home-pull 1` | 600 updates, 25.2 minutes |
| `max-ppo-alone-home-pull.log.jsonl` | `--env max --int-coef 0 --home-pull 1 --max-minutes 26` | 593 updates |
| `max-ppo-alone-home-pull-4.log.jsonl` | `--env max --int-coef 0 --home-pull 4 --max-minutes 17` | 335 updates |
| `max-home-guard.npz`, `.log.jsonl` | `--env max --home-guard --metres 0.25,0.5,1 --workers 9` | 600 updates, 30.9 minutes |
| `max-ppo-alone-home-guard.npz`, `.log.jsonl` | `--env max --home-guard --int-coef 0 --metres 0.25,0.5,1 --workers 9` | 600 updates, 30.9 minutes |

The target-mode runs were started on Modal (`PYTHONPATH=. modal run --detach lightlag_ppo_icm/modal_train.py::fit --out NAME ...`; its defaults are 200 updates of 128 missions, a discount of 0.999, an entropy bonus of 0.01 and a development check every 10 updates), two at a time, round 1 with up to 100 rollout containers and round 2 with 64:

| Files | Options | Ran |
|---|---|---|
| `traverse-targets-ppo.npz`, `.log.jsonl`, `.summary.json` | `--out traverse-targets-ppo --int-coef 0` | 200 updates, 54 minutes; Modal stopped its learner at update 16 and the run resumed from its checkpoint at update 10 |
| `traverse-targets-icm.log.jsonl`, `.summary.json` | `--out traverse-targets-icm --int-coef 0.5` | 200 updates, 83 minutes; its policy plays as the nearest rule on the development worlds and was not kept |
| `traverse-targets-ent05.npz`, `.log.jsonl`, `.summary.json` | `--out traverse-targets-ent05 --int-coef 0 --ent-coef 0.05` | 200 updates, 44 minutes |
| `traverse-targets-ent10.npz`, `.log.jsonl`, `.summary.json` | `--out traverse-targets-ent10 --int-coef 0 --ent-coef 0.1 --ent-final 0.1` | 200 updates, 49 minutes |

The first four were started with between 6 and 10 worker processes while other jobs were using the machine, which is why their minutes differ; the number of workers does not change what a run computes. The two home-guard runs ran side by side; `--metres 0.25,0.5,1` is what `auto` gives on the max env. In the logs of the first four the `steps` column was rebuilt as a running total (the trainer wrote one update's count there until that was fixed). No run was repeated to confirm that it reproduces.
