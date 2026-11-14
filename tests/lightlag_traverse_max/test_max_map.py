"""The MAX map option of the traverse, the players written for it, and the runner that compares them.

    python3 -m unittest discover -s tests/lightlag_traverse_max -v

Standard library only. The two player tests fly short missions; under a minute in all.
"""

import math
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from lightlag_traverse.environment import MISSION, TraverseEnvironment  # noqa: E402
from lightlag_traverse.pilot import Pilot, fly  # noqa: E402
from lightlag_traverse.play import PublicTools  # noqa: E402
from lightlag_traverse.surface import PHYSICS  # noqa: E402
from lightlag_traverse.terrain import TraverseWorld  # noqa: E402
from lightlag_traverse_max import play  # noqa: E402
from lightlag_traverse_max.environment import (MAX_SETTINGS, NOTHING_ON, OPTIONS,  # noqa: E402
                                               MaxTraverseEnvironment, make_env)
from lightlag_traverse_max.players import FAST, HOME, POLICIES, MaxPilot, fly_max  # noqa: E402

DELAY = MISSION["delay_ticks"]
# Drives in eight directions, a sample and a wait: commands that do not depend on the telemetry.
MIXED = [{"action": "drive", "heading_deg": h, "metres": 5} for h in (0, 30, 60, 90, 200, 250, 300, 330)] * 4 \
    + [{"action": "sample"}, {"action": "wait"}]


def only(*names):
    """Every MAX setting off but these."""
    return dict(NOTHING_ON, **{name: MAX_SETTINGS[name] for name in names})


def plane(code, grade=0.0):
    """A 200 m square of one terrain rising eastwards at `grade`, the lander in the middle."""
    rows = [[int(round(100 * grade * i * 5.0)) for i in range(41)] for _ in range(41)]
    return TraverseWorld(1, 5.0, tuple(tuple(r) for r in rows), tuple(code * 40 for _ in range(40)),
                         (100.0, 100.0), ())


def script(env, commands):
    """Send the commands five at a time, as they can go, and play the mission to the end."""
    for start in range(0, len(commands), 5):
        env.uplink(commands[start:start + 5])
        env.advance(5)
    while not env.advance(5)["episode_complete"]:
        pass
    return env


class OptionTest(unittest.TestCase):
    def test_make_env_gives_the_normal_map_or_the_max_map(self):
        self.assertEqual(OPTIONS, ("normal", "max"))
        self.assertIs(type(make_env(1)), TraverseEnvironment)
        self.assertIs(type(make_env(1, "max")), MaxTraverseEnvironment)
        for bad in (lambda: make_env(1, "mars"), lambda: make_env(1, "normal", settings={"packet_loss": 0.2}),
                    lambda: make_env(1, "max", settings={"gravity": 2.0})):
            with self.assertRaises(ValueError):
                bad()

    def test_with_every_max_setting_off_it_is_the_normal_map(self):
        for seed in (1, 5):
            normal = script(TraverseEnvironment(seed), MIXED)
            off = script(MaxTraverseEnvironment(seed, settings=NOTHING_ON), MIXED)
            replay = off.replay()
            replay.pop("max")
            self.assertEqual(replay, normal.replay())
            self.assertEqual(off.telemetry_log(), normal.telemetry_log())
            self.assertEqual(off.map(), normal.map())

    def test_a_seed_is_the_same_mission_on_both_maps(self):
        normal, hard = make_env(4), make_env(4, "max")
        a, b = normal.map(), hard.map()
        for key in ("elevation_cm", "base", "targets", "width", "height", "cell_m"):
            self.assertEqual(a[key], b[key], key)
        crust = {(i, j) for r in b["crust_regions"] for j in range(int(r["y1"] / 5), int(r["y2"] / 5))
                 for i in range(int(r["x1"] / 5), int(r["x2"] / 5))}
        for j, (mine, theirs) in enumerate(zip(a["terrain"], b["terrain"])):
            for i, (x, y) in enumerate(zip(mine, theirs)):
                self.assertEqual(y, "b" if (i, j) in crust else x)
        self.assertEqual((normal._slip, normal._efficiency, normal._heading_bias),
                         (hard._slip, hard._efficiency, hard._heading_bias))
        self.assertEqual(hard.rules()["map_option"], "max")
        self.assertNotIn("map_option", normal.rules())


