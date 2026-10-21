"""Portable attack design, legacy import and engine-independent single-carrier preview."""
import ast
import copy
import json
import math
from pathlib import Path
import uuid

from attack_model import number, save, digest, file_sha, rotate

MAX_ITEMS = 6000
PREVIEW_LIMIT = 1000
PREVIEW_EVICT_BATCH = 50
FORMAT = "pvzhe.attack-plan"
COLORS = ["#eab74d", "#42a6bc", "#d67fab", "#93b45b", "#9879d0", "#d58340"]


def uid(): return uuid.uuid4().hex


def new_item(name="发射项"):
    return dict(id=uid(), name=name, enabled=True, time=0., carrier="projectile",
                launch=dict(anchor="plant-reference", gridOffset=[0, 0], offset=[27, -17]),
                trajectory=dict(kind="straight", speed=300., direction=0., catapultProfile="pvzhe-0.30-standard", parabolaMode="target-snapshot",
                                x="v*t", y="A*sin(2*pi*v*t/L)",
                                parameters=dict(A=dict(value=30., min=0., max=120., step=1.),
                                                L=dict(value=160., min=20., max=500., step=5.))),
                guidance=dict(initialAim=False, trackingStrength=0., endBinding="fixed", endpointFollowSpeed=None),
                maxTravelCells=None, rayLength=500., rayDuration=.3,
                route=dict(rowOffset=0, duration=.25))


def default_plan(character="PlantPeaShooterSingle", interval=1.5):
    return dict(format=FORMAT, schemaVersion=5, id=uid(), name="攻击方案", character=character,
                intervalSeconds=interval,
                trigger=dict(kind="rect", coordinates="cell-boundaries", columns=[0., 9.], rows=[0., 1.], selection="inherited-target"),
                groups=[dict(id=uid(), name="攻击组 1", enabled=True, items=[new_item()])],
                implementation=dict(files={}, appliedPlanSha256=None), reference={})


def all_items(plan):
    return [(g, item) for g in plan["groups"] for item in g["items"]]


FUNCTIONS = {name: getattr(math, name) for name in ("sin", "cos", "tan", "sqrt", "exp", "log", "atan2")}
FUNCTIONS.update(abs=abs, min=min, max=max)


class Expression:
    """Small expression interpreter. No Python eval, attributes, indexing or statements."""
    def __init__(self, source, names):
        if not isinstance(source, str) or len(source)>500: raise ValueError("公式过长")
        try: self.tree=ast.parse(source, mode="eval").body
        except (SyntaxError, RecursionError) as e: raise ValueError("公式语法无效") from e
        if len(list(ast.walk(self.tree)))>120: raise ValueError("公式过于复杂")
        self.names=set(names)|{"t", "v", "pi"}
        self.check(self.tree, 0)

    def check(self, node, depth):
        if depth>24: raise ValueError("公式嵌套过深")
        if isinstance(node, ast.Constant) and type(node.value) in (int,float):
            number(node.value,-1e9,1e9,"公式常数"); return
        if isinstance(node, ast.Name) and node.id in self.names: return
        if isinstance(node, ast.UnaryOp) and isinstance(node.op,(ast.UAdd,ast.USub)):
            self.check(node.operand,depth+1); return
        if isinstance(node, ast.BinOp) and isinstance(node.op,(ast.Add,ast.Sub,ast.Mult,ast.Div,ast.Pow,ast.Mod)):
            self.check(node.left,depth+1); self.check(node.right,depth+1); return
        if (isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id in FUNCTIONS
                and not node.keywords and 1<=len(node.args)<=3):
            for arg in node.args: self.check(arg,depth+1)
            return
        raise ValueError("公式只允许白名单数学函数、参数和算术运算")

    def __call__(self, values):
        def run(n):
            if isinstance(n,ast.Constant): out=n.value
            elif isinstance(n,ast.Name): out=values[n.id] if n.id!="pi" else math.pi
            elif isinstance(n,ast.UnaryOp): out=run(n.operand)*(-1 if isinstance(n.op,ast.USub) else 1)
            elif isinstance(n,ast.Call): out=FUNCTIONS[n.func.id](*(run(a) for a in n.args))
            else:
                a,b=run(n.left),run(n.right)
                if isinstance(n.op,ast.Pow):
                    if abs(b)>12 or (a<0 and b!=int(b)): raise ValueError("幂运算超出范围")
                    out=a**b
                elif isinstance(n.op,ast.Add): out=a+b
                elif isinstance(n.op,ast.Sub): out=a-b
                elif isinstance(n.op,ast.Mult): out=a*b
                elif isinstance(n.op,ast.Div): out=a/b
                else: out=a%b
            if not isinstance(out,(int,float)) or not math.isfinite(out) or abs(out)>1e9:
                raise ValueError("公式产生非有限值或超出数值范围")
            return out
        try: return run(self.tree)
        except (ArithmeticError,KeyError,TypeError,ValueError) as e: raise ValueError("公式计算失败："+str(e)) from e


