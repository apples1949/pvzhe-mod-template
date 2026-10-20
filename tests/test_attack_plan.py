import copy
from contextlib import contextmanager
import json
import math
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from attack_model import default_attack, file_sha, save, load_session
from attack_combo import default_combo, make_preset, ComboSimulation
from attack_plan import (default_plan,new_item,preset,migrate,validate_plan,all_items,PlanSimulation,
                         launch_position,can_trigger,Expression,store_plan,load_plan,
                         implementation_changes, function_preset, bind_implementation, design_digest, region_bounds, steer_angle, upgrade_plan)

GRID=dict(begin=[260,75],size=[80,98],rows=5,plantOffset=50)
PLANT,TARGET=[300,321],[830,320]


class AttackPlanTests(unittest.TestCase):
    def test_one_item_one_carrier_and_presets_are_groups(self):
        plan=default_plan(); plan["groups"]=[preset("扇形",count=5,spread=60)]
        self.assertEqual(validate_plan(plan),5)
        sim=PlanSimulation(plan,PLANT,TARGET,GRID,repeat=False); sim.step(0,TARGET)
        self.assertEqual(sim.emitted,5)
        self.assertTrue(all(b["item"]["trajectory"]["kind"]=="straight" for b in sim.bullets))
        plan["groups"][0]["items"][0]["count"]=2
        with self.assertRaises(ValueError): validate_plan(plan)

    def test_import_retains_times_angles_positions_and_does_not_mutate(self):
        combo=make_preset("parallel-alternating"); old=copy.deepcopy(combo)
        config=dict(combo=combo,plant=dict(key="pea",position=PLANT),grid=GRID,baseline=dict(attackInterval=1.5))
        plan=migrate(config); self.assertEqual(combo,old)
        self.assertEqual(len(all_items(plan)),5)
        a=ComboSimulation(combo,PLANT,TARGET,GRID); b=PlanSimulation(plan,PLANT,TARGET,GRID,repeat=False)
        for dt in (0,.2,.3,.1):
            a.step(dt,TARGET); b.step(dt,TARGET)
            x=sorted(tuple(round(v,5) for v in p["position"]) for p in a.bullets)
            y=sorted(tuple(round(v,5) for v in p["position"]) for p in b.bullets)
            self.assertEqual(x,y)
        self.assertEqual([i["id"] for g,i in all_items(plan)],[i["id"] for g,i in all_items(migrate(config))])

    def test_legacy_rows_migrate_to_relative_offsets(self):
        config=dict(combo=make_preset("rows-alternating"),plant=dict(key="pea",position=PLANT),grid=GRID)
        plan=migrate(config)
        self.assertEqual([i["route"]["rowOffset"] for g,i in all_items(plan)],[-1,1,-2,0,2])
        moved=[300,223]
        target=[830,222]
        sim=PlanSimulation(plan,moved,target,GRID,repeat=False); sim.step(.25,target)
        self.assertEqual(sorted(round(b["position"][1]) for b in sim.bullets),[108,304])

    def test_birth_grid_offsets_and_trigger_use_relative_logical_cells(self):
        plan=default_plan(); item=all_items(plan)[0][1]
        item["launch"].update(gridOffset=[2,-1],offset=[10,-5])
        self.assertEqual(launch_position(item,PLANT,GRID),[470,218])
        plan["trigger"].update(columns=[0,8],rows=[-2,3])
        self.assertTrue(can_trigger(plan,PLANT,TARGET,GRID))
        self.assertFalse(can_trigger(plan,PLANT,[950,320],GRID))
        self.assertFalse(can_trigger(plan,PLANT,[830,26],GRID))

    def test_launch_uses_exact_pixel_displacement_and_preserves_legacy_position(self):
        from attack_plan import place_launch
        plan=default_plan(); item=all_items(plan)[0][1]
        item["launch"].update(gridOffset=[2,-1],offset=[10.125,-5.75])
        old=launch_position(item,PLANT,GRID)
        point=[old[0]+.1234567,old[1]-.7654321]
        place_launch(item,point,PLANT,GRID)
        self.assertEqual(item["launch"]["gridOffset"],[0,0])
        self.assertEqual(item["launch"]["offset"],[point[i]-PLANT[i] for i in (0,1)])
        self.assertEqual(launch_position(item,PLANT,GRID),point)
        self.assertEqual(launch_position(item,PLANT,None),point)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"plan.json"; store_plan(path,plan)
            self.assertEqual(launch_position(all_items(load_plan(path))[0][1],PLANT,None),point)

    def test_domains_and_bezier_are_not_active_plan_fields(self):
        plan=default_plan(); self.assertNotIn("domain",plan)
        self.assertNotIn("domain",all_items(plan)[0][1])
        invalid=copy.deepcopy(plan); invalid["domain"]={"kind":"unbounded"}
        with self.assertRaises(ValueError): validate_plan(invalid)
        invalid=copy.deepcopy(plan); all_items(invalid)[0][1]["trajectory"]["kind"]="bezier"
        with self.assertRaises(ValueError): validate_plan(invalid)

    def test_initial_aim_and_turn_rate_are_independent(self):
        plan=default_plan(); item=all_items(plan)[0][1]; item["launch"]["offset"]=[0,0]
        plan["trigger"].update(columns=[-100,100],rows=[-100,100])
        item["guidance"].update(initialAim=False,trackingStrength=1)
        sim=PlanSimulation(plan,[0,0],[0,800],GRID,repeat=False); sim.step(0,[0,800]); sim.step(.1,[0,800])
        vx,vy=sim.bullets[0]["velocity"]
        self.assertGreater(math.degrees(math.atan2(vy,vx)),0)
        self.assertLessEqual(math.degrees(math.atan2(vy,vx)),12)
        item["guidance"].update(initialAim=True,trackingStrength=0)
        sim=PlanSimulation(plan,[0,0],[0,800],GRID,repeat=False); sim.step(0,[0,800]); sim.step(.1,[800,0])
        self.assertAlmostEqual(sim.bullets[0]["position"][0],0)

    def test_ray_endpoint_follow_speed_limits_update(self):
        plan=default_plan(); item=all_items(plan)[0][1]; item["carrier"]="ray"
        item["guidance"].update(endBinding="live",endpointFollowSpeed=10)
        sim=PlanSimulation(plan,PLANT,TARGET,GRID,repeat=False); sim.step(0,TARGET); sim.step(.1,[830,500])
        self.assertAlmostEqual(math.dist(sim.bullets[0]["endpoint"],TARGET),1)

    def test_ray_is_instant_geometry_with_duration_no_damage_fields(self):
        plan=default_plan(); item=all_items(plan)[0][1]
        item.update(carrier="ray",rayDuration=.5); item["guidance"]["endBinding"]="snapshot"
        sim=PlanSimulation(plan,PLANT,TARGET,GRID,repeat=False); sim.step(0,TARGET)
        self.assertEqual(sim.bullets[0]["rayEnd"],TARGET)
        sim.step(.49,[900,400]); self.assertEqual(sim.bullets[0]["rayEnd"],TARGET)
        sim.step(.01,TARGET); self.assertFalse(sim.bullets)
        self.assertNotIn("damage",item)

    def test_functions_are_sandboxed_and_wave_has_editable_parameters(self):
        plan=default_plan(); item=all_items(plan)[0][1]; item["trajectory"]["kind"]="function"
        plan["trigger"].update(columns=[-100,100],rows=[-100,100])
        validate_plan(plan)
        sim=PlanSimulation(plan,[0,0],[900,0],GRID,repeat=False); sim.step(.1,[900,0])
        self.assertAlmostEqual(sim.bullets[0]["position"][0],57)
        for source in ("__import__('os')", "t.__class__", "[t][0]", "sum(t for t in [])", "True"):
            with self.assertRaises(ValueError): Expression(source,{})
        for source in ("1/0","sqrt(-1)","2**100000"):
            expr=Expression(source,{})
            with self.assertRaises(ValueError): expr(dict(t=0,v=300))
        for name in ("正弦波","回旋线","函数抛物线"):
            item["trajectory"].update(function_preset(name)); validate_plan(plan)

    def test_rounds_preserve_delayed_items_and_variable_steps(self):
        plan=default_plan(interval=.5); item=all_items(plan)[0][1]; item["time"]=.8
        a=PlanSimulation(plan,PLANT,TARGET,GRID); b=PlanSimulation(plan,PLANT,TARGET,GRID)
        a.step(1.3,TARGET)
        for n in range(130): b.step(.01,TARGET)
        self.assertEqual(a.emitted,2); self.assertEqual(a.emitted,b.emitted)
        for x,y in zip(a.bullets,b.bullets):
            for v,w in zip(x["position"],y["position"]): self.assertAlmostEqual(v,w)

    def test_portable_save_and_implementation_drift(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); plan=default_plan(); f=root/"Entry.cs"; f.write_text("first")
            plan["implementation"]["files"]={"Entry.cs":file_sha(f)}
            store_plan(root/"plan.json",plan); self.assertEqual(load_plan(root/"plan.json"),plan)
            self.assertEqual(implementation_changes(plan,root),[])
            f.write_text("second"); self.assertEqual(implementation_changes(plan,root),["Entry.cs"])
            bound=bind_implementation(plan,["Entry.cs"],root)
            self.assertEqual(bound["implementation"]["appliedPlanSha256"],design_digest(bound))
            self.assertEqual(implementation_changes(bound,root),[])
            plan["implementation"]["files"]={"../outside":"hash"}
            with self.assertRaises(ValueError): implementation_changes(plan,root)


