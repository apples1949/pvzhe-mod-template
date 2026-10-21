"""Local, opt-in template attack editor; no automatic Mod installation."""
import argparse
import copy
import json
import math
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import secrets
import threading
import uuid
import webbrowser
import os
from urllib.parse import urlparse

from attack_model import digest, load_session, save, file_sha
from attack_plan import default_plan, new_item, validate_plan, load_plan, design_digest, same_design, implementation_changes
from attack_templates import TemplateStore, TemplateConflict

STATIC = Path(__file__).with_name("attack_web")
ORIGIN_PRESETS = json.loads((STATIC / "origins.json").read_text(encoding="utf-8"))


def default_recipe(character="PlantPeaShooterSingle"):
    preset = ORIGIN_PRESETS["presets"]["pea-front"]
    return dict(format="pvzhe.attack-recipe", schemaVersion=18, id=uuid.uuid4().hex,
                character=character, pattern="straight", count=1, spread=45, direction=0., spacing=20., angleOffset=0., trackingStrength=2.,
                ammo="normal", deploymentSeconds=.15, shotDelaySeconds=0., intervalSeconds=1.5, speed=300., rangeCells=0., radius=preset["radius"],
                origin=list(preset["origin"]), originPreset="pea-front")


def validate_single_recipe(r):
    keys = set(default_recipe())
    if not isinstance(r, dict) or set(r) != keys:
        raise ValueError("方案字段不完整或不支持；复杂旧方案请保留原设计并交给AI分析差量修改")
    if r["format"] != "pvzhe.attack-recipe" or r["schemaVersion"] != 18:
        raise ValueError("不支持的简易方案格式")
    for key in ("id", "character"):
        if not isinstance(r[key], str) or not r[key] or len(r[key]) > 128:
            raise ValueError("缺少方案/角色身份")
    if r["pattern"] not in ("straight", "fan", "ring", "lob", "parallel", "starfruit") or r["ammo"] not in ("normal", "homing"):
        raise ValueError("未知攻击样式或弹药类型")
    for key, low, high in (("count", 1, 120), ("spread", 0, 360),
                           ("intervalSeconds", .1, 60), ("speed", 30, 3000), ("radius", 0, 400), ("rangeCells", 0, 1000), ("direction", 0, 360), ("spacing", 0, 400), ("angleOffset", 0, 360), ("trackingStrength", 0, 2), ("shotDelaySeconds", 0, 5), ("deploymentSeconds",0,1)):
        x = r[key]
        if isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) or not low <= x <= high:
            raise ValueError("参数超出范围：" + key)
    if type(r["count"]) is not int:
        raise ValueError("弹数必须是整数")
    if abs(r["trackingStrength"]*10-round(r["trackingStrength"]*10))>1e-8:
        raise ValueError("追踪强度以0.1为步进")
    gap=r["shotDelaySeconds"]
    if abs(gap*100-round(gap*100))>1e-8:raise ValueError("发射延迟以0.01秒为步进")
    if r["deploymentSeconds"]!=.15:raise ValueError("排射固定先展开0.15秒再发射")
    origin = r["origin"]
    if not isinstance(origin, list) or len(origin) != 2 or any(isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) or abs(x)>4096 for x in origin):
        raise ValueError("起点偏移无效")
    if r["originPreset"] != "custom":
        p = ORIGIN_PRESETS["presets"].get(r["originPreset"])
        if p is None or p["origin"] != origin or p.get("patternOnly",r["pattern"])!=r["pattern"]:
            raise ValueError("预设标识与起点不一致，请标为自定义")
    return r


