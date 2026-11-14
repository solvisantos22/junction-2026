# Lightlag Live: a campaign the reference wins every time

14 November 2026. Owner: Kristján / Claude Code (gap research chat). Code: [`lightlag_live/`](../lightlag_live/README.md), task: [`harbor/lightlag-live/`](../harbor/lightlag-live/), demo: [`viewer/ghosts-demo.html`](../viewer/ghosts-demo.html). **A proposal for the team, not a rules decision.** Nothing here changes `lightlag/`, `lightlag_dynamic/`, `lightlag_mcp/` or the canonical `harbor/lightlag` task.

Kristján asked for a challenge where the reference beats Claude in essentially every run, proved with real runs, with a demo that shows every Claude attempt as a shadow beside the reference.

RESULTS_PLACEHOLDER

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

LIMITS_PLACEHOLDER
