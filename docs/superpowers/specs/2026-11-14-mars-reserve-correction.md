# Correct the 3D demo’s home reserve

Independent read-only review of Kristján’s new `18a1351` demo found two
contract problems, while confirming all eight displayed recorded outcomes.
The HOME lower bound charges distance to the base centre although grading
accepts positions within `base_radius` (0.75 m). A07 at interpolated time 22.8
has battery 17.20, old marker 17.4663 and corrected minimum 16.7163. The
red warning can therefore appear prematurely. Both affected discrete first
warning ticks remain 23 after correcting the radius.

Choose the smallest correction: idle drain through the remaining horizon plus
`max(0, distance_to_base - base_radius) * drive_cost`. This assumes no slip or
detours and is a necessary energy bound, not a sufficient safe plan. Keep
queued commands, true motion and recorded grades untouched. Merely removing
the warning would lose a useful explanation; changing physics would invalidate
evidence and is outside scope.

Make labels distinguish insufficient reserve to **finish home and alive** from
being unable to arrive home at all or inevitable death. A01 warns at tick 23,
arrives home alive at 25, then dies at 49. Surviving away earns half science
value. A07’s death is independently unavoidable at tick 24 when 12.7 battery
cannot cover 13 idle drain; at tick 23, its sample for tick 24 is already queued,
preventing a claim that an idle-only rescue is available.

Preserve Kristján’s layout, render style, controls, selected runs and narrative
structure. Change only reserve math, relevant labels/mission wording, README
and rebuild artifacts with the existing builder. The user authorized autonomous
correctness review/fixes; this is not a new mission or final project decision.

Verify the actual JavaScript on the concrete interpolated counterexample,
at-base/in-radius positions, and all eight displayed trajectories; use the
existing viewer tests/build-freshness checks. Inspect actual Chrome output and
independently review the final diff before integration. Avoid a test that only
repeats the implementation’s formula or asserts the new prose.

## Verification

The 28 existing viewer tests passed before and after the correction, including
the standalone-page freshness and recorded-evidence checks:

```sh
python3 viewer/build_mars.py
python3 -m unittest discover -s tests/viewer -v
git diff --check
```

A one-off Playwright regression exercised the actual standalone JavaScript in
isolated headless Google Chrome 157.0.8103.52, with no user profile. Before the
fix it failed on A07 at 22.8: battery 17.199999999999996, reserve
17.466288668394117, and a red bar labelled “no way home.” After the fix the same
check passed with reserve 16.716288668394117 and an unflagged battery bar.
At tick 23 the corrected warning reads “CANNOT FINISH HOME ALIVE.” Screenshots
at both times were inspected; the caption and toast fit the existing layout.

The same actual `Run` instances verified all eight displayed trajectories:
A01 and A07 first warn at saved tick 23; the six surviving runs never warn.
At ticks 0, 22.8 and 50, positions at the centre, inside the accepted radius and
on its boundary have equal reserve bounds; a position outside has a larger
bound. A01 is alive within the base radius at tick 25 and first dead at tick 49.
Chrome reported no script errors or external requests.

The animated counterexample can also be inspected in the page's browser console:

```js
const run = LIGHTLAG.MISSIONS[0].runs[2];
const pose = run.sample(22.8);
[pose.battery, run.need(22.8, pose.x, pose.y)];
// [17.199999999999996, 16.716288668394117]
```

The rebuilt data differs only in the Deadlines mission brief. Every complete
recorded run object, including replays, calls, reported words and rewards, is
unchanged. No rendering, styling or interaction code was changed. Independent
review approved the final corrected artifact.

Independent review also distinguished the Earth feed’s noisy position-based
estimate from the true-state bound. Its warning caption now says “low estimated
reserve”; the synthetic truth-derived reserve toast is omitted from Earth.
No observed false alarm on a noisy saved run is claimed.

Final independent Chrome review also checked Earth at tick 26.2: “low estimated
reserve” appears and the synthetic true-state warning toast is absent. Root
repeated the actual-page regression and all 28 viewer tests after this change.
No script errors or external requests; captions fit the inspected desktop layout.
