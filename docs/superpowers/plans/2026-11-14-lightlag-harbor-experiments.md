# Dynamic Harbor experiment implementation plan

> For agentic workers: execute the existing design task by task with verified
> increments and the repository's junction-team-workflow. This worktree is already
> isolated. The user's standing instruction authorizes integration to main.

**Goal:** Reproducibly test the delivered dynamic profiles through Harbor without
changing teammates' simulator, controller, service or canonical task files.

**Architecture:** A small task generator copies the known Harbor packaging into
a fresh external directory, adds the existing dynamic service and a controller
entry point, and records provenance. Harbor performs the same protected grading
sequence as the original task.

**Tech stack:** Python standard library for preparation/tests; Harbor 0.25.0,
Docker and MCP 2.3.0 for execution. Model authentication is local `.env` only.

## 1. Prepare the experiment package

- [x] Add `tests/lightlag_experiments/test_prepare.py`: generate a task in a
  `TemporaryDirectory`, import its isolated reference package, instantiate its
  simulator-side service and assert profile/horizon/delay, verify every manifest
  hash, and prove a second invocation preserves an existing directory.
- [x] Run `python3 -m unittest discover -s tests/lightlag_experiments -v` before
  implementation and confirm it fails because preparation is missing.
- [x] Implement `tools/lightlag_experiments/prepare.py` and a small
  `play_policy.py` entry point. Reuse existing public-tool controllers and MCP
  client. Fail on unexpected template structure instead of silently producing a
  partially changed task.
- [x] Run the new tests, `python3 harbor/sync_task.py --check`, and the existing
  Harbor tests. Review the staged diff, commit and push the verified generator.

The intended command is:

```sh
python3 tools/lightlag_experiments/prepare.py /tmp/lightlag-rush-500-kf \
  --profile rush --seed 500 --delay 3 --policy kf_mpc
```

## 2. Verify the actual lifecycle

- [x] Install the pinned Harbor toolchain outside the repo and record its version.
- [x] Lint the generated task and run its oracle and no-op. Save jobs outside Git.
- [x] Generate identical-settings tasks for `open_loop` and `leg_and_wait`; run
  their oracle solutions and compare with direct simulator results. Treat
  infrastructure errors separately from scores.
- [ ] Once `.env` contains a key, run one model against the reference task. Keep
  the original model result untouched. Do not publish raw credentials or private
  runtime state. Record the model/version/settings and any runtime limitation.

Commands, after installing Harbor, use explicit task and external job paths:

```sh
harbor lint /tmp/lightlag-rush-500-kf
harbor run -p /tmp/lightlag-rush-500-kf -a oracle
harbor run -p /tmp/lightlag-rush-500-kf -a nop
harbor run -p /tmp/lightlag-rush-500-kf -a opencode \
  -m anthropic/claude-opus-5-5 --env-file .env
```

Check the installed CLI before executing; use its supported job-directory flags
to keep raw results outside the checkout.

## 3. Publish evidence and handoff

- [x] Add `docs/lightlag-experiments.md` with exact preparation/run commands,
  measured results, limits and next step. Link sanitized artifacts and manifest.
- [x] Refresh `docs/afterquery-readiness.md` for the already delivered base model
  run and current credit information. Attribute Kristján's and Manh's work.
- [x] Add one real contribution entry to `docs/prize-evidence.md`; update and
  release this task's claim with completed work and any unresolved API access.
- [x] Verify links, artifacts, clean diff and affected tests; fetch, integrate,
  push and confirm the final commit is on `origin/main`.

Execution note: the generator is on main at `0bc0d43`; all four scripted Harbor runs are saved and match the direct runner. The real model step is pending the user filling the Git-ignored `.env`. No harder-task model score or paid usage is claimed.
