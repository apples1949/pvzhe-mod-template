import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from attack_web import default_recipe,compile_recipe,validate_recipe,load_recipe,Editor
from attack_composition import layers
from attack_plan import PlanSimulation

def attack(identity,speed=300,interval=2):
    r=default_recipe();r.update(id=identity+"-recipe",pattern="straight",count=1,speed=speed,intervalSeconds=interval)
    return dict(kind="attack",id=identity,name=identity,enabled=True,recipe=r)
def group(identity,children,speed=1,rate=1,distance=1):
    return dict(kind="group",id=identity,name=identity,enabled=True,children=children,speedMultiplier=speed,rateMultiplier=rate,rangeMultiplier=distance)
def fixture():
    return dict(format="pvzhe.attack-composition",schemaVersion=1,id="composition",character="PlantPeaShooterSingle",root=group("root",[group("nested",[attack("a",600)],speed=2,rate=2),attack("b",300,3)],speed=2,rate=2))
class CompositionTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "Node is required for browser-model checks")
    def test_multi_selection_values_and_preview_identity(self):
        module=(Path(__file__).resolve().parents[1]/"tools/attack_web/composition.mjs").as_uri()
        script="""
import assert from 'node:assert/strict';
const {selectionValue,applySelectionValue,flatten,CompositionPreview}=await import(MODULE);
const a={kind:'attack',id:'a',enabled:true,recipe:{speed:300,intervalSeconds:1.5}},b={kind:'attack',id:'b',enabled:true,recipe:{speed:600,intervalSeconds:3}};
assert.equal(selectionValue([], 'speedMultiplier'),null);
assert.equal(selectionValue([a,b], 'speedMultiplier'),null);
assert.equal(selectionValue([a], 'rateMultiplier'),1);
applySelectionValue([a,b], 'speedMultiplier',1.5);
assert.equal(selectionValue([a,b], 'speedMultiplier'),1.5);
assert.equal(a.recipe.speed,450);assert.equal(b.recipe.speed,450);
applySelectionValue([a,b], 'rateMultiplier',2);
assert.equal(selectionValue([a,b], 'rateMultiplier'),2);
assert.equal(a.recipe.intervalSeconds,.75);assert.equal(b.recipe.intervalSeconds,.75);
const g={kind:'group',speedMultiplier:1,rateMultiplier:1};
assert.throws(()=>applySelectionValue([a,g],'speedMultiplier',11));assert.equal(a.recipe.speed,450);
applySelectionValue([g], 'rateMultiplier',2);assert.equal(g.rateMultiplier,2);
const recipe=RECIPE;
const state={canvas:[1080,600],plant:{position:[300,321]},target:{hitBoxRect:[-18,-37,44,70]},originPresets:{presets:{center:{}}},grid:{size:[80,98]}};
const sim=new CompositionPreview([{node:{id:'selected-layer'},recipe,enabled:true}],state,[830,321]);
sim.step(0,[830,321]);assert.ok(sim.bullets.length);assert.ok(sim.bullets.every(b=>b.layerId==='selected-layer'));
""".replace('MODULE',json.dumps(module)).replace('RECIPE',json.dumps(default_recipe()))
        result=subprocess.run(['node','--input-type=module','-e',script],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)

    @unittest.skipUnless(shutil.which("node"), "Node is required for browser-model checks")
    def test_ps_selection_and_transactional_tree_moves(self):
        module=(Path(__file__).resolve().parents[1]/"tools/attack_web/composition.mjs").as_uri()
        script="""
import assert from 'node:assert/strict';
const {chooseLayers,moveLayers,groupDepth,modifiedLayer,roundParameter,applySelectionValue}=await import(MODULE);
assert.equal(roundParameter(1.4000000000000001),1.4);
assert.equal(roundParameter(1.005),1.01);assert.equal(roundParameter(2.675),2.68);
assert.equal(roundParameter(-1.235),-1.24);assert.equal(roundParameter(.004),0);
const roundedGroup={kind:'group',speedMultiplier:1,rateMultiplier:1};applySelectionValue([roundedGroup],'speedMultiplier',1.4000000000000001);assert.equal(roundedGroup.speedMultiplier,1.4);
const visible=['root','a','b','g','c'];let r=chooseLayers(new Set(['b']),'a',visible,null,{});
assert.deepEqual([...r.selected],['a']);
r=chooseLayers(r.selected,'b',visible,r.anchor,{ctrlKey:true});assert.deepEqual([...r.selected],['a','b']);
r=chooseLayers(r.selected,'a',visible,r.anchor,{ctrlKey:true});assert.deepEqual([...r.selected],['b']);
r=chooseLayers(r.selected,'c',visible,'b',{shiftKey:true});assert.deepEqual([...r.selected],['b','g','c']);
r=chooseLayers(new Set(['a']),'c',visible,'g',{ctrlKey:true,shiftKey:true});assert.deepEqual([...r.selected],['a','g','c']);
const doc=DOC,before=JSON.stringify(doc);
assert.equal(groupDepth(doc,'nested'),1);
const empty=structuredClone(doc);empty.root.children=[{...empty.root, id:'empty',children:[]}];assert.equal(groupDepth(empty,'empty'),1);
assert.equal(modifiedLayer({...doc.root,speedMultiplier:1,rateMultiplier:1,rangeMultiplier:1},{}),false);
assert.equal(modifiedLayer({...doc.root,speedMultiplier:2},{}),true);
const original=doc.root.children[1];assert.equal(modifiedLayer({...original,recipe:{...original.recipe,speed:300,intervalSeconds:1.5,pattern:'parallel',originPreset:'center'}},original.recipe),false);
assert.equal(modifiedLayer({...original,recipe:{...original.recipe,speed:600}},original.recipe),true);

let moved=moveLayers(doc,['b'],'nested','inside');assert.equal(moved.root.children.length,1);assert.equal(moved.root.children[0].children[1].id,'b');assert.equal(JSON.stringify(doc),before);
moved=moveLayers(doc,['b'],'nested','before');assert.deepEqual(moved.root.children.map(n=>n.id),['b','nested']);
moved=moveLayers(doc,['nested'],'b','after');assert.deepEqual(moved.root.children.map(n=>n.id),['b','nested']);
assert.throws(()=>moveLayers(doc,['nested'],'a','inside'));
assert.throws(()=>moveLayers(doc,['root'],'b','after'));
moved=moveLayers(doc,['a'],'b','after');assert.equal(moved.root.children[0].children.length,0); // empty source group is valid
assert.throws(()=>moveLayers(doc,['b'],'a','inside'));
assert.throws(()=>moveLayers(doc,['b'],'root','before'));
// A selected parent carries its descendant exactly once.
moved=moveLayers(doc,['nested','a'],'b','after');assert.equal(moved.root.children[1].children.length,1);
assert.equal(JSON.stringify(doc),before);
""".replace('MODULE',json.dumps(module)).replace('DOC',json.dumps(fixture()))
        result=subprocess.run(['node','--input-type=module','-e',script],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_empty_groups_draft_and_compile_boundary(self):
        doc=fixture();doc['root']['children'].insert(0,group('empty',[]))
        validate_recipe(doc);self.assertEqual(len(compile_recipe(doc)['groups']),2)
        doc['root']['children']=[]
        validate_recipe(doc)
        with self.assertRaisesRegex(ValueError,'添加一个攻击图层'):
            compile_recipe(doc)
        with tempfile.TemporaryDirectory() as directory:
            editor=Editor(Path(directory)/'result.json',project_root=directory)
            doc['id']=editor.recipe['id'];doc['character']=editor.recipe['character']
            self.assertEqual(editor.accept('save',doc)['status'],'draft')
            recovered,_=load_recipe(editor.draft);self.assertEqual(recovered,doc)
            with self.assertRaisesRegex(ValueError,'添加一个攻击图层'):
                editor.accept('confirm',doc)

    def test_old_explicit_zero_phase_reopens_without_mutating_files(self):
        doc=fixture();plan=compile_recipe(doc)
        for item in plan['groups']:item['startDelaySeconds']=0
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);recipe_path=root/'recipe.json';plan_path=root/'plan.json'
            recipe_path.write_text(json.dumps(doc),encoding='utf-8');plan_path.write_text(json.dumps(plan),encoding='utf-8')
            original=plan_path.read_bytes()
            editor=Editor(root/'result.json',recipe_path,plan_path=plan_path,project_root=root)
            self.assertEqual(editor.recipe,doc);self.assertEqual(plan_path.read_bytes(),original)
        from attack_plan import same_design
        altered=json.loads(json.dumps(plan));altered['groups'][0]['startDelaySeconds']=.1
        self.assertFalse(same_design(plan,altered))

    def test_nested_start_delays_compile_and_roundtrip(self):
        self.assertTrue(all('startDelaySeconds' not in g for g in compile_recipe(fixture())['groups']))
        doc=fixture();doc['schemaVersion']=2
        doc['root']['startDelaySeconds']=.1
        nested=doc['root']['children'][0];nested['startDelaySeconds']=.2
        nested['children'][0]['startDelaySeconds']=.15
        compiled=compile_recipe(doc)
        self.assertAlmostEqual(compiled['groups'][0]['startDelaySeconds'],.45)
        self.assertAlmostEqual(compiled['groups'][1]['startDelaySeconds'],.1)
        sim=PlanSimulation(compiled,[300,321],[830,321],dict(begin=[260,75],size=[80,98],rows=5))
        for _ in range(44):sim.step(.01,[830,321])
        self.assertEqual(sim.emitted,1)
        sim.step(.02,[830,321]);self.assertEqual(sim.emitted,2)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'delay.json';path.write_text(json.dumps(doc),encoding='utf-8')
            self.assertEqual(load_recipe(path)[0],doc)
        for value in (-.1,5.01,float('nan'),True):
            doc['root']['startDelaySeconds']=value
            with self.assertRaises(ValueError):validate_recipe(doc)

    @unittest.skipUnless(shutil.which('node'), 'Node is required for browser-model checks')
    def test_clipboard_preserves_selected_ancestors_and_delay_preview(self):
        module=(Path(__file__).resolve().parents[1]/'tools/attack_web/composition.mjs').as_uri()
        script="""
import assert from 'node:assert/strict';
const {copyLayers,pasteLayers,flatten,CompositionPreview,applySelectionValue,selectionValue,modifiedLayer,editLayerProperties}=await import(MODULE);
const doc=DOC,before=JSON.stringify(doc),nested=doc.root.children[0],a=nested.children[0];
assert.throws(()=>editLayerProperties(doc,['root','a'],'speedMultiplier',10));assert.equal(JSON.stringify(doc),before);
assert.throws(()=>editLayerProperties(doc,['b'],'rateMultiplier',100));assert.equal(JSON.stringify(doc),before);
const edited=editLayerProperties(doc,['b'],'rateMultiplier',1.4);assert.equal(edited.root.children[1].recipe.intervalSeconds,1.5/1.4);assert.equal(doc.root.children[1].recipe.intervalSeconds,3);

const grand={...structuredClone(nested),id:'grand',name:'grand',children:[nested]};doc.root.children[0]=grand;
// Selected ancestor keeps even unselected intermediate groups and all descendants, with no duplicates.
let clip=copyLayers(doc,new Set(['grand','a']));assert.equal(clip.nodes.length,1);assert.equal(clip.nodes[0].children[0].id,'nested');assert.equal(clip.nodes[0].children[0].children[0].id,'a');
let pasted=pasteLayers(doc,clip,'root');const inserted=pasted.document.root.children.at(-1);
assert.equal(inserted.kind,'group');assert.equal(inserted.children[0].kind,'group');assert.notEqual(inserted.id,'grand');assert.notEqual(inserted.children[0].children[0].recipe.id,a.recipe.id);
clip=copyLayers(doc,new Set(['a','b']));assert.deepEqual(clip.nodes.map(n=>n.kind),['attack','attack']);
pasted=pasteLayers(doc,clip,'root');assert.deepEqual(pasted.document.root.children.slice(-2).map(n=>n.kind),['attack','attack']);
assert.equal(doc.root.children.length,2);assert.equal(a.id,'a'); // source and clipboard remain intact
assert.equal(clip.nodes[0].id,'a');
const many=structuredClone(doc);many.root.children=Array.from({length:32},(_,i)=>({...structuredClone(a),id:'n'+i,recipe:{...a.recipe,id:'r'+i}}));assert.throws(()=>pasteLayers(many,clip,'root'));assert.equal(many.root.children.length,32);
assert.throws(()=>pasteLayers(doc,{...clip,character:'other'},'root'));
applySelectionValue([grand,a],'startDelaySeconds',.25);assert.equal(selectionValue([grand,a],'startDelaySeconds'),.25);assert.equal(modifiedLayer(grand),true);
const entry=flatten(doc).find(e=>e.node.id==='a');assert.equal(entry.startDelaySeconds,.5);
const state={canvas:[1080,600],plant:{position:[300,321]},target:{hitBoxRect:[-18,-37,44,70]},originPresets:{presets:{center:{}}},grid:{size:[80,98]}};
const sim=new CompositionPreview([entry],state,[830,321]);sim.step(0,[830,321]);assert.equal(sim.parts[0].emitted,0);
for(let i=0;i<9;i++)sim.step(.05,[830,321]);assert.equal(sim.parts[0].emitted,0);
sim.step(.05,[830,321]);assert.equal(sim.parts[0].emitted,1);
for(let i=0;i<5;i++)sim.step(.05,[830,321]);assert.equal(sim.parts[0].emitted,2);
""".replace('MODULE',json.dumps(module)).replace('DOC',json.dumps(fixture()))
        result=subprocess.run(['node','--input-type=module','-e',script],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_nested_multipliers_and_independent_group_clocks(self):
        doc=fixture();plan=compile_recipe(doc)
        self.assertEqual([g["intervalSeconds"] for g in plan["groups"]],[.5,1.5])
        self.assertEqual([g["items"][0]["trajectory"]["speed"] for g in plan["groups"]],[2400,600])
        self.assertEqual(doc["root"]["children"][0]["children"][0]["recipe"]["speed"],600)
        sim=PlanSimulation(plan,[300,321],[830,321],dict(begin=[260,75],size=[80,98],rows=5))
        sim.step(1.01,[830,321])
        self.assertEqual(sim.emitted,4) # A at 0/.5/1; B only at 0.
        sim.step(.5,[830,321]);self.assertEqual(sim.emitted,6)
    def test_roundtrip_and_draft_protocol(self):
        doc=fixture()
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"recipe.json";path.write_text(json.dumps(doc),encoding="utf-8")
            loaded,note=load_recipe(path);self.assertEqual(loaded,doc)
            editor=Editor(Path(directory)/"result.json",project_root=directory)
            doc["id"]=editor.recipe["id"];doc["character"]=editor.recipe["character"]
            doc["character"]="demo-plant"
            for node in (doc["root"]["children"][0]["children"][0],doc["root"]["children"][1]):node["recipe"]["character"]="demo-plant"
            editor.accept("save",doc)
            restored,_=load_recipe(editor.draft);self.assertEqual(restored,doc)
    def test_disabled_parent_and_unlimited_range(self):
        doc=fixture();doc["root"]["children"][0]["enabled"]=False
        compiled=compile_recipe(doc)
        self.assertFalse(compiled["groups"][0]["enabled"])
        self.assertIsNone(compiled["groups"][0]["items"][0]["maxTravelCells"])
    def test_invalid_group_and_unsafe_effective_values(self):
        for mutate in (lambda d:d["root"].update(speedMultiplier=float("nan")),lambda d:d["root"].update(speedMultiplier=10),lambda d:d["root"]["children"][1].update(id="nested")):
            d=fixture();mutate(d)
            with self.assertRaises(ValueError):validate_recipe(d)
    def test_confirm_export_and_reopen_keep_independent_clocks(self):
        from unittest.mock import patch
        from test_attack_recipe import RecipeWorkflowTests
        from attack_recipe import export_result
        helper=RecipeWorkflowTests()
        with tempfile.TemporaryDirectory() as directory,patch("attack_recipe.check_release"):
            root=Path(directory);session,config=helper.fixture(root)
            recipe,plan,record,server=[root/n for n in ("recipe.json","plan.json","result.json","server.json")]
            editor=Editor(record,recipe,config,plan_path=plan,project_root=root)
            doc=fixture();doc["id"]=editor.recipe["id"]
            helper.server_record(editor,config,server)
            editor.accept("confirm",doc)
            export_result(record,session,server,recipe,plan,root)
            reopened=Editor(root/"reopened.json",recipe,config,plan_path=plan,project_root=root)
            self.assertEqual(reopened.recipe,doc)
            self.assertEqual([g["intervalSeconds"] for g in json.loads(plan.read_text(encoding="utf-8"))["groups"]],[.5,1.5])

    def test_browser_flatten_and_aggregate_preview_match(self):
        node=shutil.which("node")
        if not node:self.skipTest("Node unavailable")
        module=(Path(__file__).resolve().parents[1]/"tools/attack_web/composition.mjs").as_uri()
        doc=fixture();script=f"import {{flatten}} from {json.dumps(module)};console.log(JSON.stringify(flatten({json.dumps(doc)}).map(e=>[e.recipe.speed,e.recipe.intervalSeconds,e.recipe.rangeCells,e.enabled])));"
        actual=json.loads(subprocess.check_output([node,"--input-type=module","-e",script],text=True))
        expected=[[e["speed"],e["interval"],e["range"],e["enabled"]] for _,e in layers(doc)]
        self.assertEqual(actual,expected)
        state=dict(originPresets={"presets":{"lobber":{"origin":[0,0]},"center":{"shotOffsets":[]}}},plant={"position":[300,300]},target={"hitBoxRect":[-18,-37,44,70]},canvas=[1080,600],grid={"size":[80,98]})
        script=f"import {{flatten,CompositionPreview}} from {json.dumps(module)};const p=new CompositionPreview(flatten({json.dumps(doc)}),{json.dumps(state)},[800,300]);for(let i=0;i<101;i++)p.step(.01,[800,300]);console.log(JSON.stringify(p.parts.map(s=>s.emitted)));"
        emitted=json.loads(subprocess.check_output([node,"--input-type=module","-e",script],text=True))
        self.assertEqual(emitted,[3,1])
        busy=fixture()
        for child,_ in layers(busy):child["recipe"].update(pattern="ring",count=120,intervalSeconds=.1,speed=30)
        script=f"import {{flatten,CompositionPreview}} from {json.dumps(module)};const p=new CompositionPreview(flatten({json.dumps(busy)}),{json.dumps(state)},[800,300]);for(let i=0;i<10;i++)p.step(.05,[800,300]);console.log(JSON.stringify([p.bullets.length,p.evicted,p.evicted%50]));"
        count,evicted,remainder=json.loads(subprocess.check_output([node,"--input-type=module","-e",script],text=True))
        self.assertLessEqual(count,1000);self.assertGreater(evicted,0);self.assertEqual(remainder,0)
