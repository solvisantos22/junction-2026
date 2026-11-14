from copy import deepcopy
import json
import math
import random
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from lightlag_learning.environment import (
    CANDIDATE_FEATURES, GLOBAL_FEATURES, OptionPilot, build_observation,
    estimate_goal, greedy_choice, random_choice, run_episode,
)
from lightlag_traverse.pilot import DEFAULTS, Pilot
from lightlag_traverse.planning import Sun


class PublicBeliefs:
    """Only public rules/map/beliefs exist; no simulator or true-state object."""
    horizon, capacity, now = 420, 100, 0
    surface = SimpleNamespace(width=600, height=400)

    def __init__(self, efficiency=1.0, sample_cost=3.0):
        self.opt = dict(DEFAULTS)
        self.rules = {"max_ticks":420, "battery_capacity":100, "idle_cost":.15,
                      "solar_peak":2.0, "sun_margin_ticks":20, "sample_cost":sample_cost,
                      "sample_windows":{"late_fraction":.25}, "target_radius":2.5}
        self.efficiency = efficiency
        self.sun = Sun(self.rules, efficiency)
        self.targets = {"a":{"value":8.0,"late_value":2.0,"deadline_tick":300},
                        "bad":{"value":9.0,"late_value":2.25,"deadline_tick":300}}
        self.nodes = {"a":0,"bad":1}
        self.fields = {"base":SimpleNamespace(ticks=[10.,10.],energy=[35.,400.])}
        self.pending, self.sampled = {}, set()
        self.credited_science, self.sample_failures = 0.0, 0
        self.outward, self.outward_energy = 10., 35.

    def _to(self, goal, x, y):
        return (2.,2.) if goal == "base" else (self.outward,self.outward_energy)

    def _open(self, tick):
        return [t for t in self.targets if t not in self.pending and t not in self.sampled]

    def _spot(self, goal):
        return (0.,0.) if goal == "base" else (100.,100.)


class PublicModelTests(unittest.TestCase):
    def test_charge_waits_are_included_and_late_energy_failure_is_masked(self):
        pilot = PublicBeliefs()
        forecast = estimate_goal(pilot, 4, 0, 0, 10, "a")
        self.assertIsNotNone(forecast)
        self.assertGreater(forecast["wait"], 0)
        self.assertGreater(forecast["visit_duration"], 11)
        pilot.outward, pilot.outward_energy = 2., 35.
        pilot.fields["base"].ticks[0] = 2.
        self.assertIsNone(estimate_goal(pilot, 400, 0, 0, 10, "a"))
        obs = build_observation(pilot, 400, 0, 0, 1, 10)
        self.assertFalse(obs["mask"][obs["ids"].index("a")])
        self.assertTrue(obs["mask"][0])

    def test_sample_energy_is_part_of_visit_plus_home_feasibility(self):
        pilot = PublicBeliefs(efficiency=0, sample_cost=1)
        pilot.outward, pilot.outward_energy = 2., 5.
        pilot.fields["base"].ticks[0], pilot.fields["base"].energy[0] = 2.,5.
        self.assertIsNotNone(estimate_goal(pilot, 4, 0, 0, 20, "a"))
        pilot.rules["sample_cost"] = 10
        self.assertIsNone(estimate_goal(pilot, 4, 0, 0, 20, "a"))

    def test_public_observation_dimensions_status_context_and_home_fallback(self):
        pilot = PublicBeliefs(efficiency=0)
        pilot.pending["a"] = 8
        pilot.credited_science, pilot.sample_failures = 4.0, 2
        obs = build_observation(pilot, 400, 0, 0, 1.25, 1)
        self.assertEqual(set(obs), {"ids","candidates","global","mask","tick","planned_tick"})
        self.assertNotIn("a",obs["ids"])
        self.assertEqual(len(obs["global"]),len(GLOBAL_FEATURES))
        self.assertTrue(all(len(row)==len(CANDIDATE_FEATURES) for row in obs["candidates"]))
        self.assertEqual(obs["global"][GLOBAL_FEATURES.index("pending_sample_count")],1/46)
        self.assertEqual(obs["global"][GLOBAL_FEATURES.index("credited_public_science")],4/200)
        self.assertEqual(obs["global"][GLOBAL_FEATURES.index("sample_failure_count")],2/46)
        self.assertEqual(obs["global"][GLOBAL_FEATURES.index("direct_home_model_feasible")],0)
        self.assertEqual(obs["mask"],[True,False])
        json.dumps(obs,allow_nan=False)
        self.assertTrue(all(math.isfinite(v) for row in obs["candidates"] for v in row))

    def test_forced_return_mask_and_controls_use_only_legal_goals(self):
        pilot = PublicBeliefs()
        obs = build_observation(pilot, 4, 0, 0, 1, 90, force_home=True)
        self.assertEqual(obs["mask"],[True,False,False])
        self.assertEqual(greedy_choice(obs),0)
        self.assertEqual(random_choice(obs,random.Random(1)),0)


