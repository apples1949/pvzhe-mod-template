using Godot;
using PVZHE.ModEditor.ModSystem;

namespace ModeNavigation;

// Only player-authored JSON is packaged. All artwork is referenced from the host.
public sealed class ModeLevels
{
    public const string CatalogKey = "journey";
    public const string Title = "模式导航实验目录";
    readonly XWModRuntimeContext context;
    public string RuntimeKey { get; }
    public TowerDefenseLevelNewConfig[] Levels { get; }

    public ModeLevels(XWModRuntimeContext context)
    {
        this.context = context;
        RuntimeKey = context.Content.Identity("Level", CatalogKey).RuntimeKey;
        Levels = new[] { Read("first"), Read("second") };
        const string art = "res://Asset/Texture/GUI/TowerDefense/Level/Chapter1/";
        Texture2D Texture(string file) => GD.Load<Texture2D>(art + file)
            ?? throw new InvalidDataException("Missing host artwork: " + file);
        var catalog = new LevelCatalogConfig { catalogKey = CatalogKey, displayTitle = Title };
        for (int i = 0; i < Levels.Length; i++)
        {
            var chapter = new LevelChapterConfig
            {
                chapterName = i == 0 ? "第一章：起步" : "第二章：终点",
                unlockImage = Texture("Chapter1.png"), background = Texture("Chapter1Background.jpg"),
                building = Texture("Chapter1Building.png")
            };
            chapter.levelList.Add(new LevelChooseConfig
            {
                saveKey = Levels[i].name, normalLevel = Levels[i], unlockImage = Texture("Adventure_LEVEL1-1.png")
            });
            catalog.chapterList.Add(chapter);
        }
        if (!context.Content.ProvideLevelCatalog(CatalogKey, catalog, out var error))
            throw new InvalidOperationException(error);
    }

    TowerDefenseLevelNewConfig Read(string file)
    {
        var json = new Json();
        if (json.Parse(File.ReadAllText(Path.Combine(context.PackageRoot, "Assets", file + ".json"))) != Error.Ok)
            throw new InvalidDataException(json.GetErrorMessage());
        var level = new TowerDefenseLevelNewConfig { data = json };
        if (!XWModLevelValidation.Validate(level, out var error)) throw new InvalidDataException(error);
        level.TakeOverPath($"user://ModeNavigation/{context.ModId}/{file}.tres");
        return level;
    }

    void CheckAccess()
    {
        if (Global.IsMultiplayerMode) throw new InvalidOperationException("Single player recipe only.");
        if (!XWModPlayerProgressService.CanPlay(context.ModId, out var error))
            throw new InvalidOperationException(error);
    }

    public void Browse()
    {
        CheckAccess();
        XWModLevelSession.SelectCatalog(context.ModId, RuntimeKey);
        Global.Instance.currentLevelChoose = XWModLevelSession.BrowserKey;
        SceneManager.Instance.ChangeScene("LevelChoose");
    }

    public void Launch(int index)
    {
        CheckAccess();
        var identity = new XWModLevelIdentity(context.ModId, RuntimeKey, Levels[index].name, "Normal");
        if (!XWModContentCatalog.TryResolve(identity, out var config, out var error))
            throw new InvalidOperationException(error);
        XWModLevelSession.Select(identity);
        TowerDefenseManager.Instance.currentLevelConfig = config;
        Global.Instance.currentLevelId = 0;
        Global.Instance.enterLevelMode = "ModLevel";
        SceneManager.Instance.ChangeScene("TowerDefense");
    }
}
