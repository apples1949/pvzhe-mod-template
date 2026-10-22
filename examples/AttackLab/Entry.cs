using Godot;
using PVZHE.ModEditor.ModSystem;
namespace AttackLab;

public sealed partial class Entry : IXWModRuntimeEntry
{
    XWModRuntimeContext context=null!;
    internal readonly Dictionary<string,TowerDefenseLevelNewConfig> levels=new();
    internal string catalog="";
    internal PlanRunner? active;
    internal static readonly string[] Cases={"straight","fan","ring","parallel","starfruit","homing","lob","nested"};
    public void Initialize(XWModRuntimeContext value)
    {
        context=value;
        try{InitializeCore(value);}catch(Exception error){context.Log("AUDIT_INIT_ERROR: "+error);throw;}
    }
    void InitializeCore(XWModRuntimeContext value)
    {
        context=value;
        foreach(var (key,source) in new[]{("Pea","PeaDefault"),("Lob","CabbageCatapult"),("Track","PeaTrack")})
        {
            var config=(TowerDefenseProjectileConfig)ResourceManager.Instance.PROJECTILE_CONFIG[source].Duplicate(true);
            config.name=context.Content.Identity("Projectile",key).RuntimeKey;
            config.baseDamage=20;config.fireMethodFlags=key=="Lob"?2:key=="Track"?32:0;config.catapultHeight=300;
            if(!context.Content.Provide("Projectile",key,Variant.From(config),out var error))throw new Exception(error);
        }
        RegisterLevels();
        context.Lifetime.Track(context.Hooks.Subscribe(XWModPresentationPoints.BattleHud,"attack.lab",(_,surface)=>
        {
            if(XWModLevelSession.OwnerModId!=context.ModId||Global.IsMultiplayerMode)return;
            var tree=surface.Root.GetTree();
            var runners=new Dictionary<ulong,PlanRunner>();
            void Added(Node node)
            {
                if(node is not TowerDefenseCharacter plant||plant.config?.name!="PlantPeaShooterSingle")return;
                void Bind(){if(runners.ContainsKey(plant.GetInstanceId()))return;var key=levels.First(p=>p.Value.name==TowerDefenseManager.Instance.currentLevelConfig.name).Key;var plan=Read(Path.Combine(context.PackageRoot,"Assets",key+".json"));ConfigureAuditPlan(ref plan);var runner=new PlanRunner(context,plant,plan);runners.Add(plant.GetInstanceId(),runner);active=runner;}
                if(plant.IsNodeReady())Bind();else plant.Ready+=Bind;
            }
            void Tick()
            {
                if(tree.Paused||Global.IsMultiplayerMode||!context.Game.TryGetBattle(out var battle)||!battle.Running||battle.Paused)return;
                var control=TowerDefenseManager.Instance.currentControl;
                if(control==null||!control.isGameRunning||control.waitPause||(!GameSaveManager.Instance.GetConfigValue("Backgrounder").AsBool()&&!DisplayServer.WindowIsFocused()))return;
                foreach(var runner in runners.Values)runner.Tick(surface.Root.GetPhysicsProcessDeltaTime());
            }
            tree.NodeAdded+=Added;tree.PhysicsFrame+=Tick;foreach(var n in Nodes(tree.Root).ToArray())Added(n);
            surface.Lifetime.Track(()=>{tree.NodeAdded-=Added;tree.PhysicsFrame-=Tick;foreach(var r in runners.Values)r.Dispose();runners.Clear();active=null;});
        }));
        ConfigureAudit();
    }
    internal static Godot.Collections.Dictionary Read(string path)
    {
        using var file=Godot.FileAccess.Open(path,Godot.FileAccess.ModeFlags.Read);
        if(file==null)throw new IOException(path);
        var json=new Json();if(json.Parse(file.GetAsText())!=Error.Ok)throw new InvalidDataException(path);
        return json.Data.AsGodotDictionary();
    }
    void RegisterLevels()
    {
        const string art="res://Asset/Texture/GUI/TowerDefense/Level/Chapter1/";
        var chapter=new LevelChapterConfig{chapterName="攻击方案实验",unlockImage=GD.Load<Texture2D>(art+"Chapter1.png"),background=GD.Load<Texture2D>(art+"Chapter1Background.jpg"),building=GD.Load<Texture2D>(art+"Chapter1Building.png")};
        foreach(var key in Cases)
        {
            var data=Read(Path.Combine(context.PackageRoot,"Assets","level.json"));data["Name"]="attack-lab."+key;data["LevelName"]=key;
            var level=new TowerDefenseLevelNewConfig{data=new Json{Data=data}};
            if(!XWModLevelValidation.Validate(level,out var error))throw new Exception(error);
            level.TakeOverPath("user://AttackLab/"+key+".tres");levels[key]=level;
            chapter.levelList.Add(new LevelChooseConfig{saveKey=level.name,normalLevel=level,unlockImage=GD.Load<Texture2D>(art+"Adventure_LEVEL1-1.png")});
        }
        var listing=new LevelCatalogConfig{catalogKey="lab",displayTitle="攻击方案实验"};listing.chapterList.Add(chapter);
        if(!context.Content.ProvideLevelCatalog("lab",listing,out var reason))throw new Exception(reason);
        catalog=context.Content.Identity("Level","lab").RuntimeKey;
    }
    internal void Launch(string key)
    {
        var identity=new XWModLevelIdentity(context.ModId,catalog,levels[key].name,"Normal");
        if(!XWModContentCatalog.TryResolve(identity,out var config,out var error))throw new Exception(error);
        XWModLevelSession.Select(identity);TowerDefenseManager.Instance.currentLevelConfig=config;
        Global.Instance.currentLevelId=0;Global.Instance.enterLevelMode="ModLevel";SceneManager.Instance.ChangeScene("TowerDefense");
    }
    internal static IEnumerable<Node> Nodes(Node root){foreach(var child in root.GetChildren()){yield return child;foreach(var n in Nodes(child))yield return n;}}
    partial void ConfigureAudit();partial void StartAudit(SceneTree tree);
    partial void ConfigureAuditPlan(ref Godot.Collections.Dictionary plan);
    public void OnAllModsLoaded(){context.Log("ATTACK_LAB_READY: eight plans registered; no automatic launch");} public void Shutdown(){}
}