def point(value, label, limit=4096):
    if not isinstance(value,list) or len(value)!=2: raise ValueError(label+"需要两个坐标")
    for v in value: number(v,-limit,limit,label)


def validate_plan(plan):
    if plan.get("format")!=FORMAT or plan.get("schemaVersion")!=5: raise ValueError("不支持的攻击方案格式")
    number(plan["intervalSeconds"],.1,60,"攻击间隔")
    if not isinstance(plan["character"],str) or not plan["character"]: raise ValueError("缺少角色关联")
    trigger=plan["trigger"]
    if trigger["kind"]!="rect" or trigger.get("coordinates")!="cell-boundaries" or trigger["selection"]!="inherited-target": raise ValueError("触发区域必须是矩形边界")
    for key in ("columns","rows"):
        point(trigger[key],key,100)
        quantum=.5 if key=="columns" else 1.
        if trigger[key][1]-trigger[key][0]<quantum or any(abs(v/quantum-round(v/quantum))>1e-8 for v in trigger[key]):
            raise ValueError("触发区域至少0.5列、1行，按半列/整行吸附")
    if "domain" in plan: raise ValueError("命中有效域已移除")
    ids=set()
    def identity(obj):
        if not isinstance(obj["id"],str) or not obj["id"] or obj["id"] in ids: raise ValueError("空或重复的稳定ID")
        ids.add(obj["id"])
        if not isinstance(obj["name"],str) or not obj["name"].strip() or len(obj["name"])>64: raise ValueError("名称需为1～64字符")
        if type(obj["enabled"]) is not bool: raise ValueError("启用状态无效")
    if not isinstance(plan["id"],str) or not plan["id"]: raise ValueError("缺少方案ID")
    if not isinstance(plan["name"],str) or not plan["name"].strip() or len(plan["name"])>64: raise ValueError("方案名称无效")
    groups=plan["groups"]
    if not 1<=len(groups)<=128: raise ValueError("需要1～128个攻击组")
    total=0
    for g in groups:
        identity(g)
        if "startDelaySeconds" in g:number(g["startDelaySeconds"],0,30,"组发射延迟")
        if "intervalSeconds" in g:number(g["intervalSeconds"],.01,60000,"组攻击间隔")
        if not g["items"]: raise ValueError("攻击组至少保留一个发射项，可禁用")
        for item in g["items"]:
            identity(item); total+=1
            if any(k in item for k in ("count","shotGap","arrangement")): raise ValueError("单个发射项不能包含批量生成字段")
            number(item["time"],0,600,"发射时刻")
            if item["carrier"] not in ("projectile","ray"): raise ValueError("未知攻击载体")
            launch=item["launch"]
            if launch["anchor"]!="plant-reference": raise ValueError("预览只支持已标定的植物参考点")
            point(launch["gridOffset"],"网格偏移",100); point(launch["offset"],"局部偏移")
            if any(v!=int(v) for v in launch["gridOffset"]): raise ValueError("网格偏移必须为整数")
            deployment=launch.get("deployment")
            if deployment is not None:
                if not isinstance(deployment,dict) or set(deployment)!={"duration","offset"}:raise ValueError("展开配置无效")
                number(deployment["duration"],.001,1,"展开时长")
                point(deployment["offset"],"展开起点")
                if item["carrier"]!="projectile" or item["trajectory"]["kind"]!="straight":raise ValueError("展开仅支持直线弹药")
            t=item["trajectory"]; guide=item["guidance"]
            if any(k in t for k in ("count","shotGap","spread")): raise ValueError("轨迹不包含弹数或扇形参数")
            if t["kind"] not in ("straight","parabola","function"): raise ValueError("未知轨迹模型，贝塞尔已移除")
            if "domain" in item or any(k in t for k in ("controls","end")): raise ValueError("旧命中域/贝塞尔配置已移除，请先迁移")
            if t["kind"]=="parabola" and t.get("parabolaMode","target-snapshot")!="target-snapshot": raise ValueError("抛物线必须在发射时锁定目标位置")
            if any(k in t for k in ("gravity","flightTime")): raise ValueError("原版抛射自动解算，不保存手动重力/飞行时间")
            if t.get("catapultProfile")!="pvzhe-0.30-standard": raise ValueError("未知发行抛射配置，请核验发行映射")
            for key,lo,hi in (("speed",1,5000),("direction",-180,180)):
                number(t[key],lo,hi,key)
            if "catapultSpeedScale" in t:number(t["catapultSpeedScale"],1/300,5000/300,"投掷射速倍率")
            if type(guide["initialAim"]) is not bool: raise ValueError("初始瞄准无效")
            number(guide["trackingStrength"],0,2,"追踪强度")
            if any(k in guide for k in ("maxTurnRate","response","angleFalloff")): raise ValueError("底层制导参数已归并为追踪强度")
            if guide["endBinding"] not in ("fixed","snapshot","live"): raise ValueError("未知终点绑定")
            if guide["endpointFollowSpeed"] is not None: number(guide["endpointFollowSpeed"],1,10000,"端点跟随速度")
            if item["carrier"]=="projectile" and t["kind"] in ("function","parabola") and guide["trackingStrength"]:
                raise ValueError("函数/抛物线暂不组合飞行中转向制导")
            if "lifetime" in item: raise ValueError("弹药以运动距离控制，不使用存活秒数")
            if item["maxTravelCells"] is not None: number(item["maxTravelCells"],0,1000,"最大运动距离（格）")
            if item["carrier"]=="projectile" and t["kind"]=="parabola" and item["maxTravelCells"] is not None: raise ValueError("自动瞄准抛物线不设射程限制")
            number(item["rayLength"],1,10000,"射线长度"); number(item["rayDuration"],0,30,"射线持续时间")
            number(item["route"]["rowOffset"],-100,100,"相对目标行")
            if int(item["route"]["rowOffset"])!=item["route"]["rowOffset"]: raise ValueError("行偏移必须为整数")
            number(item["route"]["duration"],.05,3,"行过渡时间")
            if t["kind"]=="function":
                if len(t["parameters"])>12: raise ValueError("最多12个函数参数")
                for key,param in t["parameters"].items():
                    if not key.isidentifier() or key in {"t","v","pi",*FUNCTIONS}: raise ValueError("函数参数名称无效")
                    number(param["min"],-10000,10000,"参数最小值"); number(param["max"],param["min"],10000,"参数最大值")
                    number(param["value"],param["min"],param["max"],key); number(param["step"],.0001,10000,"参数步长")
                x,y=Expression(t["x"],t["parameters"]),Expression(t["y"],t["parameters"])
                values={k:p["value"] for k,p in t["parameters"].items()}; values["v"]=t["speed"]
                for sample in range(17):
                    values["t"]=sample*30/16; x(values); y(values)
                values["t"]=0
                if abs(x(values))>1e-6 or abs(y(values))>1e-6: raise ValueError("局部函数必须从(0,0)出发")
    if total>MAX_ITEMS: raise ValueError("一轮最多6000个发射项")
    return total


