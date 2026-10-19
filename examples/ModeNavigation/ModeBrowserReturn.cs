using Godot;
using PVZHE.ModEditor.ModSystem;

namespace ModeNavigation;

// 0.30.0 adapter: native Mod-browser root Back can target LevelEditorStage.
// Replace only this instance's native Back delegate, preserving other subscribers.
public static class ModeBrowserReturn
{
    public static void Install(XWModRuntimeContext context, XWModLifetime runtimeScope, SceneTree tree, Func<bool> ownsRoute)
    {
        void Added(Node node)
        {
            if (node is not LevelChoose choose || !ownsRoute() || XWModLevelSession.OwnerModId != context.ModId) return;
            void Bind()
            {
                if (!GodotObject.IsInstanceValid(choose) || !ownsRoute()) return;
                var button = choose.GetNode<BaseButton>("%BackButton");
                var scope = context.Presentation.CreateSceneScope(choose);
                void Back()
                {
                    if (SceneManager.Instance.isLoading || DialogManager.Instance.HasOpenDialogs) return;
                    var catalogs = choose.GetNodeOrNull<CanvasLayer>("ModBrowser");
                    if (ownsRoute() && XWModLevelSession.OwnerModId == context.ModId && catalogs?.Visible == true)
                    {
                        XWModLevelSession.Clear();
                        SceneManager.Instance.ChangeScene("MainMenu");
                    }
                    else choose.Back();
                }
                button.Pressed -= choose.Back;
                button.Pressed += Back;
                scope.Track(() =>
                {
                    if (!GodotObject.IsInstanceValid(button)) return;
                    button.Pressed -= Back;
                    if (GodotObject.IsInstanceValid(choose) && !choose.IsQueuedForDeletion()) button.Pressed += choose.Back;
                });
                context.Log("MODE_BROWSER_RETURN: own browser Back adapted");
            }
            if (choose.IsNodeReady()) Bind();
            else
            {
                void Ready() { choose.Ready -= Ready; Bind(); }
                choose.Ready += Ready;
            }
        }
        tree.NodeAdded += Added;
        runtimeScope.Track(() => tree.NodeAdded -= Added);
    }
}
