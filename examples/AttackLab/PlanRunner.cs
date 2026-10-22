using Godot;
using PVZHE.ModEditor.ModSystem;
using D=Godot.Collections.Dictionary;
namespace AttackLab;

// Deliberately scoped example adapter for the web editor's schema5 subset, not a general plan SDK.
public sealed partial class PlanRunner : IDisposable
{
    sealed class Group { public required string Id; public required D Data; public double Next,Interval; }
    sealed class Pending { public required Group Group;public required D Item;public required string ItemId;public double Due;public int Count=1; }
    sealed class Flying
    {
        public int Index,Generation;public required D Item;public Vector2 Previous,Start,End;
        public double DeployAge,DeployTime;public int Flags;public TowerDefenseCharacter? Target;
        public ulong BornFrame;
        public double BornTime;
    }
    public record Birth(string Group,string Item,double Intended,double Actual,Vector2 Root,Vector2 Position,Vector2 Velocity,Vector2 Target,int Generation,int Index,double FlightTime,double Z,double YSpeed);
    readonly XWModRuntimeContext context;readonly TowerDefenseCharacter plant;readonly BulletField field;
    readonly List<Group> groups=new();readonly List<Flying> flying=new();
    readonly List<Pending> queue=new();readonly List<TowerDefenseCharacter> targets=new();
    readonly SceneTree tree;readonly FireComponent fire;readonly bool originalFireAlive;int generation;static int nextGeneration;bool disposed;
    public double Clock{get;private set;}
    partial void ObserveSpawn(Birth birth);
    partial void ObserveStep(Flying shot,ref BulletData b,double age,double dt);
    partial void ObserveRange(double distance,double limit,double step);
    partial void ObserveInitialize();partial void ObserveDispose();
    partial void ConfigureSpawn(ref BulletFieldSpawnOverrides overrides);
    public double EmissionUntil{get;set;}=double.PositiveInfinity;
    public int RangeRemoved{get;private set;} public int DeploymentSamples{get;private set;}
    public int GuidanceSamples{get;private set;} public int SourceDeadSamples{get;private set;}
    public int ActiveCount=>flying.Count;
    public TowerDefenseCharacter Plant=>plant;
    public PlanRunner(XWModRuntimeContext context,TowerDefenseCharacter plant,D plan)
    {
        this.context=context;this.plant=plant;tree=plant.GetTree();field=BulletField.EnsureMountedOnCharacterNode();
        if(plan["schemaVersion"].AsInt32()!=5)throw new Exception("Unsupported plan version");
        foreach(var value in plan["groups"].AsGodotArray())
        {
            var group=value.AsGodotDictionary();if(!group["enabled"].AsBool())continue;
            foreach(var item in group["items"].AsGodotArray())
            {
                var data=item.AsGodotDictionary();var kind=data["trajectory"].AsGodotDictionary()["kind"].AsString();
                var guidance=data["guidance"].AsGodotDictionary();
                if(guidance.TryGetValue("model",out var model)&&model.AsString()!="host-guidance-v2")throw new Exception("Adapter requires current host guidance; do not reinterpret legacy steering as delay");
                if(data["carrier"].AsString()!="projectile"||kind is not ("straight" or "parabola"))throw new Exception("Adapter supports editor projectile straight/parabola only");
            }
            groups.Add(new Group{Id=group["id"].AsString(),Data=group,Next=Num(group,"startDelaySeconds"),Interval=Num(group,"intervalSeconds",Num(plan,"intervalSeconds"))});
        }
        fire=plant.componentManager.GetRuntime<FireComponent>();originalFireAlive=fire.alive;fire.alive=false;
        foreach(var node in Entry.Nodes(tree.Root))Added(node);tree.NodeAdded+=Added;ObserveInitialize();
    }
    void Added(Node node)
    {
        if(node is TowerDefenseCharacter target&&target!=plant)targets.Add(target);
    }
    static bool Valid(TowerDefenseCharacter? n)=>GodotObject.IsInstanceValid(n)&&n!.IsInsideTree()&&!n.die&&!n.nearDie&&n.IsHitBoxEnabled&&n.targetRegistrationComponent?.canProjectileCheck==true;
    TowerDefenseCharacter? Target(Vector2 origin)
    {
        targets.RemoveAll(n=>!GodotObject.IsInstanceValid(n)||!n.IsInsideTree());
        TowerDefenseCharacter? best=null;float nearest=float.PositiveInfinity;
        foreach(var n in targets)if(Valid(n)&&n.camp==TowerDefenseEnum.CHARACTER_CAMP.ZOMBIE){float distance=n.GetLogicalGlobalPosition().DistanceSquaredTo(origin);if(distance<nearest){nearest=distance;best=n;}}
        return best;
    }
    internal static double Num(D d,string key,double fallback=0)=>d.TryGetValue(key,out var v)&&v.VariantType!=Variant.Type.Nil?v.AsDouble():fallback;
    internal static Vector2 Point(Variant v){var a=v.AsGodotArray();return new Vector2(a[0].AsSingle(),a[1].AsSingle());}
    public void Tick(double delta)
    {
        if(disposed)return;Clock+=delta;
        UpdateFlying(delta);
        if(!ValidSource()){queue.Clear();return;}
        // This experiment's documented eligibility is a valid target in its scene.
        // A skipped round must not leave delayed shots that acquire a future target.
        bool canStartRound=Target(plant.GetLogicalGlobalPosition())!=null;
        foreach(var group in groups)
            while(group.Next<=Clock+1e-8&&group.Next<EmissionUntil-1e-8)
            {
                if(canStartRound)foreach(var value in group.Data["items"].AsGodotArray())
                {
                    var item=value.AsGodotDictionary();if(!item["enabled"].AsBool())continue;
                    double when=group.Next+Num(item,"time");string id=item["id"].AsString();
                    var stream=queue.FirstOrDefault(p=>p.Group==group&&p.ItemId==id&&Math.Abs(p.Due+p.Count*group.Interval-when)<1e-7);
                    if(stream!=null)stream.Count++;else queue.Add(new Pending{Group=group,Item=item,ItemId=id,Due=when});
                }
                group.Next+=group.Interval;
            }
        queue.Sort((a,b)=>a.Due.CompareTo(b.Due));
        while(queue.Count>0&&queue[0].Due<=Clock+1e-8)
        {
            var pending=queue[0];queue.RemoveAt(0);Spawn(pending.Group,pending.Item,pending.Due);
            if(--pending.Count>0){pending.Due+=pending.Group.Interval;queue.Add(pending);queue.Sort((a,b)=>a.Due.CompareTo(b.Due));}
        }
    }
    bool ValidSource()=>GodotObject.IsInstanceValid(plant)&&plant.IsInsideTree()&&!plant.die;
    void Spawn(Group group,D item,double intended)
    {
        var root=plant.GetLogicalGlobalPosition();var launch=item["launch"].AsGodotDictionary();
        var trajectory=item["trajectory"].AsGodotDictionary();var guide=item["guidance"].AsGodotDictionary();
        var offset=Point(launch["offset"]);var origin=root+offset;var target=Target(origin);if(target==null)return;
        double angle=Mathf.DegToRad((float)Num(trajectory,"direction"));
        if(guide["initialAim"].AsBool())
        {
            var reference=origin;
            if(launch.TryGetValue("aimFrame",out var frameValue))
            {
                var frame=frameValue.AsGodotDictionary();reference=root+Point(frame["centerOffset"]);
                float turn=(target.GetLogicalGlobalPosition()-reference).Angle();origin=reference+Point(frame["localOffset"]).Rotated(turn);
            }
            angle+=(target.GetLogicalGlobalPosition()-reference).Angle();
        }
        bool lob=trajectory["kind"].AsString()=="parabola";
        var velocity=Vector2.Right.Rotated((float)angle)*(float)Num(trajectory,"speed");
        var config=(TowerDefenseProjectileConfig)ResourceManager.Instance.PROJECTILE_CONFIG[context.Content.Identity("Projectile",lob?"Lob":Num(guide,"trackingStrength")==2?"Track":"Pea").RuntimeKey];
        generation=Interlocked.Increment(ref nextGeneration);
        var actual=origin;double height=0;var overrides=new BulletFieldSpawnOverrides{lifecycleOwnerSequence=generation,spawnSourceInstanceId=plant.GetInstanceId(),checkAllOverride=true};
        if(lob)
        {
            actual=new Vector2(origin.X,root.Y+20);height=root.Y-origin.Y;
            overrides.catapultStartPositionOverride=origin; // Host applies its native target offset and snapshot.
        }
        var deployment=launch.TryGetValue("deployment",out var deploy)?deploy.AsGodotDictionary():null;
        var start=deployment==null?actual:root+Point(deployment["offset"]);
        if(deployment!=null&&launch.TryGetValue("aimFrame",out var aim))
        {
            var frame=aim.AsGodotDictionary();var center=root+Point(frame["centerOffset"]);float turn=(target.GetLogicalGlobalPosition()-center).Angle();start=center+(start-center).Rotated(turn);
        }
        var grid=plant.gridPos;
        if(!lob&&Num(guide,"trackingStrength")==2)overrides.fireMethodFlagsOverride=32;
        ConfigureSpawn(ref overrides);
        int index=field.TrySpawnFromConfig(config,start,velocity,velocity.Length(),plant,TowerDefenseEnum.CHARACTER_CAMP.PLANT,grid,grid.Y,TowerDefenseManager.GetMapFeature().rect,lob||Num(guide,"trackingStrength")==2?target:null,height,plant.groundHeight,-1,lob?-1:Num(item,"maxTravelCells")>0?(float)Num(item,"maxTravelCells"):-1,false,true,overrides:overrides);
        if(index<0)throw new Exception("Host rejected projectile");
        ref var b=ref field.GetBulletDataRef(index);
        var flight=new Flying{Index=index,Generation=generation,Item=item,Start=start,End=actual,Previous=b.pos,Target=target,BornFrame=Engine.GetPhysicsFrames(),BornTime=Clock};
        if(deployment!=null){flight.DeployTime=Num(deployment,"duration");flight.Flags=b.collisionFlags;b.fireLength=-1;b.externalControlled=true;b.hitOver=true;}

        flying.Add(flight);
        ObserveSpawn(new Birth(group.Id,item["id"].AsString(),intended,Clock,root,b.pos,b.vel,target.GetLogicalGlobalPosition(),generation,index,b.catapultTime,b.z,b.ySpeed));

    }
    void UpdateFlying(double dt)
    {
        foreach(var shot in flying.ToArray())
        {
            ref var b=ref field.GetBulletDataRef(shot.Index);
            if(!b.active||b.over||b.lifecycleOwnerSequence!=shot.Generation){flying.Remove(shot);continue;}
            double age=Clock-shot.BornTime;
            ObserveStep(shot,ref b,age,dt);
            if(!ValidSource())SourceDeadSamples++;
            if(shot.DeployTime>0)
            {
                shot.DeployAge+=dt;float t=(float)Math.Min(1,shot.DeployAge/shot.DeployTime);b.pos=shot.Start.Lerp(shot.End,t);shot.Previous=b.pos;DeploymentSamples++;
                if(t<1)continue;
                shot.DeployTime=0;b.externalControlled=false;b.hitOver=false;b.collisionFlags=shot.Flags;b.savePos=b.pos;b.fireLength=Num(shot.Item,"maxTravelCells")>0?(int)Num(shot.Item,"maxTravelCells"):-1;
                continue;
            }
            var guide=shot.Item["guidance"].AsGodotDictionary();float strength=(float)Num(guide,"trackingStrength");
            if(strength==1&&!b.trackOpen&&WebGuidance.Active(strength,age,Num(guide,"trackingDelaySeconds",.5)))
            {
                if(!Valid(shot.Target))shot.Target=Target(b.pos);
                if(Valid(shot.Target))
                {
                    field.SetTrackData(shot.Index,shot.Target!);GuidanceSamples++;
                }
            }
        }
    }
    public void Dispose(){if(disposed)return;disposed=true;ObserveDispose();tree.NodeAdded-=Added;queue.Clear();if(GodotObject.IsInstanceValid(field))foreach(var s in flying)if(field.GetBulletDataRef(s.Index).active&&field.GetBulletDataRef(s.Index).lifecycleOwnerSequence==s.Generation)field.Despawn(s.Index);flying.Clear();if(ValidSource()&&fire.IsAttached)fire.alive=originalFireAlive;}
}