def launch_position(item, plant, grid, target=None):
    if grid is None and any(item["launch"]["gridOffset"]): raise ValueError("网格偏移需要发行网格")
    frame=item["launch"].get("aimFrame")
    if frame and target is not None:
        center=[plant[i]+frame["centerOffset"][i] for i in (0,1)]
        local=rotate(frame["localOffset"],math.atan2(target[1]-center[1],target[0]-center[0]))
        return [center[i]+local[i] for i in (0,1)]
    return [plant[i]+item["launch"]["offset"][i]+item["launch"]["gridOffset"][i]*(grid["size"][i] if grid else 0) for i in (0,1)]


def place_launch(item, position, plant, grid):
    """Store exact logical-pixel displacement. Grid offsets are legacy read support only."""
    item["launch"]["gridOffset"]=[0,0]
    item["launch"]["offset"]=[position[i]-plant[i] for i in (0,1)]



def region_bounds(region,plant,grid):
    cell=[math.floor((plant[i]-grid["begin"][i])/grid["size"][i]) for i in (0,1)]
    return [[grid["begin"][i]+(cell[i]+region[k][end]+(0 if region.get("coordinates")=="cell-boundaries" else end))*grid["size"][i] for i,k in enumerate(("columns","rows"))] for end in (0,1)]


def can_trigger(plan,plant,target,grid):
    if target is None: return False
    if grid is None: raise ValueError("触发区域需要发行网格")
    a,b=region_bounds(plan["trigger"],plant,grid)
    return all(a[i]<=target[i]<b[i] for i in (0,1))


