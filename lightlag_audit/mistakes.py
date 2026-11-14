"""Name what went wrong at each decision, and point to where the needed information was.

Every finding is one of three kinds, and the report never mixes them:

  reasoning       the tools worked and the information was available; the agent's choice
                  cost points (or broke a published rule)
  infrastructure  something outside the agent's reasoning: a call that never reached the
                  simulator, a Harbor exception, missing artifacts, a rebuild that does not
                  match the run, a reward file that disagrees with the evaluator
  outcome         how the episode ended (names shared with manh_controllers/superlog.py)

Evidence is always a pointer the agent could have followed: a telemetry packet (its state
tick and the tick it arrived), an acknowledgement (the call number and the execute ticks it
returned), a published rule key, or a map item. The simulator's hidden truth (true slip,
positions not yet reported) is only used to say what happened, never as the thing the agent
should have known.
"""

from dataclasses import asdict, dataclass, field
import math
from typing import Any, Dict, List, Optional

EPS = 1e-9

REASONING, INFRASTRUCTURE, OUTCOME = "reasoning", "infrastructure", "outcome"

# One plain sentence per tag; the report and docs/lightlag-audit.md use these.
TAGS = {
    # reasoning, attached to one decision
    "STALE_AIM": "Aimed from the last delivered position, ignoring drives still in transit.",
    "REPEATED_IN_TRANSIT": "Re-sent commands that were already queued but not yet visible in telemetry.",
    "SAMPLE_MISSED": "A sample command found no unsampled target in range (or not enough battery).",
    "SAFETY_STOP": "A drive hit a hazard or the map edge; the queue behind it was cleared.",
    "BATTERY_DEPLETED": "The battery ran out while executing this uplink's commands.",
    "LATE_SAMPLE": "A target was sampled after its published deadline, for reduced value.",
    "WAITED_WITH_EMPTY_QUEUE": "Advanced the clock with nothing queued, so the rover stood idle.",
    "QUEUE_RAN_DRY": "Advanced instead of queuing the next leg; the queue emptied before new commands could arrive.",
    "DISCOVERY_MISSED": "A discovered target arrived in telemetry and was never collected (or only late).",
    "REJECTED_BY_RULES": "The call broke a published rule and was rejected; it changed nothing.",
    "PLAN_WORSE_THAN_REFERENCE": "Legal and on time, but the reference's plan from the same information scored more.",
    "COSTLY_WAIT": "Waiting here cost points: the reference would have acted at this tick.",
    # infrastructure
    "INFRA_CALL_NOT_RECORDED": "The agent called a tool but the simulator never recorded the call.",
    "INFRA_TOOL_ERROR": "A read-only tool (rules, map, telemetry_log) returned an error.",
    "INFRA_HARBOR_EXCEPTION": "Harbor recorded an exception for this trial.",
    "INFRA_NO_TRANSCRIPT": "The simulator's transcript is missing, so decisions cannot be rebuilt.",
    "INFRA_REBUILD_MISMATCH": "Replaying the transcript does not reproduce the saved run; points lost are unreliable.",
    "INFRA_REWARD_MISMATCH": "verifier/reward.txt disagrees with the evaluator's raw score / maximum.",
    # outcome
    "PERFECT": "Matched or beat the reference from the start.",
    "DEAD": "The rover died; the score is 0.",
    "NOT_HOME": "Alive but not at base at the horizon; samples count half.",
    "NOTHING_SAMPLED": "No sample was collected.",
    "TARGETS_LEFT": "Some targets were never sampled.",
    "STOPPED_EARLY": "The agent stopped calling tools with time left that the reference would have used.",
}


@dataclass
class Finding:
    tag: str
    kind: str
    summary: str
    n: Optional[int] = None                   # transcript call number, when tied to one call
    evidence: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)


# ---- what actually happened, indexed by command ---------------------------------------------
class Timeline:
    def __init__(self, replay):
        self.states = {state["tick"]: state for state in replay.get("states", [])}
        self.executed = {}            # command_id -> tick it executed
        self.effects = {}             # command_id -> events it caused (sample, stop, battery)
        self.discoveries = []         # (state tick, received tick, target)
        for state in replay.get("states", []):
            ids = [e["command_id"] for e in state["events"] if e["type"] == "command_executed"]
            caused = [e for e in state["events"]
                      if e["type"] in ("sample_taken", "sample_failed", "safety_stop", "battery_depleted")]
            for command_id in ids:
                self.executed[command_id] = state["tick"]
                self.effects[command_id] = caused
            for event in state["events"]:
                if event["type"] == "target_discovered":
                    self.discoveries.append((state["tick"], state.get("received_tick"), event["target"]))

    def state(self, tick):
        return self.states.get(tick)


