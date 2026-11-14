# Lightlag Traverse: a Mars rover campaign where frontier agents lose to a planner

*Draft of the submission README (Saturday 14 November, about 22:15 Helsinki). Meant to become the repository's front page once the team agrees; numbers are from the files linked in each section.*

**AfterQuery: Break the Agent, Junction 2026.** One rover, three Mars-like sites in a row, a battery charged by the sun, and every command arriving three ticks late. Every rule and formula is public through five tools. A scripted planner brings its rover home at every site; seven Claude agent runs through OpenCode all score less, the closest by 0.18.

## Run it

You need Docker and [Harbor](https://docs.harborframework.com) 0.25.0. From the repository root:

```sh
harbor run -p harbor/lightlag-traverse-campaign -a oracle     # the reference: 0.476257, about two minutes
harbor run -p harbor/lightlag-traverse-campaign -a nop        # doing nothing: 0.0
harbor run -p harbor/lightlag-traverse-campaign -a opencode -m anthropic/claude-opus-5-5 --ak version=1.19.5 --env-file .env
```

The agent run needs a model key in `.env` (never committed). On a slow network add `--agent-setup-timeout-multiplier 3`: installing OpenCode can take minutes, and the flag lengthens only the setup, not the agent's 45 minutes. The score is written to `/logs/verifier/reward.txt`. The single-mission task on world 2026 is the fallback: `harbor run -p harbor/lightlag-traverse -a oracle` (0.564655).

## The task

The agent operates a rover through an MCP server with five tools: `rules`, `map`, `telemetry_log`, `uplink`, `advance` ([instruction](../harbor/lightlag-traverse-campaign/instruction.md)).

- **Three missions** at sites 2027, 2028 and 2029 (fixed before anything played them), each 420 ticks on 600 m by 400 m of ground with craters, a scarp, sand, rock fields and bedrock. About 38 targets are known at launch, with deadlines, and more appear on the way.
- **Light lag:** a command executes 4 ticks after it is sent, one per tick; telemetry arrives 3 ticks late. Only `advance` moves the clock.
- **Physics, all published in `rules()`:** slip grows with slope and depends on the terrain, whose true slip is hidden in a published range; energy per wheel metre and per metre climbed; slopes over 0.36 stop the rover and clear its queue; a hidden, drifting heading bias; noisy position fixes.
- **Power:** a battery of 100, charged by a sun that is low at the start and end of each mission. At 0 the rover is dead.
- **Score:** value sampled × (1 at the lander, ½ alive elsewhere, 0 if the battery ran out), summed over the three missions, divided by all the value there was. Computed from the rover's true state by the simulator in its own container, read by a verifier the agent never touches.

## Results

Harbor 0.25.0, campaign task 0.1.0 ([write-up](lightlag-traverse-campaign.md), runs in [`lightlag-runs/`](lightlag-runs/)):

| Player | Site 2027 | Site 2028 | Site 2029 | Campaign |
|---|---:|---:|---:|---:|
| Reference planner | 0.459 | 0.508 | 0.460 | **0.476** |
| Sonnet 5.5, agent run 2 | 0.351 | 0.260 | 0.269 | 0.293 |
| Opus 5.5, agent run 1 | 0.265 | 0.274 | 0.263 | 0.267 |
| Opus 5.5, agent run 3 | 0.259 | 0.368 | 0.111 | 0.247 |
| Opus 5.5, agent run 4 | 0.332 | 0.398 | lost | 0.244 |
| Sonnet 5.5, agent run 1 | lost | 0.486 | 0.139 away | 0.213 |
| Opus 5.5, agent run 2 | lost | 0.350 | lost | 0.120 |
| Haiku 5.5, agent run 1 | 0 | 0 | 0 | 0.000 |
| Doing nothing | | | | 0.000 |
| The reference, stopped after site 1 | | | | 0.149 |

"lost": the battery ran out (that site scores 0). Haiku ended its session without a command. The models are off the shelf, not fine-tuned; agent runs are OpenCode 1.19.5 with a 45-minute session.

**Not three lucky worlds.** Replayed on Modal on 300 fresh worlds, the reference beats every saved Claude program on 288 to 300 of them and never loses or strands a rover ([farm](traverse-farm.md)).

## Why Claude loses

1. **Worse routes.** Even the runs that came home at every site took 28–53% fewer samples than the reference. A textbook controller, A*-style terrain search with a Kalman filter and greedy target choice, scores 0.270 on the same three sites, about what Claude scores. The reference's edge is planning the whole route: which targets, in what order, against deadlines, the clock and a battery-and-sun forecast.
2. **Flat batteries with home in reach.** Three of six Opus and Sonnet runs ran a battery flat at a site, once 13 m from the lander. On 300 fresh worlds, 87% of the lost Claude rovers ran flat while the way home was still open. Under these rules the sun always out-charges the idle drain, so stopping would have saved them.
3. **Write once, look later.** The agents' autopilots played a whole site in 8–30 seconds of real time; three agents' own reports say the damage was done before they looked.

## Reward integrity

Doing nothing scores 0; stopping after the first site scores 0.149; grading reads the rover's true state after the agent's container has stopped. Harbor reports `NonZeroAgentExitCodeError` on OpenCode runs because OpenCode exits with status 1 after an `EPIPE` at the end of the session; the reward is computed and recorded as usual ([details](lightlag-traverse-campaign.md)).

## See it

- **Story mode** on the judged runs: `viewer/traverse-campaign.html?site=3#story` (or press S; N skips to the next moment).
- **Live on Modal:** [https://kristjansolvi03--lightlag-traverse-live-web.us-east.modal.run](https://kristjansolvi03--lightlag-traverse-live-web.us-east.modal.run) drives any world you choose, on Modal, with the reference, a textbook A* + Kalman controller and two Claude-written autopilots, and shows the replay (about a minute for a new world, instant once cached).
- **Video:** [link to come].

## The team and the tools

Kristján, Sölvi and Manh, with Claude Code and Codex. Modal ran the rollout farm (about 6,000 missions) and Sölvi's learning runs: a small PPO policy trained from scratch rises from 0.087 to 0.377 on validation worlds (greedy 0.381, the reference 0.514) ([learning](learning-campaign-results/pilot/README.md)). Everything we tried and retired along the way is written up under [`docs/`](.).

## Caveats

The reference was improved (0.448 → 0.565 on world 2026) after two early agent runs had beaten it there; the campaign and the 300 fresh worlds were played afterwards. The fresh-world comparison replays Claude's saved programs without their agents.
