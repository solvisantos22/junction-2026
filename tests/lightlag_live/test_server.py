"""The MCP layer: a real MCP client playing a real-clock campaign in this process.

Needs the `mcp` package (2.x, Python 3.10+); skipped without it.

    uv run --with 'mcp==2.3.0' python -m unittest discover -s tests/lightlag_live -v
"""

import os
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

try:
    import mcp  # noqa: F401
    HAVE_MCP = True
except ImportError:
    HAVE_MCP = False

from lightlag_dynamic.controllers import POLICIES  # noqa: E402
from lightlag_live import CampaignService, play_campaign  # noqa: E402

MISSIONS = [{"seed": 8000, "profile": "rush"}, {"seed": 8001, "profile": "rush_noisy"}]
TICK = 0.05


@unittest.skipUnless(HAVE_MCP, "the mcp package is not installed")
class ServerTest(unittest.TestCase):
    def setUp(self):
        from lightlag_live.server import build_server
        from lightlag_mcp.client import connect
        self.campaign = CampaignService(MISSIONS, seconds_per_tick=TICK)
        self.connect = lambda: connect(build_server(self.campaign, seconds_per_tick=TICK))

    def test_exactly_the_five_tools_and_the_clock_is_described(self):
        with self.connect() as tools:
            self.assertEqual(set(tools.tool_names()), {"rules", "map", "telemetry_log", "uplink", "advance"})
            rules = tools.rules()
            self.assertEqual(rules["clock"]["seconds_per_tick"], TICK)
            self.assertFalse(rules["clock"]["started"])
            self.assertEqual(rules["campaign"]["missions"], 2)

    def test_advance_waits_in_real_time_and_bad_calls_come_back_as_errors(self):
        with self.connect() as tools:
            tools.rules()
            time.sleep(4 * TICK)  # reading and thinking before the start is free
            started = time.monotonic()
            out = tools.advance(4)
            self.assertGreaterEqual(time.monotonic() - started, 4 * TICK * 0.9)
            self.assertEqual(out["current_tick"], 4)
            with self.assertRaises(ValueError):
                tools.advance(9)
            with self.assertRaises(ValueError):
                tools.uplink([{"action": "drive", "heading_deg": 0, "metres": 50}])

    def test_the_reference_plays_a_whole_campaign_through_mcp(self):
        with self.connect() as tools:
            play_campaign(tools, POLICIES["kf_mpc"])
        result = self.campaign.finish()
        self.assertEqual(result["finished_by"], "clock")
        self.assertEqual(len(result["missions"]), 2)
        self.assertTrue(all(m["alive"] for m in result["missions"]))
        self.assertGreater(result["reward"], 0.3)


if __name__ == "__main__":
    unittest.main()
