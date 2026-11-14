# Write a stereo-survey planner

Return one complete Python program in a single ```python code block. It must
define `solve(mission)` and return exactly `{"images": [image IDs]}`. It will be
run on many new missions, so write a general algorithm, not answers for examples.
Maximize the sum of weights of cells reconstructed by valid stereo pairs.

You have Python 3.12, its standard library, and the supplied `stereo_survey`
package containing `geometry.py` and `verify.py`. You can import these helpers,
call `verify(mission, plan)`, implement search/optimization and use all public
mission data. There is no external network or additional installed solver.
This is a single-generation test: you cannot execute code during this response.
Your program gets 30 seconds, one CPU and 512 MiB for each fresh mission, in a
new process. Return your best valid plan within that limit. Printing is not a
submission; return the plan. Runtime errors, timeouts and invalid plans earn zero.

## Rules

Two camera platforms have known candidate images. At each camera opportunity,
select at most one of two frames, or skip it. Compact missions offer 24 images
(six opportunities per camera); expanded missions offer 32 (eight per camera).
Both have 20 weighted ground cells. Every input is in `mission`; there are no
hidden parameters or stochastic transitions.

A cell earns its weight once if two returned images cover its centre, their
camera-to-cell rays make an allowed convergence angle, their capture times
differ by no more than the published maximum and their ground-sampling-distance
ratio is allowed. The thresholds are in `mission["stereo"]`. Images from the
same camera can form products too. One image can support several products.
Overlapping products never earn a cell twice. A single image earns no science.

Coordinates are metres, x east, y north, z up; ground is z=0. Supplied rectangular
footprints are orthorectified. Angles are degrees. For example, cameras at
(-5,0,10) and (5,0,10) looking at (0,0,0) make 53.1301 degrees of convergence.
No optics, terrain or orbit calculation is needed. The public geometry code
below defines boundary tolerances and the exact convention.

An exposure lasts one tick. Slewing from the previous pointing direction takes
`ceil(angle / slew_rate - 1e-9)` ticks and costs
`ceil(angle / slew_energy_angle - 1e-9)` energy, in addition to capture energy.
The initial pointing and previous end tick are supplied per platform. There is
no recharging. The next exposure must leave sufficient time for the slew.

Each captured image uses one memory slot. Public downlink windows transmit
oldest frames first up to their capacities, paying energy per frame. Downlink
happens BEFORE capture at the same tick; new data waits for a later window.
Channels are separate for the two cameras. All selected frames must be returned
by the horizon. Exceeding memory, exhausting battery, conflicting exposures,
insufficient slew time or unreturned data makes the entire plan invalid.

The supplied validator is authoritative, and returns raw science, validity,
errors and a resource trace. The evaluator independently calls the unchanged
validator on your returned plan. You receive no optimum, reference planner,
search implementation or evaluation answers. Try to get as close to the best
possible science score as you can on every mission.
