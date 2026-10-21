"""Shared session/hash helpers and legacy v1 preview for old-session migration.

The current editor simulates schema5 plans in attack_plan.PlanSimulation. Legacy
Bezier/batch routines below are compatibility inputs, not current UI capabilities.
"""
import copy
import hashlib
import json
import math
import random
from pathlib import Path


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


def default_attack():
    return dict(kind="straight", targeting="fixed", origin=[27, -17], count=7,
                shotGap=.06, speed=300, direction=0, spread=35, birthY=0,
                gravity=240, flightTime=1.6, turnRate=100,
                controls=[[170, -140], [350, -140]], curveEnd=[500,0])


def grid_row_y(grid, row, plant=False):
    number(row, 1, grid["rows"], "row")
    if int(row) != row: raise ValueError("Initial row must be an integer")
    return grid["begin"][1]+(row-1)*grid["size"][1]+(grid["plantOffset"] if plant else grid["size"][1]/2)


def number(value, low, high, name):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f"Invalid {name}: expected {low}..{high}")


def validate_attack(a):
    if a["kind"] not in ("straight", "fan", "parabola", "bezier"):
        raise ValueError("Unknown trajectory")
    if a["targeting"] not in ("fixed", "aim", "track", "track-limited"):
        raise ValueError("Unknown targeting policy")
    if a["kind"] == "parabola" and a["targeting"] != "fixed":
        raise ValueError("Parabolas currently support fixed trajectory only")
    if a["kind"] == "bezier" and a["targeting"] == "track-limited":
        raise ValueError("Limited-turn tracking is not defined for a rigid rotating curve")
    for key, low, high in (("count", 1, 300), ("shotGap", 0, 1), ("speed", 1, 5000),
                           ("direction", -180, 180), ("spread", 0, 180), ("birthY", 0, 50),
                           ("gravity", 0, 900), ("flightTime", .2, 5), ("turnRate", 1, 360)):
        number(a[key], low, high, key)
    if int(a["count"]) != a["count"]:
        raise ValueError("count must be an integer")
    for point in [a["origin"], *a["controls"], a.get("curveEnd",[500,0])]:
        if len(point) != 2:
            raise ValueError("Point must have two coordinates")
        for v in point:
            number(v, -4096, 4096, "point")
    if len(a["controls"]) != 2:
        raise ValueError("Cubic curve requires two control points")
    if math.hypot(*a.get("curveEnd",[500,0]))<.001:
        raise ValueError("Curve endpoint must differ from its origin")
    points=a.get("birthOffsets",[])
    if not isinstance(points,list) or len(points)>300: raise ValueError("Invalid birth point list")
    for point in points:
        if len(point)!=2: raise ValueError("Birth point requires x,y")
        for v in point: number(v,-4096,4096,"birth point")


def load_session(path):
    path = Path(path).resolve()
    config = json.loads(path.read_text(encoding="utf-8-sig"))
    if config["schemaVersion"] not in (1, 2, 3) or not config["sessionId"]:
        raise ValueError("Unsupported preview session")
    if config["schemaVersion"] == 1: validate_attack(config["attack"])
    elif config["schemaVersion"]==2:
        from attack_combo import validate_combo
        validate_combo(config["combo"], config.get("grid"), config["plant"]["position"])
        for field in ("bulletSpeed", "attackInterval"):
            number(config["baseline"][field], .001, 5000, field)
    else:
        from attack_plan import upgrade_plan
        config["plan"]=upgrade_plan(config["plan"])
        if config.get("baseline"):
            for field in ("bulletSpeed","attackInterval"): number(config["baseline"][field],.001,5000,field)
    for n in config["canvas"]:
        number(n, 100, 4096, "canvas")
    if len(config["canvas"]) != 2:
        raise ValueError("Canvas must have width and height")
    for item in config["assets"].values():
        asset = (path.parent / item["path"]).resolve()
        if file_sha(asset) != item["sha256"]:
            raise ValueError(f"Preview asset changed: {asset}")
        item["path"] = str(asset)
    for key in ("plant", "target"):
        actor = config[key]
        for point in (actor["position"], actor["imageOrigin"]):
            if len(point) != 2:
                raise ValueError("Actor point must have two coordinates")
            for n in point:
                number(n, -4096, 4096, key)
    rect=config["target"].get("hitBoxRect")
    if rect is not None:
        if not isinstance(rect,list) or len(rect)!=4:raise ValueError("Invalid target hit rectangle")
        for v in rect:number(v,-4096,4096,"target hit rectangle")
        if rect[2]<=0 or rect[3]<=0:raise ValueError("Empty target hit rectangle")
    number(config["target"]["speed"], 0, 120, "target speed")
    return config


