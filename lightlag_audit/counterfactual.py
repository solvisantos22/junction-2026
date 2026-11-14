"""Rebuild an episode exactly, and price each agent decision against the reference.

The simulator is deterministic given its seed, so the transcript replayed into a fresh
environment reproduces the run tick for tick (checked against the saved replay).

Points lost: V(k) is the score when the reference takes over just before the agent's k-th
state-changing call (an uplink or an advance), knowing exactly what the agent knew then: the
delivered telemetry log, the rules, the map and the acknowledgements of every command
already sent. The agent's k-th call cost V(k) - V(k+1). These differences add up exactly to
the gap between the reference playing from the start and the agent's final score, so the
report can say which decisions the gap came from. The reference only ever uses public
information; the evaluator uses the truth only to score the outcomes afterwards.
"""

import copy
from dataclasses import dataclass, field
import math
from typing import Any, Dict, List, Optional

from lightlag import Config, Environment, Rect, Target, World


class AuditError(RuntimeError):
    pass


# ---- environments --------------------------------------------------------------------------
def make_environment(replay):
    config = Config(**replay["config"])
    if "dynamic" in replay:
        from lightlag_dynamic.environment import DynamicEnvironment
        dynamic = replay["dynamic"]
        return DynamicEnvironment(seed=replay["seed"], config=config, profile=dynamic["profile"],
                                  noise_level=dynamic.get("noise_level", 1.0),
                                  bumpiness=dynamic.get("bumpiness", 0.0))
    public = replay["world"]
    world = World(width=public["width"], height=public["height"], base=tuple(public["base"]),
                  sand=tuple(Rect(**r) for r in public["sand"]),
                  hazards=tuple(Rect(**r) for r in public["hazards"]),
                  targets=tuple(Target(**t) for t in public["targets"]))
    return Environment(seed=replay["seed"], config=config, world=world)


def apply_call(env, record):
    """Repeat one transcript record. Failed calls failed for a rule; they change nothing."""
    tool, arguments = record["tool"], record.get("arguments") or {}
    try:
        if tool == "uplink":
            return env.uplink(arguments["commands"])
        if tool == "advance":
            return env.advance(**arguments)
    except (ValueError, KeyError, TypeError):
        if record.get("ok", True):
            raise AuditError(f"call {record.get('n')} succeeded in the run but fails on replay")
    return None


def finish(env):
    """What the collect hook does after the agent stops: run the clock out with no commands."""
    while _tick(env) < _horizon(env):
        env.advance(min(5, _horizon(env) - _tick(env)))
    return env.evaluate()


def _tick(env):
    return env._tick  # evaluator-side code: the audit is allowed the simulator's own clock


def _horizon(env):
    return env.rules()["max_ticks"]


# ---- the reference taking over --------------------------------------------------------------
class _TakeoverTools:
    """The five public tools, showing only the launch briefing while the reference is built
    so that every later packet goes through its normal update path in order."""

    def __init__(self, env):
        self.env = env
        self.briefing_only = True
        self.first_uplink = None

    def rules(self):
        return self.env.rules()

    def map(self):
        return self.env.map()

    def telemetry_log(self):
        log = self.env.telemetry_log()
        return log[:1] if self.briefing_only else log

    def uplink(self, commands):
        acknowledgements = self.env.uplink(commands)
        if self.first_uplink is None:
            self.first_uplink = {"tick": _tick(self.env), "commands": copy.deepcopy(commands)}
        return acknowledgements

    def advance(self, ticks=1):
        return self.env.advance(ticks)


def _core_takeover(env, acknowledgements):
    from lightlag.controllers.api import PublicTools
    from lightlag.controllers.reference import Mission
    tools = _TakeoverTools(env)
    public = PublicTools(rules=tools.rules, map=tools.map, telemetry_log=tools.telemetry_log,
                         uplink=tools.uplink, advance=tools.advance)
    mission = Mission(public)
    mission.predictor.acknowledge(copy.deepcopy(acknowledgements))
    mission.predictor.observe(env.telemetry_log()[1:])
    mission.current_tick = _tick(env)
    tools.briefing_only = False
    mission.run()
    return tools.first_uplink


def _dynamic_takeover(env, acknowledgements):
    from lightlag_dynamic.kf_mpc import KalmanMPCController
    tools = _TakeoverTools(env)
    controller = KalmanMPCController(tools)
    controller.acks = copy.deepcopy(acknowledgements)
    for packet in env.telemetry_log()[1:]:
        controller.absorb(packet)
    controller.tick = _tick(env)
    tools.briefing_only = False
    controller.run()
    return tools.first_uplink


def _team_takeover(env, acknowledgements):
    """Kristján's adaptive reference: the one Harbor's solution/solve.sh runs on the core task."""
    from lightlag_controllers import REFERENCE, make
    from lightlag_controllers.adapter import command_to_json, parse_map, parse_packets, parse_rules
    from lightlag_controllers.model import Command
    tools = _TakeoverTools(env)
    rules, world = parse_rules(env.rules()), parse_map(env.map())
    log = env.telemetry_log()
    controller = make(REFERENCE)
    controller.reset(rules, world, parse_packets(log[:1]))
    by_uplink = {}
    for ack in acknowledgements:  # the same acknowledgements the agent received, per uplink
        by_uplink.setdefault(ack["sent_tick"], []).append(ack)
    for sent_tick, acks in sorted(by_uplink.items()):
        commands = [Command(a["command"]["action"], a["command"].get("heading_deg", 0.0),
                            a["command"].get("metres", 0.0)) for a in acks]
        controller.on_ack(commands, [a["execute_tick"] for a in acks], sent_tick)
    tools.briefing_only = False
    tick, new_packets = _tick(env), parse_packets(log[1:])
    while tick < rules.horizon:  # the loop of lightlag_controllers.runner.drive, from now
        commands, ticks = controller.step(tick, new_packets)
        if commands:
            try:
                acks = tools.uplink([command_to_json(c) for c in commands])
            except ValueError:
                pass
            else:
                controller.on_ack(commands, [a["execute_tick"] for a in acks], tick)
        ticks = max(1, min(rules.max_advance, ticks, rules.horizon - tick))
        result = tools.advance(ticks)
        new_packets = parse_packets(result["packets"])
        tick = int(result["current_tick"])
    return tools.first_uplink


