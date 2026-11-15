"""Lightlag Traverse, live on Modal: pick any world, watch the reference and Claude's autopilots drive it.

    modal deploy tools/traverse_farm/live_app.py      # the web page, kept running by Modal
    modal run tools/traverse_farm/live_app.py::main --seed 871   # build one world's page here, without the web
    modal run tools/traverse_farm/live_app.py::reskin            # cached pages re-rendered with this viewer

A visitor picks a world (a seed). If its page is not cached yet, Modal plays eight drivers on it at
once, each in its own container: the reference pilot, a textbook controller (terrain graph + Kalman
filter, greedy targets: the pilot's `greedy` option) and every saved Claude program that can drive a
new world: the one-request programs of Opus, Sonnet and Haiku, and the autopilots Opus agents 1 and 3
and Sonnet agent 1 wrote during their missions, replayed without their agents. The other agent runs
drove by hand or left no program, so they can be watched only on the world they played (the
committed demo). About a minute later the page is the Traverse demo (viewer/build_traverse.py) for
that world, cached in a Modal Volume.

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
# Modal mounts the entrypoint separately from its explicitly packaged static files.
HOMEPAGE = HERE / "home_preview" if modal.is_local() else Path("/root/farm/traverse_farm/home_preview")
# The Claude programs a page shows, as farm policies: (kind, saved run, its program inside the run).
PROGRAMS = (("program", "traverse-oneshot-opus-1", "policy.py"),
            ("program", "traverse-oneshot-sonnet-1", "policy.py"),
            ("program", "traverse-oneshot-haiku-1", "policy.py"),
            ("agent", "traverse-agent-opus-1", "program/auto.py"),
            ("agent", "traverse-agent-opus-3", "program/farm_prepare.py"),
            ("agent", "traverse-agent-sonnet-1", "program/auto.py"))
PAGE = "world-{}-v3.html"        # v3: eight drivers, the short title card and story moments that hold the camera; older pages stay unread


def _skip(path) -> bool:
    path = Path(path)
    return "__pycache__" in path.parts or path.suffix == ".pyc"


def _saved_run(path) -> bool:
    """Leave out all of a saved run but who drove it (run.json) and its program."""
    path = Path(path)
    return not (path.name in ("run.json", "policy.py") or "program" in path.parts)


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
)
for _kind, _run, _entry in PROGRAMS:
    image = image.add_local_dir(RUNS / _run, "/root/farm/runs/" + _run, ignore=_saved_run)
app = modal.App("lightlag-traverse-live", image=image)
cache = modal.Volume.from_name("lightlag-traverse-live-pages", create_if_missing=True)
calls = modal.Dict.from_name("lightlag-traverse-live-calls", create_if_missing=True)
LOWEST, HIGHEST = 1, 1_000_000


def _drivers():
    """The eight drivers, as farm job specs; labels are what the page shows."""
    from traverse_farm.common import parse_policies

    specs = {"pilot": {"policy": "pilot"},
             "greedy": {"policy": "greedy", "label": "Textbook: A* + Kalman, greedy"}}
    specs.update(parse_policies(",".join("{}:/root/farm/runs/{}/{}".format(kind, run, entry)
                                         for kind, run, entry in PROGRAMS)))
    return specs


@app.function(cpu=1.0, memory=1024, timeout=900, max_containers=40)
def mission(job: dict) -> dict:
    from traverse_farm.jobs import run_job
    return run_job(job)


# Sonnet agent 1's autopilot takes about four minutes a mission (the farm's median, 237 s); the
# others take under a minute. The page is saved without it first, then again once it is done.
SLOW = ("agent:traverse-agent-sonnet-1",)


def _save(seed: int, rows: list, specs: dict) -> None:
    import sys
    import tempfile

    sys.path.insert(0, "/root/farm/viewer")
    import build_traverse
    from traverse_farm import replays

    with tempfile.TemporaryDirectory() as folder:
        replays.write(rows, specs, Path(folder))
        world = Path(folder) / "world-{}".format(seed)
        page = build_traverse.standalone(build_traverse.gather(build_traverse.run_folders(world)))
    Path("/cache/" + PAGE.format(seed)).write_text(page, encoding="utf-8")
    cache.commit()


@app.function(cpu=1.0, memory=2048, timeout=1500, max_containers=6, volumes={"/cache": cache})
def build_page(seed: int) -> str:
    """Play the eight drivers on one world and save its page in the cache: about a minute in without
    the slow driver, and again with it when it is done."""
    specs = _drivers()
    jobs = [dict(spec, candidate=name, seed=seed, keep_replay=True) for name, spec in specs.items()]
    slow = [mission.spawn(job) for job in jobs if job["candidate"] in SLOW]
    fast = [job for job in jobs if job["candidate"] not in SLOW]
    rows = []
    results = list(mission.map(fast, order_outputs=True, return_exceptions=True))   # read it all, then pair
    for job, row in zip(fast, results):
        if isinstance(row, BaseException):
            if job["candidate"] == "pilot":
                raise row                      # no page without the reference
            continue                           # a Claude program that crashed the harness is left off the page
        rows.append(row)
    _save(seed, rows, specs)
    for call in slow:
        try:
            rows.append(call.get(timeout=1200))
        except Exception:                      # a slow program that fails or runs too long stays off the page
            continue
    if slow:
        _save(seed, rows, specs)
    return PAGE.format(seed)


HEAD = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;700&family=Inter:wght@400;600&display=swap" rel="stylesheet">
<style>
:root{--bg:#121418;--panel:#1B1E25;--line:#2C313B;--text:#EDE9E1;--soft:#A9A49A;--gold:#E8B84A;--ice:#8CC6E8;--rust:#E0663A;--grey:#8E949E}
*{box-sizing:border-box}
body{margin:0;min-height:100vh;color:var(--text);font:17px/1.55 Inter,Arial,sans-serif;
 background:radial-gradient(1200px 600px at 85% -10%,#3A1E14 0%,rgba(58,30,20,0) 60%),var(--bg)}
a{color:var(--ice)}
.wrap{max-width:1100px;margin:0 auto;padding:56px 28px 40px}
.eyebrow{margin:0 0 18px;color:var(--rust);font:600 13px/1 Inter,Arial,sans-serif;letter-spacing:.24em;text-transform:uppercase}
h1{margin:0;font:700 clamp(44px,7vw,84px)/1.0 'Space Grotesk',Arial,sans-serif;letter-spacing:-.02em}
.sub{margin:14px 0 0;font:500 clamp(22px,2.6vw,30px)/1.2 'Space Grotesk',Arial,sans-serif;color:var(--gold)}
.lead{max-width:520px;margin:22px 0 0;color:#D6D1C7;font-size:18px}
.hero{display:grid;grid-template-columns:1.1fr .9fr;gap:40px;align-items:center}
.hero svg{width:100%;height:auto}
form{display:flex;gap:10px;margin:30px 0 0;max-width:520px}
form label{position:absolute;left:-9999px}
input{flex:1;min-width:0;padding:15px 18px;border-radius:12px;border:1px solid var(--line);background:var(--panel);color:var(--text);
 font:600 20px/1 'Space Grotesk',Arial,sans-serif;letter-spacing:.04em}
input:focus{outline:2px solid var(--gold);outline-offset:2px}
button{padding:15px 26px;border:0;border-radius:12px;background:var(--gold);color:#1A1C21;font:700 18px/1 'Space Grotesk',Arial,sans-serif;cursor:pointer}
button:hover{filter:brightness(1.08)}
.drivers{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:56px 0 0}
.driver{padding:18px 18px 16px;border:1px solid var(--line);border-radius:14px;background:rgba(27,30,37,.7)}
.driver b{display:flex;align-items:center;gap:10px;font:600 16px/1.2 'Space Grotesk',Arial,sans-serif}
.driver p{margin:8px 0 0;color:var(--soft);font-size:14.5px;line-height:1.45}
.dot{width:12px;height:12px;border-radius:50%;flex:none}
.gold{background:var(--gold)}.grey{background:var(--grey)}.ice{background:var(--ice)}.ring{border:3px solid var(--ice);background:transparent}
h2{margin:52px 0 16px;font:600 14px/1 Inter,Arial,sans-serif;letter-spacing:.2em;text-transform:uppercase;color:var(--soft)}
.cards{display:grid;grid-template-columns:repeat(5,1fr);gap:14px}
.card{display:block;padding:18px;border-radius:14px;background:var(--panel);border:1px solid var(--line);color:var(--text);text-decoration:none;transition:border-color .15s,transform .15s}
.card:hover{border-color:var(--gold);transform:translateY(-2px)}
.card .n{font:700 30px/1 'Space Grotesk',Arial,sans-serif}
.card .tag{margin:8px 0 0;color:var(--rust);font-size:12px;font-weight:600;letter-spacing:.14em;text-transform:uppercase}
.card p{margin:8px 0 0;color:var(--soft);font-size:14.5px;line-height:1.4}
footer{margin:56px 0 0;padding:20px 0 0;border-top:1px solid var(--line);color:var(--soft);font-size:14px;display:flex;justify-content:space-between;gap:20px;flex-wrap:wrap}
kbd{padding:1px 7px;border-radius:6px;border:1px solid var(--line);background:var(--panel);font:600 13px/1.6 Inter,Arial,sans-serif;color:var(--text)}
.lanes{max-width:620px;margin:36px 0 0;display:grid;gap:13px}
.lane{position:relative;height:2px;background:var(--line);border-radius:2px}
.lane i{position:absolute;top:-5px;left:0;width:12px;height:12px;border-radius:50%;animation:drive 3.2s ease-in-out infinite alternate}
.lane:nth-child(2) i{animation-duration:2.6s}.lane:nth-child(3) i{animation-duration:3.8s}.lane:nth-child(4) i{animation-duration:2.9s}
.lane:nth-child(5) i{animation-duration:3.5s}.lane:nth-child(6) i{animation-duration:2.4s}.lane:nth-child(7) i{animation-duration:3.7s}.lane:nth-child(8) i{animation-duration:3.0s}
@keyframes drive{from{left:0}to{left:calc(100% - 12px)}}
.small{color:var(--soft);font-size:14px;margin:28px 0 0}
@media (max-width:860px){.hero{grid-template-columns:1fr}.hero svg{max-width:420px}.drivers{grid-template-columns:1fr 1fr}.cards{grid-template-columns:1fr 1fr}}
@media (max-width:520px){.drivers,.cards{grid-template-columns:1fr}form{flex-direction:column}}
@media (prefers-reduced-motion:reduce){.lane i{animation:none;left:50%}.card{transition:none}}
</style></head><body><main class="wrap">"""

