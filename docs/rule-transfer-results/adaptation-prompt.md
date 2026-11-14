Repair your original autonomous rover program for the public rule-change mission described below. Produce a robust general policy that maximizes sampled reward while preserving the rover through the entire 50-tick mission and returning inside the base radius. You have two responses: first evaluate_policy, then submit_policy using the returned practice feedback. Submit Python defining play(tools). You may rewrite everything, use standard library and NumPy 2.3.4, perform numerical search and maintain in-episode state. Exact replacements always apply to the ORIGINAL code at the end of this prompt, including on the final response. Do not assume patches stack between responses.

You receive one practice evaluation on 20 already-used cases: four maps, each with unchanged rules or one of ground/turning/link/relay changes. Then your final code is frozen and tested on new maps with the same distribution. There is no performance advantage from naming a change; conservative budgeting and responding to public evidence are allowed. Preserve capabilities that work on unchanged, ground-change and lost-packet cases. There is no access to reference code, hidden state, the seed, reset, a score tool, environment source or internet. The sandbox contains only your policy and a public-tool adapter. Do not attempt to access evaluator files or other services. No state survives between episodes.

Public interface:
- tools.rules() -> rules dict; tools.map() -> current public map; tools.telemetry_log() -> all delivered public packets. These calls do not advance simulation time.
- tools.uplink(commands) accepts 1–5 dictionaries: {"action":"drive","heading_deg":number,"metres":number in [0,5]}, {"action":"sample"}, or {"action":"wait"}. Returns a list of acknowledgements with command_id, sent_tick, execute_tick, command. Commands execute FIFO, one per tick; respect actual acknowledged execute_tick and existing reservations. Rejected requests raise ValueError; catching it does not erase the rejected-call count. No cancellation or queue replacement tool exists.
- In the relay condition after its onset, acknowledgements also contain transmit_tick, even when transmitted immediately in an open pass. Use this public field if helpful; it is not hidden. Outside a pass, transmit waits until the next opening; execution starts at transmit_tick + delay_ticks + 1 or after existing reservations, whichever is later. A submission whose batch would execute after horizon is rejected before sending.
- tools.advance(ticks=1) accepts integer 1–5 and returns {current_tick, episode_complete, packets}. It is the only way your program advances time. Reasoning/computation does not spend mission ticks. Finish by advancing through the horizon or returning (the evaluator will still run remaining ticks including pending commands and idle drain). Arriving home or returning from play() does not end drain.
- One fresh Python 3.12 process per episode. Protection limits: 512MB memory, 1 CPU, 180 seconds total, 30 seconds between tool calls, 20,000 public calls. These protect the harness; optimize computation if needed. Do not print protocol JSON; ordinary prints go to stderr.
- Unchanged controls omit rule_change from rules(). Changed missions disclose the entire menu from the beginning, never the selected kind or onset. Exact rules and a public initial map/packet example follow. The example is a used practice map, not a fixed mission.