class RelayAndFaultTest(unittest.TestCase):
    def test_commands_wait_for_a_pass_and_packets_arrive_in_one(self):
        env = MaxTraverseEnvironment(2, settings=only("relay_passes"))
        open_ack = env.uplink([{"action": "wait"}])[0]
        self.assertEqual((open_ack["transmit_tick"], open_ack["execute_tick"]), (0, DELAY + 1))
        env.advance(5)                                       # tick 5: closed, the next pass opens at 8
        ack = env.uplink([{"action": "wait"}])[0]
        self.assertEqual((ack["sent_tick"], ack["transmit_tick"], ack["execute_tick"]), (5, 8, 8 + DELAY + 1))
        script(env, MIXED)
        log = env.telemetry_log()[1:]
        due = [(t + DELAY) if (t + DELAY) % 8 < 4 else ((t + DELAY) // 8 + 1) * 8 for t in range(1, 421)]
        self.assertEqual([p["tick"] for p in log], [t for t, when in zip(range(1, 421), due) if when <= 420])
        for packet in log:
            self.assertLess(packet["received_tick"] % 8, 4)
            self.assertGreaterEqual(packet["received_tick"], packet["tick"] + DELAY)

    def test_lost_packets_and_wild_fixes_change_the_packets_and_nothing_else(self):
        calm = dict(MAX_SETTINGS, packet_loss=0.0, fix_outliers=None)
        seen = set()
        for seed in (1, 2):
            on = script(MaxTraverseEnvironment(seed), MIXED)
            off = script(MaxTraverseEnvironment(seed, settings=calm), MIXED)
            self.assertEqual(on.replay()["states"], off.replay()["states"], "the same rover, tick for tick")
            lost = {e["tick"] for e in on.fault_events if e["fault"] == "packet_lost"}
            wild = {e["tick"] for e in on.fault_events if e["fault"] == "fix_outlier"} - lost
            mine = {p["tick"]: p for p in on.telemetry_log()}
            theirs = {p["tick"]: p for p in off.telemetry_log()}
            self.assertEqual(set(theirs) - set(mine), lost & set(theirs), "only the lost packets are missing")
            self.assertLessEqual(set(mine), set(theirs))
            for tick, packet in mine.items():
                if tick in wild:
                    self.assertNotEqual(packet["position"], theirs[tick]["position"])
                    self.assertEqual(dict(packet, position=None), dict(theirs[tick], position=None))
                else:
                    self.assertEqual(packet, theirs[tick])
            seen |= {"lost"} if lost & set(theirs) else set()
            seen |= {"wild"} if wild & set(mine) else set()
        self.assertEqual(seen, {"lost", "wild"})


class GroundTest(unittest.TestCase):
    def test_a_step_that_slips_past_the_limit_ends_the_drive_and_clears_the_queue(self):
        # Sand slips at least 0.15 + 3.5 x 0.1 - 0.02 = 0.48 up a 0.1 slope: more than 0.45.
        env = MaxTraverseEnvironment(3, plane("s", 0.1), settings=only("slip_check_limit"))
        env.uplink([{"action": "drive", "heading_deg": 0, "metres": 5}] * 5)
        env.advance(5)
        first = env._truth[DELAY + 1]
        self.assertEqual([e.get("reason") for e in first["events"] if e["type"] == "safety_stop"], ["slip_limit"])
        self.assertAlmostEqual(first["wheel_odometry"], PHYSICS["segment_m"])
        self.assertEqual((len(env._commands), env._slip_trips), (0, 1))
        for world, heading in ((plane("s", 0.1), 180), (plane("r", 0.1), 0)):   # downhill; regolith slips < 0.30
            calm = MaxTraverseEnvironment(3, world, settings=only("slip_check_limit"))
            calm.uplink([{"action": "drive", "heading_deg": heading, "metres": 5}] * 5)
            calm.advance(5)
            calm.advance(5)
            self.assertEqual(calm._slip_trips, 0)
            self.assertAlmostEqual(calm._truth[DELAY + 1]["wheel_odometry"], 5.0)

    def test_with_a_limit_above_any_slip_the_check_changes_nothing(self):
        for seed in (1, 2):
            never = script(MaxTraverseEnvironment(seed, settings=dict(NOTHING_ON, slip_check_limit=1.0)), MIXED)
            off = script(MaxTraverseEnvironment(seed, settings=NOTHING_ON), MIXED)
            self.assertEqual(never.replay()["states"], off.replay()["states"])

    def test_the_crust_is_mapped_as_bedrock_and_soft_only_on_gentle_cells(self):
        soft = 0
        for seed in (1, 2, 3):
            env = MaxTraverseEnvironment(seed, settings=only("crust"))
            world, normal = env.map(), TraverseEnvironment(seed).map()["terrain"]
            true, surface = env._surface.codes, env._world.surface()
            bx, by = world["base"]
            inside = set()
            self.assertEqual(len(world["crust_regions"]), 3)
            for r in world["crust_regions"]:
                for size in (r["x2"] - r["x1"], r["y2"] - r["y1"]):
                    self.assertTrue(40.0 <= size <= 80.0 and size % 5.0 == 0.0, size)
                gap_x, gap_y = max(r["x1"] - bx, 0.0, bx - r["x2"]), max(r["y1"] - by, 0.0, by - r["y2"])
                self.assertGreaterEqual((gap_x ** 2 + gap_y ** 2) ** 0.5, 25.0)
                inside |= {(i, j) for j in range(int(r["y1"] / 5), int(r["y2"] / 5))
                           for i in range(int(r["x1"] / 5), int(r["x2"] / 5))}
            for j, row in enumerate(world["terrain"]):
                for i, code in enumerate(row):
                    if (i, j) not in inside:
                        self.assertEqual((code, true[j][i]), (normal[j][i], normal[j][i]))
                        continue
                    self.assertEqual(code, "b")
                    self.assertIn(true[j][i], "bs")
                    if true[j][i] == "s":
                        soft += 1
                        self.assertLessEqual(surface.cell_max_slope(i, j), 0.10)
        self.assertGreater(soft, 0)

    def test_the_wheels_turn_scale_times_the_command_and_odometry_reads_the_command(self):
        env = MaxTraverseEnvironment(6, plane("r"), settings=only("wheel_scale_error"))
        scale = env._wheel_scale
        self.assertTrue(0.8 <= scale <= 1.2 and abs(scale - 1.0) > 0.01, scale)
        env.uplink([{"action": "drive", "heading_deg": 0, "metres": 5}])
        env.advance(5)
        before, drove = env._truth[DELAY], env._truth[DELAY + 1]
        self.assertAlmostEqual(drove["wheel_odometry"], 5.0, places=6)
        spent = before["battery"] + drove["charge"] - MISSION["idle_cost"] - drove["battery"]
        self.assertAlmostEqual(spent, 5.0 * scale * PHYSICS["drive_cost_per_wheel_m"]["regolith"], places=5)
        ground = 5.0 * scale * (1.0 - env._slip["regolith"])
        self.assertLessEqual(abs(drove["visual_odometry"] - ground), 5.0 * scale * PHYSICS["slip_noise"] + 1e-6)

    def test_turning_costs_energy_before_the_drive(self):
        runs = []
        for settings in (only("turn_cost_per_degree"), NOTHING_ON):
            env = MaxTraverseEnvironment(6, plane("r"), settings=settings)
            env.uplink([{"action": "drive", "heading_deg": 90, "metres": 5},
                        {"action": "drive", "heading_deg": 0, "metres": 5}])
            env.advance(5)
            env.advance(1)
            runs.append(env)
        turned = 0.01 * (90 + 90) * PHYSICS["drive_cost_per_wheel_m"]["regolith"]   # from heading 0, and back
        self.assertAlmostEqual(runs[0]._turn_energy, turned)
        self.assertAlmostEqual(runs[1]._truth[DELAY + 2]["battery"] - runs[0]._truth[DELAY + 2]["battery"], turned,
                               places=5)


class PlayerTest(unittest.TestCase):
    SHORT = {"max_ticks": 100}

    def test_on_the_normal_map_manh_max_plays_move_for_move_like_the_pilot(self):
        sent = []
        for player in (fly, fly_max):
            env = make_env(2, "normal", mission=self.SHORT)
            player(PublicTools(env), dict(FAST))
            sent.append(env._sent)
        self.assertGreater(len(sent[0]), 50)
        self.assertEqual(sent[0], sent[1])

    def test_manh_max_home_takes_the_pilots_step_on_the_way_home_and_manh_max_is_unchanged(self):
        """The same rover, 69 m out and told to go home, at 58 battery levels: manh_max_home decides as
        the pilot does (drive on, or creep on what the battery can pay for); manh_max still waits for
        the sun under its reserve, as when its published scores were played."""
        self.assertIn("manh_max_home", POLICIES)
        pilots = {}
        for name, make in (("pilot", lambda tools: Pilot(tools, dict(FAST))),
                           ("manh_max", lambda tools: MaxPilot(tools, dict(FAST))),
                           ("manh_max_home", lambda tools: MaxPilot(tools, dict(FAST, **HOME)))):
            env = make_env(2, "normal", mission=self.SHORT)
            pilot = make(PublicTools(env))
            for _ in range(40):
                pilot.act()
                out = pilot.tools.advance(1)
                pilot.observe(out["packets"], out["current_tick"])
            pilots[name] = (env, pilot)
        self.assertEqual(pilots["pilot"][0]._sent, pilots["manh_max"][0]._sent)
        self.assertEqual(pilots["pilot"][0]._sent, pilots["manh_max_home"][0]._sent)
        waited, crept = 0, 0
        for quarter in range(2, 60):
            battery, chosen = quarter / 4.0, {}
            for name, (_, pilot) in pilots.items():
                tick = max(pilot.now + pilot.delay + 1, pilot.reserved_until + 1)
                x, y, _, _ = pilot.predict(tick)
                gx, gy = pilot._spot("base")
                drive = pilot._drive if name == "pilot" else pilot._drive_command
                chosen[name] = drive("base", x, y, gx, gy, math.hypot(gx - x, gy - y), battery)
            self.assertEqual(chosen["manh_max_home"], chosen["pilot"], battery)
            if chosen["pilot"]["action"] == "drive" and chosen["manh_max"]["action"] == "wait":
                waited += 1
                crept += chosen["pilot"]["metres"] < 5.0
        self.assertGreater(waited, 10, "battery levels where the pilot drives home and manh_max waits")
        self.assertGreater(crept, 3, "... and where the pilot creeps on a shortened drive")

    def test_on_the_max_map_it_reads_the_wheel_size_off_the_battery_and_bridges_lost_packets(self):
        env = make_env(4, "max", mission=self.SHORT)
        pilot = fly_max(PublicTools(env), FAST)
        tick, scale = pilot.scale_from_battery
        self.assertAlmostEqual(scale, env._wheel_scale, places=5)
        self.assertLess(tick, 40)
        self.assertTrue(any(e["fault"] == "packet_lost" for e in env.fault_events))
        self.assertGreater(pilot.bridged, 0)
        result = env.evaluate()
        self.assertTrue(result["alive"] and result["at_base"])


class RunnerTest(unittest.TestCase):
    def test_it_compares_players_on_both_maps_on_the_same_seeds(self):
        runs = play.compare(["straight", "nothing"], [1], ["normal", "max"], workers=1)
        self.assertEqual(list(runs), [("normal", "straight"), ("normal", "nothing"), ("max", "straight"),
                                      ("max", "nothing")])
        self.assertEqual([r["seed"] for rows in runs.values() for r in rows], [1, 1, 1, 1])
        self.assertEqual(len(play.table(runs).splitlines()), 5)
        self.assertIn("max     straight - nothing", play.differences(runs))
        mean, low, high, wins = play.paired([{"seed": 1, "reward": 0.5}, {"seed": 2, "reward": 0.3}],
                                            [{"seed": 1, "reward": 0.2}, {"seed": 2, "reward": 0.4}])
        self.assertAlmostEqual(mean, 0.1)
        self.assertTrue(low <= mean <= high)
        self.assertEqual(wins, 1)
        play.policy('manh_max:{"stall_drives": 8}')
        with self.assertRaises(ValueError):
            play.policy("teleport")


if __name__ == "__main__":
    unittest.main()
