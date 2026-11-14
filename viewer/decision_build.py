#!/usr/bin/env python3
"""Build the offline, evaluator-side Lightlag decision demo from saved evidence.

    python3 viewer/decision_build.py --out viewer/decisions.html

Only the two explicitly labelled continuations are simulated locally. Recorded
model and reference replays are embedded unchanged; no model calls are made.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
MARKER = '<script id="decision-data" type="application/json">{}</script>'
PUBLIC_TOOLS = {"rules", "map", "telemetry_log", "uplink", "advance"}

CASES = [
    {
        "id": "rush-501",
        "run_name": "rush-seed501-delay3-opus-5-5",
        "tab": "01 · Energy at the horizon",
        "title": "Home is not the finish line.",
        "summary": "The rover returns home, then runs out of energy before tick 50. A post-hoc continuation that sends no more commands preserves a partial reward away from base.",
        "cutoff": 12,
        "check": "salvage-check.json",
        "decision": {
            "call": 13,
            "tick": 20,
            "title": "Call 13 adds two homeward drives",
            "action": "uplink · 3.51 m + 3.51 m · executes at ticks 24 and 25",
            "notes": [
                "Both panels share the public transcript through call 12 at tick 20. Previously queued commands still execute in the post-hoc continuation.",
                "The actual return adds 7.02 action energy. The rover reaches home at tick 25 with 11.521 battery, but dies at tick 49.",
                "Without those return drives, it finishes away from base with 6.041 battery. Its 10.5 sample points receive the 0.5 away-from-base multiplier: 5.25/12.",
            ],
            "limit": "The audit attributes its main reference-relative loss to the earlier call 11. This separate salvage check shows a feasible continuation after call 12; it does not establish an optimal action or a single cause for the whole deficit.",
        },
    },
    {
        "id": "rush-noisy-502",
        "run_name": "rush-noisy-seed502-delay3-opus-5-5",
        "tab": "02 · A queue runs dry",
        "title": "A five-tick wait empties the queue.",
        "summary": "Call 10 advances from tick 12 to 17 while queued work ends at tick 14. The next command can then execute no earlier than tick 21, narrowing the remaining sampling opportunities.",
        "decision": {
            "call": 10,
            "tick": 12,
            "title": "Call 10 waits from tick 12 to 17",
            "action": "advance(5) · queue ends at tick 14 · next possible execution at tick 21",
            "notes": [
                "At tick 12, the latest delivered packet describes tick 9. Discovery d2 arrives in a packet at tick 13, during the advance; the next tool-call decision is at tick 17.",
                "The audit's reference takeover could send a sample at tick 12 for execution at tick 16. Its value falls by 2.25 raw points across call 10; call 11 recovers 0.5.",
                "The actual run samples d2 at tick 25, after its tick-22 deadline. It finishes alive at base with 8.25/13, versus 10/13 for the independent reference run shown here.",
            ],
            "limit": "The right panel is the original KF + MPC reference playing independently from tick 0. It is not a branch at call 10. The audit's takeover calculation and this full-run comparison are separate evidence; neither is an optimality proof.",
        },
    },
    {
        "id": "rush-noisy-504",
        "run_name": "rush-noisy-seed504-delay3-opus-5-5",
        "tab": "03 · One more excursion",
        "title": "The return was already queued.",
        "summary": "At tick 25, a queued return will bring the rover home at tick 27. Call 21 adds another excursion and sample. The extra value is lost when the rover exhausts its battery at tick 47.",
        "cutoff": 20,
        "check": "stop-check.json",
        "decision": {
            "call": 21,
            "tick": 25,
            "title": "Call 21 adds an 11.1-energy excursion",
            "action": "uplink · 5 m + 3.1 m + sample · executes at ticks 29–31",
            "notes": [
                "Both panels share the public transcript through call 20 at tick 25. Their existing queue brings the rover home at tick 27.",
                "The actual run then spends 8.1 energy driving and 3 sampling d1 on time. It collects 9 sample points, but dies away from base at tick 47 and earns zero.",
                "The post-hoc continuation sends no new commands after call 20. It stays alive at base through tick 50 with 9.33 battery and 6/10 points.",
            ],
            "limit": "This is a checked post-hoc continuation under the saved simulator rules, not a new model trial or a claim that stopping is globally optimal. Earlier decisions and their positive and negative reference-relative attributions remain in the full audit.",
        },
    },
]


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def latest_visible_packet(replay, tick):
    """Return a delivered packet, never a truth state or a not-yet-arrived packet."""
    return max((packet for packet in replay.get("received_telemetry", [])
                if packet["received_tick"] <= tick),
               key=lambda packet: (packet["received_tick"], packet["tick"]), default=None)


def make_branch(replay, transcript, cutoff):
    """Replay the inclusive public-call prefix, then advance without new commands.

    This is evaluator-side reconstruction. It neither modifies the input replay
    nor supplies hidden state to the model. Pending commands are not cancelled.
    """
    from lightlag_audit.counterfactual import make_environment

    if cutoff not in {record["n"] for record in transcript}:
        raise ValueError(f"call {cutoff} is absent from the transcript")
    env = make_environment(replay)
    for record in transcript:
        if record["n"] > cutoff:
            break
        if record["tool"] not in PUBLIC_TOOLS or not record.get("ok", True):
            raise ValueError("the demo requires a successful public-tool transcript prefix")
        getattr(env, record["tool"])(**record["arguments"])
    while not env.advance(5)["episode_complete"]:
        pass
    return env.replay()


def make_track(replay, label, kind, **metadata):
    packets = replay.get("received_telemetry", [])
    indices = {id(packet): index for index, packet in enumerate(packets)}
    observations = [latest_visible_packet(replay, tick)
                    for tick in range(replay["config"]["max_ticks"] + 1)]
    return {
        "label": label,
        "kind": kind,
        "replay": replay,
        "observation_indices": [indices[id(packet)] if packet is not None else None
                                for packet in observations],
        "death_tick": next((state["tick"] for state in replay["states"] if not state["alive"]), None),
        **metadata,
    }


def build_payload(repo):
    """Load the fixed evidence selection and verify both reconstructed branches."""
    repo = Path(repo)
    cases = []
    for spec in CASES:
        name = spec["run_name"]
        run_path = Path("docs/lightlag-runs") / name
        replay_path = run_path / "artifacts/evaluator/replay.json"
        transcript_path = run_path / "artifacts/evaluator/transcript.jsonl"
        replay = read_json(repo / replay_path)
        run_result = read_json(repo / run_path / "result.json")
        agent = run_result["agent_info"]
        model = agent["model_info"]
        experiment = read_json(repo / run_path / "experiment.json")
        audit_path = Path("docs/lightlag-audits/fixed-seeds501-504") / name
        audit = read_json(repo / audit_path / "audit.json")
        if not audit["replay_matches"] or audit["infrastructure"]:
            raise ValueError(f"{name}: expected a matching audit without infrastructure findings")

        identity = {
            "model": f"{model['provider']}/{model['name']}",
            "harness": f"OpenCode {agent['version']}" if agent["name"] == "opencode" else agent["name"],
            "source_commit": experiment["source_commit"],
        }
        actual = make_track(replay, "Actual model run", "actual", source_path=str(replay_path),
                            identity=identity, description="Saved Claude Opus 5.5 run in the OpenCode harness.")
        sources = [
            {"label": "Actual replay", "href": "../" + str(replay_path)},
            {"label": "Public tool transcript", "href": "../" + str(transcript_path)},
            {"label": "Decision audit", "href": "../" + str(audit_path / "audit.md")},
            {"label": "Run identity", "href": "../" + str(run_path / "result.json")},
            {"label": "Source & task hashes", "href": "../" + str(run_path / "experiment.json")},
        ]
        if "cutoff" in spec:
            transcript = [json.loads(line) for line in (repo / transcript_path).read_text().splitlines() if line.strip()]
            branch = make_branch(replay, transcript, spec["cutoff"])
            check_path = audit_path / spec["check"]
            checked = next(item for item in read_json(repo / check_path)["counterfactuals"]
                           if item["after_call"] == spec["cutoff"])
            if (branch["result"] != checked["result"] or
                    abs(branch["states"][-1]["battery"] - checked["final_battery"]) > 1e-9):
                raise ValueError(f"{name}: reconstructed continuation differs from {spec['check']}")
            alternative = make_track(
                branch, f"Post-hoc: no new commands after call {spec['cutoff']}", "post_hoc",
                cutoff_call=spec["cutoff"],
                description=f"Same public calls through call {spec['cutoff']}; then only advance to tick 50. Queued commands still run.")
            sources.append({"label": "Checked continuation", "href": "../" + str(check_path)})
        else:
            reference_path = Path("docs/lightlag-runs") / name.replace("opus-5-5", "kf-mpc") / "artifacts/evaluator/replay.json"
            alternative = make_track(
                read_json(repo / reference_path), "Independent KF + MPC reference", "reference",
                source_path=str(reference_path),
                description="Original frozen kf_mpc policy, playing independently from tick 0. Not a branch of the model run.")
            sources.append({"label": "Independent reference replay", "href": "../" + str(reference_path)})
        cases.append({
            "id": spec["id"], "run_name": name, "tab": spec["tab"], "title": spec["title"],
            "summary": spec["summary"], "profile": replay["dynamic"]["profile"], "seed": replay["seed"],
            "decision": spec["decision"], "actual": actual, "alternative": alternative, "sources": sources,
        })
    return {"cases": cases}


def render_page(payload, template):
    if template.count(MARKER) != 1:
        raise ValueError("decision_template.html must contain exactly one data marker")
    # Escape every markup opener, including the HTML tokenizer's <!-- / <script states.
    data = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).replace("<", "\\u003c")
    return template.replace(MARKER, f'<script id="decision-data" type="application/json">{data}</script>')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    payload = build_payload(REPO)
    template = (REPO / "viewer/decision_template.html").read_text(encoding="utf-8")
    page = render_page(payload, template)
    args.out.write_text(page, encoding="utf-8")
    print(f"wrote {args.out} with {len(payload['cases'])} decision cases ({len(page.encode('utf-8')) / 1000:.0f} kB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
