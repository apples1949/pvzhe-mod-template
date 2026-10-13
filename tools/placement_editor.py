"""Local visual placement input. Defaults to the asset-free demo."""
import argparse
import json
from pathlib import Path
import time
import tkinter as tk
from tkinter import ttk
from placement_model import Session, FeedbackClock, write_result

WIDTH, HEIGHT = 900, 500
INITIAL = [
    dict(id="action", text="演示按钮", x=60, y=360, width=160, height=48, color="#5166cf"),
    dict(id="counter", text="计数：123", x=650, y=40, width=170, height=52, color="#287e76"),
    dict(id="panel", text="信息面板", x=330, y=170, width=220, height=110, color="#886440"),
]

class PlacementWindow:
    def __init__(self, root, output, seconds=60, session=None):
        self.root, self.output, self.seconds = root, Path(output), seconds
        self.session = session or Session(demo_config())
        self.objects = self.session.layout["objects"]
        self.selected = self.objects[0]["id"]
        self.drag = None
        self.changed = False
        self.finished = False
        self.clock = FeedbackClock(seconds)
        self.images = {}
        self.render_images = {}
        self.show_regions = tk.BooleanVar(value=True)
        root.title(self.session.config.get("title", "摆放组件"))
        root.resizable(False, False)
        root.protocol("WM_DELETE_WINDOW", lambda: self.finish("cancelled"))
        root.configure(bg="#f3f5f9")
        root.option_add("*Font", ("Microsoft YaHei UI", 10))
        frame = tk.Frame(root, bg="#f3f5f9", padx=24, pady=20)
        frame.pack(fill="both", expand=True)
        header = tk.Frame(frame, bg="#f3f5f9")
        header.pack(fill="x", pady=(0, 16))
        tk.Label(header, text="摆放组件", font=("Microsoft YaHei UI", 17, "bold"),
                 bg="#f3f5f9", fg="#172033").pack(side="left")
        tk.Label(header, text="拖到你喜欢的位置", bg="#f3f5f9", fg="#7a8395").pack(side="left", padx=16)
        if len(self.session.layouts) > 1:
            self.mode = ttk.Combobox(header, state="readonly", width=14,
                values=[layout.get("label", layout["id"]) for layout in self.session.layouts])
            self.mode.current(next(i for i,l in enumerate(self.session.layouts) if l["id"] == self.session.active))
            self.mode.pack(side="left", padx=8)
            self.mode.bind("<<ComboboxSelected>>", self.switch_layout)
        self.timer = tk.StringVar(value=f"{seconds}s")
        tk.Label(header, textvariable=self.timer, bg="#e7ecf5", fg="#52617a", padx=12, pady=5).pack(side="right")
        self.canvas = tk.Canvas(frame, width=WIDTH, height=HEIGHT, bg="#161e2c", highlightthickness=0)
        self.canvas.pack()
        self.canvas.bind("<ButtonPress-1>", self.press)
        self.canvas.bind("<B1-Motion>", self.move)
        self.canvas.bind("<ButtonRelease-1>", lambda event: setattr(self, "drag", None))
        controls = tk.Frame(frame, bg="#f3f5f9")
        controls.pack(fill="x", pady=(16, 0))
        self.info = tk.StringVar()
        self.note = tk.StringVar(value="")
        self.w, self.h = tk.StringVar(), tk.StringVar()
        tk.Label(controls, textvariable=self.info, bg="#f3f5f9", fg="#68758a", anchor="w").pack(side="left")
        def action(parent, text, command, primary=False):
            button = tk.Button(parent, text=text, command=command, relief="flat", bd=0,
                bg="#496cf0" if primary else "#e7ebf2", fg="white" if primary else "#46536a",
                activebackground="#3d5ed3" if primary else "#dae1ed",
                activeforeground="white" if primary else "#172033", padx=16, pady=9, cursor="hand2")
            button.pack(side="right", padx=(8, 0))
        action(controls, "确认", lambda: self.finish("confirmed"), True)
        action(controls, "取消", lambda: self.finish("cancelled"))
        action(controls, "+60秒", self.extend)
        action(controls, "重置", self.reset)
        action(controls, "尺寸", self.edit_size)
        self.region_toggle = tk.Checkbutton(frame, text="占位提示", variable=self.show_regions,
            command=self.draw, bg="#f3f5f9", fg="#68758a", activebackground="#f3f5f9")
        self.prepare_layout()
        if any(layout.get("regions") for layout in self.session.layouts):
            self.region_toggle.pack(anchor="w", pady=(8, 0))
        self.draw()
        root.bind("<Map>", self.on_map, add="+")

    def on_map(self, event):
        if event.widget == self.root and self.clock.deadline is None:
            self.session.select(self.session.active)
            self.clock.start()
            self.tick()

    def prepare_layout(self):
        layout = self.session.layout
        self.width, self.height = layout["canvas"]["width"], layout["canvas"]["height"]
        self.scale = min(1, 900/self.width, 500/self.height)
        self.canvas.configure(width=round(self.width*self.scale), height=round(self.height*self.scale),
                              bg=layout.get("backgroundColor", "#161e2c"))
        for path in [layout.get("background"), *(item.get("image") for item in layout["objects"])]:
            if path and path not in self.images:
                try:
                    from PIL import Image
                except ImportError as error:
                    raise ValueError("图片预览需要 Pillow：python -m pip install Pillow") from error
                with Image.open(self.session.asset(path)) as loaded:
                    if loaded.width > 4096 or loaded.height > 4096:
                        raise ValueError("Preview image dimensions exceed 4096")
                    self.images[path] = loaded.convert("RGBA")
        if layout.get("background"):
            image = self.images[layout["background"]]
            if abs(image.width/image.height-self.width/self.height) > 0.01:
                raise ValueError("背景宽高比与逻辑画布不一致；先裁剪客户区或指定匹配画布")

    def photo(self, path, width, height):
        from PIL import Image, ImageTk
        key = (path, max(1, round(width)), max(1, round(height)))
        if key not in self.render_images:
            self.render_images[key] = ImageTk.PhotoImage(self.images[path].resize(key[1:], Image.Resampling.LANCZOS))
        return self.render_images[key]

    def switch_layout(self, event=None):
        self.session.select(self.session.layouts[self.mode.current()]["id"])
        self.objects = self.session.layout["objects"]
        self.selected = self.objects[0]["id"]
        self.drag = None
        self.render_images.clear()
        self.prepare_layout()
        self.draw()

    def item(self):
        return next(item for item in self.objects if item["id"] == self.selected)

    def rounded(self, x, y, w, h, fill, outline, tags, radius=12):
        r = min(radius, w/4, h/4)
        points = [x+r,y, x+w-r,y, x+w,y, x+w,y+r, x+w,y+h-r,
                  x+w,y+h, x+w-r,y+h, x+r,y+h, x,y+h, x,y+h-r, x,y+r, x,y]
        return self.canvas.create_polygon(points, smooth=True, splinesteps=24,
                    fill=fill, outline=outline, width=2, tags=tags)

    def draw(self):
        self.canvas.delete("all")
        layout = self.session.layout
        if layout.get("background"):
            self.canvas.create_image(0, 0, anchor="nw", image=self.photo(layout["background"], self.width*self.scale, self.height*self.scale))
        if self.show_regions.get():
            for region in layout.get("regions", []):
                x,y,w,h = (region[k]*self.scale for k in ("x","y","width","height"))
                self.canvas.create_rectangle(x,y,x+w,y+h, outline="#d9a759", dash=(4,4), width=1)
                self.canvas.create_text(x+4,y+4,anchor="nw",text=region.get("label",""),fill="#e0b876")
        for item in self.objects:
            x, y, w, h = (item[key]*self.scale for key in ("x", "y", "width", "height"))
            tags = ("component", item["id"])
            selected = item["id"] == self.selected
            if item.get("image"):
                padding = item.get("imagePadding",0)*self.scale
                self.canvas.create_image(x-padding,y-padding,anchor="nw",image=self.photo(item["image"],w+padding*2,h+padding*2),tags=tags)
                if selected:
                    self.canvas.create_rectangle(x,y,x+w,y+h,outline="#91aaff",width=2,tags=tags)
                continue
            self.rounded(x, y+4, w, h, "#0e1420", "", tags)
            fill = "#496cf0" if item["id"] == "action" else "#263246"
            self.rounded(x, y, w, h, fill, "#91aaff" if selected else "#35445b", tags)
            if item["id"] == "panel" and h >= 80:
                self.canvas.create_text(x+18, y+24, text=item["text"], anchor="w", fill="#edf2ff",
                                        font=("Microsoft YaHei UI", 11, "bold"), tags=tags)
                for i, length in enumerate([w-36, w-70]):
                    if length > 0:
                        self.canvas.create_line(x+18, y+54+i*18, x+18+length, y+54+i*18,
                                                fill="#465773", width=4, tags=tags)
            else:
                self.canvas.create_text(x+w/2, y+h/2, text=item["text"], fill="#ffffff",
                                        font=("Microsoft YaHei UI", 11, "bold"), tags=tags)
            if selected:
                for px, py in [(x,y),(x+w,y),(x,y+h),(x+w,y+h)]:
                    self.canvas.create_rectangle(px-3,py-3,px+3,py+3,fill="#bed0ff",outline="",tags=tags)
        item = self.item()
        self.info.set(f'{item["text"]}   ·   {item["x"]}, {item["y"]}')
        self.w.set(str(item["width"]))
        self.h.set(str(item["height"]))

    def edit_size(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("组件尺寸")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        frame = ttk.Frame(dialog, padding=18)
        frame.pack()
        ttk.Label(frame, text="宽").grid(row=0, column=0, padx=6)
        ttk.Entry(frame, textvariable=self.w, width=8).grid(row=0, column=1)
        ttk.Label(frame, text="高").grid(row=0, column=2, padx=6)
        ttk.Entry(frame, textvariable=self.h, width=8).grid(row=0, column=3)
        ttk.Label(frame, textvariable=self.note).grid(row=1, column=0, columnspan=4, pady=8)
        def apply():
            self.note.set("")
            self.resize()
            if not self.note.get():
                dialog.destroy()
        ttk.Button(frame, text="应用", command=apply).grid(row=2, column=0, columnspan=4)
        self.note.set("")

    def press(self, event):
        hits = self.canvas.find_overlapping(event.x, event.y, event.x, event.y)
        for hit in reversed(hits):
            tags = self.canvas.gettags(hit)
            if "component" in tags:
                self.selected = tags[1]
                item = self.item()
                self.drag = (event.x/self.scale-item["x"], event.y/self.scale-item["y"])
                self.draw()
                return

    def move(self, event):
        if self.drag is None:
            return
        item = self.item()
        x = max(0, min(self.width-item["width"], round(event.x/self.scale-self.drag[0])))
        y = max(0, min(self.height-item["height"], round(event.y/self.scale-self.drag[1])))
        self.session.update(item["id"], x=x, y=y)
        self.changed = True
        self.draw()

    def resize(self):
        try:
            w, h = int(self.w.get()), int(self.h.get())
            item = self.item()
            if not (20 <= w <= self.width-item["x"] and 20 <= h <= self.height-item["y"]):
                raise ValueError
        except ValueError:
            self.note.set("请输入画布内有效尺寸（至少20）")
            return
        self.session.update(item["id"], width=w, height=h)
        self.render_images.clear()
        self.changed = True
        self.note.set("")
        self.draw()

    def reset(self):
        self.session.reset()
        self.objects = self.session.layout["objects"]
        self.render_images.clear()
        self.changed = True
        self.draw()

    def extend(self):
        self.clock.extend()

    def tick(self):
        if self.finished:
            return
        remaining = self.clock.remaining
        self.timer.set(f"{remaining}s")
        if remaining == 0:
            self.finish("timeout")
        else:
            self.root.after(200, self.tick)

    def finish(self, status):
        if self.finished:
            return
        self.finished = True
        result = self.session.result(status)
        write_result(self.output, result)
        print(json.dumps(result, ensure_ascii=False), flush=True)
        self.root.destroy()


def demo_config():
    return dict(schemaVersion=1, title="摆放组件 · 演示", context={"kind":"demo"},
        layouts=[dict(id="demo", label="演示", canvas=dict(width=WIDTH,height=HEIGHT), objects=INITIAL)])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", help="Local preview JSON; defaults to demo")
    parser.add_argument("--resume", help="Restore a draft/result from the same config")
    parser.add_argument("--output", default=".work/placement-editor/result.json")
    parser.add_argument("--seconds", type=int, default=60)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.seconds <= 0 or args.seconds > 86400:
        parser.error("--seconds must be 1..86400")
    root = None
    try:
        if args.config:
            session = Session.load(args.config, args.resume)
        else:
            previous = json.loads(Path(args.resume).read_text(encoding="utf-8")) if args.resume else None
            session = Session(demo_config(), resume=previous)
        root = tk.Tk()
        root.withdraw()
        window = PlacementWindow(root, args.output, args.seconds, session)
        # Validate all layout assets before the feedback timer starts.
        active = session.active
        for layout in session.layouts:
            session.active = layout["id"]
            window.prepare_layout()
        session.active = active
        window.prepare_layout()
        window.draw()
        if args.self_test:
            from types import SimpleNamespace
            first = window.item()
            x,y = first["x"],first["y"]
            window.press(SimpleNamespace(x=(x+10)*window.scale,y=(y+10)*window.scale))
            window.move(SimpleNamespace(x=(x+30)*window.scale,y=(y+30)*window.scale))
            assert window.item()["x"] == max(0,min(window.width-first["width"],round(x+20)))
            assert window.item()["y"] == max(0,min(window.height-first["height"],round(y+20)))
            window.w.set(str(first["width"])); window.h.set(str(first["height"])); window.resize()
            window.finish("confirmed")
            print("PASS: Tk drag/resize and logical-coordinate result", file=__import__("sys").stderr)
        else:
            root.deiconify()
            root.mainloop()
    except (ValueError, OSError, tk.TclError) as error:
        if root is not None:
            try: root.destroy()
            except tk.TclError: pass
        parser.exit(2, f"Preview failed: {error}\n")

if __name__ == "__main__":
    main()
