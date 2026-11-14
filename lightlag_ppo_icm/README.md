# PPO + ICM baseline tester

A generic reinforcement-learning agent that plays the Lightlag environments through the five public tools, as a learned baseline beside the scripted players. It is PPO (a standard policy-gradient method) with an Intrinsic Curiosity Module (a second reward for reaching states the agent cannot yet predict), written in NumPy with no other dependency. Built for the max env (`lightlag_dynamic/biomes/maxenv.py`); it also runs on every `lightlag_dynamic` profile and biome, and on Lightlag Traverse and its MAX map, where nothing has been trained yet.

**A sandbox baseline, not a rules or reference decision.** No model or API call is involved. On 40 fresh missions of the max env the trained agent scores 11.0% of the available value: level with three of the scripted players, above the frozen `kf_mpc` (6.2%), below a hand rule of a few lines on its own observation (15.3%) and well below `max_navigator` (28.2%). The curiosity module made no measurable difference. The agent's main fault is that it spends its energy by mid-mission and never comes home. An optional home guard, added afterwards, keeps the energy and the time for the way home in hand: with it the learned agents come home in 34 to 36 of 40 fresh missions and score 15.7 to 16.9%, 3 to 4 points above the old policy without it (12.8% on the same missions). Training with the guard did no better than switching it on for the old policy, and the agent still leaves the pacing to the guard.

