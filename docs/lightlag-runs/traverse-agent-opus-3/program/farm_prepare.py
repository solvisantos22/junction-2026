"""Added for the Traverse farm by Claude Code; not written by the agent.

Opus agent 3 prepared its autopilot by hand before starting it (trajectory calls 0, 3 and 7):
it saved the world to /tmp/map.json, kept its files in /tmp/ll, built the distance table
/tmp/ll/D.pkl with route.py, then started auto.py from /tmp/ll at tick 0. This script repeats
those steps on any world so the farm can replay the program:

    agent:docs/lightlag-runs/traverse-agent-opus-3/program/farm_prepare.py

Nothing here changes the agent's files or decisions. It writes to /tmp, so run it only in
the farm's container (or a sandbox), never on a laptop.
"""

import json
import os
import runpy
import shutil

from lightlag_client import connect

HERE = os.path.dirname(os.path.abspath(__file__))
os.makedirs("/tmp/ll", exist_ok=True)
for name in ("plan.py", "route.py", "opt.py", "auto.py"):
    shutil.copyfile(os.path.join(HERE, name), os.path.join("/tmp/ll", name))
for stale in ("/tmp/ll/D.pkl", "/tmp/map.json", "/tmp/rules.json"):   # never reuse another world's files
    if os.path.exists(stale):
        os.remove(stale)

with connect("http://lightlag:8000/mcp") as tools:            # call 0: the world, before any tick
    with open("/tmp/map.json", "w") as handle:
        json.dump(tools.map(), handle)
    with open("/tmp/rules.json", "w") as handle:
        json.dump(tools.rules(), handle)

os.chdir("/tmp/ll")
runpy.run_path("/tmp/ll/route.py", run_name="__main__")      # call 3: python3 route.py
runpy.run_path("/tmp/ll/auto.py", run_name="__main__")       # call 7: python3 auto.py
