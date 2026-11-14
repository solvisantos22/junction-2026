# PPO + ICM baseline tester

A generic reinforcement-learning agent that plays the Lightlag environments through the five public tools, as a learned baseline beside the scripted players. It is PPO (a standard policy-gradient method) with an Intrinsic Curiosity Module (a second reward for reaching states the agent cannot yet predict), written in NumPy with no other dependency. Built for the max env (`lightlag_dynamic/biomes/maxenv.py`); it also runs on every `lightlag_dynamic` profile and biome and on Lightlag Traverse.

**A sandbox baseline, not a rules or reference decision.** No model or API call is involved. RESULTS_PLACEHOLDER

It sits beside Sölvi's `lightlag_rl/`, which is a different experiment: a 256-weight scorer trained with REINFORCE that picks the next target for Kristján's Traverse pilot, which does the driving. Here the agent chooses every command itself.

## Run

From the repository root, Python 3.9+ with numpy:

```sh
python3 -m unittest discover -s tests/lightlag_ppo_icm        # 44 tests, under a minute
python3 -m lightlag_ppo_icm.check --policy lightlag_ppo_icm/policies/max.npz --seeds 2700-2739
python3 -m lightlag_ppo_icm.train --env max --out lightlag_ppo_icm/runs/max        # train a new one
python3 -m lightlag_ppo_icm.train --env max --int-coef 0 --out lightlag_ppo_icm/runs/max-plain   # PPO alone
```

`--env` takes `max`, `max_rocks`, a profile (`rush`, `rush_noisy`, `noisy`, ...), a profile in a biome (`rush_noisy@troy_crust+relay_pass`), `traverse`, or `traverse_max` once `lightlag_traverse_max/` is in the checkout. A run writes `log.jsonl` (one line per update), `best.npz` (the full agent at its best development score) and `policy.npz` (its actor alone, the file a player needs). `runs/` is ignored by git; the policies kept in the repository are in `policies/`.

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
| Battery guard | A command that could empty the battery before the horizon, pricing every unconfirmed drive at the dearest published rate, is replaced by a wait. See "What building it showed" | `task.py` |
| Observation | 138 numbers: clock, battery, belief, the base with time and energy margins for getting home, the six nearest open targets (direction, distance, in range, value, slack to the deadline), and for 16 headings the distance to a stop, to soft ground and to risky ground | `task.py` |
| Actions | 50: wait, sample, or drive at one of 16 headings for a quarter, a half or all of the longest drive allowed | `task.py` |
| Reward | The official score, cut up so that an episode's rewards add up to `raw_score / max_available_value` exactly (tested): half of a sample's credited value when it is taken, the rest at the last decision | `task.py` |

Because the adapter does this much, `check` always prints two players that use the same adapter without a network: `random` (random actions) and `plain` (a rule of a few lines: drive at the nearest open target, sample in range, go home when the margins run low). The difference between `ppo_icm` and those two is what the learning added.

## The learner

- **PPO**: clipped objective (0.2), generalised advantage estimation (gamma 0.995, lambda 0.95), four epochs of eight minibatches per update, Adam at 3e-4 falling to 30%, gradient norm capped at 0.5, entropy bonus, early stop of an update when the policy has moved too far. Actor and critic are separate networks of two tanh layers of 128.
- **ICM** (Pathak et al. 2017): an encoder to 64 features, an inverse model that predicts the action from the features of two consecutive observations (this trains the encoder), and a forward model that predicts the next features from the current ones and the action. The curiosity reward is half the squared error of the forward model, divided by a running standard deviation of its discounted return. The policy is trained on `10 x extrinsic + int_coef x curiosity`, with `int_coef` 0.5 falling to 0.05 over the run.
- **Training data**: every episode is a new map (seeds 200000-299999), so a mission cannot be memorised. The development seeds 300000-300063 pick the checkpoint that is kept. The fresh check seeds are played once, afterwards.
- Every gradient is written by hand and checked against finite differences in the tests.

## What building it showed

Three things went wrong on the way, and each says something about the environment as a learning problem.

1. **A dead rover scores 0 whatever it sampled, so an untrained agent has nothing to learn from.** Random commands drive the battery flat in almost every episode. Half a sample's value is paid when it is taken and taken back at the end if the rover died, so the two cancel, and in the first test runs the score stayed at 0.0% for 400,000 steps, with or without curiosity. With the battery guard the rover survives and the same runs start to score within a few updates. What to spend the energy on is still learned.
2. **Curiosity found a hazard to bump.** The first curious agent parked against a hazard and sent drive after drive into it. Each one was stopped at once and cost almost nothing, and the observation's "previous command" entries kept changing, which the curiosity module took for novelty. The module now sees only the entries that say where the rover is and what is around it, not the echo of the agent's own last action. A test holds that.
3. **Curiosity and energy pull in opposite directions.** The curiosity reward grows with how much the observation changes, so it favours long drives; before the guard that meant an earlier death.

## Limits

- One training run per setting, one seed of the network weights. The numbers describe these checkpoints, not how reliably training gets there.
- The belief, the scheduling and the guard are hand-written. This is a learned policy on a hand-written adapter, and the `plain` row shows how much the adapter alone is worth.
- The belief does not use the beacons or the gyroscope, and one gain cannot hold both bedrock and sand slip.
- On the traverse the adapter is tested to run (417 decisions, bounded observations, rewards adding up to the score); no policy was trained there. `traverse_max` was tried once against the unfinished `lightlag_traverse_max/` files in the biomes worktree and ran; it needs a new check when that package lands.
- The check seeds are fresh for this policy. The scripted players were tuned on other seeds (0-59, 1100-1299) and measured on 2600-2639.

## Seeds

Training maps 200000-299999, development 300000-300063, fresh check 2700-2739 (used once, now used). Reserved in `TEAM_STATUS.md` before any run.

## Files

| File | Contents |
|---|---|
| `nn.py` | Fully connected networks with hand-written backpropagation, Adam |
| `agent.py` | PPO and ICM: losses, gradients, the update, saving and loading |
| `belief.py` | The Kalman filter on position and gain |
| `ground.py` | What the published map says about the ground: expected drives, the view, energy. One class for the flat 40 m family, one for the traverse's height grid |
| `task.py` | The adapter: slots, observation, actions, guard, reward |
| `envs.py` | Environments by name, one episode through the five tools |
| `train.py`, `check.py`, `player.py` | The commands, and a policy as a player |
| `policies/` | Trained policies and the logs of their runs |