def packet_ref(packet):
    """A short pointer to one telemetry packet, as the agent saw it."""
    if not packet:
        return None
    ref = {"state_tick": packet.get("tick"), "received_tick": packet.get("received_tick"),
           "position": [round(v, 2) for v in packet.get("position", [])],
           "battery": None if packet.get("battery") is None else round(packet["battery"], 1)}
    events = [e for e in packet.get("events", []) if e.get("type") != "command_executed"]
    if events:
        ref["events"] = events
    return ref


def ack_ref(n, acks):
    return {"call": n, "command_ids": [a["command_id"] for a in acks],
            "execute_ticks": [a["execute_tick"] for a in acks]}


def _displacement(commands):
    dx = dy = 0.0
    for command in commands:
        if command.get("action") == "drive":
            heading = math.radians(float(command.get("heading_deg", 0.0)))
            metres = float(command.get("metres", 0.0))
            dx += metres * math.cos(heading)
            dy += metres * math.sin(heading)
    return dx, dy


def _same_commands(first, second):
    def key(c):
        return (c.get("action"), round(float(c.get("heading_deg", 0) or 0), 1), round(float(c.get("metres", 0) or 0), 2))
    return [key(c) for c in first] == [key(c) for c in second]


def _targets(public_map, timeline, known_at=None):
    """Map targets plus discoveries; with known_at, only discoveries delivered by that tick."""
    targets = {t["id"]: dict(t) for t in public_map.get("targets", [])}
    for _, received_tick, target in timeline.discoveries:
        if known_at is None or (received_tick is not None and received_tick <= known_at):
            targets.setdefault(target["id"], dict(target))
    return targets


def _nearest(position, targets):
    best = None
    for target in targets.values():
        distance = math.dist(position, (target["x"], target["y"]))
        if best is None or distance < best[0]:
            best = (distance, target)
    return best


def _hazard_near(position, public_map, margin=1.0):
    x, y = position
    for rect in public_map.get("hazards", []):
        if rect["x1"] - margin <= x <= rect["x2"] + margin and rect["y1"] - margin <= y <= rect["y2"] + margin:
            return rect
    return None


# ---- per decision ---------------------------------------------------------------------------
def decision_findings(point, rebuild, timeline, rules, public_map, sampled_before):
    """Findings for one uplink or advance. sampled_before: target ids sampled before this call."""
    findings = []
    lost = point.points_lost
    if not point.ok:
        findings.append(Finding("REJECTED_BY_RULES", REASONING,
                                f"call {point.n} ({point.tool}) was rejected: {point.error}", point.n,
                                {"error": point.error, "rule": _rule_for_error(point.error)}))
        return findings
    last_packet = point.log_before[-1] if point.log_before else None
    visible_tick = last_packet["tick"] if last_packet else 0
    in_transit = [a for a in point.acks_before if a["execute_tick"] > visible_tick]
    if point.tool == "uplink":
        findings += _uplink_findings(point, timeline, rules, public_map, last_packet, in_transit, sampled_before)
    else:
        findings += _advance_findings(point, rules, last_packet)
    if lost > EPS and not any(f.kind == REASONING for f in findings):
        tag = "PLAN_WORSE_THAN_REFERENCE" if point.tool == "uplink" else "COSTLY_WAIT"
        plan = point.reference_instead or {}
        findings.append(Finding(tag, REASONING,
                                f"from the same information the reference scored {point.value_before:g} "
                                f"instead of {point.value_after:g}", point.n,
                                {"packet": packet_ref(last_packet), "reference_plan": plan}))
    return findings


def _rule_for_error(error):
    text = (error or "").lower()
    for key in ("max_commands_per_uplink", "max_metres_per_drive", "max_advance_ticks", "supported_actions"):
        words = key.replace("max_", "").replace("_", " ")
        if words in text or key in text:
            return key
    if "command" in text and ("5" in text or "many" in text):
        return "max_commands_per_uplink"
    if "metre" in text:
        return "max_metres_per_drive"
    if "tick" in text:
        return "max_advance_ticks"
    return None