def migrate(config):
    """Legacy batches expand exactly once; never truncate an imported design."""
    if "plan" in config:
        return upgrade_plan(config["plan"])
    from attack_combo import default_combo, lanes, round_interval, validate_combo
    combo=config.get("combo") or default_combo(config["attack"])
    grid=config.get("grid"); plant=config["plant"]["position"]
    validate_combo(combo,grid,plant)
    plan=default_plan(config["plant"].get("key","preview-character"),round_interval(combo,config.get("baseline")) or 1.5)
    plan["reference"]={"releaseCacheKey":config.get("provenance",{}).get("releaseCacheKey")}
    import random
    groups=[]
    for old in combo["steps"]:
        a=old["attack"]; g=dict(id=old["id"],name=old["name"],enabled=old["enabled"],items=[])
        if a["kind"]=="parabola":
            note="旧抛物线改用原版标准投手及目标快照，手动角度/速度/重力/飞行时间不再控制轨迹，请重新预览"
            if note not in plan.setdefault("migrationNotes",[]): plan["migrationNotes"].append(note)
        for lane in lanes(old,grid,plant):
            rng=random.Random(42)
            for n in range(a["count"]):
                item=new_item(old["name"][:48]+" "+str(len(g["items"])+1))
                item["id"]=uuid.uuid5(uuid.NAMESPACE_URL,f"{old['id']}:{len(g['items'])}").hex
                item["time"]=old["start"]+lane["delay"]+n*a["shotGap"]
                offset=list(a["origin"])
                if a.get("birthOffsets"):
                    p=a["birthOffsets"][n%len(a["birthOffsets"])]; offset=[offset[i]+p[i] for i in (0,1)]
                offset[1]+=rng.uniform(-a["birthY"],a["birthY"])
                if lane["row"] is None: offset[1]+=lane["y"]
                else: item["route"].update(rowOffset=lane["offsetLine"],duration=old["arrangement"]["routeDuration"])
                item["launch"]["offset"]=offset
                angle=a["direction"]+(a["spread"]*(n/(a["count"]-1)-.5) if a["kind"]=="fan" and a["count"]>1 else 0)
                item["trajectory"].update(kind="straight" if a["kind"]=="fan" else a["kind"],speed=a["speed"],
                    direction=(angle+180)%360-180)
                item["guidance"].update(initialAim=a["targeting"]!="fixed",
                    trackingStrength=2. if a["targeting"]=="track" else min(1.,a["turnRate"]/120) if a["targeting"]=="track-limited" else 0.)
                if a["kind"]=="bezier":
                    item["trajectory"]["kind"]="straight"; item["enabled"]=False; item["guidance"]["trackingStrength"]=0.
                    note="贝塞尔已移除，原发射项已停用；请选择其他轨迹后再启用"
                    if note not in plan.setdefault("migrationNotes",[]): plan["migrationNotes"].append(note)
                g["items"].append(item)
        groups.append(g)
    plan["groups"]=groups; validate_plan(plan); return plan


def preset(name, base=None, count=5, spread=45, gap=.5):
    """A group factory, never a projectile trajectory with hidden multiplicity."""
    if name=="相对五行": count=5
    number(count,1,120,"数量")
    if int(count)!=count: raise ValueError("预设数量需为整数")
    group=dict(id=uid(),name=name,enabled=True,items=[])
    for n in range(count):
        item=copy.deepcopy(base or new_item()); item.update(id=uid(),name="发射项 "+str(n+1),time=0.)
        if name=="扇形":
            item["trajectory"].update(kind="straight",direction=(item["trajectory"]["direction"]+(spread*(n/(count-1)-.5) if count>1 else 0)+180)%360-180)
        elif name=="连射": item["time"]=n*gap
        elif name=="奇偶交错":
            item["launch"]["offset"][1]+=(n-(count-1)/2)*16
            item["time"]=gap if (n+1)%2 else 0.
        elif name=="相对五行":
            item["trajectory"]["kind"]="straight"; item["route"]["rowOffset"]=n-count//2; item["time"]=gap if (n+1)%2 else 0.
        else: raise ValueError("未知编排预设")
        group["items"].append(item)
    return group


def function_preset(name):
    """Friendly parameters over a common local x(t), y(t) representation."""
    if name=="正弦波":
        return dict(x="v*t",y="A*sin(2*pi*v*t/L)",parameters=dict(
            A=dict(value=30.,min=0.,max=120.,step=1.),L=dict(value=160.,min=20.,max=500.,step=5.)))
    if name=="回旋线":
        return dict(x="R*sin(w*t)",y="R*(1-cos(w*t))",parameters=dict(
            R=dict(value=100.,min=10.,max=300.,step=5.),w=dict(value=3.,min=.1,max=10.,step=.1)))
    if name=="函数抛物线":
        return dict(x="v*t",y="vy*t+g*t*t/2",parameters=dict(
            vy=dict(value=-150.,min=-500.,max=300.,step=5.),g=dict(value=240.,min=0.,max=900.,step=10.)))
    raise ValueError("未知函数预设")


