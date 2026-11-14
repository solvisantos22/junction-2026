"""One Traverse mission per job, played in this process. The unit of work the farm hands out.

A job is a small dict that survives JSON:

    {"policy": "pilot", "seed": 123}                                  # the reference, as published
    {"policy": "pilot", "options": {"floor": 6.0}, "seed": 123}       # the reference with other options
    {"policy": "greedy", "seed": 123}                                  # any scripted policy of lightlag_traverse.play
    {"policy": "program", "program": "<source defining play(tools)>", "seed": 123, "time_limit": 1500}
    {"policy": "program", "files": {"auto.py": "<source>", ...}, "entry": "auto.py", "seed": 123}
    {"policy": "pilot", "seed": 123, "mission": {"sun_margin_ticks": 0}}   # any of these, on changed rules
    {"policy": "pilot", "seed": 123, "keep_replay": True}   # the row also holds the evaluator's replay
    {"policy": "pilot", "seed": 123, "analyse": True}       # ... or whether the rover could still get home (analysis.py)

The second form is an agent's own script as it ran in the task: it is started as `__main__` with a
stand-in `lightlag_client` beside it, as `lightlag_traverse.sandbox --program` does. Both forms get
the published ground model as `lightlag_surface.py`, and every reply is a JSON copy, as over MCP.

Extra keys (for example "candidate" or "label") are copied into the row unchanged. `run_job`
returns one row per job: who played, which world, the reward and how the mission ended. Rows
hold a replay only when the job asks for one (`keep_replay`, for the demo), so thousands stay small.

A "program" job runs model-written code in this process. That is only acceptable inside an
isolated container, so it is refused unless TRAVERSE_FARM_ALLOW_PROGRAMS=1, which the Modal
image sets and nothing else does.

Standard library only. `lightlag_traverse` is imported, never modified.
"""

from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
import os
import platform
import runpy
import shutil
import signal
import sys
import tempfile
import time
import types
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

SCRIPTED = ("pilot", "greedy", "straight", "nothing")
PASSTHROUGH = ("candidate", "label", "generation", "block", "analyse")


def _play():
    from lightlag_traverse import play
    return play


_SOURCE_ID: Optional[str] = None


def source_id() -> str:
    """A short hash of the Traverse code that plays, so every row says which version it came from."""
    global _SOURCE_ID
    if _SOURCE_ID is None:
        import lightlag_traverse
        folder = Path(lightlag_traverse.__file__).parent
        digest = hashlib.sha256()
        for name in ("environment.py", "surface.py", "terrain.py", "planning.py", "pilot.py", "play.py"):
            path = folder / name
            if path.exists():
                digest.update(name.encode() + b"\0" + path.read_bytes())
        try:
            import lightlag.model
            digest.update(b"lightlag/model.py\0" + Path(lightlag.model.__file__).read_bytes())
        except ImportError:
            pass
        _SOURCE_ID = digest.hexdigest()[:12]
    return _SOURCE_ID


class _CopyingTools:
    """The five tools, handing out and taking in JSON copies, as the MCP server does."""

    def __init__(self, tools: Any) -> None:
        self._tools, self.tick = tools, 0

    @staticmethod
    def _copy(value: Any) -> Any:
        return json.loads(json.dumps(value))

    def rules(self):
        return self._copy(self._tools.rules())

    def map(self):
        return self._copy(self._tools.map())

    def telemetry_log(self):
        return self._copy(self._tools.telemetry_log())

    def uplink(self, commands):
        return self._copy(self._tools.uplink(self._copy(commands)))

    def advance(self, ticks=1):
        reply = self._copy(self._tools.advance(ticks))
        self.tick = reply["current_tick"]   # the last tick the program saw, for its row
        return reply

    def tool_names(self):
        return ["rules", "map", "telemetry_log", "uplink", "advance"]


def _client_shim(tools: Any) -> types.ModuleType:
    """Stands in for the task's lightlag_client: connect() yields the five calls."""
    shim = types.ModuleType("lightlag_client")

    class RemoteToolError(ValueError):
        pass

    @contextlib.contextmanager
    def connect(target=None, *args, **kwargs):
        yield tools

    shim.connect, shim.RemoteToolError = connect, RemoteToolError
    return shim


def program_id(job: Dict[str, Any]) -> Optional[str]:
    """A short hash of a program job's code, so rows and caches tell programs apart without holding them."""
    if job.get("policy") != "program" or not ("program" in job or "files" in job):
        return job.get("program_id")   # a scripted job, or a result row, which carries the id and not the code
    payload = json.dumps({"program": job.get("program"), "files": job.get("files"), "entry": job.get("entry")}, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]


