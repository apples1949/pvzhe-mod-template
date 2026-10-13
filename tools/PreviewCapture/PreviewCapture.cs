using Godot;

namespace ModPreview;

/// <summary>Opt-in capture helpers for an isolated host test; never invoked by Hello World.</summary>
public static class PreviewCapture
{
    private static async Task Draw(SceneTree tree)
    {
        await tree.ToSignal(tree, SceneTree.SignalName.ProcessFrame);
        await tree.ToSignal(RenderingServer.Singleton, RenderingServer.SignalName.FramePostDraw);
    }

    /// <summary>Hide only the selected Mod components before capturing the viewport texture.</summary>
    public static async Task CaptureBackground(SceneTree tree, Viewport viewport,
        IReadOnlyCollection<CanvasItem> components, string output)
    {
        var previous = components.Select(item => (Item:item, Visible:item.Visible)).ToArray();
        try
        {
            foreach (var state in previous) state.Item.Visible = false;
            await Draw(tree);
            using var image = viewport.GetTexture().GetImage();
            if (image.SavePng(output) != Error.Ok) throw new IOException("Background capture failed");
        }
        finally
        {
            foreach (var state in previous)
                if (GodotObject.IsInstanceValid(state.Item)) state.Item.Visible = state.Visible;
        }
    }

    /// <summary>Instantiate a full host scene in an independent transparent SubViewport.</summary>
    public sealed record ComponentCapture(Vector2 Size, int Padding, Vector2I ImageSize);

    public static async Task<ComponentCapture> CaptureComponent(SceneTree tree, PackedScene scene,
        Vector2 size, string output, Action<Control>? configure = null, int padding = 8)
    {
        if (!float.IsFinite(size.X) || !float.IsFinite(size.Y) || size.X <= 0 || size.Y <= 0 || padding < 0 || size.X+padding*2 > 4096 || size.Y+padding*2 > 4096) throw new ArgumentOutOfRangeException(nameof(size));
        var viewport = new SubViewport
        {
            TransparentBg = true, Disable3D = true, World2D = new World2D(),
            Size = new Vector2I((int)Math.Ceiling(size.X) + padding*2, (int)Math.Ceiling(size.Y) + padding*2),
            RenderTargetUpdateMode = SubViewport.UpdateMode.Always
        };
        tree.Root.AddChild(viewport);
        try
        {
            var control = scene.Instantiate<Control>();
            viewport.AddChild(control);
            configure?.Invoke(control);
            control.Position = new Vector2(padding,padding);
            control.Size = size;
            await Draw(tree);
            // Minimum size and font metrics can be resolved only after the scene is ready.
            var actual = control.Size;
            viewport.Size = new Vector2I((int)Math.Ceiling(actual.X)+padding*2, (int)Math.Ceiling(actual.Y)+padding*2);
            await Draw(tree);
            using var image = viewport.GetTexture().GetImage();
            if (!image.GetUsedRect().HasArea())
                throw new InvalidOperationException("Component render is empty; inspect dependencies and readiness");
            if (image.DetectAlpha() == Image.AlphaMode.None)
                throw new InvalidOperationException("Component render is opaque; do not substitute a screen crop");
            if (image.SavePng(output) != Error.Ok) throw new IOException("Transparent component capture failed");
            return new ComponentCapture(actual,padding,viewport.Size);
        }
        finally
        {
            if (GodotObject.IsInstanceValid(viewport)) viewport.QueueFree();
        }
    }
}