def load_plan(path):
    return upgrade_plan(json.loads(Path(path).read_text(encoding="utf-8-sig")))


def upgrade_plan(source):
    plan=copy.deepcopy(source)
    if plan.get("format")==FORMAT and plan.get("schemaVersion")==1:
        trigger=plan["trigger"]
        if trigger["kind"]=="any": trigger.update(kind="rect",columns=[0.,9.],rows=[0.,1.])
        else:
            # Old integer cell indices were inclusive; preserve their actual footprint.
            for key in ("columns","rows"): trigger[key]=[trigger[key][0],trigger[key][1]+1]
        trigger["coordinates"]="cell-boundaries"
        for group,item in all_items(plan):
            item["guidance"].setdefault("response",6.)
            item["guidance"].setdefault("angleFalloff",2.)
        plan["schemaVersion"]=2
    if plan.get("format")==FORMAT and plan.get("schemaVersion")==2:
        notes=plan.setdefault("migrationNotes",[])
        region=plan["trigger"]; old_rows=region["rows"][:]
        region["rows"]=[math.floor(old_rows[0]),math.ceil(old_rows[1])]
        if region["rows"]!=old_rows: notes.append("旧半行边界已向外吸附到整行，请重新确认触发区域")
        removed=False
        for group,item in all_items(plan):
            removed=("lifetime" in item) or removed
            item.pop("lifetime",None); item.setdefault("maxTravelCells",None)
            for domain in (item.get("domain"),):
                if domain is not None and domain.pop("maxTravel",None) is not None: removed=True
        if plan.get("domain",{}).pop("maxTravel",None) is not None: removed=True
        if removed: notes.append("旧存活秒数/逻辑距离未推算成格数；最大运动距离暂不限制，请重新确认射程")
        plan["schemaVersion"]=3
    if plan.get("format")==FORMAT and plan.get("schemaVersion")==3:
        for group,item in all_items(plan):
            t=item["trajectory"]
            if "parabolaMode" not in t:
                t["parabolaMode"]="target-snapshot"
                if item["carrier"]=="projectile" and t["kind"]=="parabola":
                    plan.setdefault("migrationNotes",[]).append("抛物线改为发射时目标快照解算，旧手动角度/速度不再控制轨迹，请重新预览")
        notes=plan.setdefault("migrationNotes",[])
        domains=[plan.pop("domain",None)]
        for group,item in all_items(plan):
            domains.append(item.pop("domain",None))
            t=item["trajectory"]; g=item["guidance"]
            if t["kind"]=="bezier":
                t["kind"]="straight"; item["enabled"]=False
                note="贝塞尔已移除，原发射项已停用；请选择其他轨迹后再启用"
                if note not in notes: notes.append(note)
            t.pop("controls",None); t.pop("end",None)
            maximum=g.pop("maxTurnRate",0); g.pop("response",None); g.pop("angleFalloff",None)
            g.setdefault("trackingStrength",min(1.,maximum/120) if maximum<=120 else min(2.,1+(maximum-120)/1320))
            if maximum:
                note="底层制导参数已合并为追踪强度，请重新预览"
                if note not in notes: notes.append(note)
            if t["kind"] in ("parabola","function"): g["trackingStrength"]=0.
            if t["kind"]=="parabola" and item["carrier"]=="projectile":
                if item["maxTravelCells"] is not None:
                    note="抛物线已移除射程限制，发射后飞往目标快照位置"
                    if note not in notes: notes.append(note)
                item["maxTravelCells"]=None
        if any(d and d.get("kind")!="unbounded" for d in domains): notes.append("命中有效域已从所有轨迹移除")
        plan["schemaVersion"]=4
    if plan.get("format")==FORMAT and plan.get("schemaVersion")==4:
        changed=False
        for _,item in all_items(plan):
            t=item["trajectory"]
            changed|=item["carrier"]=="projectile" and t["kind"]=="parabola"
            t.pop("gravity",None); t.pop("flightTime",None)
            t["catapultProfile"]="pvzhe-0.30-standard"
        if changed:
            plan.setdefault("migrationNotes",[]).append("抛物线改用原版标准投手抛射，手动重力/飞行时间已移除；保留炮口与编排，请重新预览确认")
        plan["schemaVersion"]=5
    validate_plan(plan); return plan


