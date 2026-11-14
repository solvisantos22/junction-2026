# Lightlag Live: a campaign the reference wins every time

14 November 2026. Owner: Kristján / Claude Code (gap research chat). Code: [`lightlag_live/`](../lightlag_live/README.md), task: [`harbor/lightlag-live/`](../harbor/lightlag-live/), demo: [`viewer/ghosts-demo.html`](../viewer/ghosts-demo.html). **A proposal for the team, not a rules decision.** Nothing here changes `lightlag/`, `lightlag_dynamic/`, `lightlag_mcp/` or the canonical `harbor/lightlag` task.

Kristján asked for a challenge where the reference beats Claude in essentially every run, proved with real runs, with a demo that shows every Claude attempt as a shadow beside the reference.

## Result

**The reference scored higher than all twelve Claude runs.** It is not far ahead of the best of them, and it does not win every mission. Scores are the mean over the task's six missions, from 0 to 1.

![Every saved run against the reference](lightlag-live-results.svg)

| Run | How it played | Score | Six missions | Rovers lost | Reported cost |
|---|---|---|---|---|---|
| **Reference** (`kf_mpc`) | Harbor `-a oracle`, real clock | **0.664** | 0.69 0.75 0.65 0.67 0.62 0.61 | 0 | none |
| Opus 5.5 · agent 2 | OpenCode in Harbor, real clock | 0.610 | **0.75** 0.73 0.42 0.67 0.42 **0.67** | 0 | $1.08 |
| Sonnet 5.5 · agent 1 | OpenCode in Harbor, real clock, task 0.1.0 | 0.599 | 0.66 0.58 0.33 0.56 **0.80** **0.67** | 0 | $1.01 |
| Opus 5.5 · one shot | one request, one program | 0.581 | 0.62 0.40 **0.75** 0.67 0.60 0.44 | 0 | $0.94 |
| Sonnet 5.5 · one shot 2 | one request, one program | 0.446 | 0.66 0.42 0.50 0.58 0.30 0.22 | 0 | $0.18 |
| Haiku 5.5 · one shot 2 | one request, one program | 0.363 | 0.22 0.32 0.28 0.42 0.23 **0.72** | 0 | $0.02 |
| Haiku 5.5 · one shot 1 | one request, one program | 0.321 | 0.50 0.13 0.50 0.53 0.10 0.17 | 0 | $0.02 |
| Haiku 5.5 · one shot 3 | one request, one program | 0.303 | 0.19 0.37 0.44 0.44 0.06 0.32 | 0 | $0.02 |
| Sonnet 5.5 · one shot 1 | one request, one program | 0.226 | 0.53 0.27 0.00 0.44 0.00 0.11 | 1 | $0.10 |
| Opus 5.5 · agent 1 | OpenCode in Harbor, real clock, task 0.1.0 | 0.089 | 0.47 0.07 then cut off | 0 | $3.13 |
| Haiku 5.5 · agent 1 | OpenCode in Harbor, real clock, task 0.1.0 | 0.000 | never started | 0 | $0.02 |
| Haiku 5.5 · agent 2 | OpenCode in Harbor, real clock | 0.000 | 0.00 0.00 then its session ended | 0 | $0.02 |
| Do nothing | Harbor `-a nop` | 0.000 | | | |
| Stop early | reference cut off after 90 s | 0.223 | 0.69 0.65 then nothing | | |

Bold mission scores are above the reference's. Every folder is under [`docs/lightlag-runs/`](lightlag-runs/) as `live-*`, with the request, the reply and the program for one-request runs and the full OpenCode trajectory for agent runs.

What the agent runs did:

- **Sonnet** read the rules and the map, wrote an autopilot with its own position filter, wrote its own simulator from the published rules, swept three parameters on it, started the campaign 13 minutes in and played all six missions. It beat the reference on missions 5 and 6.
- **Opus**, first run, did the same more thoroughly and for too long: 28 of its 30 minutes. It started the campaign 58 seconds before Harbor's limit and was cut off in mission 2. Task 0.1.0 did not tell the agent its session limit; 0.1.1 does.
- **Opus**, second run, on 0.1.1: wrote a 489-line autopilot, tested it against a mock of its own, started six minutes in and played all six missions. It beat the reference on missions 1 and 6 and tied mission 4. Its program was copied out while it ran and replayed on the 40 exploration maps: 0.46 against the reference's 0.52, with the reference higher on 23 maps and the program on 15.
- **Haiku**, first run, read the rules, the map and the helper, then spent its whole 32,000-token output limit reasoning and wrote no program. The same happened to its one-request attempts at medium and high effort (64,000 and 32,000 tokens, no program); at low effort it wrote one each time. Its second run wrote a 7 kB autopilot in one go and started it untested two minutes in; the program took no sample in two missions, and the session ended during the third.

