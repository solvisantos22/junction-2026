# One-request autopilots at the standard noise level

Exploration for [Lightlag Live](../../lightlag-live.md), 14 November 2026, Kristján / Claude Code. Each model was sent [`request.md`](request.md) once (5,634 input tokens) and asked for one Python module that plays a whole mission. Nothing was retried or repaired. These are not runs of a Harbor task.

| Folder | Model, effort | Reply | Reported cost |
|---|---|---|---|
| `opus-a/` | Claude Opus 5.5, medium | 608 lines, complete | $0.97 |
| `sonnet-a/` | Claude Sonnet 5.5, medium | 249 lines, complete | $0.15 |
| `haiku-d/` | Claude Haiku 5.5, low | 242 lines, complete | $0.02 |
| `haiku-b/` | Claude Haiku 5.5, high | none: all 32,000 output tokens went to reasoning | $0.02 |
| `haiku-c/` | Claude Haiku 5.5, medium | none: all 64,000 output tokens went to reasoning | $0.03 |

`policy.py` is the module cut out of `response.md`; `meta.json` holds the request id, token counts and cost. One more Haiku request was sent before these and its reply was lost to a script error before anything was saved.

## On the team's four known seeds

`team-seeds/` holds one `sandbox.json` per program: the scores on `rush` 501 and 500 and `rush_noisy` 502 and 504 at delay 3 and noise level 1, the settings of the team's fixed-seed runs. The reference reproduces its known scores there.

| Program | `rush` 501 | `rush` 500 | `rush_noisy` 502 | `rush_noisy` 504 | Rovers lost |
|---|---|---|---|---|---|
| Reference (`kf_mpc`) | 0.83 | 1.00 | 0.77 | 0.70 | 0 |
| Opus, this folder | 0.83 | 1.00 | 0.62 | 0.70 | 0 |
| Opus, written for noise level 2 ([run](../live-oneshot-opus-1/)) | 0.83 | 0.57 | 0.54 | 0.70 | 0 |
| Opus agent 2's program ([run](../live-agent-opus-2/)) | 0.83 | 0.71 | 0.77 | 0.60 | 0 |
| Opus agent 3's program ([run](../live-agent-opus-3/)) | 0.75 | 1.00 | 0.54 | 0.60 | 0 |
| Sonnet, written for noise level 2 ([run](../live-oneshot-sonnet-2/)) | 0.92 | 1.00 | 0.54 | 0.70 | 0 |
| Sonnet, this folder | 0.75 | 0.46 | 0.54 | 0.40 | 0 |
| Haiku, this folder | 0.62 | 0.86 | 0.00 | 0.00 | 2 |

```sh
python3 -m lightlag_live.sandbox docs/lightlag-runs/explore-standard-noise/opus-a/policy.py <new-folder> \
    --missions 501:rush,500:rush,502:rush_noisy,504:rush_noisy --noise-level 1
```

The programs ran in a locked-down container on a simulated clock, started fresh for each mission; the two agent programs ran whole, as in their task. One map each is not a comparison of controllers. What it does show: no Claude-written autopilot lost the rover on `rush` 501, where Claude Opus 5.5 driving by hand lost it in four of six attempts ([task-contract proposal](../../lightlag-task-contract-proposal.md)).
