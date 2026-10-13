using Godot;
using PVZHE.ModEditor.ModSystem;
using FeatureLab.Adapters;
using FeatureLab.Features;

namespace FeatureLab;

public sealed class Entry : IXWModRuntimeEntry
{
    private XWModRuntimeContext? _context;
    private DemoLevel? _level;
    private KillCounter? _kills;
    private bool _testStarted;

    public void Initialize(XWModRuntimeContext context)
    {
        try { InitializeCore(context); }
        catch (Exception error) { context.Log("LAB_INIT_ERROR: " + error); throw; }
    }

    private void InitializeCore(XWModRuntimeContext context)
    {
        _context = context;
        context.Log("HELLO_INIT: Feature Lab");
        using (var binary = File.OpenRead(Path.Combine(context.PackageRoot, "Runtime", "ModAssembly.dll")))
            context.Log("HELLO_BINARY: " + Convert.ToHexString(System.Security.Cryptography.SHA256.HashData(binary)).ToLowerInvariant());
        _level = new DemoLevel(context);
        _kills = new KillCounter(context);
        _ = new StartingSun(context);
        context.Lifetime.Track(context.Hooks.Subscribe(XWModLifecyclePoints.Result, "lab.result", (_, value) =>
            context.Log("LAB_RESULT: " + value.Result)));
        context.Lifetime.Track(context.Hooks.Subscribe(XWModPresentationPoints.MainMenu, "lab.menu", (_, surface) =>
        {
            var box = surface.Lifetime.TrackNode(new Control { Name = "FeatureLabMenu" });
            surface.Root.AddChild(box);
            box.SetAnchorsAndOffsetsPreset(Control.LayoutPreset.BottomLeft);
            box.Position += new Vector2(16, -176);
            bool open = false;
            HostUi.AddButton(box, surface.Lifetime, "FeatureLabHelp", "玩法说明", Vector2.Zero, () =>
            {
                if (open || DialogManager.Instance.HasOpenDialogs) return;
                open = true;
                var dialog = HostUi.ShowTips(surface.Lifetime,
                    "[center]功能开发示例[/center]\n原版按钮与弹窗；右下角击杀统计；设置与开局阳光；独立示例关卡。");
                DialogBoxBase.CloseEventHandler closed = () => open = false;
                dialog.OnClose += closed;
                surface.Lifetime.Track(() => { if (GodotObject.IsInstanceValid(dialog)) dialog.OnClose -= closed; });
                context.Log("LAB_DIALOG: original tips opened");
            });
            var toggle = HostUi.AddButton(box, surface.Lifetime, "FeatureLabToggle", "统计：" + (_context.Settings.Get<bool>("showKills") ? "开" : "关"), new Vector2(0, 52), () =>
            {
                bool next = !context.Settings.Get<bool>("showKills");
                if (!context.Settings.TrySave(new Dictionary<string, object> { ["showKills"] = next }, out var result))
                    throw new InvalidOperationException(result.Message);
                context.Log("LAB_SETTINGS: showKills=" + next + "; restart=" + result.RestartRequired);
            });
            void Changed(IReadOnlyList<string> _) => toggle.text = "统计：" + (context.Settings.Get<bool>("showKills") ? "开" : "关");
            context.Settings.Changed += Changed;
            surface.Lifetime.Track(() => context.Settings.Changed -= Changed);
            HostUi.AddButton(box, surface.Lifetime, "FeatureLabLevels", "示例关卡", new Vector2(0, 104), _level.OpenBrowser);
            context.Log("LAB_UI: original MainButton instances mounted");
            if (!_testStarted && OS.GetCmdlineUserArgs().Contains("--feature-lab-test"))
            {
                _testStarted = true;
                Verification.Smoke.Run(context, surface.Root.GetTree(), _level, _kills);
            }
            else if (!_testStarted && OS.GetCmdlineUserArgs().Contains("--feature-lab-persistence"))
            {
                _testStarted = true;
                Verification.Smoke.RunPersistence(context, surface.Root.GetTree());
            }
        }));
    }

    public void OnAllModsLoaded() => _context?.Log("HELLO_READY: all mods loaded");
    public void Shutdown()
    {
        _context?.Log("HELLO_SHUTDOWN: Feature Lab");
        _context = null; _level = null; _kills = null;
    }
}