CRATER = """<svg viewBox="0 0 760 640" role="img" aria-label="Two rover tracks around craters: a gold one that returns to the lander, a blue one that stops short">
<circle cx="420" cy="250" r="150" fill="#4A2618" stroke="#6B3622" stroke-width="10"/><circle cx="420" cy="250" r="96" fill="#2A160F"/>
<circle cx="170" cy="470" r="80" fill="#4A2618" stroke="#6B3622" stroke-width="8"/><circle cx="640" cy="520" r="56" fill="#4A2618" stroke="#6B3622" stroke-width="6"/>
<path d="M120 300 C 200 120, 300 60, 420 70 S 640 150, 660 300 S 560 470, 420 450 S 200 360, 120 300" fill="none" stroke="#E8B84A" stroke-width="8" stroke-linecap="round"/>
<path d="M120 300 C 180 380, 300 560, 470 580 S 600 600, 690 420" fill="none" stroke="#8CC6E8" stroke-width="8" stroke-linecap="round" stroke-dasharray="2 18"/>
<rect x="100" y="282" width="40" height="36" rx="6" fill="#EDE9E1"/>
<path d="M674 404 L706 436 M706 404 L674 436" stroke="#8CC6E8" stroke-width="8" stroke-linecap="round"/></svg>"""