def load_recipe(path):
    r = json.loads(Path(path).read_text(encoding="utf-8"))
    note = None
    if isinstance(r,dict) and r.get("format")=="pvzhe.attack-composition":return validate_recipe(r),None
    if isinstance(r, dict) and r.get("format") == "pvzhe.attack-recipe" and r.get("schemaVersion") in (1,2):
        version = r["schemaVersion"]
        expected = set(default_recipe()) - {"originPreset", "radius", "rangeCells", "direction", "spacing", "angleOffset", "trackingStrength", "shotDelaySeconds", "deploymentSeconds"} if version==1 else set(default_recipe()) - {"originPreset", "origin", "rangeCells", "direction", "spacing", "angleOffset", "trackingStrength", "shotDelaySeconds", "deploymentSeconds"}
        if set(r) != expected:
            raise ValueError("旧方案字段不完整，不能迁移")
        if version==1:
            r["radius"]=0.
        else:
            r["origin"]=[0.,0.]
        r.update(schemaVersion=3, originPreset="custom")
        note = "已保留旧方案的实际起点/半径，标为自定义；新方案默认豌豆正。采用前原文件不改写。"
    if isinstance(r, dict) and r.get("schemaVersion")==3:
        r.update(schemaVersion=4, rangeCells=0.)
        note = (note or "") + "旧方案保留不限射程；可在整体设置调整。"
    if isinstance(r, dict) and r.get("schemaVersion")==4:
        r.update(schemaVersion=5, direction=0., spacing=20.)
    if isinstance(r, dict) and r.get("schemaVersion")==5:
        if r.get("pattern")=="bidirectional":
            r.update(pattern="ring",count=2)
            note=(note or "")+"旧双向保留为两颗环形，不改成投掷。"
        r["schemaVersion"]=6
    if isinstance(r, dict) and r.get("schemaVersion")==6:
        r["schemaVersion"]=7
        if r.get("pattern")=="lob":note=(note or "")+"投掷采用固定投手起点，其他样式的位置配置保留。"
    if isinstance(r, dict) and r.get("schemaVersion")==7:
        r["schemaVersion"]=8
        if r.get("pattern")=="lob":
            r["speed"]=300.
            note=(note or "")+"旧投掷保持1倍飞行射速，可在发射设置调整。"
    if isinstance(r, dict) and r.get("schemaVersion")==8:
        r.update(schemaVersion=9,angleOffset=0.,trackingStrength=2.)
        note=(note or "")+"追踪弹药采用初始瞄准与可调强度，请重新预览确认。"
    if isinstance(r, dict) and r.get("schemaVersion")==9:
        r["schemaVersion"]=10
        note=(note or "")+"已修正锚点与出膛角关系，追踪在首次位移后纠偏，请重新预览。"
    if isinstance(r, dict) and r.get("schemaVersion")==10:
        r["schemaVersion"]=11
        if r.get("pattern")=="cross":
            r.update(pattern="ring",count=4)
            note=(note or "")+"四向保留为4颗环形。"
    if isinstance(r, dict) and r.get("schemaVersion")==11:
        r["schemaVersion"]=12
        if isinstance(r.get("angleOffset"),(int,float)) and r["angleOffset"]<0:
            r["angleOffset"]%=360
    if isinstance(r, dict) and r.get("schemaVersion")==12:
        r.update(schemaVersion=13,shotDelaySeconds=0.)
    if isinstance(r, dict) and r.get("schemaVersion")==13:r["schemaVersion"]=14
    if isinstance(r, dict) and r.get("schemaVersion")==14:
        r["schemaVersion"]=15
        if r.get("originPreset")=="starfruit":
            r["originPreset"]="center"
            note=(note or "")+"杨桃出弹位置已合并为中心，保留原生五个出弹点。"
        elif r.get("originPreset")=="center":
            r["originPreset"]="custom"
            note=(note or "")+"保留旧中心实际参数为自定义；新版中心半径为0。"
    if isinstance(r, dict) and r.get("schemaVersion")==15:
        r.update(schemaVersion=16,deploymentSeconds=0.)
    if isinstance(r, dict) and r.get("schemaVersion")==16:
        if r.get("pattern")=="parallel" and r.get("deploymentSeconds")!=.15:
            note=(note or "")+"排射现统一先展开0.15秒再发射，请重新预览。"
        r.update(schemaVersion=17,deploymentSeconds=.15)
    if isinstance(r, dict) and r.get("schemaVersion")==17:
        r["schemaVersion"]=18
        if isinstance(r.get("angleOffset"),(int,float)) and 360<r["angleOffset"]<=365:
            r["angleOffset"]%=360
            note=(note or "")+"旧角度偏移已换算为0～360°内的等效角度。"
    return validate_recipe(r), note