Failure feedback from unchanged original code on 40 used maps per condition:
{
  "prepared": {
    "none": {
      "n": 40,
      "mean_sampled_value": 7.9375,
      "mean_raw_score": 7.9375,
      "mean_normalized_score": 0.7447121801809302,
      "deaths": 0,
      "alive_home": 40,
      "statuses": {
        "returned": 40
      },
      "invalid_calls": 0
    },
    "ground": {
      "n": 40,
      "mean_sampled_value": 6.625,
      "mean_raw_score": 6.625,
      "mean_normalized_score": 0.6258947996447997,
      "deaths": 0,
      "alive_home": 40,
      "statuses": {
        "returned": 40
      },
      "invalid_calls": 0
    },
    "turning": {
      "n": 40,
      "mean_sampled_value": 6.9625,
      "mean_raw_score": 6.9625,
      "mean_normalized_score": 0.6552858252858252,
      "deaths": 0,
      "alive_home": 40,
      "statuses": {
        "returned": 40
      },
      "invalid_calls": 0
    },
    "link": {
      "n": 40,
      "mean_sampled_value": 6.9375,
      "mean_raw_score": 6.7625,
      "mean_normalized_score": 0.6364396714396714,
      "deaths": 0,
      "alive_home": 38,
      "statuses": {
        "returned": 40
      },
      "invalid_calls": 0
    },
    "relay": {
      "n": 40,
      "mean_sampled_value": 7.03125,
      "mean_raw_score": 7.03125,
      "mean_normalized_score": 0.6618155455655456,
      "deaths": 0,
      "alive_home": 40,
      "statuses": {
        "returned": 40
      },
      "invalid_calls": 0
    },
    "changed": {
      "n": 160,
      "mean_sampled_value": 6.8890625,
      "mean_raw_score": 6.8453125,
      "mean_normalized_score": 0.6448589604839605,
      "deaths": 0,
      "alive_home": 158,
      "statuses": {
        "returned": 160
      },
      "invalid_calls": 0
    }
  },
  "saved_opus": {
    "none": {
      "n": 40,
      "mean_sampled_value": 8.025,
      "mean_raw_score": 8.025,
      "mean_normalized_score": 0.7571109099234099,
      "deaths": 0,
      "alive_home": 40,
      "statuses": {
        "returned": 40
      },
      "invalid_calls": 0
    },
    "ground": {
      "n": 40,
      "mean_sampled_value": 7.44375,
      "mean_raw_score": 7.44375,
      "mean_normalized_score": 0.7057159507159507,
      "deaths": 0,
      "alive_home": 40,
      "statuses": {
        "returned": 40
      },
      "invalid_calls": 0
    },
    "turning": {
      "n": 40,
      "mean_sampled_value": 7.95,
      "mean_raw_score": 3.09375,
      "mean_normalized_score": 0.30264922577422576,
      "deaths": 23,
      "alive_home": 17,
      "statuses": {
        "returned": 40
      },
      "invalid_calls": 0
    },
    "link": {
      "n": 40,
      "mean_sampled_value": 8.025,
      "mean_raw_score": 8.025,
      "mean_normalized_score": 0.7571109099234099,
      "deaths": 0,
      "alive_home": 40,
      "statuses": {
        "returned": 40
      },
      "invalid_calls": 0
    },
    "relay": {
      "n": 40,
      "mean_sampled_value": 7.9375,
      "mean_raw_score": 7.9375,
      "mean_normalized_score": 0.7491942432567432,
      "deaths": 0,
      "alive_home": 40,
      "statuses": {
        "invalid_calls": 2,
        "returned": 38
      },
      "invalid_calls": 3
    },
    "changed": {
      "n": 160,
      "mean_sampled_value": 7.8390625,
      "mean_raw_score": 6.625,
      "mean_normalized_score": 0.6286675824175825,
      "deaths": 23,
      "alive_home": 137,
      "statuses": {
        "invalid_calls": 2,
        "returned": 158
      },
      "invalid_calls": 3
    }
  }
}
All 23 turning deaths finish inside base; 19 happen on ticks without executing a command. In 22/23 the program receives a public battery drop exceeding idle plus twice wheel metres before death. In 11 it submits further drives after that signal. The original forecast models idle, translation and sample costs but not turning; it can spend the reserve on small near-base corrections while the mission still has many ticks remaining. Plan both return and idle survival through tick 50, including queued work and uncertainty. Baseline nominal position correction aims around 0.15m, while the allowed base radius is 0.75m; reason about sensing uncertainty rather than blindly centering or stopping.
One public example (used map 3203): packet at tick18 arrives at21 and shows extra expenditure. A correction sent22 executes26 with a large heading change but only about0.18 commanded metres. Public battery in packet26 is6.9366; 24remainingticks would need12units just for idle. These are public packet excerpts, not hidden trajectory truth:
[
  {
    "tick": 17,
    "received_tick": 20,
    "position": [
      19.9223909045,
      19.2300639559
    ],
    "heading_deg": 193.6749,
    "battery": 25.807075432,
    "terrain": "bedrock",
    "wheel_odometry": 5.0,
    "visual_odometry": 4.642439183,
    "sampled_targets": [
      "t1",
      "t2",
      "t4",
      "t5"
    ],
    "alive": true,
    "events": [
      {
        "type": "command_executed",
        "command_id": 14
      }
    ]
  },
  {
    "tick": 18,
    "received_tick": 21,
    "position": [
      20.0564605921,
      19.8957958579
    ],
    "heading_deg": 52.5188,
    "battery": 21.5981118236,
    "terrain": "bedrock",
    "wheel_odometry": 0.3997,
    "visual_odometry": 0.3419610974,
    "sampled_targets": [
      "t1",
      "t2",
      "t4",
      "t5"
    ],
    "alive": true,
    "events": [
      {
        "type": "command_executed",
        "command_id": 15
      }
    ]
  },
  {
    "tick": 25,
    "received_tick": 28,
    "position": [
      20.1336277274,
      19.9001534441
    ],
    "heading_deg": 131.3544,
    "battery": 9.440180734,
    "terrain": "bedrock",
    "wheel_odometry": 0.0,
    "visual_odometry": 0.0,
    "sampled_targets": [
      "t1",
      "t2",
      "t4",
      "t5"
    ],
    "alive": true,
    "events": []
  },
  {
    "tick": 26,
    "received_tick": 29,
    "position": [
      20.3835237972,
      20.1761885724
    ],
    "heading_deg": 209.1724,
    "battery": 6.936615542,
    "terrain": "bedrock",
    "wheel_odometry": 0.1792,
    "visual_odometry": 0.1834490892,
    "sampled_targets": [
      "t1",
      "t2",
      "t4",
      "t5"
    ],
    "alive": true,
    "events": [
      {
        "type": "command_executed",
        "command_id": 19
      }
    ]
  }
]
Relay invalid calls on used maps3218 and3228: at missiontick44 or45 the old code estimates earliest execution48 or49. Waiting for relay opening48 makes execution52, which is beyond50. The public error is "commands would execute beyond the episode horizon". Both rovers survived and returned, but an error-free policy should predict legal timing before submitting.

