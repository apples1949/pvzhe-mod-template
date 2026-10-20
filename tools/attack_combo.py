"""Legacy v2 combo import support; the current single-carrier plan is attack_plan.

Batch/arrangement fields here only describe old inputs expanded during migration.
"""
import copy
import math
import uuid
from attack_model import Simulation, default_attack, number, validate_attack, result

COLORS = ["#ffe27c", "#72dbec", "#ef9ac4", "#c0df81", "#c5acff", "#ffb273"]


def arrangement():
    return dict(kind="single", count=5, spacing=16, rows=[1, 2, 3, 4, 5], timing="together", stagger=.5, routeDuration=.25)


def new_item(name="直射", attack=None, start=0):
    a = copy.deepcopy(attack or default_attack())
    return dict(id=uuid.uuid4().hex, name=name, enabled=True, start=start, attack=a, arrangement=arrangement())


def default_combo(attack=None):
    return dict(attackRate=1., steps=[new_item(attack=attack)])


def round_interval(combo, baseline=None):
    if "intervalSeconds" in combo: return combo["intervalSeconds"]
    return baseline["attackInterval"]/combo["attackRate"] if baseline else None


def lanes(item, grid=None, plant=None):
    a = item["arrangement"]
    if a["kind"] == "single": return [dict(y=0, delay=0, row=None, offsetLine=0)]
    count = int(a["count"]) if a["kind"] == "parallel" else len(a["rows"])
    origin_row = None
    if a["kind"] == "rows":
        if not grid or plant is None: raise ValueError("Map-row routes require version-bound grid geometry")
        origin_row = math.floor((plant[1]-grid["begin"][1])/grid["size"][1])+1
        if not 1 <= origin_row <= grid["rows"]: raise ValueError("Plant is outside the map rows")
    output = []
    for index in range(count):
        label = index+1 if a["kind"] == "parallel" else a["rows"][index]
        output.append(dict(y=(index-(count-1)/2)*a["spacing"] if a["kind"] == "parallel" else (label-origin_row)*grid["size"][1],
                           delay=a["stagger"] if a["timing"] == "alternating" and label % 2 else 0,
                           row=label if a["kind"] == "rows" else None,
                           offsetLine=0 if origin_row is None else label-origin_row))
    return output


def validate_combo(combo, grid=None, plant=None):
    number(combo["attackRate"], .05, 30, "round attack rate")
    if "intervalSeconds" in combo: number(combo["intervalSeconds"], .1, 30, "round seconds")
    steps = combo["steps"]
    if not 1 <= len(steps) <= 24: raise ValueError("A round needs 1..24 items")
    ids, total = set(), 0
    for item in steps:
        if not isinstance(item["id"], str) or not item["id"] or item["id"] in ids: raise ValueError("Duplicate/empty item identity")
        ids.add(item["id"])
        if not isinstance(item["name"], str) or not item["name"].strip() or len(item["name"]) > 64: raise ValueError("Item needs a short name")
        if not isinstance(item["enabled"], bool): raise ValueError("Item enabled must be boolean")
        number(item["start"], 0, 30, "item start")
        validate_attack(item["attack"])
        a = item["arrangement"]
        if a["kind"] not in ("single", "parallel", "rows") or a["timing"] not in ("together", "alternating"): raise ValueError("Unknown arrangement")
        number(a["count"], 1, 9, "lane count")
        if int(a["count"]) != a["count"]: raise ValueError("Lane count must be integer")
        number(a["spacing"], 0, 100, "lane spacing")
        number(a["stagger"], 0, 10, "lane stagger")
        number(a["routeDuration"], .05, 3, "route transition")
        if not a["rows"] or len(set(a["rows"])) != len(a["rows"]): raise ValueError("Select distinct map rows")
        for row in a["rows"]:
            number(row, 1, grid["rows"] if grid else 5, "map row")
            if int(row) != row: raise ValueError("Map row must be integer")
        entries = lanes(item, grid, plant)
        end = item["start"] + max(e["delay"] for e in entries) + (item["attack"]["count"]-1)*item["attack"]["shotGap"]
        if end > 60: raise ValueError("A round's last emission must be within 60 seconds (not a feedback timeout)")
        if item["enabled"]: total += len(entries)*item["attack"]["count"]
    if total > 6000: raise ValueError("Preview budget exceeded: maximum 6000 projectiles per round")
    return total


