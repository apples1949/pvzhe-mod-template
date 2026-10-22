"""Preview behavior assertions use independent expected directions and time sampling."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from attack_web import default_recipe

@unittest.skipUnless(shutil.which('node'),'Optional Node runtime unavailable')
class TrackingPreviewTests(unittest.TestCase):
    def run_model(self,body):
        recipe=default_recipe();recipe.update(ammo='homing',intervalSeconds=60,radius=0,originPreset='custom',origin=[0,0])
        script='import assert from "node:assert/strict";import {Preview,targetPosition,touchesCircle,touchesTarget} from '+json.dumps((ROOT/'tools/attack_web/model.mjs').as_uri())+';const recipe='+json.dumps(recipe)+';'+body
        subprocess.run(['node','--input-type=module','-e',script],check=True,capture_output=True,text=True)

    def test_delayed_tracking_starts_straight_while_immediate_turns(self):
        self.run_model('''
for(const strength of [0,1,2]){
  const p=new Preview({...recipe,trackingStrength:strength},[400,300],[900,300]);
  p.volley();p.next=60;p.step(1/120,[100,300]);
  const b=p.bullets[0];assert.ok(b);
  if(strength===0){assert.equal(b.angle,0);assert.equal(b.x,402.5);}
  if(strength===1){assert.equal(b.angle,0);assert.equal(b.x,402.5);}
  if(strength===2){assert.ok(Math.abs(b.angle-Math.PI)<1e-10);assert.equal(b.x,397.5);}
}
''')

    def test_each_snapshot_shot_aims_from_its_own_birth_and_keeps_layout(self):
        self.run_model('''
for(const pattern of ['straight','fan','ring','starfruit','parallel']){
 const r={...recipe,pattern,count:6,radius:70,spacing:30,deploymentSeconds:0,angleOffset:0,trackingStrength:0};
 const p=new Preview(r,[400,300],[850,120]);p.step(0);
 const starts=p.bullets.map(b=>[b.x,b.y,b.angle]);
 for(const b of p.bullets)assert.ok(Math.abs(b.angle-Math.atan2(120-b.y,850-b.x))<1e-10);
 p.step(.01,[850,500]);
 p.bullets.forEach((b,i)=>assert.equal(b.angle,starts[i][2]));
 const normal=new Preview({...r,ammo:'normal'},[400,300],[850,120]);normal.step(0);
 normal.bullets.forEach((b,i)=>assert.deepEqual([b.x,b.y],starts[i].slice(0,2)));
}
''')

    def test_delayed_tracking_switches_to_native_direction_after_half_second(self):
        self.run_model('''
const weak=new Preview({...recipe,trackingStrength:1},[100,300],[900,350]);
const native=new Preview({...recipe,trackingStrength:2},[100,300],[900,350]);
weak.step(1/120);native.step(1/120);
const wanted=Math.atan2(50,800);
assert.equal(weak.bullets[0].angle,0);
assert.ok(Math.abs(native.bullets[0].angle-wanted)<1e-10);
while(weak.time<.5-1e-9)weak.step(Math.min(.05,.5-weak.time));
assert.equal(weak.bullets[0].angle,0);assert.equal(weak.bullets[0].y,300);
const b=weak.bullets[0],aim=Math.atan2(350-b.y,900-b.x);
weak.step(1/120);
assert.ok(Math.abs(weak.bullets[0].angle-aim)<1e-10);
assert.equal(weak.bullets[0].trackingActive,true);
''')

    def test_moving_target_render_clock_and_replay_chunking_match(self):
        self.run_model('''
for(const strength of [0,1,2]){
 const target=t=>targetPosition([1000,300],t,true);
 const a=new Preview({...recipe,trackingStrength:strength},[100,300],target(0));
 const b=new Preview({...recipe,trackingStrength:strength},[100,300],target(0));
 for(let i=0;i<20;i++)a.step(.05,target);
 for(let i=0;i<60;i++)b.step(1/60,target);
 assert.ok(Math.abs(a.target[1]-target(a.time)[1])<1e-10);
 assert.ok(Math.abs(b.target[1]-target(b.time)[1])<1e-10);
 assert.equal(a.bullets.length,1);assert.equal(b.bullets.length,1);
 assert.ok(Math.hypot(a.bullets[0].x-b.bullets[0].x,a.bullets[0].y-b.bullets[0].y)<1e-7);
 assert.ok(Math.abs(a.bullets[0].angle-b.bullets[0].angle)<1e-8);
}
''')

    def test_delay_is_per_projectile_and_includes_formation_deployment(self):
        self.run_model('''
const p=new Preview({...recipe,pattern:'fan',spread:0,count:3,shotDelaySeconds:.1,trackingStrength:1},[100,300],[900,150]);
while(p.time<.55-1e-9)p.step(Math.min(.05,.55-p.time));
assert.deepEqual(p.bullets.map(b=>b.trackingActive),[true,false,false]);
assert.equal(p.bullets[1].angle,0);assert.equal(p.bullets[2].angle,0);
while(p.time<.65-1e-9)p.step(Math.min(.05,.65-p.time));
assert.deepEqual(p.bullets.map(b=>b.trackingActive),[true,true,false]);
const deployed=new Preview({...recipe,pattern:'parallel',count:1,spacing:0,deploymentSeconds:.15,trackingStrength:1},[100,300],[900,150]);
while(deployed.time<.49-1e-9)deployed.step(Math.min(.05,.49-deployed.time));
assert.equal(deployed.bullets[0].angle,0);
while(deployed.time<.55-1e-9)deployed.step(Math.min(.05,.55-deployed.time));
assert.equal(deployed.bullets[0].trackingActive,true);
''')

    def test_native_contact_uses_circle_and_removes_hit_projectile(self):
        self.run_model('''
assert.equal(touchesCircle(0,30,1000,0,[500,0]),true);
assert.equal(touchesCircle(0,30.01,1000,0,[500,0]),false);
assert.equal(touchesTarget(0,30.01,1000,0,[500,0],[-18,-37,44,70]),true);
const p=new Preview({...recipe,trackingStrength:2,speed:3000},[100,300],[500,300]);
for(let i=0;i<20;i++)p.step(.05);
assert.equal(p.emitted,1);assert.equal(p.bullets.length,0);
''')

    def test_long_delays_use_compact_streams_without_losing_emissions(self):
        self.run_model('''
const p=new Preview({...recipe,ammo:'normal',pattern:'fan',count:120,spread:0,shotDelaySeconds:5,intervalSeconds:.01},[100,300],[5000,300]);
while(p.time<10-1e-9)p.step(Math.min(.05,10-p.time));
const expected=Array.from({length:120},(_,i)=>Math.max(0,Math.floor((10-i*5)/.01+1e-7)+1)).reduce((a,b)=>a+b,0);
assert.equal(p.emitted,expected);assert.equal(p.emitted,1503);
assert.ok(p.pending.length<=120);assert.ok(p.bullets.length<=1000);
p.reset(recipe,[100,300],[5000,300]);assert.equal(p.pending.length,0);
''')
