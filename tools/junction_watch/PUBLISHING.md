# Publishing Junction Watch updates

Approved by Sölvi on Sunday 15 November: publish each new actionable event or AfterQuery update to the shared repository so teammates receive the same information as the parent chat. The 30-minute schedule and Sunday 17:00 Helsinki end remain unchanged. This is event documentation, not project implementation or permission to submit the project.

## Scope

- Publish through a dedicated clean Git worktree, never the shared checkout or another chat's worktree. The local runtime instructions hold its absolute path.
- Edit only `docs/junction-event-updates.md`, plus the Junction Watch row of `TEAM_STATUS.md` if its operational status changes. Read the root `AGENTS.md`, team workflow skill and current claims first. Other files are read-only.
- Keep a current-actions section and dated concise entries with source links, original publication times when shown, and observed Helsinki times. Separate official answers, participant questions, recommendations and unknowns. Preserve prior notices; label superseded guidance.
- Include meaningful submission-state changes and actionable monitoring coverage gaps/recoveries once per incident. Routine checks with no changes belong in private logs and require no commit or parent message.
- Never commit raw Discord conversations, private runtime/source logs, credentials, personal account data or internal task identifiers. Do not run project code, edit submission forms, post to Discord or change task requirements.

## For each actionable update

1. Complete the bounded source check and CUA completion summary. Read the latest shared note and private publication state to avoid duplicate entries.
2. Inspect the dedicated worktree and index. If changes or commits exist, establish that they belong to a prior watcher publication; otherwise stop publication and report the conflict without discarding anything.
3. Fetch `origin`, fast-forward a clean worktree, or rebase only the watcher's own unpublished commits. Do not force-push, reset, stash or amend another writer's work. Re-read current claims and any changed instructions.
4. Update the allowed note with verified information and source coverage. Stage explicit paths only. Check `git diff --cached --check`, review the entire staged diff, and validate relative links. Documentation-only updates need no implementation test suite or prize-evidence entry.
5. Commit the completed note, fetch again, integrate the latest `origin/main`, review the allowed-file diff and push `HEAD:main`. On a concurrent push, fetch/reconcile and retry once if it is unambiguous; otherwise retain the local commit and report the blocker. Bound network operations so publication cannot prevent the check from acknowledging completion.
6. Confirm the exact publication commit is on remote `main`. Record the commit and delivered update identifiers in a separate private `publication.json` (atomic replacement). Only mark an item published after verification; deduplication of parent alerts must not suppress retries of unpublished notes.
7. Relay the actionable alert to the parent with its repository link/commit. If publishing fails, alert immediately with the information and explicit push blocker, retain a pending publication, and retry on the next scheduled check even if no newer news appears.

Every attempt still writes a fresh numeric `last_finished_at` and status in `run.json`, including source-access or publication failures. Preserve each source's successful checkpoint. Record publication status separately from source coverage; a Git failure is not a failed Discord check. The watcher never edits `scheduler.json`, schedule configuration or its own instructions.

The parent chat may publish a notice if the watcher cannot. Coordinate before editing the same note, record the verified commit in the private publication state, and avoid duplicate commits. Future routine updates remain the watcher's responsibility.
