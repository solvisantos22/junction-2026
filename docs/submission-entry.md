# The platform entry: text to paste and steps to take

Sunday 15 November 2026, about 06:45 Helsinki. Prepared by Kristján / Claude Code (Traverse session) at Kristján's word. **Nothing was entered, uploaded or submitted by this session.** The form's exact fields were not seen; the blocks below are sized to fit the usual ones. Sölvi's sponsor texts are in [`sponsor-submission.md`](sponsor-submission.md) and are not repeated here.

Deadline: **10:00 Helsinki, saved as FINAL.** A draft is not reviewed. The entry stays editable until 10:00, so save FINAL early and improve it after.

## Steps, in order

| # | Step | Who | State at 06:45 |
|---|---|---|---|
| 1 | Make the repository public, or arrange judge access | Sölvi (owner) | Private. The current files hold no key-shaped string; the history was not scanned |
| 2 | Choose the video and upload it as a public video of at most two minutes | Kristján | The fallback is ready: [`docs/demo-video/lightlag-traverse-demo.mp4`](demo-video/lightlag-traverse-demo.mp4), 1:58. Manh's recorded-voice film replaces it if it is ready in time |
| 3 | Put the video's link in the README's "See it" section | whoever uploads | The README links the file in the repository |
| 4 | Fill the saved **Lightlag** entry with the text below, attach the deck, select both sponsor challenges | one teammate | Draft with empty fields at 05:23 |
| 5 | Save as FINAL, reopen it, and check every link without being logged in | the same teammate | |
| 6 | Reselect the table number: Platform → Team → Team Management → Table Number | Kristján | Reset by the organisers on Saturday |

## Text to paste

**Name**

```
Lightlag Traverse
```

**One line**

```
A Mars rover campaign where frontier agents lose to a planner.
```

**Short description**

```
Lightlag Traverse is an RL environment in Harbor format. An agent drives a rover across three Mars-like sites through a three-tick signal delay, with wheels that slip, ground that stops it and a battery charged only by the sun. A scripted planner scores 0.476. Twenty-five runs by nine frontier models from Anthropic, OpenAI and Google all score less. The reward is computed from the rover's true state in a container the agent cannot reach.
```

**Full description**

```
THE TASK. One rover, three Mars-like sites in a row, one score. Every command lands three ticks late and every position fix is three ticks old. Wheels slip on sand and slopes, ground steeper than the tilt limit stops the rover and wipes its queued commands, and the only fuel is the sun: a battery at zero ends the rover and scores that site nothing. Every rule and formula is public through five MCP tools. There is no reset and no practice run, so in practice the agent has to write a mission autopilot that works the first time.

THE GAP. Our reference is a planner, not a model. It tracks the rover through the delay, learns how each surface slips, and prices every leg of its route against the sun. Through Harbor and OpenCode it scores 0.476. Twenty-five agent runs by nine models (Claude Opus, Sonnet and Haiku 5.5; GPT-6.1 Sol and Terra, GPT-6 Luna; Gemini 4 Carbon, Argon and Hydrogen) all score less, with an average of 0.23. Google's top model comes within 0.003 on its best run and scores zero when its session runs out. On 300 worlds none of them had seen, the reference scored higher than eleven model-written programs in 3,265 of 3,300 match-ups and never lost a rover.

WHY THEY LOSE. The agents write working autopilots within minutes. What they get wrong is planning the day: worse routes (28 to 53% fewer samples), batteries run flat with the way home still open (87% of Claude's lost rovers), and programs that play a whole site before the agent looks.

REWARD INTEGRITY. Doing nothing scores 0 and stopping after one site scores 0.149. The score comes from the rover's true state, computed in the simulator's own container after the agent's has stopped. We ran 27 attacks from inside the agent's container (forged reward files, a fake grader, hidden tools, malformed commands, the delay); none changed the reward.

LEARNING. A small controller trained from scratch on Modal goes from 8% to 36% on held-out worlds and passes every Claude run on the campaign. A model trained to pick the reference planner's strategy gained less than half a point, so the reference stays.

RERUN IT. harbor run -p harbor/lightlag-traverse-campaign -a oracle gives 0.476257 in about two minutes; -a nop gives 0.

Built by Kristján, Sölvi and Manh with Claude Code and Codex. Modal ran the rollout farm, the training and the live demo.
```

**Technologies**

```
Python, Harbor, OpenCode, MCP, Docker, Modal, PyTorch, scikit-learn, three.js, Claude Code, Codex
```

**Links**

| Field | What goes in it |
|---|---|
| Project Demo | `https://kristjansolvi03--lightlag-traverse-live-web.us-east.modal.run` |
| Source Code | `https://github.com/solvisantos22/junction-2026` (after step 1) |
| Video | the public link from step 2 |
| PDF deck | upload [`docs/pitch-deck/lightlag-traverse-deck.pdf`](pitch-deck/lightlag-traverse-deck.pdf) |
| Other links | the sponsor case: `https://github.com/solvisantos22/junction-2026/blob/main/docs/sponsor-submission.md` |

**Challenges:** AfterQuery, Break the Agent, as the main challenge; Best Use of Codex and Best Use of Modal as tech challenges (Sölvi's [handoff](sponsor-submission.md) has their texts and what to check).

## What each claim above rests on

Every figure is in the [README](../README.md) with a link to its file. The three that changed on Sunday morning: the 25 runs and Gemini 4 Carbon's 0.473 ([`tier-comparison.md`](tier-comparison.md)), the 27 attacks ([`traverse-integrity.md`](traverse-integrity.md)), and the learning results ([`learning-final-results/README.md`](learning-final-results/README.md), [`learned-portfolio-results/README.md`](learned-portfolio-results/README.md)).
