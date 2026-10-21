import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import http.client
import threading
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from attack_templates import TemplateStore, TemplateConflict, filename
from attack_web import default_recipe, validate_recipe, compile_recipe, Editor, make_server


class TemplateTests(unittest.TestCase):
    def test_http_save_load_conflict_and_readonly(self):
        with tempfile.TemporaryDirectory() as root:
            editor = Editor(Path(root)/"result.json", project_root=root)
            server = make_server(editor)
            thread = threading.Thread(target=server.serve_forever, daemon=True);thread.start()
            conn = http.client.HTTPConnection("127.0.0.1", server.server_port)
            def request(action, **extra):
                payload = dict(action=action, sessionId=editor.session_id, transactionId=editor.transaction_id, **extra)
                conn.request("POST", f"/{editor.token}/api/template", json.dumps(payload), {"Content-Type":"application/json"})
                response = conn.getresponse();return response.status, json.loads(response.read())
            try:
                status, saved = request("save", name="直线", recipe=editor.recipe)
                self.assertEqual(status, 200);self.assertTrue(Path(saved["path"]).is_absolute())
                status, loaded = request("load", name="直线")
                self.assertEqual(status, 200);self.assertEqual(loaded["design"], editor.recipe)
                status, conflict = request("save", name="直线", recipe=editor.recipe)
                self.assertEqual(status, 409)
                status, _ = request("save", name="直线", recipe=editor.recipe, expectedSha256=conflict["sha256"])
                self.assertEqual(status, 200)
                editor.view_only = True
                self.assertEqual(request("save", name="其他", recipe=editor.recipe)[0], 400)
                self.assertFalse(editor.done);self.assertFalse(editor.output.exists())
            finally:
                conn.close();server.shutdown();server.server_close();thread.join()

    def test_safe_names_and_long_names(self):
        for name in ("../CON", "CON", "a/b\\c", "..", "狂野机枪" * 25):
            result = filename(name)
            self.assertTrue(result.startswith("t-"))
            self.assertNotIn("/", result)
            self.assertNotIn("\\", result)
            self.assertLess(len(result), 220)
        for name in ("", "  ", "a\n", "a" * 121):
            with self.assertRaises(ValueError): filename(name)

    def test_explicit_overwrite_and_roundtrip_compilation(self):
        with tempfile.TemporaryDirectory() as root:
            store = TemplateStore(root, validate_recipe)
            recipe = default_recipe();recipe.update(pattern="ring", count=6, shotDelaySeconds=.1)
            result = store.write("六向方案", recipe, {"version": 1})
            path = Path(result["path"])
            self.assertEqual(path.parent.name, ".attack-templaates")
            before = path.read_bytes()
            loaded = store.read("六向方案")
            self.assertEqual(compile_recipe(recipe), compile_recipe(loaded["design"]))
            self.assertEqual(store.catalog(), [{"name": "六向方案"}])
            with self.assertRaises(TemplateConflict) as caught:
                store.write("六向方案", recipe, {})
            self.assertEqual(path.read_bytes(), before)
            recipe["count"] = 8
            store.write("六向方案", recipe, {}, caught.exception.sha)
            with self.assertRaises(TemplateConflict):
                store.write("六向方案", recipe, {}, caught.exception.sha)
            self.assertEqual(store.read("六向方案")["design"]["count"], 8)
            self.assertEqual(store.read("六向方案")["id"], loaded["id"])

    def test_unknown_version_and_invalid_design_do_not_overwrite(self):
        with tempfile.TemporaryDirectory() as root:
            store = TemplateStore(root, validate_recipe)
            recipe = default_recipe()
            path = Path(store.write("直线", recipe, {})["path"])
            original = path.read_bytes();recipe["speed"] = float("nan")
            with self.assertRaises(ValueError): store.write("直线", recipe, {})
            self.assertEqual(path.read_bytes(), original)
            record = json.loads(original);record["schemaVersion"] = 999
            path.write_text(json.dumps(record), encoding="utf-8")
            with self.assertRaises(ValueError): store.read("直线")
            self.assertEqual(store.catalog(), [])

    def test_nested_design_retains_independent_cadence_and_delay(self):
        from test_attack_composition import fixture
        with tempfile.TemporaryDirectory() as root:
            store = TemplateStore(root, validate_recipe)
            design = fixture();design["schemaVersion"] = 2
            design["root"]["children"][0]["startDelaySeconds"] = .25
            expected = compile_recipe(design)
            store.write("嵌套方案", design, {})
            restored = store.read("嵌套方案")["design"]
            self.assertEqual(restored, design)
            self.assertEqual(compile_recipe(restored), expected)
            self.assertNotEqual(expected["groups"][0]["intervalSeconds"], expected["groups"][1]["intervalSeconds"])
