# Submission checklist: every point we can tick

Saturday 14 November, about 22:20 Helsinki. Kristján's freeze holds (rules 0.1.0, reference 0.1.1, the campaign as the submission). Deadline **Sunday 10:00**; physical peer review 10:30. ✅ done · 🟡 in progress · ⬜ to do.

## Required for the AfterQuery entry

| Item | Status | Owner | Where |
|---|---|---|---|
| Harbor task (instruction, task.toml, environment, tests, solution) | ✅ | Traverse session | `harbor/lightlag-traverse-campaign/` |
| One reward in [0, 1] in `/logs/verifier/reward.txt` | ✅ | Traverse session | `tests/grade.py` |
| At least one real model log and score | ✅ 7 agent runs | Traverse session | `docs/lightlag-runs/campaign-*` |
| Short README with the one-command rerun | 🟡 draft | Kristján + farm session | `docs/submission-readme.md`, to become `README.md` |
| Public video, at most 2 minutes | 🟡 being made | Traverse session | `tools/demo_video/`, script `docs/traverse-demo-script.md` |
| Platform entry (links: repo, video, README) | ⬜ still a draft | Kristján | Junction platform; final submit only on Kristján's word |

## The rubric (100 points)

| Criterion | Points | Our evidence | Still to do |
|---|---:|---|---|
| **The gap**: below a stronger reference, reproducibly | 30 | All 7 agent runs below the reference on the campaign (closest by 0.18); every run below on world 2026; 288–300 of 300 fresh worlds | Rerun the reference from `main` through Harbor once more (0.476257 expected) |
| **Meaningful difficulty**: explain the mistakes, information available | 30 | Worse routes (28–53% fewer samples); flat batteries with home in reach (87% of lost rovers); write-once autopilots; a textbook A* + Kalman controller scores like Claude (0.270) while route planning is worth 0.2; every formula in `rules()` | Put the controller ladder in the README and the deck |
| **Reward integrity**: hard to game | 25 | Doing nothing 0; stopping early 0.149; true-state grading in a separate container; the `NonZeroAgentExitCodeError` explained | Get the result of Codex's exploit hunt (claimed 19:04, unpublished); judges will spend 15 minutes on it |
| **Craft**: sensible rules, one-command rerun | 15 | Published Mars-like physics; scores repeat exactly on a laptop, on Modal and through Harbor | Make the README the front page; check the commands from a clean clone |
| **Tiebreaker**: a smaller model improving with training | — | Sölvi's PPO 0.087 → 0.377 on validation worlds (greedy 0.381, reference 0.514) | Sölvi: a clean before/after on the final frozen code, one paragraph and a figure |

## Best use of Modal ($2,000 + $3,000 credits)

| Criterion | Weight | Our evidence | Still to do |
|---|---:|---|---|
| Effective use | 40% | The rollout farm: ~6,000 missions in containers, the 300-world comparison in half an hour, model-written code isolated; Sölvi's training jobs | Keep the app IDs and spend in `docs/prize-evidence.md` current |
| Ambition | 25% | The paired 300-world evaluation, the point-of-no-return analysis on every mission, RL from scratch | — |
| Impact | 20% | It turned "the reference wins on one world" into "on 288–300 of 300"; it found the 87% | — |
| Live deployed demo | 15% | none yet | 🟡 the farm session is deploying a Modal web endpoint: pick a world, watch the reference and Claude's autopilots |

## Before 10:00

1. Merge anything left on the Traverse branch, push, and check `main` from a clean clone.
2. README to the front page; video link and live-demo link filled in.
3. Platform entry filled and checked; **submit only when Kristján says so**.
