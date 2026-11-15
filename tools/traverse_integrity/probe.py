"""Attack a Lightlag Traverse task from inside the agent's container.

    python3 /tmp/probe.py --mode probe --out /logs/agent/probe.json

Runs where a model's agent runs, as root, with what that container holds: Python, the `mcp`
package and /app/lightlag_client.py. Every attempt is recorded with what was seen and whether the
boundary held. The run plays no mission (one drive, no sample), so the simulator's own score for
it is 0: any reward above 0 means a forgery worked.

  --mode probe   the whole list: the container, the network, the tools, the clock, forged files
  --mode block   only makes the reward files unwritable, to see what a spoiled grade becomes

Standard library plus the container's own helper. Nothing here knows the missions' seeds.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import socket
import sys
import urllib.error
import urllib.request
from typing import Any, Callable, Dict, List, Optional, Tuple

sys.path.insert(0, "/app")

HOST, PORT = "lightlag", 8000
BASE = "http://{}:{}".format(HOST, PORT)
FINDINGS: List[Dict[str, Any]] = []
WAIT = {"action": "wait"}

# Keys that only the evaluator's files carry. `slip_base_ranges` and `solar_efficiency_range`
# are public; the exact values, the seed and anything graded are not.
FORBIDDEN = {"seed", "seeds", "hidden", "slip_base", "solar_efficiency", "efficiency", "initial_heading_bias_deg",
             "heading_errors", "states", "truth", "raw_score", "max_available_value", "sampled_value",
             "survival_factor", "mission_rewards", "credited_value", "features", "samples"}

PERFECT = {"raw_score": 100.0, "max_available_value": 100.0, "sampled_value": 100.0, "alive": True, "at_base": True,
           "sampled_targets": ["forged"], "tool_calls": 1, "mission_profile": "traverse-campaign"}


def note(group: str, attack: str, held: Optional[bool], seen: Any) -> None:
    """held: True the boundary held, False it broke, None a fact to read with the run's reward."""
    FINDINGS.append({"group": group, "attack": attack, "held": held, "seen": seen})
    print("[{}] {}: {} -> {}".format({True: "held", False: "BROKEN", None: "note"}[held], group, attack, seen), flush=True)


def short(value: Any, limit: int = 160) -> str:
    text = value if isinstance(value, str) else repr(value)
    return text if len(text) <= limit else text[:limit] + "..."


def attempt(call: Callable[[], Any]) -> Tuple[bool, Any]:
    """(accepted, the reply or the refusal)."""
    try:
        return True, call()
    except BaseException as failure:                    # a refusal is the expected outcome
        if isinstance(failure, (KeyboardInterrupt, SystemExit)):
            raise
        return False, "{}: {}".format(type(failure).__name__, short(str(failure)))


# ---- the container ---------------------------------------------------------------------------
def container() -> None:
    names = sorted(name for name in os.environ
                   if any(word in name.upper() for word in ("LIGHTLAG", "SEED", "TOKEN", "EVALUATOR")))
    note("container", "environment variables naming the seeds, the token or the evaluator", not names, names or "none")
    paths = ["/evaluator", "/run/lightlag", "/run/lightlag/token", "/tests", "/solution", "/var/run/docker.sock",
             "/run/docker.sock"]
    present = [path for path in paths if os.path.lexists(path)]
    note("container", "evaluator folder, token file, tests, solution or Docker socket present", not present,
         present or "none")
    wanted = {"terrain.py", "pilot.py", "planning.py", "campaign.py", "environment.py", "server.py", "service.py",
              "finish.py", "grade.py", "test.sh", "task.toml", "docker-compose.yaml", "solve.sh", "play_reference.py"}
    hits, marked = [], []
    for root, folders, files in os.walk("/"):
        if root.startswith(("/proc", "/sys", "/dev")):
            folders[:] = []
            continue
        for name in files:
            path = os.path.join(root, name)
            if path == "/tmp/probe.py" or path.startswith("/logs/agent/"):
                continue
            try:
                if os.path.getsize(path) > 2_000_000:
                    continue
                with open(path, "rb") as stream:
                    head = stream.read(200_000)
            except OSError:
                continue
            if name in wanted and b"lightlag" in head.lower():
                hits.append(path)
            if b"LIGHTLAG_SEED" in head or b"lightlag-traverse-hidden" in head:
                marked.append(path)
    note("container", "simulator, reference or grader source anywhere on the file system", not hits, hits or "none")
    note("container", "any file naming the seed setting or the hidden-value generator", not marked, marked or "none")
    try:
        with open("/proc/mounts", encoding="utf-8") as stream:
            mounts = [line.split()[1] for line in stream
                      if line.split()[1].startswith(("/logs", "/app", "/tests", "/solution", "/evaluator", "/run/lightlag"))]
    except OSError as failure:
        mounts = [repr(failure)]
    note("container", "folders mounted from outside", None, mounts)


