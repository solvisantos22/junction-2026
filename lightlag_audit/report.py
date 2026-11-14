"""Turn one rebuilt run into an audit: a JSON record and a Markdown page a judge can read.

Points are reported both in the simulator's raw score and in reward units (raw score divided
by the episode's max_available_value, which is what verifier/reward.txt holds).
"""

import json

from .counterfactual import make_environment, rebuild
from .mistakes import (EPS, INFRASTRUCTURE, OUTCOME, REASONING, TAGS, Timeline, decision_findings,
                       discovery_findings, infrastructure_findings, outcome_findings)

WORDS_LIMIT = 600


def audit_run(run, reference=None):
    built = rebuild(run.replay, run.transcript, reference)
    env = make_environment(run.replay)
    rules, public_map = env.rules(), env.map()
    timeline = Timeline(run.replay)
    result = run.replay.get("result") or run.evaluator_result
    maximum = float(result.get("max_available_value")
                    or sum(float(t.get("value", 0)) for t in public_map.get("targets", [])) or 1.0)

    decisions, sampled_before = [], set()
    for point in built.decisions:
        findings = decision_findings(point, built, timeline, rules, public_map, sampled_before)
        for ack in point.acks_sent:
            for effect in timeline.effects.get(ack["command_id"], []):
                if effect["type"] == "sample_taken":
                    sampled_before.add(effect["target_id"])
        call = run.agent_call_for(point.n)
        decisions.append({
            "n": point.n, "tool": point.tool, "arguments": point.arguments, "ok": point.ok, "error": point.error,
            "tick": point.tick, "tick_after": point.tick_after,
            "value_before": point.value_before, "value_after": point.value_after,
            "points_lost": point.points_lost, "reward_lost": point.points_lost / maximum,
            "acks": point.acks_sent, "reference_instead": point.reference_instead,
            "agent_step": call.step_id if call else None,
            "agent_words": (_tail(call.message) or None) if call else None,
            "findings": [f.to_dict() for f in findings],
        })

    unattached = []
    by_n = {d["n"]: d for d in decisions}
    for finding in discovery_findings(built, timeline, result):
        target = by_n.get(finding.n)
        (target["findings"] if target else unattached).append(finding.to_dict())

    outcome = [f.to_dict() for f in outcome_findings(built, result, public_map, timeline)]
    infrastructure = [f.to_dict() for f in infrastructure_findings(run, built)]
    gap = built.reference_from_start - built.agent_score
    decision_total = sum(d["points_lost"] for d in decisions)
    costly = sorted((d for d in decisions if d["points_lost"] > EPS), key=lambda d: -d["points_lost"])
    main = [dict(d, kind="decision") for d in costly]
    if built.stop_loss > EPS:
        stop = next(f for f in outcome if f["tag"] == "STOPPED_EARLY")
        main.append({"kind": "stop", "n": None, "tool": "stop", "tick": built.stop_tick,
                     "points_lost": built.stop_loss, "reward_lost": built.stop_loss / maximum,
                     "findings": [stop], "reference_instead": built.stop_plan, "agent_words": _last_words(run)})
    main.sort(key=lambda d: -d["points_lost"])
    if gap <= EPS:
        # The agent matched the reference overall. Any decision that "lost" points against the
        # reference's continuation was won back later, so it shows where the reference is weak
        # from states it would not have chosen, not an agent mistake.
        main = []
        for decision in decisions:
            decision["findings"] = [f for f in decision["findings"]
                                    if f["tag"] not in ("PLAN_WORSE_THAN_REFERENCE", "COSTLY_WAIT")]

    dynamic = run.replay.get("dynamic") or {}
    return {
        "run": run.name, "model": run.model, "reference": built.reference,
        "seed": run.replay.get("seed"), "delay_ticks": rules.get("delay_ticks"),
        "max_ticks": rules.get("max_ticks"), "profile": dynamic.get("profile", "core"),
        "score": {
            "max_available_value": maximum,
            "agent_raw": built.agent_score, "agent_reward": built.agent_score / maximum,
            "reference_raw": built.reference_from_start, "reference_reward": built.reference_from_start / maximum,
            "gap_raw": gap, "gap_reward": gap / maximum, "reward_txt": run.reward,
        },
        "decomposition": {"decisions_raw": decision_total, "stop_loss_raw": built.stop_loss,
                          "adds_up": abs(decision_total + built.stop_loss - gap) < 1e-6},
        "replay_matches": built.replay_matches, "stop_tick": built.stop_tick,
        "main_mistakes": main[:3],
        "decisions": decisions,
        "run_findings": unattached,
        "outcome": outcome,
        "infrastructure": infrastructure,
        "counts": _counts(decisions, unattached, outcome, infrastructure),
        "superlog": superlog_labels(run.replay),
    }


