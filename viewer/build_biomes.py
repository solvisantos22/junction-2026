#!/usr/bin/env python3
"""Build the biome edition of the 3D Mars demo: the same page, with a biome to choose.

    python3 viewer/build_biomes.py                 # writes viewer/biomes-demo.html
    python3 viewer/build_biomes.py --data-out x.json --no-page   # just the data, for a look

`viewer/biomes-demo.html` is the 3D Mars demo with a row of biomes on its title screen.
"Main Mars" holds the main demo's own missions, taken from `build_mars.gather()` unchanged.
Every other biome (lightlag_dynamic/biomes) gets one mission, played here, when the page is
built, by four scripted controllers on the same seed: the controller that did best overall in
the early test, the frozen reference, a fixed plan and leg-and-wait. No model has played a
biome; the page says so.

Nothing of the main demo is edited. This script reads `viewer/mars/` (page, styles, app,
three.js) as it is and adds one extra module, `viewer/biomes/addon.js`, which draws the
biome's features and the biome row on top of the unchanged app. `viewer/mars-demo.html`
and `viewer/mars/data.json` are not written.

Needs numpy (the Manh controllers). Deterministic: the same sources give the same page.
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "viewer"))

import build_mars  # noqa: E402

from lightlag import Config  # noqa: E402
from lightlag_dynamic.biomes import BIOME_IDS, CATALOG, MAIN  # noqa: E402
from lightlag_dynamic.biomes.serve import BiomeEpisodeService  # noqa: E402
from lightlag_dynamic.missions import PROFILES  # noqa: E402

MARS = REPO / "viewer" / "mars"
ADDON = REPO / "viewer" / "biomes" / "addon.js"
SUMMARY = REPO / "docs" / "lightlag-biomes" / "trial-summary.json"

PROFILE, DELAY = "rush_noisy", 3
SEEDS = range(2000, 2040)   # the early test's seeds; a mission takes the first one that shows its biome

# Shown side by side in every biome mission. The first is the controller with the best mean
# share over all biomes in the early test (docs/lightlag-biomes.md); the rest are fixed.
BEST = "EKF_executive_slipaware_sandodo_stayalive_aimdisc_turncost_window_MPC_manh_controller_33"
PLAYERS = [
    ("best", BEST, "Best overall", "Best overall"),
    ("reference", "EKF_MPC_manh_controller_1", "Reference controller", "Reference"),
    ("fixed-plan", "blind", "Fixed plan", "Fixed plan"),
    ("leg-and-wait", "cautious", "Leg and wait", "Leg + wait"),
]
SUBS = {
    "best": "best mean share in the early test",
    "reference": "scripted Kalman filter + MPC, the frozen reference",
    "fixed-plan": "plans once, never reads telemetry",
    "leg-and-wait": "one leg, then waits to see it land",
}

# One plain sentence per biome for the title screen, filled in from the published settings.
BLURBS = {
    "main_mars": "The environment as the team runs it today: the recorded missions below, with Claude's own attempts "
                 "and the reference.",
    "relay_pass": "The link to Mars is open {open_ticks} ticks in every {period_ticks}. Commands and telemetry sent "
                  "outside a pass wait for the next one.",
    "hidden_valley": "The rover checks its own slip. A drive that slips more than {limit:.0%} stops, and every queued "
                     "command is dropped.",
    "bagnold_dunes": "Every sand patch is a dune field. Slip on a dune face grows with its slope (up to {top:.0f}°), "
                     "by an amount per degree that nobody is told.",
    "troy_crust": "Crust regions are mapped as firm ground, but {soft_rate:.0%} of their cells are soft sand "
                  "underneath. Only telemetry shows which.",
    "gale_rock_field": "Sharp rocks jolt the rover and wear its wheels. After {budget_cells} rough cells the wheels "
                       "are worn and a drive covers at most {worn_max_metres} m.",
    "meridiani_ripples": "On uniform sand visual odometry is much noisier ({sand:.0%} against {bedrock:.0%} on "
                         "bedrock), so slip is harder to measure there.",
}


def blurb(biome: str) -> str:
    settings = dict(CATALOG[biome]["settings"])
    if biome == "bagnold_dunes":
        settings["top"] = settings["slope_deg"][1]
    if biome == "meridiani_ripples":
        settings.update(settings["visual_odometry_noise_by_terrain"])
    return BLURBS[biome].format(**settings)


def _number(name: str) -> str:
    return name.rpartition("_manh_controller_")[2] if "_manh_controller_" in name else name


def play_run(run_id: str, controller: str, label: str, short: str, biome: str, seed: int) -> Dict[str, Any]:
    """One scripted episode through the same service the MCP server uses, so every call is recorded."""
    from lightlag_dynamic.manh_controllers import controllers as zoo
    service = BiomeEpisodeService(seed=seed, biome=biome, profile=PROFILE,
                                  config=Config(delay_ticks=DELAY, max_ticks=PROFILES[PROFILE][4]))
    try:
        zoo.REGISTRY[controller]["play"](service, None)
    except ValueError:
        pass  # a rejected call ends that controller's turn; it is in the transcript
    result = service.finish()
    calls = [{"kind": "mcp", "tool": r["tool"], "arguments": r["arguments"], "tick": r["tick_before"],
              "tick_after": r["tick_after"], "ok": r["ok"], "error": r.get("error"),
              "summary": r.get("summary") or {}, "say": ""} for r in service.transcript()]
    number = _number(controller)
    return {
        "id": run_id, "kind": "scripted", "controller": controller,
        "label": f"{label} · controller {number}" if run_id == "best" else label,
        "short": f"Best · {number}" if run_id == "best" else short,
        "sub": SUBS[run_id].format(n=number),
        "source": f"played at build time: {biome}, {PROFILE}, seed {seed}, delay {DELAY}",
        "replay": service._env.replay(), "calls": calls, "report": "",
        "reward": result["raw_score"] / result["max_available_value"], "cost_usd": None,
    }


def shows_biome(biome: str, runs: List[Dict[str, Any]]) -> bool:
    """Whether the biome's own mechanic happens in this mission, so the page has something to show."""
    reference = next(r for r in runs if r["id"] == "reference")["replay"]
    info, delay = reference["biome"], reference["config"]["delay_ticks"]

    def events(replay, kind):
        return [e for s in replay["states"] for e in s["events"] if e["type"] == kind]

    def cell(state):
        return [int(state["position"][0] // 1.0), int(state["position"][1] // 1.0)]

    if biome == "relay_pass":
        held_up = any(c.get("transmit_tick", c["sent_tick"]) > c["sent_tick"] for c in reference["commands"])
        held_down = any(p["received_tick"] > p["tick"] + delay for p in reference["received_telemetry"][1:])
        return held_up and held_down
    if biome == "hidden_valley":
        return any(e.get("reason") == "slip_limit" for r in runs for e in events(r["replay"], "safety_stop"))
    if biome == "troy_crust":
        return any(cell(s) in info["soft_cells"] for s in reference["states"])
    if biome == "gale_rock_field":
        return any(events(r["replay"], "wheels_worn") for r in runs)
    if biome == "bagnold_dunes":
        steep = [f for f in info["dune_faces"] if f["slope_deg"] >= 10.0]
        return any(f["x1"] <= s["position"][0] <= f["x2"] and f["y1"] <= s["position"][1] <= f["y2"]
                   for s in reference["states"] for f in steep)
    if biome == "meridiani_ripples":
        return any(s["terrain"] == "sand" and s["wheel_odometry"] > 0 for s in reference["states"])
    raise ValueError(biome)


def mission_definition(replay: Dict[str, Any]) -> Dict[str, Any]:
    """What makes two replays the same biome mission: everything fixed by the seed, nothing a run did."""
    dynamic = dict(replay["dynamic"])
    dynamic.pop("sensing", None)
    dynamic.pop("roughness", None)
    biome = {k: v for k, v in replay["biome"].items() if k not in ("wheel_wear", "drives_limited")}
    return {"seed": replay["seed"], "world": replay["world"], "config": replay["config"],
            "dynamic": dynamic, "biome": biome}


def biome_mission(biome: str) -> Dict[str, Any]:
    """The first early-test seed on which the biome's mechanic shows; seed 2000 if none does."""
    chosen = None
    for seed in SEEDS:
        runs = [play_run(run_id, name, label, short, biome, seed) for run_id, name, label, short in PLAYERS]
        if chosen is None:
            chosen = (seed, runs)
        if shows_biome(biome, runs):
            chosen = (seed, runs)
            break
    seed, runs = chosen
    entry = CATALOG[biome]
    first = runs[0]["replay"]
    for run in runs:
        if mission_definition(run["replay"]) != mission_definition(first):
            raise SystemExit(f"{biome}: the four runs are not the same mission")
    return {
        "id": biome, "name": entry["name"], "featured": "best", "biome": biome,
        "brief": f"{entry['decision'][0].upper()}{entry['decision'][1:]}. Four scripted controllers on the same "
                 f"map; no model has played this biome.",
        "seed": seed, "profile": PROFILE, "delay": DELAY, "ticks": first["config"]["max_ticks"], "runs": runs,
    }


def early_test() -> Dict[str, Any]:
    """Per biome, what the early test found (docs/lightlag-biomes/trial-summary.json), if it is there."""
    if not SUMMARY.exists():
        return {}
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    out = {}
    for biome, scores in summary["scores"].items():
        best = summary["best"][biome]
        out[biome] = {
            "best": _number(best["controller"]), "best_share": best["share"], "best_home": best["home"],
            "shown_best_share": (scores.get(BEST) or {}).get("share"),
            "reference_share": (scores.get("EKF_MPC_manh_controller_1") or {}).get("share"),
            "fixed_plan_share": (scores.get("blind") or {}).get("share"),
            "leg_and_wait_share": (scores.get("cautious") or {}).get("share"),
        }
    meta = summary.get("meta", {})
    return {"by_biome": out, "seeds": meta.get("seeds"), "profiles": meta.get("profiles"), "delays": meta.get("delays"),
            "best_overall": _number(next(iter(summary["overall"]), BEST))}


def gather() -> Dict[str, Any]:
    main = build_mars.gather()
    missions = [dict(mission, biome=MAIN) for mission in main["missions"]]
    missions += [biome_mission(biome) for biome in BIOME_IDS if biome != MAIN]
    biomes = [{"id": biome, "name": CATALOG[biome]["name"], "kind": CATALOG[biome]["kind"],
               "modelled_on": CATALOG[biome]["modelled_on"], "rule": CATALOG[biome]["rule"],
               "decision": CATALOG[biome]["decision"], "blurb": blurb(biome)} for biome in BIOME_IDS]
    return {"title": main["title"], "missions": missions, "biomes": biomes, "early_test": early_test(),
            "shown_best": _number(BEST)}


def standalone(data: Dict[str, Any]) -> str:
    """The main demo's page, styles, app and three.js as they are, plus the data and the add-on."""
    def b64(path: Path) -> str:
        return base64.b64encode(path.read_bytes()).decode("ascii")

    page = (MARS / "index.html").read_text(encoding="utf-8")
    start, end = page.index("<!--DEV-->"), page.index("<!--/DEV-->") + len("<!--/DEV-->")
    payload = base64.b64encode(json.dumps(data, separators=(",", ":")).encode("utf-8")).decode("ascii")
    inline = """<style>{css}</style>
<script id="src-core" type="application/octet-stream">{core}</script>
<script id="src-three" type="application/octet-stream">{three}</script>
<script id="src-app" type="application/octet-stream">{app}</script>
<script id="src-biomes" type="application/octet-stream">{addon}</script>
<script id="src-data" type="application/octet-stream">{data}</script>
<script>
(async () => {{
  const text = id => new TextDecoder().decode(Uint8Array.from(atob(document.getElementById(id).textContent), c => c.charCodeAt(0)));
  const url = source => URL.createObjectURL(new Blob([source], {{ type: "text/javascript" }}));
  const core = url(text("src-core"));
  const three = url(text("src-three").split("'./three.core.js'").join(JSON.stringify(core)));
  window.LIGHTLAG_DATA = JSON.parse(text("src-data"));
  await import(url(text("src-app").split("'three'").join(JSON.stringify(three))));
  await import(url(text("src-biomes").split("'three'").join(JSON.stringify(three))));
}})().catch(error => {{ document.body.insertAdjacentHTML("beforeend", "<pre style='color:#f66;padding:20px'>" + error + "</pre>"); throw error; }});
</script>""".format(
        css=(MARS / "style.css").read_text(encoding="utf-8"),
        core=b64(MARS / "vendor" / "three.core.js"),
        three=b64(MARS / "vendor" / "three.module.js"),
        app=b64(MARS / "app.js"),
        addon=b64(ADDON),
        data=payload,
    )
    return page[:start] + inline + page[end:]


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=REPO / "viewer" / "biomes-demo.html")
    parser.add_argument("--data-out", type=Path, help="also write the data as JSON here")
    parser.add_argument("--no-page", action="store_true", help="do not write the page")
    args = parser.parse_args(argv)
    data = gather()
    for mission in data["missions"]:
        print("  {:<12} {:<24} ({} seed {}, delay {}, {} ticks)".format(
            mission["biome"], mission["name"], mission["profile"], mission["seed"], mission["delay"], mission["ticks"]))
        for run in mission["runs"]:
            result = run["replay"]["result"]
            print("    {:<22} reward {:.2f}  calls {:>3}  alive {!s:<5} at base {}".format(
                run["short"], run["reward"], len(run["calls"]), result["alive"], result["at_base"]))
    if args.data_out:
        args.data_out.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
        print("wrote {}".format(args.data_out))
    if not args.no_page:
        page = standalone(data)
        args.out.write_text(page, encoding="utf-8")
        print("wrote {} ({:.1f} MB)".format(args.out.relative_to(REPO) if args.out.is_relative_to(REPO) else args.out,
                                            len(page) / 1e6))
    return 0


if __name__ == "__main__":
    sys.exit(main())