class AttackPlanWindowTests(unittest.TestCase):
    def drag_start(self,w,dx,dy):
        origin=launch_position(w.item,w.plant["position"],w.config.get("grid"))
        w.press(SimpleNamespace(x=origin[0]*w.scale,y=origin[1]*w.scale))
        self.assertEqual(w.drag[0],"origin")
        w.move(SimpleNamespace(x=(origin[0]+dx)*w.scale,y=(origin[1]+dy)*w.scale)); w.release()

    @contextmanager
    def window(self):
        try:
            import tkinter as tk
            from PIL import Image
            from attack_editor import AttackWindow
        except ImportError: self.skipTest("Optional GUI dependencies unavailable")
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp); assets={}
            for name in ("background","plant","target"):
                file=path/(name+".png"); Image.new("RGBA",(32,32),(40,120,70,200)).save(file)
                assets[name]=dict(path=str(file),sha256=file_sha(file))
            actor=dict(key="PlantPeaShooterSingle",position=PLANT[:],imageOrigin=[16,16],speed=0)
            config=dict(schemaVersion=3,sessionId="ui",canvas=[1080,600],assets=assets,provenance={},grid=GRID,
                        baseline=dict(bulletSpeed=300,attackInterval=1.5),plan=default_plan(),plant=actor,target=dict(actor,position=TARGET[:]))
            save(path/"session.json",config); self.assertEqual(load_session(path/"session.json")["schemaVersion"],3)
            try: root=tk.Tk()
            except tk.TclError as e: self.skipTest(str(e))
            root.withdraw(); window=None
            try:
                window=AttackWindow(root,config,path/"result.json",path/"plan.json",draft_root=path/"drafts")
                root.update(); yield window,root,path
            finally:
                if window is None or not window.finished: root.destroy()

    def test_control_order_keeps_help_local_and_preview_filter_first(self):
        with self.window() as (w,root,path):
            self.assertIs(w.left.pack_slaves()[0],w.only_selected_check)
            self.assertIs(w.tracking_hint.master,w.fields["guidance.trackingStrength"][0].frame)
            self.assertIs(w.speed_hint.master,w.fields["trajectory.speed"][0].frame)
            children=w.panel.pack_slaves()
            def index(path): return children.index(w.fields[path][0].frame)
            self.assertNotIn(w.fields["plan.intervalSeconds"][0].frame,children)
            self.assertIs(w.fields["plan.intervalSeconds"][0].frame.master,w.timeline_controls)
            self.assertIs(w.repeat_check.master,w.timeline_controls)
            self.assertLess(index("maxTravelCells"),index("guidance.trackingStrength"))
            self.assertLess(children.index(w.trigger_frame),index("trajectory.speed"))
            w.toggle_straight_advanced(); w.toggle_straight_advanced()
            self.assertEqual(w.tracking_hint.winfo_manager(),"pack")
            w.fields["trajectory.kind"][0].set("抛物线"); self.assertTrue(w.apply_fields())
            self.assertNotIn("trajectory.gravity",w.fields)
            self.assertNotIn("trajectory.flightTime",w.fields)
            self.assertFalse(hasattr(w,"corn_button"))
            self.assertIn("原版投手",w.ballistic_hint["text"])

    def test_timeline_header_owns_round_controls_without_shot_time_input(self):
        with self.window() as (w,root,path):
            self.assertEqual(root.title(),"攻击方案编辑器")
            self.assertFalse(hasattr(w,"time_value")); self.assertFalse(hasattr(w,"set_time"))
            w.toggle_advanced(); root.deiconify(); root.update()
            interval=w.fields["plan.intervalSeconds"][0]
            self.assertTrue(interval.frame.winfo_viewable()); self.assertTrue(w.repeat_check.winfo_viewable())
            centers=[widget.winfo_rooty()+widget.winfo_height()/2 for widget in (interval.label,interval.slider,interval.spin,w.repeat_check)]
            self.assertLessEqual(max(centers)-min(centers),2)
            self.assertLess(interval.label.winfo_rootx(),interval.slider.winfo_rootx())
            self.assertLess(interval.slider.winfo_rootx(),interval.spin.winfo_rootx())
            self.assertEqual(w.repeat_check["text"],"循环播放")
            self.assertLess(w.timeline_controls.winfo_rooty(),w.timeline.winfo_rooty())
            w.preset_kind.set("连射"); w.preset_gap.set(".3"); w.apply_preset()
            times=[i["time"] for _,i in all_items(w.plan)]
            interval.set("4.5"); self.assertTrue(w.apply_fields())
            self.assertEqual(w.plan["intervalSeconds"],4.5)
            self.assertEqual([i["time"] for _,i in all_items(w.plan)],times)
            w.fields["trajectory.kind"][0].set("抛物线"); self.assertTrue(w.apply_fields()); root.update()
            self.assertTrue(interval.frame.winfo_viewable()); self.assertTrue(w.repeat_check.winfo_viewable())
            w.repeat_check.invoke(); self.assertFalse(w.sim.repeat)
            w.save_plan(path/"round.json"); self.assertEqual(load_plan(path/"round.json")["intervalSeconds"],4.5)

    def test_advanced_presets_preserve_individual_fields_and_wheel_safety(self):
        with self.window() as (w,root,path):
            self.assertFalse(w.advanced); self.assertFalse(w.sidebar.winfo_manager())
            w.toggle_advanced(); root.update()
            self.assertLess(w.canvas.master.pack_slaves().index(w.sidebar),w.canvas.master.pack_slaves().index(w.rail))
            self.assertEqual(int(w.rail["height"]),int(w.canvas["height"]))
            w.preset_kind.set("扇形"); w.preset_count.set("5"); w.apply_preset()
            before=copy.deepcopy(w.plan); self.assertTrue(w.apply_fields()); self.assertEqual(w.plan,before)
            angles=[i["trajectory"]["direction"] for i in w.plan["groups"][-1]["items"]]
            w.fields["trajectory.speed"][0].set("2"); self.assertTrue(w.apply_fields())
            items=w.plan["groups"][-1]["items"]
            self.assertEqual([i["trajectory"]["speed"] for i in items],[600]*5)
            self.assertEqual([i["trajectory"]["direction"] for i in items],angles)
            root.deiconify(); root.update()
            combo=w.fields["carrier"][0].frame.winfo_children()[-1]; value=combo.get()
            combo.event_generate("<MouseWheel>",delta=-120); root.update(); self.assertEqual(combo.get(),value)
            start=w.tree.yview()[0]; w.tree.event_generate("<MouseWheel>",delta=-120); root.update()
            self.assertGreater(w.tree.yview()[0],start)
            w.toggle_advanced(); self.assertEqual([i["trajectory"]["direction"] for i in w.plan["groups"][-1]["items"]],angles)

    def test_straight_angle_entry_and_expanded_control_are_visible_and_hit_testable(self):
        with self.window() as (w,root,path):
            root.deiconify(); root.attributes("-topmost",True); root.lift(); root.update()
            panel=w.panel.scroll_canvas
            def inside_view(widget):
                self.assertGreaterEqual(widget.winfo_rooty(),panel.winfo_rooty())
                self.assertLessEqual(widget.winfo_rooty()+widget.winfo_height(),panel.winfo_rooty()+panel.winfo_height())
            inside_view(w.straight_button)
            self.assertIn("角度",w.straight_label.get())
            children=w.panel.pack_slaves()
            self.assertEqual(children.index(w.straight_button),children.index(w.fields["trajectory.kind"][0].frame)+1)
            w.toggle_straight_advanced(); root.update()
            angle=w.fields["trajectory.direction"][0].frame
            inside_view(angle)
            # A managed control can still be covered by its pack container.
            hit=root.winfo_containing(angle.winfo_rootx()+angle.winfo_width()//2,
                                      angle.winfo_rooty()+angle.winfo_height()//2)
            while hit is not None and hit!=angle: hit=hit.master
            self.assertIs(hit,angle)
            w.fields["trajectory.direction"][0].set("25"); self.assertTrue(w.apply_fields())
            self.assertEqual(w.item["trajectory"]["direction"],25)
            w.fields["trajectory.kind"][0].set("抛物线"); w.apply_fields()
            self.assertFalse(w.straight_button.winfo_manager())
            w.fields["trajectory.kind"][0].set("直线"); w.apply_fields(); root.update()
            inside_view(angle)
            self.assertEqual(w.fields["trajectory.direction"][0].get(),"25")

    def test_timeline_drag_group_preserves_internal_delays_and_cancel_preserves_saved_plan(self):
        with self.window() as (w,root,path):
            w.toggle_advanced(); w.preset_kind.set("奇偶交错"); w.apply_preset(); w.draw(); root.update()
            group=w.plan["groups"][-1]; items=group["items"]
            # The second group is row 2: dragging its title moves all five items.
            w.timeline_press(SimpleNamespace(x=45,y=80,state=0))
            self.assertIsNotNone(w.time_drag)
            w.timeline_move(SimpleNamespace(x=45+w.timeline_width/w.timeline_span,y=80))
            self.assertEqual([i["time"] for i in items],[1.5,1,1.5,1,1.5])
            w.save_plan(path/"plan.json"); saved=load_plan(path/"plan.json")
            w.shift_times({i["id"]:i["time"] for i in items},1)
            w.finish("cancelled")
            self.assertEqual(load_plan(path/"plan.json"),saved)
            result=json.loads((path/"result.json").read_text(encoding="utf-8"))
            self.assertFalse(result["confirmed"]); self.assertEqual(result["schemaVersion"],3)
            self.assertNotEqual(load_plan(w.draft_path),saved)

    def test_save_reopen_restore_confirm_and_invalid_input(self):
        with self.window() as (w,root,path):
            w.config["binding"]={"attack":"power","preserveActivationProbability":True}
            self.drag_start(w,0,-196)
            self.assertEqual(w.item["launch"]["gridOffset"],[0,0])
            self.assertAlmostEqual(w.item["launch"]["offset"][1],-213)
            self.assertTrue(w.save_plan(path/"plan.json")); saved=copy.deepcopy(w.plan)
            self.drag_start(w,0,98); w.autosave(force=True); draft=copy.deepcopy(w.plan)
            w.open_plan(path/"plan.json"); self.assertEqual(w.plan,saved)
            w.autosave(force=True); w.restore_draft(); self.assertEqual(w.plan,draft)
            var=w.fields["maxTravelCells"][0]; var.set("-1"); self.assertFalse(w.apply_fields())
            self.assertEqual(w.plan,draft); var.set("0"); w.finish("confirmed")
            data=json.loads((path/"result.json").read_text(encoding="utf-8"))
            self.assertTrue(data["confirmed"]); self.assertEqual(data["plan"],load_plan(path/"plan.json"))
            self.assertEqual(data["binding"],w.config["binding"])

    def test_single_item_slider_and_function_and_ray_controls(self):
        with self.window() as (w,root,path):
            original=w.sim
            for n in range(20):
                w.fields["trajectory.direction"][0].set(str(n)); w.apply_fields(defer=True)
            self.assertIs(w.sim,original); w.flush_preview(); self.assertIsNot(w.sim,original)
            w.fields["trajectory.kind"][0].set("函数曲线"); self.assertTrue(w.apply_fields())
            w.function_kind.set("回旋线"); w.apply_function_preset()
            self.assertIn("trajectory.parameters.R.value",w.fields)
            w.fields["carrier"][0].set("射线"); self.assertTrue(w.apply_fields()); root.update()
            self.assertFalse(w.fields["trajectory.speed"][0].frame.winfo_manager())
            self.assertNotIn("trajectory.flightTime",w.fields)
            self.assertEqual(w.fields["rayDuration"][0].frame.winfo_manager(),"pack")

    def test_parabola_hides_manual_direction_speed_and_guidance(self):
        with self.window() as (w,root,path):
            w.fields["trajectory.kind"][0].set("抛物线"); self.assertTrue(w.apply_fields()); root.update()
            for key in ("trajectory.direction","trajectory.speed","guidance.endBinding","guidance.trackingStrength"):
                self.assertFalse(w.fields[key][0].frame.winfo_manager())
            self.assertFalse(w.aim_frame.winfo_manager())
            self.assertNotIn("trajectory.flightTime",w.fields)
            self.assertNotIn("trajectory.gravity",w.fields)
            self.assertEqual(w.item["trajectory"]["catapultProfile"],"pvzhe-0.30-standard")
            self.assertEqual(w.ballistic_hint.winfo_manager(),"pack")
            self.assertFalse(w.fields["maxTravelCells"][0].frame.winfo_manager())
            self.assertIsNone(w.item["maxTravelCells"])
            w.fields["trajectory.kind"][0].set("直线"); w.apply_fields(); root.update()
            self.assertEqual(w.aim_frame.winfo_manager(),"pack")

    def test_straight_settings_and_preset_controls_are_contextual(self):
        with self.window() as (w,root,path):
            from attack_editor import KINDS
            self.assertNotIn("贝塞尔",KINDS)
            self.assertFalse(any("domain" in k or k in ("guidance.maxTurnRate","guidance.response","guidance.angleFalloff") for k in w.fields))
            self.assertGreaterEqual(float(w.fields["trajectory.speed"][0].slider["to"]),10)
            self.assertEqual(w.fields["trajectory.speed"][0].label["text"],"弹速倍率")
            self.assertFalse(w.fields["trajectory.direction"][0].frame.winfo_manager())
            self.assertFalse(w.straight_extra.winfo_manager())
            w.toggle_straight_advanced(); root.update()
            self.assertEqual(w.straight_extra.winfo_manager(),"pack")
            self.assertEqual(w.fields["trajectory.direction"][0].frame.pack_info()["in"],w.straight_extra)
            self.assertFalse(w.advanced)  # independent from group/timeline expansion
            w.preset_kind.set("扇形")
            self.assertEqual(w.preset_spread.frame.winfo_manager(),"pack"); self.assertFalse(w.preset_gap.frame.winfo_manager())
            w.preset_kind.set("连射")
            self.assertEqual(w.preset_gap.frame.winfo_manager(),"pack"); self.assertFalse(w.preset_spread.frame.winfo_manager())
            w.preset_kind.set("相对五行")
            self.assertFalse(w.preset_count.frame.winfo_manager()); self.assertFalse(w.preset_spread.frame.winfo_manager())
            w.preset_kind.set("奇偶交错"); w.preset_gap.set(".8"); w.apply_preset()
            self.assertEqual([i["time"] for i in w.plan["groups"][-1]["items"]],[.8,0,.8,0,.8])

    def test_renderer_draws_retained_objects_without_sampling_and_counts_rays_together(self):
        with self.window() as (w,root,path):
            for _ in range(1000): w.sim.spawn(w.item,"green",TARGET)
            w.draw()
            self.assertEqual(len(w.sim.bullets),951)
            self.assertEqual(len(w.dots),951)  # every survivor is drawn, not every Nth item
            ray=copy.deepcopy(w.item); ray.update(carrier="ray",rayDuration=10)
            for _ in range(1000): w.sim.spawn(ray,"blue",TARGET)
            w.draw()
            active=sum(w.canvas.itemcget(obj,"state")!="hidden" for obj in w.dots+w.rays)
            self.assertLessEqual(active,1000)
            self.assertEqual(len(w.sim.bullets),951)
            self.assertEqual(w.sim.bullets[-1]["carrier"],"ray")

    def test_reopening_without_edits_never_overwrites_a_newer_draft(self):
        with self.window() as (w,root,path):
            import tkinter as tk
            from attack_editor import AttackWindow
            w.save_plan(path/"plan.json")
            self.drag_start(w,54,0); draft=copy.deepcopy(w.plan)
            w.finish("cancelled")
            second_root=tk.Tk(); second_root.withdraw()
            second=AttackWindow(second_root,w.config,path/"second.json",path/"plan.json",draft_root=path/"drafts")
            try:
                second_root.update(); second.autosave(force=True)
                self.assertNotEqual(second.plan,draft)
                self.assertEqual(load_plan(second.draft_path),draft)
                second.finish("cancelled")
            finally:
                if not second.finished: second_root.destroy()
            third_root=tk.Tk(); third_root.withdraw()
            third=AttackWindow(third_root,w.config,path/"third.json",path/"plan.json",recover=True,draft_root=path/"drafts")
            try: self.assertEqual(third.plan,draft)
            finally: third_root.destroy()

    def test_dragged_origin_keeps_subpixel_offsets_and_displays_pixels(self):
        with self.window() as (w,root,path):
            before=launch_position(w.item,PLANT,GRID)
            trigger=copy.deepcopy(w.plan["trigger"])
            self.drag_start(w,.375,-.625)
            actual=launch_position(w.item,PLANT,GRID)
            for a,b in zip(actual,[before[0]+.375,before[1]-.625]): self.assertAlmostEqual(a,b)
            self.assertIn("px",w.start_label.get()); self.assertNotIn("相对行",w.start_label.get())
            self.assertEqual(w.plan["trigger"],trigger)
            self.assertTrue(w.save_plan(path/"pixels.json"))
            stored=all_items(load_plan(path/"pixels.json"))[0][1]
            self.assertEqual(stored["launch"],w.item["launch"])
            self.assertEqual(stored["launch"]["gridOffset"],[0,0])

    def test_map_trigger_draw_move_resize_and_launch_are_independent(self):
        with self.window() as (w,root,path):
            self.assertFalse(any(k.startswith("launch.") or k.startswith("plan.trigger.columns") or k.startswith("plan.trigger.rows") for k in w.fields))
            initial=launch_position(w.item,PLANT,GRID)
            self.drag_start(w,175,-101)
            actual=launch_position(w.item,PLANT,GRID)
            for a,b in zip(actual,[initial[0]+175,initial[1]-101]): self.assertAlmostEqual(a,b)
            launch=copy.deepcopy(w.item["launch"])
            w.toggle_trigger_edit(); self.assertTrue(w.edit_trigger)
            event=lambda x,y:SimpleNamespace(x=x*w.scale,y=y*w.scale)
            w.press(event(420,200)); w.move(event(900,500)); w.release()
            self.assertEqual(w.plan["trigger"]["columns"],[2,8])
            self.assertEqual(w.plan["trigger"]["rows"],[-1,3])
            w.press(event(700,369)); w.move(event(780,271)); w.release()
            self.assertEqual(w.plan["trigger"]["columns"],[3,9])
            self.assertEqual(w.plan["trigger"]["rows"],[-2,2])
            a,b=region_bounds(w.plan["trigger"],PLANT,GRID)
            w.press(event(*a)); w.move(event(a[0]-160,a[1]+98)); w.release()
            self.assertEqual(w.plan["trigger"]["columns"],[1,9])
            self.assertEqual(w.plan["trigger"]["rows"],[-1,2])
            self.assertEqual(w.item["launch"],launch)
            w.draw(); w.toggle_trigger_edit(); self.assertFalse(w.edit_trigger)

    def test_half_column_resize_is_real_and_rows_remain_whole(self):
        with self.window() as (w,root,path):
            self.assertEqual(w.plan["trigger"]["rows"],[0,1])
            self.assertNotIn("plan.trigger.kind",w.fields)
            w.toggle_trigger_edit()
            a,b=region_bounds(w.plan["trigger"],PLANT,GRID)
            y=(a[1]+b[1])/2
            w.press(SimpleNamespace(x=b[0]*w.scale,y=y*w.scale))
            w.move(SimpleNamespace(x=(b[0]-40)*w.scale,y=y*w.scale)); w.release()
            self.assertEqual(w.plan["trigger"]["columns"],[0,8.5])
            self.assertEqual(w.plan["trigger"]["rows"],[0,1])
            self.assertTrue(can_trigger(w.plan,PLANT,[930,320],GRID))
            self.assertFalse(can_trigger(w.plan,PLANT,[950,320],GRID))
            invalid=copy.deepcopy(w.plan); invalid["trigger"]["rows"]=[0,.5]
            with self.assertRaises(ValueError): validate_plan(invalid)


class GuidanceAndRegionTests(unittest.TestCase):
    def test_corn_reference_matches_release_birth_samples_without_fixed_horizontal_speed(self):
        from attack_plan import host_catapult_reference
        # Captured native launch: ground=(297.72858,341), z=94.740509.
        reference=host_catapult_reference([297.72858,341-94.74050903320312],[300,321])
        self.assertEqual(reference["height"],300)
        self.assertEqual(reference["gravity"],2000)
        self.assertAlmostEqual(reference["flightTime"],1.1760063381594204)
        self.assertAlmostEqual(-math.sqrt(2*2000*300),-1095.4451150103323)
        duration=reference["flightTime"]
        self.assertAlmostEqual((846.09796-297.72858)/duration,466.298,places=3)
        self.assertAlmostEqual((805.5884-297.72858)/duration,431.85126,places=3)
        self.assertGreater(host_catapult_reference([300,100],[300,321])["flightTime"],duration)

    def test_standard_catapult_matches_three_native_lobber_profiles(self):
        from attack_plan import host_catapult_reference
        samples=[(94.74050903320312,1.1760063381594204),
                 (61.73468017578125,1.1491663871150317),
                 (87.25352478027344,1.1700195322529736)]
        for z,duration in samples:
            reference=host_catapult_reference([300,341-z],[300,321])
            self.assertAlmostEqual(reference["flightTime"],duration)
            self.assertEqual(reference["height"],300)
        plan=default_plan(); item=all_items(plan)[0][1]; item["trajectory"]["kind"]="parabola"
        times=[]; velocities=[]
        for target in ([500,320],[900,320]):
            sim=PlanSimulation(plan,PLANT,target,GRID,repeat=False); sim.step(0,target)
            b=sim.bullets[0]; times.append(b["ballistics"]["flightTime"]); velocities.append(b["velocity"][0])
            self.assertNotIn("flightTime",item["trajectory"]); self.assertNotIn("gravity",item["trajectory"])
            sim.step(times[-1],target)
            for actual,expected in zip(b["position"],target): self.assertAlmostEqual(actual,expected)
        self.assertEqual(times[0],times[1]); self.assertLess(velocities[0],velocities[1])

    def test_host_arc_recalculates_from_launch_height_and_survives_offscreen(self):
        plan=default_plan(); item=all_items(plan)[0][1]
        item["trajectory"]["kind"]="parabola"
        item["launch"]["offset"][1]=-621
        sim=PlanSimulation(plan,PLANT,TARGET,GRID,repeat=False,canvas=[1080,600]); sim.step(0,TARGET)
        bullet=sim.bullets[0]; duration=bullet["ballistics"]["flightTime"]
        sim.step(duration/2,TARGET)
        self.assertEqual(len(sim.bullets),1); self.assertLess(bullet["position"][1],-256)
        sim.step(duration/2,TARGET)
        for actual,expected in zip(bullet["position"],TARGET): self.assertAlmostEqual(actual,expected)
        self.assertFalse(sim.bullets)

    def test_legacy_custom_ballistics_migrates_without_overwriting_input(self):
        old=default_plan(); old["schemaVersion"]=4
        item=all_items(old)[0][1]; item["trajectory"].update(kind="parabola",gravity=240,flightTime=1.6)
        original=copy.deepcopy(old)
        new=upgrade_plan(old); t=all_items(new)[0][1]["trajectory"]
        self.assertEqual(new["schemaVersion"],5)
        self.assertNotIn("gravity",t); self.assertNotIn("flightTime",t)
        self.assertEqual(t["catapultProfile"],"pvzhe-0.30-standard")
        self.assertEqual(old,original)
        self.assertTrue(any("标准投手" in note for note in new["migrationNotes"]))
        malformed=copy.deepcopy(new); all_items(malformed)[0][1]["trajectory"]["flightTime"]=2
        with self.assertRaises(ValueError): validate_plan(malformed)

    def test_removed_bezier_is_preserved_as_disabled_identity_on_import(self):
        old=default_plan(); old["schemaVersion"]=3
        old["domain"]={"kind":"radius","radius":100}
        item=all_items(old)[0][1]; original_id=item["id"]
        item["trajectory"].update(kind="bezier",controls=[[100,-50],[200,-50]],end=[300,0])
        item["domain"]={"kind":"rect"}; item["guidance"].pop("trackingStrength")
        item["guidance"].update(maxTurnRate=120,response=6,angleFalloff=2)
        upgraded=upgrade_plan(old); new=all_items(upgraded)[0][1]
        self.assertEqual(new["id"],original_id); self.assertFalse(new["enabled"])
        self.assertNotIn("domain",upgraded); self.assertNotIn("domain",new)
        self.assertNotIn("controls",new["trajectory"])
        self.assertNotIn("maxTurnRate",new["guidance"])
        self.assertTrue(any("贝塞尔" in note for note in upgraded["migrationNotes"]))
        self.assertEqual(old["schemaVersion"],3)
    def test_preview_evicts_oldest_fifty_only_after_crossing_one_thousand(self):
        plan=default_plan(); original=copy.deepcopy(plan); item=all_items(plan)[0][1]
        sim=PlanSimulation(plan,PLANT,TARGET,GRID,repeat=False)
        for _ in range(1000): sim.spawn(item,"green",TARGET)
        self.assertEqual(len(sim.bullets),1000); self.assertEqual(sim.discarded,0)
        ray=copy.deepcopy(item); ray["carrier"]="ray"
        sim.spawn(ray,"blue",TARGET)
        self.assertEqual(len(sim.bullets),951); self.assertEqual(sim.discarded,50)
        self.assertEqual(sim.bullets[0]["creationIndex"],50)
        self.assertEqual(sim.bullets[-1]["creationIndex"],1000)
        for _ in range(49): sim.spawn(item,"green",TARGET)
        self.assertEqual(len(sim.bullets),1000); self.assertEqual(sim.discarded,50)
        sim.spawn(item,"green",TARGET)
        self.assertEqual(len(sim.bullets),951); self.assertEqual(sim.discarded,100)
        self.assertEqual(sim.bullets[0]["creationIndex"],100)
        self.assertEqual(sim.emitted,1051); self.assertEqual(plan,original); self.assertEqual(sim.plan,original)

    def test_parabola_solves_velocity_and_locks_each_delayed_shot_at_its_birth(self):
        plan=default_plan(); first=all_items(plan)[0][1]
        first["trajectory"].update(kind="parabola",direction=160,speed=10)
        first["guidance"]["initialAim"]=False
        first["route"]["rowOffset"]=2  # inactive route data cannot spoil the ballistic endpoint
        second=copy.deepcopy(first); second.update(id="delayed-parabola",time=.5)
        plan["groups"][0]["items"].append(second)
        sim=PlanSimulation(plan,PLANT,TARGET,GRID,repeat=False); sim.step(0,TARGET)
        a=sim.bullets[0]; before=a["velocity"][:]
        newer=[790,350]; sim.step(.5,newer)
        b=sim.bullets[1]
        self.assertEqual(a["targetSnapshot"],TARGET); self.assertEqual(b["targetSnapshot"],newer)
        self.assertAlmostEqual(a["velocity"][0],before[0])
        sim.step(a["ballistics"]["flightTime"]-.5,[650,300])
        for actual,expected in zip(a["position"],TARGET): self.assertAlmostEqual(actual,expected)
        sim.step(.5,[900,320])
        for actual,expected in zip(b["position"],newer): self.assertAlmostEqual(actual,expected)
        self.assertFalse(sim.bullets)

    def test_parabola_has_no_range_clamp_even_after_old_plan_import(self):
        plan=default_plan(); item=all_items(plan)[0][1]
        item["trajectory"]["kind"]="parabola"; item["maxTravelCells"]=.5
        with self.assertRaises(ValueError): validate_plan(plan)
        plan["schemaVersion"]=3; upgraded=upgrade_plan(plan)
        self.assertIsNone(all_items(upgraded)[0][1]["maxTravelCells"])
        sim=PlanSimulation(upgraded,PLANT,TARGET,GRID,repeat=False,canvas=[1080,600])
        sim.step(0,TARGET); bullet=sim.bullets[0]
        sim.step(2,TARGET)
        for a,b in zip(bullet["position"],TARGET): self.assertAlmostEqual(a,b)
        self.assertFalse(bullet["rangeReached"])

    def test_range_depends_on_travelled_cells_not_elapsed_seconds(self):
        for speed in (100,200):
            plan=default_plan(); item=all_items(plan)[0][1]
            item["maxTravelCells"]=2.5; item["trajectory"]["speed"]=speed
            sim=PlanSimulation(plan,PLANT,TARGET,GRID,repeat=False)
            sim.step(190/speed,TARGET); bullet=sim.bullets[0]
            self.assertAlmostEqual(bullet["travelCells"],190/80)
            sim.step(20/speed,TARGET)
            self.assertFalse(sim.bullets)
            self.assertAlmostEqual(bullet["position"][0],PLANT[0]+27+200)
            self.assertAlmostEqual(bullet["travelCells"],2.5)
        plan=default_plan(); item=all_items(plan)[0][1]; item["trajectory"]["speed"]=100
        item["maxTravelCells"]=30
        sim=PlanSimulation(plan,PLANT,TARGET,GRID,repeat=False); sim.step(8,TARGET)
        self.assertEqual(len(sim.bullets),1)  # no hidden five-second lifespan
        self.assertAlmostEqual(sim.bullets[0]["travelCells"],10)
        self.assertNotIn("lifetime",item)

    def test_distance_is_measured_in_normalized_grid_space_and_curves_accumulate(self):
        plan=default_plan(); item=all_items(plan)[0][1]
        item["trajectory"].update(speed=math.hypot(80,98),direction=math.degrees(math.atan2(98,80)))
        sim=PlanSimulation(plan,PLANT,TARGET,GRID,repeat=False); sim.step(1,TARGET)
        self.assertAlmostEqual(sim.bullets[0]["travelCells"],math.sqrt(2))
        item["trajectory"].update(kind="function",**function_preset("回旋线")); item["maxTravelCells"]=4
        coarse=PlanSimulation(plan,PLANT,TARGET,GRID,repeat=False)
        fine=PlanSimulation(plan,PLANT,TARGET,GRID,repeat=False)
        coarse.step(0,TARGET); fine.step(0,TARGET)
        a,b=coarse.bullets[0],fine.bullets[0]
        coarse.step(2,TARGET)
        for _ in range(240): fine.step(1/120,TARGET)
        self.assertTrue(a["rangeReached"]); self.assertTrue(b["rangeReached"])
        self.assertAlmostEqual(a["travelCells"],4); self.assertLess(math.dist(a["position"],b["position"]),.01)

    def test_seconds_and_half_row_legacy_values_are_migrated_explicitly(self):
        old=default_plan(); old["schemaVersion"]=2; old["trigger"]["rows"]=[0,.5]
        item=all_items(old)[0][1]; item["lifetime"]=5; item.pop("maxTravelCells")
        upgraded=upgrade_plan(old)
        self.assertEqual(upgraded["schemaVersion"],5)
        self.assertEqual(upgraded["trigger"]["rows"],[0,1])
        self.assertIsNone(all_items(upgraded)[0][1]["maxTravelCells"])
        self.assertNotIn("lifetime",all_items(upgraded)[0][1]); self.assertEqual(len(upgraded["migrationNotes"]),2)

    def test_error_decay_and_strength_have_distinct_effects(self):
        guide=new_item()["guidance"]; guide.update(trackingStrength=1)
        fractions=[]
        for degrees in (10,90,170):
            error=math.radians(degrees); fractions.append(abs(steer_angle(0,error,guide,.05))/error)
        self.assertGreater(fractions[0],fractions[1]); self.assertGreater(fractions[1],fractions[2])
        weak=steer_angle(0,math.pi*.9,guide,.05)
        guide["trackingStrength"]=2; strong=steer_angle(0,math.pi*.9,guide,.05)
        self.assertGreater(strong,weak)
        # Almost opposite does not get permanently stuck; tiny errors cannot overshoot.
        self.assertNotEqual(steer_angle(0,math.pi,guide,.05),0)
        self.assertLessEqual(abs(steer_angle(0,.001,guide,.05)),.001)

    def test_old_regions_upgrade_without_changing_custom_rectangle_footprint(self):
        old=default_plan(); old["schemaVersion"]=1
        old["trigger"]=dict(kind="rect",columns=[0,7],rows=[-2,2],selection="inherited-target")
        upgraded=upgrade_plan(old)
        self.assertEqual(upgraded["trigger"]["columns"],[0,8]); self.assertEqual(upgraded["trigger"]["rows"],[-2,3])
        old["trigger"]["kind"]="any"
        self.assertEqual(upgrade_plan(old)["trigger"]["rows"],[0,1])
        self.assertEqual(old["schemaVersion"],1)


if __name__=="__main__": unittest.main()
