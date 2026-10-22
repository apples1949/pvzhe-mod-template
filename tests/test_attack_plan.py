import copy
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from attack_model import default_attack, file_sha
from attack_combo import default_combo, make_preset, ComboSimulation
from attack_plan import (default_plan,new_item,preset,migrate,validate_plan,all_items,PlanSimulation,
                         launch_position,can_trigger,Expression,store_plan,load_plan,
                         implementation_changes, function_preset, bind_implementation, design_digest, region_bounds, steer_angle, upgrade_plan)

GRID=dict(begin=[260,75],size=[80,98],rows=5,plantOffset=50)
PLANT,TARGET=[300,321],[830,320]


class AttackPlanTests(unittest.TestCase):
    def test_unknown_guidance_and_invalid_delay_contracts_are_rejected(self):
        from attack_web import default_recipe,compile_recipe
        recipe=default_recipe();recipe.update(ammo='homing',trackingStrength=1)
        plan=compile_recipe(recipe);self.assertTrue(validate_plan(plan))
        for change in ('unknown','missing','negative','misplaced'):
            bad=copy.deepcopy(plan);guide=bad['groups'][0]['items'][0]['guidance']
            if change=='unknown':guide['model']='host-guidance-typo'
            elif change=='missing':guide.pop('trackingDelaySeconds')
            elif change=='negative':guide['trackingDelaySeconds']=-1
            else:guide['trackingStrength']=2
            with self.subTest(change=change),self.assertRaises(ValueError):validate_plan(bad)

    def test_one_item_one_carrier_and_presets_are_groups(self):
        plan=default_plan(); plan["groups"]=[preset("扇形",count=5,spread=60)]
        self.assertEqual(validate_plan(plan),5)
        sim=PlanSimulation(plan,PLANT,TARGET,GRID,repeat=False); sim.step(0,TARGET)
        self.assertEqual(sim.emitted,5)
        self.assertTrue(all(b["item"]["trajectory"]["kind"]=="straight" for b in sim.bullets))
        plan["groups"][0]["items"][0]["count"]=2
        with self.assertRaises(ValueError): validate_plan(plan)

    def test_import_retains_times_angles_positions_and_does_not_mutate(self):
        combo=make_preset("parallel-alternating"); old=copy.deepcopy(combo)
        config=dict(combo=combo,plant=dict(key="pea",position=PLANT),grid=GRID,baseline=dict(attackInterval=1.5))
        plan=migrate(config); self.assertEqual(combo,old)
        self.assertEqual(len(all_items(plan)),5)
        a=ComboSimulation(combo,PLANT,TARGET,GRID); b=PlanSimulation(plan,PLANT,TARGET,GRID,repeat=False)
        for dt in (0,.2,.3,.1):
            a.step(dt,TARGET); b.step(dt,TARGET)
            x=sorted(tuple(round(v,5) for v in p["position"]) for p in a.bullets)
            y=sorted(tuple(round(v,5) for v in p["position"]) for p in b.bullets)
            self.assertEqual(x,y)
        self.assertEqual([i["id"] for g,i in all_items(plan)],[i["id"] for g,i in all_items(migrate(config))])

    def test_legacy_rows_migrate_to_relative_offsets(self):
        config=dict(combo=make_preset("rows-alternating"),plant=dict(key="pea",position=PLANT),grid=GRID)
        plan=migrate(config)
        self.assertEqual([i["route"]["rowOffset"] for g,i in all_items(plan)],[-1,1,-2,0,2])
        moved=[300,223]
        target=[830,222]
        sim=PlanSimulation(plan,moved,target,GRID,repeat=False); sim.step(.25,target)
        self.assertEqual(sorted(round(b["position"][1]) for b in sim.bullets),[108,304])

    def test_birth_grid_offsets_and_trigger_use_relative_logical_cells(self):
        plan=default_plan(); item=all_items(plan)[0][1]
        item["launch"].update(gridOffset=[2,-1],offset=[10,-5])
        self.assertEqual(launch_position(item,PLANT,GRID),[470,218])
        plan["trigger"].update(columns=[0,8],rows=[-2,3])
        self.assertTrue(can_trigger(plan,PLANT,TARGET,GRID))
        self.assertFalse(can_trigger(plan,PLANT,[950,320],GRID))
        self.assertFalse(can_trigger(plan,PLANT,[830,26],GRID))

    def test_launch_uses_exact_pixel_displacement_and_preserves_legacy_position(self):
        from attack_plan import place_launch
        plan=default_plan(); item=all_items(plan)[0][1]
        item["launch"].update(gridOffset=[2,-1],offset=[10.125,-5.75])
        old=launch_position(item,PLANT,GRID)
        point=[old[0]+.1234567,old[1]-.7654321]
        place_launch(item,point,PLANT,GRID)
        self.assertEqual(item["launch"]["gridOffset"],[0,0])
        self.assertEqual(item["launch"]["offset"],[point[i]-PLANT[i] for i in (0,1)])
        self.assertEqual(launch_position(item,PLANT,GRID),point)
        self.assertEqual(launch_position(item,PLANT,None),point)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"plan.json"; store_plan(path,plan)
            self.assertEqual(launch_position(all_items(load_plan(path))[0][1],PLANT,None),point)

    def test_domains_and_bezier_are_not_active_plan_fields(self):
        plan=default_plan(); self.assertNotIn("domain",plan)
        self.assertNotIn("domain",all_items(plan)[0][1])
        invalid=copy.deepcopy(plan); invalid["domain"]={"kind":"unbounded"}
        with self.assertRaises(ValueError): validate_plan(invalid)
        invalid=copy.deepcopy(plan); all_items(invalid)[0][1]["trajectory"]["kind"]="bezier"
        with self.assertRaises(ValueError): validate_plan(invalid)

    def test_initial_aim_and_turn_rate_are_independent(self):
        plan=default_plan(); item=all_items(plan)[0][1]; item["launch"]["offset"]=[0,0]
        plan["trigger"].update(columns=[-100,100],rows=[-100,100])
        item["guidance"].update(initialAim=False,trackingStrength=1)
        sim=PlanSimulation(plan,[0,0],[0,800],GRID,repeat=False); sim.step(0,[0,800]); sim.step(.1,[0,800])
        vx,vy=sim.bullets[0]["velocity"]
        self.assertGreater(math.degrees(math.atan2(vy,vx)),0)
        self.assertLessEqual(math.degrees(math.atan2(vy,vx)),12)
        item["guidance"].update(initialAim=True,trackingStrength=0)
        sim=PlanSimulation(plan,[0,0],[0,800],GRID,repeat=False); sim.step(0,[0,800]); sim.step(.1,[800,0])
        self.assertAlmostEqual(sim.bullets[0]["position"][0],0)

    def test_ray_endpoint_follow_speed_limits_update(self):
        plan=default_plan(); item=all_items(plan)[0][1]; item["carrier"]="ray"
        item["guidance"].update(endBinding="live",endpointFollowSpeed=10)
        sim=PlanSimulation(plan,PLANT,TARGET,GRID,repeat=False); sim.step(0,TARGET); sim.step(.1,[830,500])
        self.assertAlmostEqual(math.dist(sim.bullets[0]["endpoint"],TARGET),1)

    def test_ray_is_instant_geometry_with_duration_no_damage_fields(self):
        plan=default_plan(); item=all_items(plan)[0][1]
        item.update(carrier="ray",rayDuration=.5); item["guidance"]["endBinding"]="snapshot"
        sim=PlanSimulation(plan,PLANT,TARGET,GRID,repeat=False); sim.step(0,TARGET)
        self.assertEqual(sim.bullets[0]["rayEnd"],TARGET)
        sim.step(.49,[900,400]); self.assertEqual(sim.bullets[0]["rayEnd"],TARGET)
        sim.step(.01,TARGET); self.assertFalse(sim.bullets)
        self.assertNotIn("damage",item)

    def test_functions_are_sandboxed_and_wave_has_editable_parameters(self):
        plan=default_plan(); item=all_items(plan)[0][1]; item["trajectory"]["kind"]="function"
        plan["trigger"].update(columns=[-100,100],rows=[-100,100])
        validate_plan(plan)
        sim=PlanSimulation(plan,[0,0],[900,0],GRID,repeat=False); sim.step(.1,[900,0])
        self.assertAlmostEqual(sim.bullets[0]["position"][0],57)
        for source in ("__import__('os')", "t.__class__", "[t][0]", "sum(t for t in [])", "True"):
            with self.assertRaises(ValueError): Expression(source,{})
        for source in ("1/0","sqrt(-1)","2**100000"):
            expr=Expression(source,{})
            with self.assertRaises(ValueError): expr(dict(t=0,v=300))
        for name in ("正弦波","回旋线","函数抛物线"):
            item["trajectory"].update(function_preset(name)); validate_plan(plan)

    def test_rounds_preserve_delayed_items_and_variable_steps(self):
        plan=default_plan(interval=.5); item=all_items(plan)[0][1]; item["time"]=.8
        a=PlanSimulation(plan,PLANT,TARGET,GRID); b=PlanSimulation(plan,PLANT,TARGET,GRID)
        a.step(1.3,TARGET)
        for n in range(130): b.step(.01,TARGET)
        self.assertEqual(a.emitted,2); self.assertEqual(a.emitted,b.emitted)
        for x,y in zip(a.bullets,b.bullets):
            for v,w in zip(x["position"],y["position"]): self.assertAlmostEqual(v,w)

    def test_portable_save_and_implementation_drift(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); plan=default_plan(); f=root/"Entry.cs"; f.write_text("first")
            plan["implementation"]["files"]={"Entry.cs":file_sha(f)}
            store_plan(root/"plan.json",plan); self.assertEqual(load_plan(root/"plan.json"),plan)
            self.assertEqual(implementation_changes(plan,root),[])
            f.write_text("second"); self.assertEqual(implementation_changes(plan,root),["Entry.cs"])
            bound=bind_implementation(plan,["Entry.cs"],root)
            self.assertEqual(bound["implementation"]["appliedPlanSha256"],design_digest(bound))
            self.assertEqual(implementation_changes(bound,root),[])
            plan["implementation"]["files"]={"../outside":"hash"}
            with self.assertRaises(ValueError): implementation_changes(plan,root)


