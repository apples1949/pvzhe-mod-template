import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from placement_model import Session, FeedbackClock, write_result


def config():
    return {"schemaVersion":1,"layouts":[{"id":key,"canvas":{"width":1080,"height":600},
        "objects":[{"id":"button","text":"Button","x":10,"y":20,"width":160,"height":44}],
        "regions":[{"label":"Coin","x":80,"y":550,"width":170,"height":40}]}
        for key in ("horizontal","vertical")]}


class PlacementTests(unittest.TestCase):
    def test_absolute_overlap_is_preserved(self):
        session=Session(config())
        session.update("button",x=85,y=550)
        result=session.result("confirmed")
        self.assertTrue(result["confirmed"])
        self.assertEqual(result["layouts"][0]["objects"][0]["x"],85)
        self.assertEqual(result["layouts"][0]["objects"][0]["y"],550)

    def test_layout_positions_are_independent(self):
        session=Session(config())
        session.update("button",x=200)
        session.select("vertical")
        session.update("button",x=300)
        session.select("horizontal")
        self.assertEqual(session.layout["objects"][0]["x"],200)
        session.reset()
        self.assertEqual(session.layout["objects"][0]["x"],10)
        self.assertEqual(session.layouts[1]["objects"][0]["x"],300)

    def test_timeout_and_cancel_are_not_confirmation(self):
        session=Session(config())
        self.assertEqual(session.result("timeout")["message"],"用户还未输入")
        session.update("button",x=30)
        for status in ("timeout","cancelled"):
            result=session.result(status)
            self.assertFalse(result["confirmed"])
            self.assertTrue(result["changed"])
            self.assertEqual(result["layouts"][0]["objects"][0]["x"],30)
        self.assertEqual(session.result("timeout")["message"],"用户还未输入（未确认）")

    def test_resume_does_not_inherit_confirmation(self):
        session=Session(config());session.update("button",x=350)
        draft=session.result("confirmed")
        resumed=Session(config(),resume=draft)
        self.assertEqual(resumed.layout["objects"][0]["x"],350)
        self.assertFalse(resumed.result("timeout")["confirmed"])
        self.assertNotEqual(resumed.id,draft["sessionId"])
        changed=config();changed["layouts"][0]["canvas"]["width"]=1200
        with self.assertRaises(ValueError):Session(changed,resume=draft)

    def test_invalid_inputs_are_rejected_without_partial_update(self):
        session=Session(config())
        for values in ({"x":float("nan")},{"y":-1},{"width":5000},{"x":True}):
            with self.assertRaises(ValueError):session.update("button",**values)
        self.assertEqual(session.layout["objects"][0]["x"],10)
        bad=config();bad["layouts"][1]["id"]="horizontal"
        with self.assertRaises(ValueError):Session(bad)
        bad=config();bad["layouts"][0]["objects"].append(copy.deepcopy(bad["layouts"][0]["objects"][0]))
        with self.assertRaises(ValueError):Session(bad)

    def test_clock_starts_on_visibility_and_extension(self):
        now=[100.0];clock=FeedbackClock(60,now=lambda:now[0])
        now[0]=500
        self.assertEqual(clock.remaining,60)
        clock.start();now[0]=559.1
        self.assertEqual(clock.remaining,1)
        clock.extend();now[0]=560
        self.assertEqual(clock.remaining,60)
        clock.start();now[0]=620
        self.assertEqual(clock.remaining,0)

    def test_changed_image_rejects_resume(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);image=root/"image.png";image.write_bytes(b"first")
            spec=config();spec["layouts"][0]["background"]="image.png"
            session=Session(spec,root);draft=session.result("timeout")
            image.write_bytes(b"second")
            with self.assertRaises(ValueError):Session(spec,root,resume=draft)

    def test_local_assets_and_atomic_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/"image.png").write_bytes(b"fixture")
            session=Session(config(),base=root)
            self.assertEqual(session.asset("image.png"),root/"image.png")
            with self.assertRaises(ValueError):session.asset("missing.png")
            path=root/"out"/"result.json"
            write_result(path,session.result("cancelled"))
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["status"],"cancelled")
            self.assertFalse(path.with_name("result.json.tmp").exists())

if __name__ == "__main__":unittest.main()
