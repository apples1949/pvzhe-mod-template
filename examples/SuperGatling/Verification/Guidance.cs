using Godot;
using PVZHE.ModEditor.ModSystem;
namespace SuperGatlingPea;
public sealed partial class Entry
{
    int guidedHits;
    partial void ConfigureVerification()
    {
        context.Lifetime.Track(context.Hooks.Subscribe(XWModCharacterPoints.ProjectileHit,"super.audit.guidance-hit",(_,e)=>{if(e.ProjectileKey==Key("Projectile","SuperPea"))guidedHits++;}));
    }
    bool auditStarted; readonly HashSet<ulong> pausePrompts=new();
    static void Check(bool yes,string why){if(!yes)throw new Exception(why);}
    static async Task Wait(SceneTree t,double seconds)=>await t.ToSignal(t.CreateTimer(seconds,true,false,true),SceneTreeTimer.SignalName.Timeout);
    static async Task Shot(SceneTree t,string name){await t.ToSignal(RenderingServer.Singleton,RenderingServer.SignalName.FramePostDraw);using var im=t.Root.GetTexture().GetImage();Check(im.SavePng("user://audit-"+name+".png")==Error.Ok,"capture");}
    async Task Until(SceneTree t,Func<bool> yes,string why){for(int i=0;i<180;i++){var prompt=Nodes(t.Root).OfType<DialogBoxBase>().FirstOrDefault(d=>d.GetType().Name=="DialogBoxGamePause");if(prompt!=null&&pausePrompts.Add(prompt.GetInstanceId())){Check(pausePrompts.Count<=4,"Repeated environment pause prompts");t.Root.GrabFocus();context.Log("SUPER_ENV_PAUSE: known game pause prompt closed");prompt.CloseDialog();}if(yes())return;await Wait(t,.1);}throw new Exception(why);}
    partial void StartVerification(SceneTree tree){var t=tree;if(auditStarted||!OS.GetCmdlineUserArgs().Contains("--skill-audit"))return;auditStarted=true;Run(t);}
    async void Run(SceneTree t){try{
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
            var manager=activeGuidance ?? throw new Exception("guidance manager missing");
            var field=BulletField.EnsureMountedOnCharacterNode();
            var targetResult=await context.Game.Characters.SpawnAsync("ZombieNormalBucket",8,3);Check(targetResult.Succeeded,targetResult.Diagnostic);
            var zombie=Nodes(t.Root).OfType<TowerDefenseCharacter>().Single(n=>context.Game.Characters.TryGetHandle(n,out var h)&&h.Equals(targetResult.Value));
            zombie.instance.hitpoints=1000000;
            int normalIndex=-1,first=-1;Vector2 born=default;bool power=false;var samples=new List<float>();var ordinary=new List<int>();
            void Spawned(int index){ref var bullet=ref field.GetBulletDataRef(index);if(bullet.fireCharacter!=plant)return;if(power){if(first<0){first=index;born=bullet.vel;}}else {ordinary.Add(index);if(normalIndex<0)normalIndex=index;}}
            field.OnBulletSpawned+=Spawned;
            await Until(t,()=>normalIndex>=0,"ordinary bullet");await Wait(t,.12);
            Check(field.GetBulletDataRef(normalIndex).vel.DistanceTo(new Vector2(300,0))<.01f,"ordinary bullet acquired guidance");
            Check(manager.TrackedCount==0,"ordinary shot was registered");
            var fire=plant.componentManager.GetRuntime<FireComponent>();fire.alive=false;
            // Remove control ammunition so it cannot satisfy the later guided-hit assertion.
            foreach(int index in ordinary)field.GetBulletDataRef(index).over=true;
            guidedHits=0;
            power=true;controller.Begin();
            await Until(t,()=>first>=0,"first guided bullet");
            Check(Math.Abs(Mathf.RadToDeg(born.Angle())+22.5f)<.01,"fan birth direction changed");
            var baseTarget=zombie.GetLogicalGlobalPosition();double clock=0;
            void Observe(){
                if(t.Paused||!context.Game.TryGetBattle(out var battle)||battle.Paused)return;
                clock+=t.Root.GetPhysicsProcessDeltaTime();
                if(GodotObject.IsInstanceValid(zombie))zombie.SetLogicalGlobalPosition(baseTarget+new Vector2(0,(float)Math.Sin(clock*3)*20));
                ref var bullet=ref field.GetBulletDataRef(first);
                if(!bullet.active)return;
                Check(!bullet.trackOpen,"native snap tracking was enabled");
                Check(Math.Abs(bullet.vel.Length()-300)<.05,"guidance changed speed");
                float angle=bullet.vel.Angle();
                if(samples.Count>0)Check(Math.Abs(Mathf.Wrap(angle-samples[^1],-Mathf.Pi,Mathf.Pi))<=Mathf.DegToRad((float)(120*t.Root.GetPhysicsProcessDeltaTime()))+.002f,"weak turn exceeded 120 degrees/sec");
                if(samples.Count<4)context.Log("SUPER_GUIDANCE_SAMPLE: "+manager.Describe(first)+" count="+manager.TrackedCount+" flags="+bullet.collisionFlags+" targetCheck="+zombie.targetRegistrationComponent?.canProjectileCheck+" candidate="+GodotObject.IsInstanceValid(fire.FindCatapultTarget(-1,bullet.pos))+" velocity="+bullet.vel);
                samples.Add(angle);
            }
            t.PhysicsFrame+=Observe;
            await Wait(t,.15);
            Check(samples.Count>=3&&Math.Abs(samples[^1]-born.Angle())>.01,"projectile never turned");
            var guidedNow=field.GetBulletDataRef(first);
            float residual=Math.Abs(Mathf.Wrap((zombie.GetLogicalGlobalPosition()-guidedNow.pos).Angle()-guidedNow.vel.Angle(),-Mathf.Pi,Mathf.Pi));
            Check(residual>Mathf.DegToRad(1),"weak guidance snapped directly to target");
            await Shot(t,"guidance-curving");
            TowerDefenseManager.Instance.currentControl.buttonPause.ButtonPressed=true;
            await Until(t,()=>context.Game.TryGetBattle(out var battle)&&battle.Paused,"pause");
            var frozen=field.GetBulletDataRef(first);int frozenSamples=samples.Count;
            await Wait(t,.4);var pausedBullet=field.GetBulletDataRef(first);
            Check(pausedBullet.pos.DistanceTo(frozen.pos)<.01f&&pausedBullet.vel.DistanceTo(frozen.vel)<.01f&&samples.Count==frozenSamples,"guidance advanced during pause");
            Nodes(t.Root).OfType<DialogBoxBase>().Single(d=>d.GetType().Name=="DialogBattlePause").CloseDialog();
            await Until(t,()=>context.Game.TryGetBattle(out var battle)&&!battle.Paused&&!t.Paused,"resume");
            ulong plantId=plant.GetInstanceId();Check(context.Game.Characters.TryGetHandle(plant,out var handle),"owner handle");
            var beforeDeath=field.GetBulletDataRef(first).vel;var death=await context.Game.Combat.Damage(handle,100000);Check(death.Succeeded,death.Diagnostic);
            await Until(t,()=>!bursts.ContainsKey(plantId),"dead owner removed");int requests=controller.Requests;
            await Wait(t,.2);
            Check(controller.Requests==requests&&requests<300,"dead owner continued launching");
            Check(manager.TrackedCount>0&&field.GetBulletDataRef(first).active,"existing guided ammunition was cancelled with owner");
            Check(field.GetBulletDataRef(first).vel.DistanceTo(beforeDeath)>.01f,"guidance stopped when owner died");
            t.PhysicsFrame-=Observe;field.OnBulletSpawned-=Spawned;
            // Damage is a separate live-owner case, not implied by continued visual flight after death.
            var secondResult=await context.Game.Characters.SpawnAsync(Key("Character"),2,3);Check(secondResult.Succeeded,secondResult.Diagnostic);
            var second=Nodes(t.Root).OfType<TowerDefenseCharacter>().Single(n=>context.Game.Characters.TryGetHandle(n,out var h)&&h.Equals(secondResult.Value));
            await Until(t,()=>bursts.ContainsKey(second.GetInstanceId()),"second controller");
            var secondController=bursts[second.GetInstanceId()];secondController.Automatic=false;
            second.componentManager.GetRuntime<FireComponent>().alive=false;secondController.Begin();
            await Until(t,()=>guidedHits>0&&zombie.instance.hitpoints<1000000,"guided hit and actual damage");
            context.Log("SUPER_GUIDANCE_PASS: ordinary unaffected; strength1 finite turn; moving target; speed300; pause; owner death cancels only pending launches; samples="+samples.Count+" hits="+guidedHits+" targetHP="+zombie.instance.hitpoints);
            SceneManager.Instance.ChangeScene("MainMenu");await Until(t,()=>t.CurrentScene is MainMenu&&!SceneManager.Instance.isLoading,"menu");
            Check(manager.TrackedCount==0&&activeGuidance==null,"guidance scope leaked");
            context.Log("AUDIT_DISCOVERY_DONE: guidance");t.Quit();
        }catch(Exception error){context.Log("AUDIT_TEST_ERROR: "+error);await Shot(t,"guidance-failed");t.Quit(2);}}
}
