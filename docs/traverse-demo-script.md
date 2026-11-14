# Lightlag Traverse: demo script and talking points

Saturday 14 November 2026, about 21:15 Helsinki. Owner: Kristján / Claude Code (farm session). A draft for the two-minute video and the 10:30 peer review, with every number traced to its source. Campaign numbers are final: seven Claude agent runs, all below the reference (the Traverse session's table, `docs/lightlag-traverse-campaign.md`).

## The pitch in one sentence

Lightlag Traverse is a Mars rover mission behind a 3-tick light delay: every rule is public, a scripted planner brings its rover home every time, and Claude agents consistently score far less, because they don't budget energy, time or routes the way the physics demands.

## The video, under two minutes

| Time | On screen | Voice-over (draft) |
|---|---|---|
| 0:00–0:15 | `viewer/traverse-campaign.html` title screen, then the map of site 1 | "A rover on 600 by 400 metres of Mars-like ground: craters, sand, rock fields. Every command arrives three ticks late. The sun charges the battery; driving drains it, more uphill and in sand. Run the battery flat and the whole mission scores zero. Judges run three such sites in a row." |
| 0:15–1:00 | Story mode: `viewer/traverse-campaign.html?site=3#story` (or press S; N skips to the next moment). Site 3, ticks 93 and 97; then `?site=1#story`, ticks 392 and 409 | "These are the judged worlds and real Claude agent runs through Harbor. Site 3, tick 93: our reference is at 9% battery, and waits a tick for the sun whenever the next drive would take it under its reserve. Four ticks later Claude Opus drives its battery to zero 152 metres out. Waiting six ticks, then driving home, would have reached the lander. Site 1: Sonnet runs flat 47 metres from the lander, Opus 13 metres from it. Both held 21 samples, worth over 40% of the site, and both scored zero there." |
| 1:00–1:25 | The campaign table | "Across the campaign the reference scores 0.476. All seven Claude agent runs scored less; the best, Sonnet, 0.293. Half of the Opus and Sonnet runs ran a battery flat at a site, the others came home with a third to a half fewer samples, and their autopilots played a whole site in 8 to 30 seconds before the agent looked." |
| 1:25–1:45 | `docs/traverse-farm/replays/world-871.html` final screen, then the 87% number (`docs/traverse-farm.md`) | "It's not three unlucky worlds. Replayed on 300 fresh worlds, every Claude program loses to the reference on 288 to 300 of them, and 87% of its lost rovers ran flat while the way home was still open: stopping to recharge would have saved every one." |
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
| Campaign scenes (story mode) | site 3: the reference waits at 9% battery (tick 93), Opus agent 4 runs flat 152 m out at tick 97 (6 ticks of waiting, then the drive home, would have reached the lander); site 1: Sonnet agent 1 runs flat 47 m from the lander (tick 392), Opus agent 2 13 m from it (tick 409), each holding 21 samples worth 0.43 and 0.40 of the site, both scoring 0 there | the Traverse session's `viewer/traverse_story.py` on the campaign replays (commit `bfdcc93`) |
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

- **Story mode** (the Traverse session's, commit `bfdcc93`, on main once Kristján merges branch `worktree-claude-gap-research`): `viewer/traverse-campaign.html?site=1#story`, or press S on any Traverse page. It plays itself, slows down and flies the camera to each moment that decided a score, and holds a caption card. Where a battery ran flat or the way home closed, the cheapest way home is drawn as dots, green while open and red once closed. N skips to the next moment. The moments come from the replays with the farm's point-of-no-return check (`viewer/traverse_story.py`), and its ticks match the farm's on the campaign runs. Best scenes: site 3, ticks 93 and 97 (the reference waits at 9% battery; Opus agent 4 runs flat 152 m out); site 1, ticks 392 and 409 (Sonnet agent 1 flat 47 m from the lander, Opus agent 2 13 m from it, both holding 21 samples worth over 0.40 of the site); site 3, tick 397 (Sonnet agent 1 passes its point of no return with a full battery after 24 stops on steep ground, ends 72 m out).

- `docs/traverse-farm/replays/world-871.html` and `world-610.html`: standalone, offline. Enter starts, Tab or a click follows a rover, `=` speeds up, `C` is the chase camera.
- `viewer/traverse-campaign.html`: the campaign's three sites.
- `viewer/traverse-demo.html`: every recorded run on world 2026.