def emission_end(combo, grid=None, plant=None):
    return max((item["start"]+max(l["delay"] for l in lanes(item, grid, plant))+(item["attack"]["count"]-1)*item["attack"]["shotGap"]
                for item in combo["steps"] if item["enabled"]), default=0.)


def make_preset(name, attack=None):
    a = copy.deepcopy(attack or default_attack())
    a.pop("birthOffsets",None)
    a.update(kind="straight", targeting="fixed", count=5, shotGap=.06, direction=0)
    if name == "single":
        a.update(count=1, shotGap=0)
        return default_combo(a)
    if name == "parallel-alternating":
        first=new_item("偶数弹流",dict(a,kind="fan",count=2,shotGap=0,spread=0,birthOffsets=[[0,-16],[0,16]]))
        second=new_item("奇数弹流",dict(a,kind="fan",count=3,shotGap=0,spread=0,birthOffsets=[[0,-32],[0,0],[0,32]]),start=.5)
        return dict(attackRate=1.,steps=[first,second])
    if name == "rows-alternating":
        steps=[]
        for row in (2,4,1,3,5):
            step=new_item("第"+str(row)+"行",dict(a,count=1,shotGap=0),start=0 if row%2==0 else .5)
            step["arrangement"].update(kind="rows",rows=[row])
            steps.append(step)
        return dict(attackRate=1.,steps=steps)
    if name == "fan-track":
        first = new_item("扇形", dict(a, kind="fan", count=7, shotGap=0, spread=45))
        second = new_item("追踪", dict(a, targeting="track"), start=.5)
        return dict(attackRate=1., steps=[first, second])
    if name == "dual-alternating":
        first = new_item("上炮口", a); first["attack"]["origin"][1] -= 10
        second = new_item("下炮口", a, start=.5); second["attack"]["origin"][1] += 10
        return dict(attackRate=1., steps=[first, second])
    raise ValueError("Unknown combo preset")


def expand_arrangements(combo, grid, plant):
    """Flatten legacy convenience layouts without changing emission times/counts."""
    output=copy.deepcopy(combo)
    output["steps"]=[]
    for item in combo["steps"]:
        if item["arrangement"]["kind"]=="single" or (item["arrangement"]["kind"]=="rows" and len(item["arrangement"]["rows"])==1):
            output["steps"].append(copy.deepcopy(item)); continue
        for index,lane in enumerate(lanes(item,grid,plant)):
            child=copy.deepcopy(item)
            child.update(id=uuid.uuid4().hex,name=item["name"][:50]+" "+str(index+1),start=item["start"]+lane["delay"])
            child["arrangement"]=arrangement()
            if lane["row"] is None: child["attack"]["origin"][1]+=lane["y"]
            else: child["arrangement"].update(kind="rows",rows=[lane["row"]],routeDuration=item["arrangement"]["routeDuration"])
            output["steps"].append(child)
    validate_combo(output,grid,plant)
    return output


def expand_fan(combo, identity, grid=None, plant=None):
    """Fan is syntax sugar for independently editable straight projectiles."""
    output=copy.deepcopy(combo)
    index=next(i for i,s in enumerate(output["steps"]) if s["id"]==identity)
    item=output["steps"][index]; attack=item["attack"]
    if attack["kind"]!="fan": raise ValueError("请选择扇形子项")
    children=[]
    for n in range(attack["count"]):
        child=copy.deepcopy(item)
        child.update(id=uuid.uuid4().hex,name=item["name"][:50]+" "+str(n+1),start=item["start"]+n*attack["shotGap"])
        delta=attack["spread"]*(n/(attack["count"]-1)-.5) if attack["count"]>1 else 0
        direction=(attack["direction"]+delta+180)%360-180
        child["attack"].update(kind="straight",count=1,shotGap=0,direction=direction)
        if attack.get("birthOffsets"):
            child["attack"]["birthOffsets"]=[copy.deepcopy(attack["birthOffsets"][n%len(attack["birthOffsets"])])]
        children.append(child)
    output["steps"][index:index+1]=children
    validate_combo(output,grid,plant)
    return output


