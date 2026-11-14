# Lightlag Decision Demo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Produce an offline page explaining three verified decisions without overstating the evidence.

**Architecture:** A standard-library Python builder loads existing saved runs and
reconstructs two explicitly labelled continuations. A separate template embeds
that data and renders synchronized SVG maps, battery curves and decision notes.
Existing simulator, audit and viewer files are preserved.

**Tech Stack:** Python 3.9+, unittest, HTML/CSS and vanilla JavaScript/SVG.

## Task 1: Payload and counterfactual correctness

Files: new `viewer/decision_build.py`, `tests/viewer/test_decision_build.py`.

- [ ] Write failing tests for `build_payload(repo)` and `make_branch(replay,
  transcript, cutoff)`. Tests load actual saved artifacts, not mocked outcomes.
  Required assertions include:

```python
payload = decision_build.build_payload(REPO)
assert len(payload["cases"]) == 3
assert [c["actual"]["replay"]["result"]["raw_score"] for c in payload["cases"]] == [0, 8.25, 0]
assert [c["alternative"]["replay"]["result"]["raw_score"] for c in payload["cases"]] == [5.25, 10, 6]
assert [c["alternative"]["kind"] for c in payload["cases"]] == ["post_hoc", "reference", "post_hoc"]
```

- [ ] Observe the missing-feature failure, then implement those functions using
  `lightlag_audit.counterfactual.make_environment` and the transcript's public
  calls through cutoffs 12 and 20. Finish the horizon with no additional commands.
- [ ] Assert branch results against `salvage-check.json` and `stop-check.json`;
  preserve full original replays and keep references separate from branches.
- [ ] Test that the visible-packet helper never returns a packet before its
  `received_tick`, and uses observation positions when sensing noise is enabled.
- [ ] Run `python3 -m unittest discover -s tests/viewer -p 'test_decision_*.py' -v`.

## Task 2: Standalone page and safe build

Files: new `viewer/decision_template.html`, `viewer/decisions.html`; extend new tests.

- [ ] Add an embedding test that round-trips the JSON and neutralizes literal
  `</script>` in text. The page must have no external scripts/assets.
- [ ] Implement the builder CLI:

```sh
python3 viewer/decision_build.py --out viewer/decisions.html
```

- [ ] Implement the three case tabs, synchronized maps/tick controls, true versus
  observed positions, queue details, battery curves, final score cards, decision
  notes and evidence links described in the design. No invented beliefs.
- [ ] Keep labels plain: actual run, post-hoc continuation, or independent
  reference. Explain the common 25-energy idle bill and selected-case limitation.
- [ ] Generate the page and run all viewer tests:

```sh
python3 -m unittest discover -s tests/viewer -v
```

## Task 3: Review and handoff

File: new `docs/lightlag-decision-demo.md`.

- [ ] Document open/build commands, exact evidence inputs, the three decision
  walkthroughs, what the counterfactual can/cannot establish, and privacy limits.
- [ ] Obtain independent spec review, then implementation-quality review; address
  material findings. Parent handles repository integration and prize evidence.
- [ ] Parent opens the page in a browser, checks all three cases, playback,
  decision/end jumps, narrow viewport and console/runtime state; fixes problems.
- [ ] Confirm generated scores match authoritative files, source links resolve,
  no credentials/personal paths or new simulator changes appear, and the original
  viewer files match their pre-task bytes. Push the verified increment.

Plan self-review: all required data and UI behaviors map to tasks; the new code
is isolated, the experimental rules stay fixed, and verification covers real
counterfactual behavior instead of duplicating implementation logic.