def compile_single_recipe(recipe):
    """Expand one simultaneous volley; global speed and cadence apply to every item."""
    r = validate_single_recipe(recipe)
    plan = default_plan(r["character"], r["intervalSeconds"])
    plan["id"] = r["id"]
    origin = ORIGIN_PRESETS["presets"]["lobber"]["origin"] if r["pattern"]=="lob" else r["origin"]
    radius = 0. if r["pattern"]=="lob" else r["radius"]
    group = plan["groups"][0]
    group.update(id=r["id"] + "-volley", name="齐射", items=[])
    n = {"straight":1,"lob":1,"starfruit":5}.get(r["pattern"],r["count"])
    for i in range(n):
        angle = 0.
        if r["pattern"]=="starfruit":angle=[330.,270.,180.,90.,30.][i]
        elif r["pattern"]=="ring" or r["pattern"]=="fan" and r["spread"]==360:
            angle = 360. * i / n
            if angle > 180:
                angle -= 360
        elif r["pattern"] == "fan" and n > 1:
            angle = -r["spread"] / 2 + r["spread"] * i / (n - 1)
        angle = 0. if r["pattern"]=="lob" else (angle + r["direction"]) % 360
        if angle > 180: angle -= 360
        item = new_item()
        item.update(id=r["id"] + f"-shot-{i}", time=round(i*r["shotDelaySeconds"],8) if r["pattern"] not in ("straight","lob") else 0.)
        radians = math.radians(angle)
        item["launch"]["offset"] = [origin[0]+math.cos(radians)*radius, origin[1]+math.sin(radians)*radius]
        if r["originPreset"]=="center" and r["pattern"]=="starfruit":
            port=ORIGIN_PRESETS["presets"]["center"]["shotOffsets"][i]
            turn=math.radians(r["direction"])
            item["launch"]["offset"][0]+=port[0]*math.cos(turn)-port[1]*math.sin(turn)
            item["launch"]["offset"][1]+=port[0]*math.sin(turn)+port[1]*math.cos(turn)
        if r["pattern"]=="parallel":
            sideways=(i-(n-1)/2)*r["spacing"]
            item["launch"]["offset"][0]-=math.sin(radians)*sideways
            item["launch"]["offset"][1]+=math.cos(radians)*sideways
        if r["pattern"]=="parallel" and r["deploymentSeconds"]>0:
            item["launch"]["deployment"]=dict(duration=r["deploymentSeconds"],offset=[origin[0]+math.cos(radians)*radius,origin[1]+math.sin(radians)*radius])
        heading=(angle+r["angleOffset"])%360
        if heading>180:heading-=360
        item["trajectory"].update(speed=r["speed"], direction=heading)
        item["maxTravelCells"] = r["rangeCells"] or None
        # Homing is an explicit ammo choice; normal straight shots never steer.
        if r["ammo"]=="homing" and r["pattern"]!="lob":
            item["guidance"].update(initialAim=r["trackingStrength"]==0,trackingStrength=r["trackingStrength"],model="web-homing-v2")
            if r["trackingStrength"]==0:
                item["launch"]["aimFrame"]=dict(centerOffset=list(origin),localOffset=[item["launch"]["offset"][j]-origin[j] for j in (0,1)])
        if r["pattern"]=="lob":
            item["trajectory"].update(kind="parabola",speed=300.,direction=0.)
            item["guidance"].update(initialAim=True,trackingStrength=0.,endBinding="snapshot")
            item["maxTravelCells"]=None
            if r["speed"]!=300.:item["trajectory"]["catapultSpeedScale"]=r["speed"]/300.
        group["items"].append(item)
    validate_plan(plan)
    return plan


def validate_recipe(recipe):
    if isinstance(recipe,dict) and recipe.get("format")=="pvzhe.attack-composition":
        from attack_composition import validate
        return validate(recipe)
    return validate_single_recipe(recipe)


def compile_recipe(recipe):
    if isinstance(recipe,dict) and recipe.get("format")=="pvzhe.attack-composition":
        from attack_composition import compile_document
        return compile_document(recipe)
    return compile_single_recipe(recipe)


