# Correct the 3D demo’s home reserve

Independent read-only review of Kristján’s new `18a1351` demo found two
contract problems, while confirming all eight displayed recorded outcomes.
The HOME lower bound charges distance to the base centre although grading
accepts positions within `base_radius` (0.75 m). A07 at interpolated time22.8
has battery17.20, current marker17.4663 and corrected minimum16.7163. The
red warning can therefore appear prematurely. Both affected discrete first
warning ticks remain23 after correcting the radius.

Choose the smallest correction: idle drain through the remaining horizon plus
`max(0, distance_to_base - base_radius) * drive_cost`. This assumes no slip or
detours and is a necessary energy bound, not a sufficient safe plan. Keep
queued commands, true motion and recorded grades untouched. Merely removing
the warning would lose a useful explanation; changing physics would invalidate
evidence and is outside scope.

Make labels distinguish insufficient reserve to **finish home and alive** from
being unable to arrive home at all or inevitable death. A01 warns23, arrives
home alive25, then dies49. Surviving away earns half science value. A07’s death
is independently unavoidable at24 when12.7 battery cannot cover13 idle drain;
its already-queued sample at23 prevents claiming an available idle-only rescue.

Preserve Kristján’s layout, render style, controls, selected runs and narrative
structure. Change only reserve math, relevant labels/mission wording, README
and rebuild artifacts with the existing builder. The user authorized autonomous
correctness review/fixes; this is not a new mission or final project decision.

Verify the actual JavaScript on the concrete interpolated counterexample,
at-base/in-radius positions, and all eight displayed trajectories; use the
existing viewer tests/build-freshness checks. Inspect actual Chrome output and
independently review the final diff before integration. Avoid a test that only
repeats the implementation’s formula or asserts the new prose.
