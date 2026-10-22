"""Seeded cross-language geometry and composition boundary tests, without game assets."""
import importlib.util
import json
import math
from pathlib import Path
import random
import shutil
import subprocess
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from attack_web import default_recipe,compile_recipe,ORIGIN_PRESETS
from attack_composition import layers,validate
from attack_plan import launch_position

def group(identity,children,speed=1,rate=1):
    return dict(kind='group',id=identity,name=identity,enabled=True,children=children,speedMultiplier=speed,rateMultiplier=rate,rangeMultiplier=1)

def document(root):
    return dict(format='pvzhe.attack-composition',schemaVersion=2,id='matrix',character='PlantPeaShooterSingle',root=root)

@unittest.skipUnless(shutil.which('node'),'Optional Node runtime unavailable')
class NativeMatrixTests(unittest.TestCase):
    def node(self,module,body,values):
        # stdin avoids Windows command-line length and shell interpolation limits.
        script='import fs from "node:fs";const input=JSON.parse(fs.readFileSync(0,"utf8"));const m=await import('+json.dumps(module.as_uri())+');'+body
        return json.loads(subprocess.check_output(['node','--input-type=module','-e',script],input=json.dumps(values),text=True))

    def test_96_seeded_launches_match_compiled_geometry_and_timing(self):
        rng=random.Random(20261022);recipes=[]
        for n in range(96):
            r=default_recipe();r.update(id=f'matrix-{n}',pattern=['straight','fan','ring','parallel','starfruit','lob'][n%6],
                count=rng.randint(1,12),spread=rng.choice([0,25.5,180,360]),direction=rng.choice([0,37.25,90,180,270,360]),
                spacing=rng.choice([0,20.25,90]),radius=rng.choice([0,25.5,80]),angleOffset=rng.choice([0,90,120,180,360]),
                originPreset='custom',origin=[round(rng.uniform(-40,40),2),round(rng.uniform(-80,20),2)],
                ammo=rng.choice(['normal','homing']),trackingStrength=rng.choice([0,1,2]),shotDelaySeconds=rng.choice([0,.01,.25,5]))
            recipes.append(r)
        actual=self.node(ROOT/'tools/attack_web/model.mjs',
            'console.log(JSON.stringify(input.map(r=>{const lob=r.pattern==="lob",o=lob?[-2.27142333984375,-74.7405090332031]:r.origin;return {shots:m.launches({...r,radius:lob?0:r.radius},o,[620,400]),times:m.shotTimes(r)};})));',recipes)
        # Use the captured preset rather than relying on the rounded illustrative numbers in the JS script.
        # It is intentionally an independent fixed native-origin expectation below.
        self.assertAlmostEqual(ORIGIN_PRESETS['presets']['lobber']['origin'][0],-2.27142333984375,places=5)
        for r,result in zip(recipes,actual):
            with self.subTest(pattern=r['pattern'],identity=r['id']):
                items=compile_recipe(r)['groups'][0]['items'];self.assertEqual(len(items),len(result['shots']))
                for item,shot,time in zip(items,result['shots'],result['times']):
                    point=launch_position(item,[0,0],dict(size=[80,98]),[620,400])
                    self.assertAlmostEqual(point[0],shot['x'],places=5);self.assertAlmostEqual(point[1],shot['y'],places=5)
                    self.assertAlmostEqual(item['time'],time,places=7)
                    if r['pattern']!='lob':
                        angle=shot['angle']+math.radians(r['angleOffset'])
                        expected=math.radians(item['trajectory']['direction'])
                        if item['guidance']['initialAim']:expected+=math.atan2(400-shot['y'],620-shot['x'])
                        self.assertAlmostEqual(math.cos(angle),math.cos(expected),places=7)
                        self.assertAlmostEqual(math.sin(angle),math.sin(expected),places=7)

    def test_composition_effective_values_and_rejections_match_browser(self):
        rng=random.Random(7731);documents=[]
        for n in range(32):
            children=[]
            for i in range(4):
                r=default_recipe();r.update(id=f'recipe-{n}-{i}',pattern='lob' if i==0 else 'straight',speed=rng.choice([30,300,3000]),intervalSeconds=rng.choice([.1,1.5,60]))
                attack=dict(kind='attack',id=f'attack-{n}-{i}',name='attack',enabled=i!=3,recipe=r)
                children.append(group(f'group-{n}-{i}',[attack],speed=rng.choice([.1,1,10]),rate=rng.choice([.1,1,10])))
            documents.append(document(group('root',children,speed=rng.choice([.1,1,10]),rate=rng.choice([.1,1,10]))))
        actual=self.node(ROOT/'tools/attack_web/composition.mjs',
            'console.log(JSON.stringify(input.map(d=>{try{return m.flatten(d).map(e=>[e.recipe.speed,e.recipe.intervalSeconds,e.enabled]);}catch{return null;}})));',documents)
        for doc,js in zip(documents,actual):
            try:
                validate(doc);py=[[e['speed'],e['interval'],e['enabled']] for _,e in layers(doc)]
            except ValueError:py=None
            self.assertEqual(py,js)

    def test_lob_ignores_three_large_group_multipliers(self):
        r=default_recipe();r.update(pattern='lob',speed=3000)
        node=dict(kind='attack',id='lob',name='lob',enabled=True,recipe=r)
        for n in range(3):node=group(str(n),[node],speed=10)
        doc=document(node);validate(doc)
        actual=self.node(ROOT/'tools/attack_web/composition.mjs','console.log(JSON.stringify(m.flatten(input).map(e=>e.recipe.speed)));',doc)
        self.assertEqual(actual,[300]);self.assertEqual(compile_recipe(doc)['groups'][0]['items'][0]['trajectory']['speed'],300)
