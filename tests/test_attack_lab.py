import json
import math
from pathlib import Path
import sys
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from attack_web import compile_recipe


class AttackLabRecipes(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node') and shutil.which('dotnet'),'Node and .NET SDK are optional test dependencies')
    def test_delayed_activation_matches_preview(self):
        strengths=[0,1,2];ages=[0,.49,.5,.51,1]
        values=[[strength,age] for strength in strengths for age in ages]
        module=(ROOT/'tools/attack_web/model.mjs').as_uri()
        script=f"import {{guidanceActive}} from {json.dumps(module)};console.log(JSON.stringify({json.dumps(values)}.map(([s,a])=>guidanceActive(s,a))));"
        expected=json.loads(subprocess.check_output(['node','--input-type=module','-e',script],text=True))
        self.assertEqual(expected,[s==2 or s==1 and age>=.5 for s,age in values])
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary);shutil.copyfile(ROOT/'examples/AttackLab/WebGuidance.cs',path/'WebGuidance.cs')
            (path/'Test.csproj').write_text('<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><OutputType>Exe</OutputType><TargetFramework>net9.0</TargetFramework><ImplicitUsings>enable</ImplicitUsings></PropertyGroup></Project>')
            (path/'Program.cs').write_text('''using AttackLab;
foreach(double s in new double[]{0,1,2})
foreach(double age in new double[]{0,.49,.5,.51,1})
Console.WriteLine("ACTIVE:"+WebGuidance.Active(s,age));
''')
            output=subprocess.check_output(['dotnet','run','--project',str(path/'Test.csproj'),'-c','Release'],text=True)
            actual=[line[7:]=='True' for line in output.splitlines() if line.startswith('ACTIVE:')]
            self.assertEqual(actual,expected)
    def test_saved_plans_match_designs_and_fixed_window_counts(self):
        totals={'straight':6,'fan':50,'ring':12,'parallel':20,'starfruit':15,'homing':13,'lob':4,'nested':36}
        for case,expected in totals.items():
            with self.subTest(case=case):
                root=ROOT/'examples/AttackLab'
                doc=json.loads((root/'design'/f'{case}.json').read_text(encoding='utf-8'))
                plan=compile_recipe(doc)
                self.assertEqual(plan,json.loads((root/'mod/Assets'/f'{case}.json').read_text(encoding='utf-8')))
                emitted=0
                for group in plan['groups']:
                    if not group['enabled']:continue
                    rounds=math.ceil((2.4-group.get('startDelaySeconds',0))/group['intervalSeconds']-1e-8)
                    emitted+=rounds*sum(item['enabled'] for item in group['items'])
                self.assertEqual(emitted,expected)

    def test_nested_effective_values_and_disabled_layer(self):
        plan=json.loads((ROOT/'examples/AttackLab/mod/Assets/nested.json').read_text(encoding='utf-8'))
        groups={g['id']:g for g in plan['groups']}
        self.assertAlmostEqual(groups['layer-a-layer']['intervalSeconds'],.4)
        self.assertAlmostEqual(groups['layer-b-layer']['intervalSeconds'],.6)
        self.assertAlmostEqual(groups['plain-layer']['intervalSeconds'],.7/1.5)
        self.assertAlmostEqual(groups['layer-b-layer']['startDelaySeconds'],.35)
        self.assertEqual(groups['layer-b-layer']['items'][0]['trajectory']['speed'],1012.5)
        self.assertFalse(groups['disabled-layer']['enabled'])