class Editor:
    def __init__(self, output, recipe_path=None, config=None, recover=False, view_only=False,
                 plan_path=None, project_root=None):
        self.output = Path(output).resolve()
        self.recipe_path = Path(recipe_path).resolve() if recipe_path else self.output.with_suffix(".recipe.json")
        self.draft = self.recipe_path.with_suffix(".draft.json")
        self.state_path = self.output.with_suffix(".state.json")
        self.view_only = view_only
        self.project_root = Path(project_root or Path.cwd()).resolve()
        legacy_draft = self.draft
        self.draft = self.project_root / ".work/attack-web/drafts" / (digest(str(self.recipe_path)) + ".json")
        self.plan_path = Path(plan_path).resolve() if plan_path else None
        self.source_recipe_sha = file_sha(self.recipe_path) if self.recipe_path.is_file() else None
        self.source_plan_sha = file_sha(self.plan_path) if self.plan_path and self.plan_path.is_file() else None
        if len({p for p in (self.output, self.recipe_path, self.draft, self.state_path, self.plan_path) if p}) != (5 if self.plan_path else 4):
            raise ValueError("会话输出、草稿、方案和编译文件不能使用同一路径")
        if self.output.exists() or self.state_path.exists():
            raise ValueError("请使用新的会话输出路径")
        self.config = config
        if config:
            sha = config.get("provenance", {}).get("release", {}).get("assemblies", {}).get("PlantsVsZombies.dll")
            if sha and sha != ORIGIN_PRESETS["dllSha256"]:
                raise ValueError("起点预设与发行程序集不匹配，需要重新核对预设")
        self.session_id = config["sessionId"] if config else uuid.uuid4().hex
        self.recipe = default_recipe(config["plant"]["key"] if config else "demo-plant")
        self.migration_note = None
        source = self.recipe_path
        if recover and not view_only:
            source = self.draft if self.draft.exists() else legacy_draft if legacy_draft.exists() else self.recipe_path
        if source.exists():
            self.recipe, self.migration_note = load_recipe(source)
        if config and self.recipe["character"] != config["plant"]["key"]:
            raise ValueError("方案与素材角色不匹配")
        if self.source_plan_sha:
            plan = load_plan(self.plan_path)
            expected = compile_recipe(load_recipe(self.recipe_path)[0]) if self.recipe_path.is_file() else compile_recipe(self.recipe)
            if not same_design(plan,expected):
                raise ValueError("现有编排不匹配简易方案；先调查差异，保留复杂方案原文件，由AI分析差量修改")
            if implementation_changes(plan, self.project_root):
                raise ValueError("实现文件已改变，先核对与已保存方案的差异")
        if view_only:
            # Do not restore a project's unpublished draft or write any project path in viewing mode.
            if self.recipe_path.exists():
                self.recipe, self.migration_note = load_recipe(self.recipe_path)
            self.draft = self.output.with_suffix(".view-draft.json")
        self.done = False
        self.lock = threading.Lock()
        self.token = secrets.token_urlsafe(24)
        self.transaction_id = uuid.uuid4().hex
        self.assets = {k: Path(v["path"]) for k, v in config["assets"].items()} if config else {}
        save(self.state_path, dict(status="waiting", sessionId=self.session_id, transactionId=self.transaction_id, viewOnly=view_only))

    def check_sources(self):
        current = file_sha(self.recipe_path) if self.recipe_path.is_file() else None
        if current != self.source_recipe_sha:
            raise ValueError("正式方案在本轮打开后已改变，请重新核对，不能覆盖")
        current_plan = file_sha(self.plan_path) if self.plan_path and self.plan_path.is_file() else None
        if current_plan != self.source_plan_sha:
            raise ValueError("编译方案在本轮打开后已改变，请重新核对")
        if self.source_plan_sha and implementation_changes(load_plan(self.plan_path), self.project_root):
            raise ValueError("实现文件在编辑期间已改变，请重新核对")

    def state(self):
        c = self.config
        return dict(recipe=self.recipe, defaultRecipe=default_recipe(self.recipe["character"]), done=self.done, demo=c is None, viewOnly=self.view_only, migrationNote=self.migration_note,
                    storageKey="pvzhe.attack-editor:" + digest([str(self.project_root), str(self.recipe_path), self.source_recipe_sha, self.source_plan_sha, ORIGIN_PRESETS["dllSha256"], self.view_only]),
                    originPresets=ORIGIN_PRESETS,
                    canvas=c["canvas"] if c else [1080, 600],
                    backgroundCrop=c.get("backgroundCrop", [0, 0, *c["canvas"]]) if c else None,
                    plant=c["plant"] if c else dict(position=[340, 321], imageOrigin=[60, 95], scale=1),
                    target=c["target"] if c else dict(position=[830, 321], imageOrigin=[60, 120], scale=1, hitBoxRect=[-20,-40,40,80]),
                    grid=c.get("grid") if c else dict(begin=[260, 75], size=[80, 98], rows=5),
                    assets={k: "asset/" + k for k in self.assets}, sessionId=self.session_id,
                    transactionId=self.transaction_id)

    def accept(self, action, recipe):
        if action not in ("save", "confirm", "cancel"):
            raise ValueError("未知操作")
        with self.lock:
            if self.done:
                raise ValueError("本轮已结束")
            if action != "cancel" and not self.view_only:
                self.check_sources()
            if action != "cancel":
                validate_recipe(recipe)
                if action == "confirm" and not self.view_only and recipe.get("format") == "pvzhe.attack-composition":
                    from attack_composition import layers
                    if not list(layers(recipe)):
                        raise ValueError("请先添加一个攻击图层再采用方案；空组可保存草稿")
                if recipe["id"] != self.recipe["id"] or recipe["character"] != self.recipe["character"]:
                    raise ValueError("方案身份不匹配")
                self.recipe = copy.deepcopy(recipe)
                save(self.draft, self.recipe)
            if action == "save":
                return dict(status="draft")
            status = ("viewed" if self.view_only else "confirmed") if action == "confirm" else "cancelled"
            record = dict(format="pvzhe.attack-recipe-result", schemaVersion=2, status=status,
                          sessionId=self.session_id, demo=self.config is None,
                          transactionId=self.transaction_id, viewOnly=self.view_only,
                          sourcePlanSha256=self.source_plan_sha,
                          recipe=copy.deepcopy(self.recipe), recipeSha256=digest(self.recipe),
                          originPresetCatalogSha256=digest(ORIGIN_PRESETS),
                          migrationNotes=[self.migration_note] if self.migration_note else [],
                          requiresRuntimeBinding=True)
            if action == "confirm" and not self.view_only:
                record["plan"] = compile_recipe(self.recipe)
                record["planSha256"] = digest(record["plan"])
                save(self.recipe_path, self.recipe)
            if self.config:
                record.update(configSha256=digest(self.config), provenance=self.config.get("provenance", {}),
                              assets=self.config["assets"], binding=self.config.get("binding", {}))
            save(self.output, record)
            self.done = True
            save(self.state_path, dict(status=status, sessionId=self.session_id, transactionId=self.transaction_id, viewOnly=self.view_only))
            return dict(status=status)


