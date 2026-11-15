# Saved Junction draft — interactive demo and sponsor cases

Prepared at Sölvi's request. This is the exact saved Description field for the existing Lightlag entry; the limit is 5,000 characters. **Verified after saving Draft, reloading and reopening at about 08:12 Helsinki on Sunday 15 November 2026: 4,651/5,000 characters.** The interactive-demo invitation and direct URL now lead the description. The previous 4,205-character project and sponsor text is retained in full. Name, punchline, main challenge, demo/source/video/evidence links and both Best use of Modal and Best Use of Codex selections are retained. The entry remains Draft; this edit did not submit FINAL.

The current project overview uses [Kristján's entry notes](submission-entry.md) and the [README](../README.md); sponsor claims and their limitations are sourced in the [sponsor evidence pack](sponsor-submission.md). No new experiment or benchmark was run.

Team-voice correction saved and verified after reload/reopen at **06:57 Helsinki**: the Codex paragraph says “We used Codex throughout development on Lightlag.”

## Description

```text
TRY THE INTERACTIVE DEMO
https://kristjansolvi03--lightlag-traverse-live-web.us-east.modal.run/

AfterQuery judges can explore the rover environment in the browser: open a featured world, press Play or Story Mode, and compare the reference planner with model-written autopilots. Inspect their routes, battery use and scores, or choose your own world number. To evaluate your own agent, use the reproducible Harbor task linked in the repository.

Lightlag Traverse is an RL environment for AfterQuery's Break the Agent challenge: one rover, three Mars-like sites, one score. Agents must collect science and get home while commands and telemetry are delayed, wheels slip, slopes block routes, and a solar-charged battery can run flat. Rules and formulas are public through five MCP tools. There is no reset or practice run: the agent must write an autopilot that works.

Our scripted reference planner scores 0.476. Twenty-five campaign runs across nine models from Anthropic, OpenAI and Google all score below it; the closest reaches 0.473. The challenge tests planning over a whole mission: choosing worthwhile targets, forecasting battery and sun, and returning safely. The reward comes from the simulator's true state in a separate container. Doing nothing scores zero; stopping after one site scores 0.149. We ran 27 integrity attacks from the agent's container; none changed the reward.

BEST USE OF MODAL — A learning laboratory built inside a hackathon

Modal powered the complete experiment cycle: parallel rover rollouts, competing reinforcement-learning controllers, fresh-world comparisons and a public interactive demo. Six RL jobs produced 47,840 training missions. Their recorded durations total 14 hours 23 minutes, overlapping into just 2 hours 58 minutes elapsed. This is a measured parallel window versus those same job durations placed end to end, not a laptop benchmark. A separate 1,500-mission comparison finished in about seven minutes on up to 100 CPU containers; its recorded execution times sum to 10.3 hours.

That capacity let our small team compare methods and training seeds simultaneously while continuing development and presentation work. Modal Functions ran the jobs, Volumes kept checkpoints and replays, and Dicts tracked progress. We preserved failed runs, froze policies before fresh tests, and linked results to the source and weights that produced them. Our small replay learner improved from 8.27% to 36.29% on 40 fresh worlds, averaged over three initializations; greedy scored 37.99% and the reference 50.82%. We retained the stronger reference.

Our case for Modal is the combination of scale, scientific checks and a usable deployment: the same project went from investigating agent failures to training and testing alternatives, then to a live app judges can explore. Parallel capacity made that breadth practical within the event. The repository includes checkpoints, app IDs, timing evidence and a reproducible concurrency figure.

BEST USE OF CODEX — From research questions to verified software

We used Codex throughout development on Lightlag: building prototypes, implementing rover controllers and evaluation tools, debugging experiments, and shipping verified increments. Parallel Codex agents worked on implementation and independent reviews, coordinated through shared task claims, isolated worktrees and small commits. Humans chose the hypotheses, budgets, acceptance criteria and stopping decisions.

The contribution went beyond generating code. Codex helped deliver the RL pipeline and Modal orchestration, recover interrupted work without repeating completed training, and turn experimental outputs into reproducible reports. One evaluator fix ensured invalid tool requests could not be swallowed while keeping a valid score. The final hybrid audit checked 2,560 missions across 256 fresh worlds and more than one million replay commands. We reported its modest gain honestly and kept the stronger reference.

We also tested the environment with three OpenAI models in 18 scored agent runs, retaining configurations, trajectories and rewards. These were OpenCode/Harbor benchmark participants, distinct from Codex's development role. Our case is the connected workflow: human research questions became tested implementations, parallel experiments and inspectable evidence. Judges can follow concrete contributions from code changes to saved outcomes, including failures, rather than relying on a claim that AI helped us code.

The public source and sponsor evidence document the results, limitations and team contributions. The live Modal demo lets judges explore rover behavior themselves.
```

## Demo check and links saved

The public Modal homepage and featured world **2027** opened while signed out; Story Mode advanced the replay with changing positions, battery values and scores. The invitation describes the current browser experience and points judges to Harbor for evaluating their own agents. This was a sample replay check, not a new benchmark or a test of arbitrary-world execution. The team is still polishing the website; this edit highlights the current stable URL.

The YouTube link was uploaded and saved separately at about 07:56; see the [upload handoff](video-upload.md).

- Project Demo: https://kristjansolvi03--lightlag-traverse-live-web.us-east.modal.run/
- Source Code: https://github.com/solvisantos22/junction-2026
- Video: https://youtu.be/GifcHfCczHo
- Other Link: https://github.com/solvisantos22/junction-2026/blob/main/docs/sponsor-submission.md

## Remaining handoff

The **Presentation field is still empty**. The team is finalizing the PDF; attach the chosen deck and save FINAL before **10:00 Helsinki**. Existing video and interactive-demo links are saved. If the finished website uses a different URL, update both Project Demo and the opening description link together. Sölvi specifies sponsor narratives in the written submission, not the demo video.
