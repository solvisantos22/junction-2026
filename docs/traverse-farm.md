# Traverse rollout farm

Saturday 14 November 2026. Owner: Kristján / Claude Code. Code: [`tools/traverse_farm/`](../tools/traverse_farm/), tests: [`tests/traverse_farm/`](../tests/traverse_farm/). **A tool for the Traverse owner, not a rules decision.** It reads `lightlag_traverse` and never edits it.

## What it is for

Lightlag Traverse ([README](../lightlag_traverse/README.md)) is a 420-tick mission on a 600 m by 400 m Mars-like map. A reference pilot mission takes about 25 CPU-seconds, so comparing controllers on hundreds of worlds is slow on one laptop. The farm plays many missions at once, on Modal or on a local process pool, for two jobs:

1. **Pilot against Claude's programs on fresh worlds, paired.** The pilot and each saved Claude-written Traverse program play the same unseen worlds; the farm reports means, rovers lost or stranded, and how often each is higher. This is what the Traverse owner asked for first.
2. **Searching the pilot's options.** A cross-entropy search over the pilot's numeric options (search budgets, beam widths, margins, the battery floor, slacks, energy weight, slip prior), each candidate compared paired with the published defaults on the same worlds, then selection on a fresh block and confirmation on worlds nobody searched. A gain is claimed only if its 95% paired bootstrap interval excludes zero. The Traverse owner reports that no single option moved the mean by more than about 0.01 on 32 worlds, so expect little here.

## Seeds

Agreed with the Traverse owner: search 100–399, selection 400–499, confirmation and program comparison 600–799 (and up to 899 for program comparison). Untouched: 1–99 (the owner's development), 2026 (the task's world), 99991 (the example in the one-request text), 1000–1199 (the owner's own fresh check).

## Run it

Locally, standard library only:

```sh
python3 -m unittest discover -s tests/traverse_farm -v
python3 tools/traverse_farm/local.py evaluate --policies pilot,greedy,straight,nothing --seeds 600-601 --workers 8
```

On Modal (needs the `modal` package and a login, `modal setup`, done by the account owner):

```sh
modal run tools/traverse_farm/modal_app.py::smoke         # 8 worlds here and on Modal: same scores expected
modal run tools/traverse_farm/modal_app.py::evaluate \
    --policies "pilot,program:docs/lightlag-runs/traverse-oneshot-opus-1/policy.py,agent:docs/lightlag-runs/traverse-agent-opus-1/program/auto.py" \
    --seeds 600-899 --out docs/traverse-farm/programs-1
modal run tools/traverse_farm/modal_app.py::search --out docs/traverse-farm/search-1
```

`TRAVERSE_SOURCE=<folder>` plays another version of `lightlag_traverse` (for example a commit extracted with `git archive`). Every result row records a hash of the code that played and the machine it ran on.

**Model-written programs run only on Modal**, inside its isolated containers; the local command refuses them. Each program gets the published ground model as `lightlag_surface.py`, JSON copies of every reply (as over MCP), a stand-in `lightlag_client` for agent scripts, and a time limit.

## Checked so far

- 23 tests pass (1 skipped without the `modal` package; it passes with it).
- Local run of the pilot at commit `f90cb6b` on fresh worlds 600–601: pilot 0.523, greedy 0.296, straight 0.213, nothing 0.000; about 35 s per pilot mission with eight in parallel on this laptop.
- Not yet run on Modal: it needs the account owner's login.
