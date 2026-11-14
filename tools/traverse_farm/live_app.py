"""Lightlag Traverse, live on Modal: pick any world, watch the reference and Claude's autopilots drive it.

    modal deploy tools/traverse_farm/live_app.py      # the web page, kept running by Modal
    modal run tools/traverse_farm/live_app.py --seed 871   # build one world's page here, without the web

A visitor picks a world (a seed). If its page is not cached yet, Modal plays four drivers on it at
once, each in its own container: the reference pilot, a textbook controller (terrain graph + Kalman
filter, greedy targets: the pilot's `greedy` option), Opus agent 3's autopilot and the one-request
Opus program, both Claude-written and replayed without their agents. About a minute later the page
is the Traverse demo (viewer/build_traverse.py) for that world, cached in a Modal Volume.

Only fixed code from this repository runs: the visitor supplies a number, nothing else. The rules
are the frozen Lightlag Traverse 0.1.0 rules, the reference task 0.1.1's pilot.
"""

from __future__ import annotations

import html
import time
from pathlib import Path

import modal

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
RUNS = REPO / "docs" / "lightlag-runs"
PROGRAMS = ("traverse-oneshot-opus-1", "traverse-agent-opus-3")     # the Claude programs a page shows


def _skip(path) -> bool:
    path = Path(path)
    return "__pycache__" in path.parts or path.suffix == ".pyc"


image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install("fastapi[standard]==0.115.6")
    .env({"PYTHONPATH": "/root/farm", "TRAVERSE_FARM_ALLOW_PROGRAMS": "1", "PYTHONDONTWRITEBYTECODE": "1"})
    .add_local_dir(REPO / "lightlag", "/root/farm/lightlag", ignore=_skip)
    .add_local_dir(REPO / "lightlag_traverse", "/root/farm/lightlag_traverse", ignore=_skip)
    .add_local_dir(HERE, "/root/farm/traverse_farm", ignore=_skip)
    .add_local_dir(REPO / "viewer" / "traverse", "/root/farm/viewer/traverse", ignore=_skip)
    .add_local_dir(REPO / "viewer" / "mars" / "vendor", "/root/farm/viewer/mars/vendor")
    .add_local_file(REPO / "viewer" / "build_traverse.py", "/root/farm/viewer/build_traverse.py")
    .add_local_file(REPO / "viewer" / "traverse_story.py", "/root/farm/viewer/traverse_story.py")
    .add_local_dir(RUNS / "traverse-oneshot-opus-1", "/root/farm/runs/traverse-oneshot-opus-1",
                   ignore=lambda p: Path(p).name not in ("policy.py", "run.json"))
    .add_local_dir(RUNS / "traverse-agent-opus-3", "/root/farm/runs/traverse-agent-opus-3",
                   ignore=lambda p: not (Path(p).name == "run.json" or "program" in Path(p).parts))
)
app = modal.App("lightlag-traverse-live", image=image)
cache = modal.Volume.from_name("lightlag-traverse-live-pages", create_if_missing=True)
calls = modal.Dict.from_name("lightlag-traverse-live-calls", create_if_missing=True)
LOWEST, HIGHEST = 1, 1_000_000


def _drivers():
    """The four drivers, as farm job specs; labels are what the page shows."""
    from traverse_farm.common import parse_policies

    specs = {"pilot": {"policy": "pilot"},
             "greedy": {"policy": "greedy", "label": "Textbook: A* + Kalman, greedy"}}
    specs.update(parse_policies("program:/root/farm/runs/traverse-oneshot-opus-1/policy.py,"
                                "agent:/root/farm/runs/traverse-agent-opus-3/program/farm_prepare.py"))
    return specs


@app.function(cpu=1.0, memory=1024, timeout=900, max_containers=40)
def mission(job: dict) -> dict:
    from traverse_farm.jobs import run_job
    return run_job(job)


@app.function(cpu=1.0, memory=2048, timeout=1200, max_containers=6, volumes={"/cache": cache})
def build_page(seed: int) -> str:
    """Play the four drivers on one world and save its page in the cache."""
    import sys
    import tempfile

    sys.path.insert(0, "/root/farm/viewer")
    import build_traverse
    from traverse_farm import replays

    specs = _drivers()
    jobs = [dict(spec, candidate=name, seed=seed, keep_replay=True) for name, spec in specs.items()]
    rows = []
    results = list(mission.map(jobs, order_outputs=True, return_exceptions=True))   # read it all, then pair
    for job, row in zip(jobs, results):
        if isinstance(row, BaseException):
            if job["candidate"] == "pilot":
                raise row                      # no page without the reference
            continue                           # a Claude program that crashed the harness is left off the page
        rows.append(row)
    with tempfile.TemporaryDirectory() as folder:
        replays.write(rows, specs, Path(folder))
        world = Path(folder) / "world-{}".format(seed)
        page = build_traverse.standalone(build_traverse.gather(build_traverse.run_folders(world)))
    Path("/cache/world-{}.html".format(seed)).write_text(page, encoding="utf-8")
    cache.commit()
    return "world-{}.html".format(seed)


