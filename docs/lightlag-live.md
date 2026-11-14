# Lightlag Live: what happens when Claude writes the autopilot

14 November 2026. Owner: Kristján / Claude Code (gap research chat). Code: [`lightlag_live/`](../lightlag_live/README.md), task: [`harbor/lightlag-live/`](../harbor/lightlag-live/) (version 0.1.3), demo: [`viewer/ghosts-demo.html`](../viewer/ghosts-demo.html). **A proposal for the team, not a rules decision.** Nothing here changes `lightlag/`, `lightlag_dynamic/`, `lightlag_mcp/` or the canonical `harbor/lightlag` task.

Kristján asked for a challenge where the reference beats Claude in essentially every run, proved with real runs, with a demo that shows every Claude attempt as a shadow beside the reference. This page is what was built, what it showed, and where it falls short of that request.

## Bottom line

- **On the task, the reference scored higher than all fourteen Claude runs:** 0.664 against 0.610 for the best of them. The task grades as intended: doing nothing scores 0, and stopping early scores what was finished.
- **Against Opus that lead is narrow, and most of it comes from how the six missions were chosen.** On 200 fresh maps Opus's one-request autopilot is level with the reference, 0.515 against 0.518. The two programs Opus's agents built in a few minutes are 0.04 and 0.06 behind it.
- **Against Sonnet's and Haiku's one-request programs the lead is real:** 0.10 to 0.31 a map, and the reference wins 89 to 100% of six-map campaigns on maps nobody chose.
- **So this is not a task the reference wins every time against Opus.** Making the agent write an autopilot removes most of the gap, because Opus writes a controller about as good as ours.
- **The same autopilots handle the team's `rush` seed 501.** Opus's programs score 0.75 to 0.83 there and never lose the rover; the reference scores 0.83. Opus playing that map turn by turn lost the rover in four of six attempts. The gap the team has measured is a gap in acting through the delay, and it closes when the model writes a program to act for it.
- **Recommendation:** keep the turn-based task as the judged one, use this as the control experiment that shows what its gap is made of, and use the ghost pages as the demo.

## Result on the task

Scores are the mean over the task's six missions, from 0 to 1.

![Every saved run against the reference](lightlag-live-results.svg)

| Run | How it played | Score | Six missions | Rovers lost | Reported cost |
|---|---|---|---|---|---|
| **Reference** (`kf_mpc`) | Harbor `-a oracle`, real clock | **0.664** | 0.69 0.75 0.65 0.67 0.62 0.61 | 0 | none |
| Opus 5.5 · agent 2 | OpenCode in Harbor, real clock, task 0.1.1 | 0.610 | **0.75** 0.73 0.42 0.67 0.42 **0.67** | 0 | $1.08 |
| Sonnet 5.5 · agent 1 | OpenCode in Harbor, real clock, task 0.1.0 | 0.599 | 0.66 0.58 0.33 0.56 **0.80** **0.67** | 0 | $1.01 |
| Opus 5.5 · one shot | one request, one program | 0.581 | 0.62 0.40 **0.75** 0.67 0.60 0.44 | 0 | $0.94 |
| Sonnet 5.5 · one shot 2 | one request, one program | 0.446 | 0.66 0.42 0.50 0.58 0.30 0.22 | 0 | $0.18 |
| Haiku 5.5 · one shot 2 | one request, one program | 0.363 | 0.22 0.32 0.28 0.42 0.23 **0.72** | 0 | $0.02 |
| Haiku 5.5 · one shot 1 | one request, one program | 0.321 | 0.50 0.13 0.50 0.53 0.10 0.17 | 0 | $0.02 |
| Opus 5.5 · agent 3 | OpenCode in Harbor, real clock, task 0.1.1; its program was killed two minutes in | 0.320 | 0.50 **0.80** 0.18 0.00 0.00 0.44 | 0 | $0.73 |
| Haiku 5.5 · one shot 3 | one request, one program | 0.303 | 0.19 0.37 0.44 0.44 0.06 0.32 | 0 | $0.02 |
| Sonnet 5.5 · one shot 1 | one request, one program | 0.226 | 0.53 0.27 0.00 0.44 0.00 0.11 | 1 | $0.10 |
| Opus 5.5 · agent 1 | OpenCode in Harbor, real clock, task 0.1.0 | 0.089 | 0.47 0.07 then cut off | 0 | $3.13 |
| Haiku 5.5 · agent 3 | OpenCode in Harbor, real clock, task 0.1.2 | 0.058 | 0.19 0.01 0.02 0.07 0.06 0.00 | 0 | $0.04 |
| Haiku 5.5 · agent 4 | OpenCode in Harbor, real clock, task 0.1.2; it ended its session 92 s in | 0.003 | 0.02 0.00 then nothing | 0 | $0.03 |
| Haiku 5.5 · agent 1 | OpenCode in Harbor, real clock, task 0.1.0 | 0.000 | never started | 0 | $0.02 |
| Haiku 5.5 · agent 2 | OpenCode in Harbor, real clock, task 0.1.1; its program was killed two minutes in | 0.000 | 0.00 0.00 0.00 then nothing | 0 | $0.02 |
| Do nothing | Harbor `-a nop` | 0.000 | | | |
| Stop early | reference cut off after 90 s | 0.223 | 0.69 0.65 then nothing | | |

