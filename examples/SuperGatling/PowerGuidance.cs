using Godot;
namespace SuperGatlingPea;

// Battle-scoped: already-fired ammunition keeps guiding after its plant dies.
public sealed class PowerGuidance : IDisposable
{
    sealed class Guided
    {
        public required FireComponent Source;
        public required float Strength;
        public required float Speed;
        public TowerDefenseCharacter? Target;
    }
    readonly Dictionary<int,Guided> tracked=new();
    readonly Dictionary<(FireComponent,int),TowerDefenseCharacter?> candidates=new();
    ulong candidateFrame=ulong.MaxValue;
    readonly string projectile;
    BulletField? field;
    FireComponent? pendingSource;
    float pendingStrength;
    public int TrackedCount=>tracked.Count;
    internal string Describe(int index)=>tracked.TryGetValue(index,out var g)?$"strength={g.Strength} targetValid={Valid(g.Target)} attached={g.Source.IsAttached}":"unregistered";
    public PowerGuidance(string projectile){this.projectile=projectile;}
    void Attach()
    {
        var current=BulletField.EnsureMountedOnCharacterNode();
        if(ReferenceEquals(field,current))return;
        if(GodotObject.IsInstanceValid(field))field!.OnBulletSpawned-=Spawned;
        tracked.Clear();field=current;field.OnBulletSpawned+=Spawned;
    }
    public void Launch(FireComponent source,float strength,Action spawn)
    {
        Attach();
        var previous=pendingSource;float previousStrength=pendingStrength;
        pendingSource=source;pendingStrength=strength;
        try{spawn();}finally{pendingSource=previous;pendingStrength=previousStrength;}
    }
    static bool Valid(TowerDefenseCharacter? target)=>GodotObject.IsInstanceValid(target)&&target!.IsInsideTree()&&!target.die&&target.targetRegistrationComponent?.canProjectileCheck==true;
    TowerDefenseCharacter? FindTarget(FireComponent source,int flags,Vector2 position)
    {
        ulong frame=Engine.GetPhysicsFrames();
        if(frame!=candidateFrame){candidates.Clear();candidateFrame=frame;}
        var key=(source,flags);
        if(candidates.TryGetValue(key,out var cached))return cached;
        // Peashooters have ray checks, not the area shapes required by FindCatapultTarget.
        TowerDefenseCharacter? target=null;
        for(int i=0;i<source.checkRayResources.Count;i++)
        {
            var hit=FireRayQuery.Check(source,source.checkRayResources[i],flags,i);
            if(Valid(hit)){target=hit;break;}
        }
        if(!Valid(target)&&source.checkShapeResources.Count>0)target=source.FindCatapultTarget(flags,position);
        candidates[key]=target;
        return target;
    }
    void Spawned(int index)
    {
        // Every birth invalidates any old registration at this recycled field slot.
        tracked.Remove(index);
        if(pendingSource==null||pendingStrength<=0||field==null)return;
        ref var bullet=ref field.GetBulletDataRef(index);
        if(!bullet.active||bullet.fireCharacter!=pendingSource.parent||bullet.config.name!=projectile)return;
        var guided=new Guided{Source=pendingSource,Strength=pendingStrength,Speed=bullet.vel.Length()};
        guided.Target=FindTarget(pendingSource,bullet.collisionFlags,bullet.pos);
        tracked[index]=guided;
    }
    public void Tick(double delta)
    {
        if(!GodotObject.IsInstanceValid(field)){tracked.Clear();return;}
        foreach(var pair in tracked.ToArray())
        {
            ref var bullet=ref field!.GetBulletDataRef(pair.Key);
            if(!bullet.active||bullet.over||bullet.config.name!=projectile){tracked.Remove(pair.Key);continue;}
            var guided=pair.Value;
            if(!Valid(guided.Target))
            {
                guided.Target=null;
                if(guided.Source.IsAttached&&GodotObject.IsInstanceValid(guided.Source.parent)&&!guided.Source.parent.die)
                    guided.Target=FindTarget(guided.Source,bullet.collisionFlags,bullet.pos);
            }
            if(!Valid(guided.Target))continue;
            var point=guided.Target!.GetLogicalGlobalPosition();
            var direction=point-bullet.pos;
            if(direction.LengthSquared()<.0001f)continue;
            float angle=(float)WeakGuidanceMath.Turn(bullet.vel.Angle(),direction.Angle(),guided.Strength,delta);
            bullet.vel=Vector2.Right.Rotated(angle)*guided.Speed;
            if(bullet.rotateFollowVelocity)bullet.rotation=angle;
        }
    }
    public void Dispose()
    {
        if(GodotObject.IsInstanceValid(field))field!.OnBulletSpawned-=Spawned;
        tracked.Clear();candidates.Clear();field=null;pendingSource=null;
    }
}
