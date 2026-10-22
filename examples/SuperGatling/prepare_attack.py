"""Compile this example's confirmed straight-shot design into its small runtime asset."""
import argparse
import json
import math
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"tools"))
from attack_model import load_session,digest,save
from attack_plan import validate_plan,all_items,launch_position,design_digest


def compile_pattern(result,session,emission_window=1.):
    plan=result["plan"]
    if result.get("schemaVersion")!=3 or result.get("status")!="confirmed" or result.get("confirmed") is not True:
        raise ValueError("Only a confirmed plan can be applied")
    if (result.get("sessionId")!=session["sessionId"] or result.get("configSha256")!=digest(session)
            or result.get("planSha256")!=digest(plan)):
        raise ValueError("Session or plan identity mismatch")
    validate_plan(plan)
    binding=result.get("binding",{})
    if binding!=session.get("binding",{}): raise ValueError("Attack binding mismatch")
    if plan["trigger"]!=session["plan"]["trigger"]:
        raise ValueError("Changed trigger region requires a separate host mapping")
    if binding.get("attack")!="power" or binding.get("sourceModId")!="super-gatling-pea":
        raise ValueError("Not this example's power attack")
    if binding.get("preserveNormalAttack") is not True or binding.get("preserveActivationProbability") is not True:
        raise ValueError("Activation/normal attack changes need a separate implementation")
    if plan["character"]!=session["plant"]["key"]: raise ValueError("Character mismatch")
    anchor=binding["referencePoseMuzzleOffset"]
    shots=[]
    for group,item in all_items(plan):
        if not group["enabled"] or not item["enabled"]: continue
        trajectory=item["trajectory"]
        if item["guidance"].get("model")in ("host-guidance-v1","host-guidance-v2"):
            raise ValueError("This legacy finite-turn adapter cannot apply host-guidance-v1; use the native-first mapping instead of silently changing tracking")
        if (item["carrier"]!="projectile" or trajectory["kind"]!="straight"
                or item["guidance"]["initialAim"]
                or item["route"]["rowOffset"] or item["maxTravelCells"] is not None):
            raise ValueError("This example adapter supports unbounded straight shots with finite-turn guidance, without initial aim or row routing")
        position=launch_position(item,[0,0],session["grid"])
        angle=math.radians(trajectory["direction"])
        shots.append(dict(time=item["time"],offset=[position[n]-anchor[n] for n in (0,1)],
                          velocity=[math.cos(angle)*trajectory["speed"],math.sin(angle)*trajectory["speed"]],
                          trackingStrength=item["guidance"]["trackingStrength"],id=item["id"]))
    if not shots: raise ValueError("Power pattern must contain an enabled shot")
    if not math.isfinite(emission_window) or not 0<emission_window<=60:
        raise ValueError("Invalid finite power emission window")
    interval=plan["intervalSeconds"]
    rounds=math.ceil(emission_window/interval-1e-9)
    if rounds*len(shots)>6000: raise ValueError("Expanded power schedule exceeds this adapter's 6000-shot budget")
    scheduled=[]
    for round_index in range(rounds):
        for shot in shots:
            value=dict(shot,time=round(round_index*interval+shot["time"],9),round=round_index)
            if value["time"]>60: raise ValueError("Expanded power tail exceeds supported 60 seconds")
            scheduled.append(value)
    scheduled.sort(key=lambda shot:shot["time"])
    return dict(schemaVersion=3,designSha256=design_digest(plan),activation="existing-10-percent-per-normal-round",
                intervalRole="power-round-start-interval",roundIntervalSeconds=interval,
                emissionWindowSeconds=emission_window,roundCount=rounds,shotsPerRound=len(shots),shots=scheduled)



if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result",required=True); parser.add_argument("--session",required=True)
    parser.add_argument("--emission-window",type=float,default=1.,help="Power round-start window in seconds; pending delayed shots finish afterwards")
    args=parser.parse_args()
    value=compile_pattern(json.loads(Path(args.result).read_text(encoding="utf-8")),load_session(args.session),args.emission_window)
    save(Path(__file__).parent/"mod/Assets/power-pattern.json",value)
    print("Compiled",len(value["shots"]),"shots; normal attack and activation probability preserved")
