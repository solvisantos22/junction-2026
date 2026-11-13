# Junction Watch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Check agreed Junction sources every 15 minutes and deliver actionable updates to the user's existing chat until Sunday 17:00 Helsinki.

**Architecture:** A small Python standard-library timer adapter dispatches a dedicated Codex task via the local daemon. A macOS LaunchAgent schedules it. The agent reads native apps through CUA and owns source checkpoints; the adapter owns scheduling state.

**Tech Stack:** Python 3.9+, unittest, launchd, installed Codex CLI 0.169.0, existing CUA/tools.

## Task 1: timer adapter

Files: `tools/junction_watch/watch.py`, `tools/junction_watch/test_watch.py`, `tools/junction_watch/README.md`. The full runtime contract is in the approved design next to this plan.

- [ ] Write failing behavioral tests for: enabled dispatch, no dispatch when paused/expired, no duplicate while pending, one health alert per stalled check, resume after acknowledgement, and nonzero exit or resume warnings being recorded as failures. Test with temporary directories and an injected queue boundary; never call the real user's agent in unit tests.
- [ ] Run `python3 -m unittest discover -s tools/junction_watch -p 'test_*.py' -v` and observe the missing behavior before implementation.
- [ ] Implement CLI `watch.py --config PATH tick|status|pause|resume|stop`. Use JSON files with atomic replacement and a file lock to serialize manual/timed invocations. Defaults are explicit in config, not guessed. Status prints config and state without credentials.
- [ ] Queue with a subprocess argument array, never a shell:

```python
subprocess.run([config['codex_path'], 'queue', '--thread', thread_id,
                '--message', message, '--resume'],
               cwd=config['working_directory'], capture_output=True,
               text=True, timeout=45)
```

- [ ] The check message points to `instructions_path` and requires writing `run.json` after the attempt. Health messages are clearly labelled and target parent_thread_id. Do not queue another check while previous last_queued_at > run.last_finished_at. Warn once after interval_seconds; permit dispatch again when acknowledged. At ends_at disable config and remove/unload only the configured watcher timer.
- [ ] Document installation config, commands, source access limitations, state-file ownership and stopping. Run tests, self-review, and commit only Task 1 files. Do not install a real job from the implementation subagent.

## Task 2: configure, integrate and verify (primary agent)

- [ ] Prepare the watcher instructions and initial source knowledge in the private runtime directory, including verified URLs and the unresolved preliminary-submission discrepancy.
- [ ] Create the user-requested dedicated Codex task, inheriting the current model. Ask it to complete one real baseline check and send one clearly labelled test alert to the parent.
- [ ] Review Task 1 for spec compliance, then code quality. Resolve findings and rerun relevant tests.
- [ ] Install stable copies of the adapter and instructions in the runtime directory. Write config with real task IDs and end time `2026-11-15T17:00:00+02:00`.
- [ ] Create a LaunchAgent plist with label `com.solvisantos.junction-watch-2026`, ProgramArguments `/usr/bin/python3`, runtime `watch.py`, `--config`, runtime `config.json`, `tick`; StartInterval 900; stdout/stderr files in runtime; working directory is the Junction repository.
- [ ] Validate with `plutil -lint`, load with `launchctl bootstrap gui/UID PLIST`, then trigger with `launchctl kickstart gui/UID/com.solvisantos.junction-watch-2026`.
- [ ] Inspect launchctl state, adapter state, and the watcher's actual completion acknowledgement; inspect the parent test alert. These are required before claiming end-to-end success.
- [ ] Report schedule, stop time, source scope, log location, and actual limitations. Preserve the existing shareable idea brief and do not send it to Discord.