def job_key(item: Dict[str, Any]) -> str:
    """What makes two jobs (or a job and a row) the same mission: who plays, with what, on which world."""
    key = {"policy": item.get("policy"), "options": item.get("options") or {},
           "program": program_id(item), "seed": item.get("seed")}
    if item.get("mission"):   # changed rules make another mission; unchanged keys stay as they were saved
        key["mission"] = item["mission"]
    if item.get("analyse"):   # a row with the analysis is not the same as one without it
        key["analyse"] = True
    if item.get("map"):       # the MAX map is another mission on the same seed
        key["map"] = item["map"]
    return json.dumps(key, sort_keys=True)


def pilot_defaults() -> Dict[str, Any]:
    from lightlag_traverse.pilot import DEFAULTS
    return dict(DEFAULTS)


def policy_name(job: Dict[str, Any]) -> str:
    """The name lightlag_traverse.play understands for a scripted job."""
    policy, options = job["policy"], job.get("options") or {}
    if policy not in SCRIPTED:
        raise ValueError("unknown policy {!r}".format(policy))
    if not options:
        return policy
    if policy != "pilot":
        raise ValueError("only the pilot takes options")
    unknown = sorted(set(options) - set(pilot_defaults()))
    if unknown:   # the pilot would silently ignore them, and a search would tune nothing
        raise ValueError("the pilot has no option(s) {}".format(", ".join(unknown)))
    return "pilot:" + json.dumps(options, sort_keys=True)


class _TimeLimit(Exception):
    pass


@contextlib.contextmanager
def _time_limit(seconds: Optional[float]):
    """Interrupt the block after `seconds` of wall time (Unix, main thread only)."""
    usable = seconds and hasattr(signal, "SIGALRM") and _main_thread()
    if not usable:
        yield
        return

    def ring(signum, frame):
        raise _TimeLimit("time limit of {} s reached".format(seconds))

    previous = signal.signal(signal.SIGALRM, ring)
    signal.setitimer(signal.ITIMER_REAL, float(seconds))
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def _main_thread() -> bool:
    import threading
    return threading.current_thread() is threading.main_thread()


class _Tail(io.StringIO):
    """Stands in for a program's stdout and stderr, keeping only the end of what it printed."""

    def __init__(self, size: int = 2000) -> None:
        super().__init__()
        self.size = size

    def write(self, text: str) -> int:
        if self.tell() > 8 * self.size:   # trim now and then, so a chatty program cannot fill the memory
            rest = self.getvalue()[-self.size:]
            self.seek(0)
            self.truncate()
            super().write(rest)
        return super().write(text)

    def tail(self) -> str:
        return self.getvalue()[-self.size:]


def _run_program(job: Dict[str, Any], tools: Any, time_limit: Optional[float]) -> Dict[str, Any]:
    """Run a model-written controller once: `play(tools)` from "program", or an agent's script.

    Returns the program's failure as text (None if it ended normally: a failure is a result, never
    a harness crash), the last tick it saw, and the end of what it printed.
    """
    if os.environ.get("TRAVERSE_FARM_ALLOW_PROGRAMS") != "1":
        raise PermissionError("program jobs run model-written code; only inside the isolated farm container")
    from lightlag_traverse import surface

    tools = _CopyingTools(tools)
    work = Path(tempfile.mkdtemp(prefix="traverse-program-"))
    shutil.copyfile(surface.__file__, work / "lightlag_surface.py")   # as in the task's container
    script = None
    if "files" in job:
        for name, source in job["files"].items():
            if "/" in name or name in ("lightlag_client.py", "lightlag_surface.py"):
                raise ValueError("program file name {!r} is not allowed".format(name))
            (work / name).write_text(source, encoding="utf-8")
        script = work / job["entry"]
    else:
        (work / "policy.py").write_text(job["program"], encoding="utf-8")
    saved_path, saved_modules, saved_cwd = list(sys.path), set(sys.modules), os.getcwd()
    sys.path.insert(0, str(work))
    sys.modules["lightlag_client"] = _client_shim(tools)
    error, printed = None, _Tail()
    try:
        os.chdir(work)
        with contextlib.redirect_stdout(printed), contextlib.redirect_stderr(printed), _time_limit(time_limit):
            if script is not None:
                runpy.run_path(str(script), run_name="__main__")
            else:
                spec = importlib.util.spec_from_file_location("policy", work / "policy.py")
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                module.play(tools)
    except SystemExit:
        pass
    except BaseException as failure:  # noqa: B902 - a program's failure, whatever it is, is its result
        if isinstance(failure, KeyboardInterrupt):
            raise
        error = "{}: {}".format(type(failure).__name__, failure)[:400]
    finally:
        os.chdir(saved_cwd)
        sys.path[:] = saved_path
        for name in set(sys.modules) - saved_modules:   # nothing a program imported leaks into the next job
            sys.modules.pop(name, None)
        sys.modules.pop("lightlag_client", None)
        shutil.rmtree(work, ignore_errors=True)
    return {"error": error, "tick": tools.tick, "printed": printed.tail()}


