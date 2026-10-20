using Godot;
using PVZHE.ModEditor.ModSystem;
namespace SuperGatlingPea;
public sealed partial class Entry
{
    bool auditStarted; readonly HashSet<ulong> pausePrompts=new();
    static void Check(bool yes,string why){if(!yes)throw new Exception(why);}
    static async Task Wait(SceneTree t,double seconds)=>await t.ToSignal(t.CreateTimer(seconds,true,false,true),SceneTreeTimer.SignalName.Timeout);
    static async Task Shot(SceneTree t,string name){await t.ToSignal(RenderingServer.Singleton,RenderingServer.SignalName.FramePostDraw);using var im=t.Root.GetTexture().GetImage();Check(im.SavePng("user://audit-"+name+".png")==Error.Ok,"capture");}
    async Task Until(SceneTree t,Func<bool> yes,string why){for(int i=0;i<180;i++){var prompt=Nodes(t.Root).OfType<DialogBoxBase>().FirstOrDefault(d=>d.GetType().Name=="DialogBoxGamePause");if(prompt!=null&&pausePrompts.Add(prompt.GetInstanceId())){Check(pausePrompts.Count<=4,"Repeated environment pause prompts");t.Root.GrabFocus();context.Log("SUPER_ENV_PAUSE: known game pause prompt closed");prompt.CloseDialog();}if(yes())return;await Wait(t,.1);}throw new Exception(why);}
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
            var bank=TowerDefenseManager.Instance.GetSeedBankList();var baseline=bank.Single(p=>p.config.saveKey=="PlantWallnut");
            Check(baseline.Plant(new Vector2I(2,4))!=null,"native control card placement");
            var card=bank.Single(p=>p.config.saveKey==Key("Packet"));long balance=TowerDefenseManager.Instance.GetSun();
            var plant=card.Plant(new Vector2I(2,3));Check(plant!=null,"own card placement");
            Check(balance-TowerDefenseManager.Instance.GetSun()==250,"cost");Check(card.coldDownOpen&&card.coldDownTimer>0,"cooldown");
            await Until(t,()=>bursts.ContainsKey(plant!.GetInstanceId()),"runtime controller");
            var controller=bursts[plant!.GetInstanceId()];controller.Automatic=false;
            var body=plant.GetNode<AdobeAnimateSprite>("SpriteGroup/TransformPoint/PeaShooterSingle");
            var head=body.GetNode<AdobeAnimateSprite>("Head");
            Check(body.forceLocalRender&&head.forceLocalRender,"runtime local drawing was not applied after instancing");
            Check(head.parentSprite==body,"head parent binding");
            Check(head.followParentSpriteLayerId==16&&head.insertLayerId==16,"source stem layer identity");
            Check(head.offset.DistanceTo(new Vector2(-37.6f,-48.7f))<.001f,"source reference inverse");
            Check(body.clipRange==new Vector2I(0,25)&&head.clipRange==new Vector2I(25,50),"half-open idle ranges");
            var positions=new List<Vector2>();var powerFrames=new HashSet<int>();
            var fireFrames=new HashSet<int>();int completed=0;double duration=0,startedAt=0;bool observePower=false;
            void Collect(){
                positions.Add(head.Position);
                if(head.clip=="HeadFire")fireFrames.Add(head.frameIndex);
                if(observePower&&head.clip=="HeadPower"){
                    powerFrames.Add(head.frameIndex);Check(Math.Abs(head.timeScale-1)<.001,"power inherited fire speed");
                }
            }
            void Completed(string clip){if(clip=="HeadPower"&&observePower){completed++;duration=Time.GetTicksMsec()/1000.0-startedAt;}}
            t.PhysicsFrame+=Collect;head.OnAnimeCompleted+=Completed;
            async Task Sequence(string label,int count){
                for(int i=0;i<count;i++){
                    context.Log("SUPER_ANIMATION_SAMPLE: "+label+" i="+i+" body="+body.frameIndex+" head="+head.clip+"/"+head.frameIndex+" position="+head.Position+" speed="+head.timeScale);
                    await Shot(t,"animation-"+label+"-"+i.ToString("D2"));await Wait(t,.12);
                }
            }
            await Sequence("idle",20);
            (float X,float Y) Span(){
                float minX=float.MaxValue,minY=float.MaxValue,maxX=float.MinValue,maxY=float.MinValue;
                foreach(var p in positions){minX=Math.Min(minX,p.X);maxX=Math.Max(maxX,p.X);minY=Math.Min(minY,p.Y);maxY=Math.Max(maxY,p.Y);}
                return(maxX-minX,maxY-minY);
            }
            var span=Span();float xSpan=span.X,ySpan=span.Y;
            Check(xSpan>5&&ySpan>3,"head did not follow moving stem");
            context.Log("SUPER_ANIMATION_IDLE_PASS: head span="+xSpan+","+ySpan+"; source-bound parent and reference");
            positions.Clear();head.followParentSpriteLayerId=-1;head.insertLayerId=-1;
            await Sequence("negative-detached",10);
            var detached=Span();Check(detached.X<.01&&detached.Y<.01,"detached negative control unexpectedly moved");
            head.followParentSpriteLayerId=16;head.insertLayerId=16;positions.Clear();
            context.Log("SUPER_ANIMATION_NEGATIVE_PASS: same plant without attachment would fail motion assertion");
            var enemy=await context.Game.Characters.SpawnAsync("ZombieNormalBucket",7,3);Check(enemy.Succeeded,enemy.Diagnostic);
            await Sequence("fire",24);
            Check(fireFrames.Any(f=>f>=50&&f<=54)&&fireFrames.Any(f=>f>=70&&f<75),"shooting beginning/end not observed");
            await Until(t,()=>head.clip=="HeadIdle","attack finished before power");
            context.Log("SUPER_ANIMATION_FIRE_PASS: shooting motion and return-to-idle observed");
            observePower=true;startedAt=Time.GetTicksMsec()/1000.0;controller.Begin();
            await Sequence("power",12);
            Check(powerFrames.Contains(75)&&powerFrames.Contains(86),"power start/final source frame not shown");
            Check(completed==1&&duration>=.9&&duration<=1.2,"power completion duration="+duration+" count="+completed);
            Check(head.clip=="HeadIdle"&&head.loop,"power did not return to looping idle");
            Check(plant.componentManager.GetRuntime<FireComponent>().alive,"native fire not restored after power");
            Check(controller.Requests==300,"power projectile budget");
            context.Log("SUPER_ANIMATION_POWER_PASS: frames75..86 duration="+duration+" completed once; idle restored");
            t.PhysicsFrame-=Collect;head.OnAnimeCompleted-=Completed;
            SceneManager.Instance.ChangeScene("MainMenu");await Until(t,()=>t.CurrentScene is MainMenu&&!SceneManager.Instance.isLoading,"return");Check(bursts.Count==0,"runtime residue");
            context.Log("AUDIT_DISCOVERY_DONE: super plant core");t.Quit();
        }
        catch(Exception e){context.Log("AUDIT_TEST_ERROR: "+e);await Shot(t,"super-failed");t.Quit(2);}
    }
}
