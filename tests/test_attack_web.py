import copy
import http.client
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from attack_web import ORIGIN_PRESETS, Editor, compile_recipe, default_recipe, make_server, validate_recipe, load_recipe


class RecipeTests(unittest.TestCase):
    def test_fan_is_simultaneous_and_uses_outer_settings(self):
        r = default_recipe()
        r.update(pattern="fan",count=5, spread=60, speed=900, intervalSeconds=.3, radius=31.123, originPreset="custom")
        p = compile_recipe(r)
        shots = p["groups"][0]["items"]
        self.assertEqual([s["trajectory"]["direction"] for s in shots], [-30, -15, 0, 15, 30])
        self.assertEqual({s["time"] for s in shots}, {0})
        self.assertEqual({s["trajectory"]["speed"] for s in shots}, {900})
        self.assertEqual(p["intervalSeconds"], .3)
        for shot in shots:
            offset = shot["launch"]["offset"]
            self.assertAlmostEqual(math.hypot(offset[0]-r["origin"][0],offset[1]-r["origin"][1]), r["radius"])
            self.assertAlmostEqual(math.degrees(math.atan2(offset[1]-r["origin"][1], offset[0]-r["origin"][0])), shot["trajectory"]["direction"])
        self.assertEqual(compile_recipe(r), p, "Stable item IDs must survive reopening")

    def test_rotated_patterns_and_parallel_births_match_export(self):
        node=shutil.which("node")
        if not node: self.skipTest("Optional Node runtime unavailable")
        module=(Path(__file__).resolve().parents[1]/"tools/attack_web/model.mjs").as_uri()
        recipes=[]
        for pattern in ("straight","fan","ring","lob","parallel","starfruit"):
            for direction in (0,90,270,360):
                r=default_recipe();r.update(pattern=pattern,direction=direction,count=3,spacing=18.5)
                if pattern=="lob": r.update(origin=list(ORIGIN_PRESETS["presets"]["lobber"]["origin"]),radius=0,originPreset="lobber")
                recipes.append(r)
        script=f"import {{launches}} from {json.dumps(module)}; console.log(JSON.stringify({json.dumps(recipes)}.map(r=>launches(r,[0,0]))));"
        previews=json.loads(subprocess.check_output([node,"--input-type=module","-e",script],text=True))
        for r,shots in zip(recipes,previews):
            exported=compile_recipe(r)["groups"][0]["items"]
            self.assertEqual(len(shots),len(exported))
            for shot,item in zip(shots,exported):
                self.assertAlmostEqual(shot["angle"]*180/math.pi,item["trajectory"]["direction"])
                self.assertAlmostEqual(shot["x"]+r["origin"][0],item["launch"]["offset"][0])
                self.assertAlmostEqual(shot["y"]+r["origin"][1],item["launch"]["offset"][1])
        r=default_recipe();r.update(pattern="parallel",count=3,direction=90,spacing=20)
        items=compile_recipe(r)["groups"][0]["items"]
        self.assertAlmostEqual(items[0]["launch"]["offset"][0]-items[2]["launch"]["offset"][0],40)

    def test_lob_uses_host_profile_and_snapshot_without_homing(self):
        from attack_plan import host_catapult_reference
        r=default_recipe();r.update(pattern="lob",ammo="homing",direction=275,speed=600,rangeCells=.1,intervalSeconds=30)
        item=compile_recipe(r)["groups"][0]["items"][0]
        self.assertEqual(item["trajectory"]["kind"],"parabola")
        self.assertTrue(item["guidance"]["initialAim"])
        self.assertEqual(item["guidance"]["trackingStrength"],0)
        self.assertIsNone(item["maxTravelCells"])
        self.assertEqual(item["launch"]["offset"],ORIGIN_PRESETS["presets"]["lobber"]["origin"])
        node=shutil.which("node")
        if not node:self.skipTest("Optional Node runtime unavailable")
        module=(Path(__file__).resolve().parents[1]/"tools/attack_web/model.mjs").as_uri()
        script=f"""
import {{catapult,Preview}} from {json.dumps(module)};
const origin=[297.72858,246.259491],plant=[300,321],target=[846.09796,321];
const c=catapult(origin,plant,target);
const p=new Preview({json.dumps(r)},origin,target,1080,600,[80,98],plant);
p.step(.05); const vx=p.bullets[0].ballistics.vx;
p.step(.05,[100,100]);const after=p.bullets[0].ballistics.vx;
const survives=p.bullets.length;
for(let i=0;i<30;i++)p.step(.05,[100,100]);
console.log(JSON.stringify({{c,vx,after,survives,end:p.bullets.length,x:origin[0]+c.vx*c.flightTime,y:origin[1]+c.vy*c.flightTime+.5*c.gravity*c.flightTime**2}}));
"""
        out=json.loads(subprocess.check_output([node,"--input-type=module","-e",script],text=True))
        host=host_catapult_reference([297.72858,246.259491],[300,321])
        self.assertAlmostEqual(out["c"]["flightTime"],host["flightTime"])
        self.assertAlmostEqual(out["x"],836.09796);self.assertAlmostEqual(out["y"],321)
        self.assertEqual(out["vx"],out["after"])
        self.assertEqual(out["survives"],1);self.assertEqual(out["end"],0)
        with tempfile.TemporaryDirectory() as temp:
            old=default_recipe();old.update(schemaVersion=5,pattern="bidirectional")
            path=Path(temp)/"old.json";path.write_text(json.dumps({k:v for k,v in old.items() if k not in ("angleOffset","trackingStrength","shotDelaySeconds","deploymentSeconds")}),encoding="utf-8")
            migrated,note=load_recipe(path)
            self.assertEqual(migrated["pattern"],"ring");self.assertEqual(migrated["count"],2)

    def test_lob_keeps_native_arc_ignoring_speed_multipliers(self):
        r=default_recipe();r.update(pattern="lob",speed=600)
        item=compile_recipe(r)["groups"][0]["items"][0]
        self.assertNotIn("catapultSpeedScale",item["trajectory"])
        self.assertEqual(item["trajectory"]["speed"],300)
        doc=dict(format="pvzhe.attack-composition",schemaVersion=2,id="lob-test",character=r["character"],root=dict(kind="group",id="root",name="root",enabled=True,speedMultiplier=3,rateMultiplier=1,rangeMultiplier=1,children=[dict(kind="attack",id="lob-layer",name="lob",enabled=True,recipe=r)]))
        self.assertNotIn("catapultSpeedScale",compile_recipe(doc)["groups"][0]["items"][0]["trajectory"])
        node=shutil.which("node")
        if not node:self.skipTest("Optional Node runtime unavailable")
        module=(Path(__file__).resolve().parents[1]/"tools/attack_web/model.mjs").as_uri()
        script=f"import {{catapult}} from {json.dumps(module)};console.log(JSON.stringify([1,2,10].map(s=>catapult([300,230],[300,321],[800,321],s))));"
        profiles=json.loads(subprocess.check_output([node,"--input-type=module","-e",script],text=True))
        self.assertEqual(profiles[0],profiles[1]);self.assertEqual(profiles[0],profiles[2])

    def test_guidance_strength_and_velocity_offset_are_independent(self):
        from attack_plan import steer_angle
        node=shutil.which("node")
        if not node:self.skipTest("Optional Node runtime unavailable")
        module=(Path(__file__).resolve().parents[1]/"tools/attack_web/model.mjs").as_uri()
        r=default_recipe();r.update(pattern="straight",ammo="homing",trackingStrength=0,intervalSeconds=30)
        normal=default_recipe();normal.update(pattern="parallel",count=3,radius=40,originPreset="custom")
        offset=copy.deepcopy(normal);offset["angleOffset"]=60
        before=compile_recipe(normal)["groups"][0]["items"];after=compile_recipe(offset)["groups"][0]["items"]
        self.assertEqual([i["launch"] for i in before],[i["launch"] for i in after])
        self.assertEqual(after[0]["trajectory"]["direction"],60)
        guide=compile_recipe(r)["groups"][0]["items"][0]["guidance"]
        self.assertTrue(guide["initialAim"]);self.assertEqual(guide["trackingStrength"],0)
        samples=[(s,e) for s in (0,1,2) for e in (.1,1.5,3.14)]
        script=f"""
import {{steer,Preview}} from {json.dumps(module)};
const samples={json.dumps(samples)};
const p=new Preview({json.dumps(r)},[100,100],[100,400]);p.step(.05);const angle=p.bullets[0].angle;p.step(.05,[400,100]);
const strong=new Preview({{...{json.dumps(r)},trackingStrength:2}},[2000,300],[800,300]);strong.step(.05);const outside=strong.bullets.length;
for(let i=0;i<90;i++)strong.step(.05,[800,300]);
console.log(JSON.stringify({{turns:samples.map(([s,e])=>steer(0,e,.016,s)),angle,after:p.bullets[0].angle,outside,end:strong.bullets.length}}));
"""
        out=json.loads(subprocess.check_output([node,"--input-type=module","-e",script],text=True))
        for (strength,error),turn in zip(samples,out["turns"]):
            self.assertAlmostEqual(turn,steer_angle(0,error,dict(trackingStrength=strength,model="host-guidance-v2",trackingDelaySeconds=.5),.016))
        self.assertAlmostEqual(out["angle"],math.pi/2);self.assertEqual(out["angle"],out["after"])
        self.assertEqual(out["outside"],1);self.assertEqual(out["end"],0)
        for value in (-.1,2.1,.15):
            bad=default_recipe();bad["trackingStrength"]=value
            with self.assertRaises(ValueError):validate_recipe(bad)

    def test_cross_ninety_offset_is_tangent_before_any_guidance(self):
        from attack_plan import PlanSimulation
        node=shutil.which("node")
        if not node:self.skipTest("Optional Node runtime unavailable")
        module=(Path(__file__).resolve().parents[1]/"tools/attack_web/model.mjs").as_uri()
        recipes=[]
        for ammo,strength in (("normal",0),):
            r=default_recipe();r.update(pattern="ring",count=4,originPreset="custom",origin=[0,0],radius=50,angleOffset=90,direction=37,ammo=ammo,trackingStrength=strength,intervalSeconds=30)
            recipes.append(r)
        script=f"""
import {{Preview}} from {json.dumps(module)};
console.log(JSON.stringify({json.dumps(recipes)}.map(r=>{{const p=new Preview(r,[500,300],[800,420],2000,1000,[80,98],[500,300]);p.volley();p.next=30;const before=p.bullets.map(b=>[b.x,b.y]);p.step(.001);return before.map((v,i)=>[v,[p.bullets[i].x,p.bullets[i].y]]);}})));
"""
        cases=json.loads(subprocess.check_output([node,"--input-type=module","-e",script],text=True))
        for r,shots in zip(recipes,cases):
            plan=compile_recipe(r);sim=PlanSimulation(plan,[500,300],[800,420],dict(size=[80,98]),False)
            for item in plan["groups"][0]["items"]:sim.spawn(item,"white",[800,420])
            for b,(before,after) in zip(sim.bullets,shots):
                radial=[before[0]-500,before[1]-300];movement=[after[i]-before[i] for i in (0,1)]
                self.assertAlmostEqual(sum(radial[i]*movement[i] for i in (0,1)),0,places=8)
                self.assertGreater(math.hypot(*movement),0)
                sim.advance(b,.001,[800,420])
                for i in (0,1):self.assertAlmostEqual(b["origin"][i],before[i]);self.assertAlmostEqual(b["position"][i],after[i])

    def test_six_ring_120_degree_paths_follow_hexagon_edges(self):
        node=shutil.which("node")
        if not node:self.skipTest("Optional Node runtime unavailable")
        module=(Path(__file__).resolve().parents[1]/"tools/attack_web/model.mjs").as_uri()
        recipes=[]
        for anchor in (0,37):
            for offset in (120,240):
                r=default_recipe();r.update(pattern="ring",count=6,ammo="normal",radius=80,originPreset="custom",origin=[13,-22],direction=anchor,angleOffset=offset,intervalSeconds=30)
                recipes.append(r)
        script=f"""
import {{Preview}} from {json.dumps(module)};
console.log(JSON.stringify({json.dumps(recipes)}.map(r=>{{
  const p=new Preview(r,[513,278],[800,420],2000,1000);p.volley();p.next=30;
  const starts=p.bullets.map(b=>[b.x,b.y]);const duration=r.radius/r.speed;
  while(p.time<duration-1e-9)p.step(Math.min(.05,duration-p.time));
  return {{starts,ends:p.bullets.map(b=>[b.x,b.y])}};
}})));
"""
        results=json.loads(subprocess.check_output([node,"--input-type=module","-e",script],text=True))
        for r,result in zip(recipes,results):
            items=compile_recipe(r)["groups"][0]["items"]
            for i,item in enumerate(items):
                next_index=(i+(1 if r["angleOffset"]==120 else -1))%6
                next_start=result["starts"][next_index]
                heading=math.radians(item["trajectory"]["direction"])
                endpoint=[500+item["launch"]["offset"][0]+math.cos(heading)*r["radius"],300+item["launch"]["offset"][1]+math.sin(heading)*r["radius"]]
                for axis in (0,1):
                    self.assertAlmostEqual(endpoint[axis],next_start[axis])
                    self.assertAlmostEqual(result["ends"][i][axis],next_start[axis])

    def test_full_fan_has_no_duplicate_and_legacy_cross_is_four_ring(self):
        node=shutil.which("node")
        if not node:self.skipTest("Optional Node runtime unavailable")
        module=(Path(__file__).resolve().parents[1]/"tools/attack_web/model.mjs").as_uri()
        recipes=[]
        for count in (1,4,5,6,12):
            fan=default_recipe();fan.update(pattern="fan",spread=360,count=count)
            ring=copy.deepcopy(fan);ring["pattern"]="ring"
            self.assertEqual(compile_recipe(fan),compile_recipe(ring))
            headings=[i["trajectory"]["direction"] for i in compile_recipe(fan)["groups"][0]["items"]]
            self.assertEqual(len(set(headings)),count)
            recipes.append(fan)
        script=f"import {{angles}} from {json.dumps(module)};console.log(JSON.stringify({json.dumps(recipes)}.map(angles)));"
        for r,headings in zip(recipes,json.loads(subprocess.check_output([node,"--input-type=module","-e",script],text=True))):
            self.assertEqual(headings,[i["trajectory"]["direction"] for i in compile_recipe(r)["groups"][0]["items"]])
        with tempfile.TemporaryDirectory() as temp:
            old=default_recipe();old.update(schemaVersion=10,pattern="cross",count=99)
            path=Path(temp)/"old.json";path.write_text(json.dumps(old),encoding="utf-8")
            migrated,note=load_recipe(path)
            self.assertEqual(migrated["pattern"],"ring");self.assertEqual(migrated["count"],4)
            self.assertEqual(len(compile_recipe(migrated)["groups"][0]["items"]),4)

    def test_angle_offset_360_and_legacy_wrapping(self):
        r=default_recipe();r["angleOffset"]=360
        expected=copy.deepcopy(r);expected["angleOffset"]=0
        self.assertEqual(compile_recipe(r),compile_recipe(expected))
        for angle in (-1,360.1,365):
            bad=copy.deepcopy(r);bad["angleOffset"]=angle
            with self.assertRaises(ValueError):validate_recipe(bad)
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"old.json";old=copy.deepcopy(r);old.update(schemaVersion=11,angleOffset=-120)
            path.write_text(json.dumps(old),encoding="utf-8")
            upgraded,note=load_recipe(path);self.assertEqual(upgraded["angleOffset"],240)
            old.update(schemaVersion=17,angleOffset=365)
            path.write_text(json.dumps(old),encoding="utf-8")
            upgraded,note=load_recipe(path);self.assertEqual(upgraded["angleOffset"],5)
            self.assertTrue(note)

    def test_delayed_volley_schedule_overlap_and_target_sampling(self):
        r=default_recipe();r.update(pattern="fan",count=5,spread=45,shotDelaySeconds=.1,intervalSeconds=30)
        self.assertEqual([i["time"] for i in compile_recipe(r)["groups"][0]["items"]],[0,.1,.2,.3,.4])
        for pattern in ("straight","lob"):
            one=copy.deepcopy(r);one["pattern"]=pattern
            self.assertEqual([i["time"] for i in compile_recipe(one)["groups"][0]["items"]],[0])
        for gap in (.005,5.01,-.1):
            bad=copy.deepcopy(r);bad["shotDelaySeconds"]=gap
            with self.assertRaises(ValueError):validate_recipe(bad)
        node=shutil.which("node")
        if not node:self.skipTest("Optional Node runtime unavailable")
        module=(Path(__file__).resolve().parents[1]/"tools/attack_web/model.mjs").as_uri()
        script=f"""
import {{Preview}} from {json.dumps(module)};
const r={json.dumps(r)};
const p=new Preview(r,[100,100],[800,100]);const counts=[];
p.step(0);counts.push(p.emitted);for(let i=0;i<4;i++){{p.step(.05);p.step(.05);counts.push(p.emitted);}}
const births=p.bullets.map(b=>b.born);
const overlap=new Preview({{...r,count:3,shotDelaySeconds:.15,intervalSeconds:.2}},[100,100],[800,100]);for(let i=0;i<8;i++)overlap.step(.05);
const aim=new Preview({{...r,count:2,spread:0,ammo:'homing',trackingStrength:0}},[100,100],[500,100]);aim.step(.05);aim.step(.05,[100,500]);
const headings=aim.bullets.map(b=>b.angle);
p.reset(r,[100,100],[800,100]);
console.log(JSON.stringify({{counts,births,overlap:overlap.bullets.map(b=>b.born),headings,pendingAfterReset:p.pending.length}}));
"""
        out=json.loads(subprocess.check_output([node,"--input-type=module","-e",script],text=True))
        self.assertEqual(out["counts"],[1,2,3,4,5])
        for actual,expected in zip(out["births"],[0,.1,.2,.3,.4]):self.assertAlmostEqual(actual,expected)
        self.assertEqual(len(out["overlap"]),6)
        for actual,expected in zip(out["overlap"],[0,.15,.2,.3,.35,.4]):self.assertAlmostEqual(actual,expected)
        self.assertAlmostEqual(out["headings"][0],0);self.assertAlmostEqual(out["headings"][1],math.pi/2)
        self.assertEqual(out["pendingAfterReset"],0)
        with tempfile.TemporaryDirectory() as temp:
            old=default_recipe();old.pop("shotDelaySeconds");old["schemaVersion"]=12
            path=Path(temp)/"old.json";path.write_text(json.dumps(old),encoding="utf-8")
            migrated,note=load_recipe(path);self.assertEqual(migrated["shotDelaySeconds"],0)

    def test_starfruit_uses_release_five_directions_not_even_ring(self):
        r=default_recipe();r.update(pattern="starfruit",count=99,shotDelaySeconds=.1)
        items=compile_recipe(r)["groups"][0]["items"]
        self.assertEqual([i["trajectory"]["direction"] for i in items],[-30,-90,180,90,30])
        self.assertEqual([i["time"] for i in items],[0,.1,.2,.3,.4])
        self.assertEqual(len(items),5)
        r["direction"]=90
        self.assertEqual([i["trajectory"]["direction"] for i in compile_recipe(r)["groups"][0]["items"]],[60,0,-90,180,120])

    def test_center_uses_native_starfruit_ports_and_rotates_with_anchor(self):
        node=shutil.which("node")
        if not node:self.skipTest("Optional Node runtime unavailable")
        module=(Path(__file__).resolve().parents[1]/"tools/attack_web/model.mjs").as_uri()
        recipes=[]
        for turn in (0,90):
            r=default_recipe();r.update(pattern="starfruit",originPreset="center",origin=[0,0],radius=0,direction=turn)
            recipes.append(r)
        ports=ORIGIN_PRESETS["presets"]["center"]["shotOffsets"]
        script=f"import {{launches}} from {json.dumps(module)};console.log(JSON.stringify({json.dumps(recipes)}.map(r=>launches({{...r,originShotOffsets:{json.dumps(ports)}}},[500,300]))));"
        cases=json.loads(subprocess.check_output([node,"--input-type=module","-e",script],text=True))
        for r,shots in zip(recipes,cases):
            items=compile_recipe(r)["groups"][0]["items"]
            self.assertEqual(len({tuple(i["launch"]["offset"]) for i in items}),5)
            for i,(item,shot) in enumerate(zip(items,shots)):
                point=item["launch"]["offset"]
                self.assertAlmostEqual(point[0]+500,shot["x"]);self.assertAlmostEqual(point[1]+300,shot["y"])
                expected=ports[i] if r["direction"]==0 else [-ports[i][1],ports[i][0]]
                for a,b in zip(point,expected):self.assertAlmostEqual(a,b)
        wrong=copy.deepcopy(recipes[0]);wrong["pattern"]="ring"
        validate_recipe(wrong)
        self.assertEqual(len({tuple(i["launch"]["offset"]) for i in compile_recipe(wrong)["groups"][0]["items"]}),1)

    def test_preview_contact_uses_released_rectangle_and_stops_oscillation(self):
        node=shutil.which("node")
        if not node:self.skipTest("Optional Node runtime unavailable")
        module=(Path(__file__).resolve().parents[1]/"tools/attack_web/model.mjs").as_uri()
        r=default_recipe();r.update(pattern="straight",ammo="homing",trackingStrength=2,intervalSeconds=60,speed=3000)
        script=f"""
import {{Preview,touchesTarget}} from {json.dumps(module)};
const p=new Preview({json.dumps(r)},[2000,300],[800,300]);p.step(.05);const outside=p.bullets.length;
for(let i=0;i<30;i++)p.step(.05);
console.log(JSON.stringify({{outside,end:p.bullets.length,near:touchesTarget(0,-52,1000,0,[500,0],[-18,-37,44,70]),miss:touchesTarget(0,-52.01,1000,0,[500,0],[-18,-37,44,70]),inside:touchesTarget(500,0,0,0,[500,0]),cross:touchesTarget(0,0,1000,0,[500,0],[-18,-37,44,70]),behind:touchesTarget(550,0,100,0,[500,0],[-18,-37,44,70])}}));
"""
        out=json.loads(subprocess.check_output([node,"--input-type=module","-e",script],text=True))
        self.assertEqual(out,{"outside":1,"end":0,"near":True,"miss":False,"inside":True,"cross":True,"behind":False})

    def test_full_delay_and_interval_limits_compile_without_truncation(self):
        r=default_recipe();r.update(pattern="fan",count=120,shotDelaySeconds=5,intervalSeconds=60)
        plan=compile_recipe(r)
        self.assertEqual(plan["intervalSeconds"],60)
        self.assertEqual(plan["groups"][0]["items"][-1]["time"],595)
        r["intervalSeconds"]=60.1
        with self.assertRaises(ValueError):validate_recipe(r)

    def test_parallel_deployment_matches_compiled_python_preview(self):
        from attack_plan import PlanSimulation
        node=shutil.which("node")
        if not node:self.skipTest("Optional Node runtime unavailable")
        module=(Path(__file__).resolve().parents[1]/"tools/attack_web/model.mjs").as_uri()
        r=default_recipe();r.update(pattern="parallel",count=3,spacing=98,direction=90,deploymentSeconds=.15,intervalSeconds=60)
        plant=[300,300];origin=[plant[i]+r["origin"][i] for i in (0,1)];target=[700,300]
        script=f"import {{Preview}} from {json.dumps(module)};const r={json.dumps(r)},out=[];for(const time of [0,.075,.15,.2]){{const p=new Preview(r,{json.dumps(origin)},{json.dumps(target)});p.volley();while(p.time<time-1e-9)p.step(Math.min(.05,time-p.time));out.push(p.bullets.map(b=>[b.x,b.y,b.canHit??true,b.travelCells]));}}console.log(JSON.stringify(out));"
        samples=json.loads(subprocess.check_output([node,"--input-type=module","-e",script],text=True))
        plan=compile_recipe(r)
        for time,points in zip((0,.075,.15,.2),samples):
            sim=PlanSimulation(plan,plant,target,grid={"size":[80,98]})
            for item in plan["groups"][0]["items"]:sim.spawn(item,"green",target)
            for b,point in zip(sim.bullets,points):
                sim.advance(b,time,target)
                for a,c in zip(b["position"],point[:2]):self.assertAlmostEqual(a,c)
                self.assertEqual(b["canHit"],point[2])
                self.assertAlmostEqual(b["travelCells"],point[3])
                if time<.15:self.assertFalse(b["canHit"])
        self.assertEqual(len({tuple(p[:2]) for p in samples[0]}),1)
        r["deploymentSeconds"]=0
        with self.assertRaises(ValueError):compile_recipe(r)
        r["schemaVersion"]=16
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"old-parallel.json";path.write_text(json.dumps(r),encoding="utf-8")
            migrated,note=load_recipe(path)
            self.assertEqual(migrated["deploymentSeconds"],.15)
            self.assertTrue(note)
            self.assertTrue(all("deployment" in item["launch"] for item in compile_recipe(migrated)["groups"][0]["items"]))
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")),r)

    def test_radius_is_independent_of_origin_presets(self):
        for preset in ORIGIN_PRESETS["presets"]:
            for pattern in ("fan","starfruit"):
                r=default_recipe();r.update(pattern=pattern,originPreset=preset,origin=list(ORIGIN_PRESETS["presets"][preset]["origin"]))
                before=compile_recipe(r)["groups"][0]["items"]
                r["radius"]=37.25
                after=compile_recipe(r)["groups"][0]["items"]
                self.assertEqual(r["originPreset"],preset)
                for a,b in zip(before,after):
                    self.assertAlmostEqual(math.dist(a["launch"]["offset"],b["launch"]["offset"]),37.25)

    def test_origin_merge_preserves_old_recipes(self):
        self.assertNotIn("starfruit", ORIGIN_PRESETS["presets"])
        self.assertEqual(ORIGIN_PRESETS["presets"]["center"]["radius"],0)
        for preset,radius,expected in (("starfruit",0,"center"),("center",40,"custom")):
            old=default_recipe();old.update(schemaVersion=14,pattern="starfruit",originPreset=preset,origin=[0,0],radius=radius)
            with tempfile.TemporaryDirectory() as directory:
                path=Path(directory)/"old.json";path.write_text(json.dumps(old),encoding="utf-8")
                migrated,note=load_recipe(path)
                self.assertEqual(migrated["originPreset"],expected)
                self.assertEqual(migrated["radius"],radius)
                self.assertTrue(note)
                self.assertEqual(json.loads(path.read_text(encoding="utf-8")),old)

    def test_fractional_range_export_and_preview_expiry(self):
        r=default_recipe()
        r.update(pattern="straight",rangeCells=1.25,intervalSeconds=30)
        self.assertEqual(compile_recipe(r)["groups"][0]["items"][0]["maxTravelCells"],1.25)
        node=shutil.which("node")
        if not node: self.skipTest("Optional Node runtime unavailable")
        module=(Path(__file__).resolve().parents[1]/"tools/attack_web/model.mjs").as_uri()
        script=f"""
import {{Preview}} from {json.dumps(module)};
const r={json.dumps(r)};
const p=new Preview(r,[500,300],[800,300],2000,2000,[80,98]);
for(let i=0;i<6;i++)p.step(.05);
const before=p.bullets.length;
for(let i=0;i<2;i++)p.step(.05);
console.log(JSON.stringify([before,p.bullets.length]));
"""
        self.assertEqual(json.loads(subprocess.check_output([node,"--input-type=module","-e",script],text=True)),[1,0])
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"old.json"
            old=default_recipe();old.pop("rangeCells")
            old.pop("direction")
            old.pop("spacing")
            old.pop("shotDelaySeconds",None);old["schemaVersion"]=3
            path.write_text(json.dumps({k:v for k,v in old.items() if k not in ("angleOffset","trackingStrength","shotDelaySeconds","deploymentSeconds")}),encoding="utf-8")
            migrated,note=load_recipe(path)
            self.assertEqual(migrated["rangeCells"],0)
            self.assertIsNone(compile_recipe(migrated)["groups"][0]["items"][0]["maxTravelCells"])

    def test_ring_no_duplicate_endpoint_and_single_center(self):
        r = default_recipe()
        r.update(pattern="ring", count=4)
        self.assertEqual([s["trajectory"]["direction"] for s in compile_recipe(r)["groups"][0]["items"]], [0, 90, 180, -90])
        r.update(pattern="fan", count=1, spread=90)
        self.assertEqual(compile_recipe(r)["groups"][0]["items"][0]["trajectory"]["direction"], 0)

    def test_ammo_is_independent_and_straight_has_no_implicit_homing(self):
        r = default_recipe()
        r.update(pattern="straight", count=20)
        p = compile_recipe(r)
        self.assertEqual(len(p["groups"][0]["items"]), 1)
        self.assertEqual(p["groups"][0]["items"][0]["guidance"]["trackingStrength"], 0)
        r["ammo"] = "homing"
        self.assertEqual(compile_recipe(r)["groups"][0]["items"][0]["guidance"]["trackingStrength"], 2)

    def test_reject_bad_values_and_complex_plan(self):
        for key, value in (("count", 3.2), ("count", True), ("speed", float("nan")),
                           ("spread", 361), ("intervalSeconds", 0), ("ammo", "arbitrary"),
                           ("radius", float("inf"))):
            r = default_recipe()
            r[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                validate_recipe(r)
        r = default_recipe()
        r["groups"] = []
        with self.assertRaises(ValueError):
            compile_recipe(r)

    def test_draft_cancel_and_reopen_preserve_project_recipe(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / "recipe.json"
            original = default_recipe("demo-plant")
            path.write_text(json.dumps(original), encoding="utf-8")
            e = Editor(root / "first.json", path)
            changed = copy.deepcopy(e.recipe)
            changed["pattern"] = "fan"
            changed["count"] = 17
            e.accept("save", changed)
            self.assertFalse(e.output.exists())
            e.accept("cancel", None)
            self.assertEqual(json.loads(path.read_text()), original)
            e2 = Editor(root / "second.json", path, recover=True)
            self.assertEqual(e2.recipe["count"], 17)
            e2.accept("confirm", e2.recipe)
            result = json.loads(e2.output.read_text(encoding="utf-8"))
            self.assertEqual(result["status"], "confirmed")
            self.assertEqual(len(result["plan"]["groups"][0]["items"]), 17)
            with self.assertRaises(ValueError):
                e2.accept("confirm", e2.recipe)

    def test_browser_and_export_angles_agree_and_preview_is_bounded(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("Optional Node runtime unavailable")
        module = (Path(__file__).resolve().parents[1] / "tools/attack_web/model.mjs").as_uri()
        recipes = []
        for pattern, count in (("straight", 20), ("fan", 1), ("fan", 9), ("ring", 12)):
            r = default_recipe()
            r.update(pattern=pattern, count=count)
            recipes.append(r)
        script = f"""
import {{angles,Preview}} from {json.dumps(module)};
const recipes={json.dumps(recipes)};
const r={{...recipes[2],count:120,spread:0,speed:30,intervalSeconds:.1}};
const sim=new Preview(r,[500,300],[800,300],100000,100000);
for(let i=0;i<240;i++)sim.step(.05);
const straight=new Preview({{...r,pattern:'straight',ammo:'normal'}},[100,100],[100,400]);
straight.step(.05);
console.log(JSON.stringify({{angles:recipes.map(angles),live:sim.bullets.length,evicted:sim.evicted,y:straight.bullets[0].y}}));
"""
        out = json.loads(subprocess.check_output([node, "--input-type=module", "-e", script], text=True))
        for r, angles in zip(recipes, out["angles"]):
            expected = [s["trajectory"]["direction"] for s in compile_recipe(r)["groups"][0]["items"]]
            self.assertEqual(angles, expected)
        self.assertLessEqual(out["live"], 1000)
        self.assertGreater(out["evicted"], 0)
        self.assertEqual(out["evicted"] % 50, 0)
        self.assertEqual(out["y"], 100)

    def test_radius_birth_positions_match_export_and_old_file_is_preserved(self):
        node = shutil.which("node")
        r = default_recipe()
        r.update(pattern="ring", count=4, radius=63.75, originPreset="custom")
        if node:
            module = (Path(__file__).resolve().parents[1] / "tools/attack_web/model.mjs").as_uri()
            script = f"import {{Preview}} from {json.dumps(module)};const s=new Preview({json.dumps(r)},[300+{r["origin"][0]},321+{r["origin"][1]}],[800,321]);s.volley();console.log(JSON.stringify(s.bullets.map(b=>[b.x-300,b.y-321])));"
            positions = json.loads(subprocess.check_output([node,"--input-type=module","-e",script],text=True))
            for position, shot in zip(positions, compile_recipe(r)["groups"][0]["items"]):
                for actual, expected in zip(position, shot["launch"]["offset"]):
                    self.assertAlmostEqual(actual, expected)
        r["radius"] = 0
        self.assertTrue(all(s["launch"]["offset"] == r["origin"] for s in compile_recipe(r)["groups"][0]["items"]))
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/"old.json"
            old = default_recipe()
            old.update(schemaVersion=1, origin=[27,-17])
            old.pop("radius")
            old.pop("originPreset")
            old.pop("rangeCells")
            old.pop("direction")
            old.pop("spacing")
            old.pop("shotDelaySeconds",None)
            source = json.dumps({k:v for k,v in old.items() if k not in ("angleOffset","trackingStrength","shotDelaySeconds","deploymentSeconds")})
            path.write_text(source,encoding="utf-8")
            upgraded, note = load_recipe(path)
            self.assertEqual(upgraded["schemaVersion"],19)
            self.assertEqual(upgraded["origin"],[27,-17])
            self.assertEqual(upgraded["radius"],0)
            self.assertEqual(upgraded["originPreset"],"custom")
            self.assertTrue(note)
            self.assertEqual(path.read_text(encoding="utf-8"),source)

    def test_presets_default_and_custom_offsets_are_not_silently_reset(self):
        r=default_recipe()
        self.assertEqual(r["originPreset"],"pea-front")
        self.assertEqual(r["pattern"],"straight")
        self.assertEqual(r["count"],1)
        r["origin"][0]+=0.12345
        with self.assertRaises(ValueError):
            validate_recipe(r)
        r["originPreset"]="custom"
        r["radius"]=23.5
        shot=compile_recipe(r)["groups"][0]["items"][0]
        self.assertAlmostEqual(shot["launch"]["offset"][0],r["origin"][0]+23.5)
        self.assertAlmostEqual(shot["launch"]["offset"][1],r["origin"][1])
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"v2.json"
            old={k:v for k,v in r.items() if k not in ("origin","originPreset","rangeCells","direction","spacing","shotDelaySeconds","deploymentSeconds")}
            old["schemaVersion"]=2
            path.write_text(json.dumps({k:v for k,v in old.items() if k not in ("angleOffset","trackingStrength","shotDelaySeconds","deploymentSeconds")}),encoding="utf-8")
            upgraded,note=load_recipe(path)
            self.assertEqual(upgraded["origin"],[0,0])
            self.assertEqual(upgraded["radius"],23.5)
            self.assertEqual(upgraded["originPreset"],"custom")

    def test_local_server_rejects_wrong_session_and_cross_origin(self):
        with tempfile.TemporaryDirectory() as temp:
            e = Editor(Path(temp) / "result.json")
            server = make_server(e)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                conn = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=3)
                conn.request("GET", "/wrong/api/state")
                response = conn.getresponse()
                self.assertEqual(response.status, 404)
                response.read()
                conn.request("GET", f"/{e.token}/api/state")
                self.assertEqual(json.loads(conn.getresponse().read())["recipe"]["id"], e.recipe["id"])
                payload = json.dumps(dict(action="confirm", recipe=e.recipe, sessionId=e.session_id, transactionId=e.transaction_id))
                conn.request("POST", f"/{e.token}/api/action", payload,
                             {"Content-Type": "application/json", "Origin": "https://example.com"})
                response = conn.getresponse()
                self.assertEqual(response.status, 403)
                response.read()
                self.assertFalse(e.output.exists())
                stale = json.loads(payload)
                stale["transactionId"] = "old-service-at-same-url"
                conn.request("POST", f"/{e.token}/api/action", json.dumps(stale), {"Content-Type":"application/json"})
                response = conn.getresponse()
                self.assertEqual(response.status,400)
                response.read()
                self.assertFalse(e.output.exists())
                conn.request("POST", f"/{e.token}/api/action", payload, {"Content-Type": "application/json"})
                self.assertEqual(json.loads(conn.getresponse().read())["status"], "confirmed")
                self.assertTrue(e.output.exists())
                conn.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)


class NativeDistanceTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"),"Optional Node runtime unavailable")
    def test_vertical_distance_uses_grid_width_not_height(self):
        r=default_recipe();r.update(originPreset="custom",origin=[0,0],radius=0,direction=90,rangeCells=2.5,intervalSeconds=60)
        module=(Path(__file__).resolve().parents[1]/"tools/attack_web/model.mjs").as_uri()
        script=f"import {{Preview}} from {json.dumps(module)};const p=new Preview({json.dumps(r)},[500,100],[1000,500]);for(let i=0;i<13;i++)p.step(.05);const before=p.bullets.length;p.step(.05);console.log(JSON.stringify([before,p.bullets.length]));"
        self.assertEqual(json.loads(subprocess.check_output(['node','--input-type=module','-e',script],text=True)),[1,0])
        from attack_plan import PlanSimulation
        sim=PlanSimulation(compile_recipe(r),[500,100],[1000,500],dict(size=[80,98]),False)
        sim.step(.65,[1000,500]);self.assertEqual(len(sim.bullets),1)
        sim.step(.05,[1000,500]);self.assertEqual(len(sim.bullets),0)

    def test_unknown_native_semantics_rejected(self):
        from attack_plan import validate_plan
        plan=compile_recipe(default_recipe());item=plan['groups'][0]['items'][0]
        self.assertEqual(plan['trigger'],dict(kind='inherited',selection='inherited-target'))
        item['distanceModel']='guess'
        with self.assertRaises(ValueError):validate_plan(plan)
