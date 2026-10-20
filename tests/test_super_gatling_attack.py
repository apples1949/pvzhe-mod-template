"""Independent adapter guards; no game runtime/assets needed."""
import copy
import importlib.util
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from attack_plan import default_plan
from attack_model import digest

spec=importlib.util.spec_from_file_location("super_attack",Path(__file__).resolve().parents[1]/"examples/SuperGatling/prepare_attack.py")
adapter=importlib.util.module_from_spec(spec);spec.loader.exec_module(adapter)

class SuperAttackAdapterTests(unittest.TestCase):
    def inputs(self):
        plan=default_plan("mod/super-gatling-pea/SuperGatlingPea")
        binding=dict(attack="power",sourceModId="super-gatling-pea",preserveNormalAttack=True,
                     preserveActivationProbability=True,referencePoseMuzzleOffset=[28.8,-19.8])
        session=dict(sessionId="current",plant=dict(key=plan["character"]),plan=copy.deepcopy(plan),
                     grid=dict(size=[80,98]),binding=binding)
        result=dict(schemaVersion=3,status="confirmed",confirmed=True,sessionId="current",plan=plan,binding=copy.deepcopy(binding),
                    configSha256=digest(session),planSha256=digest(plan))
        return result,session

    def test_pixel_offset_velocity_and_duplicates_preserved(self):
        result,session=self.inputs();plan=result["plan"]
        first=plan["groups"][0]["items"][0];first["trajectory"]["direction"]=90
        duplicate=copy.deepcopy(first);duplicate["id"]="second";plan["groups"][0]["items"].append(duplicate)
        result["planSha256"]=digest(plan)
        value=adapter.compile_pattern(result,session)
        self.assertEqual(len(value["shots"]),2)
        self.assertAlmostEqual(value["shots"][0]["offset"][0],-1.8)
        self.assertAlmostEqual(value["shots"][0]["offset"][1],2.8)
        self.assertAlmostEqual(value["shots"][0]["velocity"][0],0)
        self.assertAlmostEqual(value["shots"][0]["velocity"][1],300)
        self.assertEqual(value["intervalRole"],"power-round-start-interval")
        self.assertEqual(value["roundIntervalSeconds"],1.5)
        self.assertNotIn("intervalSeconds",value)

    def test_identity_confirmation_and_binding_are_required(self):
        for field,value in (("confirmed",False),("status","cancelled"),("sessionId","old"),("planSha256","wrong"),("configSha256","wrong")):
            result,session=self.inputs();result[field]=value
            with self.assertRaises(ValueError):adapter.compile_pattern(result,session)
        result,session=self.inputs();result["binding"]["referencePoseMuzzleOffset"]=[0,0]
        with self.assertRaises(ValueError):adapter.compile_pattern(result,session)

    def test_unsupported_motion_and_trigger_are_not_silently_dropped(self):
        result,session=self.inputs();result["plan"]["trigger"]["rows"]=[0,2];result["planSha256"]=digest(result["plan"])
        with self.assertRaises(ValueError):adapter.compile_pattern(result,session)
        result,session=self.inputs();result["plan"]["groups"][0]["items"][0]["guidance"]["initialAim"]=True
        result["planSha256"]=digest(result["plan"])
        with self.assertRaises(ValueError):adapter.compile_pattern(result,session)

    def test_point_one_interval_starts_ten_overlapping_rounds_and_finishes_tail(self):
        result,session=self.inputs();plan=result["plan"];plan["intervalSeconds"]=.1
        first=plan["groups"][0]["items"][0];items=[]
        for n in range(30):
            item=copy.deepcopy(first);item["id"]=str(n);item["time"]=(n//10)*.25;items.append(item)
        plan["groups"][0]["items"]=items;result["planSha256"]=digest(plan)
        value=adapter.compile_pattern(result,session)
        self.assertEqual(value["roundCount"],10);self.assertEqual(value["shotsPerRound"],30)
        self.assertEqual(len(value["shots"]),300)
        self.assertEqual(max(s["time"] for s in value["shots"]),1.4)
        self.assertEqual(sorted(set(s["time"] for s in value["shots"] if s["id"]=="0")),[0,.1,.2,.3,.4,.5,.6,.7,.8,.9])
        for r in range(10):
            self.assertEqual([s["time"] for s in value["shots"] if s["round"]==r and s["id"] in ("0","10","20")],
                             [round(r*.1,9),round(r*.1+.25,9),round(r*.1+.5,9)])
        plan["intervalSeconds"]=.2;result["planSha256"]=digest(plan)
        slower=adapter.compile_pattern(result,session)
        self.assertEqual(slower["roundCount"],5);self.assertEqual(len(slower["shots"]),150)

    def test_tracking_strength_is_preserved_for_each_round(self):
        result,session=self.inputs();result["plan"]["intervalSeconds"]=.1
        result["plan"]["groups"][0]["items"][0]["guidance"]["trackingStrength"]=1
        result["planSha256"]=digest(result["plan"])
        pattern=adapter.compile_pattern(result,session)
        self.assertEqual(pattern["schemaVersion"],3)
        self.assertEqual(len(pattern["shots"]),10)
        self.assertTrue(all(shot["trackingStrength"]==1 for shot in pattern["shots"]))