def steer_angle(angle,wanted,guide,dt):
    strength=guide["trackingStrength"]
    if strength==0: return angle
    if guide.get("model") in ("web-homing-v1","web-homing-v2") and strength>=2:return wanted
    if strength<=1: maximum,response,falloff=120*strength,3*strength,2.
    else:
        f=strength-1; maximum,response,falloff=120+1320*f,3+21*f,2-1.5*f
    error=(wanted-angle+math.pi)%(2*math.pi)-math.pi
    alignment=.05+.95*max(0.,math.cos(abs(error)/2))**falloff
    correction=error*(-math.expm1(-response*alignment*dt))
    cap=math.radians(maximum)*dt
    return angle+max(-cap,min(cap,correction))


def store_plan(path,plan):
    validate_plan(plan); save(path,plan)


def implementation_changes(plan,root):
    changed=[]; root=Path(root).resolve()
    for relative,sha in plan["implementation"]["files"].items():
        path=(root/relative).resolve()
        if not path.is_relative_to(root): raise ValueError("实现关联路径必须在项目内")
        if not path.is_file() or file_sha(path)!=sha: changed.append(relative)
    return changed


def design_digest(plan):
    design={k:v for k,v in plan.items() if k not in ("implementation","reference")}
    return digest(design)


def same_design(left,right):
    """Compare optional zero phase without weakening stored file/digest checks."""
    def normalized(plan):
        output=copy.deepcopy(plan)
        for group in output['groups']:
            if group.get('startDelaySeconds')==0:group.pop('startDelaySeconds',None)
        return design_digest(output)
    return normalized(left)==normalized(right)


def bind_implementation(plan,paths,root):
    """Called by the developer after applying/verifying, never by preview confirmation."""
    output=copy.deepcopy(plan); root=Path(root).resolve(); files={}
    for relative in paths:
        path=(root/relative).resolve()
        if not path.is_relative_to(root): raise ValueError("实现关联路径必须在项目内")
        files[path.relative_to(root).as_posix()]=file_sha(path)
    output["implementation"]=dict(files=files,appliedPlanSha256=design_digest(plan))
    return output


def approach(point,target,speed,dt):
    if speed is None: return list(target)
    distance=math.dist(point,target)
    f=min(1.,speed*dt/distance) if distance else 1.
    return [point[i]+(target[i]-point[i])*f for i in (0,1)]


def host_catapult_reference(origin, plant, speed_scale=1.):
    """0.30 standard catapult shape; static IL g=2000, launch ground Y=plant.Y+20.

    Returns a continuous visual approximation, not the host's discrete collision path.
    Fixed standard profile: catapultHeight=300. Height is rise above launch; horizontal velocity is solved from the target snapshot.
    """
    gravity,height=2000.,300.
    launch_height=max(0.,plant[1]+20.-origin[1])
    duration=math.sqrt(2*height/gravity)+math.sqrt(2*(height+launch_height)/gravity)
    return dict(gravity=gravity*speed_scale**2,flightTime=duration/speed_scale,height=height,launchHeight=launch_height)


def ballistic_velocity(origin,target,flight_time,gravity):
    """Unique velocity reaching a position snapshot in a chosen flight time (Y down)."""
    return [(target[0]-origin[0])/flight_time,(target[1]-origin[1])/flight_time-.5*gravity*flight_time]


