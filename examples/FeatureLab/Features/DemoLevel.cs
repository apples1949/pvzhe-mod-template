using Godot;
using PVZHE.ModEditor.ModSystem;

namespace FeatureLab.Features;

public sealed class DemoLevel
{
    public const string CatalogKey = "demo";
    public TowerDefenseLevelNewConfig Config { get; }
    private readonly XWModRuntimeContext _context;
    private readonly string _runtimeCatalogKey;

    public DemoLevel(XWModRuntimeContext context)
    {
        _context = context;
        _runtimeCatalogKey = context.Content.Identity("Level", CatalogKey).RuntimeKey;
        var path = Path.Combine(context.PackageRoot, "Assets", "level.json");
        var data = new Json();
        if (data.Parse(File.ReadAllText(path)) != Error.Ok) throw new InvalidDataException(data.GetErrorMessage());
        Config = new TowerDefenseLevelNewConfig { data = data };
        if (string.IsNullOrWhiteSpace(Config.name)) throw new InvalidDataException("Level requires an independent save key.");
        if (!XWModLevelValidation.Validate(Config, out string error)) throw new InvalidDataException(error);
        // 管理目录需要 ResourcePath；仅建立内存映射，不向宿主 PCK 写文件。
        string resourceKey = $"user://FeatureLab/{context.ModId}/demo-level.tres";
        Config.TakeOverPath(resourceKey);
        const string art = "res://Asset/Texture/GUI/TowerDefense/Level/Chapter1/";
        Texture2D Texture(string name) => GD.Load<Texture2D>(art + name)
            ?? throw new InvalidDataException("Missing released catalog texture: " + name);
        var chapter = new LevelChapterConfig
        {
            chapterName = "基础示例", unlockImage = Texture("Chapter1.png"),
            background = Texture("Chapter1Background.jpg"), building = Texture("Chapter1Building.png")
        };
        chapter.levelList.Add(new LevelChooseConfig
        {
            saveKey = Config.name, normalLevel = Config, unlockImage = Texture("Adventure_LEVEL1-1.png")
        });
        var catalog = new LevelCatalogConfig { catalogKey = CatalogKey, displayTitle = "功能实验关卡" };
        catalog.chapterList.Add(chapter);
        if (!context.Content.ProvideLevelCatalog(CatalogKey, catalog, out error)) throw new InvalidOperationException(error);
        context.Log("LAB_LEVEL: registered " + Config.name);
    }

    public void OpenBrowser()
    {
        if (Global.IsMultiplayerMode) throw new InvalidOperationException("This example currently supports single player only.");
        XWModLevelSession.SelectCatalog(_context.ModId, _runtimeCatalogKey);
        Global.Instance.currentLevelChoose = XWModLevelSession.BrowserKey;
        SceneManager.Instance.ChangeScene("LevelChoose");
    }

    // 用公开身份、校验和宿主切场景流程启动；集中隔离宿主全局状态接入。
    public void Launch()
    {
        if (Global.IsMultiplayerMode) throw new InvalidOperationException("Single player example only.");
        var identity = new XWModLevelIdentity(_context.ModId, _runtimeCatalogKey, Config.name, "Normal");
        if (!XWModPlayerProgressService.CanPlay(_context.ModId, out string error) ||
            !XWModContentCatalog.TryResolve(identity, out var config, out error)) throw new InvalidOperationException(error);
        XWModLevelSession.Select(identity);
        TowerDefenseManager.Instance.currentLevelConfig = config;
        Global.Instance.currentLevelId = 0;
        Global.Instance.enterLevelMode = "ModLevel";
        SceneManager.Instance.ChangeScene("TowerDefense");
    }
}