class OptionBoundaryTests(unittest.TestCase):
    def make_pilot(self, choose):
        pilot = OptionPilot.__new__(OptionPilot)
        pilot.choose, pilot._goal, pilot._active = choose, None, None
        pilot._force_home, pilot._next_reason = False, "initial"
        pilot.transitions, pilot.decision_count = [], 0
        pilot.predict = lambda tick: (0,0,1,90)
        pilot.now = 0
        return pilot

    def obs(self,tick):
        return {"ids":["base","a"],"candidates":[[0.]*20,[0.]*20],
                "global":[0.]*14,"mask":[True,True],"tick":tick,"planned_tick":tick+4}

    def test_held_replans_do_not_sample_or_create_learning_transitions(self):
        calls=[]
        pilot=self.make_pilot(lambda obs: calls.append(obs) or 1)
        with patch('lightlag_learning.environment.build_observation',side_effect=lambda *a,**k:self.obs(pilot.now)):
            pilot._plan(4,0,0,90,0)
            for t in (12,24,36):
                pilot.now=t
                pilot._plan(t+4,0,0,90,0)
            self.assertEqual(len(calls),1)
            self.assertEqual(pilot.transitions,[])
            pilot._goal,pilot._next_reason,pilot.now=None,"sample_queued",37
            pilot._plan(41,0,0,90,0)
        self.assertEqual(len(calls),2)
        self.assertEqual(len(pilot.transitions),1)
        self.assertEqual(pilot.transitions[0]["elapsed_ticks"],37)
        self.assertEqual(pilot.transitions[0]["termination_reason"],"sample_queued")
        self.assertEqual(pilot.transitions[0]["reward"],0)
        self.assertFalse(pilot.transitions[0]["done"])

    def test_masked_and_noninteger_actions_are_rejected(self):
        obs=self.obs(0);obs['mask']=[True,False]
        for action in (True,1,2,-1,0.0,None):
            pilot=self.make_pilot(lambda obs:action)
            with self.subTest(action=action),patch('lightlag_learning.environment.build_observation',return_value=obs):
                with self.assertRaises(ValueError):pilot._plan(4,0,0,90,0)
            self.assertEqual(pilot.decision_count,0)

    def test_callback_mutation_does_not_change_stored_observation(self):
        def choose(obs):
            obs['candidates'][0][0]=999
            obs['mask'][0]=False
            return 0
        pilot=self.make_pilot(choose);obs=self.obs(0);original=deepcopy(obs)
        with patch('lightlag_learning.environment.build_observation',return_value=obs):
            pilot._plan(4,0,0,90,0)
        self.assertEqual(obs,original)
        self.assertEqual(pilot._active[0],original)

    def test_public_return_failure_closes_science_option_and_forces_home_mask(self):
        actions=iter([1,0])
        pilot=self.make_pilot(lambda obs:next(actions))
        pilot.alive,pilot.delay,pilot.horizon,pilot.reserved_until=True,3,420,0
        pilot.by_id,pilot.schedule,pilot.opt={},{},dict(DEFAULTS)

        def observation(*args,**kwargs):
            obs=self.obs(pilot.now)
            if args[-1] is True:obs['mask'][1]=False
            return obs

        with patch('lightlag_learning.environment.build_observation',side_effect=observation):
            pilot._plan(4,0,0,90,0)
            pilot.now=10
            with patch('lightlag_learning.environment.estimate_goal',return_value=None),\
                    patch.object(Pilot,'act',side_effect=lambda:pilot._plan(14,0,0,90,0)):
                pilot.act()
        self.assertEqual(pilot.transitions[0]['termination_reason'],'return_guard')
        self.assertEqual(pilot.transitions[0]['elapsed_ticks'],10)
        self.assertEqual(pilot._active[0]['mask'],[True,False])
        self.assertEqual(pilot._goal,'base')
        self.assertTrue(pilot._force_home)


class UsedMapIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.greedy=run_episode(1,greedy_choice,keep_replay=True)

    def test_full_grade_terminal_only_reward_and_transition_chain(self):
        run=self.greedy;transitions=run['transitions']
        self.assertEqual(run['result']['tick'],420)
        self.assertEqual(run['calls_by_tool']['advance'],420)
        self.assertEqual(run['invalid_calls'],[])
        self.assertEqual(run['replay']['result'],run['result'])
        self.assertEqual(run['reward'],run['result']['raw_score']/run['result']['max_available_value'])
        self.assertEqual(len(transitions),run['decision_count'])
        self.assertEqual(sum(t['reward'] for t in transitions),run['reward'])
        self.assertTrue(all(not t['done'] and t['reward']==0 for t in transitions[:-1]))
        self.assertTrue(transitions[-1]['done'])
        self.assertEqual(sum(t['elapsed_ticks'] for t in transitions),420)
        for previous,current in zip(transitions,transitions[1:]):
            self.assertEqual(previous['next_obs'],current['obs'])
        self.assertTrue(all(t['obs']['mask'][t['action']] for t in transitions))

    def test_queued_sample_releases_before_acknowledgement_without_wait_tax(self):
        run=self.greedy
        queued=[c for c in run['replay']['commands'] if c['command']['action']=='sample']
        transitions=[t for t in run['transitions'] if t['termination_reason']=='sample_queued']
        self.assertTrue(transitions)
        pending_index=GLOBAL_FEATURES.index('pending_sample_count')
        for transition in transitions:
            next_obs=transition['next_obs']
            matching=[c for c in queued if c['sent_tick']+1==next_obs['tick']]
            self.assertTrue(matching)
            self.assertGreater(next_obs['global'][pending_index],0)
            self.assertGreater(matching[0]['execute_tick'],next_obs['tick'])

    def test_home_choice_is_one_option_but_mission_still_runs_full_horizon(self):
        calls=[]
        run=run_episode(2,lambda obs:calls.append(obs) or 0)
        self.assertEqual(len(calls),1)
        self.assertEqual(run['decision_count'],1)
        self.assertEqual(run['transitions'][0]['elapsed_ticks'],420)
        self.assertEqual(run['reward'],0)
        self.assertTrue(run['result']['at_base'])
        self.assertEqual(run['result']['tick'],420)


if __name__=='__main__':unittest.main()
