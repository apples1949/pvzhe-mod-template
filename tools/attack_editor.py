"""Explicit opt-in attack plan editor. No timeout, installation or automatic adoption."""
import argparse
import copy
import json
import math
from pathlib import Path
import time
import tkinter as tk
from tkinter import ttk, filedialog

from attack_model import load_session, save, digest
from attack_plan import (new_item, uid, migrate, validate_plan, all_items, preset, store_plan,
                         load_plan, implementation_changes, launch_position, PlanSimulation,
                         can_trigger, function_preset, design_digest,
                         place_launch, region_bounds, ballistic_velocity, host_catapult_reference)

BG, INK, BLUE, MUTED = "#f3f5f9", "#172033", "#496cf0", "#748094"
KINDS={"直线":"straight","抛物线":"parabola","函数曲线":"function"}
CARRIERS={"弹药":"projectile","射线":"ray"}
BINDINGS={"固定终点":"fixed","发射时目标位置":"snapshot","实时目标位置":"live"}


def get_path(obj,path):
    for key in path.split("."): obj=obj[int(key)] if isinstance(obj,list) else obj[key]
    return obj


def put_path(obj,path,value):
    parts=path.split(".")
    for key in parts[:-1]: obj=obj[int(key)] if isinstance(obj,list) else obj[key]
    key=int(parts[-1]) if isinstance(obj,list) else parts[-1]; obj[key]=value