It sits beside the team's learning work on the traverse, which is a different experiment in different files: Sölvi's `lightlag_rl/` (a 256-weight scorer trained with REINFORCE that picks the next target for Kristján's pilot, which does the driving) and its follow-ups. Here the agent chooses every command itself. It reads the frozen traverse and changes none of it.

## Run

From the repository root, Python 3.9+ with numpy (checked on 3.14 with numpy 2.5 and on 3.12 with numpy 1.26):

```sh
python3 -m unittest discover -s tests/lightlag_ppo_icm        # 60 tests, under a minute
python3 -m lightlag_ppo_icm.check --policy lightlag_ppo_icm/policies/max.npz --seeds 2700-2739   # beside the scripted players
python3 -m lightlag_ppo_icm.habits --policy lightlag_ppo_icm/policies/max.npz                    # what it does with its commands
python3 -m lightlag_ppo_icm.train --env max --out lightlag_ppo_icm/runs/max                      # train a new one, about half an hour
python3 -m lightlag_ppo_icm.train --env max --int-coef 0 --out lightlag_ppo_icm/runs/max-alone   # PPO without curiosity
python3 -m lightlag_ppo_icm.train --env max --home-guard --out lightlag_ppo_icm/runs/max-guard   # with the home guard
```

`--env` takes `max`, `max_rocks`, a profile (`rush`, `rush_noisy`, `noisy`, ...), a profile in a biome (`rush_noisy@troy_crust+relay_pass`), `traverse` or `traverse_max`. A run writes `log.jsonl` (one line per update), `best.npz` (the full agent at its best development score) and `policy.npz` (its actor alone, the file a player needs). `runs/` is ignored by git; the policies kept in the repository are in `policies/`.

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

## What building it showed

Things that went wrong on the way. Each says something about the environment as a learning problem.

1. **A dead rover scores 0 whatever it sampled, so an untrained agent has nothing to learn from.** Random commands drive the battery flat in almost every episode. Half a sample's value is paid when it is taken and taken back at the end if the rover died, so the two cancel: in the first test runs on `rush` the score stayed at or below 0.2% for 450,000 decisions, with or without curiosity, with 1 to 7% of the rovers alive at the end. With the battery guard every rover survived and the same settings were at 1.4% and 2.2% after 250,000 decisions and rising. What to spend the energy on is still learned. (Those test runs were not kept; the numbers are from their printed logs.)
2. **Curiosity found a hazard to bump.** The first curious agent parked against a hazard and sent drive after drive into it. Each one was stopped at once and cost almost nothing, and the observation's "previous command" entries kept changing, which the curiosity module took for novelty. The module now sees only the entries that say where the rover is and what is around it, not the echo of the agent's own last action. A test holds that.
3. **Curiosity and energy pull in opposite directions.** The curiosity reward grows with how much the observation changes, so it favours long drives; before the guard that meant an earlier death.
4. **The shortest drive has to fit inside the sampling disc.** With a quarter, a half and a full drive, `rush` (drives up to 5 m, a disc 1.5 m across) reached 4.2% on the development seeds after 1.2 million decisions (`policies/rush-quarter-half-full.log.jsonl`). With 0.5, 1 and 2 m, the lengths the max env's 2 m limit gives anyway, the same learner passed 25% within 0.6 million. Drive lengths are now set from the sampling radius by default (`--metres auto`).
5. **Energy has no price until it is gone.** Nothing in the score charges for a drive, so the agent drives at every turn, and the cost arrives twenty decisions later as a rover that cannot move. That gap is too long for this learner to bridge in three million decisions, with or without the pull toward home. The home guard (Results) now keeps the energy and the time for the way home in hand instead of waiting for the agent to learn it. The team's learning work on the traverse met the same fault: Sölvi's persistence study found that every rover that ended away from base had under 10 battery left, and Kristján's charging-aware follow-up reports that a visit-and-return feasibility check took returns home from 28 of 48 to 48 of 48 (their rows in `TEAM_STATUS.md`).
6. **Sand that trips the slip check is a trap under relay passes.** On the max env the slip check stops a drive at the first step that slips more than its limit and clears the queue. On sand that trips at every step each command moves the rover one 0.1 m wheel step, about 6 cm of ground, and with relay passes the next command arrives only at the next pass: two drives into such sand can cost the rest of the mission. The first version of the home guard priced sand as ground where one stop can happen, and on the development seeds 15 of the 64 `max.npz` missions with it still ended away, 13 of them after two to six slip-check stops on sand (read from the simulator, for diagnosis only). Learning from the first stop helped little (50 of 64 home, against 49), because by then the rover is in the sand. Keeping it off sand from the start wherever the published slip range reaches over the check brought 55 of 64 home at the same score.

## Limits

- One training run per setting, one seed of the network weights. The numbers describe these checkpoints, not how reliably training gets there.
- The belief, the scheduling and the guard are hand-written. This is a learned policy on a hand-written adapter, and the `plain` row shows how much the adapter alone is worth.
- The guard is cautious: on the max env it leaves about 19 of the 100 battery units unspent, because up to a dozen commands can be unconfirmed and each is priced at the dearest rate.
- The belief does not use the beacons or the gyroscope, and one gain cannot hold both bedrock and sand slip.
- The home guard works on the flat 40 m family only (it refuses the traverse). It trusts the belief: it takes the rover to be home within half the base radius of where the belief puts it, and at the end of a mission the belief can be off by more than the radius. It keeps the rover off sand wherever the published slip range can trip the check, which also keeps it from targets on sand. Crust, which hides soft cells under ground mapped as bedrock, is only priced at twice its cost. On the development seeds, of the 9 `max.npz` missions that still ended away with the guard on, 6 had a belief more than 0.75 m off at the end, and their slip-check stops were in crust (35 of 36; read from the simulator, for diagnosis only). Keeping off a crust cell once it has stopped the rover is the obvious next step; reading the beacon ranges would help the end of the way home.
- The home guard is cautious in the way the battery guard is: it prices the way home at the dearest rate with the biggest wheels, and counts a whole stop for any command that can be stopped where the map does not expect it. The guarded rovers end with 15 to 20 battery units left.
- On the traverse and its MAX map the adapter is tested to run (417 decisions, one per slot, bounded observations, rewards adding up to the score, the MAX map's relay passes, wheel scale and wild fixes read from its rules). No policy was trained there: a mission is 420 ticks and takes about a second to play, some twenty times a max env mission.
- The comparison of training with the guard against switching it on is one run each, on 40 missions.
- The check seeds are fresh for these policies. The scripted players were tuned on other seeds (0-59, 1100-1299) and measured on 2600-2639.

## Seeds

Training maps 200000-299999, development 300000-300063, fresh checks 2700-2739 (the first policies) and 2800-2839 (the home guard), each used once and now used. Reserved in `TEAM_STATUS.md` before any run.

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
| `train.py`, `check.py`, `habits.py`, `player.py` | The commands, and a policy as a player |
| `policies/` | Trained policies, the logs of every run reported here, and the rows of the three checks |

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

The first four were started with between 6 and 10 worker processes while other jobs were using the machine, which is why their minutes differ; the number of workers does not change what a run computes. The two home-guard runs ran side by side; `--metres 0.25,0.5,1` is what `auto` gives on the max env. In the logs of the first four the `steps` column was rebuilt as a running total (the trainer wrote one update's count there until that was fixed). No run was repeated to confirm that it reproduces.
