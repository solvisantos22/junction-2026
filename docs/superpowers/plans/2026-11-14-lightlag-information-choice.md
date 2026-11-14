# Selective information prototype implementation plan

> **For agentic workers:** Use subagent-driven-development for isolated tasks, with independent spec and quality review before integration.

**Goal:** Establish that choosing whether to obtain delayed evidence has measurable value in a small declared route-choice environment.

**Architecture:** Add an independent package; root owns coordination/docs, one implementer owns environment/tests, another owns public-only policies/study/tests. Existing simulator and active teammate scopes are read-only.

**Tech Stack:** Python standard library, unittest, JSON artifact files, Git.

## Task 1: deterministic environment

Files: `lightlag_information/__init__.py`, `model.py`, `environment.py`; `tests/lightlag_information/test_environment.py`.

- [ ] Write failing tests for signal unavailable at tick 2 / available at 3, immutable accepted commitment, atomic invalid batches, one inspection, copy safety and seed-independent initial public surfaces.
- [ ] Implement frozen context dataclass/constants and `Environment(seed=0, context="uncertain", *, terrain=None, signal=None)`; overrides are evaluator fixtures only. Constructor context accepts a context id or Context. Follow exact design timing and reward.
- [ ] Check realized firm direct reward: execute at 2, finish at 4, `(10 - .25*4)/10 == .9`; soft direct is zero; direct detour finishes at 8 and scores `.4`.
- [ ] Test delayed probe plus route, energy exhaustion and horizon completion; replay includes public transcript and evaluator-only state/signal.
- [ ] Run `python3 -m unittest discover -s tests/lightlag_information -p 'test_environment.py' -v`; independent review; root commits/pushes environment increment.

## Task 2: public-only policies and study

Files: `lightlag_information/policies.py`, `study.py`; `tests/lightlag_information/test_policies.py`.

- [ ] Write analytical tests before policy code; derive posterior with `p*a/(p*a+(1-p)*(1-a))` for a firm signal and corresponding complement likelihood for soft.
- [ ] Define `expected_values(rules)` and `run_policy(tools, name)`, names `never_probe`, `always_probe`, `selective`, `blind_probe`. Tools expose only the five methods. Use earliest legal execution/delivery timing, exact remaining resources and public distributions.
- [ ] Independently run all 4 state/signal branches per context/policy and compare weighted realized means with analytical expected values. Check ignored evidence removes the adaptation benefit, and repeated log reads cannot change posterior.
- [ ] Add reproducible study CLI: `python3 -m lightlag_information.study --output PATH`; refuse existing output; publish protocol/context values, exact rows with weights, separate seeded rows (0–39), aggregate gates, source hashes and replay evidence. No hidden state passed to policies.
- [ ] Run `python3 -m unittest discover -s tests/lightlag_information -v`; inspect aggregate gate and all negative/context-specific findings; independent review before push.

## Task 3: result and handoff

Files: `docs/lightlag-information-choice.md`, `docs/lightlag-runs/information-choice-v1/`, exact claim row in `TEAM_STATUS.md`, one `docs/prize-evidence.md` entry.

- [ ] Record commands, exact expected and seeded results separately, abstraction limits and whether gate passed. No fabricated model run.
- [ ] Check all artifact hashes, local Markdown links, source-diff scope and package tests; preserve teammate rows byte-for-byte.
- [ ] Publish remaining verified increment to main, confirm remote SHA, release completed scope with next model-pilot gate explicit.
