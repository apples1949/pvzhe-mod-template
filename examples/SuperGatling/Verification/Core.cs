using Godot;
using PVZHE.ModEditor.ModSystem;
namespace SuperGatlingPea;
public sealed partial class Entry
{
    bool auditStarted; readonly HashSet<ulong> pausePrompts=new(); int shots,hits; readonly List<double> times=new();
    static void Check(bool yes,string why){if(!yes)throw new Exception(why);}
    static async Task Wait(SceneTree t,double seconds)=>await t.ToSignal(t.CreateTimer(seconds,true,false,true),SceneTreeTimer.SignalName.Timeout);
    static async Task Shot(SceneTree t,string name){await t.ToSignal(RenderingServer.Singleton,RenderingServer.SignalName.FramePostDraw);using var im=t.Root.GetTexture().GetImage();Check(im.SavePng("user://audit-"+name+".png")==Error.Ok,"capture");}
    async Task Until(SceneTree t,Func<bool> yes,string why){for(int i=0;i<180;i++){var prompt=Nodes(t.Root).OfType<DialogBoxBase>().FirstOrDefault(d=>d.GetType().Name=="DialogBoxGamePause");if(prompt!=null&&pausePrompts.Add(prompt.GetInstanceId())){Check(pausePrompts.Count<=4,"Repeated environment pause prompts");t.Root.GrabFocus();context.Log("SUPER_ENV_PAUSE: known game pause prompt closed");prompt.CloseDialog();}if(yes())return;await Wait(t,.1);}throw new Exception(why);}
    partial void ConfigureVerification()
    {
        if(!OS.GetCmdlineUserArgs().Contains("--skill-audit"))return;
        context.Lifetime.Track(context.Hooks.Modify(XWModCharacterPoints.ProjectileLaunch,"super.audit.launch",(_,e)=>{if(e.ProjectileKey==Key("Projectile","SuperPea")){shots++;times.Add(Time.GetTicksMsec()/1000.0);}return e;}));
        context.Lifetime.Track(context.Hooks.Subscribe(XWModCharacterPoints.ProjectileHit,"super.audit.hit",(_,e)=>{if(e.ProjectileKey==Key("Projectile","SuperPea"))hits++;}));
    }
    partial void StartVerification(SceneTree tree){var t=tree;if(auditStarted||!OS.GetCmdlineUserArgs().Contains("--skill-audit"))return;auditStarted=true;Run(t);}
    async void Run(SceneTree t)
    {
        try
        {
            await Until(t,()=>Nodes(t.Root).OfType<DialogBoxNewUser>().Any(d=>d.nameLineEdit!=null),"new user readiness");
            var profile=Nodes(t.Root).OfType<DialogBoxNewUser>().Single();profile.nameLineEdit.Text="SuperAudit";profile.readyButtonNewUser.EmitSignal(BaseButton.SignalName.Pressed);
            await Until(t,()=>GameSaveManager.Instance.GetUserCurrent()=="SuperAudit"&&!DialogManager.Instance.HasOpenDialogs&&!SceneManager.Instance.isLoading,"profile committed");
            level.Launch();
            await Until(t,()=>context.Game.TryGetBattle(out var b)&&b.Running&&!b.Paused&&!t.Paused&&!SceneManager.Instance.isLoading,"battle running");
            Check(TowerDefenseManager.GetMapFeature()?.currentMap!=null,"map missing");
            var preview=ResourceManager.Instance.GetCharacterSprite(Key("CharacterSprite")).Instantiate<AdobeAnimateSprite>();
            try { Check(preview.GetNode<AdobeAnimateSprite>("Head").parentSprite==preview,"preview points at external parent"); }
            finally { preview.Free(); }
            context.Log("SUPER_PREVIEW_PASS: packed preview head references its own body");
            var bank=TowerDefenseManager.Instance.GetSeedBankList();var baseline=bank.Single(p=>p.config.saveKey=="PlantWallnut");
            Check(baseline.Plant(new Vector2I(2,4))!=null,"native control card placement");
            var card=bank.Single(p=>p.config.saveKey==Key("Packet"));long balance=TowerDefenseManager.Instance.GetSun();
            var plant=card.Plant(new Vector2I(2,3));Check(plant!=null,"own card placement");
            Check(balance-TowerDefenseManager.Instance.GetSun()==250,"cost");Check(card.coldDownOpen&&card.coldDownTimer>0,"cooldown");
            await Until(t,()=>bursts.ContainsKey(plant!.GetInstanceId()),"runtime controller");
            var controller=bursts[plant!.GetInstanceId()];controller.Automatic=false;
            var muzzle=plant.GetNode<Marker2D>("SpriteGroup/TransformPoint/PeaShooterSingle/Head/SuperMuzzle/FirePoint");
            if(OS.GetCmdlineUserArgs().Contains("--power-death-only")) {
                ulong plantId=plant.GetInstanceId();int deathStart=controller.Requests;
                controller.Begin();await Wait(t,.1);
                Check(context.Game.Characters.TryGetHandle(plant,out var handle),"death handle");
                var death=await context.Game.Combat.Damage(handle,100000);Check(death.Succeeded,death.Diagnostic);
                await Until(t,()=>!bursts.ContainsKey(plantId),"dead power controller removed");
                int stopped=controller.Requests;await Wait(t,.6);
                Check(controller.Requests==stopped&&stopped-deathStart>0&&stopped-deathStart<300,"power continued after death");
                context.Log("SUPER_POWER_DEATH_PASS: emitted="+(stopped-deathStart)+"; pending shots cancelled");
                context.Log("AUDIT_DISCOVERY_DONE: power death only");t.Quit();return;
            }
            var slot=(AdobeAnimateSlot)muzzle.GetParent();
            Check(slot.followSlotId==19,"mouth layer slot identity");
            var muzzleOrigins=new List<Vector2>();var jitters=new List<float>();var powerAngles=new List<float>();var powerTimes=new List<double>();double powerClock=0;bool observePower=false;
            // Expectations come from the confirmed six groups and explicit cadence,
            // independently of the compiled runtime asset.
            var expectedPower=new List<(double Time,float Angle,int Order)>();
            for(int round=0;round<10;round++)for(int group=0;group<6;group++)for(int item=0;item<5;item++)
                expectedPower.Add((Math.Round(round*.1+(group%3)*.25,9),(group%3==0?-22.5f:-45f)+item*11.25f,expectedPower.Count));
            expectedPower.Sort((a,b)=>{int compare=a.Time.CompareTo(b.Time);return compare!=0?compare:a.Order.CompareTo(b.Order);});
            void Spawned(int index){
                ref var bullet=ref BulletField.Instance.GetBulletDataRef(index);
                if(bullet.config.name!=Key("Projectile","SuperPea"))return;
                if(observePower&&!controller.IsScheduling)return;
                var expected=plant.GetLogicalGlobalPosition(muzzle);
                Check(bullet.pos.DistanceTo(expected)<.01f,"actual bullet origin differs from live muzzle: "+bullet.pos+" / "+expected);
                if(observePower) {
                    int shotIndex=powerAngles.Count;
                    float expectedAngle=expectedPower[shotIndex].Angle;
                    Check(!plant.componentManager.GetRuntime<FireComponent>().alive,"ordinary fire resumed before delayed power tail ended");
                    var expectedVelocity=Vector2.Right.Rotated(Mathf.DegToRad(expectedAngle))*300;
                    Check(bullet.vel.DistanceTo(expectedVelocity)<.01f,"confirmed angle mismatch: "+shotIndex+" "+bullet.vel);
                    var offset=muzzle.GlobalPosition-muzzle.GetParent<Node2D>().GlobalPosition;
                    Check(offset.DistanceTo(new Vector2(-1.8394775f,2.8001099f))<.01f,"confirmed muzzle pixel offset mismatch: "+offset);
                    powerAngles.Add(Mathf.RadToDeg(bullet.vel.Angle()));powerTimes.Add(powerClock);
                } else Check(bullet.vel.DistanceTo(new Vector2(300,0))<.01f,"normal projectile is not horizontal: "+bullet.vel);
                muzzleOrigins.Add(muzzle.GlobalPosition);
                if(observePower)jitters.Add(muzzle.Position.Y);
                if(muzzleOrigins.Count<=14)context.Log("SUPER_MUZZLE_SAMPLE: pos="+bullet.pos+" screen="+muzzle.GetGlobalTransformWithCanvas().Origin+" vel="+bullet.vel);
            }
            void Clock(){if(observePower&&!t.Paused&&context.Game.TryGetBattle(out var b)&&!b.Paused)powerClock+=t.Root.GetPhysicsProcessDeltaTime();}
            t.PhysicsFrame+=Clock;
            BulletField.Instance.OnBulletSpawned+=Spawned;
            if(!OS.GetCmdlineUserArgs().Contains("--power-cadence-only")) {
            Check(plant.instance.hitpoints==1000,"health");context.Log("SUPER_CARD_PASS: native control + own card cost250 cooldown30 hp1000");await Shot(t,"super-planted");
            var adjacent=await context.Game.Characters.SpawnAsync("ZombieNormal",7,4);Check(adjacent.Succeeded,adjacent.Diagnostic);
            await Wait(t,2.4);Check(shots==0,"unexpected target on another row");
            var target=await context.Game.Characters.SpawnAsync("ZombieNormalBucket",7,3);Check(target.Succeeded,target.Diagnostic);
            await Until(t,()=>shots>=14&&hits>0,"normal attacks and hits");
            Check(times.Count==14&&times[7]-times[6]>.5,"two distinct seven-shot groups");
            for(int i=1;i<14;i++)if(i!=7)Check(times[i]-times[i-1]<.5,"within-group shot gap");
            Check(times[7]-times[0]>=1.8&&times[7]-times[0]<=2.3,"actual attack period outside 2s tolerance");
            context.Log("SUPER_NORMAL: shots="+shots+" hits="+hits+" times="+string.Join(",",times));await Shot(t,"super-firing");
            await Until(t,()=>plant.GetNode<AdobeAnimateSprite>("SpriteGroup/TransformPoint/PeaShooterSingle/Head").clip=="HeadIdle","fire completion before power");
            Check(muzzleOrigins.Count==14,"normal muzzle samples");
            context.Log("SUPER_MUZZLE_PASS: normal14 actual origins equal moving mouth marker; horizontal velocity300");
            }
            int before=controller.Requests;int launchesBefore=shots;observePower=true;controller.Begin();await Wait(t,.15);await Shot(t,"super-power-early");TowerDefenseManager.Instance.currentControl.buttonPause.ButtonPressed=true;
            await Until(t,()=>Nodes(t.Root).OfType<DialogBoxBase>().Any(d=>d.GetType().Name=="DialogBattlePause")&&context.Game.TryGetBattle(out var b)&&b.Paused,"actual battle pause");
            int paused=controller.Requests;await Wait(t,.6);Check(controller.Requests==paused,"burst advanced while paused");
            Nodes(t.Root).OfType<DialogBoxBase>().Single(d=>d.GetType().Name=="DialogBattlePause").CloseDialog();
            await Until(t,()=>context.Game.TryGetBattle(out var b)&&!b.Paused&&!t.Paused,"actual battle resume");
            await Until(t,()=>controller.Requests-before==300,"power 300 overlapping rounds");
            context.Log("SUPER_POWER_TIMING_RAW: times="+string.Join(",",powerTimes));
            Check(powerAngles.Count==300,"actual power launch events missing: "+powerAngles.Count);context.Log("SUPER_POWER_PASS: requests300 actualLaunches="+powerAngles.Count+"; paused generation stopped");observePower=false;await Shot(t,"super-power");
            await Until(t,()=>plant.GetNode<AdobeAnimateSprite>("SpriteGroup/TransformPoint/PeaShooterSingle/Head").clip=="HeadIdle"&&plant.componentManager.GetRuntime<FireComponent>().alive,"power restores native fire and idle");
            Check(powerAngles.Count==300,"power launch samples missing");
            for(int index=0;index<300;index++) {
                double intended=expectedPower[index].Time;
                Check(Math.Abs((powerTimes[index]-powerTimes[0])-intended)<.05,"confirmed shot time mismatch: "+index+" "+powerTimes[index]);
            }
            Check(muzzle.Position==Vector2.Zero,"temporary muzzle adjustment leaked");
            context.Log("SUPER_TRAJECTORY_PASS: confirmed300; interval0.1/window1/tail1.4; angles="+string.Join(",",powerAngles)+"; times="+string.Join(",",powerTimes)+"; pixel offset and marker restored");
            t.PhysicsFrame-=Clock;
            BulletField.Instance.OnBulletSpawned-=Spawned;
            SceneManager.Instance.ChangeScene("MainMenu");await Until(t,()=>t.CurrentScene is MainMenu&&!SceneManager.Instance.isLoading,"return");Check(bursts.Count==0,"runtime residue");
            context.Log("AUDIT_DISCOVERY_DONE: super plant core");t.Quit();
        }
        catch(Exception e){context.Log("AUDIT_TEST_ERROR: "+e);await Shot(t,"super-failed");t.Quit(2);}
    }
}
