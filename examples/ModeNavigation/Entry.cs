using PVZHE.ModEditor.ModSystem;

namespace ModeNavigation;

public sealed class Entry : IXWModRuntimeEntry
{
    public void Initialize(XWModRuntimeContext context)
    {
        var levels = new ModeLevels(context);
        var page = new ModePage(context, levels);
        context.Lifetime.Track(context.Hooks.Subscribe(XWModPresentationPoints.MainMenu,
            "mode-navigation.menu", (_, surface) => page.Mount(surface)));
        context.Log("MODE_NAVIGATION_INIT: registered journey catalog");
    }

    public void OnAllModsLoaded() { }
    public void Shutdown() { }
}
