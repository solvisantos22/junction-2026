"""Real-time-aware KF + MPC (optional extra): identical to kf_mpc without lag, better with it.

Standard library only; the real-time clock is a fake, so these run in seconds.
"""

import unittest

from lightlag import Config
from lightlag_dynamic.controllers import POLICIES
from lightlag_dynamic.kf_mpc_rt import RealTimeKalmanMPC, kf_mpc_rt
from lightlag_dynamic.realtime import RealTimeEpisodeService
from lightlag_dynamic.serve import DynamicEpisodeService

SPT = 5.0


class FakeClock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t

    def sleep(self, seconds):
        self.t += seconds


class Thinking:
    """Tools whose every call first spends `latency` seconds, as a slow controller would."""

    def __init__(self, service, clock, latency):
        self.service, self.clock, self.latency = service, clock, latency

    def _call(self, tool, arguments=None):
        self.clock.t += self.latency
        return self.service.call(tool, arguments)

    def rules(self):
        return self._call("rules")

    def map(self):
        return self._call("map")

    def telemetry_log(self):
        return self._call("telemetry_log")

    def uplink(self, commands):
        return self._call("uplink", {"commands": commands})

    def advance(self, ticks=1):
        return self._call("advance", {"ticks": ticks})


def config():
    return Config(delay_ticks=3, max_ticks=50)


def play_real_time(policy, seed, profile, thinking_ticks):
    clock = FakeClock()
    service = RealTimeEpisodeService(seed=seed, seconds_per_tick=SPT, clock=clock, sleep=clock.sleep,
                                     profile=profile, config=config())
    policy(Thinking(service, clock, thinking_ticks * SPT))
    result = service.finish()
    return result["raw_score"] / result["max_available_value"], service._env.replay()["commands"]


class RealTimeReferenceTest(unittest.TestCase):
    def test_turn_based_play_is_kf_mpc(self):
        for seed in (0, 7, 11):
            for profile in ("rush", "rush_noisy"):
                with self.subTest(seed=seed, profile=profile):
                    runs = []
                    for policy in (POLICIES["kf_mpc"], kf_mpc_rt):
                        service = DynamicEpisodeService(seed=seed, profile=profile, config=config())
                        policy(service)
                        runs.append((service.finish(), service._env.replay()["commands"]))
                    self.assertEqual(runs[0], runs[1])

    def test_instant_real_time_play_is_kf_mpc(self):
        for seed in (0, 7):
            self.assertEqual(play_real_time(POLICIES["kf_mpc"], seed, "rush_noisy", 0.0),
                             play_real_time(kf_mpc_rt, seed, "rush_noisy", 0.0))

    def test_measures_its_lag(self):
        clock = FakeClock()
        service = RealTimeEpisodeService(seed=7, seconds_per_tick=SPT, clock=clock, sleep=clock.sleep,
                                         profile="rush_noisy", config=config())
        controller = RealTimeKalmanMPC(Thinking(service, clock, 1.0 * SPT))
        controller.run()
        self.assertTrue(controller.lags, "it sent commands")
        self.assertGreaterEqual(controller.lag, 1)

    def test_slow_thinking_scores_at_least_kf_mpc(self):
        # Fresh seeds 600-639 at 1 tick per call: +4.0 points on rush_noisy, +8.9 on rush (paired).
        totals = {}
        for name, policy in (("kf_mpc", POLICIES["kf_mpc"]), ("kf_mpc_rt", kf_mpc_rt)):
            totals[name] = sum(play_real_time(policy, seed, "rush", 1.0)[0] for seed in range(600, 606))
        self.assertGreater(totals["kf_mpc_rt"], totals["kf_mpc"])


if __name__ == "__main__":
    unittest.main()