def make_server(editor, port=0):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def reply(self, status, data, content_type="application/json; charset=utf-8"):
            payload = data if isinstance(data, bytes) else json.dumps(data, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(payload)

        def route(self):
            if self.headers.get("Host") != f"127.0.0.1:{self.server.server_port}":
                return None
            prefix = "/" + editor.token + "/"
            return self.path[len(prefix):] if self.path.startswith(prefix) else None

        def do_GET(self):
            route = self.route()
            if route == "api/templates":
                try:
                    return self.reply(200, dict(templates=TemplateStore(editor.project_root, validate_recipe).catalog()))
                except (ValueError, OSError) as error:
                    return self.reply(400, dict(error=str(error)))
            if route == "api/state":
                return self.reply(200, editor.state())
            if route in ("", "index.html", "app.js", "style.css", "model.mjs", "composition.mjs"):
                name = route or "index.html"
                mime = "text/html" if name.endswith("html") else "text/css" if name.endswith("css") else "text/javascript"
                return self.reply(200, (STATIC / name).read_bytes(), mime + "; charset=utf-8")
            if route and route.startswith("asset/") and route[6:] in editor.assets:
                return self.reply(200, editor.assets[route[6:]].read_bytes(), "image/png")
            self.reply(404, dict(error="Not found"))

        def do_POST(self):
            origin = self.headers.get("Origin")
            if self.route() not in ("api/action", "api/template") or (origin and origin != f"http://127.0.0.1:{self.server.server_port}"):
                return self.reply(403, dict(error="拒绝非本轮请求"))
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= 1048576 or self.headers.get_content_type() != "application/json":
                    raise ValueError("请求格式无效")
                data = json.loads(self.rfile.read(size))
                if data.get("transactionId") != editor.transaction_id or data.get("sessionId") != editor.session_id:
                    raise ValueError("页面来自旧会话，请刷新当前页面后再操作")
                if self.route() == "api/template":
                    with editor.lock:
                        if editor.done:
                            raise ValueError("本轮已经结束")
                        store = TemplateStore(editor.project_root, validate_recipe)
                        if data["action"] == "load":
                            answer = store.read(data["name"])
                            if answer["reference"].get("presetDllSha256") != ORIGIN_PRESETS["dllSha256"]:
                                raise ValueError("模板的游戏基准不同，请交给AI核对兼容性")
                        elif data["action"] == "save":
                            if editor.view_only:
                                raise ValueError("仅查看会话不能写入项目模板")
                            editor.check_sources()
                            answer = store.write(data["name"], data["recipe"], dict(
                                presetDllSha256=ORIGIN_PRESETS["dllSha256"],
                                coordinateSpace="plant-root-logical-pixels", speedBaseline=300,
                                speedUnit="logical-pixels/second", timeUnit="seconds",
                                rangeUnit="grid-columns", semantics="docs/attack-template-format.md"),
                                data.get("expectedSha256"))
                        else:
                            raise ValueError("未知模板操作")
                else:
                    answer = editor.accept(data["action"], data.get("recipe"))
            except TemplateConflict as error:
                return self.reply(409, dict(error=str(error), path=error.path, sha256=error.sha))
            except (ValueError, KeyError, TypeError) as error:
                return self.reply(400, dict(error=str(error)))
            except OSError:
                return self.reply(500, dict(error="文件写入失败，本轮未完成，请检查服务日志和目录权限"))
            self.reply(200, answer)

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--customize", action="store_true")
    choice = p.add_mutually_exclusive_group(required=True)
    choice.add_argument("--session")
    choice.add_argument("--demo", action="store_true", help="Use illustrative shapes instead of game assets")
    p.add_argument("--output", required=True)
    p.add_argument("--recipe")
    p.add_argument("--recover", action="store_true")
    p.add_argument("--no-browser", action="store_true")
    p.add_argument("--view-only", action="store_true")
    p.add_argument("--plan", help="Linked schema5 plan; checked for design and implementation drift")
    p.add_argument("--root", default=str(Path.cwd()), help="Mod project root for implementation checks")
    p.add_argument("--reuse-url", help="Previous .server.json; retain its local port and URL during an intentional restart")
    args = p.parse_args()
    if not args.customize:
        p.error("仅在玩家明确要求自定义攻击方式时打开")
    config = load_session(args.session) if args.session else None
    if config:
        from attack_recipe import check_release
        check_release(config, Path(args.root))
    editor = Editor(args.output, args.recipe, config, args.recover, args.view_only, args.plan, args.root)
    port = 0
    if args.reuse_url:
        old = json.loads(Path(args.reuse_url).read_text(encoding="utf-8"))
        url = urlparse(old["url"])
        token = url.path.strip("/")
        if url.scheme != "http" or url.hostname != "127.0.0.1" or not url.port or url.query or url.fragment or len(token)<24 or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for c in token):
            p.error("只能复用本地编辑器地址")
        port = url.port
        editor.token = token
    server = make_server(editor, port)
    url = f"http://127.0.0.1:{server.server_port}/{editor.token}/"
    save(editor.output.with_suffix(".server.json"), dict(url=url, sessionId=editor.session_id,
         transactionId=editor.transaction_id, pid=os.getpid(), viewOnly=editor.view_only,
         configSha256=digest(config) if config else None, demo=config is None,
         recipePath=str(editor.recipe_path), planPath=str(editor.plan_path) if editor.plan_path else None))
    print(url, flush=True)
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
