# Public-tool description correction

The overnight readiness audit used a real MCP client and found a concrete
contract ambiguity: the shared map description promises the full map, and
the telemetry description calls visual odometry metres actually moved.
Dynamic missions disclose targets later and can return noisy odometry.
Their authoritative `rules()` correctly explains both effects. This is a
description defect, not a demonstrated grading defect or cause of a model's
failure. The user authorized autonomous fixes and critical review overnight.

Choose neutral descriptions valid for core and dynamic missions. Say that
`map` returns currently available public map/target information, and that the
episode's rules define discoveries and timing. Describe visual odometry as
reported movement, with measurement accuracy defined by `rules`, and heading
as commanded heading. The shared introduction should refer to credited
science under the episode's sampling rules and estimation from telemetry,
so it does not promise exact inference or omit enabled deadline discounts.
Retain the explicit timing, energy horizon, scripting permission and all five
tool signatures. No simulator, scoring, queue, rule-return or controller changes.

An optional profile-specific description framework would add machinery for
this small correction. Changing only dynamic serving would leave the shared
description's claimed generality misleading. A short neutral correction is
sufficient; keep core explanations concrete and avoid unnecessary caveats.

Prepare only in a separate worktree while Block B is running. Do not change
the evaluation worktree, copied experimental tasks, hashes or old evidence.
Synchronize the canonical generated server copy using `harbor/sync_task.py`;
inspect its exact diff to ensure no unrelated files are changed. Integrate
only after the paid block is complete and its frozen-source exports verified.
This is a future package revision, not a repair to historical evidence.

Verification: inspect actual MCP instructions/descriptions alongside returned
rules for core, rush and rush_noisy; check the demonstrated partial-map and
noisy-odometry examples; run existing MCP and Harbor suites plus source-copy
synchronization. Do not add tests that merely repeat the new wording. Review
the diff to prove only descriptive constants and the generated copy changed.
Independent review precedes integration. Record the package-byte change and
retain the old manifests so later model evidence cannot be confused with the
corrected version. Final mission/profile adoption remains the team's decision.

## Delivered correction and historical reproduction

Integrated as `64fe6db` after Block B was complete and independently verified.
AST comparison confirms only `INSTRUCTIONS`, `MAP_DESCRIPTION` and
`TELEMETRY_DESCRIPTION` changed, with the generated canonical copy identical.
Fresh checks: 18 MCP tests, 11 Harbor tests, copy synchronization and whitespace
checks all pass. Independent review also checked core/rush/noisy MCP schemas,
responses, scores and replays, including partial-drive odometry.

The corrected server SHA-256 is
`a15c05da870cca1ae8a9f8f3bae718a076b8c301757d249bf48abe22cf5e7e59`.
Package bytes changed; historical A/B tasks and evidence did not. For the B
exporter's unchanged-source check, use checkout `6fb112f`, not this corrected
package revision. Do not rewrite old manifest hashes to match current code.
The synthesis experiment separately imports the declared `02e4f70` snapshot.
No new paid model run was needed to verify this description-only correction.
