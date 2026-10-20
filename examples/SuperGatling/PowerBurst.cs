using Godot;
using PVZHE.ModEditor.ModSystem;

namespace SuperGatlingPea;

public sealed class PowerBurst : IDisposable
{
    readonly XWModRuntimeContext context;
    readonly TowerDefenseCharacter plant;
    readonly FireComponent fire;
    readonly string projectile;
    readonly Marker2D muzzle;
    readonly PowerPattern pattern;
    readonly PowerGuidance guidance;
    int attacks, serial, next;
    bool firing;
    double elapsed;
    bool pending, animationPlaying, restoreFire;
    internal bool Automatic { get; set; } = true;
    public bool IsValid => GodotObject.IsInstanceValid(plant) && plant.IsInsideTree() && !plant.die;
    public int Requests { get; private set; }
    internal bool IsScheduling => firing;
    public PowerBurst(XWModRuntimeContext context, TowerDefenseCharacter plant, FireComponent fire, string projectile, PowerPattern pattern, PowerGuidance guidance)
    {
        this.context = context; this.plant = plant; this.fire = fire; this.projectile = projectile; this.pattern = pattern; this.guidance = guidance;
        muzzle = plant.GetNode<Marker2D>("SpriteGroup/TransformPoint/PeaShooterSingle/Head/SuperMuzzle/FirePoint");
        fire.OnFireOver += AttackFinished;
        fire.sprite.OnAnimeCompleted += AnimationCompleted;
    }
    void AttackFinished()
    {
        if (!Automatic || !IsValid || plant.GetTree().Paused || Global.IsMultiplayerMode) return;
        // Let FireComponent finish its state/idle transition before taking over
        // the same head sprite on the next battle tick.
        if (context.Game.Random.Unit((ulong)plant.GetInstanceId(), "super.power", (ulong)++attacks) < .1) pending = true;
    }
    internal void Begin()
    {
        if (!IsValid || firing || animationPlaying) return;
        serial++; next = 0; elapsed = 0; firing = true;
        if (fire.sprite?.HasClip("HeadPower") == true)
        {
            // The native idle/attack state also writes this sprite. Suspend
            // automatic fire for the special action, while keeping its muzzle
            // and projectile creation service available to the burst.
            restoreFire = fire.alive;
            fire.alive = false;
            animationPlaying = true;
            fire.sprite.timeScale = 1;
            fire.sprite.SetAnimation("HeadPower", false, blendTime: 0);
        }
        context.Log("SUPER_POWER_BEGIN: " + serial + " roundInterval=" + pattern.RoundIntervalSeconds + " rounds=" + pattern.RoundCount);
    }
    void AnimationCompleted(string clip)
    {
        if (clip != "HeadPower" || !animationPlaying || !IsValid) return;
        animationPlaying = false;
        fire.sprite.timeScale = 1;
        fire.sprite.SetAnimation("HeadIdle", true, blendTime: 0);
        RestoreWhenFinished();
        context.Log("SUPER_POWER_ANIMATION_END: " + serial);
    }
    public void Tick(double delta)
    {
        if (pending) { pending = false; Begin(); }
        if (!firing) return;
        elapsed += delta;
        while (next < pattern.Shots.Length && pattern.Shots[next].Time <= elapsed + 1e-9)
        {
            var shot = pattern.Shots[next++];
            var original = muzzle.Position;
            try
            {
                // Pixel offset is relative to the live animated muzzle, not a frozen plant origin.
                var parent = muzzle.GetParent<Node2D>();
                muzzle.Position = parent.ToLocal(muzzle.GlobalPosition + shot.Offset);
                guidance.Launch(fire,shot.TrackingStrength,()=>fire.CreateProjectileByName(0, shot.Velocity, projectile, -1, TowerDefenseEnum.CHARACTER_CAMP.PLANT, Vector2.Zero, "Default", default));
            }
            finally { muzzle.Position = original; }
            Requests++;
        }
        if (next == pattern.Shots.Length)
        {
            firing = false;
            RestoreWhenFinished();
            context.Log("SUPER_POWER_END: requestsTotal=" + Requests);
        }
    }
    void RestoreWhenFinished()
    {
        if (!firing && !animationPlaying && restoreFire && IsValid && fire.IsAttached)
        { restoreFire = false; fire.alive = true; }
    }
    public void Dispose()
    {
        firing = false; pending = animationPlaying = false;
        if (restoreFire && IsValid && fire.IsAttached) fire.alive = true;
        restoreFire = false;
        if (fire.IsAttached) fire.OnFireOver -= AttackFinished;
        if (GodotObject.IsInstanceValid(fire.sprite)) fire.sprite.OnAnimeCompleted -= AnimationCompleted;
    }
}