DRIVERS = [("gold", "Our planner", "Plans the whole route against the battery and the sun."),
           ("grey", "Textbook A* + Kalman", "Finds the cheapest path, then takes the best next target."),
           ("ice", "Claude, one request", "Three autopilots that Opus, Sonnet and Haiku each wrote in a single answer."),
           ("ring", "Claude, agent runs", "Three autopilots that Opus and Sonnet agents wrote during a mission.")]
LANES = ["gold", "grey", "ice", "ice", "ice", "ring", "ring", "ring"]      # one per rover on the waiting page
WORLDS = [(2027, "Judged site 1", "Two of Claude's three agent autopilots run their batteries flat."),
          (2028, "Judged site 2", "The closest race: 0.457 against our 0.508."),
          (2029, "Judged site 3", "Three Claude rovers run their batteries flat."),
          (871, "Fresh world", "Opus agent 3 holds 19 samples. Then its battery dies."),
          (610, "Fresh world", "We bring 28 samples home. Two Claude rovers die by tick 166.")]


def _page(title: str, body: str) -> str:
    return HEAD.replace("__TITLE__", html.escape(title)) + body + "</main></body></html>"


def _landing() -> str:
    return (HOMEPAGE / "index.html").read_text(encoding="utf-8")


def _waiting(seed: int, since: float) -> str:
    lanes = "".join('<div class="lane"><i class="{}"></i></div>'.format(css) for css in LANES)
    # The page asks /status in the background and reloads only once the replay is ready, so its rovers never
    # jump back to the start; without JavaScript it falls back to refreshing itself.
    body = """<p class="eyebrow">World __SEED__</p>
<h1>Rovers on<br>the ground.</h1>
<p class="lead">Eight rovers are driving world __SEED__ right now, each in its own Modal container.
A mission is 420 ticks. Seven of them finish in about a minute, and the replay opens by itself.
Sonnet agent 1's autopilot is slower: it joins the replay a few minutes later.</p>
<div class="lanes">__LANES__</div>
<p class="small" id="note">Started <span id="ago">__AGO__</span> s ago · <a href="/">Pick another world</a></p>
<script>
(function () {
  var start = Date.now() - __AGO__ * 1000, ago = document.getElementById("ago");
  setInterval(function () { ago.textContent = Math.round((Date.now() - start) / 1000); }, 1000);
  function poll() {
    if (Date.now() - start > 600000) {
      document.getElementById("note").innerHTML = 'This is taking longer than it should. <a href="">Try again</a> · <a href="/">Pick another world</a>';
      return;
    }
    fetch("/world/__SEED__/status", { cache: "no-store" })
      .then(function (r) { return r.json(); })
      .then(function (s) { if (s.state === "driving") setTimeout(poll, 2500); else location.reload(); })
      .catch(function () { setTimeout(poll, 5000); });
  }
  setTimeout(poll, 2500);
})();
</script>"""
    body = (body.replace("__SEED__", str(seed)).replace("__LANES__", lanes)
            .replace("__AGO__", "{:.0f}".format(max(0.0, time.time() - since))))
    page = _page("World {} · driving".format(seed), body)
    return page.replace('<meta charset="utf-8">', '<meta charset="utf-8"><noscript><meta http-equiv="refresh" content="6"></noscript>', 1)


