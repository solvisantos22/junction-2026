"""Lightlag Traverse as a campaign: several missions on several worlds, one after another.

One mission is one world, and on one world a controller can be lucky. On the task's world two
Claude agents came within 0.04 and 0.05 of the reference; replayed on 300 fresh worlds their
programs ran the battery flat on 91 and 157 of them, and scored below the reference on 288 to 294
(docs/traverse-farm.md). A campaign plays several worlds in a row, each under exactly the rules
of a single mission, and scores them together, so a program has to work everywhere, not once.

What a campaign changes, compared with one mission, and nothing else:

- `rules()` and `map()` describe the mission in play and say which one it is (`mission`, and a
  `campaign` block in the rules); telemetry packets, acknowledgements and `advance` replies
  carry `mission`, and `advance` also says `campaign_complete`;
- when a mission's last tick passes it is scored, and the next one begins at once at its tick 0,
  with the rover at that world's lander and a full battery. The clock still moves only on
  `advance`, so between missions there is time to look at what happened;
- the campaign's score is the value credited in all missions divided by all the value there
  was in them: each mission counts by what it offered.

`TraverseCampaign` has the interface of one `TraverseEnvironment`; `TraverseCampaignService` is
the team's episode service around it, with the same lock, transcript and evaluator-only finish.
Standard library only.
"""

from __future__ import annotations

import os
from copy import deepcopy
from typing import Any, Dict, List, Optional, Sequence

from lightlag_mcp.service import EpisodeService

from .environment import TraverseEnvironment

VERSION = "lightlag-traverse-campaign-v1"
MAX_ADVANCE = 5