def run_job(job: Dict[str, Any]) -> Dict[str, Any]:
    play = _play()
    seed = int(job["seed"])
    row: Dict[str, Any] = {key: job[key] for key in PASSTHROUGH if key in job}
    row.update(seed=seed, policy=job["policy"], options=job.get("options") or {})
    if job["policy"] == "program":
        row["program_id"] = program_id(job)
    mission = job.get("mission") or None   # rule changes for this mission, e.g. {"sun_margin_ticks": 0}
    if mission:
        row["mission"] = mission
    board = job.get("map") or None         # None: the Traverse map; "max": Manh's MAX map (lightlag_traverse_max)
    if board not in (None, "max"):
        raise ValueError("unknown map {!r}: leave it out, or use 'max'".format(board))
    if board and mission:
        raise ValueError("the MAX map takes no rule changes here")
    if board:
        row["map"] = board

    def environment():
        if board == "max":
            from lightlag_traverse_max.environment import make_env
            return make_env(seed, "max")
        return play.TraverseEnvironment(seed, mission=mission)

    want = bool(job.get("keep_replay") or job.get("analyse"))   # the evaluator's replay, for the demo or the analysis
    replay = None
    started = time.time()
    if job["policy"] == "program":
        env = environment()
        tools = play.PublicTools(env)
        ran = _run_program(job, tools, job.get("time_limit", 1500))
        seconds, calls = time.time() - started, tools.calls
        while not env.advance(5)["episode_complete"]:
            pass
        result = env.evaluate()
        # Where the program stopped steering, when the rover's battery ran out (None: it did not),
        # and, if either went wrong, the end of what the program printed.
        row.update(error=ran["error"], program_tick=ran["tick"], died_tick=None)
        if want or not result["alive"]:
            replay = env.replay()
        if not result["alive"]:
            row["died_tick"] = next(s["tick"] for s in replay["states"] if not s["alive"])
        if ran["error"] or not result["alive"]:
            row["printed"] = ran["printed"]
    elif not mission and not board:
        run = play.run_episode(play.policy(policy_name(job)), seed, keep_replay=want)
        result, seconds, calls = run["result"], run["seconds"], run["public_calls"]
        row["error"] = None
        replay = run.get("replay")
    else:   # play.run_episode, on changed rules or the MAX map
        if board == "max":
            from lightlag_traverse_max.play import policy as max_policy
            name = job["policy"] if job["policy"] == "manh_max" and not job.get("options") else (
                "manh_max:" + json.dumps(job["options"], sort_keys=True) if job["policy"] == "manh_max" else policy_name(job))
            controller = max_policy(name)
        else:
            controller = play.policy(policy_name(job))
        env = environment()
        tools = play.PublicTools(env)
        started = time.time()
        controller(tools)          # as there, a policy's error propagates: it must not turn into a low score
        seconds, calls = time.time() - started, tools.calls
        while not env.advance(5)["episode_complete"]:
            pass
        result = env.evaluate()
        row["error"] = None
        if want:
            replay = env.replay()
    if board == "max":
        row["trips"] = getattr(env, "_slip_trips", None)   # MAX-map slip-check stops, as lightlag_traverse_max.play counts them
    if job.get("analyse"):   # could the rover still have got home, tick by tick (see analysis.py)
        from .analysis import home_margin
        row.update(analyse=True, home=home_margin(replay))
    if job.get("keep_replay"):
        row["replay"] = replay
    row.update(
        reward=result["raw_score"] / result["max_available_value"],
        raw_score=result["raw_score"], max_value=result["max_available_value"],
        sampled_value=result.get("sampled_value"), samples=len(result.get("samples") or []),
        alive=bool(result["alive"]), at_base=bool(result["at_base"]),
        seconds=round(seconds, 3), public_calls=calls,
        host="{} {} / Python {}".format(platform.system(), platform.machine(), platform.python_version()),
        source=source_id(),
    )
    return row


def _safe(job: Dict[str, Any]) -> Dict[str, Any]:
    try:
        return run_job(job)
    except Exception as failure:  # a crashed job is reported, not silently dropped
        row = {key: job[key] for key in PASSTHROUGH if key in job}
        row.update(seed=job.get("seed"), policy=job.get("policy"), options=job.get("options") or {},
                   crash="{}: {}".format(type(failure).__name__, failure)[:400])
        if job.get("policy") == "program":
            row["program_id"] = program_id(job)
        if job.get("mission"):
            row["mission"] = job["mission"]
        return row


def local_map(jobs: Iterable[Dict[str, Any]], workers: int = 4) -> List[Dict[str, Any]]:
    """Run jobs on a local process pool; rows come back in job order, crashes as rows with `crash`."""
    jobs = list(jobs)
    if workers <= 1:
        return [_safe(job) for job in jobs]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(_safe, jobs, chunksize=1))