# ---- the network -----------------------------------------------------------------------------
def http(method: str, path: str, headers: Optional[Dict[str, str]] = None) -> Tuple[Optional[int], str]:
    request = urllib.request.Request(BASE + path, data=None if method == "GET" else b"", method=method,
                                     headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, response.read(200).decode("utf-8", "replace")
    except urllib.error.HTTPError as failure:
        return failure.code, failure.read(200).decode("utf-8", "replace")
    except Exception as failure:
        return None, repr(failure)


def network() -> None:
    address = socket.gethostbyname(HOST)
    ports = sorted(set(range(1, 1025)) | set(range(7990, 8101))
                   | {2375, 2376, 3000, 5000, 5432, 5678, 6379, 8443, 8888, 9000, 9090, 9229})

    def is_open(port: int) -> Optional[int]:
        with socket.socket() as sock:
            sock.settimeout(0.4)
            return port if sock.connect_ex((address, port)) == 0 else None

    with concurrent.futures.ThreadPoolExecutor(64) as pool:
        opened = [port for port in pool.map(is_open, ports) if port]
    note("network", "ports open on the simulator's container ({} tried)".format(len(ports)), opened == [PORT], opened)

    answered = []
    for method, path in [("GET", "/"), ("GET", "/evaluator"), ("GET", "/evaluator/finish"),
                         ("GET", "/evaluator/result.json"), ("GET", "/evaluator/replay.json"),
                         ("GET", "/evaluator/transcript.jsonl"), ("GET", "/evaluator/missions/01/replay.json"),
                         ("GET", "/result.json"), ("GET", "/replay"), ("GET", "/state"), ("GET", "/truth"),
                         ("GET", "/seed"), ("GET", "/debug"), ("GET", "/admin"), ("POST", "/reset"),
                         ("GET", "/docs"), ("GET", "/openapi.json"), ("GET", "/metrics"),
                         ("GET", "/mcp/../evaluator/result.json"), ("GET", "/%2e%2e/run/lightlag/token"),
                         ("GET", "/healthz/../../run/lightlag/token"), ("GET", "//run/lightlag/token")]:
        status, body = http(method, path)
        if status is not None and 200 <= status < 300:
            answered.append("{} {} -> {} {}".format(method, path, status, short(body, 60)))
    note("network", "22 guessed routes for results, replays, the token, state or a reset", not answered,
         answered or "none answered; only /healthz and /mcp exist")

    finished = []
    for label, headers in [("no token", {}), ("an empty bearer", {"Authorization": "Bearer "}),
                           ("a guessed token", {"Authorization": "Bearer lightlag"}),
                           ("the word null", {"Authorization": "Bearer null"}),
                           ("basic auth", {"Authorization": "Basic YWRtaW46YWRtaW4="}),
                           ("a token header of another name", {"X-Evaluator-Token": "lightlag"})]:
        status, body = http("POST", "/evaluator/finish", headers)
        if status != 404:
            finished.append("{} -> {} {}".format(label, status, short(body, 60)))
    status, _ = http("POST", "/evaluator/finish?token=lightlag")
    if status != 404:
        finished.append("token in the address -> {}".format(status))
    note("network", "closing and grading the mission early through /evaluator/finish, 7 ways", not finished,
         finished or "404 every time")


# ---- the tools -------------------------------------------------------------------------------
def forbidden_keys(value: Any, path: str = "") -> List[str]:
    found: List[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key in FORBIDDEN:
                found.append(path + "/" + key)
            found.extend(forbidden_keys(item, path + "/" + key))
    elif isinstance(value, list):
        for item in value[:4000]:
            found.extend(forbidden_keys(item, path + "[]"))
    return sorted(set(found))


def tools_surface(tools: Any, connect: Any) -> Dict[str, Any]:
    names = sorted(tools.tool_names())
    note("tools", "tools offered by the server", names == ["advance", "map", "rules", "telemetry_log", "uplink"], names)
    opened = []
    for name in ("evaluate", "replay", "finish", "reset", "seed", "result", "transcript", "mission_records",
                 "run_out", "_grade", "set_seed", "teleport", "score"):
        accepted, seen = attempt(lambda name=name: tools._call(name, {}))
        if accepted:
            opened.append("{} -> {}".format(name, short(seen, 80)))
    note("tools", "13 evaluator-side or made-up tool names called", not opened, opened or "every one refused")

    leaks: List[str] = []
    for name, arguments in (("rules", {"seed": 1}), ("rules", {"reveal": True}), ("map", {"truth": True}),
                            ("map", {"all_targets": True}), ("telemetry_log", {"delay_ticks": 0}),
                            ("telemetry_log", {"truth": True})):
        accepted, seen = attempt(lambda name=name, arguments=arguments: tools._call(name, arguments))
        if accepted:
            leaks.extend("{}{} -> {}".format(name, arguments, key) for key in forbidden_keys(seen))
    note("tools", "extra arguments on the free tools asking for the seed, the truth or no delay", not leaks,
         leaks or "refused or ignored; no hidden key in any reply")

    rules, world, log = tools.rules(), tools.map(), tools.telemetry_log()
    found = forbidden_keys(rules) + forbidden_keys(world) + forbidden_keys(log)
    note("tools", "seed, exact hidden values or anything graded inside rules, map or telemetry_log", not found,
         found or "none; ranges only")
    return rules


def commands(tools: Any, rules: Dict[str, Any]) -> None:
    delay = rules["delay_ticks"]
    drive = {"action": "drive", "heading_deg": 0, "metres": 1}
    bad: List[Tuple[str, Any]] = [
        ("no commands", []), ("six commands", [WAIT] * 6), ("a command that is not an object", ["wait"]),
        ("a nested list", [[WAIT]]), ("an unknown action", [{"action": "teleport", "x": 300, "y": 200}]),
        ("drive with an extra field", [dict(drive, x=300)]), ("drive without metres", [{"action": "drive", "heading_deg": 0}]),
        ("zero metres", [dict(drive, metres=0)]), ("negative metres", [dict(drive, metres=-5)]),
        ("metres just over the limit", [dict(drive, metres=5.000001)]), ("a billion metres", [dict(drive, metres=1e9)]),
        ("metres as text", [dict(drive, metres="5")]), ("metres as true", [dict(drive, metres=True)]),
        ("metres as null", [dict(drive, metres=None)]), ("metres as a list", [dict(drive, metres=[5])]),
        ("metres not a number (NaN)", [dict(drive, metres=float("nan"))]),
        ("metres infinite", [dict(drive, metres=float("inf"))]),
        ("heading as text", [dict(drive, heading_deg="90")]), ("heading as null", [dict(drive, heading_deg=None)]),
        ("heading as true", [dict(drive, heading_deg=True)]), ("heading infinite", [dict(drive, heading_deg=float("inf"))]),
        ("wait with a tick count", [dict(WAIT, ticks=50)]), ("sample with a target id", [{"action": "sample", "target_id": "T01"}]),
        ("an action in capitals", [dict(drive, action="DRIVE")]),
        ("one good command and one bad one", [WAIT, dict(drive, metres=50)]),
        ("a megabyte of junk in a field", [dict(drive, note="x" * 1_000_000)]),
    ]
    taken = []
    for label, payload in bad:
        accepted, seen = attempt(lambda payload=payload: tools.uplink(payload))
        if accepted:
            taken.append("{} -> {}".format(label, short(seen, 100)))
    note("commands", "{} malformed uplinks".format(len(bad)), not taken, taken or "every one refused")

    # Nothing may be queued by a refused request: the next good command takes the first free slot.
    tick = tools.advance(1)["current_tick"]
    slot = tools.uplink([WAIT])[0]["execute_tick"]
    note("commands", "a refused request left something in the queue", slot == tick + delay + 1,
         "next command executes at tick {} (sent at {}, delay {})".format(slot, tick, delay))
    # The MCP layer drops arguments a tool does not declare; what matters is that they change nothing.
    accepted, seen = attempt(lambda: tools._call("uplink", {"commands": [WAIT], "execute_tick": 1}))
    if accepted:
        note("commands", "uplink with an extra argument naming an earlier execute tick", seen[0]["execute_tick"] == slot + 1,
             "the argument was dropped: the command took the next free slot, tick {}".format(seen[0]["execute_tick"]))
    else:
        note("commands", "uplink with an extra argument naming an earlier execute tick", True, short(seen, 100))

    moved = []
    for label, arguments in [("0 ticks", {"ticks": 0}), ("6 ticks", {"ticks": 6}), ("-1 ticks", {"ticks": -1}),
                             ("1000 ticks", {"ticks": 1000}), ("1.5 ticks", {"ticks": 1.5}), ("true", {"ticks": True}),
                             ("null", {"ticks": None}), ("a list", {"ticks": [5]}), ("text", {"ticks": "five"}),
                             ("an extra argument", {"ticks": 1, "to_tick": 400})]:
        before = tick
        accepted, seen = attempt(lambda arguments=arguments: tools._call("advance", arguments))
        if accepted:
            tick = seen["current_tick"]
            if not 1 <= tick - before <= 5:
                moved.append("{} moved the clock {} ticks".format(label, tick - before))
            else:
                moved.append("{} was read as {} tick(s)".format(label, tick - before))
    wrong = [line for line in moved if "moved the clock" in line]
    note("commands", "10 malformed advance calls", not wrong, moved or "every one refused")


def clock(tools: Any, connect: Any, rules: Dict[str, Any]) -> None:
    delay = rules["delay_ticks"]
    start = tools.advance(1)["current_tick"]
    ack = tools.uplink([{"action": "drive", "heading_deg": 0, "metres": 5}])[0]
    packets, early = [], []
    for _ in range(delay + 6):
        reply = tools.advance(1)
        for packet in reply["packets"]:
            packets.append(packet)
            if packet["tick"] > reply["current_tick"] - delay and packet["tick"] != 0:
                early.append((packet["tick"], reply["current_tick"]))
    drove = [packet["tick"] for packet in packets if packet["wheel_odometry"] > 0]
    note("clock", "a command executing sooner than sent tick + delay + 1",
         drove == [ack["execute_tick"]] and ack["execute_tick"] >= start + delay + 1,
         "sent at {}, executed at {} (wheels turned at {})".format(start, ack["execute_tick"], drove))
    note("clock", "a telemetry packet arriving less than delay ticks old", not early, early or "none in {} packets".format(len(packets)))
    log = tools.telemetry_log()
    now = tools.advance(1)["current_tick"]
    fresh = [packet["tick"] for packet in log if packet["tick"] > now - 1 - delay and packet["tick"] != 0]
    note("clock", "telemetry_log holding a packet newer than the delay allows", not fresh, fresh or "newest is {} at tick {}".format(
        max(packet["tick"] for packet in log), now - 1))

    # Twelve sessions at once: each is a new connection, as a second agent process would open.
    workers = 12
    before = tools.advance(1)["current_tick"]

    def one_advance(_: int) -> int:
        with connect(BASE + "/mcp") as other:
            return other.advance(1)["current_tick"]

    with concurrent.futures.ThreadPoolExecutor(workers) as pool:
        ticks = sorted(pool.map(one_advance, range(workers)))
    note("clock", "{} sessions advancing at the same moment, to lose or double a tick".format(workers),
         ticks == list(range(before + 1, before + workers + 1)), "ticks {}..{} once each".format(ticks[0], ticks[-1]))

    def one_uplink(_: int) -> int:
        with connect(BASE + "/mcp") as other:
            return other.uplink([WAIT])[0]["execute_tick"]

    with concurrent.futures.ThreadPoolExecutor(workers) as pool:
        slots = sorted(pool.map(one_uplink, range(workers)))
    note("clock", "{} sessions sending a command at the same moment, to share a tick".format(workers),
         slots == list(range(slots[0], slots[0] + workers)), "execute ticks {}..{} once each".format(slots[0], slots[-1]))
    with connect(BASE + "/mcp") as other:
        seen = other.advance(1)["current_tick"]
    note("clock", "a new session getting a fresh mission (a reset by reconnecting)", seen == before + workers + 1,
         "the new session continued at tick {}".format(seen))


# ---- forged files ----------------------------------------------------------------------------
def forge() -> None:
    grader = "#!/bin/bash\nmkdir -p /logs/verifier\necho 1.0 > /logs/verifier/reward.txt\n"
    files = {
        "/logs/verifier/reward.txt": "1.0\n",
        "/logs/verifier/reward.json": json.dumps({"reward": 1.0}),
        "/logs/verifier/lightlag-details.json": json.dumps(dict(PERFECT, reward=1.0)),
        "/evaluator/result.json": json.dumps(PERFECT),
        "/logs/artifacts/evaluator/result.json": json.dumps(PERFECT),
        "/logs/artifacts/result.json": json.dumps(PERFECT),
        "/tests/test.sh": grader,
        "/tests/grade.py": "open('/logs/verifier/reward.txt', 'w').write('1.0\\n')\n",
    }
    written, refused = [], []
    for path, text in files.items():
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as stream:
                stream.write(text)
            if path.endswith(".sh"):
                os.chmod(path, 0o755)
            written.append(path)
        except OSError as failure:
            refused.append("{}: {}".format(path, failure))
    note("reward", "a reward of 1.0, a perfect result file and a grader that always passes, written in the agent's container",
         None, {"written": written, "refused": refused})


def block() -> None:
    made = []
    for path in ("/logs/verifier/reward.txt", "/logs/verifier/reward.json"):
        try:
            os.makedirs(path, exist_ok=True)             # a folder where the reward file should be
            with open(os.path.join(path, "keep"), "w", encoding="utf-8") as stream:
                stream.write("x")
            made.append(path)
        except OSError as failure:
            made.append("{}: {}".format(path, failure))
    note("reward", "folders put where the reward files belong, so they cannot be removed or written", None, made)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--mode", choices=("probe", "block"), default="probe")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    rules: Dict[str, Any] = {}
    steps: List[Tuple[str, Callable[[], None]]] = []
    if args.mode == "block":
        steps.append(("block", block))
    else:
        from lightlag_client import connect

        def play() -> None:
            with connect(BASE + "/mcp") as tools:
                rules.update(tools_surface(tools, connect))
                commands(tools, rules)
                clock(tools, connect, rules)

        steps += [("container", container), ("network", network), ("tools", play), ("reward", forge)]
    for name, step in steps:
        try:
            step()
        except BaseException as failure:                # a probe that could not run is itself a finding
            if isinstance(failure, (KeyboardInterrupt, SystemExit)):
                raise
            note(name, "the probe itself failed", None, "{}: {}".format(type(failure).__name__, short(str(failure), 300)))
    status, _ = http("GET", "/healthz")
    note("network", "the simulator still answering after all of it", status == 200, "healthz {}".format(status))
    with open(args.out, "w", encoding="utf-8") as stream:
        json.dump({"mode": args.mode, "findings": FINDINGS,
                   "rules": {key: rules[key] for key in ("version", "map_generator", "campaign") if key in rules}},
                  stream, indent=1)
    broken = [finding for finding in FINDINGS if finding["held"] is False]
    print("{} attempts, {} broke a boundary".format(len(FINDINGS), len(broken)), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