def _uplink_findings(point, timeline, rules, public_map, last_packet, in_transit, sampled_before):
    findings = []
    commands = point.arguments.get("commands", []) or []
    radius = float(rules.get("target_radius", 0.75))
    targets = _targets(public_map, timeline)
    known = _targets(public_map, timeline, known_at=point.tick)
    has_sample = any(c.get("action") == "sample" for c in commands)

    # Did the agent aim from the stale position? Compare nominal endpoints with and without
    # the drives that were queued but not yet visible in telemetry.
    stale = None
    transit_commands = [a["command"] for a in in_transit]
    transit_shift = _displacement(transit_commands)
    if has_sample and last_packet and math.hypot(*transit_shift) > radius:
        dx, dy = _displacement(commands[:max(i for i, c in enumerate(commands) if c.get("action") == "sample") + 1])
        px, py = last_packet["position"]
        stale_end = (px + dx, py + dy)
        aware_end = (px + transit_shift[0] + dx, py + transit_shift[1] + dy)
        slack = radius + 0.15 * sum(float(c.get("metres", 0) or 0) for c in commands if c.get("action") == "drive") + 0.5
        near_stale = _nearest(stale_end, known)
        if near_stale and near_stale[0] <= slack and math.dist(aware_end, (near_stale[1]["x"], near_stale[1]["y"])) > slack:
            stale = {"aimed_at": near_stale[1]["id"], "packet": packet_ref(last_packet),
                     "in_transit": [ack_ref(None, [a]) | {"command": a["command"]} for a in in_transit],
                     "nominal_end_from_packet": [round(v, 2) for v in stale_end],
                     "nominal_end_after_transit": [round(v, 2) for v in aware_end],
                     "rule": "first_execution_tick / telemetry_arrival_tick"}

    # Repeated a queued uplink that had not shown up in telemetry yet.
    by_sent = {}
    for ack in in_transit:
        by_sent.setdefault(ack["sent_tick"], []).append(ack)
    for sent_tick, acks in sorted(by_sent.items()):
        earlier = [a["command"] for a in point.acks_before if a["sent_tick"] == sent_tick]
        if commands and _same_commands(earlier, commands):
            findings.append(Finding("REPEATED_IN_TRANSIT", REASONING,
                                    f"call {point.n} repeats the uplink sent at tick {sent_tick}, still in transit "
                                    f"(last packet shows tick {last_packet['tick'] if last_packet else 0})", point.n,
                                    {"packet": packet_ref(last_packet), "earlier_uplink": ack_ref(None, acks),
                                     "rule": "telemetry_arrival_tick"}))
            break

    # What this uplink's commands actually did.
    sampled = set(sampled_before)
    for ack in point.acks_sent:
        command, command_id = ack["command"], ack["command_id"]
        tick = timeline.executed.get(command_id)
        if tick is None:
            continue
        state = timeline.state(tick) or {}
        for effect in timeline.effects.get(command_id, []):
            if effect["type"] == "sample_taken":
                sampled.add(effect["target_id"])
                if effect.get("on_time") is False:
                    target = targets.get(effect["target_id"], {})
                    findings.append(Finding("LATE_SAMPLE", REASONING,
                                            f"{effect['target_id']} sampled at tick {tick}, deadline tick "
                                            f"{target.get('deadline_tick')}", point.n,
                                            {"target": target, "executed_tick": tick, "ack": ack_ref(point.n, [ack]),
                                             "map_item": f"targets[{effect['target_id']}].deadline_tick"}))
            elif effect["type"] == "sample_failed":
                cause, detail = _miss_cause(effect, state, targets, sampled, stale, point, timeline, radius)
                findings.append(Finding("SAMPLE_MISSED", REASONING,
                                        f"sample command {command_id} at tick {tick} failed ({cause})", point.n,
                                        {"reason": effect.get("reason"), "cause": cause, "executed_tick": tick,
                                         "ack": ack_ref(point.n, [ack]), "packet_planned_from": packet_ref(last_packet),
                                         **detail}))
            elif effect["type"] == "safety_stop":
                position = state.get("position", [0, 0])
                cleared = [a["command_id"] for a in point.acks_sent + point.acks_before
                           if a["execute_tick"] > tick and a["command_id"] not in timeline.executed]
                findings.append(Finding("SAFETY_STOP", REASONING,
                                        f"drive {command_id} stopped at tick {tick} ({effect.get('reason')}); "
                                        f"{len(cleared)} queued commands cleared", point.n,
                                        {"reason": effect.get("reason"), "executed_tick": tick,
                                         "position": [round(v, 2) for v in position],
                                         "hazard": _hazard_near(position, public_map), "cleared": cleared,
                                         "command": command, "rule": "safety_stop"}))
            elif effect["type"] == "battery_depleted":
                findings.append(Finding("BATTERY_DEPLETED", REASONING,
                                        f"battery ran out at tick {tick} during command {command_id}", point.n,
                                        {"executed_tick": tick, "packet": packet_ref(last_packet),
                                         "rule": "energy_order / drive_cost / sample_cost / idle_cost"}))
    missed = any(f.tag == "SAMPLE_MISSED" and f.evidence.get("cause") == "stale_aim" for f in findings)
    if stale and (missed or point.points_lost > EPS):
        findings.insert(0, Finding("STALE_AIM", REASONING,
                                   f"aimed at {stale['aimed_at']} from the position in packet tick "
                                   f"{stale['packet']['state_tick']}, ignoring {len(in_transit)} commands in transit",
                                   point.n, stale))
    return findings


