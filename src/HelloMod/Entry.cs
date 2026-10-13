using Godot;
using PVZHE.ModEditor.ModSystem;

namespace HelloMod;

/// <summary>普通托管入口，不继承 Godot.Node，无需 Godot 源生成器。</summary>
public sealed class Entry : IXWModRuntimeEntry
{
    private XWModRuntimeContext? _context;

    public void Initialize(XWModRuntimeContext context)
    {
        _context = context;
        context.Log("HELLO_INIT: Hello World!");
        using (var binary = File.OpenRead(Path.Combine(context.PackageRoot, "Runtime", "ModAssembly.dll")))
            context.Log("HELLO_BINARY: " + Convert.ToHexString(
                System.Security.Cryptography.SHA256.HashData(binary)).ToLowerInvariant());
        // 复用宿主 UI 挂载点及场景作用域，切换场景/卸载时由宿主清理。
        context.Lifetime.Track(context.Hooks.Subscribe(XWModHookPoints.UiMount,
            "hello.banner", surface =>
            {
                var label = surface.SceneLifetime.TrackNode(new Label
                {
                    Name = "HelloModBanner",
                    Text = "Hello World! · PVZHE Mod",
                    Position = new Vector2(16, 16),
                    MouseFilter = Control.MouseFilterEnum.Ignore
                });
                surface.Root.AddChild(label);
                context.Log("HELLO_UI: banner mounted");
            }));
    }

    public void OnAllModsLoaded() => _context?.Log("HELLO_READY: all mods loaded");

    public void Shutdown()
    {
        _context?.Log("HELLO_SHUTDOWN: goodbye");
        _context = null;
    }
}
