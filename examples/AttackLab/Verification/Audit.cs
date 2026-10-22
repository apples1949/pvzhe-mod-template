using Godot;
using PVZHE.ModEditor.ModSystem;
using D=Godot.Collections.Dictionary;
namespace AttackLab;

public sealed partial class Entry
{
    bool auditStarted;int hits;readonly HashSet<ulong> prompts=new();
    static void Check(bool yes,string reason){if(!yes)throw new Exception(reason);}
    static async Task Wait(SceneTree tree,double seconds)=>await tree.ToSignal(tree.CreateTimer(seconds,true,false,true),SceneTreeTimer.SignalName.Timeout);
    async Task Until(SceneTree tree,Func<bool> test,string reason)
    {
        for(int i=0;i<300;i++)
        {
            var prompt=Nodes(tree.Root).OfType<DialogBoxBase>().FirstOrDefault(n=>n.GetType().Name=="DialogBoxGamePause");
            if(prompt!=null&&prompts.Add(prompt.GetInstanceId())){Check(prompts.Count<6,"Repeated environment pauses");tree.Root.GrabFocus();prompt.CloseDialog();}
            if(test())return;await Wait(tree,.05);
        }
        throw new Exception("Readiness: "+reason);
    }
    static async Task Screenshot(SceneTree tree,string name)
    {
        await tree.ToSignal(RenderingServer.Singleton,RenderingServer.SignalName.FramePostDraw);
        using var image=tree.Root.GetTexture().GetImage();Check(image.SavePng("user://attack-lab-"+name+".png")==Error.Ok,"Screenshot write");
    }
    partial void ConfigureAudit()
    {
        context.Lifetime.Track(context.Hooks.Subscribe(XWModPresentationPoints.MainMenu,"attack.lab.audit",(_,s)=>StartAudit(s.Root.GetTree())));
        context.Lifetime.Track(context.Hooks.Subscribe(XWModCharacterPoints.ProjectileHit,"attack.lab.hits",(_,e)=>{if(e.ProjectileKey.Contains("local.attack-lab"))hits++;}));
    }
    partial void StartAudit(SceneTree tree)
    {
        if(auditStarted||!OS.GetCmdlineUserArgs().Contains("--attack-lab-audit"))return;
        auditStarted=true;RunAudit(tree);
    }
    async void RunAudit(SceneTree tree)
    {
        try
        {
            await Until(tree,()=>Nodes(tree.Root).OfType<DialogBoxNewUser>().Any(n=>n.nameLineEdit!=null),"new user");
            var profile=Nodes(tree.Root).OfType<DialogBoxNewUser>().Single();profile.nameLineEdit.Text="AttackLabAudit";profile.readyButtonNewUser.EmitSignal(BaseButton.SignalName.Pressed);
            await Until(tree,()=>GameSaveManager.Instance.GetUserCurrent()=="AttackLabAudit"&&!DialogManager.Instance.HasOpenDialogs&&!SceneManager.Instance.isLoading,"profile");
            // Isolated test profile only: focus changes from evidence inspection must not open environment pauses.
            GameSaveManager.Instance.SetConfigValue("Backgrounder",true);
            context.Log("ATTACK_LAB_ENVIRONMENT: isolated Backgrounder=true; explicit in-game pause still tested");
            if(OS.GetCmdlineUserArgs().Contains("--boundaries")){await RunBoundaries(tree);context.Log("ATTACK_LAB_BOUNDARIES_CAPTURED: offline business judgement required");tree.Quit();return;}
            var selected=OS.GetCmdlineUserArgs().Contains("--only-fan")?new[]{"fan"}:OS.GetCmdlineUserArgs().Contains("--only-homing")?new[]{"homing"}:OS.GetCmdlineUserArgs().Contains("--only-nested")?new[]{"nested"}:OS.GetCmdlineUserArgs().Contains("--second-half")?Cases.Skip(4):Cases.Take(4);
            var only=OS.GetCmdlineUserArgs().FirstOrDefault(a=>a.StartsWith("--only-case="))?.Split('=',2)[1];
            if(only!=null){Check(selected.Contains(only),"Invalid case selection");selected=new[]{only};}
            foreach(var key in selected)
            {
                Launch(key);
                await Until(tree,()=>context.Game.TryGetBattle(out var b)&&b.Running&&!b.Paused&&!tree.Paused&&!SceneManager.Instance.isLoading,"battle "+key);
                Engine.TimeScale=1;
                var spawned=await context.Game.Characters.SpawnAsync("ZombieNormal",6,3);Check(spawned.Succeeded,spawned.Diagnostic);
                var target=Nodes(tree.Root).OfType<TowerDefenseCharacter>().Single(n=>context.Game.Characters.TryGetHandle(n,out var handle)&&handle.Equals(spawned.Value));target.instance.hitpoints=1000000;
                hits=0;
                var card=TowerDefenseManager.Instance.GetSeedBankList().Single(p=>p.config.saveKey=="PlantPeaShooterSingle");
                var plant=card.Plant(new Vector2I(2,3));Check(plant!=null,"Native seed planting");
                if(key=="starfruit")target.SetLogicalGlobalPosition(plant!.GetLogicalGlobalPosition()+new Vector2(270,-156));
                await Until(tree,()=>active?.Plant==plant,"plan controller");var runner=active!;runner.EmissionUntil=2.4;runner.TraceMotion=key is "nested" or "fan" or "ring" or "straight";
                var targetBase=target.GetLogicalGlobalPosition();
                void Move(){if(key=="homing"&&!tree.Paused&&!target.die)target.SetLogicalGlobalPosition(targetBase+new Vector2(0,(float)Math.Sin(runner.Clock*2)*35));}
                tree.PhysicsFrame+=Move;
                await Until(tree,()=>runner.Clock>=.55,"first motion samples");
                if(key=="fan")
                {
                    TowerDefenseManager.Instance.currentControl.buttonPause.ButtonPressed=true;
                    await Until(tree,()=>context.Game.TryGetBattle(out var b)&&b.Paused,"real pause");
                    int births=runner.Births.Count;double clock=runner.Clock;await Wait(tree,.35);
                    Check(runner.Births.Count==births&&runner.Clock==clock,"Schedule advanced while paused");
                    Nodes(tree.Root).OfType<DialogBoxBase>().Single(n=>n.GetType().Name=="DialogBattlePause").CloseDialog();
                    await Until(tree,()=>!tree.Paused&&context.Game.TryGetBattle(out var b)&&!b.Paused,"resume");context.Log("ATTACK_LAB_PAUSE_PASS: schedule and clock frozen");
                }
                await Screenshot(tree,key+"-motion");
                await Until(tree,()=>runner.Clock>=3.35,"tail emissions "+key);
                if(key!="straight"&&key!="ring")await Until(tree,()=>hits>0&&target.instance.hitpoints<1000000,"real hit and HP "+key);
                if(key=="straight")Check(runner.RangeRemoved>0&&hits==0,"Fractional range failed or unintended distant hit");
                if(key=="parallel")Check(runner.DeploymentSamples>0,"No deployment");
                int observedHits=hits;double observedHP=target.instance.hitpoints;int afterDeathSamples=0;
                if(key=="homing")
                {
                    Check(runner.GuidanceSamples>0,"No guidance");
                    var added=await context.Game.Characters.SpawnAsync("PlantPeaShooterSingle",3,3);Check(added.Succeeded,added.Diagnostic);
                    await Until(tree,()=>active!=null&&active!=runner&&active.Clock>=.07,"second source with pending shots");var auxiliary=active!;
                    var damage=await context.Game.Combat.Damage(added.Value,100000);Check(damage.Succeeded,damage.Diagnostic);
                    int count=auxiliary.Births.Count;Check(count>0,"No airborne auxiliary shots");
                    await Wait(tree,.8);Check(count==auxiliary.Births.Count,"Dead source emitted pending/future shots");
                    Check(auxiliary.SourceDeadSamples>0,"Airborne processing stopped with owner");afterDeathSamples=auxiliary.SourceDeadSamples;
                    context.Log("ATTACK_LAB_OWNER_PASS: pending/future cancelled before scheduled tails; airborne samples="+afterDeathSamples);
                }
                tree.PhysicsFrame-=Move;
                var birthsData=new Godot.Collections.Array();
                foreach(var b in runner.Births)birthsData.Add(new D{{"group",b.Group},{"item",b.Item},{"generation",b.Generation},{"intended",b.Intended},{"actual",b.Actual},{"root",new Godot.Collections.Array{b.Root.X,b.Root.Y}},{"position",new Godot.Collections.Array{b.Position.X,b.Position.Y}},{"velocity",new Godot.Collections.Array{b.Velocity.X,b.Velocity.Y}},{"target",new Godot.Collections.Array{b.Target.X,b.Target.Y}},{"flightTime",b.FlightTime},{"z",b.Z},{"ySpeed",b.YSpeed}});
                var result=new D{{"case",key},{"physicsTicksPerSecond",Engine.PhysicsTicksPerSecond},{"births",birthsData},{"samples",runner.Samples},{"terminals",runner.Terminals},{"ranges",runner.Ranges},{"hits",observedHits},{"targetHP",observedHP},{"afterDeathSamples",afterDeathSamples},{"deploymentSamples",runner.DeploymentSamples},{"guidanceSamples",runner.GuidanceSamples},{"gridSize",new Godot.Collections.Array{TowerDefenseManager.Instance.GetMapGridSize().X,TowerDefenseManager.Instance.GetMapGridSize().Y}}};
                using(var file=Godot.FileAccess.Open("user://attack-lab-"+key+".json",Godot.FileAccess.ModeFlags.Write))file.StoreString(Json.Stringify(result));
                if(runner.TraceMotion)using(var trace=Godot.FileAccess.Open("user://motion-trace-"+key+".json",Godot.FileAccess.ModeFlags.Write))trace.StoreString(Json.Stringify(runner.MotionTrace));
                context.Log("ATTACK_LAB_CASE_PASS: "+key+" actualBirths="+runner.Births.Count+" hits="+hits);
                SceneManager.Instance.ChangeScene("MainMenu");
                await Until(tree,()=>tree.CurrentScene is MainMenu&&!SceneManager.Instance.isLoading&&active==null,"scene cleanup "+key);
                Check(runner.ActiveCount==0,"Airborne registrations leaked");
            }
            context.Log("ATTACK_LAB_SUITE_PASS: tested distinct plans and scene cleanup");tree.Quit();
        }
        catch(Exception error){context.Log("AUDIT_TEST_ERROR: "+error);await Screenshot(tree,"failure");tree.Quit(2);}
    }
}
