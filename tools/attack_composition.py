"""Independent attack layers and nested multiplicative groups."""
import math
from attack_plan import default_plan, validate_plan

FORMAT="pvzhe.attack-composition"

def layers(document):
    def walk(node, multipliers, enabled, path, depth, delay=0):
        if depth>5:raise ValueError("攻击组最多嵌套5层")
        if not isinstance(node,dict) or node.get("kind") not in ("group","attack"):raise ValueError("未知图层类型")
        expected={"kind","id","name","enabled","children","speedMultiplier","rateMultiplier","rangeMultiplier"} if node["kind"]=="group" else {"kind","id","name","enabled","recipe"}
        if set(node)-{"startDelaySeconds"}!=expected:raise ValueError("图层字段不完整")
        if not isinstance(node["id"],str) or not node["id"] or len(node["id"])>128:raise ValueError("图层ID无效")
        if node["id"] in ids:raise ValueError("图层ID重复")
        ids.add(node["id"])
        if len(ids)>160:raise ValueError("图层总数最多160项")
        if not isinstance(node["name"],str) or not node["name"].strip() or len(node["name"])>64:raise ValueError("图层名称需1～64字符")
        if type(node["enabled"]) is not bool:raise ValueError("图层启用状态无效")
        local_delay=node.get("startDelaySeconds",0)
        if isinstance(local_delay,bool) or not isinstance(local_delay,(int,float)) or not math.isfinite(local_delay) or not 0<=local_delay<=5:raise ValueError("发射延迟需0～5秒")
        delay+=local_delay
        enabled=enabled and node["enabled"]
        path=path+[node["name"]]
        if node["kind"]=="group":
            factors=[]
            for key in ("speedMultiplier","rateMultiplier","rangeMultiplier"):
                value=node[key]
                if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not .1<=value<=10:raise ValueError("组倍率需0.1～10")
                factors.append(value)
            if not isinstance(node["children"],list):raise ValueError("攻击组children须为列表")
            for child in node["children"]:yield from walk(child,[a*b for a,b in zip(multipliers,factors)],enabled,path,depth+1,delay)
        else:
            from attack_web import validate_single_recipe
            r=validate_single_recipe(node["recipe"])
            if r["character"]!=document["character"]:raise ValueError("图层角色不同")
            if r["id"] in recipe_ids:raise ValueError("攻击方案ID重复")
            recipe_ids.add(r["id"])
            speed=r["speed"]*multipliers[0];interval=r["intervalSeconds"]/multipliers[1];distance=r["rangeCells"]*multipliers[2]
            if not 1<=speed<=5000 or not .01<=interval<=60000 or distance>1000:raise ValueError("叠加后射速需1～5000逻辑单位/秒、攻击间隔0.01～60000秒、射程最多1000格")
            yield node,dict(speed=speed,interval=interval,range=distance,enabled=enabled,path=path,delay=delay)
    ids=set();recipe_ids=set()
    yield from walk(document["root"],[1,1,1],True,[],0)

def validate(document):
    if set(document)!={"format","schemaVersion","id","character","root"} or document.get("format")!=FORMAT or document.get("schemaVersion") not in (1,2):raise ValueError("组合方案格式无效")
    for key in ("id","character"):
        if not isinstance(document[key],str) or not document[key] or len(document[key])>128:raise ValueError("组合身份无效")
    if document["root"].get("kind")!="group":raise ValueError("组合根节点须为组")
    result=list(layers(document))
    if len(result)>32:raise ValueError("组合最多32个攻击图层")
    return document

def compile_document(document):
    validate(document)
    if not list(layers(document)):raise ValueError("请先添加一个攻击图层再采用方案；空组可保存草稿")
    from attack_web import compile_single_recipe
    plan=default_plan(document["character"]);plan["id"]=document["id"];plan["name"]=document["root"]["name"];plan["groups"]=[]
    for node,effective in layers(document):
        child=compile_single_recipe(node["recipe"])
        group=child["groups"][0];group["id"]=node["id"];group["name"]=node["name"];group["enabled"]=effective["enabled"];group["intervalSeconds"]=effective["interval"]
        if effective["delay"]:group["startDelaySeconds"]=effective["delay"]
        for item in group["items"]:
            item["trajectory"]["speed"]=effective["speed"] if node["recipe"]["pattern"]!="lob" else 300.
            if node["recipe"]["pattern"]=="lob":item["trajectory"]["catapultSpeedScale"]=effective["speed"]/300.
            item["maxTravelCells"]=(effective["range"] or None) if node["recipe"]["pattern"]!="lob" else None
        plan["groups"].append(group)
    validate_plan(plan)
    return plan
