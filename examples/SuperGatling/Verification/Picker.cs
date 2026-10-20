using Godot;
using PVZHE.ModEditor.ModSystem;
namespace SuperGatlingPea;
public sealed partial class Entry
{
    bool auditStarted; readonly HashSet<ulong> pausePrompts=new(); readonly List<double> losses=new();
    static void Check(bool yes,string why){if(!yes)throw new Exception(why);}
    static async Task Wait(SceneTree t,double seconds)=>await t.ToSignal(t.CreateTimer(seconds,true,false,true),SceneTreeTimer.SignalName.Timeout);
    static async Task Shot(SceneTree t,string name){await t.ToSignal(RenderingServer.Singleton,RenderingServer.SignalName.FramePostDraw);using var im=t.Root.GetTexture().GetImage();Check(im.SavePng("user://audit-"+name+".png")==Error.Ok,"capture");}
    async Task Until(SceneTree t,Func<bool> yes,string why){for(int i=0;i<200;i++){var prompt=Nodes(t.Root).OfType<DialogBoxBase>().FirstOrDefault(d=>d.GetType().Name=="DialogBoxGamePause");if(prompt!=null&&pausePrompts.Add(prompt.GetInstanceId())){Check(pausePrompts.Count<=4,"Repeated environment pause prompts");t.Root.GrabFocus();context.Log("SUPER_ENV_PAUSE: known game pause closed");prompt.CloseDialog();}if(yes())return;await Wait(t,.1);}throw new Exception(why);}
    partial void ConfigureVerification(){if(OS.GetCmdlineUserArgs().Contains("--skill-audit"))context.Lifetime.Track(context.Hooks.Subscribe(XWModCharacterPoints.ProjectileHit,"super.audit.hit",(_,e)=>{if(e.ProjectileKey==Key("Projectile","SuperPea"))losses.Add(e.LifeLost);}));}
    partial void StartVerification(SceneTree tree){if(auditStarted||!OS.GetCmdlineUserArgs().Contains("--skill-audit"))return;auditStarted=true;Run(tree);}
    async Task Ready(SceneTree t)=>await Until(t,()=>t.CurrentScene is TowerDefenseControlNew&&context.Game.TryGetBattle(out var b)&&b.Running&&!b.Paused&&!t.Paused&&!SceneManager.Instance.isLoading,"battle actual scene/running");
    async Task Menu(SceneTree t){SceneManager.Instance.ChangeScene("MainMenu");await Until(t,()=>t.CurrentScene is MainMenu&&!SceneManager.Instance.isLoading,"actual main menu");}
    async void Run(SceneTree t)
    {
        try
        {
            await Until(t,()=>Nodes(t.Root).OfType<DialogBoxNewUser>().Any(d=>d.nameLineEdit!=null),"new user");var profile=Nodes(t.Root).OfType<DialogBoxNewUser>().Single();profile.nameLineEdit.Text="SuperPicker";profile.readyButtonNewUser.EmitSignal(BaseButton.SignalName.Pressed);
            await Until(t,()=>GameSaveManager.Instance.GetUserCurrent()=="SuperPicker"&&!DialogManager.Instance.HasOpenDialogs&&!SceneManager.Instance.isLoading,"profile");
            if(!OS.GetCmdlineUserArgs().Contains("--native-only"))
            {
            level.Launch();await Ready(t);
            var feature=TowerDefenseManager.Instance.GetPacketBankFeature();int unlocked=feature.packetBankData.GetUnlockPacket().Count;int slots=TowerDefenseManager.Instance.seedbankPacketMax;
            Check(feature.skipPacketChoose&&unlocked<=slots,"natural auto choose branch");var card=TowerDefenseManager.Instance.GetSeedBankList().Single(p=>p.config.saveKey==Key("Packet"));
            var plant=card.Plant(new Vector2I(2,3));Check(plant!=null,"auto-added native pool card placement");context.Log("SUPER_AUTO_POOL_PASS: unlocked="+unlocked+" slots="+slots+" skip="+feature.skipPacketChoose);await Shot(t,"super-auto-pool");
            await Until(t,()=>bursts.ContainsKey(plant!.GetInstanceId()),"controller");var controller=bursts[plant!.GetInstanceId()];controller.Automatic=false;
            var target=await context.Game.Characters.SpawnAsync("ZombieNormal",7,3);Check(target.Succeeded,target.Diagnostic);await Until(t,()=>losses.Any(x=>Math.Abs(x-20)<.01),"actual20 life damage");context.Log("SUPER_DAMAGE_PASS: lifeLost20");
            ulong plantId=plant.GetInstanceId();controller.Begin();await Wait(t,.1);Check(context.Game.Characters.TryGetHandle(plant,out var handle),"own handle");var death=await context.Game.Combat.Damage(handle,100000);Check(death.Succeeded,death.Diagnostic);
            await Until(t,()=>!bursts.ContainsKey(plantId),"dead controller removal");int stopped=controller.Requests;await Wait(t,.4);Check(controller.Requests==stopped&&stopped<300,"burst continued after death");context.Log("SUPER_DEATH_PASS: pending requests stopped at="+stopped);
            await Menu(t);
            }
            int slotsNative=TowerDefenseManager.Instance?.seedbankPacketMax??7;
            // Explicit isolated-player progress fixture, never production unlock logic.
            var rm=ResourceManager.Instance;var bank=rm.TOWERDEFENSE_PACKETBANKS["GeneralPlant"];var prerequisites=new HashSet<string>();
            foreach(var item in bank.GetPacketList())
            {
                var packet=TowerDefenseManager.GetPacketConfigReadOnly(item.AsString());
                foreach(var condition in packet.unlockCheckList.OfType<UnlockConditionLevelFinishConfig>())
                    if(condition.levelSaveKey!="Unlock")prerequisites.Add(condition.levelSaveKey);
                foreach(string key in prerequisites)GameSaveManager.Instance.SetLevelValue(key,new Godot.Collections.Dictionary{{"Key",new Godot.Collections.Dictionary{{"Finish",1d}}}});
                if(bank.GetUnlockPacket().Count>slotsNative+2)break;
            }
            context.Log("SUPER_PICKER_FIXTURE: simulated completed prerequisites="+string.Join(",",prerequisites)+" unlocked="+bank.GetUnlockPacket().Count);
            if(!OS.GetCmdlineUserArgs().Contains("--native-only"))
            {
            level.Launch();await Until(t,()=>TowerDefenseManager.Instance?.GetPacketBankFeature()?.packetList.Count>0&&!SceneManager.Instance.isLoading,"natural picker");var feature=TowerDefenseManager.Instance.GetPacketBankFeature();
            Check(!feature.skipPacketChoose&&feature.packetBankData.GetUnlockPacket().Count>slotsNative,"natural picker count");feature.CategoryChoose("Gold",true);await Wait(t,.5);
            var own=feature.packetList.Single(p=>p.config.saveKey==Key("Packet"));Check(own.IsVisibleInTree(),"own card not visible in Gold");await Shot(t,"super-gold-picker");feature.PacketChoose(own);await Until(t,()=>feature.packetBank.seedBank.packetNum>0&&feature.packetBank.seedBank.HasPacket(Key("Packet")),"selected card flight completed");feature.RockButtonPressed();await Ready(t);
            var card=TowerDefenseManager.Instance.GetSeedBankList().Single(p=>p.config.saveKey==Key("Packet"));long balance=TowerDefenseManager.Instance.GetSun();Check(card.Plant(new Vector2I(2,3))!=null,"chosen card placement");Check(balance-TowerDefenseManager.Instance.GetSun()==250,"chosen card cost");await Shot(t,"super-chosen-plant");context.Log("SUPER_PICKER_PASS: original GeneralPlant Gold, natural choose, confirm, seed card Plant/cost");
            await Menu(t);Check(bursts.Count==0,"residue");
            }
            GameSaveManager.Instance.SetLevelValue("Level1_11",new Godot.Collections.Dictionary{{"Key",new Godot.Collections.Dictionary{{"Finish",1d}}}});
            XWModLevelSession.Clear();
            ((MainMenu)t.CurrentScene).AdventureButtonPressed();
            await Until(t,()=>t.CurrentScene is LevelChoose&&!SceneManager.Instance.isLoading,"native adventure browser");
            var choose=(LevelChoose)t.CurrentScene;choose.Select(0);
            await Until(t,()=>(int)choose.currentMode==1&&!(choose.tween?.IsRunning()??false),"native chapter transition");
            var entries=choose.currentChapter["Level"].AsGodotArray();int selected=-1;
            for(int i=0;i<entries.Count;i++)if(entries[i].AsGodotDictionary()["SaveKey"].AsString()=="Level1_12")selected=i;
            Check(selected>=0,"original Level1_12 identity");choose.Select(selected);
            await Until(t,()=>t.CurrentScene is TowerDefenseControlNew&&!SceneManager.Instance.isLoading&&TowerDefenseManager.Instance.GetPacketBankFeature()?.packetList.Count>0,"native level picker");
            Check(TowerDefenseManager.Instance.currentLevelConfig.name=="Level1_12","native level identity");
            var nativeFeature=TowerDefenseManager.Instance.GetPacketBankFeature();
            await Until(t,()=>nativeFeature.packetBank.IsVisibleInTree()&&!nativeFeature.packetBank.packetBankAnimationPlayer.IsPlaying()&&
                (typeof(TowerDefenseBattleFeaturePacketBank).GetField("OnChooseOver",System.Reflection.BindingFlags.Instance|System.Reflection.BindingFlags.NonPublic)?.GetValue(nativeFeature) as Delegate)?.GetInvocationList().Any(d=>d.Method.DeclaringType?.FullName?.Contains("TowerDefenseBattleProcessWave")==true)==true,"native entry awaiting choose signal");
            context.Log("SUPER_NATIVE_READY: visible settled picker and Wave choose listener");
            nativeFeature.CategoryChoose("Gold",true);await Wait(t,.3);
            var nativeOwn=nativeFeature.packetList.Single(p=>p.config.saveKey==Key("Packet"));nativeFeature.PacketChoose(nativeOwn);await Until(t,()=>nativeFeature.packetBank.seedBank.packetNum>0&&nativeFeature.packetBank.seedBank.HasPacket(Key("Packet")),"selected card flight completed");nativeFeature.RockButtonPressed();await Ready(t);
            TowerDefenseManager.Instance.AddSun(1000);
            var nativeCard=TowerDefenseManager.Instance.GetSeedBankList().Single(p=>p.config.saveKey==Key("Packet"));
            await Until(t,()=>nativeCard.alive&&!nativeCard.@lock,"native card readiness");
            Check(nativeCard.Plant(new Vector2I(2,3))!=null,"native original level placement");
            await Shot(t,"super-native-level");context.Log("SUPER_NATIVE_LEVEL_PASS: MainMenu Adventure, chapter, Level1_12, Gold choose/confirm and actual card Plant");
            await Menu(t);context.Log("AUDIT_DISCOVERY_DONE: original pool auto and picker branches");t.Quit();
        }
        catch(Exception e){context.Log("AUDIT_TEST_ERROR: "+e);await Shot(t,"super-picker-failed");t.Quit(2);}
    }
}