def _miss_cause(effect, state, targets, sampled, stale, point, timeline, radius):
    if effect.get("reason") == "insufficient_energy":
        return "battery", {"battery_at_tick": state.get("battery"), "rule": "sample_cost"}
    position = state.get("position") or [0, 0]
    detail = {"true_position": [round(v, 2) for v in position]}
    nearest = _nearest(position, targets)
    if nearest:
        detail["nearest_target"] = {"id": nearest[1]["id"], "distance": round(nearest[0], 2)}
        if nearest[0] <= radius and nearest[1]["id"] in sampled:
            return "already_sampled", detail
    if stale:
        detail["stale_aim"] = stale
        return "stale_aim", detail
    # Slip: the drives of this uplink went over sand, or wheel and visual odometry disagree.
    for ack in point.acks_sent:
        tick = timeline.executed.get(ack["command_id"])
        drive_state = timeline.state(tick) if tick is not None else None
        if ack["command"].get("action") != "drive" or not drive_state:
            continue
        wheel, visual = drive_state.get("wheel_odometry", 0.0), drive_state.get("visual_odometry", 0.0)
        if drive_state.get("terrain") == "sand" or wheel - visual > 0.05 * max(wheel, 1e-9):
            detail["slip_seen_at"] = {"state_tick": tick, "received_tick": drive_state.get("received_tick"),
                                      "wheel_odometry": round(wheel, 3), "visual_odometry": round(visual, 3),
                                      "terrain": drive_state.get("terrain")}
            detail["rule"] = "slip_ranges / slip_model"
            return "slip_not_corrected", detail
    return "aim", detail


def _advance_findings(point, rules, last_packet):
    findings = []
    if point.points_lost <= EPS:
        return findings
    delay = int(rules.get("delay_ticks", 0))
    queue_end = max([a["execute_tick"] for a in point.acks_before] or [0])
    start_now = max(queue_end + 1, point.tick + delay + 1)
    start_later = max(queue_end + 1, point.tick_after + delay + 1)
    idle = start_later - start_now
    evidence = {"queue_ends_tick": queue_end, "advanced": [point.tick, point.tick_after],
                "earliest_new_command_if_uplinked_now": start_now,
                "earliest_new_command_after_this_wait": start_later, "extra_idle_ticks": idle,
                "packet": packet_ref(last_packet), "rule": "first_execution_tick",
                "reference_plan": point.reference_instead}
    if queue_end <= point.tick:
        findings.append(Finding("WAITED_WITH_EMPTY_QUEUE", REASONING,
                                f"advanced {point.tick}->{point.tick_after} with nothing queued "
                                f"(last command ran at tick {queue_end})", point.n, evidence))
    elif idle > 0:
        findings.append(Finding("QUEUE_RAN_DRY", REASONING,
                                f"queue ends at tick {queue_end}; waiting until {point.tick_after} means the next "
                                f"command cannot run before tick {start_later} ({idle} more idle ticks)",
                                point.n, evidence))
    return findings


# ---- the whole run --------------------------------------------------------------------------
def discovery_findings(rebuild, timeline, result):
    """Discovered targets the agent could see but never collected (or collected late)."""
    findings = []
    samples = {s["target_id"]: s for s in result.get("samples", [])}
    sampled = set(result.get("sampled_targets", []))
    for state_tick, received_tick, target in timeline.discoveries:
        if received_tick is None or received_tick > rebuild.stop_tick:
            continue  # the agent stopped before this packet arrived
        taken = samples.get(target["id"])
        if target["id"] in sampled and (taken is None or taken.get("on_time", True)):
            continue
        first_seen = next((p for p in rebuild.decisions if p.tick >= received_tick), None)
        findings.append(Finding("DISCOVERY_MISSED", REASONING,
                                f"{target['id']} (value {target.get('value')}, deadline tick "
                                f"{target.get('deadline_tick')}) arrived in the packet for tick {state_tick} at "
                                f"tick {received_tick}; " + ("sampled late" if taken else "never sampled"),
                                first_seen.n if first_seen else None,
                                {"packet": {"state_tick": state_tick, "received_tick": received_tick},
                                 "target": target}))
    return findings


