# Complete hybrid development screening

All **8320 declared cases** are complete and audited: 65 arms on the same 128
worlds, 610000–610127. The six retained trained policies and all 41 declared groups
are included. Single-policy groups average all three training seeds within
each map before comparing maps. **8300 cases returned home alive; 20 rovers
died; zero invalid calls.** All outcomes remain in the published data.

[Full analysis and artifact hashes](analysis.json) · [all 41 groups](summary.csv) ·
[8320-row aggregate](aggregate-state.json) · [independent science audit](independent-audit.json) ·
[terminal/lineage/cost audit](terminal-audit.json).
The independent audit reproduced every group summary, paired-map bootstrap
interval and fixed selection exactly. Audits bind every completed row to the
saved physics/choice audit and original source/weight hashes. This closure
did not rerun simulations or independently replay every trajectory locally;
compressed trajectories remain on Modal with their hashes and storage paths.

Matched greedy averages **38.3869%**, and the frozen beam reference averages
**50.1834%**. The predeclared top-two-per-family rule selects these six groups:

| Group | Mean reward | Paired gain over greedy | Arms |
|---|---:|---:|---:|
| single-ppo-rho090 | 39.2638% | +0.8770 pp | 3 |
| single-ppo-rho075 | 39.1707% | +0.7839 pp | 3 |
| ensemble-ppo-rho090 | 39.4404% | +1.0536 pp | 1 |
| ensemble-all-rho090 | 39.3135% | +0.9267 pp | 1 |
| blend-ppo-greedy075 | 39.0243% | +0.6375 pp | 1 |
| blend-all-greedy050 | 38.9909% | +0.6040 pp | 1 |

All six selected groups have zero deaths/invalid calls and 100% home/alive
outcomes. The best observed group scores 39.4404%, a +1.0536 percentage-point
development difference from greedy. **This is screening evidence, not a
confirmed gain.** The same development maps chose the groups; intervals do not
correct for that selection, and even the best group's development interval
crosses zero. Report the full search, including its 20 deaths and the unsafe
groups excluded by the fixed gate. Keep the current team reference.

## Preserved execution lineage

The original coordinator and first recovery failed. Their states, original
calls and two failed worker attempts remain retained. Recovery2 call
`fc-01M7EDXYD8614C8X0ST20CR7N3` completed all 2510 permitted new attempts at
**01:56:45 UTC**: two explicitly diagnosed failed retries plus 2508 never-started
cases. Its combined record preserves all 5810 previous complete rows and call
IDs exactly. No committed completed case was submitted again. Lost uncommitted
computation on the two old failed attempts cannot be ruled out.

The final aggregate SHA256 is
`142d0b629c1a46ba1cd570fd4c61ce024daf3e5d3bde99ae0c3d5270f056cc80`.
The unchanged original analysis SHA256 is
`c14c476263dbffdc5ecfef562237b964296721ee1a98bff8336f342d05a70088`.
Full lineage and raw/mapped attempt-storage bindings are retained in the
[terminal state](recovery2-terminal-state.json), aggregate and published
[recovery freeze](../recovery2/freeze.json). All 54 scientific source pins and
parent weights remain exact in `/tmp/junction-hybrid-recovery2-frozen`;
teammates' newer main-branch harness changes remain intact.

Recorded hybrid running CPU/memory estimates total **$1.858378**, including the
65 smoke missions and four coordinators. Separate closed prior-training
compute is **$2.404367**, giving **$4.262745 combined recorded compute**.
These exclude ancillary/idle charges and unrecorded lost work and are not an
invoice. There were 8387 unique worker attempts including smoke (8322 for
development, of which two were retained failures), plus four coordinators.

## Next gate

The selected groups advance to a separately published [confirmation stage](../../confirmation/README.md):
21 arms including matched greedy, reference and all original pure learned
controls, on 256 new maps, 611000–611255. Publish this analysis, the exact stage
matrix and operations freeze before launching its 5376 cases. Confirmation
must choose at most one qualified group using the unchanged rules; if none
qualifies, stop and leave final 612000–612255 unopened. Final evaluation needs
its own published selection/source/weight/control freeze. No training restarts,
new policies, threshold tuning or reference change.
