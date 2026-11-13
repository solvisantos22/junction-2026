# Lightlag dynamic-rules pilot: deadlines, discoveries and time pressure

14 November 2026, about 01:45 Helsinki. Owner: Manh / Claude Code. Code: [`lightlag_dynamic/`](../lightlag_dynamic/README.md), tests: `tests/lightlag_dynamic/`. Runs on Sölvi's simulator in [`lightlag/`](../lightlag/README.md) and changes nothing in it, nor in `lightlag_controllers/`.

**No real agent has been run.** Everything below compares scripted controllers. It shows how the environment behaves under different rules, not whether a frontier agent struggles.

## Why

On the simulator's map the delay barely matters: there is plenty of time, and waiting costs clock rather than battery. Kristján's [pilot](lightlag-pilot.md) found that a plan that never reads telemetry scores 97–101% of the reference on varied maps. This pilot tests whether "varying samples" change that: targets with deadlines, targets discovered mid-mission (the controller learns about them through delayed telemetry), a fresh map every seed, and a time-pressured profile.

## The result in short

**Time pressure is what makes the delay matter.** On the `rush` profile (50 ticks, five targets plus one or two discoveries, tight windows), on 40 seeds (100–139) never used during development:

| Controller, as a share of the reference on the same seed | Delay 0 | Delay 3 | Delay 5 |
|---|---|---|---|
| Cautious: sends a whole leg, waits to see it land | 99% | 80% | 59% |
| Blind plan: plans once from the briefing, never reads telemetry | 71% | 81% | 86% |
| Ignores deadlines and discoveries | 79% | 83% | 83% |
| Treats old telemetry as the present | 99% | 1% (90% die) | 1% (88% die) |
| Do nothing | 0 | 0 | 0 |

The reference got home alive in every episode.

- **Neither shortcut closes the gap.** The blind plan misses discoveries, which arrive only through telemetry (71% even with no delay). Careful waiting runs out of clock (59% at delay 5). Matching the reference requires using late information without waiting for it, which is the skill Lightlag is meant to test.
- **The fairness check holds.** With no delay the cautious controller ties the reference (99%), so its loss at delays 3 and 5 comes from the delay itself.
- **Without time pressure there is no gap.** On the simulator's map, and on seeded maps with loose deadlines, the cautious controller scores 95–102% at every delay.
- **Deadlines change the plan.** A controller that ignores them loses 13–24% on `rush`, and 36–44% on the simulator's map with deadlines at delays 3 and 5.

## Cross-check with `lightlag_controllers` and tougher physics

Seeds 0–19 (`python3 -m lightlag_dynamic.crosscheck --hard`). Shares are of this pilot's reference on the same seed. "Tougher physics" is the variant recommended in the team pilot (sampling radius 0.4 m, slip noise ±0.08, sand slip 0.15–0.60), applied through `lightlag_controllers.pilot.physics_overrides()`. `lightlag.evaluation.run_episode` gave the same score as this pilot's runner on 5 of 5 seeds in all four settings.

**Rush, current physics**

| Controller | Delay 0 | Delay 3 | Delay 5 |
|---|---|---|---|
| Reference (this pilot), raw score | 8.95 | 7.97 | 7.05 |
| Cautious: whole leg, then wait | 100% | 77% | 59% |
| `team_move_and_wait`: one command, then wait | 76% | 20% | 13% |
| Blind plan (this pilot / `team_open_loop`) | 70% / 76% | 78% / 82% | 86% / 87% |
| `team_reference` (knows no deadlines or discoveries) | 76% | 76% | 68% |
| Old telemetry as the present (this pilot / `team_stale`) | 100% / 76% | 2% / 0% | 0% / 0% |

**Rush, tougher physics**

| Controller | Delay 0 | Delay 3 | Delay 5 |
|---|---|---|---|
| Reference (this pilot), raw score | 8.86 | 6.03 | 5.10 |
| Cautious: whole leg, then wait | 99% | 96% | 73% |
| Blind plan (this pilot / `team_open_loop`) | 46% / 57% | 78% / 78% | 67% / 88% |
| `team_reference` | 76% | 59% | 26% |

What this adds:
- **`move_and_wait` understates what a cautious agent can do.** Sending one command and then waiting loses heavily (20% on `rush`, 80% on the simulator's map at delay 3). Sending a whole leg and then waiting scores 95–98% on the simulator's map and 77% on `rush`. A leg-and-wait baseline would show the real cost of caution in the team pilot.
- **On `rush`, the team's blind plan beats the team reference** (82% vs 76% at delay 3, 87% vs 68% at delay 5). That reference was built for the plain map: it stops to confirm, and it knows nothing about deadlines or discoveries. A time-pressured rule set needs a reference built for it.
- **Tougher physics and `rush` don't simply add up yet.** With noise ±0.08 and a 0.4 m radius, this pilot's reference loses a quarter of its score at delay 3, and the cautious controller nearly catches up (96%). The reference has to handle noise better first, for example by aiming with a margin and confirming only near the target. This matches the team pilot's warning that a shorter horizon needs a faster reference.
- **On the plain map the team reference is stronger** (104–107% of this pilot's; 122–128% under tougher physics). This pilot's reference only earns its keep on the new rules.

## Limits

- **This pilot's reference is a stand-in and not optimal.** On the simulator's map with deadlines the blind plan beats it (120% at delay 3), because it stops to confirm the sand target before sampling.
- **The `rush` ranges and the fixed-map deadlines are hand-set difficulty dials.** `rush` was designed once and then checked on untouched seeds, not tuned per seed.
- **Exact visual odometry still makes slip easy to learn.**
- **20–40 seeds per row.** Differences of a few percent are noise. Seed sets used: development 0–19, untouched check 100–139. Sölvi's frozen comparison uses 200–209 for its own check, so pick fresh seeds outside these for new checks.
- **`DynamicEnvironment` uses private hooks of `lightlag.Environment`** (`_sample`, `_snapshot` and a few fields); a test guards them.

## Suggested next steps

1. **Rules decision (team):** the cleanest result is `rush`-style time pressure with deadlines and discoveries, on the current physics. Add the tougher physics only once a reference handles the noise.
2. **One reference:** port deadline and discovery handling into the team reference instead of keeping this stand-in.
3. **A fairer cautious baseline:** add "whole leg, then wait" next to `move_and_wait` in the shared comparison.
4. **Plumbing:** an environment-factory argument in `lightlag.evaluation.run_episode`, and the MCP server building `DynamicEnvironment` when a profile is chosen.
5. **Real agent runs** at delays 0 and 3 on `rush`, compared with the reference, the blind plan and the cautious controller. If the agent matches the blind plan, it isn't using feedback; if it matches the cautious one, it isn't predicting.