SUPERLOG_FIELDS = ("labels", "share", "samples_taken", "samples_failed", "safety_stops", "late", "battery_end",
                   "home_dist")


def superlog_labels(replay):
    """Episode labels from lightlag_dynamic/manh_controllers/superlog.py, run on the evaluator's replay.

    Optional: superlog needs numpy. Without a controller log, a failed sample is labelled
    MISS_UNLOGGED (superlog only knows the confidence of Manh's own controllers)."""
    try:
        from lightlag_dynamic.manh_controllers.superlog import summarize
        summary = summarize(replay, None, None)
    except Exception as failure:  # an optional add-on: never let it stop the audit
        return {"available": False, "reason": f"{type(failure).__name__}: {failure}"}
    return {"available": True, **{key: summary.get(key) for key in SUPERLOG_FIELDS}}


def _tail(text, limit=WORDS_LIMIT):
    text = " ".join((text or "").split())
    return text if len(text) <= limit else "…" + text[-limit:]


def _last_words(run):
    return _tail(run.agent_calls[-1].message) if run.agent_calls else None


def _counts(decisions, unattached, outcome, infrastructure):
    counts = {REASONING: {}, INFRASTRUCTURE: {}, OUTCOME: {}}
    every = [f for d in decisions for f in d["findings"]] + unattached + outcome + infrastructure
    for finding in every:
        bucket = counts[finding["kind"]]
        bucket[finding["tag"]] = bucket.get(finding["tag"], 0) + 1
    return counts


# ---- Markdown -------------------------------------------------------------------------------
def _command_text(command):
    action = command.get("action")
    if action == "drive":
        return f"drive {round(float(command.get('heading_deg', 0)), 1):g}° {round(float(command.get('metres', 0)), 2):g} m"
    return action or "?"


def _call_text(decision):
    if decision["tool"] == "uplink":
        return "uplink [" + ", ".join(_command_text(c) for c in decision["arguments"].get("commands", [])) + "]"
    if decision["tool"] == "advance":
        return f"advance {decision['arguments'].get('ticks', 1)}"
    return decision["tool"]


def _plan_text(plan):
    if not plan:
        return "no plan recorded"
    parts = []
    first = plan.get("first_uplink")
    if first:
        parts.append(f"at tick {first['tick']} uplink [" + ", ".join(_command_text(c) for c in first["commands"]) + "]")
    else:
        parts.append("send nothing more")
    if plan.get("samples"):
        parts.append("then sample " + ", ".join(
            f"{s['target_id']} (tick {s['tick']}{'' if s.get('on_time', True) else ', late'})" for s in plan["samples"]))
    end = "home" if plan.get("at_base") else ("alive, away from base" if plan.get("alive") else "dead")
    parts.append(f"finish {end}, score {plan.get('raw_score', 0):g}")
    return "; ".join(parts)


