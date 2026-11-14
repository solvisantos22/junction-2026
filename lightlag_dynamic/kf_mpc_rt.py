"""Real-time-aware KF + MPC: `kf_mpc` that plans around its own thinking time. Optional extra.

    from lightlag_dynamic.kf_mpc_rt import kf_mpc_rt
    kf_mpc_rt(tools)          # tools: rules, map, telemetry_log, uplink, advance

Status: a PROPOSAL for the real-time clock (`python3 -m lightlag_dynamic.realtime`). Nothing
uses it unless the team accepts it; `kf_mpc` stays the reference everywhere it is used. How to
adopt or decline it: docs/lightlag-dynamic-pilot.md, section "Real-time-aware reference".

Why: on the real-time clock, ticks pass while a controller thinks. `kf_mpc` plans each command
for `tick + delay + 1`, the tick it last saw, so a controller that needs time to think sends
commands that land later than planned. Its predictions, deadlines and battery budget are then
off, and near the horizon its uplinks are rejected. A model that thinks for seconds should be
compared against a controller that also pays for thinking and plans around it.

What it changes, and nothing else:
- It measures its lag: the ticks between the tick it decided on and the tick its uplink
  arrived (`sent_tick` in the acknowledgement); the estimate is the median of the last five.
- It decides that much earlier: the queue counts as covering the earliest usable slot only
  from tick + lag + delay + 1. Its next commands then arrive as the queue runs out, so the
  rover does not idle while the controller thinks. The plan itself is kf_mpc's.
- If the clock has run past the horizon while it was thinking, it drops the commands that no
  longer fit instead of crashing.
- With no lag (turn-based play, or an instant controller on the real-time clock) it sends
  exactly kf_mpc's commands: tested on the same seeds.

Design choice, measured on development seeds 0-39 (rush and rush_noisy, delay 3): also moving
the planning slot by the lag, or using the largest recent lag, did worse than kf_mpc at small
lags. While a controller thinks the rover usually stands still, so a late plan is still
geometrically right; what costs score is the idle queue, and deciding early fixes that.

Standard library only, like kf_mpc.py; works through the same five public tools.
"""

import statistics

from .kf_mpc import KalmanMPCController

LAG_MEMORY = 5  # uplinks whose lag is remembered; the estimate is their median
TOO_LATE = ("beyond the episode horizon", "episode complete")


class RealTimeKalmanMPC(KalmanMPCController):
    def __init__(self, tools):
        self.lag = 0
        self.lags = []
        super().__init__(tools)

    # ---- timing ---------------------------------------------------------------------
    def ready(self):
        last = self.packets[-1]
        if not last["alive"]:
            return False
        if self.reserved_until() >= self.tick + self.lag + self.k + 1:
            return False  # the queue covers the earliest slot a command decided now could reach
        if self.confirm_tick is not None:
            if last["tick"] < self.confirm_tick:
                return False
            self.confirm_tick = None
        return True

    def _observe_lag(self, ticks):
        self.lags = (self.lags + [max(0, ticks)])[-LAG_MEMORY:]
        self.lag = int(statistics.median(self.lags))

    # ---- acting ---------------------------------------------------------------------
    def send(self, commands):
        decided_at = self.tick
        room = self.horizon - self.next_slot() + 1
        commands = commands[:max(0, room)]
        sent = False
        for i in range(0, len(commands), self.max_batch):
            batch = commands[i:i + self.max_batch]
            acks = None
            while batch:
                try:
                    acks = self.tools.uplink(batch)
                    break
                except Exception as error:  # in-process, MCP and PublicTools raise different types
                    if not any(reason in str(error) for reason in TOO_LATE):
                        raise
                    batch = batch[:-1]  # the clock moved on while thinking: drop what no longer fits
            if not acks:
                break
            self.acks.extend(acks)
            sent = True
            self.tick = max(self.tick, acks[0]["sent_tick"])  # the acknowledgement is a clock reading
            self._observe_lag(acks[0]["sent_tick"] - decided_at)
            if len(acks) < len(commands[i:i + self.max_batch]):
                break
        return sent


def kf_mpc_rt(tools):
    RealTimeKalmanMPC(tools).run()


POLICIES = {"kf_mpc_rt": kf_mpc_rt}
