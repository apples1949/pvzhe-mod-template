using Godot;

namespace SuperGatlingPea;

public sealed partial class Entry
{
    const string LocalRenderMarker = "super_gatling_local_draw";

    void InstallSpriteRendering()
    {
        var tree = (SceneTree)Engine.GetMainLoop();
        void Configure(Node node)
        {
            if (node is not AdobeAnimateSprite sprite || !sprite.HasMeta(LocalRenderMarker)) return;
            void Apply()
            {
                if (GodotObject.IsInstanceValid(sprite) && sprite.IsInsideTree())
                    sprite.forceLocalRender = true;
            }
            if (sprite.IsNodeReady()) Apply();
            else sprite.Ready += Apply;
        }
        // Includes our card/selection previews as well as planted instances.
        // No unmarked host character or global renderer is modified.
        tree.NodeAdded += Configure;
        context.Lifetime.Track(() => tree.NodeAdded -= Configure);
        foreach (var node in Nodes(tree.Root)) Configure(node);
    }
}