def outcome_findings(rebuild, result, public_map, timeline):
    findings = []
    targets = _targets(public_map, timeline)
    sampled = set(result.get("sampled_targets", []))
    if rebuild.agent_score >= rebuild.reference_from_start - EPS and rebuild.agent_score > 0:
        findings.append(Finding("PERFECT", OUTCOME, f"scored {rebuild.agent_score:g}, the reference "
                                f"scored {rebuild.reference_from_start:g} from the start"))
    if result.get("alive") is False:
        findings.append(Finding("DEAD", OUTCOME, "the rover died", evidence={"result": result}))
    elif result.get("at_base") is False:
        findings.append(Finding("NOT_HOME", OUTCOME, "alive but away from base at the horizon",
                                evidence={"rule": "reward"}))
    if not sampled:
        findings.append(Finding("NOTHING_SAMPLED", OUTCOME, "no sample was collected"))
    left = sorted(t for t in targets if t not in sampled)
    if left and sampled:
        findings.append(Finding("TARGETS_LEFT", OUTCOME, "never sampled: " + ", ".join(left),
                                evidence={"targets": [targets[t] for t in left]}))
    if rebuild.stop_loss > EPS:
        findings.append(Finding("STOPPED_EARLY", REASONING,
                                f"stopped at tick {rebuild.stop_tick}; the reference would have scored "
                                f"{rebuild.reference_after_agent_stopped:g} from there, not {rebuild.agent_score:g}",
                                evidence={"stop_tick": rebuild.stop_tick, "reference_plan": rebuild.stop_plan}))
    return findings


def infrastructure_findings(run, rebuild):
    findings = []
    if not run.has_transcript or (not run.transcript and run.replay.get("commands")):
        findings.append(Finding("INFRA_NO_TRANSCRIPT", INFRASTRUCTURE,
                                "artifacts/evaluator/transcript.jsonl is missing or empty",
                                evidence={"replay_commands": len(run.replay.get("commands", []))}))
    for record in run.transcript:
        if record["tool"] not in ("uplink", "advance") and not record.get("ok", True):
            findings.append(Finding("INFRA_TOOL_ERROR", INFRASTRUCTURE,
                                    f"call {record.get('n')} ({record['tool']}) failed: {record.get('error')}",
                                    record.get("n"), {"error": record.get("error")}))
    for call in run.unmatched_agent_calls:
        findings.append(Finding("INFRA_CALL_NOT_RECORDED", INFRASTRUCTURE,
                                f"the agent called {call.tool} in step {call.step_id} but the simulator has no "
                                f"record of it", evidence={"step_id": call.step_id, "arguments": call.arguments,
                                                           "result_seen_by_agent": call.result_text[:300]}))
    exception = (run.trial or {}).get("exception_info")
    if exception:
        findings.append(Finding("INFRA_HARBOR_EXCEPTION", INFRASTRUCTURE,
                                f"{exception.get('exception_type', 'exception')}: "
                                f"{str(exception.get('exception_message', ''))[:200]}",
                                evidence={"exception_info": {k: str(v)[:500] for k, v in exception.items()}}))
    if not rebuild.replay_matches:
        findings.append(Finding("INFRA_REBUILD_MISMATCH", INFRASTRUCTURE, rebuild.mismatch or "mismatch"))
    maximum = run.evaluator_result.get("max_available_value") or run.replay.get("result", {}).get("max_available_value")
    raw = run.evaluator_result.get("raw_score", run.replay.get("result", {}).get("raw_score"))
    if run.reward is not None and maximum and raw is not None and abs(run.reward - raw / maximum) > 1e-4:
        findings.append(Finding("INFRA_REWARD_MISMATCH", INFRASTRUCTURE,
                                f"reward.txt says {run.reward}, the evaluator says {raw}/{maximum}",
                                evidence={"reward_txt": run.reward, "raw_score": raw, "max_available_value": maximum}))
    return findings
