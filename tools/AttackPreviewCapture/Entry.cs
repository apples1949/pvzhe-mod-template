using Godot;
using PVZHE.ModEditor.ModSystem;
namespace AttackPreviewCapture;

// A temporary asset-capture Mod, built only inside .work. Never installed.
public sealed partial class Entry : IXWModRuntimeEntry
{
    XWModRuntimeContext context = null!;
    bool started;
    public void Initialize(XWModRuntimeContext value)
    {
        context = value;
        RegisterCalibration();
        context.Lifetime.Track(context.Hooks.Subscribe(XWModPresentationPoints.MainMenu, "attack.assets", (_, surface) =>
        { if (!started) { started = true; Capture(surface.Root.GetTree()); } }));
    }
    public void OnAllModsLoaded() { }
    public void Shutdown() { }
    static async Task Draw(SceneTree tree)
    {
        await tree.ToSignal(tree, SceneTree.SignalName.ProcessFrame);
        await tree.ToSignal(RenderingServer.Singleton, RenderingServer.SignalName.FramePostDraw);
    }
    static IEnumerable<Node> Nodes(Node node)
    { foreach (var child in node.GetChildren()) { yield return child; foreach (var descendant in Nodes(child)) yield return descendant; } }
    async Task Sprite(SceneTree tree, string key, string output)
    {
        var viewport = new SubViewport { TransparentBg = true, Disable3D = true,
            World2D = new World2D(), Size = new Vector2I(256, 256), RenderTargetUpdateMode = SubViewport.UpdateMode.Always };
        tree.Root.AddChild(viewport);
        try
        {
            var sprite = ResourceManager.Instance.GetCharacterSprite(key).Instantiate<AdobeAnimateSprite>();
            viewport.AddChild(sprite);
            var prototype = ResourceManager.Instance.GetCharacterScene(key).Instantiate<TowerDefenseCharacter>();
            try
            {
                var native = Nodes(prototype).OfType<AdobeAnimateSprite>().First();
                var transform = native.Transform;
                for (var parent = native.GetParent(); parent != prototype; parent = parent.GetParent())
                    if (parent is Node2D node) transform = node.Transform * transform;
                sprite.Transform = transform;
                sprite.Position += new Vector2(128, 190);
                var geometry = new Godot.Collections.Dictionary { { "key", key },
                    { "visualOffset", new Godot.Collections.Array { transform.Origin.X, transform.Origin.Y } },
                    { "nativeSpritePath", prototype.GetPathTo(native).ToString() }, { "trackingOffset", new Godot.Collections.Array { 0, 0 } } };
                context.Log("ATTACK_GEOMETRY_"+output+": " + Json.Stringify(geometry));
            }
            finally { prototype.Free(); }
            // Keep this isolated capture's actual native clips and attachments.
            // Runtime-only rendering properties must be set on live instances.
            void Local(Node node) { if (node is AdobeAnimateSprite s) s.forceLocalRender = true; foreach (var child in node.GetChildren()) Local(child); }
            Local(sprite);
            await Draw(tree); await Draw(tree); await Draw(tree);
            using var image = viewport.GetTexture().GetImage();
            if (!image.GetUsedRect().HasArea() || image.DetectAlpha() == Image.AlphaMode.None)
                throw new InvalidOperationException("Character capture empty or opaque: " + key);
            if (image.SavePng("user://"+output+".png") != Error.Ok) throw new IOException("Capture write failed");
            context.Log("ATTACK_ASSET_POSE: " + output + " key=" + key + " clip=" + sprite.clip + " frame=" + sprite.frameIndex);
        }
        finally { viewport.QueueFree(); }
    }
    async void Capture(SceneTree tree)
    {
        try
        {
            using var file = Godot.FileAccess.Open(Path.Combine(context.PackageRoot, "capture.json"), Godot.FileAccess.ModeFlags.Read);
            var settings = Json.ParseString(file.GetAsText()).AsGodotDictionary();
            // Measure in a fresh battle before constructing/freeing detached
            // preview prototypes; keep calibration independent of those views.
            await Calibrate(tree);
            var map = GD.Load<TowerDefenseMapConfig>("res://Asset/Config/Map/Frontlawn/Config/FrontlawnMapFrontlawn.tres");
            context.Log("ATTACK_GRID: " + Json.Stringify(new Godot.Collections.Dictionary {
                { "begin", new Godot.Collections.Array { map.gridBeginPos.X, map.gridBeginPos.Y } },
                { "size", new Godot.Collections.Array { map.gridSize.X, map.gridSize.Y } },
                { "rows", map.gridNum.Y }, { "columns", map.gridNum.X }, { "plantOffset", map.plantOffset } }));
            var texture = GD.Load<Texture2D>(settings["background"].AsString());
            using var image = texture.GetImage();
            if (image.IsCompressed()) image.Decompress();
            if (image.SavePng("user://background.png") != Error.Ok) throw new IOException("Background export failed");
            await Sprite(tree, settings["plant"].AsString(), "plant");
            await Sprite(tree, settings["target"].AsString(), "target");
            context.Log("ATTACK_ASSETS_DONE: background and transparent character reference poses");
            tree.Quit();
        }
        catch (Exception error) { context.Log("AUDIT_TEST_ERROR: " + error); tree.Quit(2); }
    }
}
