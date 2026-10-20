import copy
import math
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from attack_model import Simulation, default_attack, result, digest, load_session, save, file_sha, validate_attack, grid_row_y, curve_points


class AttackPreviewTests(unittest.TestCase):
    def test_initial_actors_are_in_native_third_row(self):
        grid = dict(begin=[260, 75], size=[80, 98], rows=5, plantOffset=50)
        self.assertEqual(grid_row_y(grid, 3), 320)
        self.assertEqual(grid_row_y(grid, 3, plant=True), 321)
        for plant in (False, True):
            y = grid_row_y(grid, 3, plant=plant)
            self.assertEqual(math.floor((y-75)/98)+1, 3)
        with self.assertRaises(ValueError): grid_row_y(grid, 3.5)

    def test_parallel_birth_band_is_not_angular_spread(self):
        a = dict(default_attack(), origin=[35, -65], count=100, shotGap=0, birthY=4)
        sim = Simulation(a, [100, 200], [800, 200])
        sim.step(.01, [800, 200])
        ys = [b["position"][1] for b in sim.bullets]
        self.assertGreater(max(ys)-min(ys), 7)
        self.assertTrue(all(131 <= y <= 139 for y in ys))
        sim.step(.5, [800, 200])
        self.assertEqual(ys, [b["position"][1] for b in sim.bullets])
        self.assertTrue(all(b["velocity"] == [300., 0.] for b in sim.bullets))

    def test_fan_angles_and_single_shot_center(self):
        a = dict(default_attack(), kind="fan", count=3, shotGap=0, spread=60)
        sim = Simulation(a, [0, 0], [800, 0]); sim.step(.01, [800, 0])
        angles = [round(math.degrees(math.atan2(*reversed(b["velocity"])))) for b in sim.bullets]
        self.assertEqual(angles, [-30, 0, 30])
        a["count"] = 1
        sim = Simulation(a, [0, 0], [800, 0]); sim.step(.01, [800, 0])
        self.assertEqual(sim.bullets[0]["velocity"][1], 0)

    def test_single_attack_budget_and_intra_attack_timing(self):
        a = dict(default_attack(), count=3, shotGap=.2)
        sim = Simulation(a, [0, 0], [800, 0])
        sim.step(.01, [800, 0]); self.assertEqual(sim.emitted, 1)
        sim.step(.2, [800, 0]); self.assertEqual(sim.emitted, 2)
        sim.step(.2, [800, 0]); self.assertEqual(sim.emitted, 3)
        sim.step(8, [800, 0]); self.assertEqual(sim.emitted, 3)

    def test_aim_is_locked_and_tracking_turn_is_bounded(self):
        a = dict(default_attack(), origin=[0, 0], count=1, targeting="aim")
        aim = Simulation(a, [0, 0], [800, 0]); aim.step(0, [800, 0]); aim.step(.1, [0, -800])
        self.assertEqual(aim.bullets[0]["velocity"][1], 0)
        a.update(targeting="track-limited", turnRate=90)
        track = Simulation(a, [0, 0], [800, 0]); track.step(0, [800, 0]); track.step(.1, [0, -800])
        self.assertAlmostEqual(math.degrees(math.atan2(track.bullets[0]["velocity"][1], track.bullets[0]["velocity"][0])), -9)
        a["targeting"] = "track"
        native = Simulation(a, [0, 0], [800, 0]); native.step(0, [800, 0]); native.step(.1, [0, -800])
        self.assertAlmostEqual(native.bullets[0]["velocity"][0], 0, places=5)
        self.assertEqual(native.bullets[0]["velocity"][1], -300)

    def test_parabola_and_bezier_geometry(self):
        a = dict(default_attack(), count=1, origin=[0, 0], kind="parabola", direction=0, gravity=200)
        sim = Simulation(a, [0, 0], [600, 0]); sim.step(0, [600, 0]); sim.step(.5, [600, 0])
        self.assertEqual(sim.bullets[0]["position"], (150., 25.))
        a.update(kind="bezier", flightTime=2, controls=[[200, -100], [400, -100]],curveEnd=[600,0])
        sim = Simulation(a, [0, 0], [600, 0]); sim.step(0, [600, 0]); sim.step(1, [900, 80])
        self.assertEqual(sim.bullets[0]["position"], (300., -75.))  # endpoint locked at launch

    def test_incompatible_policies_and_nonfinite_rejected(self):
        for change in (dict(count=1.5), dict(speed=float("nan")), dict(kind="bezier", targeting="track-limited"), dict(controls=[[0, 0]])):
            with self.assertRaises(ValueError): validate_attack(dict(default_attack(), **change))

    def test_bezier_aim_rotates_entire_template_without_stretching(self):
        a=dict(default_attack(),kind="bezier",origin=[0,0],count=1,targeting="aim",flightTime=2,
               controls=[[100,-50],[200,-50]],curveEnd=[300,0])
        points=curve_points(a,[10,20],[10,900])
        for actual,expected in zip(points,([10,20],[60,120],[60,220],[10,320])):
            for x,y in zip(actual,expected): self.assertAlmostEqual(x,y)
        aim=Simulation(a,[10,20],[10,900]); aim.step(0,[10,900]); locked=copy.deepcopy(aim.bullets[0]["curve"])
        aim.step(.5,[900,20]); self.assertEqual(aim.bullets[0]["curve"],locked)
        a["targeting"]="track"
        track=Simulation(a,[10,20],[10,900]); track.step(0,[10,900]); track.step(.5,[900,20])
        for actual,expected in zip(track.bullets[0]["curve"],([10,20],[110,-30],[210,-30],[310,20])):
            for x,y in zip(actual,expected): self.assertAlmostEqual(x,y)
        self.assertEqual(track.bullets[0]["curve"][0],[10,20])

    def test_confirmation_identity_and_no_cooldown(self):
        config = dict(sessionId="this-run", canvas=[1080, 600], provenance={}, assets={})
        a = default_attack()
        for status, yes in (("confirmed", True), ("cancelled", False)):
            r = result(config, a, {}, {}, status)
            self.assertEqual(r["configSha256"], digest(config))
            self.assertEqual(r["confirmed"], yes)
            self.assertNotIn("cooldown", r["attack"])
            self.assertFalse(r["attackCooldownIncluded"])
        with self.assertRaises(ValueError): result(config, a, {}, {}, "timeout")

    def test_stale_or_modified_asset_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); asset = root/"pose.png"; asset.write_bytes(b"reference")
            actor = dict(position=[300, 370], imageOrigin=[128, 190], speed=0)
            config = dict(schemaVersion=1, sessionId="a", canvas=[1080, 600], attack=default_attack(), plant=actor, target=actor,
                          assets={"plant": dict(path="pose.png", sha256=file_sha(asset))})
            save(root/"session.json", config)
            self.assertEqual(load_session(root/"session.json")["sessionId"], "a")
            asset.write_bytes(b"modified")
            with self.assertRaises(ValueError): load_session(root/"session.json")


if __name__ == '__main__': unittest.main()
