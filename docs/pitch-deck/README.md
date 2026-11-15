# Lightlag Traverse: the pitch deck

Sunday 15 November 2026, about 06:20 Helsinki. Owner: Kristján / Claude Code (Traverse session), at Kristján's word ("make everything ready for the submission"). The Junction guide asks for a PDF deck beside the video.

**[`lightlag-traverse-deck.pdf`](lightlag-traverse-deck.pdf)**: eleven slides, 1920 by 1080, 3.5 MB. A proposal for the team to change: nobody but Claude Code has read it yet.

Six slides are the demo video's own slides at their last frame, drawn from the same numbers, so the deck and the film cannot disagree. Two carry a frame of the film. Rebuild after any change to the numbers:

```sh
uv run --no-project --python 3.12 --with playwright python -m tools.pitch_deck.make
```

## The slides, and what to say (five minutes at the table)

| # | Slide | Say, in about this many seconds |
|---|---|---|
| 1 | Title | (10) We built a day of driving on Mars for an AI agent, and a planner that beats every agent we ran on it. |
| 2 | The task | (35) One rover, three sites in a row, one score. Every command lands three ticks late. Wheels slip, steep ground stops the rover, and the only fuel is the sun. Every formula is public: the agent can read all of it through five tools. No reset, no practice run. |
| 3 | 13 metres from home | (35) This is Claude Opus's rover: 21 samples on board, battery flat 13 metres from the lander, score zero for the site. Waiting seven ticks for the sun would have saved it. The agents all wrote working autopilots in minutes. What they got wrong was planning the day. |
| 4 | In Claude's own words | (20) Its own report says so: the planner only counted time, and all three sites were played before it checked one result. |
| 5 | The reference | (30) Our reference is a planner, not a model. It tracks the rover through the delay, learns how each surface slips, and prices every leg of its route against the sun. It waits when the battery is low and it is home before dark. |
| 6 | Results | (40) Through Harbor and OpenCode: the reference scores 0.476. Twenty-five runs by nine models from three labs are all below it. Most are far below. Google's top model comes within 0.003 on its best run, and scores zero when its session runs out. |
| 7 | 300 fresh worlds | (30) Was it three lucky worlds? On Modal we replayed the models' own programs on 300 worlds none had seen. Against Claude's six, on this slide, the reference scored higher 99 times in 100. Against every model's best program it is 95 in 100, the film's figure. It never lost a rover. |
| 8 | Models that learn | (35) A small controller trained from scratch goes from 8% to 36% on held-out worlds, past every Claude run on the campaign. And when we tried to beat our own planner with learning, the best model added less than half a point. |
| 9 | Hard to game | (30) Doing nothing scores zero; stopping early earns only what was done. The score comes from the rover's true state in a container the agent cannot reach. We ran 27 attacks from inside the agent's container and none changed the reward. |
| 10 | How it was built | (20) Modal ran the farm, the training and the live demo. Codex and Claude Code built and audited it under our direction. |
| 11 | End card | (15) One command reruns it. The live demo plays any world you pick. Can your agent make it home? |

About 300 seconds. Open the live demo on a cached world before the pitch: `https://kristjansolvi03--lightlag-traverse-live-web.us-east.modal.run/world/2027`.

**The three-minute cut** (the main stage, if we are one of the five): slides 1, 3, 5, 6, 7, 9, 11. Drop the task detail into slide 3's sentence ("every command three ticks late, the only fuel the sun").

## Questions to expect

- **"Gemini 4 Carbon ties you."** Nearly, on the three campaign worlds: 0.473 and 0.449 against 0.476, and one run of three timed out at zero. On the one-site task one of its runs is above the reference (0.567 against 0.565). Its program, replayed on 300 worlds it had not seen, averages 0.410 against the reference's 0.502. Its best run wrote a simulator of its own and tested its autopilot there before starting the mission, which is what most agents skipped.
- **"Did you tune the reference on the test worlds?"** No. It was improved once, on the one-site world, after two early agent runs had beaten its first version there. The campaign's three worlds and the 300 fresh worlds were played afterwards and nothing was tuned on them.
- **"Can the reward be gamed?"** See [`docs/traverse-integrity.md`](../traverse-integrity.md). One limit is known: the worlds are fixed by seeds that are public with the code. The judges can change the seeds in one line.
- **"Is the trained model an LLM?"** No. It is a small controller that picks the next goal above hand-written navigation. It shows the environment can be learned on; it is not a fine-tuned language model.
- **"Why not replace the reference with the learned model?"** The gains were real and small: 0.48 points for Extra Trees, under the 1-point bar set before the test. The reference stays.

## Where the numbers come from

The six film slides: [`docs/demo-video/README.md`](../demo-video/README.md), "Where each number comes from". The text slides: the campaign baselines ([`docs/campaign-baselines.md`](../campaign-baselines.md)), the integrity review ([`docs/traverse-integrity.md`](../traverse-integrity.md)), the farm ([`docs/traverse-farm.md`](../traverse-farm.md)), Sölvi's final report ([`docs/learning-final-results/README.md`](../learning-final-results/README.md)) and the learned planner ([`docs/learned-portfolio-results/README.md`](../learned-portfolio-results/README.md)).