def _pointer_text(evidence):
    """The 'where was the information' line for one finding."""
    bits = []
    for key in ("packet", "packet_planned_from"):
        packet = evidence.get(key)
        if packet:
            text = f"telemetry packet for tick {packet['state_tick']}, delivered at tick {packet['received_tick']}"
            if packet.get("position"):
                text += f" (position {packet['position']}, battery {packet.get('battery')})"
            bits.append(text)
            break
    if evidence.get("in_transit"):
        bits.append("acknowledgements for commands still in transit, execute ticks " +
                    ", ".join(str(a["execute_ticks"][0]) for a in evidence["in_transit"]))
    if evidence.get("earlier_uplink"):
        bits.append(f"the earlier uplink's acknowledgement, execute ticks {evidence['earlier_uplink']['execute_ticks']}")
    if evidence.get("ack"):
        bits.append(f"acknowledgement of call {evidence['ack']['call']}: execute tick {evidence['ack']['execute_ticks']}")
    if evidence.get("slip_seen_at"):
        slip = evidence["slip_seen_at"]
        bits.append(f"packet for tick {slip['state_tick']} (delivered tick {slip['received_tick']}): wheel "
                    f"{slip['wheel_odometry']} m vs visual {slip['visual_odometry']} m on {slip['terrain']}")
    if evidence.get("target"):
        target = evidence["target"]
        bits.append(f"map target {target.get('id')} (deadline tick {target.get('deadline_tick')}, "
                    f"value {target.get('value')})")
    if evidence.get("hazard"):
        bits.append(f"map hazard {evidence['hazard']}")
    if evidence.get("rule"):
        bits.append(f"rules(): {evidence['rule']}")
    if evidence.get("map_item"):
        bits.append(f"map(): {evidence['map_item']}")
    return "; ".join(bits)