class GuidanceAndRegionTests(unittest.TestCase):
    def test_corn_reference_matches_release_birth_samples_without_fixed_horizontal_speed(self):
        from attack_plan import host_catapult_reference
        # Captured native launch: ground=(297.72858,341), z=94.740509.
        reference=host_catapult_reference([297.72858,341-94.74050903320312],[300,321])
        self.assertEqual(reference["height"],300)
        self.assertEqual(reference["gravity"],2000)
        self.assertAlmostEqual(reference["flightTime"],1.1760063381594204)
        self.assertAlmostEqual(-math.sqrt(2*2000*300),-1095.4451150103323)
        duration=reference["flightTime"]
        self.assertAlmostEqual((846.09796-297.72858)/duration,466.298,places=3)
        self.assertAlmostEqual((805.5884-297.72858)/duration,431.85126,places=3)
        self.assertGreater(host_catapult_reference([300,100],[300,321])["flightTime"],duration)

    def test_standard_catapult_matches_three_native_lobber_profiles(self):
        from attack_plan import host_catapult_reference
        samples=[(94.74050903320312,1.1760063381594204),
                 (61.73468017578125,1.1491663871150317),
                 (87.25352478027344,1.1700195322529736)]
        for z,duration in samples:
            reference=host_catapult_reference([300,341-z],[300,321])
            self.assertAlmostEqual(reference["flightTime"],duration)
            self.assertEqual(reference["height"],300)
        plan=default_plan(); item=all_items(plan)[0][1]; item["trajectory"]["kind"]="parabola"
        times=[]; velocities=[]
        for target in ([500,320],[900,320]):
            sim=PlanSimulation(plan,PLANT,target,GRID,repeat=False); sim.step(0,target)
            b=sim.bullets[0]; times.append(b["ballistics"]["flightTime"]); velocities.append(b["velocity"][0])
            self.assertNotIn("flightTime",item["trajectory"]); self.assertNotIn("gravity",item["trajectory"])
            sim.step(times[-1],target)
            for actual,expected in zip(b["position"],target): self.assertAlmostEqual(actual,expected)
        self.assertEqual(times[0],times[1]); self.assertLess(velocities[0],velocities[1])

    def test_host_arc_recalculates_from_launch_height_and_survives_offscreen(self):
        plan=default_plan(); item=all_items(plan)[0][1]
        item["trajectory"]["kind"]="parabola"
        item["launch"]["offset"][1]=-621
        sim=PlanSimulation(plan,PLANT,TARGET,GRID,repeat=False,canvas=[1080,600]); sim.step(0,TARGET)
        bullet=sim.bullets[0]; duration=bullet["ballistics"]["flightTime"]
        sim.step(duration/2,TARGET)
        self.assertEqual(len(sim.bullets),1); self.assertLess(bullet["position"][1],-256)
        sim.step(duration/2,TARGET)
        for actual,expected in zip(bullet["position"],TARGET): self.assertAlmostEqual(actual,expected)
        self.assertFalse(sim.bullets)

    def test_legacy_custom_ballistics_migrates_without_overwriting_input(self):
        old=default_plan(); old["schemaVersion"]=4
        item=all_items(old)[0][1]; item["trajectory"].update(kind="parabola",gravity=240,flightTime=1.6)
        original=copy.deepcopy(old)
        new=upgrade_plan(old); t=all_items(new)[0][1]["trajectory"]
        self.assertEqual(new["schemaVersion"],5)
        self.assertNotIn("gravity",t); self.assertNotIn("flightTime",t)
        self.assertEqual(t["catapultProfile"],"pvzhe-0.30-standard")
        self.assertEqual(old,original)
        self.assertTrue(any("标准投手" in note for note in new["migrationNotes"]))
        malformed=copy.deepcopy(new); all_items(malformed)[0][1]["trajectory"]["flightTime"]=2
        with self.assertRaises(ValueError): validate_plan(malformed)

    def test_removed_bezier_is_preserved_as_disabled_identity_on_import(self):
        old=default_plan(); old["schemaVersion"]=3
        old["domain"]={"kind":"radius","radius":100}
        item=all_items(old)[0][1]; original_id=item["id"]
        item["trajectory"].update(kind="bezier",controls=[[100,-50],[200,-50]],end=[300,0])
        item["domain"]={"kind":"rect"}; item["guidance"].pop("trackingStrength")
        item["guidance"].update(maxTurnRate=120,response=6,angleFalloff=2)
        upgraded=upgrade_plan(old); new=all_items(upgraded)[0][1]
        self.assertEqual(new["id"],original_id); self.assertFalse(new["enabled"])
        self.assertNotIn("domain",upgraded); self.assertNotIn("domain",new)
        self.assertNotIn("controls",new["trajectory"])
        self.assertNotIn("maxTurnRate",new["guidance"])
        self.assertTrue(any("贝塞尔" in note for note in upgraded["migrationNotes"]))
        self.assertEqual(old["schemaVersion"],3)
    def test_preview_evicts_oldest_fifty_only_after_crossing_one_thousand(self):
        plan=default_plan(); original=copy.deepcopy(plan); item=all_items(plan)[0][1]
        sim=PlanSimulation(plan,PLANT,TARGET,GRID,repeat=False)
        for _ in range(1000): sim.spawn(item,"green",TARGET)
        self.assertEqual(len(sim.bullets),1000); self.assertEqual(sim.discarded,0)
        ray=copy.deepcopy(item); ray["carrier"]="ray"
        sim.spawn(ray,"blue",TARGET)
        self.assertEqual(len(sim.bullets),951); self.assertEqual(sim.discarded,50)
        self.assertEqual(sim.bullets[0]["creationIndex"],50)
        self.assertEqual(sim.bullets[-1]["creationIndex"],1000)
        for _ in range(49): sim.spawn(item,"green",TARGET)
        self.assertEqual(len(sim.bullets),1000); self.assertEqual(sim.discarded,50)
        sim.spawn(item,"green",TARGET)
        self.assertEqual(len(sim.bullets),951); self.assertEqual(sim.discarded,100)
        self.assertEqual(sim.bullets[0]["creationIndex"],100)
        self.assertEqual(sim.emitted,1051); self.assertEqual(plan,original); self.assertEqual(sim.plan,original)

    def test_parabola_solves_velocity_and_locks_each_delayed_shot_at_its_birth(self):
        plan=default_plan(); first=all_items(plan)[0][1]
        first["trajectory"].update(kind="parabola",direction=160,speed=10)
        first["guidance"]["initialAim"]=False
        first["route"]["rowOffset"]=2  # inactive route data cannot spoil the ballistic endpoint
        second=copy.deepcopy(first); second.update(id="delayed-parabola",time=.5)
        plan["groups"][0]["items"].append(second)
        sim=PlanSimulation(plan,PLANT,TARGET,GRID,repeat=False); sim.step(0,TARGET)
        a=sim.bullets[0]; before=a["velocity"][:]
        newer=[790,350]; sim.step(.5,newer)
        b=sim.bullets[1]
        self.assertEqual(a["targetSnapshot"],TARGET); self.assertEqual(b["targetSnapshot"],newer)
        self.assertAlmostEqual(a["velocity"][0],before[0])
        sim.step(a["ballistics"]["flightTime"]-.5,[650,300])
        for actual,expected in zip(a["position"],TARGET): self.assertAlmostEqual(actual,expected)
        sim.step(.5,[900,320])
        for actual,expected in zip(b["position"],newer): self.assertAlmostEqual(actual,expected)
        self.assertFalse(sim.bullets)

    def test_parabola_has_no_range_clamp_even_after_old_plan_import(self):
        plan=default_plan(); item=all_items(plan)[0][1]
        item["trajectory"]["kind"]="parabola"; item["maxTravelCells"]=.5
        with self.assertRaises(ValueError): validate_plan(plan)
        plan["schemaVersion"]=3; upgraded=upgrade_plan(plan)
        self.assertIsNone(all_items(upgraded)[0][1]["maxTravelCells"])
        sim=PlanSimulation(upgraded,PLANT,TARGET,GRID,repeat=False,canvas=[1080,600])
        sim.step(0,TARGET); bullet=sim.bullets[0]
        sim.step(2,TARGET)
        for a,b in zip(bullet["position"],TARGET): self.assertAlmostEqual(a,b)
        self.assertFalse(bullet["rangeReached"])

    def test_range_depends_on_travelled_cells_not_elapsed_seconds(self):
        for speed in (100,200):
            plan=default_plan(); item=all_items(plan)[0][1]
            item["maxTravelCells"]=2.5; item["trajectory"]["speed"]=speed
            sim=PlanSimulation(plan,PLANT,TARGET,GRID,repeat=False)
            sim.step(190/speed,TARGET); bullet=sim.bullets[0]
            self.assertAlmostEqual(bullet["travelCells"],190/80)
            sim.step(20/speed,TARGET)
            self.assertFalse(sim.bullets)
            self.assertAlmostEqual(bullet["position"][0],PLANT[0]+27+200)
            self.assertAlmostEqual(bullet["travelCells"],2.5)
        plan=default_plan(); item=all_items(plan)[0][1]; item["trajectory"]["speed"]=100
        item["maxTravelCells"]=30
        sim=PlanSimulation(plan,PLANT,TARGET,GRID,repeat=False); sim.step(8,TARGET)
        self.assertEqual(len(sim.bullets),1)  # no hidden five-second lifespan
        self.assertAlmostEqual(sim.bullets[0]["travelCells"],10)
        self.assertNotIn("lifetime",item)

    def test_distance_is_measured_in_normalized_grid_space_and_curves_accumulate(self):
        plan=default_plan(); item=all_items(plan)[0][1]
        item["trajectory"].update(speed=math.hypot(80,98),direction=math.degrees(math.atan2(98,80)))
        sim=PlanSimulation(plan,PLANT,TARGET,GRID,repeat=False); sim.step(1,TARGET)
        self.assertAlmostEqual(sim.bullets[0]["travelCells"],math.sqrt(2))
        item["trajectory"].update(kind="function",**function_preset("回旋线")); item["maxTravelCells"]=4
        coarse=PlanSimulation(plan,PLANT,TARGET,GRID,repeat=False)
        fine=PlanSimulation(plan,PLANT,TARGET,GRID,repeat=False)
        coarse.step(0,TARGET); fine.step(0,TARGET)
        a,b=coarse.bullets[0],fine.bullets[0]
        coarse.step(2,TARGET)
        for _ in range(240): fine.step(1/120,TARGET)
        self.assertTrue(a["rangeReached"]); self.assertTrue(b["rangeReached"])
        self.assertAlmostEqual(a["travelCells"],4); self.assertLess(math.dist(a["position"],b["position"]),.01)

    def test_seconds_and_half_row_legacy_values_are_migrated_explicitly(self):
        old=default_plan(); old["schemaVersion"]=2; old["trigger"]["rows"]=[0,.5]
        item=all_items(old)[0][1]; item["lifetime"]=5; item.pop("maxTravelCells")
        upgraded=upgrade_plan(old)
        self.assertEqual(upgraded["schemaVersion"],5)
        self.assertEqual(upgraded["trigger"]["rows"],[0,1])
        self.assertIsNone(all_items(upgraded)[0][1]["maxTravelCells"])
        self.assertNotIn("lifetime",all_items(upgraded)[0][1]); self.assertEqual(len(upgraded["migrationNotes"]),2)

    def test_error_decay_and_strength_have_distinct_effects(self):
        guide=new_item()["guidance"]; guide.update(trackingStrength=1)
        fractions=[]
        for degrees in (10,90,170):
            error=math.radians(degrees); fractions.append(abs(steer_angle(0,error,guide,.05))/error)
        self.assertGreater(fractions[0],fractions[1]); self.assertGreater(fractions[1],fractions[2])
        weak=steer_angle(0,math.pi*.9,guide,.05)
        guide["trackingStrength"]=2; strong=steer_angle(0,math.pi*.9,guide,.05)
        self.assertGreater(strong,weak)
        # Almost opposite does not get permanently stuck; tiny errors cannot overshoot.
        self.assertNotEqual(steer_angle(0,math.pi,guide,.05),0)
        self.assertLessEqual(abs(steer_angle(0,.001,guide,.05)),.001)

    def test_old_regions_upgrade_without_changing_custom_rectangle_footprint(self):
        old=default_plan(); old["schemaVersion"]=1
        old["trigger"]=dict(kind="rect",columns=[0,7],rows=[-2,2],selection="inherited-target")
        upgraded=upgrade_plan(old)
        self.assertEqual(upgraded["trigger"]["columns"],[0,8]); self.assertEqual(upgraded["trigger"]["rows"],[-2,3])
        old["trigger"]["kind"]="any"
        self.assertEqual(upgrade_plan(old)["trigger"]["rows"],[0,1])
        self.assertEqual(old["schemaVersion"],1)


if __name__=="__main__": unittest.main()