Bold mission scores are above the reference's. Every folder is under [`docs/lightlag-runs/`](lightlag-runs/) as `live-*`, with the request, the reply and the program for one-request runs and the full OpenCode trajectory for agent runs. Each `run.json` says which task version the run played and what happened in it.

What the agent runs did:

- **Sonnet** read the rules and the map, wrote an autopilot with its own position filter, wrote its own simulator from the published rules, swept three parameters on it, started the campaign 13 minutes in and played all six missions. It beat the reference on missions 5 and 6.
- **Opus**, first run, did the same more thoroughly and for too long: 28 of its 30 minutes. It started the campaign 58 seconds before Harbor's limit and was cut off in mission 2. Task 0.1.0 did not tell the agent its session limit; later versions do.
- **Opus**, second run: wrote a 489-line autopilot, tested it against a mock of its own, started six minutes in and played all six missions. It beat the reference on missions 1 and 6 and tied mission 4. Its shell tool killed the program two minutes into the campaign; the agent restarted it within ten seconds and lost nothing by it ([the launch trap](#the-launch-trap-in-011-and-its-fix)).
- **Opus**, third run: wrote its autopilot in one go, tested it once and started three minutes in. The same kill, and this time the agent did not notice for two minutes: missions 4 and 5 scored 0. Replayed without the interruption, its program scores 0.509.
- **Haiku**, first run, read the rules, the map and the helper, then spent its whole 32,000-token output limit reasoning and wrote no program. The same happened to its one-request attempts at medium and high effort (64,000 and 32,000 tokens, no program); at low effort it wrote one each time.
- **Haiku**, second run: wrote a 7 kB autopilot in one go and started it untested two minutes in. The program took no sample in two missions and was killed in the third like the two above; the session ended before a restart. Uninterrupted it scores 0.000 as well.
- **Haiku**, third run, the first on 0.1.2: wrote an 8.7 kB autopilot and started it through the launcher. The program drove for 261 seconds and sampled little; by the agent's own account its estimate of slip was wrong on sand. In mission 6 it died on a network error when Docker on the laptop stalled, so that mission's 0.00 is not a fair reading of the program.
- **Haiku**, fourth run, on 0.1.2 with nothing else running: started its autopilot untested, stopped and restarted it twice with changes, and ended its session 92 seconds into the campaign with 27 minutes left. Ending the session stopped the program, so missions 3 to 6 scored 0. Task 0.1.3 says in as many words that a program stops when the session ends.

What the reference does better, summed over the six missions:

| Run | Value sampled on time | Failed samples | Hazard stops | Missions ended away from base |
|---|---|---|---|---|
| Reference | 62% | 2 | 0 | 0 |
| Opus 5.5 · agent 2 | 60% | 6 | 0 | 0 |
| Sonnet 5.5 · agent 1 | 57% | 3 | 1 | 0 |
| Opus 5.5 · one shot | 57% | 10 | 0 | 0 |
| Sonnet 5.5 · one shot 2 | 43% | 12 | 2 | 0 |
| Haiku 5.5 · one shots | 30–52% | 7–24 | 0 | 3–4 each |

On these six missions the reference almost never spends a sample on a place that is not the target, it never drives into a hazard, and it spends what battery is left on late targets for a quarter of their value (another 21% of the value, against 0–6% for the three best Claude runs). Both agents estimated nearly as well as the reference and then left battery unused: Sonnet's kept a fixed 15-unit reserve, and Opus's ended its missions with 13 to 22 units.

A separate check, not part of the task: **playing turn by turn, Opus scored 0.650 on mission 2 against the reference's 0.750** ([run](lightlag-runs/turn-noise2-seed9007-opus-5-5/), $0.63). One mission says little either way.

## The fresh-data check: 200 new maps

Two choices on the way to this task favour the reference. The noise level was picked on 40 exploration maps because the reference did best against Claude there, and the six missions are picked by the reference's own score. To see what is left of its lead without either, the reference and every saved Claude-written program played 200 maps that none of this had touched: `rush_noisy`, seeds 30000–30199, the task's settings. No model was called.

**Every map.** The reference's mean is 0.518.

| Against | Its mean | Reference's lead, with 95% interval | Maps where the reference is higher / equal / lower | Six-map campaigns the reference wins | 24-map campaigns |
|---|---|---|---|---|---|
| Opus 5.5 · one shot | 0.515 | +0.002 (−0.029 to +0.034) | 93 / 18 / 89 | 50% | 52% |
| Opus 5.5 · agent 2's program | 0.480 | +0.038 (+0.011 to +0.066) | 111 / 10 / 79 | 68% | 84% |
| Opus 5.5 · agent 3's program | 0.459 | +0.058 (+0.027 to +0.090) | 103 / 22 / 75 | 73% | 91% |
| Sonnet 5.5 · one shot 2 | 0.416 | +0.102 (+0.073 to +0.131) | 128 / 11 / 61 | 89% | 100% |
| Sonnet 5.5 · one shot 1 | 0.265 | +0.253 (+0.221 to +0.284) | 167 / 6 / 27 | 100% | 100% |
| Haiku 5.5 · one shots, three programs | 0.207–0.305 | +0.212 to +0.311 | 167–194 higher of 200 | 100% | 100% |

**The 56 maps the mission rule would pick.** The reference's mean is 0.688.

| Against | Its mean | Reference's lead, with 95% interval | Higher / equal / lower | Six-map campaigns the reference wins | 24-map campaigns |
|---|---|---|---|---|---|
| Opus 5.5 · one shot | 0.603 | +0.086 (+0.028 to +0.143) | 37 / 2 / 17 | 84% | 99% |
| Opus 5.5 · agent 2's program | 0.621 | +0.068 (+0.017 to +0.119) | 34 / 4 / 18 | 81% | 99% |
| Opus 5.5 · agent 3's program | 0.543 | +0.146 (+0.084 to +0.207) | 36 / 8 / 12 | 95% | 100% |
| Sonnet 5.5 · one shot 2 | 0.543 | +0.145 (+0.088 to +0.202) | 39 / 6 / 11 | 97% | 100% |
| Sonnet 5.5 · one shot 1, Haiku 5.5 · one shots | 0.220–0.387 | +0.302 to +0.468 | 50–56 higher of 56 | 100% | 100% |

A campaign is that many maps drawn without replacement from the pool; the reference wins it when its mean score is higher.

What it says:

- **Against Opus's one-request program the reference has no lead on maps nobody chose.** The interval straddles zero and a campaign is a coin flip at any length. That program cost one request and $0.94.
- **Against the programs Opus's agents built, the lead is 0.04 to 0.06 a map.** It is real, since both intervals exclude zero, and too small for six missions: the reference would lose about three campaigns in ten.
- **The mission rule adds 0.03 to 0.09 to the lead over every Opus program.** It keeps the maps where the reference's own run went well. Some of that is the map being easy, which helps every controller; the rest is the noise having suited the reference's route, which says nothing about another controller's route on the same map. The reference repeats its score on a fixed map exactly, so the lead is reproducible on the task. It is not evidence that the reference drives better.
- **A longer rule-picked campaign would win nearly always:** 99% of 24-mission campaigns against all three Opus programs. It would be measuring the rule.
- **The 40 exploration maps flattered the reference.** There it led Opus's one-request program 0.52 to 0.43, higher on 25 maps of 40. The noise level was chosen on those maps because of that lead, so some of it was bound to be luck, and on fresh maps it is gone.
- **Against the smaller models' programs none of this matters.** The reference is 0.10 to 0.31 ahead a map and wins almost every campaign, rule or no rule.

```sh
python3 -m lightlag_live.fresh_maps table                 # both tables, from docs/lightlag-live-fresh-maps.json
python3 -m lightlag_live.fresh_maps play <new-folder>     # replay everything; needs Docker, about 7 minutes
```

## The same programs on the team's seed 501

Manh's [task-contract proposal](lightlag-task-contract-proposal.md) names `rush` seed 501 at the standard noise level: Opus, playing turn by turn through its own tool calls, scored a mean of 0.212 over six attempts and lost the rover in four of them, against the reference's 0.833. The saved Claude-written autopilots were replayed on that map and on the team's three other known seeds. No model was called.

| Program | `rush` 501 | `rush` 500 | `rush_noisy` 502 | `rush_noisy` 504 | Rovers lost |
|---|---|---|---|---|---|
| Reference (`kf_mpc`) | 0.83 | 1.00 | 0.77 | 0.70 | 0 |
| Opus, one request, written for the standard noise level | 0.83 | 1.00 | 0.62 | 0.70 | 0 |
| Opus, one request, written for noise level 2 | 0.83 | 0.57 | 0.54 | 0.70 | 0 |
| Opus agent 2's program | 0.83 | 0.71 | 0.77 | 0.60 | 0 |
| Opus agent 3's program | 0.75 | 1.00 | 0.54 | 0.60 | 0 |
| Sonnet, one request, written for noise level 2 | **0.92** | 1.00 | 0.54 | 0.70 | 0 |
| Sonnet, one request, written for the standard noise level | 0.75 | 0.46 | 0.54 | 0.40 | 0 |
| Haiku, one request, written for the standard noise level | 0.62 | 0.86 | 0.00 | 0.00 | 2 |
| *Opus turn by turn, six attempts (the team's runs)* | *0.00 0.00 0.83 0.00 0.00 0.44* | | | | *4 on 501* |

The reference reproduces its known score on all four, so the replay matches the team's episodes. One map each is not a comparison of controllers. What the 501 column does show:

- **No Claude-written autopilot lost the rover on seed 501,** and three of Opus's four programs tie the reference there.
- **So the failure on 501 is not a failure to understand the mission.** The same model, asked for a program, writes one that takes the discovery it can reach, leaves the one it cannot and drives home. Playing turn by turn it commits to a discovery it can no longer reach in time and runs the battery out.
- **The turn-based gap depends on the agent playing turn by turn.** In all six of the team's attempts on 501 it did: 6 or 7 `uplink` calls and 11 to 13 `advance` calls of its own, and no shell command that called the rover. Nothing in that task stops an agent from writing a control loop instead, and one that does would probably tie the reference.

Programs, request and scores: [`docs/lightlag-runs/explore-standard-noise/`](lightlag-runs/explore-standard-noise/README.md).

## What the task is

Six `rush_noisy` missions in a row, on a clock that runs in real time.

- **Each mission is unchanged.** It is a `DynamicEnvironment` episode with the team's physics, five tools and scoring. The campaign's reward is the mean of the six mission scores.
- **The clock is real.** One tick passes every second from the agent's first `uplink` or `advance`, whether or not it calls a tool, and each mission starts the moment the last one ends. Before the start, `rules`, `map` and `telemetry_log` are free, so the agent can prepare for as long as it likes.
- **The noise dial is at 2.** `noise_level` is the dial `lightlag_dynamic` already publishes "so difficulty can rise as controllers improve". At 2, a position fix is off by 0.6 m per axis against a 0.75 m sampling radius, and the heading bias starts anywhere within 10 degrees.
- **The agent has to build an autopilot.** A 50-tick mission is over in 50 seconds, so nobody can drive by calling tools by hand. The agent's container holds a small helper that gives a program the five tools as function calls, and a launcher that keeps the program running; the instruction describes both.

The reference is the team's frozen `kf_mpc`, started fresh for each mission.

## Why this design, and what was dropped on the way

Each step below was tested before the next was built. All of it used seeds 8000–8039, which are not the task's. The fresh-data check above came last and corrects step 2.

1. **Making the agent write an autopilot is not enough against Opus.** Asked once for a mission autopilot at the standard noise level, Opus 5.5 wrote 608 lines that scored 0.78 on `rush` and 0.65 on `rush_noisy` over 40 maps each; the reference scored 0.76 and 0.68. No rover was lost. Sonnet's scored 0.62 and 0.34 with 11 rovers lost. So the first hypothesis, "a real-time clock alone will beat Claude", was wrong for Opus and was dropped.
2. **State estimation under noise looked like the place where the reference pulls away.** With the dial at 2, on the same 40 maps:

   | Controller | Mean score | Maps where the reference scores higher |
   |---|---|---|
   | Reference (`kf_mpc`) | 0.52 | |
   | Opus autopilot, told the noise level | 0.43 | 25 of 40, 2 ties |
   | Opus autopilot, written for level 1 | 0.25 | 37 of 40, 2 ties |
   | Sonnet autopilot, told the noise level | 0.25 | 35 of 40, 2 ties |
   | Haiku autopilot, told the noise level | 0.25 | 38 of 40, 1 tie |
   | Plan that never reads telemetry | 0.29 | 36 of 40 |

   The second row did not hold: on 200 fresh maps that program is level with the reference. The rows for Sonnet and Haiku did hold.
3. **One mission is close to a coin flip; a campaign is as good as the lead behind it.** Averaging over six missions turns a real per-mission lead into a result that repeats. It cannot make a lead that is not there.
4. **The reference was left as it is.** A search over its ten decision thresholds at level 2 (200 settings, seeds 20000–20079, checked on 21000–21079) found nothing clearly better: 0.505 for the frozen values against 0.52–0.54 for the best eight. The team's other controllers also sit at 0.52–0.53.

## How the six missions were chosen

By one rule that looks only at the reference: **the first six seeds from 9001 upward on which `kf_mpc`, turn-based at noise level 2, ends at base with a score of at least 0.6.** That gives 9003, 9007, 9008, 9012, 9013 and 9020. The rule and the seeds were committed (`3ff2210`) before any model-written program touched these maps.

The rule is disclosed, model-blind and fixed in advance, and it favours the reference: over all forty candidates, 9001–9040, the reference averages 0.50, and on the six chosen missions 0.66. The fresh-data check puts a number on the favour: 0.03 to 0.09 of lead over each Opus program, which is most of the lead the task shows. With six unselected missions the reference would average about 0.52 and lose to Opus's one-request program as often as it won.

## Reward integrity

| Check | Result |
|---|---|
| Reference through Harbor on the real clock | **0.664352**: 0.688, 0.750, 0.646, 0.667, 0.625, 0.611. Identical to its turn-based scores, so it loses nothing to the clock |
| Do nothing (`-a nop`) | **0.000000** in 21 s: the collect hook lets all 300 ticks pass at once |
| Stop early (the reference cut off by Harbor after 90 s) | **0.222917**: 0.688, 0.650, then four zeros. Commands already queued still ran |
| A rejected first `uplink` | does not start the clock (tested) |
| Later missions' maps | not served before their mission starts (tested); no tool returns a seed or a score |
| Malformed or missing result | the verifier fails instead of writing a reward (tested) |

The simulator, seeds and token live in the sidecar container, as in `harbor/lightlag`; the agent's image holds only the client helper and a launcher (tested). Stopping early earns what was finished and nothing more, which is stricter than the single-mission task. The three Harbor checks above were run on task 0.1.0. On 0.1.3 the reference scored 0.664352 again and doing nothing 0.000000 ([rewards](lightlag-runs/live-checks-0.1.3/)); stopping early was not repeated. Versions 0.1.1 to 0.1.3 changed the instruction and added one file to the agent's image, and nothing in the simulator, the reference or the grader.

## The launch trap in 0.1.1, and its fix

In all three agent runs on task 0.1.1 the agent's program stopped exactly 120 seconds into the campaign. The task caused it.

The instruction suggested starting the program with `nohup python3 autopilot.py > autopilot.log 2>&1 &`. All three agents did, with `cd /app &&` in front and a `sleep` and a `cat` behind to see the first lines of the log. In that form the shell that waits for the program still holds the shell tool's output. OpenCode's tool therefore did not return after the `sleep`: it waited, reached its own limit of 120 seconds and stopped everything the command had started, the autopilot included. The campaign went on without it.

| Run | Rover without a program | As played | The same program, uninterrupted |
|---|---|---|---|
| Opus 5.5 · agent 2 | 9.7 s: the agent restarted it at once | 0.610 | 0.610, the same in every mission |
| Opus 5.5 · agent 3 | 125 s: missions 4 and 5 scored 0 | 0.320 | 0.509 |
| Haiku 5.5 · agent 2 | to the end: its session ended before a restart | 0.000 | 0.000 |

The right-hand column is each agent's own `autopilot.py`, copied out of its container during the campaign and replayed on the same six missions (`python3 -m lightlag_live.sandbox --program <run>/program <new folder>`, results in each run's `uninterrupted/`). The missions that were not interrupted come out identical to the Harbor run, which is why the replay can be trusted for the others.

So the trap did not make the reference's lead: it changed nothing for the best Claude run. It did turn a middling Opus run into a poor one for a reason that has nothing to do with driving a rover, and a judge reading that trajectory would be right to hold it against the task.

Task 0.1.2 removes it:

- **A launcher in the agent's container.** `python3 /app/detach.py python3 autopilot.py` starts the program in its own session with its output in a log file, and returns at once. The instruction tells the agent to use it and why.
- **A test that reproduces the failure.** [`tests/lightlag_live/test_detach.py`](../tests/lightlag_live/test_detach.py) runs commands through a small model of the shell tool: own process group, returns when the command's output is closed, kills the group at the limit. The old form hangs until the limit and loses the program; a program started through the launcher keeps running, also when a later command is killed at its limit.
- **A check in the real harness.** Haiku 5.5 played 0.1.2 twice. Both times it started its program through the launcher and the call returned at once: 0.4 seconds, and 5.2 seconds with a five-second sleep of its own. No command was cut off by the shell tool, and in the first run the program was still calling the simulator every tick 261 seconds in, well past the mark where the three programs on 0.1.1 died. Neither run is a clean campaign, for other reasons: the first lost its last mission to a stall of this laptop, and in the second the agent ended its session in mission 2.

Sonnet's run was on 0.1.0 and was not affected: it had run into the same limit earlier, on its own parameter sweep, and started its autopilot in a form the tool does not wait for.

## Run it

```sh
harbor run -p harbor/lightlag-live -a oracle                                   # reference, about 5.5 minutes
harbor run -p harbor/lightlag-live -a nop                                      # do nothing
harbor run -p harbor/lightlag-live -a oracle --agent-timeout-multiplier 0.05   # stop early
harbor run -p harbor/lightlag-live -a opencode -m anthropic/claude-opus-5-5 --ak version=1.19.5 --env-file .env
python3 -m unittest discover -s tests/lightlag_live -v
```

Harbor 0.25.0, local Docker. The task needs a backend that supports Docker Compose sidecars, like `harbor/lightlag`. Run nothing else that is heavy on Docker beside an agent run: the clock is real, and a stall of the machine is a stall of the agent's program.

## The demo

[`viewer/ghosts-demo.html`](../viewer/ghosts-demo.html), one file, double-click. It replays the six missions with every saved run on the same ground: the reference in gold, the Claude run you follow in blue, every other Claude run as a dark shadow, and live standings on the right. [Controls and limits](../viewer/ghosts/README.md).

The same page also plays the team's own saved runs: [`viewer/ghosts-rush-501.html`](../viewer/ghosts-rush-501.html) shows the six turn-based attempts by Opus on `rush` seed 501 as shadows beside the reference. Four of them are ahead of the reference at tick 24; three of those run out of battery in the last two ticks, two of them at base itself, and the fourth ends away from base. A fifth loses its rover at tick 29. That is the wider gap of the two, on one map chosen because the model failed there. [`viewer/ghosts-rush-501-control.html`](../viewer/ghosts-rush-501-control.html) adds one more rover to the same map: the autopilot Opus wrote in one reply, which ties the reference at 0.83.

## Spend

Reported usage on Kristján's key, not a checked balance. About $9.15 in all, against the $10 this chat said it would stay under.

| What | Count | Reported cost |
|---|---|---|
| One-request autopilots that are runs on the task: Opus 1, Sonnet 2, Haiku 3 | 6 requests | $1.27 |
| One-request autopilots at the standard noise level, for exploration: Opus 1, Sonnet 1, Haiku 3 | 5 requests | $1.18 |
| One Haiku reply lost to a script error before its usage was saved | 1 request | not recorded; at most about $0.02 |
| Agent runs through Harbor: Opus 3, Sonnet 1, Haiku 4 | 8 runs | $6.05 |
| Turn-based check, Opus on one mission | 1 run | $0.63 |

The first Opus agent run alone was $3.13: it prepared for 28 minutes and was then cut off. The replays, the 200 fresh maps, the seed-501 check and the reference runs called no model.

## What this does not show

- **It is a small sample of agents.** One campaign per run, and one to four runs per model and method. "Every run so far" is not a measured win rate.
- **The lead over Opus on the task is narrow and mostly chosen.** The reference leads the three best Claude runs by 0.05 to 0.08 on the task and loses single missions to all three. On fresh maps it has no lead over Opus's one-request program.
- **The fresh maps hold programs fixed.** Each saved program is one draw of what a model writes. A new agent run writes a new program, better or worse than these.
- **The noise level was chosen where the reference looked best.** At level 1 Opus's one-request autopilot matched the reference, and at 2.5 it matched it again (0.40 against 0.39 on the 40 exploration maps). On fresh maps it matches it at level 2 as well.
- **The reference is not an optimum.** It samples about a third of the value late and reaches about a quarter of the value in discoveries. A better controller is possible; nothing here found one.
- **One-request programs ran on a simulated clock**, restarted fresh for every mission. Both choices favour the program. Agent runs through Harbor ran on the real clock with no such help.
- **Only Claude models were run.** No other provider's model has played this task.
- **Agent runs depend on wall time and on the machine.** An agent that prepares for too long is cut off by the session limit, which the task states since 0.1.1. A stalled machine stalls the agent's program: one run here lost its last mission that way.
- **No strong model has played 0.1.2 or 0.1.3.** The two agent runs on 0.1.2 are Haiku's, and no agent has played 0.1.3, which adds one sentence to it. The Opus and Sonnet agent runs were on 0.1.0 and 0.1.1.

## Decisions for the team

1. **Which task is judged.** This research says the turn-based task: its gap against Opus is several times wider than anything here. Lightlag Live could be judged only as a task whose lead over Opus is 0.05 and comes from its mission rule, and that is a weak claim to defend.
2. **Whether to tell the 501 story with its control.** "Playing turn by turn, the model lost the rover in four of six attempts; asked for a program, the same model wrote one that ties the reference on the same map." That is a stronger account of what the task measures than the failures alone, and it is the first thing a judge who scripts the task will find out.
3. **Whether the turn-based task should say anything about scripting.** It is silent now. Leaving it silent is fair. The team should decide knowing that an agent which writes a control loop will probably tie the reference on 501.
4. **Whether to buy one Opus agent run on 0.1.3,** about $1. It would show the strongest model on the corrected task, and it is the only paid run this page would still ask for.
5. **Who else should play it.** One other frontier model through the same command would show whether any of this is about Claude or about the task.
