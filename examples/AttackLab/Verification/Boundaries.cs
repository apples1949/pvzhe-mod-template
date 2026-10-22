using Godot;
using D=Godot.Collections.Dictionary;
using A=Godot.Collections.Array;
namespace AttackLab;

// Test-only scene conditions. These methods are excluded from the normal DLL.
public sealed partial class Entry
{
    string? boundaryPlanName;
    partial void ConfigureAuditPlan(ref D plan)
    {
        if(boundaryPlanName!=null)plan=Read(Path.Combine(context.PackageRoot,"AuditPlans",boundaryPlanName+".json"));
    }
    static A V(Vector2 p)=>new(){p.X,p.Y};
    async Task RunBoundaries(SceneTree tree)
    {
        var cases=OS.GetCmdlineUserArgs().Contains("--only-weak-boundary")?new[]{"weak-retarget"}:new[]{"distance-octants","deploy-native","native-retarget","weak-retarget","lob-native","pending-target"};
        foreach(var key in cases)
        {
            boundaryPlanName=key;Launch("straight");
            await Until(tree,()=>context.Game.TryGetBattle(out var b)&&b.Running&&!b.Paused&&!tree.Paused&&!SceneManager.Instance.isLoading,"boundary battle "+key);
            Engine.TimeScale=1;hits=0;
            TowerDefenseCharacter? primary=null;
            if(key!="pending-target")
            {
                var spawned=await context.Game.Characters.SpawnAsync("ZombieNormal",6,3);Check(spawned.Succeeded,spawned.Diagnostic);
                primary=Nodes(tree.Root).OfType<TowerDefenseCharacter>().Single(n=>context.Game.Characters.TryGetHandle(n,out var h)&&h.Equals(spawned.Value));
                primary.instance.hitpoints=1000000;
            }
            var card=TowerDefenseManager.Instance.GetSeedBankList().Single(p=>p.config.saveKey=="PlantPeaShooterSingle");
            var plant=card.Plant(new Vector2I(2,3));Check(plant!=null,"Boundary planting");
            await Until(tree,()=>active?.Plant==plant,"boundary runner");var runner=active!;
            runner.EmissionUntil=key=="pending-target"?1.4:.01;
            // lob-native has a second group's independent first delay at .25.
            if(key=="lob-native")runner.EmissionUntil=.4;
            var result=new D{{"case",key},{"gridWidth",TowerDefenseManager.Instance.GetMapGridSize().X}};
            if(key is "distance-octants" or "deploy-native")
            {
                await Until(tree,()=>runner.Clock>=.1,"early boundary motion");result["early"]=runner.AuditState();
                await Until(tree,()=>runner.Clock>=.65,"distance expiration");
                Check(runner.RangeRemoved==(key=="distance-octants"?8:3),"Native distance did not clear every shot");
                Check(hits==0,"Short distance reached distant target");result["remaining"]=runner.AuditState();
            }
            else if(key is "native-retarget" or "weak-retarget")
            {
                await Until(tree,()=>runner.Clock>=.1,"initial tracking");result["before"]=runner.AuditState();
                var spawned=await context.Game.Characters.SpawnAsync("ZombieNormal",6,2);Check(spawned.Succeeded,spawned.Diagnostic);
                var backup=Nodes(tree.Root).OfType<TowerDefenseCharacter>().Single(n=>context.Game.Characters.TryGetHandle(n,out var h)&&h.Equals(spawned.Value));backup.instance.hitpoints=1000000;
                primary!.SetHitBoxEnabled(false);
                Check(!primary.IsHitBoxEnabled&&primary.targetRegistrationComponent.canProjectileCheck,"Hitbox-only invalidation precondition");
                await Until(tree,()=>runner.AuditHasTarget(backup.GetInstanceId()),"target reacquisition "+key);
                await Until(tree,()=>runner.Clock>=.3,"post-reacquire motion");
                if(key=="weak-retarget")await Wait(tree,.06); // Observe host motion after delayed activation.
                result["after"]=runner.AuditState();result["backupId"]=backup.GetInstanceId();
                if(key=="native-retarget")
                {
                    backup.SetLogicalGlobalPosition(plant!.GetLogicalGlobalPosition()+new Vector2(-150,-80));
                    await Until(tree,()=>runner.AuditHasNegativeX(),"native turnaround");result["turned"]=runner.AuditState();
                    var damaged=await context.Game.Combat.Damage(spawned.Value,2000000);Check(damaged.Succeeded,damaged.Diagnostic);
                    await Until(tree,()=>runner.AuditState().Count==0,"native no-target offscreen cleanup");result["remaining"]=runner.AuditState();
                }
                else
                {
                    primary.SetHitBoxEnabled(true);primary.nearDie=true;backup.SetHitBoxEnabled(false);
                    await Wait(tree,.1);result["invalidOnly"]=runner.AuditState();
                    Check(!runner.AuditHasTarget(primary.GetInstanceId())&&!runner.AuditHasTarget(backup.GetInstanceId()),"Weak tracking retained disabled/near-death target");
                    primary.SetHitBoxEnabled(false);
                    Check(context.Game.Characters.TryGetHandle(plant!,out var plantHandle),"Weak source handle");
                    var sourceDamage=await context.Game.Combat.Damage(plantHandle,100000);Check(sourceDamage.Succeeded,sourceDamage.Diagnostic);
                    int afterDeathBirths=runner.Births.Count;
                    var thirdSpawn=await context.Game.Characters.SpawnAsync("ZombieNormal",7,3);Check(thirdSpawn.Succeeded,thirdSpawn.Diagnostic);
                    var third=Nodes(tree.Root).OfType<TowerDefenseCharacter>().Single(n=>context.Game.Characters.TryGetHandle(n,out var h)&&h.Equals(thirdSpawn.Value));third.instance.hitpoints=1000000;
                    await Until(tree,()=>runner.AuditHasTarget(third.GetInstanceId()),"weak replacement target");
                    Check(afterDeathBirths==runner.Births.Count&&runner.SourceDeadSamples>0,"Owner death cancelled airborne weak behavior or emitted more shots");
                    result["ownerDeathReacquire"]=true;result["sourceDeadSamples"]=runner.SourceDeadSamples;
                    result["thirdId"]=third.GetInstanceId();result["replacement"]=runner.AuditState();
                }
            }
            else if(key=="lob-native")
            {
                await Until(tree,()=>runner.Clock>=.1,"lob first snapshot");result["before"]=runner.AuditState();
                primary!.SetLogicalGlobalPosition(primary.GetLogicalGlobalPosition()+new Vector2(100,-98));
                await Until(tree,()=>runner.Clock>=.6,"lob second snapshot");result["after"]=runner.AuditState();
                Check(runner.Births.Count==2,"Extreme group multiplier changed lob count");
            }
            else
            {
                await Until(tree,()=>runner.Clock>=.65,"empty-target period");Check(runner.Births.Count==0,"Fired without target");
                result["targetArrival"]=runner.Clock;
                var spawned=await context.Game.Characters.SpawnAsync("ZombieNormal",6,3);Check(spawned.Succeeded,spawned.Diagnostic);
                Check(runner.Clock<.79,"Target readiness passed the controlled .8-second round");
                await Until(tree,()=>runner.Clock>=.86,"pending tails before pause");
                TowerDefenseManager.Instance.currentControl.buttonPause.ButtonPressed=true;
                await Until(tree,()=>context.Game.TryGetBattle(out var b)&&b.Paused,"boundary real pause");
                var before=runner.AuditState();int count=runner.Births.Count;double clock=runner.Clock;await Wait(tree,.25);
                Check(runner.Clock==clock&&count==runner.Births.Count&&Json.Stringify(before)==Json.Stringify(runner.AuditState()),"Pending/airborne state advanced during pause");result["pauseFrozen"]=true;
                Nodes(tree.Root).OfType<DialogBoxBase>().Single(n=>n.GetType().Name=="DialogBattlePause").CloseDialog();
                await Until(tree,()=>runner.Clock>=1.8,"pending target completion");
            }
            await Screenshot(tree,"boundary-"+key);
            result["births"]=runner.AuditBirths();result["terminals"]=runner.Terminals;result["samples"]=runner.Samples;result["ranges"]=runner.Ranges;result["hits"]=hits;
            using(var file=Godot.FileAccess.Open("user://boundary-"+key+".json",Godot.FileAccess.ModeFlags.Write))file.StoreString(Json.Stringify(result));
            context.Log("ATTACK_LAB_BOUNDARY_CASE: "+key+" births="+runner.Births.Count+" ranges="+runner.RangeRemoved);
            SceneManager.Instance.ChangeScene("MainMenu");await Until(tree,()=>tree.CurrentScene is MainMenu&&!SceneManager.Instance.isLoading&&active==null,"boundary cleanup "+key);
            Check(runner.ActiveCount==0,"Boundary registrations leaked");
        }
        boundaryPlanName=null;
    }
}