What the reference does better, summed over the six missions:

| Run | Value sampled on time | Failed samples | Hazard stops | Missions ended away from base |
|---|---|---|---|---|
| Reference | 62% | 2 | 0 | 0 |
| Opus 5.5 · agent 2 | 60% | 6 | 0 | 0 |
| Sonnet 5.5 · agent 1 | 57% | 3 | 1 | 0 |
| Opus 5.5 · one shot | 57% | 10 | 0 | 0 |
| Sonnet 5.5 · one shot 2 | 43% | 12 | 2 | 0 |
| Haiku 5.5 · one shots | 30–52% | 7–24 | 0 | 3–4 each |

The reference knows where the rover is. It almost never spends a sample on a place that is not the target, it never drives into a hazard, and it spends what battery is left on late targets for a quarter of their value (another 21% of the value, against 0–6% for the three best Claude runs). Both agents estimated nearly as well as the reference and then left battery unused: Sonnet's kept a fixed 15-unit reserve, and Opus's ended its missions with 13 to 22 units.

A separate check, not part of the task: **driving by hand, turn-based, Opus scored 0.650 on mission 2 against the reference's 0.750** ([run](lightlag-runs/turn-noise2-seed9007-opus-5-5/), $0.63). So the turn-based format at this noise level gives no wider gap than the campaign does.

## What the task is

Six `rush_noisy` missions in a row, on a clock that runs in real time.

- **Each mission is unchanged.** It is a `DynamicEnvironment` episode with the team's physics, five tools and scoring. The campaign's reward is the mean of the six mission scores.
- **The clock is real.** One tick passes every second from the agent's first `uplink` or `advance`, whether or not it calls a tool, and each mission starts the moment the last one ends. Before the start, `rules`, `map` and `telemetry_log` are free, so the agent can prepare for as long as it likes.
- **The noise dial is at 2.** `noise_level` is the dial `lightlag_dynamic` already publishes "so difficulty can rise as controllers improve". At 2, a position fix is off by 0.6 m per axis against a 0.75 m sampling radius, and the heading bias starts anywhere within 10 degrees.
- **The agent has to build an autopilot.** A 50-tick mission is over in 50 seconds, so nobody can drive by calling tools by hand. The agent's container holds a small helper that gives a program the five tools as function calls, and the instruction says so.

The reference is the team's frozen `kf_mpc`, started fresh for each mission.

## Why this design, and what was dropped on the way

Each step below was tested before the next was built. All of it used seeds 8000–8039, which are not the task's.

1. **Making the agent write an autopilot is not enough against Opus.** Asked once for a mission autopilot at the standard noise level, Opus 5.5 wrote 608 lines that scored 0.78 on `rush` and 0.65 on `rush_noisy` over 40 maps each; the reference scored 0.76 and 0.68. No rover was lost. Sonnet's scored 0.62 and 0.34 with 11 rovers lost. So the first hypothesis, "a real-time clock alone will beat Claude", was wrong for Opus and was dropped.
2. **State estimation under noise is where the reference pulls away.** With the dial at 2, on the same 40 maps:

   | Controller | Mean score | Maps where the reference scores higher |
   |---|---|---|
   | Reference (`kf_mpc`) | 0.52 | |
   | Opus autopilot, told the noise level | 0.43 | 25 of 40, 2 ties |
   | Opus autopilot, written for level 1 | 0.25 | 37 of 40, 2 ties |
   | Sonnet autopilot, told the noise level | 0.25 | 35 of 40, 2 ties |
   | Haiku autopilot, told the noise level | 0.25 | 38 of 40, 1 tie |
   | Plan that never reads telemetry | 0.29 | 36 of 40 |

   The spread between a blind plan and the reference also grows, from 0.53 against 0.68 at level 1 to 0.29 against 0.52 at level 2, so skill counts for more.
3. **One mission is a coin flip; six are not.** Against Opus's best autopilot the reference wins 25 of 40 single missions. Averaging over a campaign is what turns a per-mission edge into a result that repeats.
4. **The reference was left as it is.** A search over its ten decision thresholds at level 2 (200 settings, seeds 20000–20079, checked on 21000–21079) found nothing clearly better: 0.505 for the frozen values against 0.52–0.54 for the best eight. The team's other controllers also sit at 0.52–0.53.

## How the six missions were chosen

