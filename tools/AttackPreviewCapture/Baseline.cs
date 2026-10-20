using Godot;
using PVZHE.ModEditor.ModSystem;
namespace AttackPreviewCapture;

public sealed partial class Entry
{
    string calibrationCatalog = "";
    TowerDefenseLevelNewConfig calibrationLevel = null!;
    void RegisterCalibration()
    {
        var json = new Json();
        if (json.Parse(File.ReadAllText(Path.Combine(context.PackageRoot, "level.json"))) != Error.Ok) throw new InvalidDataException("Calibration level JSON");
        calibrationLevel = new TowerDefenseLevelNewConfig { data = json };
        if (!XWModLevelValidation.Validate(calibrationLevel, out var error)) throw new InvalidDataException(error);
        calibrationLevel.TakeOverPath("user://AttackPreview/calibration.tres");
        const string art = "res://Asset/Texture/GUI/TowerDefense/Level/Chapter1/";
        var chapter = new LevelChapterConfig { chapterName = "Calibration", unlockImage = GD.Load<Texture2D>(art+"Chapter1.png"),
            background = GD.Load<Texture2D>(art+"Chapter1Background.jpg"), building = GD.Load<Texture2D>(art+"Chapter1Building.png") };
        chapter.levelList.Add(new LevelChooseConfig { saveKey = calibrationLevel.name, normalLevel = calibrationLevel,
            unlockImage = GD.Load<Texture2D>(art+"Adventure_LEVEL1-1.png") });
        var catalog = new LevelCatalogConfig { catalogKey = "calibration", displayTitle = "Calibration" };
        catalog.chapterList.Add(chapter);
        if (!context.Content.ProvideLevelCatalog("calibration", catalog, out error)) throw new InvalidOperationException(error);
        calibrationCatalog = context.Content.Identity("Level", "calibration").RuntimeKey;
    }
    static async Task Wait(SceneTree tree, double seconds) => await tree.ToSignal(tree.CreateTimer(seconds, true, false, true), SceneTreeTimer.SignalName.Timeout);
    async Task Until(SceneTree tree, Func<bool> condition, string stage)
    {
        var prompts = new HashSet<ulong>();
        for (int i=0; i<240; i++)
        {
            var prompt = Nodes(tree.Root).OfType<DialogBoxBase>().FirstOrDefault(n => n.GetType().Name=="DialogBoxGamePause");
            if (prompt != null && prompts.Add(prompt.GetInstanceId()))
            {
                if (prompts.Count > 4) throw new Exception("Repeated environment pause");
                tree.Root.GrabFocus(); prompt.CloseDialog(); context.Log("ATTACK_ENV_PAUSE: closed known environment prompt");
            }
            if (condition()) return;
            await Wait(tree, .1);
        }
        throw new Exception("Calibration readiness failed: "+stage);
    }
    async Task Calibrate(SceneTree tree)
    {
        await Until(tree, () => Nodes(tree.Root).OfType<DialogBoxNewUser>().Any(n => n.nameLineEdit != null), "new user");
        var profile = Nodes(tree.Root).OfType<DialogBoxNewUser>().Single();
        profile.nameLineEdit.Text = "AttackBaseline"; profile.readyButtonNewUser.EmitSignal(BaseButton.SignalName.Pressed);
        await Until(tree, () => GameSaveManager.Instance.GetUserCurrent()=="AttackBaseline" && !DialogManager.Instance.HasOpenDialogs && !SceneManager.Instance.isLoading, "profile");
        var identity = new XWModLevelIdentity(context.ModId, calibrationCatalog, calibrationLevel.name, "Normal");
        if (!XWModContentCatalog.TryResolve(identity, out var config, out var error)) throw new Exception(error);
        XWModLevelSession.Select(identity); TowerDefenseManager.Instance.currentLevelConfig=config;
        Global.Instance.currentLevelId=0; Global.Instance.enterLevelMode="ModLevel"; SceneManager.Instance.ChangeScene("TowerDefense");
        await Until(tree, () => context.Game.TryGetBattle(out var b) && b.Running && !b.Paused && !tree.Paused && !SceneManager.Instance.isLoading, "battle");
        Engine.TimeScale=1;
        var card=TowerDefenseManager.Instance.GetSeedBankList().Single(p=>p.config.saveKey=="PlantPeaShooterSingle");
        var plant=card.Plant(new Vector2I(1,3)) ?? throw new Exception("Native card planting failed");
        var target=await context.Game.Characters.SpawnAsync("ZombieNormalBucket",8,3);
        if (!target.Succeeded) throw new Exception(target.Diagnostic);
        var definition=plant.ComponentSet.GetFlattenedDefinitions().OfType<FireComponentDefinition>().First();
        var times=new List<double>(); var speeds=new List<float>(); var positions=new List<Vector2>();
        double clock=0, sampleStart=-1, sampleEnd=-1; Vector2 p0=default,p1=default; int tracked=-1;
        string projectile="";
        void Spawned(int index)
        {
            ref var b=ref BulletField.Instance.GetBulletDataRef(index);
            if (b.fireCharacter!=plant) return;
            times.Add(clock); speeds.Add(b.vel.Length()); positions.Add(b.pos); projectile=b.config.name;
            if (tracked<0) tracked=index;
        }
        void Frame()
        {
            clock+=tree.Root.GetPhysicsProcessDeltaTime();
            if (tracked<0 || sampleEnd>=0) return;
            ref var b=ref BulletField.Instance.GetBulletDataRef(tracked);
            if (!b.active) throw new Exception("Calibration bullet disappeared before displacement sample");
            if (sampleStart<0) { sampleStart=clock; p0=b.pos; }
            else if (clock-sampleStart>=.4) { sampleEnd=clock; p1=b.pos; }
        }
        BulletField.Instance.OnBulletSpawned+=Spawned; tree.PhysicsFrame+=Frame;
        try
        {
            await Until(tree, () => times.Count>=5 && sampleEnd>sampleStart, "five native shots + displacement");
            double interval=(times[4]-times[0])/4;
            double observedSpeed=p1.DistanceTo(p0)/(sampleEnd-sampleStart);
            if (interval<=0 || speeds[0]<=0 || Math.Abs(observedSpeed-speeds[0])>speeds[0]*.05) throw new Exception("Native velocity/displacement mismatch");
            var shotTimes=new Godot.Collections.Array(); foreach (var t in times) shotTimes.Add(t);
            var baseline=new Godot.Collections.Dictionary {
                { "characterKey", "PlantPeaShooterSingle" }, { "projectileKey", projectile },
                { "bulletSpeed", speeds[0] }, { "measuredBulletSpeed", observedSpeed },
                { "attackInterval", interval }, { "configuredInterval", definition.fireInterval },
                { "shotTimes", shotTimes }, { "displacement", p1.DistanceTo(p0) }, { "displacementSeconds", sampleEnd-sampleStart },
                { "engineTimeScale", Engine.TimeScale }, { "coordinateUnits", "host-logical-units-per-second" } };
            context.Log("ATTACK_BASELINE: "+Json.Stringify(baseline));
        }
        finally { BulletField.Instance.OnBulletSpawned-=Spawned; tree.PhysicsFrame-=Frame; }
    }
}