class TraverseCampaign:
    """Several traverse missions in a row, behind the interface of one `TraverseEnvironment`."""

    def __init__(self, seeds: Sequence[int], mission: Optional[Dict[str, Any]] = None) -> None:
        seeds = list(seeds)
        if not seeds or any(type(seed) is not int for seed in seeds):
            raise ValueError("a campaign needs one or more integer seeds")
        self.seeds = seeds
        self._overrides = dict(mission or {})
        self._results: List[Dict[str, Any]] = []
        self._replays: List[Dict[str, Any]] = []
        self._open(0)
        self.ticks = self._env.rules()["max_ticks"]

    # ---- progress ---------------------------------------------------------------------
    @property
    def mission(self) -> int:
        """The mission in play, counted from 1; the last one once the campaign is complete."""
        return self._index + 1

    @property
    def complete(self) -> bool:
        return len(self._results) == len(self.seeds)

    @property
    def elapsed(self) -> int:
        """Ticks played over the whole campaign."""
        return len(self._results) * self.ticks + (0 if self.complete else self._tick)

    # ---- the five tools ----------------------------------------------------------------
    def rules(self) -> Dict[str, Any]:
        rules = self._env.rules()
        rules["campaign"] = {
            "missions": len(self.seeds),
            "mission": self.mission,
            "ticks_per_mission": self.ticks,
            "complete": self.complete,
            "next_mission": ("begins the moment the last tick of the mission in play passes: at its tick 0, on a "
                             "new map, with the rover at that map's lander and a full battery. From then on "
                             "rules, map, telemetry_log and uplink describe the new mission"),
            "scoring": ("each mission is scored as `reward` says; the campaign's score is the value credited in "
                        "all missions divided by the value of every target of all of them"),
            "after_the_last": "advance answers campaign_complete true and lets no time pass; uplink is refused",
        }
        return rules

    def map(self) -> Dict[str, Any]:
        world = self._env.map()
        world["mission"] = self.mission
        world["missions"] = len(self.seeds)
        return world

    def telemetry_log(self) -> List[Dict[str, Any]]:
        return [dict(packet, mission=self.mission) for packet in self._env.telemetry_log()]

    def uplink(self, commands: Any) -> List[Dict[str, Any]]:
        if self.complete:
            raise ValueError("the campaign is complete")
        return [dict(ack, mission=self.mission) for ack in self._env.uplink(commands)]

    def advance(self, ticks: int = 1) -> Dict[str, Any]:
        if type(ticks) is not int or not 1 <= ticks <= MAX_ADVANCE:
            raise ValueError("ticks must be an integer from 1 to {}".format(MAX_ADVANCE))
        if self.complete:
            return {"current_tick": self.ticks, "episode_complete": True, "campaign_complete": True,
                    "mission": self.mission, "missions": len(self.seeds), "packets": []}
        mission = self.mission
        out = self._env.advance(ticks)
        self._tick = out["current_tick"]
        reply = {"current_tick": out["current_tick"], "episode_complete": out["episode_complete"],
                 "campaign_complete": False, "mission": mission, "missions": len(self.seeds),
                 "packets": [dict(packet, mission=mission) for packet in out["packets"]]}
        if out["episode_complete"]:
            self._close()
            reply["campaign_complete"] = self.complete
        return reply

    # ---- evaluator side ----------------------------------------------------------------
    def run_out(self) -> None:
        """Let every remaining tick of every remaining mission pass. Queued commands still execute;
        a mission not yet begun passes with its rover standing at its lander."""
        while not self.complete:
            out = self._env.advance(min(MAX_ADVANCE, self.ticks - self._tick))
            self._tick = out["current_tick"]
            if out["episode_complete"]:
                self._close()

    def evaluate(self) -> Dict[str, Any]:
        """Trusted evaluator API, once every mission has ended. Never expose it as an agent tool."""
        if not self.complete:
            raise ValueError("evaluation requires every mission to have ended")
        raw = sum(result["raw_score"] for result in self._results)
        available = sum(result["max_available_value"] for result in self._results)
        return {
            "version": VERSION, "mission_profile": "traverse-campaign", "tick": self.elapsed,
            "raw_score": raw, "max_available_value": available,
            "sampled_value": sum(result["sampled_value"] for result in self._results),
            "sampled_targets": ["{}:{}".format(result["mission"], target)
                                for result in self._results for target in result["sampled_targets"]],
            "alive": all(result["alive"] for result in self._results),
            "at_base": all(result["at_base"] for result in self._results),
            "mission_rewards": [result["reward"] for result in self._results],
            "seeds": list(self.seeds),
            "missions": deepcopy(self._results),
        }

    def replay(self) -> Dict[str, Any]:
        """Evaluator-only: every mission's replay, hidden truth included."""
        return {"version": VERSION + "-replay", "missions": deepcopy(self._replays)}

    def mission_records(self) -> List[Dict[str, Any]]:
        """Evaluator-only: (result, replay) of every mission that has ended, in order."""
        return [{"result": deepcopy(result), "replay": deepcopy(replay)}
                for result, replay in zip(self._results, self._replays)]

    # ---- internals ---------------------------------------------------------------------
    def _open(self, index: int) -> None:
        self._index = index
        self._env = TraverseEnvironment(self.seeds[index], mission=self._overrides or None)
        self._tick = 0

    def _close(self) -> None:
        result = self._env.evaluate()
        result.update(mission=self.mission, seed=self.seeds[self._index],
                      reward=result["raw_score"] / result["max_available_value"])
        self._results.append(result)
        self._replays.append(self._env.replay())
        if not self.complete:
            self._open(self._index + 1)


