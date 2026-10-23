import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from attack_model import digest, file_sha, load_session, save
from attack_plan import default_plan
from attack_web import Editor, ORIGIN_PRESETS, default_recipe
from attack_recipe import verify_result, export_result, bind_recipe, new_session, check_release


class RecipeWorkflowTests(unittest.TestCase):
    def test_presets_require_a_verified_pck_and_dll_pair(self):
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); (root / '.work').mkdir()
            (root / '.work/release.json').write_text('{}', encoding='utf-8')
            for baseline in ORIGIN_PRESETS['verifiedReleases']:
                identity = dict(pckSha256=baseline['pckSha256'], assemblies={'PlantsVsZombies.dll':baseline['dllSha256']})
                config = dict(provenance=dict(releaseCacheKey='fixture', release=identity), assets={k:{} for k in ('background','plant','target')})
                with patch('game_cache.GameCache', return_value=SimpleNamespace(key='fixture', identity=identity)):
                    check_release(config, root)
                    identity['pckSha256'] = 'unknown-resource-pack'
                    with self.assertRaisesRegex(ValueError, '预设'): check_release(config, root)

    def fixture(self, root):
        assets = {}
        for name in ("background", "plant", "target"):
            path = root / (name + ".png")
            path.write_bytes(b"protocol-fixture-" + name.encode())
            assets[name] = dict(path=str(path), sha256=file_sha(path))
        config = dict(schemaVersion=3, sessionId="current-session", canvas=[1080, 600], assets=assets,
                      plant=dict(key="PlantPeaShooterSingle", position=[300,321], imageOrigin=[128,190]),
                      target=dict(position=[830,321], imageOrigin=[128,190], speed=0),
                      grid=dict(begin=[260,75],size=[80,98],rows=5),
                      plan=default_plan(), binding=dict(action="primary"),
                      provenance=dict(releaseCacheKey="fixture-release",release=dict(assemblies={"PlantsVsZombies.dll":ORIGIN_PRESETS["dllSha256"]})))
        session = root / "session.json"
        save(session, config)
        return session, load_session(session)

    def server_record(self, editor, config, path):
        save(path, dict(sessionId=config["sessionId"], transactionId=editor.transaction_id,
                        configSha256=digest(config), demo=False, viewOnly=editor.view_only,
                        recipePath=str(editor.recipe_path), planPath=str(editor.plan_path)))

    @patch("attack_recipe.check_release")
    def test_confirm_export_bind_and_reopen_detects_source_drift(self, _):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            session,c=self.fixture(root)
            recipe,plan,record,server=[root/n for n in ("primary.recipe.json","primary.json","result.json","server.json")]
            e=Editor(record,recipe,c,plan_path=plan,project_root=root)
            self.server_record(e,c,server)
            r=copy.deepcopy(e.recipe);r.update(pattern="fan",count=7,spread=60,intervalSeconds=.2,speed=600)
            e.accept("confirm",r)
            result=export_result(record,session,server,recipe,plan,root)
            self.assertTrue(result["implementationPending"])
            compiled=json.loads(plan.read_text(encoding="utf-8"))
            self.assertEqual(len(compiled["groups"][0]["items"]),7)
            self.assertEqual(compiled["reference"]["recipeSha256"],digest(r))
            with self.assertRaises(ValueError):
                export_result(record,session,server,recipe,plan,root)
            code=root/'feature.cs';code.write_text('// implementation fixture',encoding='utf-8')
            bind_recipe(recipe,plan,['feature.cs'],root)
            Editor(root/'reopen.json',recipe,c,plan_path=plan,project_root=root)
            code.write_text('// external edit',encoding='utf-8')
            with self.assertRaises(ValueError):
                Editor(root/'drift.json',recipe,c,plan_path=plan,project_root=root)

    @patch("attack_recipe.check_release")
    def test_stale_view_demo_tampered_plan_and_wrong_action_are_rejected(self, _):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);session,c=self.fixture(root)
            recipe,plan,record,server=[root/n for n in ('recipe.json','plan.json','result.json','server.json')]
            e=Editor(record,recipe,c,plan_path=plan,project_root=root);self.server_record(e,c,server)
            e.accept('confirm',e.recipe)
            valid=json.loads(record.read_text(encoding='utf-8'))
            variants=[]
            for key,value in [('status','viewed'),('demo',True),('viewOnly',True),('transactionId','old'),('recipeSha256','old')]:
                wrong=copy.deepcopy(valid);wrong[key]=value;variants.append(wrong)
            wrong=copy.deepcopy(valid);wrong['binding']['action']='special';variants.append(wrong)
            wrong=copy.deepcopy(valid);wrong['plan']['groups'][0]['items'][0]['time']=1.;variants.append(wrong)
            for wrong in variants:
                with self.subTest(wrong=wrong.get('status')):
                    save(record,wrong)
                    with self.assertRaises(ValueError):verify_result(record,session,server,recipe,plan,root)
                    self.assertFalse(plan.exists())
            save(record,valid)
            verify_result(record,session,server,recipe,plan,root)
            (root/'plant.png').write_bytes(b'changed capture')
            with self.assertRaises(ValueError):verify_result(record,session,server,recipe,plan,root)

    def test_view_and_cancel_do_not_write_project_recipe_or_restore_project_draft(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);recipe=root/'recipe.json';save(recipe,default_recipe())
            original=recipe.read_bytes()
            edit=Editor(root/'edit.json',recipe,project_root=root)
            draft=copy.deepcopy(edit.recipe);draft['count']=20;edit.accept('save',draft)
            view=Editor(root/'view.json',recipe,recover=True,view_only=True,project_root=root)
            self.assertNotEqual(view.recipe['count'],20)
            trial=copy.deepcopy(view.recipe);trial['count']=17;view.accept('confirm',trial)
            result=json.loads(view.output.read_text(encoding='utf-8'))
            self.assertEqual(result['status'],'viewed');self.assertNotIn('plan',result)
            self.assertEqual(recipe.read_bytes(),original)
            edit.accept('cancel',None)
            resumed=Editor(root/'resumed.json',recipe,recover=True,project_root=root)
            self.assertEqual(resumed.recipe['count'],20)

    def test_editing_does_not_overwrite_concurrent_recipe_change(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);recipe=root/'recipe.json';save(recipe,default_recipe())
            e=Editor(root/'result.json',recipe,project_root=root)
            other=copy.deepcopy(e.recipe);other['count']=10;save(recipe,other)
            with self.assertRaises(ValueError):e.accept('confirm',e.recipe)
            self.assertFalse(e.output.exists())
            self.assertEqual(json.loads(recipe.read_text(encoding='utf-8'))['count'],10)

    @patch('attack_recipe.check_release')
    def test_new_session_keeps_assets_and_updates_action_and_identity(self, _):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source,c=self.fixture(root);output=root/'next.json'
            new_session(source,output,root,'special')
            actual=load_session(output)
            self.assertNotEqual(c['sessionId'],actual['sessionId'])
            self.assertEqual(c['assets'],actual['assets'])
            self.assertEqual(actual['binding']['action'],'special')
            self.assertEqual(load_session(source),c)