Complete public rules and example initial map/telemetry:
{
  "rules": {
    "version": "lightlag-dynamic-v1",
    "delay_ticks": 3,
    "max_ticks": 50,
    "initial_battery": 100.0,
    "idle_cost": 0.5,
    "drive_cost": 1.0,
    "sample_cost": 3.0,
    "target_radius": 0.75,
    "base_radius": 0.75,
    "supported_actions": [
      "drive",
      "sample",
      "wait"
    ],
    "scripting_allowed": true,
    "first_execution_tick": "sent_tick + delay_ticks + 1; FIFO, one command per tick",
    "telemetry_arrival_tick": "state_tick + delay_ticks; tick 0 is the initial briefing",
    "max_commands_per_uplink": 5,
    "max_metres_per_drive": 5.0,
    "max_advance_ticks": 5,
    "slip_ranges": {
      "bedrock": [
        0.0,
        0.05
      ],
      "sand": [
        0.2,
        0.45
      ]
    },
    "slip_noise": [
      -0.02,
      0.02
    ],
    "terrain_drive_multipliers": {
      "bedrock": 1.0,
      "sand": 2.0
    },
    "energy_order": "idle drain, then command; drive costs per wheel metre",
    "safety_stop": "at a hazard or map edge, stop at last safe position and clear queued commands; reservations remain",
    "sampling": "pay sampling cost; collect the nearest unsampled active target within target_radius; a discovered target is active from its appear tick",
    "reward": "sum over sampled targets of value if the sample executed at or before deadline_tick, otherwise value * late_fraction; times 1 at base, 0.5 alive elsewhere, 0 if dead; scored at the horizon",
    "drive_integration_metres": 0.1,
    "slip_model": "clip(terrain coefficient + per-drive noise, 0, 0.9); noise is fixed by seed and execution tick",
    "heading": "0 degrees east, 90 north; each executed drive travels at the commanded heading plus a heading error: a hidden bias, uniform in +-heading_bias_deg at launch, which takes a Gaussian random-walk step of heading_bias_walk_deg before every executed drive, plus independent Gaussian noise of heading_noise_deg; telemetry heading_deg reports the commanded heading",
    "visual_odometry": "reported distance = true distance * (1 + Gaussian noise with std dev visual_odometry_noise)",
    "mission_profile": "rush_noisy",
    "random_map": true,
    "sample_windows_enabled": true,
    "discoveries_enabled": true,
    "map_generator": {
      "base": [
        20.0,
        20.0
      ],
      "sand_patches": 2,
      "sand_size_m": [
        6,
        12
      ],
      "hazards": 2,
      "hazard_size_m": [
        [
          2,
          4
        ],
        [
          1,
          2.5
        ]
      ],
      "hazard_distance_m": [
        4,
        10
      ],
      "initial_targets": 5,
      "initial_distance_m": [
        3,
        9
      ],
      "initial_values": [
        1,
        2
      ],
      "initial_deadline_tick": [
        10,
        32
      ],
      "discoveries": [
        1,
        2
      ],
      "discovery_appear_tick": [
        6,
        24
      ],
      "discovery_distance_m": [
        3,
        8
      ],
      "discovery_values": [
        2,
        3
      ],
      "discovery_window_ticks": [
        6,
        12
      ],
      "min_spacing_m": 3.0,
      "hazard_clearance_m": 1.2
    },
    "profile_default_horizon": 50,
    "sensing": {
      "position_noise_m": 0.3,
      "visual_odometry_noise": 0.05,
      "heading_bias_deg": 5.0,
      "heading_bias_walk_deg": 0.5,
      "heading_noise_deg": 1.5
    },
    "noise_level": 1.0,
    "roughness": null,
    "sample_windows": {
      "late_fraction": 0.25,
      "deadline": "deadline_tick per target in map(); null means no deadline"
    },
    "discoveries": "new targets can appear mid-mission; a target_discovered event in the telemetry packet for its appear tick announces it, so it arrives delay_ticks later, and map() lists it from then on",
    "position_fix": "every delivered position after the tick-0 briefing = true position + independent Gaussian noise with std dev position_noise_m per axis, clipped to the map; the tick-0 briefing position is exact; the terrain field reports the terrain under the rover",
    "scoring_position": "sampling, base return and safety stops use the true position",
    "rule_change": {
      "happens": "exactly once per mission: one entry of `one_of`, from some tick in `tick_window` to the end",
      "tick_window": [
        12,
        30
      ],
      "announced": false,
      "this_entry": "never changes; no tool says which change happened or when",
      "one_of": {
        "ground": {
          "what": "the slip coefficient of every terrain changes",
          "slip_after": {
            "bedrock": [
              0.1,
              0.25
            ],
            "sand": [
              0.45,
              0.7
            ]
          },
          "shows_as": "a drive covers less ground than its wheel metres"
        },
        "turning": {
          "what": "turning costs energy: degrees of heading change at the start of a drive, times `energy_per_degree`, times the drive cost per metre (doubled when starting on sand)",
          "energy_per_degree": [
            0.02,
            0.04
          ],
          "shows_as": "the battery falls faster than idle, drive and sample costs explain"
        },
        "link": {
          "what": "each telemetry packet is lost with a fixed probability; a lost packet never arrives",
          "loss_probability": [
            0.25,
            0.45
          ],
          "shows_as": "ticks missing from the telemetry you receive"
        },
        "relay": {
          "what": "uplinks are transmitted only while a relay is overhead: the first `open_ticks` of every `period_ticks`, counted from tick 0; one sent outside a pass waits for the next",
          "period_ticks": 8,
          "open_ticks": 4,
          "shows_as": "an uplink acknowledgement whose transmit_tick is later than the tick it was sent"
        }
      }
    }
  },
  "map_example": {
    "width": 40.0,
    "height": 40.0,
    "base": [
      20.0,
      20.0
    ],
    "default_terrain": "bedrock",
    "sand": [
      {
        "x1": 12.81,
        "y1": 22.29,
        "x2": 23.32,
        "y2": 28.77
      },
      {
        "x1": 11.28,
        "y1": 27.44,
        "x2": 22.23,
        "y2": 37.75
      }
    ],
    "hazards": [
      {
        "x1": 26.58,
        "y1": 22.66,
        "x2": 29.93,
        "y2": 24.63
      },
      {
        "x1": 23.63,
        "y1": 22.12,
        "x2": 26.31,
        "y2": 24.03
      }
    ],
    "targets": [
      {
        "id": "t1",
        "x": 23.51,
        "y": 26.49,
        "value": 2,
        "deadline_tick": 28,
        "late_value": 0.5,
        "appear_tick": 0
      },
      {
        "id": "t2",
        "x": 17.87,
        "y": 12.2,
        "value": 2,
        "deadline_tick": 24,
        "late_value": 0.5,
        "appear_tick": 0
      },
      {
        "id": "t3",
        "x": 13.88,
        "y": 16.97,
        "value": 2,
        "deadline_tick": 17,
        "late_value": 0.5,
        "appear_tick": 0
      },
      {
        "id": "t4",
        "x": 26.88,
        "y": 14.74,
        "value": 1,
        "deadline_tick": 28,
        "late_value": 0.25,
        "appear_tick": 0
      },
      {
        "id": "t5",
        "x": 17.76,
        "y": 15.2,
        "value": 1,
        "deadline_tick": 13,
        "late_value": 0.25,
        "appear_tick": 0
      }
    ]
  },
  "initial_telemetry_example": [
    {
      "tick": 0,
      "received_tick": 0,
      "position": [
        20.0,
        20.0
      ],
      "heading_deg": 0.0,
      "battery": 100.0,
      "terrain": "bedrock",
      "wheel_odometry": 0,
      "visual_odometry": 0,
      "sampled_targets": [],
      "alive": true,
      "events": []
    }
  ]
}