STYLE = """<style>
body{margin:0;background:#14161B;color:#EDE9E1;font:18px/1.5 Inter,Arial,sans-serif}
main{max-width:860px;margin:0 auto;padding:48px 24px}
h1{font:700 48px/1.1 'Space Grotesk',Arial,sans-serif;margin:0 0 8px}
.eyebrow{color:#E0663A;letter-spacing:3px;font-weight:600;font-size:14px}
.ref{color:#E8B84A}.claude{color:#8CC6E8}
a{color:#8CC6E8}
form{display:flex;gap:12px;margin:24px 0}
input{flex:1;font:inherit;padding:12px 14px;border-radius:10px;border:1px solid #3A3F49;background:#1D2027;color:#EDE9E1}
button{font:inherit;font-weight:600;padding:12px 20px;border-radius:10px;border:0;background:#E8B84A;color:#1A1C21;cursor:pointer}
.worlds{display:flex;flex-wrap:wrap;gap:10px}
.worlds a{padding:8px 14px;border-radius:999px;background:#22262E;text-decoration:none}
.note{color:#9C978E;font-size:15px}
</style>"""


def _landing() -> str:
    worlds = [(2027, "campaign site 1"), (2028, "campaign site 2"), (2029, "campaign site 3"),
              (871, "level at tick 244, then lost"), (610, "two rovers lost early")]
    links = "".join('<a href="/world/{0}">{0} · {1}</a>'.format(seed, html.escape(note)) for seed, note in worlds)
    return """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Lightlag Traverse, live</title>{style}</head><body><main>
<p class="eyebrow">JUNCTION 2026 · AFTERQUERY: BREAK THE AGENT</p>
<h1>Lightlag Traverse, live on Modal</h1>
<p>A rover on 600 by 400 metres of Mars-like ground: craters, sand, rock fields, a battery charged by the sun, every command arriving three ticks late.
Pick any world. Modal drives it four times at once: the <span class="ref">reference planner</span>, a textbook controller (A*-style terrain search and a Kalman filter, greedy targets),
and two <span class="claude">autopilots Claude wrote</span>, replayed without their agents. About a minute later you watch all four.</p>
<form onsubmit="location.href='/world/'+encodeURIComponent(this.seed.value);return false;">
<input name="seed" type="number" min="{lo}" max="{hi}" placeholder="a world number, {lo} to {hi}" required>
<button type="submit">Drive it</button></form>
<div class="worlds">{links}</div>
<p class="note">The rules are the frozen Lightlag Traverse 0.1.0 rules; worlds you open are kept, so the second visit is instant.
On the page: Enter starts, Tab or a click follows a rover, S plays story mode, = speeds up.
Code and results: the team's repository, tools/traverse_farm/ and docs/traverse-farm.md.</p>
</main></body></html>""".format(style=STYLE, lo=LOWEST, hi=HIGHEST, links=links)


def _waiting(seed: int, since: float) -> str:
    return """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta http-equiv="refresh" content="5">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Driving world {seed}</title>{style}</head><body><main>
<p class="eyebrow">WORLD {seed}</p><h1>Driving it now</h1>
<p>Four rovers are crossing world {seed} on Modal, each in its own container: the <span class="ref">reference</span>, the textbook controller,
and two <span class="claude">Claude-written autopilots</span>. A mission is 420 ticks; this takes about a minute. The page reloads by itself.</p>
<p class="note">Started {ago:.0f} s ago. <a href="/">Back</a></p></main></body></html>""".format(
        seed=seed, style=STYLE, ago=max(0.0, time.time() - since))


def _forget(seed: int) -> None:
    try:
        calls.pop(seed)
    except KeyError:
        pass


def _problem(message: str) -> str:
    return """<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Lightlag Traverse</title>{style}</head>
<body><main><h1>Not this time</h1><p>{message}</p><p><a href="/">Back</a></p></main></body></html>""".format(
        style=STYLE, message=html.escape(message))


@app.function(cpu=0.5, memory=1024, volumes={"/cache": cache}, max_containers=4)
@modal.concurrent(max_inputs=20)
@modal.asgi_app()
def web():
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, RedirectResponse

    api = FastAPI(title="Lightlag Traverse, live", docs_url=None, redoc_url=None)

    @api.get("/", response_class=HTMLResponse)
    def landing():
        return _landing()

    @api.get("/world/{seed}")
    def world(seed: str):
        if not seed.isdigit() or not LOWEST <= int(seed) <= HIGHEST:
            return HTMLResponse(_problem("A world is a whole number from {} to {}.".format(LOWEST, HIGHEST)), 400)
        seed_n = int(seed)
        page = Path("/cache/world-{}.html".format(seed_n))
        cache.reload()
        if page.exists():
            return HTMLResponse(page.read_text(encoding="utf-8"))
        entry = calls.get(seed_n)
        if entry:
            call = modal.FunctionCall.from_id(entry["call"])
            try:
                call.get(timeout=0)
            except TimeoutError:
                return HTMLResponse(_waiting(seed_n, entry["since"]))
            except Exception:                  # the build failed: forget it, so a reload tries again
                _forget(seed_n)
                return HTMLResponse(_problem("Something went wrong driving world {}. Reload to try again.".format(seed_n)), 500)
            _forget(seed_n)
            return RedirectResponse("/world/{}".format(seed_n), status_code=303)
        call = build_page.spawn(seed_n)
        calls[seed_n] = {"call": call.object_id, "since": time.time()}
        return HTMLResponse(_waiting(seed_n, time.time()))

    return api


@app.local_entrypoint()
def main(seed: int = 871, out: str = ""):
    """Build one world's page on Modal and save it here (a check of everything but the web part)."""
    name = build_page.remote(seed)
    print("built", name)
    if out:
        with open(out, "wb") as handle:
            for chunk in cache.read_file(name):
                handle.write(chunk)
        print("saved", out)