public sealed partial class PlanRunner
{
    public A AuditState()
    {
        var rows=new A();
        foreach(var shot in flying)
        {
            ref var b=ref field.GetBulletDataRef(shot.Index);if(!b.active||b.over||b.lifecycleOwnerSequence!=shot.Generation)continue;
            var target=b.trackOpen?b.target:shot.Target;
            rows.Add(new D{{"item",shot.Item["id"]},{"generation",shot.Generation},{"position",new A{b.pos.X,b.pos.Y}},{"velocity",new A{b.vel.X,b.vel.Y}},
                {"age",Clock-shot.BornTime},{"nativeTracking",b.trackOpen},{"deployed",shot.DeployTime>0},{"hitOver",b.hitOver},
                {"targetId",GodotObject.IsInstanceValid(target)?target!.GetInstanceId():0UL},{"distanceOrigin",new A{b.savePos.X,b.savePos.Y}},
                {"fireLength",b.fireLength},{"checkDistance",b.checkDistance},{"catapultTarget",new A{b.catapultTargetPos.X,b.catapultTargetPos.Y}},
                {"flightTime",b.catapultTime},{"z",b.z},{"ySpeed",b.ySpeed}});
        }
        return rows;
    }
    public bool AuditHasTarget(ulong id)=>AuditState().Any(v=>v.AsGodotDictionary()["targetId"].AsUInt64()==id);
    public bool AuditHasNegativeX()=>AuditState().Any(v=>Point(v.AsGodotDictionary()["velocity"]).X<0);
    public A AuditBirths()
    {
        var rows=new A();foreach(var b in Births)rows.Add(new D{{"item",b.Item},{"group",b.Group},{"generation",b.Generation},{"intended",b.Intended},{"actual",b.Actual},
            {"root",new A{b.Root.X,b.Root.Y}},{"position",new A{b.Position.X,b.Position.Y}},{"velocity",new A{b.Velocity.X,b.Velocity.Y}},
            {"flightTime",b.FlightTime},{"z",b.Z},{"ySpeed",b.YSpeed},{"target",new A{b.Target.X,b.Target.Y}}});return rows;
    }
}
