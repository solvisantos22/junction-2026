# Five-minute main-push watcher

At Kristján's request, a dedicated Codex task on his Mac checks this repository
every 300 seconds for local commits missing from `origin/main`, then verifies
and publishes finished increments. Its task is **Main push watcher · every
5 minutes**. It runs until paused or stopped; no end date was requested.

The watcher fetches `origin`, inspects local branches and registered worktree
HEADs, and checks ancestry and patch equivalence. It uses its own integration
worktree and preserves source branch history. It checks the committed changes
and runs the affected existing tests, integrates any intervening remote changes,
then uses a normal push to `main` and confirms the commits reached the remote.

It leaves uncommitted work and other workers' Git operations alone. Explicit WIP,
failed checks, substantive conflicts and uncertain ownership are reported and
deferred. It never force-pushes or changes project rules. A task still being in
progress does not prevent a finished, verified increment from being published.

## Local operation

The installed macOS LaunchAgent is `com.krissi.junction-main-push-2026`, with
`StartInterval` set to `300`. Private instructions, configuration and state live
under `~/.codex/junction-main-push-2026/`; they are not committed to this repo.
The integration worktree is `/private/tmp/junction-main-push-integration`, on
`codex/main-push-watch`. The agent can recreate that worktree if it disappears.

The timer reuses an unchanged copy of the existing
[Junction Watch adapter](../tools/junction_watch/README.md), independently of
Sölvi's event-news watcher. Its required `ends_at` field uses the year 9999 as a
practical no-expiry value. Each timer tick can queue only one outstanding check;
if verification runs longer than five minutes, subsequent ticks wait for the
agent's completion acknowledgement. A missing acknowledgement produces one
health alert, rather than piling up overlapping checks.

Status and controls on Kristján's Mac:

```sh
python3 ~/.codex/junction-main-push-2026/watch.py \
  --config ~/.codex/junction-main-push-2026/config.json status
```

Replace `status` with `pause`, `resume`, or `stop`. Pause keeps the timer
installed. Stop disables it and removes only its own LaunchAgent. Resume
re-enables a paused installation; a stopped installation must be loaded again.
Already running work can finish after pausing or stopping.

The agent records each check in private `run.json` and in its dedicated task.
It reports successful pushes and new blockers to the setup conversation, with
repeat alerts suppressed. No-change checks do not create repository commits.
The Mac must be awake, online, and able to resume the local Codex task. Sleep,
network or authentication failures can delay checks; this is a local timer,
not a hosted service. It does not change the Mac's sleep settings.

## Installation verification

- Existing timer adapter: all 26 tests pass, including duplicate suppression,
  uncertain queue delivery, acknowledgement, pause/resume/stop and health alerts.
- LaunchAgent plist validates, and the loaded job reports a 300-second interval.
- Dedicated task has read the repository workflow and watcher instructions.
- A real launchd dispatch resumed the task, which fetched origin and confirmed
  all seven then-local branch tips and worktree HEADs were already included in
  `origin/main` at `269217a`; no integration or push was needed.
- The agent atomically recorded successful completion and delivered its setup
  acknowledgement to the parent conversation, with no blockers.
