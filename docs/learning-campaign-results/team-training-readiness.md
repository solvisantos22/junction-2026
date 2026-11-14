# Team question: final map before larger training

Sölvi asked us to wait while the team combines results and finalizes the map/task, and to get these questions to the other working sessions. **Kristján / Manh / final task owner: please answer here and push to main; link the answer from your TEAM_STATUS row.**

Sölvi's automatic8192/32768-mission continuations are paused. The local continuation supervisor has been stopped and verified absent; already-running2048-mission pilot jobs may finish and retain their evidence. Do not restart the old `--follow` command while this pause is in effect. No final-check worlds have been opened. This pause applies to Sölvi's campaign.

## Questions for the final task owners

1. **What exact version should larger training target?** Please give the Git commit, environment/package and Harbor task path, and whether this is normal Traverse, the three-mission campaign, MAX, or a combined version. Which mechanics or map-generation settings are still changing?
2. **What has actually broken or remains uncertain during integration?** Especially observation/action fields, command timing/queues, charging and energy forecasts, mission resets, reward normalization/full-horizon grading, and reference compatibility. Which issues must block training, and which are demo/documentation cleanup?
3. **What concrete checks will establish readiness, and who will post the ready commit?** Suggested starting points: relevant simulator/controller tests, clean Docker/Harbor baseline runs (reference, no-op and early stop), reproducible complete rewards, and disjoint agreed training/validation/final map ranges. Please adjust these based on the failures you have seen.

## Reply template

- Owner/session and timestamp:
- Proposed final commit + environment + Harbor task path:
- Rules still changing (or explicitly none):
- Training-blocking issues and owners:
- Checks already passed, commands/artifact links:
- Remaining required checks:
- Agreed map ranges / known overlaps:
- Ready for a bounded compatibility pilot? yes/no + reason:
- Team/user final choice or approval still needed:

No response has been received yet. A proposed version or successful baseline does not by itself choose the team's final project. After a final version is identified, first verify our training adapter against it and freeze the new experiment before spending on larger runs. The old normal-Traverse pilot remains evidence for its own frozen source; do not silently relabel it as a MAX or changed-task result.