def to_markdown(audit):
    score = audit["score"]
    lines = [f"# Decision audit: {audit['run']}", ""]
    lines.append(f"- Model: {audit['model'] or 'scripted (no agent trajectory)'}")
    lines.append(f"- Profile `{audit['profile']}`, seed {audit['seed']}, delay {audit['delay_ticks']} ticks, "
                 f"horizon {audit['max_ticks']}")
    lines.append(f"- Agent: **{score['agent_raw']:g}** of {score['max_available_value']:g} "
                 f"(reward {score['agent_reward']:.3f}"
                 + (f", reward.txt {score['reward_txt']:.3f}" if score["reward_txt"] is not None else "") + ")")
    lines.append(f"- Reference (`{audit['reference']}`) from the start: **{score['reference_raw']:g}** "
                 f"(reward {score['reference_reward']:.3f})")
    lines.append(f"- Gap: {score['gap_raw']:g} points = {score['gap_reward']:.3f} reward. Decisions account for "
                 f"{audit['decomposition']['decisions_raw']:g}, stopping early for "
                 f"{audit['decomposition']['stop_loss_raw']:g}"
                 + ("" if audit["decomposition"]["adds_up"] else " (DOES NOT ADD UP: check the rebuild)") + ".")
    lines.append(f"- Rebuild reproduces the saved run tick for tick: **{'yes' if audit['replay_matches'] else 'NO'}**")
    lines.append("")

    lines.append("## Main mistakes")
    lines.append("")
    if not audit["main_mistakes"]:
        if score["gap_raw"] <= EPS and any(d["points_lost"] > EPS for d in audit["decisions"]):
            lines.append("None: the agent matched the reference's score. Some decisions below lost points against "
                         "the reference's continuation and later decisions won them back; that measures the "
                         "reference from states it would not have chosen, not an agent mistake.")
        else:
            lines.append("None: no decision scored less than the reference would have from the same moment.")
        lines.append("")
    for rank, item in enumerate(audit["main_mistakes"], 1):
        where = (f"call {item['n']}, {_call_text(item)} at tick {item['tick']}" if item["kind"] == "decision"
                 else f"stopped at tick {item['tick']}")
        lines.append(f"### {rank}. {where}: −{item['points_lost']:g} points (−{item['reward_lost']:.3f} reward)")
        lines.append("")
        for finding in item["findings"]:
            if finding["kind"] == OUTCOME:
                continue
            lines.append(f"- **{finding['tag']}**: {finding['summary']}. {TAGS.get(finding['tag'], '')}")
            pointer = _pointer_text(finding["evidence"])
            if pointer:
                lines.append(f"  - Information the agent had: {pointer}")
        lines.append(f"- Reference instead: {_plan_text(item.get('reference_instead'))}")
        if item.get("agent_words"):
            lines.append(f"- Agent's own words: > {item['agent_words']}")
        elif item.get("agent_step") is not None:
            lines.append(f"- Agent's own words: none recorded (trajectory step {item['agent_step']} holds the "
                         "tool call but no message or reasoning text)")
        lines.append("")

    gains = [d for d in audit["decisions"] if d["points_lost"] < -EPS]
    if gains:
        lines.append("## Where the agent did better than the reference")
        lines.append("")
        for d in gains:
            lines.append(f"- call {d['n']}, {_call_text(d)} at tick {d['tick']}: +{-d['points_lost']:g} points "
                         f"(the reference taking over before this call would have scored {d['value_before']:g}, "
                         f"after it {d['value_after']:g})")
        lines.append("")

    lines.append("## Infrastructure (kept apart from reasoning)")
    lines.append("")
    if audit["infrastructure"]:
        for finding in audit["infrastructure"]:
            lines.append(f"- **{finding['tag']}**: {finding['summary']}")
    else:
        lines.append("None found: every agent call reached the simulator, Harbor recorded no exception, the "
                     "rebuild matches the run and reward.txt matches the evaluator.")
    lines.append("")

    other = [f for d in audit["decisions"] if d["points_lost"] <= EPS for f in d["findings"]] + audit["run_findings"]
    if other:
        lines.append("## Other reasoning findings (no points lost against the reference)")
        lines.append("")
        for finding in other:
            lines.append(f"- call {finding['n']}: **{finding['tag']}**: {finding['summary']}")
        lines.append("")

    lines.append("## Episode outcome")
    lines.append("")
    for finding in audit["outcome"]:
        lines.append(f"- **{finding['tag']}**: {finding['summary']}")
    if not audit["outcome"]:
        lines.append("- nothing notable")
    superlog = audit.get("superlog") or {}
    if superlog.get("available"):
        lines.append(f"- superlog labels (`lightlag_dynamic/manh_controllers/superlog.py`): "
                     f"{', '.join(superlog['labels']) or 'none'}; share {superlog['share']:.3f}, "
                     f"{superlog['samples_taken']} samples taken, {superlog['samples_failed']} failed, "
                     f"{superlog['late']} late, battery at the end {superlog['battery_end']:.1f}")
    elif superlog:
        lines.append(f"- superlog labels unavailable here ({superlog.get('reason')})")
    lines.append("")

    lines.append("## Every decision")
    lines.append("")
    lines.append("| call | tick | what the agent did | reference before | reference after | points lost | tags |")
    lines.append("|---:|---|---|---:|---:|---:|---|")
    for d in audit["decisions"]:
        tags = ", ".join(sorted({f["tag"] for f in d["findings"]})) or ""
        lines.append(f"| {d['n']} | {d['tick']}→{d['tick_after']} | {_call_text(d)}"
                     + ("" if d["ok"] else " (rejected)") +
                     f" | {d['value_before']:g} | {d['value_after']:g} | {d['points_lost']:g} | {tags} |")
    lines.append("")
    lines.append("*Reference before/after*: the score if the reference took over just before or just after this "
                 "call, knowing only what the agent knew then (delivered telemetry, rules, map, its own "
                 "acknowledgements). *Points lost* = before − after; the column plus the stop loss adds up to the gap.")
    lines.append("")
    return "\n".join(lines)


def write(audit, folder):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "audit.json").write_text(json.dumps(audit, indent=2, sort_keys=True, default=str) + "\n")
    (folder / "audit.md").write_text(to_markdown(audit))