class ComboSimulation:
    def __init__(self, combo, plant, target, grid=None, only=None):
        validate_combo(combo, grid, plant)
        self.time, self.entries = 0., []
        self.emitted = 0
        self.bullets = []
        for index, item in enumerate(combo["steps"]):
            if not item["enabled"] or (only is not None and item["id"] != only): continue
            for lane in lanes(item, grid, plant):
                attack = copy.deepcopy(item["attack"])
                if lane["row"] is None: attack["origin"][1] += lane["y"]
                self.entries.append(dict(start=item["start"]+lane["delay"], sim=Simulation(attack, plant, target,
                                         route_y=lane["y"] if lane["row"] is not None else 0, route_duration=item["arrangement"]["routeDuration"]),
                                         begun=False, lane=lane, duration=item["arrangement"]["routeDuration"], id=item["id"], color=COLORS[index % len(COLORS)]))

    def step(self, delta, target):
        previous = self.time
        self.time += delta
        self.bullets = []
        for entry in self.entries:
            if self.time+1e-9 < entry["start"]: continue
            sim = entry["sim"]
            if not entry["begun"]:
                sim.step(0, target); entry["begun"] = True
            elapsed = max(0., self.time-max(previous, entry["start"]))
            if elapsed: sim.step(elapsed, target)
            for b in sim.bullets:
                shown = dict(b, itemId=entry["id"], color=entry["color"], lane=entry["lane"])
                self.bullets.append(shown)
        self.emitted = sum(e["sim"].emitted for e in self.entries)


class ComboPlayback:
    """Round-start cadence is separate from item offsets; overlapping rounds survive."""
    def __init__(self, combo, plant, target, grid=None, interval=None, repeat=False, only=None):
        if interval is not None: number(interval, .001, 50000, "round interval")
        self.combo, self.plant, self.grid = copy.deepcopy(combo), list(plant), grid
        self.interval = interval
        self.repeat, self.only = repeat, only
        self.time, self.next_round, self.rounds_started = 0., 0., 0
        self.rounds, self.bullets, self.emitted = [], [], 0
        self.keep = emission_end(combo, grid, plant)+5.1

    def step(self, delta, target):
        self.time += delta
        for start, sim in self.rounds: sim.step(delta, target)
        while self.next_round <= self.time+1e-9:
            if self.rounds_started and (not self.repeat or self.interval is None): break
            start = self.next_round
            sim = ComboSimulation(self.combo, self.plant, target, self.grid, self.only)
            sim.step(max(0., self.time-start), target)
            self.rounds.append((start, sim)); self.rounds_started += 1
            if not self.repeat or self.interval is None: break
            self.next_round += self.interval
        self.rounds = [(start, sim) for start, sim in self.rounds if self.time-start <= self.keep]
        self.bullets = [b for _, sim in self.rounds for b in sim.bullets]
        self.emitted = sum(sim.emitted for _, sim in self.rounds)


def combo_result(config, combo, plant, target, status):
    if status == "confirmed": validate_combo(combo, config.get("grid"), plant["position"])
    output = result(config, combo["steps"][0]["attack"], plant, target, status)
    output.pop("attack")
    baseline = config.get("baseline")
    interval = round_interval(combo,baseline)
    output.update(schemaVersion=2, combo=copy.deepcopy(combo), baseline=baseline, roundInterval=interval,
                  attackCooldownIncluded=interval is not None, grid=config.get("grid"))
    return output
