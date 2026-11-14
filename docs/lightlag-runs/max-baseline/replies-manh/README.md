# A second set of replies to the frozen MAX request (Manh's key)

Six replies to the baseline's frozen request ([`../request.md`](../request.md)), sent with Manh's API key on Saturday 14 November at 22:11 to 22:20 Helsinki: Opus 5.5 reply 1, Sonnet 5.5 replies 1 to 3 and Haiku 5.5 replies 1 and 2. The protocol is the baseline's ([`../freeze.json`](../freeze.json)): effort medium, adaptive thinking, up to 128,000 output tokens, no retries, no fallback model.

Kristján's farm session sent the same request with his key a few minutes later and committed its nine replies as the baseline's own [`../replies/`](../replies/). These are kept beside them, unchanged, as independent samples. Nothing here is read by `oneshot play` or `oneshot report`.

- Each folder: `request.md` (the frozen request, as sent), `response.md` (the reply as it came), `policy.py` (the program in it) and `meta.json` (model, tokens, cost).
- [`../asks-manh.jsonl`](../asks-manh.jsonl): one line per reply, with its cost. **$2.80 in all.**
- [`../plays-manh.json`](../plays-manh.json): every program on the baseline's seven worlds, MAX map, played in the bubblewrap sandbox (`lightlag_traverse_max/sandbox.py`). The `normal-*` rows in that file are Kristján's three saved normal-map programs.
- **Not recorded:** four further calls (Opus 2 and Haiku 3, twice each) were cut off when the run was stopped and left no reply. Their cost is unknown: at most about $5.35 if billed in full.

Scores and what they say: [`docs/second-machine-check.md`](../../../second-machine-check.md#two-sets-of-replies-for-the-frozen-max-baseline).