class AttackWindow:
    def __init__(self,root,config,output,plan_path=None,recover=False,draft_root=None):
        from PIL import Image, ImageTk
        self.root,self.config,self.output=root,config,Path(output)
        if self.output.exists(): raise ValueError("请使用新的本轮结果路径")
        self.plan_path=Path(plan_path) if plan_path else None
        self.plan=load_plan(self.plan_path) if self.plan_path and self.plan_path.exists() else migrate(config)
        if self.plan_path and not self.plan_path.exists():
            import uuid
            self.plan["id"]=uuid.uuid5(uuid.NAMESPACE_URL,str(self.plan_path.resolve()).casefold()).hex
        self.draft_root=Path(draft_root or ".work/attack-preview/drafts")
        self.draft_path=self.draft_root/(self.plan["id"]+".json")
        self.recovery_path=self.draft_path
        if self.draft_path.exists() and not recover:
            self.recovery_path=self.draft_root/(self.plan["id"]+".recovery-"+config["sessionId"]+".json")
            store_plan(self.recovery_path,load_plan(self.draft_path))
        if recover and self.draft_path.exists(): self.plan=load_plan(self.draft_path)
        self.check_character(self.plan)
        self.initial_plan_sha=digest(self.plan)
        self.plant,self.target=copy.deepcopy(config["plant"]),copy.deepcopy(config["target"])
        self.selected={all_items(self.plan)[0][1]["id"]}; self.selected_groups=set()
        self.advanced=False; self.ready=False; self.finished=False; self.paused=False; self.drag=None
        self.edit_trigger=False; self.region_drag=None
        self.region_new=False
        self.due=None; self.error=""; self.notice=""; self.last=time.monotonic(); self.last_save=0.; self.last_draft=None
        self.fields={}; self.initial={}; self.scene=None; self.dots=[]; self.rays=[]; self.timeline_dirty=True
        self.time_drag=None; self.loading_tree=False; self.syncing=False
        self.base_speed=config.get("baseline",{}).get("bulletSpeed")
        self.scale=min(800/config["canvas"][0],445/config["canvas"][1]); w,h=[round(v*self.scale) for v in config["canvas"]]
        root.title("攻击方案编辑器"); root.configure(bg=BG); root.resizable(False,False)
        root.option_add("*Font",("Microsoft YaHei UI",10)); root.protocol("WM_DELETE_WINDOW",lambda:self.finish("cancelled"))
        shell=tk.Frame(root,bg=BG,padx=16,pady=12); shell.pack()
        head=tk.Frame(shell,bg=BG); head.pack(fill="x",pady=(0,10))
        tk.Label(head,text="攻击方案编辑器",bg=BG,fg=INK,font=("Microsoft YaHei UI",16,"bold")).pack(side="left")
        self.path_label=tk.StringVar(); tk.Label(head,textvariable=self.path_label,bg=BG,fg=MUTED).pack(side="left",padx=10)
        for label,cmd in (("打开方案",self.open_plan),("保存方案",self.save_plan),("恢复草稿",self.restore_draft)):
            ttk.Button(head,text=label,command=cmd).pack(side="right",padx=3)
        content=tk.Frame(shell,bg=BG); content.pack()
        self.sidebar=tk.Frame(content,bg=BG,width=208); self.sidebar.pack_propagate(False)
        self.left=self.scroller(self.sidebar,190)
        self.only_selected=tk.BooleanVar(value=False)
        self.only_selected_check=tk.Checkbutton(self.left,text="只预览所选项",variable=self.only_selected,command=self.replay,bg=BG)
        self.only_selected_check.pack(anchor="w",pady=(0,5))
        tk.Label(self.left,text="攻击组 / 发射项",bg=BG,fg=INK).pack(anchor="w",pady=(0,6))
        tree_box=tk.Frame(self.left,bg=BG); tree_box.pack(fill="x")
        self.tree=ttk.Treeview(tree_box,show="tree",height=7,selectmode="extended")
        self.tree_bar=ttk.Scrollbar(tree_box,orient="vertical",command=self.tree.yview)
        self.tree_bar.pack(side="right",fill="y"); self.tree.pack(side="left",fill="both",expand=True)
        self.tree.configure(yscrollcommand=self.tree_bar.set); self.tree.column("#0",width=145,minwidth=100)
        self.tree.bind("<<TreeviewSelect>>",self.select_tree); self.tree.bind("<MouseWheel>",self.scroll_tree)
        row=tk.Frame(self.left,bg=BG); row.pack(fill="x",pady=5)
        for label,cmd in (("＋项",self.add_item),("＋组",self.add_group),("复制",self.copy_selection),("删除",self.delete_selection)):
            ttk.Button(row,text=label,width=4,command=cmd).pack(side="left")
        self.name=tk.StringVar(); entry=ttk.Entry(self.left,textvariable=self.name); entry.pack(fill="x")
        entry.bind("<Return>",self.rename); entry.bind("<FocusOut>",self.rename)
        self.enabled=tk.BooleanVar(value=True)
        tk.Checkbutton(self.left,text="启用所选项 / 组",variable=self.enabled,command=self.enable_selection,bg=BG).pack(anchor="w")
        self.preset_kind=tk.StringVar(value="扇形")
        self.combo(self.left,self.preset_kind,["扇形","连射","奇偶交错","相对五行"])
        self.preset_count=self.numeric(self.left,"数量",5,1,120,1,common=(1,30),callback=False)
        self.preset_spread=self.numeric(self.left,"展开角度 / 度",45,0,180,1,callback=False)
        self.preset_gap=self.numeric(self.left,"发射间隔 / 秒",.1,0,10,.05,common=(0,2),callback=False)
        self.preset_button=ttk.Button(self.left,text="添加编排预设",command=self.apply_preset)
        self.preset_button.pack(fill="x",pady=4)
        self.preset_gaps={"连射":.1,"奇偶交错":.5,"相对五行":.5}; self.last_preset="扇形"
        self.preset_kind.trace_add("write",lambda *_:self.update_preset_fields())
        self.update_preset_fields()
        self.rail=tk.Frame(content,bg=BG,width=32,height=h); self.rail.pack(side="left",anchor="n"); self.rail.pack_propagate(False)
        self.advanced_label=tk.StringVar(value="◂\n\n高\n级")
        tk.Button(self.rail,textvariable=self.advanced_label,command=self.toggle_advanced,bg="#e5eaf6",fg=BLUE,
                  activebackground="#d7e0f5",relief="flat",bd=0,cursor="hand2").pack(fill="both",expand=True,padx=(0,4))
        self.canvas=tk.Canvas(content,width=w,height=h,bg="#537c3b",highlightthickness=0); self.canvas.pack(side="left")
        self.images={}
        for key,asset in config["assets"].items():
            with Image.open(asset["path"]) as im:
                im=im.convert("RGBA")
                if key=="background" and config.get("backgroundCrop"): im=im.crop(tuple(config["backgroundCrop"]))
                size=(w,h) if key=="background" else tuple(max(1,round(n*self.scale)) for n in im.size)
                self.images[key]=ImageTk.PhotoImage(im.resize(size,Image.Resampling.LANCZOS))
        box=tk.Frame(content,bg=BG,width=258); box.pack(side="left",fill="y"); box.pack_propagate(False)
        self.panel=self.scroller(box,240)
        self.controls_end=tk.Frame(self.panel,bg=BG,height=0); self.controls_end.pack(fill="x")
        self.add_enum("carrier","攻击载体",CARRIERS); self.add_enum("trajectory.kind","轨迹模型",KINDS)
        self.start_label=tk.StringVar()
        self.start_hint=tk.Label(self.panel,textvariable=self.start_label,bg=BG,fg=MUTED,anchor="w")
        self.aim=tk.BooleanVar()
        self.aim_frame=tk.Checkbutton(self.panel,text="初始瞄准",variable=self.aim,command=self.apply_fields,bg=BG); self.aim_frame.pack(anchor="w")
        self.ballistic_hint=tk.Label(self.panel,text="原版投手抛射 · 发射时锁定目标",wraplength=218,justify="left",bg=BG,fg=MUTED)
        self.add_enum("guidance.endBinding","终点绑定方式",BINDINGS)
        specs=[("trajectory.speed","弹速倍率" if self.base_speed else "弹速",1,5000,.05 if self.base_speed else 10,(.1,10) if self.base_speed else (10,1500)),
               ("trajectory.direction","发射角度 / 度",-180,180,1,(-180,180)),
               ("guidance.trackingStrength","追踪强度（0～2）",0,2,.1,(0,2)),
               ("rayLength","射线长度",1,10000,10,(50,2000)),("rayDuration","射线持续时间 / 秒",0,30,.05,(0,10)),
               ("maxTravelCells","射程（格，0=不限）",0,1000,.5,(0,30)),
               ("guidance.endpointFollowSpeed","端点跟随速度（0=立即）",0,10000,10,(0,3000))]
        for path,label,lo,hi,step,common in specs:
            if path=="trajectory.speed" and self.base_speed: lo/=self.base_speed; hi/=self.base_speed
            self.add_numeric(path,label,lo,hi,step,common)
        self.speed_hint=tk.Label(self.fields["trajectory.speed"][0].frame,text="1 倍＝普通豌豆弹速" if self.base_speed else "",bg=BG,fg=MUTED)
        self.tracking_hint=tk.Label(self.fields["guidance.trackingStrength"][0].frame,text="0 不追踪 · 1 弱 · 2 强",bg=BG,fg=MUTED)
        self.straight_advanced=False; self.straight_label=tk.StringVar(value="高级设置 ▸")
        self.straight_button=ttk.Button(self.panel,textvariable=self.straight_label,command=self.toggle_straight_advanced)
        self.straight_extra=tk.Frame(self.panel,bg=BG)
        self.add_numeric("route.rowOffset","行路线偏移",-100,100,1,(-4,4),self.straight_extra)
        self.trigger_frame=tk.Frame(self.panel,bg=BG)
        tk.Label(self.trigger_frame,text="攻击触发区域 · 矩形",bg=BG,fg=MUTED).pack(anchor="w",pady=3)
        self.trigger_button=tk.StringVar(value="在地图上调整范围")
        ttk.Button(self.trigger_frame,textvariable=self.trigger_button,command=self.toggle_trigger_edit).pack(fill="x",pady=3)
        self.function_options=tk.Frame(self.panel,bg=BG)
        self.function_kind=tk.StringVar(value="正弦波")
        self.combo(self.function_options,self.function_kind,["正弦波","回旋线","函数抛物线"],"函数预设")
        ttk.Button(self.function_options,text="应用函数预设",command=self.apply_function_preset).pack(fill="x")
        self.params_frame=tk.Frame(self.panel,bg=BG); self.formula_frame=tk.Frame(self.panel,bg=BG)
        for path,label in (("trajectory.x","x(t)"),("trajectory.y","y(t)")):
            self.add_text(path,label,self.formula_frame)
        self.parameter_edit=tk.Text(self.formula_frame,height=4,width=24,wrap="word"); self.parameter_edit.pack(fill="x",pady=4)
        ttk.Button(self.formula_frame,text="更新函数参数定义",command=self.apply_parameters).pack(fill="x")
        self.move_target=tk.BooleanVar(value=self.target.get("speed",0)>0)
        tk.Checkbutton(self.panel,text="移动目标",variable=self.move_target,bg=BG,command=self.replay).pack(anchor="w",pady=5)
        self.timeline_frame=tk.Frame(shell,bg=BG); header=tk.Frame(self.timeline_frame,bg=BG); header.pack(fill="x")
        tk.Label(header,text="时间轴 · 拖动发射项 / 组",bg=BG,fg=INK).pack(side="left")
        self.timeline_controls=tk.Frame(header,bg=BG); self.timeline_controls.pack(side="right")
        self.repeat=tk.BooleanVar(value=True)
        self.repeat_check=tk.Checkbutton(self.timeline_controls,text="循环播放",variable=self.repeat,command=self.replay,bg=BG)
        self.repeat_check.pack(side="right",padx=(12,0))
        self.add_numeric("plan.intervalSeconds","攻击间隔 / 秒",.1,30,.05,(.1,10),self.timeline_controls,inline=True)
        self.fields["plan.intervalSeconds"][0].frame.pack(side="right",fill="x",pady=2)
        self.timeline=tk.Canvas(self.timeline_frame,width=w+280,height=130,bg="white",highlightthickness=0)
        bar=ttk.Scrollbar(self.timeline_frame,orient="vertical",command=self.timeline.yview); bar.pack(side="right",fill="y")
        self.timeline.pack(fill="x",expand=True); self.timeline.configure(yscrollcommand=bar.set)
        self.timeline.bind("<MouseWheel>",lambda e:(self.timeline.yview_scroll(-1 if e.delta>0 else 1,"units"),"break")[1])
        self.timeline.bind("<ButtonPress-1>",self.timeline_press); self.timeline.bind("<B1-Motion>",self.timeline_move)
        self.timeline.bind("<ButtonRelease-1>",lambda e:setattr(self,"time_drag",None))
        self.footer=tk.Frame(shell,bg=BG); self.footer.pack(fill="x",pady=(10,0))
        self.status=tk.StringVar(); tk.Label(self.footer,textvariable=self.status,bg=BG,fg=MUTED,wraplength=500,justify="left").pack(side="left")
        for label,cmd in (("确认采用",lambda:self.finish("confirmed")),("取消",lambda:self.finish("cancelled")),("重播",self.replay),("暂停 / 播放",self.toggle_pause)):
            ttk.Button(self.footer,text=label,command=cmd).pack(side="right",padx=3)
        self.canvas.bind("<ButtonPress-1>",self.press); self.canvas.bind("<B1-Motion>",self.move)
        self.canvas.bind("<ButtonRelease-1>",self.release)
        root.bind("<MouseWheel>",self.scroll_panel,add="+"); self.protect_wheels(root)
        self.ready=True; self.load_fields(); self.refresh_tree(); self.replay(); self.check_references()
        save(self.output.with_suffix(".state.json"),dict(status="waiting",sessionId=config["sessionId"],planId=self.plan["id"]))
        self.tick()

    @property
    def item(self): return next(i for g,i in all_items(self.plan) if i["id"] in self.selected)

    def check_character(self,plan):
        key=self.config["plant"].get("key")
        if key and plan["character"]!=key: raise ValueError("方案角色与预览素材不同；请重新准备对应角色会话")

    def scroller(self,parent,width):
        c=tk.Canvas(parent,bg=BG,width=width,highlightthickness=0)
        bar=ttk.Scrollbar(parent,orient="vertical",command=c.yview); bar.pack(side="right",fill="y"); c.pack(side="left",fill="both",expand=True)
        c.configure(yscrollcommand=bar.set); panel=tk.Frame(c,bg=BG,padx=8)
        c.create_window(0,0,window=panel,anchor="nw",width=width)
        panel.bind("<Configure>",lambda e:c.configure(scrollregion=c.bbox("all"))); panel.scroll_canvas=c; return panel

    def combo(self,parent,var,values,label=None):
        frame=tk.Frame(parent,bg=BG); frame.pack(fill="x",pady=3)
        if label: tk.Label(frame,text=label,bg=BG,fg=MUTED).pack(anchor="w")
        box=ttk.Combobox(frame,textvariable=var,values=values,state="readonly",width=17); box.pack(fill="x")
        box.bind("<<ComboboxSelected>>",self.apply_fields); return frame

    def numeric(self,parent,title,value,lo,hi,step,common=None,callback=True,inline=False):
        frame=tk.Frame(parent,bg=BG); frame.pack(fill="x",pady=2)
        line=frame if inline else tk.Frame(frame,bg=BG)
        if not inline: line.pack(fill="x")
        label=tk.Label(line,text=title,bg=BG,fg=MUTED,font=("Microsoft YaHei UI",9)); label.pack(side="left")
        var=tk.StringVar(value=str(value))
        spin=ttk.Spinbox(line,from_=lo,to=hi,increment=step,width=7,textvariable=var,command=self.apply_fields if callback else None); spin.pack(side="right")
        if callback: spin.bind("<Return>",self.apply_fields); spin.bind("<FocusOut>",self.apply_fields)
        low,high=common or (lo,hi); slider=ttk.Scale(frame,from_=low,to=high,length=160 if inline else 100); slider.set(max(low,min(high,value)))
        if inline: slider.pack(side="left",fill="x",expand=True,padx=8)
        else: slider.pack(fill="x")
        def slide(raw):
            if self.syncing or not self.ready: return
            var.set(f"{round(round(float(raw)/step)*step,6):g}")
            if callback: self.apply_fields(defer=True)
        slider.configure(command=slide)
        if callback: slider.bind("<ButtonRelease-1>",lambda e:self.flush_preview())
        var.frame,var.slider,var.label,var.spin=frame,slider,label,spin; return var

    def add_numeric(self,path,label,lo,hi,step,common,parent=None,inline=False):
        var=self.numeric(parent or self.panel,label,lo,lo,hi,step,common,inline=inline)
        self.fields[path]=(var,"number",None)

    def add_enum(self,path,label,choices,parent=None):
        var=tk.StringVar(); var.frame=self.combo(parent or self.panel,var,list(choices),label)
        self.fields[path]=(var,"enum",choices)

    def add_text(self,path,label,parent):
        frame=tk.Frame(parent,bg=BG); frame.pack(fill="x")
        tk.Label(frame,text=label,bg=BG,fg=MUTED).pack(anchor="w")
        var=tk.StringVar(); entry=ttk.Entry(frame,textvariable=var); entry.pack(fill="x")
        entry.bind("<Return>",self.apply_fields); entry.bind("<FocusOut>",self.apply_fields)
        var.frame=frame; self.fields[path]=(var,"text",None)

    def scroll_panel(self,event):
        widget=event.widget
        while widget is not None:
            if hasattr(widget,"scroll_canvas"):
                widget.scroll_canvas.yview_scroll(-1 if event.delta>0 else 1,"units"); return "break"
            for panel in (getattr(self,"panel",None),getattr(self,"left",None)):
                if panel is not None and widget==panel.scroll_canvas:
                    widget.yview_scroll(-1 if event.delta>0 else 1,"units"); return "break"
            widget=widget.master

    def protect_wheels(self,widget):
        if isinstance(widget,(ttk.Combobox,ttk.Spinbox)):
            widget.bind("<MouseWheel>",lambda e:(self.scroll_panel(e),"break")[1])
        for child in widget.winfo_children(): self.protect_wheels(child)

    def scroll_tree(self,event):
        if self.tree.yview()!=(0.,1.): self.tree.yview_scroll(-1 if event.delta>0 else 1,"units")
        else: self.left.scroll_canvas.yview_scroll(-1 if event.delta>0 else 1,"units")
        return "break"

    def toggle_advanced(self):
        if not self.apply_fields(): return
        self.root.update_idletasks(); before=(self.canvas.winfo_rootx(),self.canvas.winfo_rooty()); self.advanced=not self.advanced
        if self.advanced:
            self.sidebar.pack(side="left",fill="y",before=self.rail); self.timeline_frame.pack(fill="x",pady=(8,0),before=self.footer)
        else:
            self.sidebar.pack_forget(); self.timeline_frame.pack_forget(); self.only_selected.set(False)
        self.advanced_label.set(("▸" if self.advanced else "◂")+"\n\n高\n级")
        self.update_visibility(); self.replay(); self.root.update_idletasks(); self.root.geometry(""); self.root.update_idletasks()
        x=self.root.winfo_x()+before[0]-self.canvas.winfo_rootx(); y=self.root.winfo_y()+before[1]-self.canvas.winfo_rooty()
        x=max(0,min(x,max(0,self.root.winfo_screenwidth()-self.root.winfo_width())))
        y=max(0,min(y,max(0,self.root.winfo_screenheight()-self.root.winfo_height()-40))); self.root.geometry(f"+{x}+{y}")

    def load_fields(self):
        self.syncing=True
        try:
            # Dynamic parameter sliders belong to the current item, not the source code.
            for path in [k for k in self.fields if k.startswith("trajectory.parameters.")]: del self.fields[path]
            for child in self.params_frame.winfo_children(): child.destroy()
            for key,param in self.item["trajectory"]["parameters"].items():
                self.add_numeric("trajectory.parameters."+key+".value",key,param["min"],param["max"],param["step"],None,self.params_frame)
            for path,(var,kind,choices) in self.fields.items():
                value=get_path(self.plan,path[5:]) if path.startswith("plan.") else get_path(self.item,path)
                if kind=="enum": value=next(k for k,v in choices.items() if v==value)
                elif value is None: value=0
                if path=="trajectory.speed" and self.base_speed: value/=self.base_speed
                var.set(f"{value:g}" if isinstance(value,(int,float)) else value)
                if hasattr(var,"slider"):
                    lo,hi=float(var.slider["from"]),float(var.slider["to"]); var.slider.set(max(lo,min(hi,value)))
            self.aim.set(self.item["guidance"]["initialAim"])
            self.initial={k:v[0].get() for k,v in self.fields.items()}; self.initial["aim"]=self.aim.get()
            self.name.set(self.item["name"]); self.enabled.set(self.item["enabled"])
            self.initial_name=self.name.get()
            self.parameter_edit.delete("1.0","end"); self.parameter_edit.insert("1.0",json.dumps(self.item["trajectory"]["parameters"],ensure_ascii=False,indent=2))
            self.path_label.set(self.plan_path.name if self.plan_path else "尚未保存方案")
            self.protect_wheels(self.params_frame)
        finally: self.syncing=False
        self.visibility_key=None
        self.update_visibility()

    def update_preset_fields(self):
        kind=self.preset_kind.get()
        if self.last_preset in self.preset_gaps:
            try: self.preset_gaps[self.last_preset]=float(self.preset_gap.get())
            except ValueError: pass
        if kind!=self.last_preset and kind in self.preset_gaps:
            value=self.preset_gaps[kind]; self.preset_gap.set(f"{value:g}")
            self.syncing=True
            try: self.preset_gap.slider.set(value)
            finally: self.syncing=False
        self.last_preset=kind
        for var,show in ((self.preset_count,kind!="相对五行"),(self.preset_spread,kind=="扇形"),(self.preset_gap,kind!="扇形")):
            var.frame.pack_forget()
            if show: var.frame.pack(fill="x",pady=2,before=self.preset_button)
        self.preset_gap.label.configure(text="发射间隔 / 秒" if kind=="连射" else "交错间隔 / 秒")

    def toggle_straight_advanced(self):
        self.straight_advanced=not self.straight_advanced
        self.update_visibility()

    def update_visibility(self):
        kind=self.item["trajectory"]["kind"]; ray=self.item["carrier"]=="ray"
        origin=launch_position(self.item,self.plant["position"],self.config.get("grid"))
        dx,dy=[origin[i]-self.plant["position"][i] for i in (0,1)]
        self.start_label.set(f"起点：拖动橙色标记\nX {dx:+.2f} · Y {dy:+.2f} px")
        key=(kind,ray,self.straight_advanced,self.advanced,self.item["guidance"]["endBinding"])
        if getattr(self,"visibility_key",None)==key: return
        self.visibility_key=key
        visible={"carrier"}
        if ray:
            visible|={"rayDuration","guidance.endBinding"}
            if self.item["guidance"]["endBinding"]=="fixed": visible|={"rayLength","trajectory.direction"}
            if self.item["guidance"]["endBinding"]=="live": visible.add("guidance.endpointFollowSpeed")
        else:
            visible.add("trajectory.kind")
            if kind in ("straight","function"): visible|={"maxTravelCells","trajectory.speed"}
            if kind=="straight": visible.add("guidance.trackingStrength")
            if kind=="function": visible.add("trajectory.direction")
        # Explicit reading order; parameter help belongs to its own field frame.
        for path,(var,field_kind,choices) in self.fields.items():
            if var.frame.master==self.panel: var.frame.pack_forget()
        blocks=[self.start_hint,self.trigger_frame,self.aim_frame,self.ballistic_hint,
                self.straight_button,self.straight_extra,
                self.formula_frame,self.params_frame,self.function_options]
        for block in blocks: block.pack_forget()
        def pack(widget): widget.pack(fill="x",pady=3,before=self.controls_end)
        def field(path):
            if path in visible: pack(self.fields[path][0].frame)
        field("carrier"); field("trajectory.kind")
        straight=not ray and kind=="straight"
        self.straight_label.set("直线高级：角度 / 行偏移 "+("▾" if self.straight_advanced else "▸"))
        if straight:
            pack(self.straight_button)
            if self.straight_advanced:
                pack(self.straight_extra)
                angle=self.fields["trajectory.direction"][0].frame
                angle.pack(in_=self.straight_extra,fill="x",pady=2,before=self.fields["route.rowOffset"][0].frame)
                # This field also serves rays/functions; its real parent is panel.
                # Raise it over the later-created advanced frame used as pack container.
                angle.lift(self.straight_extra)
        pack(self.start_hint); pack(self.trigger_frame)
        if not ray and kind=="parabola":
            pack(self.ballistic_hint)
        else:
            field("guidance.endBinding")
            if not ray or self.item["guidance"]["endBinding"]=="fixed": pack(self.aim_frame)
            for path in ("trajectory.speed","maxTravelCells","guidance.trackingStrength",
                         "rayLength","rayDuration","guidance.endpointFollowSpeed"):
                field(path)
        self.speed_hint.pack_forget(); self.tracking_hint.pack_forget()
        if "trajectory.speed" in visible and self.base_speed: self.speed_hint.pack(anchor="w")
        if straight: self.tracking_hint.pack(anchor="w")
        else: field("trajectory.direction")
        if not ray and kind=="function":
            pack(self.function_options); pack(self.params_frame)
            if self.advanced: pack(self.formula_frame)

    def apply_fields(self,event=None,defer=False):
        if not self.ready or self.syncing: return True
        proposed=copy.deepcopy(self.plan)
        try:
            for path,(var,kind,choices) in self.fields.items():
                raw=var.get()
                if raw==self.initial.get(path): continue
                value=choices[raw] if kind=="enum" else float(raw) if kind=="number" else raw
                if path=="trajectory.speed" and self.base_speed: value*=self.base_speed
                if path in ("guidance.endpointFollowSpeed","maxTravelCells") and value==0: value=None
                if path.startswith("plan."): put_path(proposed,path[5:],value)
                else:
                    for group,item in all_items(proposed):
                        if item["id"] in self.selected: put_path(item,path,value)
            for group,item in all_items(proposed):
                if item["id"] not in self.selected: continue
                if self.aim.get()!=self.initial["aim"]: item["guidance"]["initialAim"]=self.aim.get()
                if item["trajectory"]["kind"] in ("parabola","function"): item["guidance"]["trackingStrength"]=0.
                if item["trajectory"]["kind"]=="parabola": item["maxTravelCells"]=None
            validate_plan(proposed)
        except (ValueError,KeyError,TypeError,OverflowError) as e: self.error=str(e); self.due=None; return False
        changed=proposed!=self.plan; self.plan=proposed; self.error=""
        self.syncing=True
        try:
            for path in ("maxTravelCells","guidance.trackingStrength"):
                value=get_path(self.item,path) or 0.; var=self.fields[path][0]
                if float(var.get())!=value:
                    var.set(f"{value:g}"); var.slider.set(max(float(var.slider["from"]),min(float(var.slider["to"]),value)))
        finally: self.syncing=False
        self.initial={k:v[0].get() for k,v in self.fields.items()}; self.initial["aim"]=self.aim.get()
        if changed:
            self.update_visibility()
            if defer: self.due=time.monotonic()+.075
            else: self.replay()
        return True

    def apply_parameters(self):
        try:
            parameters=json.loads(self.parameter_edit.get("1.0","end")); proposed=copy.deepcopy(self.plan)
            for group,item in all_items(proposed):
                if item["id"] in self.selected: item["trajectory"]["parameters"]=copy.deepcopy(parameters)
            validate_plan(proposed)
        except (ValueError,KeyError,TypeError) as e: self.error=str(e); return
        self.plan=proposed; self.load_fields(); self.replay()

    def apply_function_preset(self):
        proposed=copy.deepcopy(self.plan)
        for group,item in all_items(proposed):
            if item["id"] in self.selected:
                item["trajectory"].update(function_preset(self.function_kind.get()),kind="function")
                item["guidance"]["trackingStrength"]=0.
        self.adopt(proposed,self.selected.copy())

    def refresh_tree(self):
        self.loading_tree=True
        try:
            # Reuse rows during drag; rebuilding the tree emits selection events.
            wanted={g["id"] for g in self.plan["groups"]}|{i["id"] for g,i in all_items(self.plan)}
            for parent in list(self.tree.get_children()):
                for child in list(self.tree.get_children(parent)):
                    if child not in wanted: self.tree.delete(child)
                if parent not in wanted: self.tree.delete(parent)
            for group in self.plan["groups"]:
                label=("● " if group["enabled"] else "○ ")+group["name"]
                if not self.tree.exists(group["id"]): self.tree.insert("","end",iid=group["id"],open=True)
                self.tree.item(group["id"],text=label)
                for i in group["items"]:
                    if not self.tree.exists(i["id"]): self.tree.insert(group["id"],"end",iid=i["id"])
                    self.tree.item(i["id"],text=f"{'●' if i['enabled'] else '○'} {i['name']}  {i['time']:g}s")
            selection=self.selected_groups or self.selected
            if set(self.tree.selection())!=selection: self.tree.selection_set(*selection)
        finally: self.loading_tree=False
        self.timeline_dirty=True

    def select_tree(self,event=None):
        if self.loading_tree: return
        values=set(self.tree.selection()); selected=set()
        groups={g["id"] for g in self.plan["groups"] if g["id"] in values}
        for g,i in all_items(self.plan):
            if i["id"] in values or g["id"] in groups: selected.add(i["id"])
        if selected and (selected!=self.selected or groups!=self.selected_groups):
            self.selected,self.selected_groups=selected,groups; self.load_fields(); self.timeline_dirty=True
        if len(groups)==1:
            group=next(g for g in self.plan["groups"] if g["id"] in groups)
            self.name.set(group["name"]); self.enabled.set(group["enabled"])
            self.initial_name=self.name.get()

    def rename(self,event=None):
        name=self.name.get().strip()
        if not self.ready or not name or len(name)>64 or name==self.initial_name: return
        for g in self.plan["groups"]:
            if self.selected_groups:
                if g["id"] in self.selected_groups: g["name"]=name
            else:
                for item in g["items"]:
                    if item["id"] in self.selected: item["name"]=name
        self.initial_name=name; self.refresh_tree()

    def enable_selection(self):
        for g in self.plan["groups"]:
            if self.selected_groups:
                if g["id"] in self.selected_groups: g["enabled"]=self.enabled.get()
            else:
                for item in g["items"]:
                    if item["id"] in self.selected: item["enabled"]=self.enabled.get()
        self.refresh_tree(); self.replay()

    def adopt(self,proposed,selected):
        try: validate_plan(proposed)
        except (ValueError,KeyError,TypeError) as e: self.error=str(e); return False
        self.plan=proposed; self.selected=selected; self.selected_groups=set()
        self.load_fields(); self.refresh_tree(); self.replay(); return True

    def add_item(self):
        if not self.apply_fields(): return
        proposed=copy.deepcopy(self.plan); group=next(g for g,i in all_items(proposed) if i["id"] in self.selected)
        item=new_item(); group["items"].append(item); self.adopt(proposed,{item["id"]})

    def add_group(self):
        proposed=copy.deepcopy(self.plan); item=new_item()
        proposed["groups"].append(dict(id=uid(),name="攻击组 "+str(len(proposed["groups"])+1),enabled=True,items=[item]))
        self.adopt(proposed,{item["id"]})

    def copy_selection(self):
        proposed=copy.deepcopy(self.plan); selected=set()
        if self.selected_groups:
            for group in list(proposed["groups"]):
                if group["id"] not in self.selected_groups: continue
                duplicate=copy.deepcopy(group); duplicate.update(id=uid(),name=group["name"][:58]+" 副本")
                for item in duplicate["items"]: item["id"]=uid(); selected.add(item["id"])
                proposed["groups"].append(duplicate)
        else:
            for group in proposed["groups"]:
                for item in list(group["items"]):
                    if item["id"] in self.selected:
                        duplicate=copy.deepcopy(item); duplicate.update(id=uid(),name=item["name"][:58]+" 副本")
                        group["items"].append(duplicate); selected.add(duplicate["id"])
        self.adopt(proposed,selected)

    def delete_selection(self):
        proposed=copy.deepcopy(self.plan)
        for g in proposed["groups"]: g["items"]=[i for i in g["items"] if i["id"] not in self.selected]
        proposed["groups"]=[g for g in proposed["groups"] if g["items"]]
        if not proposed["groups"]: self.error="至少保留一个发射项，可禁用"; return
        self.adopt(proposed,{all_items(proposed)[0][1]["id"]})

    def apply_preset(self):
        if not self.apply_fields(): return
        try:
            count=float(self.preset_count.get())
            if count!=int(count): raise ValueError("预设数量需为整数")
            group=preset(self.preset_kind.get(),self.item,int(count),float(self.preset_spread.get()),float(self.preset_gap.get()))
            proposed=copy.deepcopy(self.plan); proposed["groups"].append(group)
        except (ValueError,KeyError) as e: self.error=str(e); return
        self.adopt(proposed,{i["id"] for i in group["items"]})

    def target_point(self):
        p=self.target["position"][:]; offset=self.target.get("aimOffset",[0,0])
        if self.move_target.get(): p[1]+=math.sin(self.sim.time*.8 if hasattr(self,"sim") else 0)*45
        return [p[i]+offset[i] for i in (0,1)]

    def replay(self):
        try:
            self.sim=PlanSimulation(self.plan,self.plant["position"],self.target_point(),self.config.get("grid"),self.repeat.get(),self.selected if self.only_selected.get() else None,canvas=self.config["canvas"])
            self.sim.step(0,self.target_point()); self.due=None; self.timeline_dirty=True
        except ValueError as e: self.error=str(e)

    def flush_preview(self):
        if self.apply_fields() and self.due is not None: self.replay()

    def toggle_pause(self): self.paused=not self.paused

    def timeline_rows(self):
        rows=[]
        for g in self.plan["groups"]:
            rows.append((g["id"],g["name"],g["items"],True))
            rows.extend((i["id"],i["name"],[i],False) for i in g["items"])
        return rows

    def draw_timeline(self):
        if not self.advanced or not self.timeline_dirty: return
        c=self.timeline; c.delete("all")
        self.timeline_span=max(2.,self.plan["intervalSeconds"],max(i["time"]+(i["rayDuration"] if i["carrier"]=="ray" else 0) for g,i in all_items(self.plan))+.5)
        self.timeline_width=float(c["width"])-160
        for n in range(6): c.create_text(150+self.timeline_width*n/5,12,text=f"{self.timeline_span*n/5:.2g}s",fill=MUTED)
        for row,(identity,name,items,group) in enumerate(self.timeline_rows()):
            y=34+row*23; tags=("pick:"+identity,)
            c.create_text(8 if group else 20,y,text=name[:13],anchor="w",fill=INK if group else MUTED,tags=tags)
            for item in items:
                x=150+self.timeline_width*item["time"]/self.timeline_span
                end=x+(self.timeline_width*item["rayDuration"]/self.timeline_span if item["carrier"]=="ray" else 0)
                c.create_rectangle(x-3,y-5,max(x+4,end),y+5,fill=BLUE if item["id"] in self.selected else "#b2bfdc",outline="",tags=tags)
        c.configure(scrollregion=(0,0,float(c["width"]),max(130,len(self.timeline_rows())*23+28))); self.timeline_dirty=False

    def timeline_press(self,event):
        c=self.timeline; x,y=c.canvasx(event.x),c.canvasy(event.y)
        for obj in reversed(c.find_overlapping(x-2,y-2,x+2,y+2)):
            tags=[t for t in c.gettags(obj) if t.startswith("pick:")]
            if not tags: continue
            identity=tags[0][5:]; group=next((g for g in self.plan["groups"] if g["id"]==identity),None)
            clicked={i["id"] for i in group["items"]} if group else {identity}
            if not clicked.issubset(self.selected): self.selected=self.selected|clicked if event.state&4 else clicked
            self.selected_groups={identity} if group else set(); self.load_fields(); self.refresh_tree()
            self.time_drag=(x,{i["id"]:i["time"] for g,i in all_items(self.plan) if i["id"] in self.selected},self.timeline_span,self.timeline_width)
            return

    def shift_times(self,original,delta):
        lo=min(original.values()); hi=max(original.values()); delta=max(-lo,min(60-hi,delta))
        for g,i in all_items(self.plan):
            if i["id"] in original: i["time"]=round(original[i["id"]]+delta,6)
        self.refresh_tree(); self.replay()

    def timeline_move(self,event):
        if self.time_drag:
            x,original,span,width=self.time_drag
            self.shift_times(original,round((self.timeline.canvasx(event.x)-x)*span/width/.05)*.05)

    def toggle_trigger_edit(self):
        if not self.config.get("grid"):
            self.error="当前会话缺少发行网格，不能框选触发区域"; return
        if not self.apply_fields(): return
        self.edit_trigger=not self.edit_trigger; self.region_drag=None; self.drag=None
        if self.edit_trigger:
            self.region_new=False
        self.trigger_button.set("完成范围调整" if self.edit_trigger else "在地图上调整范围")
        self.canvas.configure(cursor="crosshair" if self.edit_trigger else "")

    def trigger_press(self,p):
        grid=self.config["grid"]; region=self.plan["trigger"]
        a,b=region_bounds(region,self.plant["position"],grid); tolerance=9/self.scale
        edge=""
        if a[0]-tolerance<=p[0]<=b[0]+tolerance:
            if abs(p[1]-a[1])<tolerance: edge+="n"
            elif abs(p[1]-b[1])<tolerance: edge+="s"
        if a[1]-tolerance<=p[1]<=b[1]+tolerance:
            if abs(p[0]-a[0])<tolerance: edge+="w"
            elif abs(p[0]-b[0])<tolerance: edge+="e"
        mode="new" if self.region_new else edge or ("move" if a[0]<=p[0]<=b[0] and a[1]<=p[1]<=b[1] else "new")
        self.region_new=False
        self.region_drag=(mode,p,copy.deepcopy(region),[a,b])
        if mode=="new": self.trigger_move(p)

    def trigger_move(self,p):
        if self.region_drag is None: return
        mode,start,old,bounds=self.region_drag; grid=self.config["grid"]
        plant_cell=[math.floor((self.plant["position"][i]-grid["begin"][i])/grid["size"][i]) for i in (0,1)]
        region=copy.deepcopy(old)
        if mode=="move":
            for i,key in enumerate(("columns","rows")):
                quantum=.5 if i==0 else 1.
                delta=round((p[i]-start[i])/grid["size"][i]/quantum)*quantum; region[key]=[v+delta for v in old[key]]
        elif mode=="new":
            for i,key in enumerate(("columns","rows")):
                quantum=.5 if i==0 else 1.
                coords=[(point[i]-grid["begin"][i])/grid["size"][i] for point in (start,p)]
                low=math.floor((min(coords)+1e-9)/quantum)*quantum
                high=max(low+quantum,math.ceil((max(coords)-1e-9)/quantum)*quantum)
                region[key]=[low-plant_cell[i],high-plant_cell[i]]
        else:
            for i,key,low,high in ((0,"columns","w","e"),(1,"rows","n","s")):
                quantum=.5 if i==0 else 1.
                snap=lambda v:round((v-grid["begin"][i])/grid["size"][i]/quantum)*quantum
                edges=[snap(point[i]) for point in bounds]
                if low in mode: edges[0]=snap(p[i])
                if high in mode: edges[1]=snap(p[i])
                left,right=sorted(edges)
                if right==left: right=left+quantum
                region[key]=[left-plant_cell[i],right-plant_cell[i]]
        proposed=copy.deepcopy(self.plan); proposed["trigger"]=region
        try: validate_plan(proposed)
        except ValueError as e: self.error=str(e); return
        self.plan=proposed; self.error=""; self.due=time.monotonic()+.075

    def release(self,event=None):
        self.drag=None; self.region_drag=None; self.flush_preview()

    def press(self,event):
        p=[event.x/self.scale,event.y/self.scale]
        if self.edit_trigger:
            self.trigger_press(p); return
        origin=launch_position(self.item,self.plant["position"],self.config.get("grid"))
        handles={"origin":origin,"target":self.target_point(),"plant":[self.plant["position"][0],self.plant["position"][1]-25]}
        for key,handle in handles.items():
            if math.dist(p,handle)<(10 if key.startswith("control") or key=="end" else 18 if key=="origin" else 40):
                self.drag=(key,p,copy.deepcopy(self.plan),copy.deepcopy(self.plant),copy.deepcopy(self.target)); return

    def move(self,event):
        if self.region_drag is not None:
            self.trigger_move([event.x/self.scale,event.y/self.scale]); return
        if self.drag is None: return
        key,p,plan,plant,target=self.drag; delta=[event.x/self.scale-p[0],event.y/self.scale-p[1]]; proposed=copy.deepcopy(plan)
        if key in ("target","plant"):
            actor=self.target if key=="target" else self.plant; old=target if key=="target" else plant
            actor["position"]=[old["position"][i]+delta[i] for i in (0,1)]
        else:
            for g,item in all_items(proposed):
                if item["id"] not in self.selected: continue
                if key=="origin":
                    old_origin=launch_position(item,self.plant["position"],self.config.get("grid"))
                    place_launch(item,[old_origin[i]+delta[i] for i in (0,1)],self.plant["position"],self.config.get("grid"))
            try: validate_plan(proposed)
            except ValueError as e: self.error=str(e); return
            self.plan=proposed
        self.load_fields(); self.due=time.monotonic()+.075

    def draw_region(self,region,color):
        grid=self.config.get("grid")
        if not grid or region["kind"]!="rect": return
        p=self.plant["position"]; s=self.scale
        a,b=region_bounds(region,p,grid)
        editing=self.edit_trigger and region is self.plan["trigger"]
        self.canvas.create_rectangle(*[v*s for v in a+b],outline=color,fill="#4caac5" if editing else "",
                                     stipple="gray25",width=2,dash=() if editing else (5,4),tags="guides")
        if editing:
            for x,y in ((a[0],a[1]),((a[0]+b[0])/2,a[1]),(b[0],a[1]),(b[0],(a[1]+b[1])/2),
                        (b[0],b[1]),((a[0]+b[0])/2,b[1]),(a[0],b[1]),(a[0],(a[1]+b[1])/2)):
                self.canvas.create_rectangle(x*s-4,y*s-4,x*s+4,y*s+4,fill="white",outline=color,tags="guides")
            text=f"触发区域 · 宽 {region['columns'][1]-region['columns'][0]:g} 列 × 高 {region['rows'][1]-region['rows'][0]:g} 行"
            self.canvas.create_text(max(5,a[0]*s+5),max(12,a[1]*s-12),text=text,anchor="w",fill="#e5f9ff",tags="guides")

    def draw(self):
        c,s=self.canvas,self.scale
        self.sim.trim_preview()
        if self.scene is None:
            c.create_image(0,0,anchor="nw",image=self.images["background"])
            self.scene={key:c.create_image(0,0,anchor="nw",image=self.images[key]) for key in ("plant","target")}
            grid=self.config.get("grid")
            if grid:
                for row in range(grid["rows"]): c.create_text((grid["begin"][0]-20)*s,(grid["begin"][1]+(row+.5)*grid["size"][1])*s,text=str(row+1),fill="#e4efbf")
        c.delete("guides")
        grid=self.config.get("grid")
        if self.edit_trigger and grid:
            x0,y0=grid["begin"]; bottom=y0+grid["rows"]*grid["size"][1]
            columns=grid.get("columns",max(1,math.ceil((self.config["canvas"][0]-x0)/grid["size"][0])))
            right=x0+columns*grid["size"][0]
            for row in range(grid["rows"]+1):
                y=y0+row*grid["size"][1]; c.create_line(x0*s,y*s,right*s,y*s,fill="#c1ddd1",dash=(4,4),tags="guides")
            for halfcol in range(columns*2+1):
                x=x0+halfcol*.5*grid["size"][0]; c.create_line(x*s,y0*s,x*s,bottom*s,fill="#c1ddd1",dash=(2,5) if halfcol%2 else (4,4),tags="guides")
        for key,actor,position in (("plant",self.plant,self.plant["position"]),("target",self.target,self.target_point())):
            offset=self.target.get("aimOffset",[0,0]) if key=="target" else [0,0]
            c.coords(self.scene[key],*[(position[i]-actor["imageOrigin"][i]-offset[i])*s for i in (0,1)])
        origin=launch_position(self.item,self.plant["position"],self.config.get("grid"))
        def dot(p,color,r=6): c.create_oval((p[0]*s-r,p[1]*s-r,p[0]*s+r,p[1]*s+r),fill=color,outline="white",width=2,tags="guides")
        dot(origin,"#f0a446"); target=self.target_point()
        dot(target,"#82c462" if can_trigger(self.plan,self.plant["position"],target,self.config.get("grid")) else "#dc7979",4)
        self.draw_region(self.plan["trigger"],"#83cfe1")
        if self.item["trajectory"]["kind"]=="parabola" and self.item["carrier"]=="projectile":
            reference=host_catapult_reference(origin,self.plant["position"]); duration=reference["flightTime"]
            vx,vy=ballistic_velocity(origin,target,duration,reference["gravity"])
            points=[[origin[0]+vx*duration*n/32,origin[1]+vy*duration*n/32+.5*reference["gravity"]*(duration*n/32)**2] for n in range(33)]
            c.create_line(*[v*s for p in points for v in p],fill="#e8efff",dash=(4,4),tags="guides")
            latched=next((b for b in self.sim.bullets if b["itemId"] in self.selected and "targetSnapshot" in b),None)
            if latched: dot(latched["targetSnapshot"],"#b376c9",4)
        visible=self.sim.bullets
        projectiles=[b for b in visible if b["carrier"]=="projectile"]
        while len(self.dots)<len(projectiles): self.dots.append(c.create_oval(0,0,1,1,outline="#4b602b",width=1))
        for index,obj in enumerate(self.dots):
            if index>=len(projectiles): c.itemconfigure(obj,state="hidden"); continue
            b=projectiles[index]; x,y=[v*s for v in b["position"]]
            c.coords(obj,x-4,y-4,x+4,y+4); c.itemconfigure(obj,state="normal",fill=b["color"] if b["canHit"] else "#9ba1a9")
        segments=[([b["origin"],b["rayEnd"]],b["color"]) for b in visible if b["carrier"]=="ray" and b["rayEnd"] is not None]
        while len(self.rays)<len(segments): self.rays.append(c.create_line(0,0,1,1,width=3))
        for n,obj in enumerate(self.rays):
            if n>=len(segments): c.itemconfigure(obj,state="hidden"); continue
            points,color=segments[n]; c.coords(obj,*[v*s for p in points for v in p]); c.itemconfigure(obj,state="normal",fill=color)
        self.draw_timeline()
        self.status.set(self.error or (("在地图上拖出触发区域" if self.region_new else "空白处框选 · 框内拖动 · 边缘拉伸") if self.edit_trigger else "") or self.notice or f"在场 {len(self.sim.bullets)}/1000 · 已发射 {self.sim.emitted} · 已清理 {self.sim.discarded}")

    def check_references(self):
        current=self.config.get("provenance",{}).get("releaseCacheKey"); previous=self.plan.get("reference",{}).get("releaseCacheKey")
        changed=implementation_changes(self.plan,Path.cwd())
        self.notice="实现文件已变化，采用前需由 AI 对照差异" if changed else "发行基准已变化，需重新验证" if previous and previous!=current else "；".join(self.plan.get("migrationNotes",[]))

    def save_plan(self,path=None):
        if not self.apply_fields(): return False
        path=path or self.plan_path
        if not path:
            folder=Path("design/attacks"); folder.mkdir(parents=True,exist_ok=True)
            path=filedialog.asksaveasfilename(parent=self.root,title="保存攻击方案",initialdir=str(folder.resolve()),initialfile=self.plan["character"]+".json",defaultextension=".json",filetypes=[("攻击方案","*.json")])
        if not path: return False
        try: store_plan(path,self.plan)
        except (OSError,ValueError) as e: self.error=str(e); return False
        self.plan_path=Path(path); self.path_label.set(self.plan_path.name); self.notice="方案已保存；尚未确认采用"; return True

    def open_plan(self,path=None):
        if path is None: path=filedialog.askopenfilename(parent=self.root,title="打开攻击方案",filetypes=[("攻击方案","*.json")])
        if not path: return
        try:
            plan=load_plan(path); self.check_character(plan); self.autosave(force=True)
            self.plan_path=Path(path); self.draft_path=self.draft_root/(plan["id"]+".json")
            self.initial_plan_sha=digest(plan)
            self.recovery_path=self.draft_path
            if self.draft_path.exists():
                self.recovery_path=self.draft_root/(plan["id"]+".recovery-"+self.config["sessionId"]+".json")
                store_plan(self.recovery_path,load_plan(self.draft_path))
            self.adopt(plan,{all_items(plan)[0][1]["id"]}); self.check_references()
        except (OSError,ValueError,KeyError,TypeError) as e: self.error=str(e)

    def restore_draft(self):
        if not self.recovery_path.exists(): self.notice="当前方案没有可恢复草稿"; return
        try:
            plan=load_plan(self.recovery_path); self.check_character(plan)
            self.adopt(plan,{all_items(plan)[0][1]["id"]}); self.notice="已恢复草稿，尚未确认采用"
        except (OSError,ValueError,KeyError,TypeError) as e: self.error=str(e)

    def autosave(self,force=False):
        now=time.monotonic()
        if not force and now-self.last_save<1: return
        sha=digest(self.plan)
        # Merely opening/cancelling an unchanged saved plan must not replace a newer draft.
        if sha==self.initial_plan_sha and self.draft_path.exists():
            self.last_save=now; return
        if sha!=self.last_draft: store_plan(self.draft_path,self.plan); self.last_draft=sha
        self.last_save=now

    def finish(self,status):
        if self.finished: return
        if status not in ("confirmed","cancelled"): raise ValueError("只能确认或取消")
        if status=="confirmed" and not self.apply_fields(): return
        if status=="confirmed" and self.plan_path is None:
            if not self.save_plan(): return
        try:
            self.autosave(force=True)
            if status=="confirmed" and self.plan_path: store_plan(self.plan_path,self.plan)
            record=dict(schemaVersion=3,status=status,confirmed=status=="confirmed",sessionId=self.config["sessionId"],
                        configSha256=digest(self.config),plan=copy.deepcopy(self.plan),planSha256=digest(self.plan),
                        designSha256=design_digest(self.plan),
                        planPath=str(self.plan_path.resolve()) if self.plan_path else None,
                        assets=self.config["assets"],provenance=self.config.get("provenance",{}),baseline=self.config.get("baseline"),
                        binding=copy.deepcopy(self.config.get("binding",{})),
                        canvas=self.config["canvas"],grid=self.config.get("grid"),plant=self.plant,target=self.target,
                        actorPlacementIsPreviewOnly=True,requiresRuntimeBinding=True,
                        implementationChanges=implementation_changes(self.plan,Path.cwd()))
            save(self.output,record); save(self.output.with_suffix(".state.json"),dict(status=status,sessionId=self.config["sessionId"],planId=self.plan["id"]))
        except (OSError,ValueError) as e: self.error=str(e); return
        self.finished=True; self.root.destroy()

    def tick(self):
        if self.finished: return
        now=time.monotonic(); dt=min(.05,now-self.last); self.last=now
        try:
            if self.due is not None and now>=self.due: self.flush_preview()
            if not self.paused: self.sim.step(dt,self.target_point())
            self.autosave(); self.draw()
        except (ValueError,OSError) as e: self.error=str(e); self.paused=True; self.status.set(self.error)
        self.root.after(16,self.tick)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session",required=True); parser.add_argument("--output",required=True)
    parser.add_argument("--plan",help="Project plan to open/save; extracted assets remain in the session")
    parser.add_argument("--recover",action="store_true",help="Explicitly restore this plan's autosaved draft")
    parser.add_argument("--customize",action="store_true")
    args=parser.parse_args()
    if not args.customize: parser.error("仅在玩家明确要求自定义攻击方式时打开")
    config=load_session(args.session)
    if not args.plan:
        import re
        name=re.sub(r"[^a-zA-Z0-9_.-]","_",config["plant"].get("key","character"))
        args.plan=str(Path("design/attacks")/(name+".json"))
    root=tk.Tk()
    try: AttackWindow(root,config,args.output,args.plan,args.recover)
    except Exception: root.destroy(); raise
    root.mainloop()


if __name__=="__main__": main()
