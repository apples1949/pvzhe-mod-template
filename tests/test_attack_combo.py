import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"tools"))
from attack_model import default_attack
from attack_combo import (ComboSimulation, ComboPlayback, default_combo, make_preset,
                          new_item, validate_combo, combo_result, emission_end, expand_arrangements, expand_fan)

GRID = dict(begin=[260,75], size=[80,98], rows=5, plantOffset=50)
PLANT, TARGET = [300,321], [830,320]


class ComboTests(unittest.TestCase):
    def test_same_type_items_have_independent_start_origin_and_budget(self):
        attack=dict(default_attack(), count=2, shotGap=.1)
        first=new_item("A", attack)
        second=new_item("B", attack, .5); second["attack"]["origin"][1]+=20
        combo=dict(attackRate=1, steps=[first,second])
        sim=ComboSimulation(combo,PLANT,TARGET,GRID)
        sim.step(0,TARGET); self.assertEqual(sim.emitted,1)
        sim.step(.49,TARGET); self.assertEqual(sim.emitted,2)
        sim.step(.01,TARGET); self.assertEqual(sim.emitted,3)
        self.assertEqual(sum(b["itemId"]==second["id"] for b in sim.bullets),1)
        self.assertEqual(next(b for b in sim.bullets if b["itemId"]==second["id"])["position"][1],324)
        sim.step(.1,TARGET); self.assertEqual(sim.emitted,4)
        self.assertEqual(first["attack"]["origin"],[27,-17])

    def test_mixed_items_can_be_simultaneous_or_solo_and_disabled(self):
        combo=make_preset("fan-track")
        combo["steps"][1]["start"]=0
        sim=ComboSimulation(combo,PLANT,TARGET,GRID); sim.step(0,TARGET)
        self.assertEqual(sim.emitted,8)  # fan7 + first tracking bullet
        self.assertEqual(len(set(b["color"] for b in sim.bullets)),2)
        solo=ComboSimulation(combo,PLANT,TARGET,GRID,only=combo["steps"][0]["id"]); solo.step(1,TARGET)
        self.assertEqual(solo.emitted,7)
        combo["steps"][0]["enabled"]=False
        self.assertEqual(validate_combo(combo,GRID,PLANT),5)

    def test_alternating_parallel_lanes_start_even_then_odd(self):
        combo=make_preset("parallel-alternating")
        self.assertEqual([s["attack"]["count"] for s in combo["steps"]],[2,3])
        self.assertTrue(all(s["attack"]["kind"]=="fan" and s["attack"]["spread"]==0
                            and s["arrangement"]["kind"]=="single" for s in combo["steps"]))
        sim=ComboSimulation(combo,PLANT,TARGET,GRID); sim.step(0,TARGET)
        self.assertEqual(sim.emitted,2)
        self.assertEqual(sorted(b["position"][1] for b in sim.bullets),[288,320])
        sim.step(.5,TARGET); self.assertEqual(sim.emitted,5)
        newborn=[b for b in sim.bullets if b["age"]==0]
        self.assertEqual(sorted(b["position"][1] for b in newborn),[272,304,336])

    def test_map_rows_are_routes_from_muzzle_not_teleported_births(self):
        combo=make_preset("rows-alternating")
        sim=ComboSimulation(combo,PLANT,TARGET,GRID); sim.step(0,TARGET)
        self.assertEqual([b["position"][1] for b in sim.bullets],[304,304])
        self.assertEqual([b["lane"]["offsetLine"] for b in sim.bullets],[-1,1])
        sim.step(.25,TARGET)
        self.assertEqual([b["position"][1] for b in sim.bullets],[206,402])
        with self.assertRaises(ValueError): validate_combo(combo,None,PLANT)

    def test_coarse_and_fine_updates_preserve_birth_times_and_positions(self):
        combo=default_combo(dict(default_attack(),count=5,shotGap=.1))
        combo["steps"][0]["start"] = .25
        coarse=ComboSimulation(combo,PLANT,TARGET,GRID); coarse.step(1,TARGET)
        fine=ComboSimulation(combo,PLANT,TARGET,GRID)
        for _ in range(100): fine.step(.01,TARGET)
        self.assertEqual(coarse.emitted,fine.emitted)
        for a,b in zip(coarse.bullets,fine.bullets):
            self.assertAlmostEqual(a["age"],b["age"])
            for x,y in zip(a["position"],b["position"]): self.assertAlmostEqual(x,y)

    def test_routed_tracking_uses_visible_position_not_an_unshifted_proxy(self):
        combo=make_preset("rows-alternating")
        item=combo["steps"][0]; item["arrangement"].update(rows=[2],timing="together")
        item["attack"].update(targeting="track")
        sim=ComboSimulation(combo,PLANT,TARGET,GRID); sim.step(.4,TARGET)
        before=sim.bullets[0]["position"]
        sim.step(.1,TARGET)
        velocity=sim.bullets[0]["velocity"]
        self.assertAlmostEqual(velocity[1]/velocity[0],(TARGET[1]-before[1])/(TARGET[0]-before[0]))

    def test_repeating_rounds_overlap_and_do_not_cancel_delayed_items(self):
        combo=default_combo(dict(default_attack(),count=1,shotGap=0))
        combo["steps"][0]["start"] = .8
        playback=ComboPlayback(combo,PLANT,TARGET,GRID,interval=.5,repeat=True)
        playback.step(.8,TARGET); self.assertEqual(len(playback.bullets),1)
        playback.step(.5,TARGET); self.assertEqual(len(playback.bullets),2)
        self.assertEqual(playback.rounds_started,3)
        self.assertAlmostEqual(emission_end(combo,GRID,PLANT),.8)

    def test_baseline_rate_does_not_scale_internal_offsets(self):
        combo=make_preset("fan-track"); combo["attackRate"]=2
        config=dict(sessionId="run",canvas=[1080,600],assets={},provenance={},grid=GRID,
                    baseline=dict(bulletSpeed=300,attackInterval=1.5))
        actor=dict(position=PLANT)
        output=combo_result(config,combo,actor,{},"confirmed")
        self.assertEqual(output["schemaVersion"],2)
        self.assertEqual(output["roundInterval"],.75)
        self.assertEqual(output["combo"]["steps"][1]["start"],.5)
        self.assertNotIn("attack",output)
        self.assertTrue(output["attackCooldownIncluded"])
        cancelled=combo_result(config,combo,dict(position=[300,-100]),{},"cancelled")
        self.assertFalse(cancelled["confirmed"])

    def test_identity_budget_and_bad_interval_fail_early(self):
        combo=default_combo(); combo["steps"].append(copy.deepcopy(combo["steps"][0]))
        with self.assertRaises(ValueError): validate_combo(combo,GRID,PLANT)
        combo=make_preset("parallel-alternating")
        combo["steps"][0]["arrangement"].update(kind="parallel",count=9)
        combo["steps"][0]["attack"].update(count=300,shotGap=0)
        other=new_item(attack=combo["steps"][0]["attack"]); other["arrangement"]=copy.deepcopy(combo["steps"][0]["arrangement"])
        combo["steps"] += [other,new_item(attack=other["attack"])]
        combo["steps"][-1]["arrangement"]=copy.deepcopy(other["arrangement"])
        with self.assertRaises(ValueError): validate_combo(combo,GRID,PLANT)
        with self.assertRaises(ValueError): ComboPlayback(default_combo(),PLANT,TARGET,GRID,interval=0,repeat=True)

    def test_explicit_round_seconds_and_flattened_groups(self):
        combo=default_combo(dict(default_attack(),count=2,shotGap=.1))
        combo["intervalSeconds"]=2
        config=dict(sessionId="seconds",canvas=[1080,600],assets={},provenance={},grid=GRID)
        output=combo_result(config,combo,dict(position=PLANT),{},"confirmed")
        self.assertEqual(output["roundInterval"],2)
        self.assertTrue(output["attackCooldownIncluded"])
        combo["steps"][0]["arrangement"].update(kind="parallel",count=5,timing="alternating")
        original=copy.deepcopy(combo)
        flat=expand_arrangements(combo,GRID,PLANT)
        self.assertEqual(combo,original)
        self.assertEqual(len(flat["steps"]),5)
        before=ComboSimulation(combo,PLANT,TARGET,GRID)
        after=ComboSimulation(flat,PLANT,TARGET,GRID)
        for dt in (0,.1,.4,.1,.2):
            before.step(dt,TARGET); after.step(dt,TARGET)
            a=sorted((round(b["age"],6),tuple(round(x,6) for x in b["position"])) for b in before.bullets)
            b=sorted((round(b["age"],6),tuple(round(x,6) for x in b["position"])) for b in after.bullets)
            self.assertEqual(a,b)

    def test_fan_is_expandable_straight_sugar(self):
        combo=default_combo(dict(default_attack(),kind="fan",count=3,shotGap=.2,spread=60,direction=170,
                                 birthOffsets=[[0,-10],[0,10]],birthY=0))
        original=copy.deepcopy(combo)
        flat=expand_fan(combo,combo["steps"][0]["id"],GRID,PLANT)
        self.assertEqual(combo,original)
        self.assertEqual([s["attack"]["kind"] for s in flat["steps"]],["straight"]*3)
        self.assertEqual([s["start"] for s in flat["steps"]],[0,.2,.4])
        a=ComboSimulation(combo,PLANT,TARGET,GRID); b=ComboSimulation(flat,PLANT,TARGET,GRID)
        a.step(.5,TARGET); b.step(.5,TARGET)
        for x,y in zip(a.bullets,b.bullets):
            for v,w in zip(x["position"],y["position"]): self.assertAlmostEqual(v,w)
        flat["steps"][0]["attack"]["speed"]=600
        self.assertEqual(flat["steps"][1]["attack"]["speed"],300)
        combo["steps"][0]["attack"]["count"]=25
        with self.assertRaises(ValueError): expand_fan(combo,combo["steps"][0]["id"],GRID,PLANT)


if __name__ == "__main__": unittest.main()