def _forget(seed: int) -> None:
    try:
        calls.pop(seed)
    except KeyError:
        pass


def _reload() -> None:
    """See pages other containers saved; a reload that clashes with a read in flight is skipped."""
    try:
        cache.reload()
    except Exception:
        pass


def _problem(message: str) -> str:
    body = '<p class="eyebrow">Lightlag Traverse</p><h1>That didn\'t work.</h1><p class="lead">{}</p><p class="small"><a href="/">Back to the worlds</a></p>'
    return _page("Lightlag Traverse", body.format(html.escape(message)))


# One web container is kept running (about $0.03 an hour), so the site and every cached world still answer when
# other jobs fill the workspace's 100 containers; only new worlds then wait for room.
@app.function(cpu=0.5, memory=1024, volumes={"/cache": cache}, min_containers=1, max_containers=4)
@modal.concurrent(max_inputs=20)
@modal.asgi_app()
def web():
    from fastapi import FastAPI
    from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
    from fastapi.staticfiles import StaticFiles

    api = FastAPI(title="Lightlag Traverse, live", docs_url=None, redoc_url=None)
    home = HOMEPAGE
    api.mount("/assets", StaticFiles(directory=home / "assets"), name="home-assets")

    @api.get("/style.css", include_in_schema=False)
    def home_style():
        return FileResponse(home / "style.css", media_type="text/css")

    @api.get("/home.js", include_in_schema=False)
    def home_script():
        return FileResponse(home / "home.js", media_type="application/javascript")

    def _seed(seed: str):
        return int(seed) if seed.isdigit() and LOWEST <= int(seed) <= HIGHEST else None

    def _state(seed_n: int) -> str:
        """ready (the page is in the cache), driving, failed, or none (no build has been asked for)."""
        _reload()
        if Path("/cache/" + PAGE.format(seed_n)).exists():
            return "ready"
        entry = calls.get(seed_n)
        if not entry:
            return "none"
        try:
            modal.FunctionCall.from_id(entry["call"]).get(timeout=0)
        except TimeoutError:
            return "driving"
        except Exception:
            return "failed"
        _reload()                              # done: a build saves its page before it returns
        if Path("/cache/" + PAGE.format(seed_n)).exists():
            return "ready"
        _forget(seed_n)                        # a finished build with no page here (one for an older page version): build again
        return "none"

    @api.get("/", response_class=HTMLResponse)
    def landing():
        return _landing()

    @api.get("/world", include_in_schema=False)
    def world_form(seed: str = ""):
        seed_n = _seed(seed)
        if seed_n is None:
            return HTMLResponse(_problem("A world is a whole number from {:,} to {:,}.".format(LOWEST, HIGHEST)), 400)
        return RedirectResponse("/world/{}".format(seed_n), status_code=303)

    @api.get("/world/{seed}")
    def world(seed: str):
        seed_n = _seed(seed)
        if seed_n is None:
            return HTMLResponse(_problem("A world is a whole number from {:,} to {:,}.".format(LOWEST, HIGHEST)), 400)
        state = _state(seed_n)
        if state == "ready":
            _forget(seed_n)
            return HTMLResponse(Path("/cache/" + PAGE.format(seed_n)).read_text(encoding="utf-8"))
        if state == "failed":                  # forget it, so a reload tries again
            _forget(seed_n)
            return HTMLResponse(_problem("Driving world {} failed. Reload to try again.".format(seed_n)), 500)
        if state == "driving":
            return HTMLResponse(_waiting(seed_n, calls.get(seed_n, {}).get("since", time.time())))
        call = build_page.spawn(seed_n)
        calls[seed_n] = {"call": call.object_id, "since": time.time()}
        return HTMLResponse(_waiting(seed_n, time.time()))

    @api.get("/world/{seed}/status")
    def status(seed: str):
        """What the waiting page asks, so that it reloads only when there is something new to show."""
        seed_n = _seed(seed)
        if seed_n is None:
            return JSONResponse({"state": "bad"}, 400)
        return JSONResponse({"state": _state(seed_n)}, headers={"Cache-Control": "no-store"})

    return api


@app.local_entrypoint()
def reskin():
    """Re-render every cached page with this checkout's viewer, keeping each page's own runs: no rover is
    driven again and no container starts, so it works while other jobs fill the workspace. Run it after a
    viewer change: `modal run tools/traverse_farm/live_app.py::reskin` (then deploy, for pages built later)."""
    import base64
    import json
    import re
    import sys
    import tempfile

    sys.path.insert(0, str(REPO / "viewer"))
    import build_traverse

    suffix = PAGE.split("{}")[1]
    names = sorted(entry.path for entry in cache.listdir("/") if entry.path.endswith(suffix))
    with tempfile.TemporaryDirectory() as folder, cache.batch_upload(force=True) as batch:
        for name in names:
            page = b"".join(cache.read_file(name)).decode("utf-8")
            found = re.search(r'<script id="src-data" type="application/octet-stream">([^<]+)</script>', page)
            if not found:
                print("skipped", name, "(no data in it)")
                continue
            local = Path(folder) / Path(name).name
            local.write_text(build_traverse.standalone(json.loads(base64.b64decode(found.group(1)))), encoding="utf-8")
            batch.put_file(str(local), "/" + name)
            print("re-rendered", name)


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
