# Claude on the MAX map: one-request programs against `manh_max`

Saturday 14 November, about 23:05 Helsinki. The farm session (Claude Code), played on Modal with the Traverse farm's `--map max`. The request and the replies are the frozen MAX baseline's ([`lightlag-runs/max-baseline/`](lightlag-runs/max-baseline/README.md)), unchanged.

## What ran

- **The programs.** Each model writes one program from one request: the baseline's frozen request (`request.md`), with the MAX map's public rules and its example world 99991. Opus 5.5, Sonnet 5.5 and Haiku 5.5, three replies each, effort medium, adaptive thinking, no retries. **All 9 replies came back with a program** (every reply stopped normally). API cost **$6.19**, measured from the usage each reply reports (`asks.jsonl`); Opus's three cost $1.50–1.81 each.
- **The worlds.** The baseline's seven: superhard 505, 509, 515; fair 500, 510, 520; and 2026. Also **100 fresh MAX worlds, 600–699**, outside the held-out pool 500–523.
- **The playing.** On Modal with the farm (`tools/traverse_farm`, `--map max`): every mission is `lightlag_traverse_max.environment.make_env(seed, "max")`, and model-written programs run only in Modal's containers. bubblewrap isn't available on the machine that played them, so the farm stood in for `lightlag_traverse_max.sandbox`. **Check:** the farm's `manh_max` repeats the baseline's table exactly on all seven worlds, including the two that end away from the lander.

## Results

| Player | 7 baseline worlds | 100 fresh MAX worlds | Lost | Away | Minus `manh_max`, fresh [95% paired] | `manh_max` higher, fresh |
|---|---:|---:|---:|---:|---|---|
| `manh_max` | 0.338 | 0.317 | 0 | 17 | | |
| **Opus 5.5, reply 3** | **0.346** | **0.293** | 0 | 8 | **−0.025 [−0.050, +0.001]** | **54 / 100** |
| **Opus 5.5, reply 1** | **0.313** | **0.289** | 2 | 20 | **−0.028 [−0.057, +0.000]** | **53 / 100** |
| Opus 5.5, reply 2 | 0.192 | 0.207 | 0 | 30 | −0.110 [−0.139, −0.081] | 77 / 100 |
| Sonnet 5.5, reply 3 | 0.068 | 0.081 | 28 | 31 | −0.236 [−0.266, −0.206] | 95 / 100 |
| Sonnet 5.5, reply 2 | 0.069 | 0.075 | 0 | 78 | −0.243 [−0.265, −0.220] | 97 / 100 |
| The normal-map reference pilot | 0.059 | 0.068 | 12 | 51 | −0.249 [−0.273, −0.225] | 98 / 100 |
| Haiku 5.5, reply 1 | 0.066 | 0.064 | 1 | 40 | −0.253 [−0.278, −0.228] | 96 / 100 |
| Sonnet 5.5, reply 1 | 0.059 | 0.049 | 0 | 19 | −0.268 [−0.290, −0.246] | 99 / 100 |
| Haiku 5.5, reply 3 | 0.028 | 0.042 | 0 | 57 | −0.275 [−0.299, −0.250] | 97 / 100 |
| Haiku 5.5, reply 2 | 0.032 | 0.031 | 2 | 68 | −0.287 [−0.310, −0.263] | 99 / 100 |

Rows: `docs/traverse-farm/max-baseline-check/` and `docs/traverse-farm/max-fresh/` (Modal apps `ap-1AYfkACqiAQZAK52k9KvnC` and the one after it for the last additions). Sonnet's third program stops with an error in every mission and is scored where it stopped.

On the seven baseline worlds Opus's third program beats `manh_max` on 4 of 7 and its first on 3 of 7; on superhard 505 the first scores 0.357 against `manh_max`'s 0.199.

## What it says

- **The MAX map separates the weaker models sharply.** Sonnet's and Haiku's six programs, written with the MAX rules in hand, score 0.031–0.081: no better than the normal-map pilot, which knows nothing of those rules.
- **Opus, in a single answer, nearly ties `manh_max`.** Two of its three programs are within 0.03 of it on 100 fresh MAX worlds, with intervals touching zero, and each is the higher of the two on 45–47 worlds; one strands fewer rovers (8 against 17). The third is 0.110 behind. Over the three, Opus averages 0.263 against 0.317.
- **So, against Opus, the MAX map with `manh_max` as its reference is not a gap environment.** It would need a clearly stronger reference first. For comparison, on the normal map the reference beats the one-request Opus program by 0.180 on 300 fresh worlds (higher on 298), and every Claude agent run on the judged campaign by at least 0.18.
- **Agents may do better still.** In the MAX Harbor tasks (`harbor/lightlag-traverse-max-fair`, `-superhard`), an agent can test and fix its code during the session; one-request programs can't.
- **Where the MAX map does help:** as the "harder variant" story. Realistic hardware faults (radio blackouts, slip-check stops, a hidden wheel-size error) wreck controllers that don't model them, the weaker models among them, and the reference needs MAX-aware layers to cope.

## Next

- **Reproduce or extend:** a rerun into the same folders plays only missions it has not seen:

  ```sh
  modal run tools/traverse_farm/modal_app.py::evaluate --map max --baseline manh_max \
      --policies "manh_max,pilot,program:docs/lightlag-runs/max-baseline/replies/opus-1/policy.py,..." \
      --seeds 600-699 --out docs/traverse-farm/max-fresh
  ```

- **Agent runs on the MAX Harbor tasks:** on Modal with `--env modal -n 6` after one oracle check, since our tasks run the simulator in a second container ([`modal-playbook.md`](modal-playbook.md)).
- **The baseline's own report:** the replies are committed, so `python3 -m lightlag_traverse_max.oneshot play` and `report` can rebuild the baseline's README with its sandbox where bubblewrap is available.
