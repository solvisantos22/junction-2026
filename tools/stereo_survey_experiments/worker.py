"""Only this worker, the policy and public helpers enter the container."""

import contextlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
mission = json.load(sys.stdin)
with contextlib.redirect_stdout(sys.stderr):
    from policy import solve
    plan = solve(mission)
print(json.dumps(plan, allow_nan=False))
