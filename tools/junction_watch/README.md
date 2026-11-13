# Junction Watch timer adapter

A Python 3.9+ standard-library CLI for macOS that queues one dedicated Codex
check every 15 minutes. It does not read Discord or websites itself; the
dedicated agent follows the configured instructions and reports actionable
updates to the parent chat.

## Configuration and installation

Keep runtime files in `~/.codex/junction-watch-2026`, with directory mode `700`
and configuration/instructions mode `600`. Copy `watch.py` there so the timer
does not depend on a temporary worktree. Create the dedicated task and its
instructions before enabling the timer. No credentials belong in config.

All config fields are required; use absolute paths and real task IDs:

```json
{
  "enabled": true,
  "thread_id": "DEDICATED_TASK_ID",
  "parent_thread_id": "PARENT_TASK_ID",
  "codex_path": "/absolute/path/to/codex",
  "working_directory": "/Users/solvisantos/Desktop/Junction",
  "interval_seconds": 900,
  "ends_at": "2026-11-15T17:00:00+02:00",
  "instructions_path": "/Users/solvisantos/.codex/junction-watch-2026/INSTRUCTIONS.md",
  "launch_agent_path": "/Users/solvisantos/Library/LaunchAgents/com.solvisantos.junction-watch-2026.plist",
  "launch_agent_label": "com.solvisantos.junction-watch-2026"
}
```

Save this as runtime `config.json`. The CLI must support
`codex queue --thread ID --message TEXT --resume` (the approved setup uses
Codex 0.169.0). The adapter invokes an argument array with the configured
working directory and a 45-second timeout, without a shell.

Create the configured LaunchAgent plist with these keys:

| Key | Value |
| --- | --- |
| `Label` | The exact configured `launch_agent_label` |
| `ProgramArguments` | `/usr/bin/python3`, absolute runtime `watch.py`, `--config`, absolute runtime `config.json`, `tick` |
| `StartInterval` | `900` |
| `WorkingDirectory` | The configured working directory |
| `StandardOutPath` / `StandardErrorPath` | Separate log paths inside the private runtime directory |

Validate the plist with `plutil -lint`, then load it using
`launchctl bootstrap gui/$(id -u) /absolute/path/to/watcher.plist`.
Use `launchctl kickstart gui/$(id -u)/com.solvisantos.junction-watch-2026` for
an initial tick. Verify both a real agent completion acknowledgement and a
clearly labelled parent test alert before treating monitoring as active.
This repository does not install or start the timer automatically.

## Commands

```sh
python3 ~/.codex/junction-watch-2026/watch.py \
  --config ~/.codex/junction-watch-2026/config.json status
```

Replace `status` with the required command:

| Command | Effect |
| --- | --- |
| `tick` | Queue a due check, or report paused, waiting, pending, or expired. |
| `status` | Print safe configuration values, UTC times, and scheduling health; omit task IDs, paths, source text, and credentials. |
| `pause` | Disable future checks while leaving the timer installed. |
| `resume` | Enable checks before the deadline; preserve any pending reservation. Does not reinstall a stopped timer. |
| `stop` | Disable checks, remove the configured plist, and unload only its configured launchd service. |

At the first tick on or after `ends_at`, even a paused watcher disables itself
and removes its timer. Resume is refused after expiry. Stop and expiry disable
config and unlink the plist before `launchctl bootout`, because unloading the
current job can terminate its process. If the plist's `Label` differs from the
configured label, removal is refused. A nonzero unload result is reported as
uncertain; checks remain disabled. Already queued or running checks may finish.

## State and recovery

The adapter owns `scheduler.json` and serializes commands with `watch.lock`.
JSON updates use same-directory atomic replacement. It reserves
`last_queued_at` **before** invoking Codex, then records `queue_status`, errors,
and `last_successful_queue_at` only after a confirmed successful dispatch.
`last_queued_at` is a conservative reservation, not proof of delivery.
Each reservation is strictly later than the previous completion it observed,
even when that completion was written after the tick sampled its clock.

The dedicated agent owns `run.json`. After every attempt, including partial or
blocked attempts, it must atomically replace that file with numeric UTC epoch
timestamps, a status, and per-source results, for example:

```json
{
  "last_started_at": 1794596401.0,
  "last_finished_at": 1794596470.0,
  "status": "partial",
  "sources": {
    "discord": {"status": "blocked", "detail": "Application unavailable"},
    "junction": {"status": "checked", "changes": []}
  }
}
```

While `scheduler.last_queued_at > run.last_finished_at`, no new check is
queued. After one interval, the adapter attempts one clearly labelled health
alert to `parent_thread_id`. Its alert marker is persisted before delivery;
even a failed or uncertain health alert is not retried for that check.
Acknowledgement releases the reservation, and normal scheduled checks resume.
Invalid completion timestamps or unreadable/malformed `run.json` cannot release
a pending check, but still allow its one health alert. Status reports an
`acknowledgement_error` until the agent writes valid state. Config and scheduler
errors continue to block dispatches.

A nonzero queue exit, timeout, interrupted process, or failed-resume warning
(even with exit code zero) leaves dispatch uncertain and pending. There is no
automatic retry: the command may have queued work before reporting failure.
Inspect the dedicated task and have it finish or acknowledge a blocked attempt
in `run.json`. If it cannot do so, pause and establish that no check remains
active before manually reconciling the pending state. Preserve the error
record; blindly deleting scheduler state can create duplicate checks.

## Limitations and tests

Monitoring requires the local Mac, a working Codex daemon, network access,
and authenticated app/browser sessions. Sleeping or offline time creates gaps;
the agent must catch up from source checkpoints and explicitly report failed
access. A failed check is not evidence of no updates. If Codex cannot resume
either task, the parent health alert may also be undeliverable; inspect local
status/logs. The adapter does not change sleep or security settings.

Run from the repository root:

```sh
python3 -m unittest discover -s tools/junction_watch -p 'test_*.py' -v
```

Tests use temporary files and an injected subprocess boundary. They never
invoke the real Codex queue or `launchctl`.