class PlanSimulation:
    """Preview one target point; canHit is eligibility, never a collision/damage claim."""
    def __init__(self,plan,plant,target,grid=None,repeat=True,only=None,canvas=None):
        validate_plan(plan)
        self.plan=copy.deepcopy(plan); self.plant=list(plant); self.grid=grid
        self.time=0.; self.next_round=0.; self.rounds_started=0; self.emitted=0
        self.discarded=0
        self.group_next={g["id"]:g.get("startDelaySeconds",0.) for g in plan["groups"]} if any("intervalSeconds" in g or "startDelaySeconds" in g for g in plan["groups"]) else None
        self.events=[]; self.bullets=[]; self.repeat=repeat; self.only=only
        self.canvas=canvas

    def start_round(self,at,target,group_id=None):
        if not can_trigger(self.plan,self.plant,target,self.grid): return
        colors={g["id"]:COLORS[n%len(COLORS)] for n,g in enumerate(self.plan["groups"])}
        for group,item in all_items(self.plan):
            if (group_id is None or group["id"]==group_id) and group["enabled"] and item["enabled"] and (self.only is None or item["id"] in self.only):
                self.events.append((at+item["time"],item,colors[group["id"]]))
        self.rounds_started+=1

    def spawn(self,item,color,target):
        t=item["trajectory"]; g=item["guidance"]; origin=launch_position(item,self.plant,self.grid,target)
        angle=math.radians(t["direction"])
        if g["initialAim"]:
            frame=item["launch"].get("aimFrame")
            reference=[self.plant[i]+frame["centerOffset"][i] for i in (0,1)] if frame else origin
            angle+=math.atan2(target[1]-reference[1],target[0]-reference[0])
        velocity=[math.cos(angle)*t["speed"],math.sin(angle)*t["speed"]]
        ballistics=None
        if item["carrier"]=="projectile" and t["kind"]=="parabola":
            ballistics=host_catapult_reference(origin,self.plant,t.get("catapultSpeedScale",1.))
            velocity=ballistic_velocity(origin,target,ballistics["flightTime"],ballistics["gravity"])
            angle=math.atan2(velocity[1],velocity[0])
        b=dict(item=item,itemId=item["id"],color=color,origin=origin,position=list(origin),age=0.,velocity=velocity,
               creationIndex=self.emitted,ballistics=ballistics,
               travelCells=0.,rangeReached=False,
               angle=angle,travel=0.,endpoint=list(target),
               carrier=item["carrier"],canHit=True,rayEnd=None)
        if item["carrier"]=="projectile" and t["kind"]=="parabola": b["targetSnapshot"]=list(target)
        if t["kind"]=="function": b["expressions"]=[Expression(t[k],t["parameters"]) for k in ("x","y")]
        deployment=item["launch"].get("deployment")
        if deployment:
            start=[self.plant[i]+deployment["offset"][i] for i in (0,1)]
            frame=item["launch"].get("aimFrame")
            if frame:
                center=[self.plant[i]+frame["centerOffset"][i] for i in (0,1)]
                turn=math.atan2(target[1]-center[1],target[0]-center[0])
                local=rotate([start[i]-center[i] for i in (0,1)],turn)
                start=[center[i]+local[i] for i in (0,1)]
            b["deployment"]=dict(start=start,end=list(origin),elapsed=0.,duration=deployment["duration"])
            b["position"]=start[:];b["canHit"]=False
        self.bullets.append(b); self.emitted+=1
        self.trim_preview()
        if item["carrier"]=="ray": self.advance(b,0,target)

    def trim_preview(self):
        # Append/filter preserve creation order; evict whole batches, never sample survivors.
        while len(self.bullets)>PREVIEW_LIMIT:
            del self.bullets[:PREVIEW_EVICT_BATCH]
            self.discarded+=PREVIEW_EVICT_BATCH

    def advance(self,b,dt,target):
        if b.get("deployment"):
            d=b["deployment"];used=min(dt,d["duration"]-d["elapsed"]);d["elapsed"]+=used
            k=min(1.,d["elapsed"]/d["duration"])
            b["position"]=[d["start"][i]+(d["end"][i]-d["start"][i])*k for i in (0,1)]
            b["canHit"]=False
            if k<1.-1e-9:return
            b["deployment"]=None;b["canHit"]=True;dt-=used
            if dt<1e-9:return
        if b["item"]["carrier"]=="projectile" and b["item"]["maxTravelCells"] is not None and b["item"]["trajectory"]["kind"]!="straight" and dt>1/120:
            steps=math.ceil(dt*120)
            for _ in range(steps):
                self.advance(b,dt/steps,target)
                if b["rangeReached"]: break
            return
        item=b["item"]; t=item["trajectory"]; g=item["guidance"]
        if b["rangeReached"]: return
        limit=max(.08,item["rayDuration"]) if item["carrier"]=="ray" else b["ballistics"]["flightTime"] if t["kind"]=="parabola" else math.inf
        dt=min(dt,max(0,limit-b["age"]))
        old=b["position"][:]; old_age=b["age"]; b["age"]+=dt
        if item["carrier"]=="ray":
            if g["endBinding"]=="live":
                b["endpoint"]=approach(b["endpoint"],target,g["endpointFollowSpeed"],dt)
                b["rayEnd"]=b["endpoint"][:]
            elif g["endBinding"]=="snapshot": b["rayEnd"]=b["endpoint"][:]
            else: b["rayEnd"]=[b["origin"][i]+rotate([item["rayLength"],0],b["angle"])[i] for i in (0,1)]
        elif t["kind"]=="function":
            values={k:p["value"] for k,p in t["parameters"].items()}; values.update(t=b["age"],v=t["speed"])
            local=[expr(values) for expr in b["expressions"]]
            b["position"]=[b["origin"][i]+rotate(local,b["angle"])[i] for i in (0,1)]
        else:
            angle=math.atan2(b["velocity"][1],b["velocity"][0])
            if g["trackingStrength"] and g.get("model")!="web-homing-v2":
                wanted=math.atan2(target[1]-old[1],target[0]-old[0]); angle=steer_angle(angle,wanted,g,dt)
                b["velocity"]=[math.cos(angle)*t["speed"],math.sin(angle)*t["speed"]]
            gravity=b["ballistics"]["gravity"] if t["kind"]=="parabola" else 0
            vx,vy=b["velocity"]; b["position"]=[old[0]+vx*dt,old[1]+vy*dt+.5*gravity*dt*dt]; b["velocity"][1]+=gravity*dt
            if g.get("model")=="web-homing-v2" and g["trackingStrength"]:
                wanted=math.atan2(target[1]-b["position"][1],target[0]-b["position"][0])
                next_angle=steer_angle(angle,wanted,g,dt)
                b["velocity"]=[math.cos(next_angle)*t["speed"],math.sin(next_angle)*t["speed"]]
        if item["carrier"]!="ray":
            route=item["route"] if t["kind"]!="parabola" else dict(rowOffset=0,duration=.25)
            height=self.grid["size"][1] if self.grid else 0
            offset=route["rowOffset"]*height*(min(1.,b["age"]/route["duration"])-min(1.,old_age/route["duration"]))
            if t["kind"]=="function":
                offset=route["rowOffset"]*height*min(1.,b["age"]/route["duration"])
            b["position"][1]+=offset
            delta=[b["position"][i]-old[i] for i in (0,1)]
            if self.grid is None and item["maxTravelCells"] is not None: raise ValueError("格数射程需要发行网格")
            segment=math.hypot(*(delta[i]/self.grid["size"][i] for i in (0,1))) if self.grid else 0.
            maximum=item["maxTravelCells"] if t["kind"]!="parabola" else None
            if maximum is not None and b["travelCells"]+segment>=maximum-1e-9:
                fraction=max(0.,min(1.,(maximum-b["travelCells"])/segment)) if segment else 0.
                b["position"]=[old[i]+delta[i]*fraction for i in (0,1)]; segment=maximum-b["travelCells"]
                b["rangeReached"]=True
            b["travelCells"]+=segment; b["travel"]+=math.dist(old,b["position"])
        b["canHit"]=not b["rangeReached"]

    def step(self,dt,target):
        number(dt,0,60,"预览步长")
        end=self.time+dt
        # Trigger is checked at each eligible start, not once at the end of a long step.
        if self.group_next is not None:
            for group in self.plan["groups"]:
                while self.group_next[group["id"]]<=end+1e-9:
                    self.start_round(self.group_next[group["id"]],target,group["id"])
                    self.group_next[group["id"]]+=group.get("intervalSeconds",self.plan["intervalSeconds"]) if self.repeat else math.inf
                    if len(self.events)+len(self.bullets)>20000:raise ValueError("同时待发/在途项超过20000，预览已暂停")
            self.next_round=math.inf
        while self.next_round<=end+1e-9:
            self.start_round(self.next_round,target)
            if len(self.events)+len(self.bullets)>20000: raise ValueError("同时待发/在途项超过20000，预览已暂停")
            if not self.repeat: self.next_round=math.inf; break
            self.next_round+=self.plan["intervalSeconds"]
        events=sorted((e for e in self.events if e[0]<=end+1e-9),key=lambda e:e[0])
        self.events=[e for e in self.events if e[0]>end+1e-9]
        cursor=self.time
        for at,item,color in events:
            elapsed=max(0,at-cursor)
            if elapsed:
                for b in self.bullets: self.advance(b,elapsed,target)
            cursor=max(cursor,at); self.spawn(item,color,target)
        elapsed=max(0,end-cursor)
        if elapsed:
            for b in self.bullets: self.advance(b,elapsed,target)
        self.bullets=[b for b in self.bullets if not b["rangeReached"] and
                      (b["age"]<max(.08,b["item"]["rayDuration"]) if b["carrier"]=="ray" else
                       b["age"]<b["ballistics"]["flightTime"]-1e-9 if b["item"]["trajectory"]["kind"]=="parabola" else True) and
                      (b["carrier"]=="ray" or b["item"]["trajectory"]["kind"]=="parabola" or self.canvas is None or all(-256<=b["position"][i]<=self.canvas[i]+256 for i in (0,1)))]
        self.time=end
