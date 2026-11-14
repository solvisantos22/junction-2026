## Planning aid: energy and outstanding commands

Use the existing public rules, map, telemetry and acknowledgements to maintain
a compact ledger in your own notes or code. Update it when new information
arrives. Distinguish observations from estimates.

Record the current tick, the newest telemetry packet's state tick and battery,
and the commands you have submitted with their acknowledged execution ticks.
Keep track of executions or cancellations confirmed by telemetry. An action
missing from an old packet may still be pending or already executing.

Before each new uplink, check the energy remaining at the fixed episode
horizon, including commands already committed and any additional return:

    forecast terminal battery
      = battery reported at packet tick p
        - idle_cost * (max_ticks - p)
        - action expenditure after tick p

Action expenditure after p includes actions whose execution is not yet visible,
outstanding queued commands, the proposed batch, and additional actions needed
to return. Partition these costs so each command is counted once. Costs paid
at or before p are already reflected in that packet's battery.

Every tick through the horizon consumes idle energy, including ticks spent
at base after you finish. With initial battery 100, horizon 50 and idle cost
0.5, 25 energy is reserved for idle drain, leaving less than 75 for executed
drive and sample costs while retaining positive terminal battery. Recompute
from rules() if those values differ. Keep a positive margin.

Driving costs use wheel metres and the published terrain multipliers. Slip
changes ground displacement and the wheel distance required for a return.
Use justified estimates or conservative bounds where the path or terrain is
uncertain. Count sampling energy even when a sample might fail.

Use acknowledged execution ticks to track the command timeline. Account for
FIFO reservations and the published safety-stop rules; a cancellation need
not release reserved execution slots. Compare sample execution times with
deadlines, not their send times or telemetry arrival times.

Before advance(), check whether commands should be submitted first to avoid
an unintended queue gap or missed deadline. Waiting can be deliberate, but
stopping your interaction does not cancel accepted commands or future idle
drain. You may write and run code to maintain these checks.
