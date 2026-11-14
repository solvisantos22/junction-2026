# Claude on the MAX map: one-request programs against `manh_max`

Saturday 14 November, about 22:50 Helsinki. The farm session (Claude Code), played on Modal with the Traverse farm's `--map max`. The request and the replies are the frozen MAX baseline's ([`lightlag-runs/max-baseline/`](lightlag-runs/max-baseline/README.md)), unchanged.

## What ran

- **The programs.** Each model writes one program from one request: the baseline's frozen request (`request.md`), with the MAX map's public rules and its example world 99991. Opus 5.5, Sonnet 5.5 and Haiku 5.5, three replies each, effort medium, adaptive thinking, no retries. **7 of 9 replies are in and played**; Opus 2 and 3 and Haiku 3 are still being written. API cost so far $2.82, measured from the usage each reply reports (`asks.jsonl`).
- **The worlds.** The baseline's seven: superhard 505, 509, 515; fair 500, 510, 520; and 2026. Also **100 fresh MAX worlds, 600–699**, outside the held-out pool 500–523.
- **The playing.** On Modal with the farm (`tools/traverse_farm`, `--map max`): every mission is `lightlag_traverse_max.environment.make_env(seed, "max")`, and model-written programs run only in Modal's containers. bubblewrap isn't available on the machine that played them, so the farm stood in for `lightlag_traverse_max.sandbox`. **Check:** the farm's `manh_max` repeats the baseline's table exactly on all seven worlds, including the two that end away from the lander.

## Results

| Player | 7 baseline worlds | 100 fresh MAX worlds | Lost | Away | Minus `manh_max`, fresh [95% paired] | `manh_max` higher, fresh |
|---|---:|---:|---:|---:|---|---|
| `manh_max` | 0.338 | 0.317 | 0 | 17 | | |
| **Opus 5.5, reply 1** | **0.313** | **0.289** | 2 | 20 | **−0.028 [−0.057, +0.000]** | **53 / 100** |
| Sonnet 5.5, reply 3 | 0.068 | 0.081 | 28 | 31 | −0.236 [−0.266, −0.206] | 95 / 100 |
| Sonnet 5.5, reply 2 | 0.069 | 0.075 | 0 | 78 | −0.243 [−0.265, −0.220] | 97 / 100 |
| The normal-map reference pilot | 0.059 | 0.068 | 12 | 51 | −0.249 [−0.273, −0.225] | 98 / 100 |
| Haiku 5.5, reply 1 | 0.066 | 0.064 | 1 | 40 | −0.253 [−0.278, −0.228] | 96 / 100 |
| Sonnet 5.5, reply 1 | 0.059 | 0.049 | 0 | 19 | −0.268 [−0.290, −0.246] | 99 / 100 |
| Haiku 5.5, reply 2 | 0.032 | 0.031 | 2 | 68 | −0.287 [−0.310, −0.263] | 99 / 100 |

Rows: `docs/traverse-farm/max-baseline-check/` and `docs/traverse-farm/max-fresh/` (Modal apps `ap-x2LyP43X8ItN9HLYYsy4ph` and `ap-PMWenOkDKWYKVpDfzI5Maz` for the last additions). Sonnet's third program stops with an error in every mission and is scored where it stopped.

On the seven baseline worlds, Opus's program scores 0.357 on superhard 505 (`manh_max` 0.199), 0.074 on 509 (0.180), 0.112 away on 515 (0.094 away), 0.504 on 500 (0.455), 0.414 on 510 (0.481), 0.520 on 520 (0.529) and 0.207 on 2026 (0.431). It beats `manh_max` on 3 of the 7.

## What it says

- **The MAX map separates the weaker models sharply.** Sonnet's and Haiku's five programs, written with the MAX rules in hand, score 0.031–0.081: no better than the normal-map pilot, which knows nothing of those rules.
- **The strongest model comes within 0.03 of `manh_max` in a single answer.** On 100 fresh MAX worlds Opus's first program is 0.028 behind, the interval touching zero, and it is the higher of the two on 47 worlds. Against Opus, the MAX map needs a stronger reference than `manh_max` before it is a gap environment. `manh_max` also ends away from the lander on 17 of 100 fresh worlds.
- **Agents may do better still.** In the MAX Harbor tasks (`harbor/lightlag-traverse-max-fair`, `-superhard`), an agent can test and fix its code during the session; one-request programs can't. On the normal map that didn't always help: the one-request Opus program scored 0.362 on the campaign's worlds, above every agent run there (best 0.293).
- **One reply so far for Opus.** If its other two replies score well below this one, the first was a lucky draw. They will be added here.

## Next

- **Opus 2–3 and Haiku 3:** play them into the same folders as they arrive; only their new missions play. The command, with the program list grown:

  ```sh
  modal run tools/traverse_farm/modal_app.py::evaluate --map max --baseline manh_max \
      --policies "manh_max,pilot,program:docs/lightlag-runs/max-baseline/replies/opus-2/policy.py,..." \
      --seeds 600-699 --out docs/traverse-farm/max-fresh
  ```

- **Agent runs on the MAX Harbor tasks:** on Modal with `--env modal -n 6` after one oracle check, since our tasks run the simulator in a second container ([`modal-playbook.md`](modal-playbook.md)).
- **The baseline's own report:** the replies are committed, so `python3 -m lightlag_traverse_max.oneshot play` and `report` can rebuild the baseline's README with its sandbox where bubblewrap is available.