# "team": the Harbor reference on the core task; "kf_mpc": the reference on the dynamic profiles;
# "mission": Sölvi's lightlag.controllers reference, kept for comparison.
REFERENCES = {"team": _team_takeover, "kf_mpc": _dynamic_takeover, "mission": _core_takeover}


def default_reference(replay):
    return "kf_mpc" if "dynamic" in replay else "team"


def takeover_value(env, acknowledgements, reference):
    """Score if the reference plays from this exact moment; env is copied, never changed.

    Returns (raw score, plan): the plan says what the reference would have sent first and
    which samples it would have collected from here, for the report's "instead" line."""
    trial = copy.deepcopy(env)
    start = _tick(trial)
    first = REFERENCES[reference](trial, acknowledgements) if start < _horizon(trial) else None
    result = finish(trial)
    samples = [{"target_id": event["target_id"], "tick": state["tick"], "on_time": event.get("on_time", True)}
               for state in trial.replay()["states"] if state["tick"] > start
               for event in state["events"] if event["type"] == "sample_taken"]
    plan = {"tick": start, "first_uplink": first, "samples": samples, "raw_score": result["raw_score"],
            "alive": result.get("alive"), "at_base": result.get("at_base")}
    return result["raw_score"], plan


# ---- one pass over the transcript ----------------------------------------------------------
@dataclass
class DecisionPoint:
    n: int
    tool: str
    arguments: Dict[str, Any]
    ok: bool
    error: Optional[str]
    tick: int                       # simulator tick when the call was made
    tick_after: int
    log_before: List[Dict[str, Any]]
    acks_before: List[Dict[str, Any]]
    acks_sent: List[Dict[str, Any]] = field(default_factory=list)
    value_before: float = 0.0       # V(k): reference takes over instead of this call
    value_after: float = 0.0        # V(k+1): reference takes over right after it
    reference_instead: Optional[Dict[str, Any]] = None   # the reference's plan from just before this call

    @property
    def points_lost(self):
        return self.value_before - self.value_after


@dataclass
class Rebuild:
    reference: str
    decisions: List[DecisionPoint]
    reference_from_start: float
    agent_score: float
    reference_after_agent_stopped: float
    stop_tick: int
    replay_matches: bool
    mismatch: Optional[str]
    stop_plan: Optional[Dict[str, Any]] = None        # the reference's plan from where the agent stopped

    @property
    def stop_loss(self):
        return self.reference_after_agent_stopped - self.agent_score


def rebuild(replay, transcript, reference=None):
    reference = reference or default_reference(replay)
    env = make_environment(replay)
    acknowledgements = []
    decisions = []
    pending_value, pending_first = takeover_value(env, acknowledgements, reference)
    reference_from_start = pending_value
    for record in transcript:
        if record["tool"] not in ("uplink", "advance"):
            continue
        point = DecisionPoint(
            n=record.get("n"), tool=record["tool"], arguments=copy.deepcopy(record.get("arguments") or {}),
            ok=bool(record.get("ok", True)), error=record.get("error"), tick=_tick(env), tick_after=_tick(env),
            log_before=env.telemetry_log(), acks_before=copy.deepcopy(acknowledgements))
        point.value_before, point.reference_instead = pending_value, pending_first
        result = apply_call(env, record)
        if record["tool"] == "uplink" and result:
            point.acks_sent = copy.deepcopy(result)
            acknowledgements.extend(copy.deepcopy(result))
        point.tick_after = _tick(env)
        if point.ok:
            pending_value, pending_first = takeover_value(env, acknowledgements, reference)
        point.value_after = pending_value
        decisions.append(point)
    stop_tick = _tick(env)
    reference_after_stop = pending_value
    final = finish(env)
    matches, mismatch = _check_against_replay(env, replay)
    return Rebuild(reference, decisions, reference_from_start, final["raw_score"], reference_after_stop,
                   stop_tick, matches, mismatch, stop_plan=pending_first)


def _check_against_replay(env, replay):
    rebuilt = env.replay()
    saved_states = replay.get("states", [])
    if len(rebuilt["states"]) != len(saved_states):
        return False, f"{len(rebuilt['states'])} rebuilt states vs {len(saved_states)} saved"
    for mine, theirs in zip(rebuilt["states"], saved_states):
        if (mine["tick"] != theirs["tick"] or
                math.dist(mine["position"], theirs["position"]) > 1e-6 or
                abs(mine["battery"] - theirs["battery"]) > 1e-6):
            return False, f"state differs at tick {theirs['tick']}"
    if abs(rebuilt["result"]["raw_score"] - replay["result"]["raw_score"]) > 1e-9:
        return False, "final score differs"
    return True, None