Original source (the base for every replacement; exactly once):
```python
import math

_D2R = math.pi / 180.0


def _rect(r):
    if isinstance(r, dict):
        x1, y1, x2, y2 = float(r["x1"]), float(r["y1"]), float(r["x2"]), float(r["y2"])
    else:
        x1, y1, x2, y2 = [float(v) for v in r[:4]]
    return (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))


def _inflate(r, m):
    return (r[0] - m, r[1] - m, r[2] + m, r[3] + m)


def _inside(p, r):
    return r[0] <= p[0] <= r[2] and r[1] <= p[1] <= r[3]


def _seg_hits(p, q, r):
    x0, y0 = p
    dx, dy = q[0] - x0, q[1] - y0
    t0, t1 = 0.0, 1.0
    for pp, qq in ((-dx, x0 - r[0]), (dx, r[2] - x0), (-dy, y0 - r[1]), (dy, r[3] - y0)):
        if abs(pp) < 1e-12:
            if qq < 0:
                return False
        else:
            t = qq / pp
            if pp < 0:
                if t > t1:
                    return False
                if t > t0:
                    t0 = t
            else:
                if t < t0:
                    return False
                if t < t1:
                    t1 = t
    return t0 <= t1


def _dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _p_in(dx, dy, S, r):
    a = S[0][0] + 0.004
    b = S[0][1]
    c = S[1][1] + 0.004
    det = a * c - b * b
    if det <= 1e-12:
        return 1.0 if math.hypot(dx, dy) < r else 0.0
    ia, ib, ic = c / det, -b / det, a / det
    norm = 1.0 / (2 * math.pi * math.sqrt(det))
    nr, nt = 12, 24
    tot = 0.0
    for i in range(nr):
        rr = (i + 0.5) * r / nr
        for j in range(nt):
            th = (j + 0.5) * 2 * math.pi / nt
            zx = rr * math.cos(th) - dx
            zy = rr * math.sin(th) - dy
            q = ia * zx * zx + 2 * ib * zx * zy + ic * zy * zy
            tot += math.exp(-0.5 * q) * rr
    p = tot * norm * (r / nr) * (2 * math.pi / nt)
    return max(0.0, min(1.0, p))


class _EKF:
    def __init__(self, n):
        self.X = [0.0] * n
        self.P = [[0.0] * n for _ in range(n)]

    def copy(self):
        e = _EKF.__new__(_EKF)
        e.X = self.X[:]
        e.P = [row[:] for row in self.P]
        return e

    def scalar_update(self, H, resid, R):
        n = len(self.X)
        P = self.P
        PH = [sum(P[i][k] * H[k] for k in range(n)) for i in range(n)]
        S = sum(H[i] * PH[i] for i in range(n)) + R
        if S <= 1e-12:
            return
        K = [PH[i] / S for i in range(n)]
        for i in range(n):
            self.X[i] += K[i] * resid
        for i in range(n):
            for j in range(n):
                P[i][j] -= K[i] * PH[j]
        for i in range(n):
            for j in range(i + 1, n):
                v = 0.5 * (P[i][j] + P[j][i])
                P[i][j] = v
                P[j][i] = v
            if P[i][i] < 1e-9:
                P[i][i] = 1e-9


class _Rec:
    def __init__(self, cid, cmd, sent, exe, target=None):
        self.cid = cid
        self.cmd = cmd
        self.sent = sent
        self.exe = exe
        self.target = target
        self.status = "pending"


class _Pilot:
    def __init__(self, rules, mp):
        self.delay = int(rules.get("delay_ticks", 3))
        self.max_ticks = int(rules.get("max_ticks", 50))
        self.last_tick = self.max_ticks
        self.idle = float(rules.get("idle_cost", 0.5))
        self.dcost = float(rules.get("drive_cost", 1.0))
        self.scost = float(rules.get("sample_cost", 3.0))
        self.trad = float(rules.get("target_radius", 0.75))
        self.brad = float(rules.get("base_radius", 0.75))
        self.maxm = float(rules.get("max_metres_per_drive", 5.0))
        sens = rules.get("sensing", {}) or {}
        self.pos_sd = float(sens.get("position_noise_m", 0.6))
        self.vo_sd = float(sens.get("visual_odometry_noise", 0.1))
        bias0 = float(sens.get("heading_bias_deg", 10.0))
        walk = float(sens.get("heading_bias_walk_deg", 1.0))
        hn = float(sens.get("heading_noise_deg", 3.0))
        self.walk_var = (walk * _D2R) ** 2
        self.h_sd = math.sqrt(hn ** 2 + 1.5 ** 2) * _D2R
        sr = dict(rules.get("slip_ranges", {}) or {})
        dt = mp.get("default_terrain", "bedrock")
        if dt not in sr:
            sr[dt] = [0.0, 0.05]
        self.terrains = list(sr.keys())
        mults = rules.get("terrain_drive_multipliers", {}) or {}
        self.mult = [float(mults.get(t, 1.0)) for t in self.terrains]
        sn = rules.get("slip_noise", [-0.02, 0.02]) or [-0.02, 0.02]
        self.sn_var = (float(sn[1]) - float(sn[0])) ** 2 / 12.0
        self.nT = len(self.terrains)
        self.def_idx = self.terrains.index(dt)
        self.s_prior = []
        self.s_var = []
        for t in self.terrains:
            lo, hi = float(sr[t][0]), float(sr[t][1])
            self.s_prior.append(0.5 * (lo + hi))
            self.s_var.append((hi - lo) ** 2 / 12.0 + 1e-5)
        self.bias_var = (bias0 * _D2R) ** 2 / 3.0 + 1e-6

        self.Wm = float(mp.get("width", 40.0))
        self.Hm = float(mp.get("height", 40.0))
        b = mp.get("base", [20.0, 20.0])
        self.base = (float(b[0]), float(b[1]))
        self.areas = []
        for i, name in enumerate(self.terrains):
            if i == self.def_idx:
                continue
            rl = mp.get(name)
            if isinstance(rl, list):
                for r in rl:
                    try:
                        self.areas.append((i, _rect(r)))
                    except Exception:
                        pass
        self.hazards = []
        for h in mp.get("hazards", []) or []:
            try:
                self.hazards.append(_rect(h))
            except Exception:
                pass
        self.chk_m = 0.8
        self.cor_m = 1.05
        corners = []
        for h in self.hazards:
            R = _inflate(h, self.cor_m)
            for c in ((R[0], R[1]), (R[2], R[1]), (R[0], R[3]), (R[2], R[3])):
                c = (min(max(c[0], 0.3), self.Wm - 0.3), min(max(c[1], 0.3), self.Hm - 0.3))
                ok = True
                for h2 in self.hazards:
                    if _inside(c, _inflate(h2, self.chk_m)):
                        ok = False
                if ok:
                    corners.append(c)
        self.corners = corners
        nc = len(corners)
        self.cvis = [[False] * nc for _ in range(nc)]
        for i in range(nc):
            for j in range(i + 1, nc):
                v = self.visible(corners[i], corners[j])
                self.cvis[i][j] = v
                self.cvis[j][i] = v
        self.path_cache = {}

        n = 3 + self.nT
        self.ekf = _EKF(n)
        self.ekf.X[0], self.ekf.X[1] = self.base
        for i in range(self.nT):
            self.ekf.X[3 + i] = self.s_prior[i]
            self.ekf.P[3 + i][3 + i] = self.s_var[i]
        self.ekf.P[2][2] = self.bias_var
        self.known_tick = -1
        self.battery = float(rules.get("initial_battery", 100.0))
        self.alive = True
        self.sampled = set()
        self.cmds = {}
        self.by_exec = {}
        self.last_exec = 0
        self.targets = list(mp.get("targets", []) or [])
        self.R_ret = 8
        self.margin = 4.0

    # ---------- geometry ----------
    def terrain_idx(self, p):
        for i, r in self.areas:
            if _inside(p, r):
                return i
        return self.def_idx

    def fractions(self, p, q):
        L = _dist(p, q)
        n = max(1, int(L / 0.2) + 1)
        cnt = [0] * self.nT
        for k in range(n):
            t = (k + 0.5) / n
            cnt[self.terrain_idx((p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1])))] += 1
        return [c / n for c in cnt]

    def visible(self, p, q):
        for h in self.hazards:
            R = _inflate(h, self.chk_m)
            if _inside(p, R) or _inside(q, R):
                R = _inflate(h, 0.05)
                if _inside(p, R) or _inside(q, R):
                    continue
            if _seg_hits(p, q, R):
                return False
        return True

    def path(self, a, b):
        if not self.hazards or self.visible(a, b):
            return [a, b]
        nodes = self.corners
        N = len(nodes)
        INF = float("inf")
        dist = [INF] * N
        prev = [-1] * N
        for k in range(N):
            if self.visible(a, nodes[k]):
                dist[k] = _dist(a, nodes[k])
        done = [False] * N
        best, best_k = INF, -1
        for _ in range(N):
            k, dk = -1, INF
            for m in range(N):
                if not done[m] and dist[m] < dk:
                    k, dk = m, dist[m]
            if k < 0:
                break
            done[k] = True
            if self.visible(nodes[k], b):
                tot = dk + _dist(nodes[k], b)
                if tot < best:
                    best, best_k = tot, k
            for m in range(N):
                if not done[m] and self.cvis[k][m]:
                    nd = dk + _dist(nodes[k], nodes[m])
                    if nd < dist[m]:
                        dist[m] = nd
                        prev[m] = k
        if best_k < 0:
            return [a, b]
        seq = []
        k = best_k
        while k >= 0:
            seq.append(nodes[k])
            k = prev[k]
        seq.reverse()
        return [a] + seq + [b]

    def segs_of(self, path):
        out = []
        for i in range(len(path) - 1):
            out.append((_dist(path[i], path[i + 1]), self.fractions(path[i], path[i + 1])))
        return out

    def cached_segs(self, a, b):
        key = (round(a[0], 3), round(a[1], 3), round(b[0], 3), round(b[1], 3))
        s = self.path_cache.get(key)
        if s is None:
            s = self.segs_of(self.path(a, b))
            self.path_cache[key] = s
        return s

    def leg_cost(self, segs, svec):
        tot = sum(s[0] for s in segs)
        if tot <= 0.25:
            return 0, 0.0
        ticks, en = 0, 0.0
        for L, fr in segs:
            if L < 1e-6:
                continue
            eff = max(0.05, sum(fr[i] * (1 - svec[i]) for i in range(self.nT)))
            W = L / eff
            ticks += max(1, int(math.ceil(W / self.maxm - 1e-9)))
            en += self.dcost * W * sum(fr[i] * self.mult[i] for i in range(self.nT))
        return ticks, en

    # ---------- filter ----------
    def svec(self, ek):
        return [min(0.9, max(0.0, ek.X[3 + i])) for i in range(self.nT)]

    def drive_predict(self, ek, H_deg, W):
        X, n = ek.X, len(ek.X)
        ek.P[2][2] += self.walk_var
        c = H_deg * _D2R + X[2]
        s = self.svec(ek)
        u0, u1 = math.cos(c), math.sin(c)
        L0 = W * (1 - s[self.def_idx])
        p0 = (X[0], X[1])
        fr = self.fractions(p0, (p0[0] + L0 * u0, p0[1] + L0 * u1))
        Wt = [W * f for f in fr]
        d = sum(Wt[i] * (1 - s[i]) for i in range(self.nT))
        F = [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]
        F[0][2] = -d * u1
        F[1][2] = d * u0
        for i in range(self.nT):
            F[0][3 + i] = -Wt[i] * u0
            F[1][3 + i] = -Wt[i] * u1
        X[0] += d * u0
        X[1] += d * u1
        P = ek.P
        A = [[sum(F[i][k] * P[k][j] for k in range(n)) for j in range(n)] for i in range(n)]
        P2 = [[sum(A[i][k] * F[j][k] for k in range(n)) for j in range(n)] for i in range(n)]
        sd2 = self.sn_var * W * W + 0.02 ** 2
        sh2 = (d * self.h_sd) ** 2
        P2[0][0] += sd2 * u0 * u0 + sh2 * u1 * u1
        P2[1][1] += sd2 * u1 * u1 + sh2 * u0 * u0
        P2[0][1] += (sd2 - sh2) * u0 * u1
        P2[1][0] += (sd2 - sh2) * u0 * u1
        ek.P = P2
        en = self.dcost * sum(Wt[i] * self.mult[i] for i in range(self.nT))
        return Wt, d, en

    def clamp_slip(self, ek):
        for i in range(self.nT):
            ek.X[3 + i] = min(0.9, max(0.0, ek.X[3 + i]))

    # ---------- telemetry ----------
    def ingest(self, log):
        pk = [p for p in log if isinstance(p, dict) and int(p.get("tick", -1)) > self.known_tick]
        pk.sort(key=lambda p: int(p.get("tick", 0)))
        for p in pk:
            self.process(p)

    def process(self, p):
        k = int(p.get("tick", 0))
        ek = self.ekf
        n = len(ek.X)
        if self.known_tick < 0:
            pos = p.get("position")
            if pos and k == 0:
                ek.X[0], ek.X[1] = float(pos[0]), float(pos[1])
            self.finish_packet(p, k)
            return
        for tau in range(self.known_tick + 1, k):
            r = self.by_exec.get(tau)
            if r is not None and r.status == "pending":
                r.status = "done"
                if r.cmd.get("action") == "drive":
                    self.drive_predict(ek, float(r.cmd["heading_deg"]), float(r.cmd["metres"]))
        events = p.get("events") or []
        executed = []
        stop = False
        for ev in events:
            if not isinstance(ev, dict):
                continue
            typ = str(ev.get("type", "")).lower()
            if typ == "command_executed":
                executed.append(ev.get("command_id"))
            elif ("cancel" in typ or "drop" in typ) and ev.get("command_id") in self.cmds:
                self.cmds[ev.get("command_id")].status = "cancelled"
                if "stop" in typ or "safety" in typ:
                    stop = True
            elif any(s in typ for s in ("stop", "safety", "hazard", "edge", "abort")):
                stop = True
        for cid in executed:
            r = self.cmds.get(cid)
            if r is None:
                continue
            r.status = "done"
            if r.cmd.get("action") == "drive":
                try:
                    W = float(p.get("wheel_odometry") or 0.0)
                except Exception:
                    W = float(r.cmd["metres"])
                if W > 1e-6:
                    Wt, d, _ = self.drive_predict(ek, float(r.cmd["heading_deg"]), W)
                    vo = p.get("visual_odometry")
                    if vo is not None:
                        try:
                            vo = float(vo)
                            H = [0.0] * n
                            for i in range(self.nT):
                                H[3 + i] = -Wt[i]
                            h = sum(Wt[i] * (1 - ek.X[3 + i]) for i in range(self.nT))
                            R = (self.vo_sd * max(h, 0.05)) ** 2 + self.sn_var * W * W + 0.0004
                            ek.scalar_update(H, vo - h, R)
                            self.clamp_slip(ek)
                        except Exception:
                            pass
                if W < float(r.cmd["metres"]) - 0.02:
                    stop = True
        if stop:
            for r in self.cmds.values():
                if r.status == "pending" and r.sent <= k - 1 and r.exe > k:
                    r.status = "cancelled"
        for r in self.cmds.values():
            if r.status == "pending" and r.exe <= k:
                r.status = "cancelled"
        pos = p.get("position")
        if pos is not None and k > 0:
            R = self.pos_sd ** 2
            H = [0.0] * n
            H[0] = 1.0
            ek.scalar_update(H, float(pos[0]) - ek.X[0], R)
            H = [0.0] * n
            H[1] = 1.0
            ek.scalar_update(H, float(pos[1]) - ek.X[1], R)
            self.clamp_slip(ek)
        self.finish_packet(p, k)

    def finish_packet(self, p, k):
        try:
            self.battery = float(p.get("battery", self.battery))
        except Exception:
            pass
        self.alive = bool(p.get("alive", True)) and self.battery > 0
        st = set()
        for s in p.get("sampled_targets") or []:
            if isinstance(s, dict):
                s = s.get("id")
            st.add(s)
        self.sampled = st
        self.known_tick = k

    # ---------- prediction / planning ----------
    def predict(self, e):
        ek = self.ekf.copy()
        B = self.battery
        for tau in range(self.known_tick + 1, e):
            B -= self.idle
            r = self.by_exec.get(tau)
            if r is not None and r.status == "pending":
                a = r.cmd.get("action")
                if a == "drive":
                    _, _, en = self.drive_predict(ek, float(r.cmd["heading_deg"]), float(r.cmd["metres"]))
                    B -= en
                elif a == "sample":
                    B -= self.scost
        return ek, B

    def available(self):
        excl = set(self.sampled)
        for r in self.cmds.values():
            if r.status == "pending" and r.target is not None:
                excl.add(r.target)
        out = []
        for t in self.targets:
            try:
                if t.get("id") in excl:
                    continue
                if float(t.get("value", 0)) <= 0:
                    continue
                if int(t.get("appear_tick", 0) or 0) > self.last_tick:
                    continue
                out.append(t)
            except Exception:
                pass
        return out

    def plan(self, mu, e, budget, tl, svec):
        n = len(tl)
        pts = [mu] + [(float(t["x"]), float(t["y"])) for t in tl] + [self.base]
        L = {}
        for i in range(n + 1):
            for j in range(1, n + 2):
                if i == j:
                    continue
                if i == 0:
                    segs = self.segs_of(self.path(mu, pts[j]))
                else:
                    segs = self.cached_segs(pts[i], pts[j])
                L[(i, j)] = self.leg_cost(segs, svec)
        info = []
        for t in tl:
            v = float(t.get("value", 0))
            lv = t.get("late_value")
            lv = float(lv) if lv is not None else 0.25 * v
            dl = t.get("deadline_tick")
            dl = int(dl) if dl is not None else None
            ap = int(t.get("appear_tick", 0) or 0)
            info.append((v, lv, dl, ap))
        limit = self.last_tick + 1 - self.R_ret
        best = {"key": None, "order": [], "end": None}
        hb = n + 1

        def dfs(i, tau, en, val, used, order):
            tk, eg = L[(i, hb)]
            end = tau + tk
            if end <= limit and en + eg <= budget:
                key = (round(val, 9), -end, -(en + eg))
                if best["key"] is None or key > best["key"]:
                    best["key"] = key
                    best["order"] = list(order)
                    best["end"] = end
            for j in range(1, n + 1):
                if used & (1 << j):
                    continue
                tk, eg = L[(i, j)]
                v, lv, dl, ap = info[j - 1]
                s = max(tau + tk, ap)
                if s > self.last_tick:
                    continue
                en2 = en + eg + self.scost
                if en2 > budget:
                    continue
                tkb, egb = L[(j, hb)]
                if s + 1 + tkb > limit or en2 + egb > budget:
                    continue
                gain = v if (dl is None or s <= dl) else lv
                order.append(j - 1)
                dfs(j, s + 1, en2, val + gain, used | (1 << j), order)
                order.pop()

        dfs(0, e, 0.0, 0.0, 0, [])
        if best["key"] is None:
            return [], None
        return [tl[k] for k in best["order"]], best["end"]

    def drive_toward(self, mu, g, bh, svec):
        path = self.path(mu, g)
        w = path[1]
        if _dist(mu, w) < 0.1 and len(path) > 2:
            w = path[2]
        Lg = _dist(mu, w)
        if Lg < 0.03:
            return None, 0.0
        fr = self.fractions(mu, w)
        eff = max(0.05, sum(fr[i] * (1 - svec[i]) for i in range(self.nT)))
        W = min(self.maxm, Lg / eff)
        W = round(W, 4)
        if W > self.maxm:
            W = self.maxm
        if W < 0.05:
            return None, 0.0
        phi = math.atan2(w[1] - mu[1], w[0] - mu[0])
        H = math.degrees(phi - bh) % 360.0
        en = self.dcost * W * sum(fr[i] * self.mult[i] for i in range(self.nT))
        return {"action": "drive", "heading_deg": round(H, 4), "metres": W}, en

    def decide(self, e):
        ek, B = self.predict(e)
        mu = (ek.X[0], ek.X[1])
        S = [[ek.P[0][0], ek.P[0][1]], [ek.P[1][0], ek.P[1][1]]]
        bh = ek.X[2]
        svec = self.svec(ek)
        budget0 = B - self.idle * (self.last_tick - e + 1)
        route, end = self.plan(mu, e, budget0 - self.margin, self.available(), svec)
        limit = self.last_tick + 1 - self.R_ret
        if route:
            tg = route[0]
            g = (float(tg["x"]), float(tg["y"]))
            d = _dist(mu, g)
            slack = limit - end if end is not None else 0
            if d <= 0.45:
                if e < int(tg.get("appear_tick", 0) or 0):
                    return None, None
                p = _p_in(mu[0] - g[0], mu[1] - g[1], S, self.trad)
                if p >= 0.5:
                    if budget0 - self.scost >= 0.5:
                        return {"action": "sample"}, tg.get("id")
                    return None, None
                if d > 0.2:
                    cmd, en = self.drive_toward(mu, g, bh, svec)
                    if cmd is not None and budget0 - en >= 0.5:
                        return cmd, None
                dl = tg.get("deadline_tick")
                if slack >= 5 and not (dl is not None and e + 1 > int(dl)):
                    return None, None
                if budget0 - self.scost >= 0.5:
                    return {"action": "sample"}, tg.get("id")
                return None, None
            cmd, en = self.drive_toward(mu, g, bh, svec)
            if cmd is not None and budget0 - en >= 0.5:
                return cmd, None
            return None, None
        g = self.base
        d = _dist(mu, g)
        if d > 0.15:
            cmd, en = self.drive_toward(mu, g, bh, svec)
            if cmd is not None and budget0 - en >= 0.3:
                return cmd, None
        return None, None

    def step(self, tools, t):
        if not self.alive:
            return
        e = max(t + self.delay + 1, self.last_exec + 1)
        if e != t + self.delay + 1 or e > self.last_tick:
            return
        cmd, tid = self.decide(e)
        if cmd is None:
            return
        try:
            acks = tools.uplink([cmd])
        except ValueError:
            if e >= self.max_ticks - 1:
                self.last_tick = min(self.last_tick, e - 1)
            return
        for a in acks or []:
            try:
                cid = a.get("command_id")
                exe = int(a.get("execute_tick", e))
                sent = int(a.get("sent_tick", t))
                rec = _Rec(cid, dict(a.get("command", cmd)), sent, exe,
                           tid if cmd.get("action") == "sample" else None)
                self.cmds[cid] = rec
                self.by_exec[exe] = rec
                if exe > self.last_exec:
                    self.last_exec = exe
            except Exception:
                pass


def play(tools):
    pilot = None
    try:
        pilot = _Pilot(tools.rules(), tools.map())
    except Exception:
        pilot = None
    t = 0
    try:
        log = tools.telemetry_log()
        for p in log:
            try:
                t = max(t, int(p.get("received_tick", 0) or 0))
            except Exception:
                pass
    except Exception:
        pass
    while True:
        if pilot is not None:
            try:
                pilot.ingest(tools.telemetry_log())
            except Exception:
                pass
            try:
                mp = tools.map()
                pilot.targets = list(mp.get("targets", []) or [])
            except Exception:
                pass
            try:
                pilot.step(tools, t)
            except Exception:
                pass
        try:
            res = tools.advance(1)
        except Exception:
            return
        try:
            t = int(res.get("current_tick", t + 1))
        except Exception:
            t += 1
        if res.get("episode_complete"):
            return

```
