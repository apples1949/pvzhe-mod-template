using Godot;
using PVZHE.ModEditor.ModSystem;

namespace ModeNavigation;

// A local navigation page hosted by MainMenu; not a registered SceneManager scene.
public sealed class ModePage
{
    readonly ModeLevels levels;
    readonly XWModRuntimeContext context;
    readonly XWModLifetime runtimeScope;
    bool observing;
    bool returnToPage;
    bool navigating;

    public ModePage(XWModRuntimeContext context, ModeLevels levels)
    {
        this.context = context;
        runtimeScope = context.Lifetime.CreateChildScope();
        this.levels = levels;
    }

    public void Mount(XWModUiSurface surface)
    {
        navigating = false;
        if (!observing)
        {
            observing = true;
            ModeBrowserReturn.Install(context, runtimeScope, surface.Root.GetTree(), () => returnToPage);
        }
        var scope = surface.Lifetime;
        var launcherBox = scope.TrackNode(new Control { MouseFilter = Control.MouseFilterEnum.Ignore });
        surface.Root.AddChild(launcherBox);
        launcherBox.SetAnchorsAndOffsetsPreset(Control.LayoutPreset.BottomLeft);
        launcherBox.Position += new Vector2(16, -180);
        CanvasLayer? page = null;
        MainButton launcher = null!;
        launcher = AddButton(launcherBox, "AuditLaunch", "模式导航实验", Vector2.Zero, Show);

        void Close()
        {
            returnToPage = false;
            if (GodotObject.IsInstanceValid(page)) { page!.QueueFree(); page = null; }
            launcher.Show();
        }

        void Navigate(Action action)
        {
            if (navigating || SceneManager.Instance.isLoading || DialogManager.Instance.HasOpenDialogs) return;
            navigating = true;
            try { action(); }
            catch { navigating = false; throw; }
        }

        void Show()
        {
            if (SceneManager.Instance.isLoading || DialogManager.Instance.HasOpenDialogs) return;
            if (GodotObject.IsInstanceValid(page)) return;
            returnToPage = true;
            launcher.Hide();
            page = scope.TrackNode(new CanvasLayer { Name = "ModeNavigationPage", Layer = 10 });
            surface.Root.AddChild(page);
            var root = new Control { Name = "Page", MouseFilter = Control.MouseFilterEnum.Stop };
            page.AddChild(root);
            root.SetAnchorsAndOffsetsPreset(Control.LayoutPreset.FullRect);
            var background = new TextureRect
            {
                Texture = GD.Load<Texture2D>("res://Asset/Texture/GUI/TowerDefense/Level/Chapter1/Chapter1Background.jpg"),
                ExpandMode = TextureRect.ExpandModeEnum.IgnoreSize,
                StretchMode = TextureRect.StretchModeEnum.KeepAspectCovered,
                MouseFilter = Control.MouseFilterEnum.Ignore, Modulate = new Color(.65f, .65f, .65f)
            };
            root.AddChild(background);
            background.SetAnchorsAndOffsetsPreset(Control.LayoutPreset.FullRect);
            var center = new Control { MouseFilter = Control.MouseFilterEnum.Ignore };
            root.AddChild(center);
            center.SetAnchorsAndOffsetsPreset(Control.LayoutPreset.Center);
            var title = new Label { Text = "模式导航实验", Position = new Vector2(-170, -155), Size = new Vector2(340, 48), HorizontalAlignment = HorizontalAlignment.Center };
            center.AddChild(title);
            title.AddThemeFontSizeOverride("font_size", 32);
            AddButton(center, "ModeChapters", "章节选关", new Vector2(-95, -75), () => Navigate(levels.Browse));
            AddButton(center, "ModeDirect", "直接挑战终点关", new Vector2(-95, -15), () => Navigate(() => levels.Launch(1)));
            AddButton(center, "ModeBack", "返回主菜单", new Vector2(-95, 75), Close);
        }

        MainButton AddButton(Control parent, string name, string text, Vector2 position, Action pressed)
        {
            var button = GD.Load<PackedScene>("res://Prefab/GUI/Button/MainButton.tscn").Instantiate<MainButton>();
            button.Name = name;
            button.text = text;
            parent.AddChild(button);
            button.Position = position;
            button.Size = new Vector2(190, 46);
            button.Pressed += pressed;
            return button;
        }

        // Page child nodes are freed recursively; only route intent survives remounting.
        if (returnToPage) Show();
    }
}