class TraverseCampaignService(EpisodeService):
    """lightlag_mcp's EpisodeService, playing a traverse campaign.

    Its tick counter runs over the whole campaign, so the service grades once, when the last
    mission has ended, and `finish()` lets every remaining tick of every remaining mission pass.
    """

    def __init__(self, seeds: Sequence[int], artifact_dir: Optional[str] = None,
                 mission: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(seed=list(seeds)[0], artifact_dir=artifact_dir)
        self._campaign = TraverseCampaign(seeds, mission)
        self._env = self._campaign
        rules = self._campaign.rules()
        self._max_ticks = len(self._campaign.seeds) * rules["max_ticks"]
        self._max_advance = rules["max_advance_ticks"]

    def _dispatch(self, tool: str, arguments: Dict[str, Any]) -> Any:
        result = super()._dispatch(tool, arguments)
        self._tick = self._campaign.elapsed
        return result

    def finish(self) -> Dict[str, Any]:
        with self._lock:
            self._closed = True
            self._campaign.run_out()
            self._tick = self._campaign.elapsed
            if self._result is None:
                self._grade()
            assert self._result is not None
            return dict(self._result)

    def _grade(self) -> None:
        self._result = dict(self._campaign.evaluate(), tool_calls=self._calls)
        if not self._artifact_dir:
            return
        self._write("result.json", self._result)
        for number, record in enumerate(self._campaign.mission_records(), 1):
            folder = os.path.join("missions", "{:02d}".format(number))
            os.makedirs(os.path.join(self._artifact_dir, folder), exist_ok=True)
            self._write(os.path.join(folder, "result.json"), record["result"])
            self._write(os.path.join(folder, "replay.json"), record["replay"])

    @staticmethod
    def _summarise(tool: str, result: Any) -> Dict[str, Any]:
        summary = EpisodeService._summarise(tool, result)
        if tool == "advance":
            summary.update(mission=result["mission"], campaign_complete=result["campaign_complete"])
        return summary


INSTRUCTIONS = """\
Lightlag Traverse campaign: you drive a rover across Mars-like ground for several missions in a \
row, each on its own map, through a signal delay.

Goal: in every mission, sample science targets and end at that map's lander. A mission is scored \
as one traverse: credited sample value x 1.0 if the rover ends within base_radius of the lander, \
x 0.5 if it ends alive elsewhere, x 0 if the battery reached zero. The campaign's score is the \
value credited in all missions divided by the value of every target of all of them.

Missions: when a mission's last tick passes, it is scored and the next one begins at once, at its \
tick 0, on a new map, with the rover at its lander and a full battery; rules, map and \
telemetry_log then describe it. map(), every telemetry packet and every advance reply carry \
`mission`; advance says episode_complete when a mission ends and campaign_complete when the last \
one has.

Timing: a command you send at tick t executes at tick t + delay_ticks + 1 at the earliest, one \
command per tick, in order. A telemetry packet describes the rover at packet.tick and reaches \
you delay_ticks later. Only `advance` moves the clock; every other tool is free.

The ground: `map` gives a height grid and a terrain class per cell. Slip, sideways slide and \
energy depend on the slope and the terrain; ground steeper than max_tilt stops the rover and \
clears its queue. The battery is charged by a sun that climbs and sinks over each mission. \
`rules` gives every formula and number.

Start with `rules` and `map`. The map is large, so read it with a program. You may write and \
run code.\
"""

TEXTS = {
    "instructions": INSTRUCTIONS,
    "rules": (
        "Published rules for the mission in play: timing, the drive physics on sloping ground (slip, sideways "
        "slide, the tilt limit), energy and solar charging, sensing noise, sampling, deadlines, discoveries and the "
        "reward; `campaign` says how many missions there are, which one is in play and how the campaign is "
        "scored. Free: does not advance time."),
    "map": (
        "The public map of the mission in play (`mission`, of `missions`): width, height and cell_m in metres; "
        "elevation_cm[j][i], the height in centimetres at x = i * cell_m, y = j * cell_m; terrain[j], one class "
        "code per grid cell (terrain_codes names them); the lander (base) and the targets known so far (id, x, y, "
        "value, deadline_tick, late_value, appear_tick). About 65 kB of JSON. `rules` defines how the ground acts "
        "on the rover. Free: does not advance time."),
    "telemetry_log": (
        "Every telemetry packet of the mission in play received so far, oldest first. Each packet has mission, "
        "tick (the moment it describes), received_tick, position [x, y], heading_deg (commanded heading), "
        "battery, charge (solar energy gained that tick), terrain, tilt (slope under the rover), wheel_odometry, "
        "visual_odometry, sampled_targets, alive and events. `rules` defines measurement accuracy. Packets are "
        "delay_ticks old when they arrive. Free: does not advance time."),
    "uplink": (
        "Send 1 to 5 commands to the rover of the mission in play. They execute in order, one per tick. The "
        "first executes at current_tick + delay_ticks + 1, or one tick after the last command already queued, "
        'whichever is later. Commands: {"action": "drive", "heading_deg": H, "metres": M} with heading 0 = east '
        'and 90 = north and M the wheel distance in (0, 5]; {"action": "sample"} collects the nearest unsampled '
        'target if the rover is within target_radius, and costs energy either way; {"action": "wait"}. Returns '
        "the execute_tick of each command. A request with any invalid command, or one that would execute past "
        "the end of the mission, is rejected whole and changes nothing. Does not advance time."),
    "advance": (
        "Let 1 to 5 ticks pass in the mission in play (default 1), never past its end. This is the only tool "
        "that moves the clock. Returns current_tick, episode_complete (this mission has ended, and the next one "
        "has begun at its tick 0 if there is one), campaign_complete, mission and the telemetry packets that "
        "arrived during those ticks."),
}
