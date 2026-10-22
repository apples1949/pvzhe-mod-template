using Godot;
using D=Godot.Collections.Dictionary;
namespace AttackLab;

// These buffers and per-frame traces are compiled only into the audit DLL.
public sealed partial class PlanRunner
{
    public List<Birth> Births{get;}=new();
    public readonly Godot.Collections.Array Samples=new(),Ranges=new(),MotionTrace=new(),Terminals=new();
    public bool TraceMotion{get;set;}
    readonly Dictionary<int,int> sampleCounts=new();
    partial void ObserveInitialize(){field.OnBulletLifecycleEnded+=Ended;}
    partial void ObserveDispose(){if(GodotObject.IsInstanceValid(field))field.OnBulletLifecycleEnded-=Ended;}
    void Ended(TowerDefenseCharacter source,int owner,int slot,BulletField.BulletLifecycleTerminalReason reason)
    {
        if(source!=plant)return;
        var shot=flying.FirstOrDefault(s=>s.Generation==owner);
        if(shot!=null){ref var b=ref field.GetBulletDataRef(shot.Index);double limit=Num(shot.Item,"maxTravelCells");double distance=b.savePos.DistanceTo(b.pos)/TowerDefenseManager.Instance.GetMapGridSize().X;
            if(limit>0&&distance>limit){RangeRemoved++;ObserveRange(distance,limit,b.vel.Length()/TowerDefenseManager.Instance.GetMapGridSize().X/Engine.PhysicsTicksPerSecond);}}
        var terminal=new D{{"generation",owner},{"slot",slot},{"frame",Engine.GetPhysicsFrames()},{"reason",reason.ToString()}};
        if(shot!=null){ref var b=ref field.GetBulletDataRef(shot.Index);terminal["position"]=new Godot.Collections.Array{b.pos.X,b.pos.Y};terminal["distanceOrigin"]=new Godot.Collections.Array{b.savePos.X,b.savePos.Y};terminal["fireLength"]=b.fireLength;terminal["checkDistance"]=b.checkDistance;terminal["nativeTracking"]=b.trackOpen;}
        Terminals.Add(terminal);
    }
    partial void ConfigureSpawn(ref BulletFieldSpawnOverrides overrides){overrides.lifecycleSubscribed=true;overrides.lifecycleSlot=overrides.lifecycleOwnerSequence;}
    partial void ObserveSpawn(Birth birth){Births.Add(birth);}
    partial void ObserveRange(double distance,double limit,double step){Ranges.Add(new D{{"distance",distance},{"limit",limit},{"step",step}});}
    partial void ObserveStep(Flying shot,ref BulletData b,double age,double dt)
    {
        if(TraceMotion)MotionTrace.Add(new D{{"clock",Clock},{"age",age},{"generation",shot.Generation},{"index",shot.Index},{"x",b.pos.X},{"y",b.pos.Y},{"vx",b.vel.X},{"vy",b.vel.Y},{"external",b.externalControlled},{"hitOver",b.hitOver},{"blocked",b.blocked},{"tween",b.spawnTweenDuration},{"delta",dt},{"physicsFrame",Engine.GetPhysicsFrames()}});
        int sample=sampleCounts.TryGetValue(shot.Generation,out var count)?count:0;
        double[] thresholds={.1,.3,.55,.7};
        if(sample<thresholds.Length&&age>=thresholds[sample]-1e-8)
        {
            Samples.Add(new D{{"item",shot.Item["id"]},{"generation",shot.Generation},{"age",age},{"position",new Godot.Collections.Array{b.pos.X,b.pos.Y}},{"velocity",new Godot.Collections.Array{b.vel.X,b.vel.Y}},{"z",b.z},{"ySpeed",b.ySpeed},{"nativeTracking",b.trackOpen},{"checkDistance",b.checkDistance},{"catapultTime",b.catapultTime},{"deployment",shot.DeployTime>0},{"hitOver",b.hitOver}});sampleCounts[shot.Generation]=sample+1;
        }
    }
}