def result(config, attack, plant, target, status):
    if status not in ("confirmed", "cancelled"):
        raise ValueError("Only user confirmation or cancellation can finish a session")
    validate_attack(attack)
    return dict(schemaVersion=1, sessionId=config["sessionId"], configSha256=digest(config),
                status=status, confirmed=status == "confirmed", canvas=config["canvas"],
                provenance=config["provenance"], assets=config["assets"],
                backgroundCrop=config.get("backgroundCrop"),
                coordinateSystem="reference-canvas-x-right-y-down",
                plant=copy.deepcopy(plant), target=copy.deepcopy(target),
                actorPlacementIsPreviewOnly=True,
                attack=copy.deepcopy(attack), attackCooldownIncluded=False,
                binding=config.get("binding", {}))


def bezier(p, t):
    u = 1 - t
    return tuple(u**3*p[0][i]+3*u*u*t*p[1][i]+3*u*t*t*p[2][i]+t**3*p[3][i] for i in (0, 1))


def curve_rotation(attack, origin, target):
    angle=math.radians(attack["direction"])
    endpoint=attack.get("curveEnd",[500,0])
    if attack["targeting"] != "fixed" and math.dist(origin,target)>.001:
        angle+=math.atan2(target[1]-origin[1],target[0]-origin[0])-math.atan2(endpoint[1],endpoint[0])
    return angle


def rotate(point, angle):
    c,s=math.cos(angle),math.sin(angle)
    return [point[0]*c-point[1]*s,point[0]*s+point[1]*c]


def curve_points(attack, origin, target):
    """Rigid local template: rotate all points about birth origin, never stretch."""
    angle=curve_rotation(attack,origin,target)
    local=[*attack["controls"],attack.get("curveEnd",[500,0])]
    return [list(origin), *[[origin[i]+p[i] for i in (0,1)] for p in (rotate(v,angle) for v in local)]]


class Simulation:
    """A single attack; replay delay belongs to the UI, never exported."""
    def __init__(self, attack, plant, target, route_y=0, route_duration=.25):
        validate_attack(attack)
        self.attack = copy.deepcopy(attack)
        self.plant, self.target = list(plant), list(target)
        self.time = 0.
        self.emitted = 0
        self.bullets = []
        self.random = random.Random(42)
        self.route_y, self.route_duration = route_y, route_duration

    def step(self, delta, target):
        number(delta, 0, 3600, "simulation delta")
        self.target = list(target)
        end = self.time+delta
        while self.emitted < self.attack["count"] and self.emitted*self.attack["shotGap"] <= end+1e-9:
            due = self.emitted*self.attack["shotGap"]
            self._advance(max(0.,due-self.time), target)
            self.time=max(self.time,due)
            self._emit(target)
        self._advance(max(0.,end-self.time), target)
        self.time=end

    def _advance(self, delta, target):
        if delta <= 0: return
        a = self.attack
        for b in self.bullets:
            old_age=b["age"]
            b["age"] += delta
            route=self.route_y*min(1., b["age"]/self.route_duration)
            route_delta=route-self.route_y*min(1., old_age/self.route_duration)
            if a["kind"] == "bezier":
                if a["targeting"]=="track": b["curve"]=curve_points(a,b["curve"][0],target)
                b["position"] = bezier(b["curve"], min(1., b["age"]/a["flightTime"]))
                b["position"] = (b["position"][0],b["position"][1]+route)
                continue
            angle = math.atan2(b["velocity"][1], b["velocity"][0])
            if a["targeting"] in ("track", "track-limited"):
                wanted = math.atan2(target[1]-b["position"][1], target[0]-b["position"][0])
                change = (wanted-angle+math.pi) % (2*math.pi)-math.pi
                limit = math.radians(a["turnRate"])*delta
                angle = wanted if a["targeting"] == "track" else angle + max(-limit, min(limit, change))
                b["velocity"] = [math.cos(angle)*a["speed"], math.sin(angle)*a["speed"]]
            vx, vy = b["velocity"]
            gravity = a["gravity"] if a["kind"] == "parabola" else 0
            b["position"] = (b["position"][0]+vx*delta, b["position"][1]+vy*delta+.5*gravity*delta*delta+route_delta)
            b["velocity"][1] += gravity*delta
        self.bullets = [b for b in self.bullets if b["age"] < (a["flightTime"] if a["kind"] == "bezier" else 5)]

    def _emit(self, target):
        a = self.attack
        origin = [self.plant[i]+a["origin"][i] for i in (0, 1)]
        if a.get("birthOffsets"):
            point=a["birthOffsets"][self.emitted % len(a["birthOffsets"])]
            origin=[origin[i]+point[i] for i in (0,1)]
        origin[1] += self.random.uniform(-a["birthY"], a["birthY"])
        angle = math.radians(a["direction"])
        if a["targeting"] != "fixed":
            angle += math.atan2(target[1]-origin[1], target[0]-origin[0])
        if a["kind"] == "fan":
            angle += math.radians(a["spread"])*(self.emitted/(a["count"]-1)-.5) if a["count"] > 1 else 0
        curve = curve_points(a,origin,target)
        self.bullets.append(dict(position=tuple(origin), velocity=[math.cos(angle)*a["speed"], math.sin(angle)*a["speed"]], age=0., curve=curve))
        self.emitted += 1
