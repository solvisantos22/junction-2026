# Lightlag Traverse: demo script and talking points

Saturday 14 November 2026, about 21:15 Helsinki. Owner: Kristján / Claude Code (farm session). A draft for the two-minute video and the 10:30 peer review, with every number traced to its source. Campaign numbers are final: seven Claude agent runs, all below the reference (the Traverse session's table, `docs/lightlag-traverse-campaign.md`).

## The pitch in one sentence

Lightlag Traverse is a Mars rover mission behind a 3-tick light delay: every rule is public, a scripted planner brings its rover home every time, and Claude agents consistently score far less, because they don't budget energy, time or routes the way the physics demands.

## The video, under two minutes

| Time | On screen | Voice-over (draft) |
|---|---|---|
| 0:00–0:15 | `docs/traverse-farm/replays/world-871.html` title screen, then the map | "A rover on 600 by 400 metres of Mars-like ground: craters, sand, rock fields. Every command arrives three ticks late. The sun charges the battery; driving drains it, more uphill and in sand. Run the battery flat and the whole mission scores zero." |
| 0:15–0:50 | Same page: Enter, click "Opus 5.5 · agent 3", speed up with `=`; pause at tick 244, then at 324; final screen | "This is Claude Opus's own autopilot, on a world it has never seen. Two-thirds of the way in it is level with our reference, 0.39 each. Then it keeps collecting, past the point where it could still get home, and at tick 324 the battery runs out holding 19 samples. Score: zero. The reference keeps a reserve and brings 25 samples home." |
| 0:50–1:20 | `viewer/traverse-campaign.html` (the three campaign sites), then the campaign table | "What judges run is a campaign: three unseen sites in a row, scored together. The reference scores 0.476. Seven Claude agent runs through OpenCode all scored less; the best, Sonnet, 0.293. Half of the Opus and Sonnet runs ran a battery flat at a site, the others came home with a third to a half fewer samples, and their autopilots played a whole site in 8 to 30 seconds before the agent looked." |
| 1:20–1:45 | The 300-world table and the 87% number (`docs/traverse-farm.md`) | "It's not one unlucky world. On 300 fresh worlds the reference beats every Claude program on 288 to 300 of them and never loses a rover. And 87% of Claude's lost rovers ran flat while the way home was still open: stopping to recharge would have saved every one." |
| 1:45–2:00 | Terminal: `harbor run -p harbor/lightlag-traverse-campaign -a oracle` | "Everything is public through five tools, and it reruns in Docker: the reference scores 0.476 in two minutes, the same on a laptop, on Modal and through Harbor." |

## Numbers and where they come from

| Claim | Number | Source |
|---|---|---|
| Campaign, reference (Harbor 0.25.0) | 0.476257 (0.459, 0.508, 0.460, all at the lander), about 2 minutes | `lightlag_traverse/README.md`, `docs/lightlag-traverse-readiness.md` |
| Campaign, controls | do nothing 0, stopped after site 1 0.149 | same |
| Campaign, 7 Claude agent runs (OpenCode 1.19.5) | all below the reference: Sonnet 2 0.293, Opus 1 0.267, Opus 3 0.247, Opus 4 0.244, Sonnet 1 0.213, Opus 2 0.120, Haiku 0.000 (ended without a command); Opus mean 0.220 (4 runs), Sonnet 0.253 (2); reported cost $4.15 | `docs/lightlag-traverse-campaign.md` |
| Campaign failures | 3 of 6 Opus/Sonnet runs ran a battery flat at one or two sites (once 13 m from the lander); the other 3 came home with 28–53% fewer samples; programs played a site in 8–30 s of wall time | same |
| One mission, world 2026 | reference 0.565; 7 Opus/Sonnet agent runs average 0.258, best 0.528 | `docs/reference-gap-review/review.json`, `lightlag_traverse/README.md` |
| Gap split on world 2026 | 69% less sample value (0.212 of 0.307), 31% lost or stranded rovers (0.095) | `docs/reference-gap-review/review.json` |
| 300 fresh worlds | reference 0.502, never lost or stranded; higher than every saved Claude program on 288–300 of 300 | `docs/traverse-farm.md` |
| Lost rovers with the way home still open | 257 of 294 (87%); Opus agent 3: 140 of 157, Sonnet agent 1: 90 of 91 | `docs/traverse-farm.md` (point of no return) |
| Stranded rovers | Opus agent 1: way home closed a median 2 ticks before the end; one-request Sonnet: 12 | same |
| World 871 | Opus agent 3 level with the reference at tick 244 (0.39), lost at 324 with 19 samples; Sonnet agent 1 lost at 369, 30 m from the lander; reference 0.524 with 25 samples | `docs/traverse-farm.md` (Demo worlds) |
| Reproducibility | the reference's campaign missions repeat exactly on Modal; Modal repeats the laptop on 16 of 16 missions | `docs/traverse-farm.md` |

## What makes it hard for Claude

1. **Routes.** It collects less science on every mission: it picks the next target greedily, where the reference prices every leg on the real ground and searches visiting orders against deadlines, the clock and a battery-and-sun forecast. This is most of the gap (69% on world 2026).
2. **Energy.** It drives its battery to zero with the way home still open (87% of lost rovers). The sun always outpaces the idle drain, so stopping would have saved them.
3. **Time.** Stranded rovers leave for home a few ticks too late.
4. **Write once, walk away.** Agents write one autopilot and let it run; under light lag nobody is watching in time.

## Why the reference wins

It plans with the physics the rules publish: a cost for every move across the height map (ticks and energy, with the slip it believes), a beam search over visiting orders, a battery floor while collecting and a margin for the trip home, slip learned from odometry, filtered position fixes, and predictions of where the rover will be when a command lands (`lightlag_traverse/pilot.py`, `planning.py`). Tuning its options on Modal moved it by at most +0.005, so it sits near the top of its own design.

## Say these caveats yourself

- The 300-world numbers replay Claude's **saved programs without their agents**. Fair for the one-request programs, which never saw a world; a proxy for agent programs, written during a mission on world 2026.
- Haiku's one agent run on world 2026 scored 0 because its reply hit the output-length limit at tick 8: not a planning failure, so leave it out of claims about planning.
- In an older environment, an "energy ledger" hint fixed most of Claude's energy failures (Sölvi's experiments). That would touch at most the 31% of the gap from lost or stranded rovers; the route-quality gap and the campaign's unseen sites remain.
- Opus agent 1's program uses an unseeded random search against the clock, so its scores vary from run to run.

## Open the pages

- `docs/traverse-farm/replays/world-871.html` and `world-610.html`: standalone, offline. Enter starts, Tab or a click follows a rover, `=` speeds up, `C` is the chase camera.
- `viewer/traverse-campaign.html`: the campaign's three sites.
- `viewer/traverse-demo.html`: every recorded run on world 2026.
