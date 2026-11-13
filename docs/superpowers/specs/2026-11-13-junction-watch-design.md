# Junction Watch design

Approved scope: the user selected checks every 15 minutes for Discord announcements, AfterQuery and tech-support discussions, plus the challenge/submission pages; actionable changes are relayed to the current chat. Stop Sunday 15 November 2026 at 17:00 Europe/Helsinki.

## Approach

Use a dedicated local Codex task and a user-level macOS LaunchAgent. Each timer invocation calls the installed `codex queue --thread ID --message TEXT --resume`. The currently running Codex 0.169.0 daemon supports this command. A hosted task cannot use the already authenticated native Discord app; a continuously sleeping agent is less robust than the local scheduler.

The watcher uses connected tools when suitable, otherwise the documented CUA APIs for native Discord and Chrome. It reads only the agreed sources. It does not send Discord messages, react, change settings, submit the project, or operate unrelated pages. No personal-token scraping or unofficial Discord API access.

## Sources and output

- Junction Community Discord server 1268184974784336004: official announcements, AfterQuery, and tech support; relevant general discussion only when linked or needed to explain an update.
- https://hackjunction.app/participate/45 (dashboard), /challenges/328, /guide, /project.
- Read linked official AfterQuery starter resources if newly announced.
- Alert for changed deadlines, submission instructions, judging criteria, starter kits/credits, mentor clarifications, blockers, and actionable AfterQuery discussion. Exclude travel and routine chatter.
- Deduplicate using source links/message IDs and content summaries. Record timestamps and source access failures. Failed access is not evidence of no updates.
- Save a concise local updates log. Relay new actionable items through `send_message_to_thread` to the original thread. Routine checks stay in the watcher task.

## Runtime contract

Private runtime directory: `/Users/solvisantos/.codex/junction-watch-2026`.

`config.json` contains enabled, thread_id, parent_thread_id, codex_path, working_directory, interval_seconds=900, ends_at (ISO timestamp with offset), instructions_path, launch_agent_path, and launch_agent_label.

`scheduler.json` is owned by the timer and records queue times/errors and the pending check already alerted about. `run.json` is owned by the agent and contains numeric UTC epoch last_started_at and last_finished_at, status, and per-source results. The agent writes both timestamps after a complete attempt, including partial/blocked attempts. Separate files avoid overwriting each other's state.

The timer queues at most one outstanding check. If the last queued check has no completion acknowledgement by the next 15-minute tick, relay one health alert and refrain from adding more checks until it finishes. A queue warning about failed resume is an error, even if the CLI exits zero. Expiry disables checks and unloads/removes this watcher's LaunchAgent. Pausing disables dispatch; stopping also removes its timer.

## Limits and validation

This relies on the local Mac, Codex daemon, network and authenticated app access. Do not change sleep/security settings. Catch up from the last successful source check when access returns; explicitly report gaps.

Test deadline cutoff, paused behavior, pending-check suppression, one-time stalled alert, recovery after acknowledgement, and resume warnings. Then verify a real dedicated-task check, a clearly labelled test alert to the parent chat, and a check triggered through the installed LaunchAgent. Do not call the monitor active based only on a successful timer installation.
