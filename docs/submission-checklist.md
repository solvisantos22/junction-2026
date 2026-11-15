# Submission checklist: every point we can tick

Saturday 14 November, about 22:20 Helsinki; rows for the README, the integrity review, the other labs' runs and the learning result updated Sunday 15 November about 05:10. Kristján's freeze holds (rules 0.1.0, reference 0.1.1, the campaign as the submission). Deadline **Sunday 10:00**; physical peer review 10:30. ✅ done · 🟡 in progress · ⬜ to do.

## Required for the AfterQuery entry

| Item | Status | Owner | Where |
|---|---|---|---|
| Harbor task (instruction, task.toml, environment, tests, solution) | ✅ | Traverse session | `harbor/lightlag-traverse-campaign/` |
| One reward in [0, 1] in `/logs/verifier/reward.txt` | ✅ | Traverse session | `tests/grade.py` |
| At least one real model log and score | ✅ 25 agent runs, nine models, three labs | Traverse session, Manh | `docs/lightlag-runs/campaign-*`, `docs/tier-comparison/runs.jsonl` |
| Short README with the one-command rerun | ✅ the front page since Sunday 05:10 | Traverse session | `README.md`; put the public video link in it once the video is uploaded |
| Public video, at most 2 minutes | 🟡 the fallback is ready: the third cut, 1:58, with Sunday's numbers (nine models, the final learning result, Extra Trees). Manh's second draft, `manh_demo_2.mp4` (1:59, plain words, all nine models in the replay), is the other candidate; the team has not chosen. Nothing uploaded | Kristján uploads | `docs/demo-video/`, `docs/manh-demo/` |
| PDF pitch deck (the Junction guide requires it beside the video) | ✅ built, a proposal nobody has read yet: eleven slides | Traverse session | `docs/pitch-deck/lightlag-traverse-deck.pdf`, talk track in `docs/pitch-deck/README.md` |
| Repository visible to the judges | ✅ public since Sunday about 06:14 | Sölvi (owner) | GitHub settings. The current files hold no key-shaped string (scanned Sunday 04:30), and no commit on `main` adds or removes one (history scanned at 06:25 for Anthropic, OpenAI project, Google and GitHub key shapes; the runs' replay artifacts, videos and built pages were left out) |
| Platform entry (links: repo, video, README) | ⬜ still a draft | Kristján | Junction platform; final submit only on Kristján's word |

## The rubric (100 points)

| Criterion | Points | Our evidence | Still to do |
|---|---:|---|---|
| **The gap**: below a stronger reference, reproducibly | 30 | All 25 agent runs (Claude, GPT, Gemini) below the reference on the campaign: Claude's closest by 0.18, GPT's by 0.10, and the closest of all (Gemini 4 Carbon, 0.473) by 0.003; the reference higher in 6,390 of 6,600 program-world match-ups on fresh worlds (22 programs from all nine models; 95 in 100 against each model's best). Rerun through Harbor on Sunday: reference 0.476257, do nothing 0.000 | **Gemini 4 Carbon nearly ties** (0.473 and 0.449 on the campaign, one run timed out at 0) **and beat the reference once on world 2026** (0.567 against 0.565), with a planner it wrote and tested itself. The judges' models are undisclosed: do not say "no model comes close"; say 0.18 only of Claude |
| **Meaningful difficulty**: explain the mistakes, information available | 30 | Worse routes (28–53% fewer samples); flat batteries with home in reach (87% of lost rovers); write-once autopilots; a textbook A* + Kalman controller scores like Claude (0.270) while route planning is worth 0.2; every formula in `rules()` | Put the controller ladder in the README and the deck |
| **Reward integrity**: hard to game | 25 | Doing nothing 0; stopping early 0.149; true-state grading in a separate container; the `NonZeroAgentExitCodeError` explained; [the exploit hunt](traverse-integrity.md): 27 attacks from inside the agent's container, none changed the reward or disclosed a hidden value | One limit is disclosed, not fixed: the seeds and the simulator's code are in the repository, so its holder can predict a mission; judges can change the seeds in one line. Not run on a Linux host |
| **Craft**: sensible rules, one-command rerun | 15 | Published Mars-like physics; scores repeat exactly on a laptop, on Modal and through Harbor; the README is the front page | Check the commands from a clean clone once the repository is public |
| **Tiebreaker**: a smaller model improving with training | — | Sölvi's final result: 8.3% → 35.9% (PPO) and 36.3% (replay) on 40 held-out worlds; on the campaign 36.6% and 33.4%, every trained seed above every recorded Claude run; greedy 36.7%, reference 47.6% | The fallback video and the deck show it; the two earlier cuts still show the pilot's 0.38 |

## Best use of Modal ($2,000 + $3,000 credits)

| Criterion | Weight | Our evidence | Still to do |
|---|---:|---|---|
| Effective use | 40% | The rollout farm: ~6,000 missions in containers, the 300-world comparison in half an hour, model-written code isolated; Sölvi's training jobs | Keep the app IDs and spend in `docs/prize-evidence.md` current |
| Ambition | 25% | The paired 300-world evaluation, the point-of-no-return analysis on every mission, RL from scratch | — |
| Impact | 20% | It turned "the reference wins on one world" into "on 288–300 of 300"; it found the 87% | — |
| Live deployed demo | 15% | ✅ deployed: https://kristjansolvi03--lightlag-traverse-live-web.us-east.modal.run (pick any world; Modal drives the reference, a textbook controller and six Claude autopilots on it and serves the replay) | Put the link in the README, the video and the platform entry |

## Before 10:00

1. Merge anything left on the Traverse branch, push, make the repository public, and check `main` from a clean clone.
2. Choose and upload the video; put its link in the README. Read the PDF deck once.
3. Platform entry filled and checked (source, video, live demo, deck), saved as FINAL; **submit only when Kristján says so**. Reselect the table number. The text to paste and the steps in order: [`submission-entry.md`](submission-entry.md).