By one rule that looks only at the reference: **the first six seeds from 9001 upward on which `kf_mpc`, turn-based at noise level 2, ends at base with a score of at least 0.6.** That gives 9003, 9007, 9008, 9012, 9013 and 9020. The rule and the seeds were committed (`3ff2210`) before any model-written program touched these maps.

This matters and should be said out loud in any presentation: over all forty candidates, 9001–9040, the reference averages 0.50; on the six chosen missions it averages 0.66. The rule picks missions the reference handles well. On unselected maps the reference still wins most campaigns, but not all: resampling the 40 exploration maps, it beats Opus's best autopilot in 88% of six-mission campaigns, and the other five autopilots in all of them.

## Reward integrity

| Check | Result |
|---|---|
| Reference through Harbor on the real clock | **0.664352**: 0.688, 0.750, 0.646, 0.667, 0.625, 0.611. Identical to its turn-based scores, so it loses nothing to the clock |
| Do nothing (`-a nop`) | **0.000000** in 21 s: the collect hook lets all 300 ticks pass at once |
| Stop early (the reference cut off by Harbor after 90 s) | **0.222917**: 0.688, 0.650, then four zeros. Commands already queued still ran |
| A rejected first `uplink` | does not start the clock (tested) |
| Later missions' maps | not served before their mission starts (tested); no tool returns a seed or a score |
| Malformed or missing result | the verifier fails instead of writing a reward (tested) |

The simulator, seeds and token live in the sidecar container, as in `harbor/lightlag`; the agent's image holds only the client helper (tested). Stopping early earns what was finished and nothing more, which is stricter than the single-mission task.

## Run it

```sh
harbor run -p harbor/lightlag-live -a oracle                                   # reference, about 5.5 minutes
harbor run -p harbor/lightlag-live -a nop                                      # do nothing
harbor run -p harbor/lightlag-live -a oracle --agent-timeout-multiplier 0.05   # stop early
harbor run -p harbor/lightlag-live -a opencode -m anthropic/claude-opus-5-5 --ak version=1.19.5 --env-file .env
python3 -m unittest discover -s tests/lightlag_live -v
```

Harbor 0.25.0, local Docker. The task needs a backend that supports Docker Compose sidecars, like `harbor/lightlag`.

## The demo

[`viewer/ghosts-demo.html`](../viewer/ghosts-demo.html), one file, double-click. It replays the six missions with every saved run on the same ground: the reference in gold, the Claude run you follow in blue, every other Claude run as a dark shadow, and live standings on the right. [Controls and limits](../viewer/ghosts/README.md).

## Spend

Reported usage on Kristján's key, not a checked balance. SPEND_PLACEHOLDER

## What this does not show

- **It is a small sample.** One campaign per run, and one to three runs per model and method. "Every run so far" is not a measured win rate.
- **The lead over the best Claude runs is narrow.** Against Haiku and against one-request Sonnet programs the reference is far ahead. Against Sonnet's agent and Opus's one-request program it leads by 0.07 to 0.08, and it loses single missions to both.
- **The lead over Opus exists at noise level 2 and not around it.** At level 1 Opus's one-request autopilot matched the reference, and at 2.5 it matched it again (0.40 against 0.39 on the 40 exploration maps). Level 2 is where the frozen reference does best relative to Claude; that is why it was chosen, and it should be described that way.
- **The missions are chosen by the reference's own score.** See above. It is disclosed, model-blind and fixed in advance, and it favours the reference.
- **The reference is not an optimum.** It samples about a third of the value late and reaches about a quarter of the value in discoveries. A better controller is possible; nothing here found one.
- **One-request programs ran on a simulated clock**, restarted fresh for every mission. Both choices favour the program. Agent runs through Harbor ran on the real clock with no such help.
- **Only Claude models were run.** No other provider's model has played this task.
- **Reproducibility of agent runs depends on wall time.** An agent that prepares for too long is cut off by the session limit. Task 0.1.1 states the limit; 0.1.0 did not, and the first Opus agent run was lost to it.

## Decisions for the team

1. **Whether this becomes the judged task.** It reuses the team's simulator, reference, Harbor layout and replay format, so the auditor and the Mars demo still apply mission by mission. It is a different claim from the turn-based task: "can the agent build an autopilot that estimates well under noise" and no longer "can it drive by hand through delay".
2. **Whether to keep the mission rule.** The alternative is six unselected seeds, with a reference near 0.50 and a win rate against Opus's best program near 88% of campaigns on the exploration maps.
3. **Whether to say "every time".** The evidence supports "in every run so far". The title of this page is the request, not a guarantee.
4. **Who else should play it.** One other frontier model through the same command would show whether this is about Claude or about the task.
