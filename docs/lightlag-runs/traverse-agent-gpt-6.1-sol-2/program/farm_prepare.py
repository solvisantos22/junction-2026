"""Added for the Traverse farm by Claude Code; not written by the agent.

GPT-6.1 Sol agent 2 prepared its autopilot by hand (calls 7, 11, 15, 16 and 19): inspect_mission.py
saved the world and rules to /app, mission_plan.py wrote /app/route.json, the agent sent one
`wait` and advanced one tick through its own tools, then started autopilot.py (which expects
that wait at tick 4). It installed numpy 2.5.4 and scipy 1.18.1 first (call 9); the replay
needs them.
This script repeats that on any world so the farm (or the sandbox) can replay the program:

    agent:docs/lightlag-runs/traverse-agent-gpt-6.1-sol-2/program/farm_prepare.py

The program keeps its files in /app, as in the task's container, so /app is emptied first and
the agent's files copied in: one world's files (a checkpoint the program would resume from)
never reach the next. Nothing here changes the agent's files or decisions. It writes to /app,
so run it only in the farm's container or the sandbox, never on a laptop.
"""

import os
import runpy
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
KEEP = ("lightlag_client.py", "lightlag_surface.py", "sandbox_main.py")
os.makedirs("/app", exist_ok=True)
if os.path.realpath(HERE) == "/app":           # the sandbox: the program is already in /app; drop all but .py
    stale = [name for name in os.listdir("/app") if not name.endswith(".py")]
else:                                           # the farm: a fresh /app holding the agent's files
    stale = [name for name in os.listdir("/app") if name not in KEEP]
for name in stale:
    path = os.path.join("/app", name)
    shutil.rmtree(path) if os.path.isdir(path) else os.remove(path)
if os.path.realpath(HERE) != "/app":
    for name in os.listdir(HERE):
        if name.endswith(".py") and name != "farm_prepare.py":
            shutil.copyfile(os.path.join(HERE, name), os.path.join("/app", name))
os.chdir("/app")
runpy.run_path("/app/inspect_mission.py", run_name="__main__")   # call 7
runpy.run_path("/app/mission_plan.py", run_name="__main__")       # call 11
from lightlag_client import connect
with connect("http://lightlag:8000/mcp") as tools:                 # calls 15 and 16, by hand
    tools.uplink([{"action": "wait"}])
    tools.advance(1)
runpy.run_path("/app/autopilot.py", run_name="__main__")         # call 19
