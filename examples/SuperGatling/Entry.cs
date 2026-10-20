using Godot;
using PVZHE.ModEditor.ModSystem;

namespace SuperGatlingPea;

public sealed partial class Entry : IXWModRuntimeEntry
{
    XWModRuntimeContext context = null!;
    DemoLevel level = null!;
    PowerPattern powerPattern = null!;
    PowerGuidance? activeGuidance;
    readonly Dictionary<ulong, PowerBurst> bursts = new();
    internal string Key(string category, string local = "SuperGatlingPea") => context.Content.Identity(category, local).RuntimeKey;
    internal static IEnumerable<Node> Nodes(Node root)
    {
        foreach (var child in root.GetChildren()) { yield return child; foreach (var item in Nodes(child)) yield return item; }
    }

    public void Initialize(XWModRuntimeContext value)
    {
        context = value;
        powerPattern = PowerPattern.Load(context);
        RegisterPlant();
        InstallSpriteRendering();
        level = new DemoLevel(context);
        context.Lifetime.Track(context.Hooks.Subscribe(XWModPresentationPoints.BattleHud, "super-gatling.runtime", (_, surface) =>
        {
            var tree = surface.Root.GetTree();
            var guidance = new PowerGuidance(Key("Projectile", "SuperPea"));
            activeGuidance = guidance;
            void Bind(TowerDefenseCharacter plant)
            {
                if (!GodotObject.IsInstanceValid(plant) || plant.config?.name != Key("Character") || bursts.ContainsKey(plant.GetInstanceId())) return;
                var fire = plant.componentManager?.GetRuntime<FireComponent>();
                if (fire == null) throw new InvalidOperationException("Super Gatling runtime has no FireComponent.");
                bursts.Add(plant.GetInstanceId(), new PowerBurst(context, plant, fire, Key("Projectile", "SuperPea"), powerPattern, guidance));
            }
            void Added(Node node)
            {
                if (node is not TowerDefenseCharacter plant || plant.config?.name != Key("Character")) return;
                if (plant.IsNodeReady()) Bind(plant); else plant.Ready += () => Bind(plant);
            }
            void Tick()
            {
                if (tree.Paused || Global.IsMultiplayerMode || !context.Game.TryGetBattle(out var battle) || !battle.Running || battle.Paused) return;
                guidance.Tick(surface.Root.GetPhysicsProcessDeltaTime());
                foreach (var pair in bursts.ToArray())
                {
                    if (!pair.Value.IsValid) { pair.Value.Dispose(); bursts.Remove(pair.Key); }
                    else pair.Value.Tick(surface.Root.GetPhysicsProcessDeltaTime());
                }
            }
            tree.NodeAdded += Added;
            tree.PhysicsFrame += Tick;
            foreach (var node in Nodes(tree.Root).ToArray()) Added(node);
            surface.Lifetime.Track(() => { tree.NodeAdded -= Added; tree.PhysicsFrame -= Tick; foreach (var burst in bursts.Values) burst.Dispose(); bursts.Clear(); guidance.Dispose(); if(ReferenceEquals(activeGuidance,guidance))activeGuidance=null; });
        }));
        context.Lifetime.Track(context.Hooks.Subscribe(XWModPresentationPoints.MainMenu, "super-gatling.menu", (_, surface) =>
        {
            if (XWModLevelSession.OwnerModId == context.ModId) XWModLevelSession.Clear();
            var box = surface.Lifetime.TrackNode(new Control { MouseFilter = Control.MouseFilterEnum.Ignore });
            surface.Root.AddChild(box);
            box.SetAnchorsAndOffsetsPreset(Control.LayoutPreset.BottomLeft);
            box.Position += new Vector2(16, -180);
            var button = GD.Load<PackedScene>("res://Prefab/GUI/Button/MainButton.tscn").Instantiate<MainButton>();
            box.AddChild(button); button.Name = "SuperGatlingLaunch"; button.text = "超级机枪体验"; button.Position = Vector2.Zero; button.Size = new Vector2(190, 46);
            button.Pressed += level.Launch;
            StartVerification(surface.Root.GetTree());
        }));
        ConfigureVerification();
        context.Log("SUPER_REGISTERED: own character, projectile, packet and GeneralPlant/Gold override");
    }

    partial void StartVerification(SceneTree tree);
    partial void ConfigureVerification();
    public void OnAllModsLoaded() { }
    public void Shutdown() { }

    void Publish(string category, GodotObject resource, string local = "SuperGatlingPea")
    {
        if (!context.Content.Provide(category, local, Variant.From(resource), out var error)) throw new InvalidOperationException(error);
    }

    void RegisterPlant()
    {
        var rm = ResourceManager.Instance;
        var data = AnimationDataFactory.Load(context);
        var bullet = (TowerDefenseProjectileConfig)rm.PROJECTILE_CONFIG["PeaDefault"].Duplicate(true);
        bullet.name = Key("Projectile", "SuperPea"); bullet.baseDamage = 20; Publish("Projectile", bullet, "SuperPea");
        var root = rm.GetCharacterScene("PlantPeaShooterSingle").Instantiate<TowerDefenseCharacter>();
        try
        {
            root.config = (TowerDefenseCharacterConfig)root.config.Duplicate(true);
            root.config.name = Key("Character"); root.config.hitpoints = 1000; root.config.hitpointsNearDeath = 0; root.config.cost = 250; root.config.packetCooldown = 30;
            root.ComponentSet = (CharacterComponentSet)root.ComponentSet.Duplicate(true);
            foreach (var sprite in Nodes(root).OfType<AdobeAnimateSprite>())
            {
                sprite.flashAnimeData = data;
                // Runtime rendering switches are not PackedScene storage
                // properties. Persist only our marker; apply after instancing.
                sprite.SetMeta(LocalRenderMarker, true);
                sprite.layerVisible = new(); for (int i = 0; i < data.layerDictionary.Count; i++) sprite.layerVisible.Add(true);
                sprite.mediaReplace = new(); sprite.mediaReplaceUse = new(); sprite.mediaReplaceAtlasPaths = new();
                for (int i = 0; i < data.mediaDictionary.Count; i++) { sprite.mediaReplace.Add(null!); sprite.mediaReplaceUse.Add(false); sprite.mediaReplaceAtlasPaths.Add(""); }
                sprite.offset = new Vector2(-38, -45); sprite.Scale = Vector2.One;
                if (sprite.Name == "Head")
                {
                    var body = (AdobeAnimateSprite)sprite.GetParent();
                    int stemLayer = data.layerDictionary["anim_idle"].AsInt32();
                    sprite.parentSprite = body;
                    sprite.followParentSpriteLayerId = stemLayer;
                    sprite.insertLayerId = stemLayer;
                    sprite.usePos = true;
                    // Raw head coordinates already include the stem's reference
                    // position. Remove it once; the host supplies the live pose.
                    sprite.offset = -AnimationDataFactory.StemReference;
                    sprite.Position = body.offset + AnimationDataFactory.StemReference;
                    sprite.clip = "HeadIdle";
                }
                else sprite.clip = "BodyIdle";
            }
            var head = root.GetNode<AdobeAnimateSprite>("SpriteGroup/TransformPoint/PeaShooterSingle/Head");
            // Source mouth image is 52x60; (38,30) lies at its forward opening.
            // Slot offsets are transformed by the current layer pose, including
            // the head's reference compensation. Marker remains the native API.
            var muzzle = new AdobeAnimateSlot { Name = "SuperMuzzle", mode = 0,
                followSlotId = data.layerDictionary["GatlingPea_mouth"].AsInt32() + 1,
                offset = new Vector2(38, 30), useRotate = false, useScale = false,
                useFollowVisible = false, updateAllFrame = true };
            head.AddChild(muzzle); muzzle.Owner = root;
            var marker = new Marker2D { Name = "FirePoint" };
            muzzle.AddChild(marker); marker.Owner = root;
            foreach (var fire in root.ComponentSet.GetFlattenedDefinitions().OfType<FireComponentDefinition>())
            {
                fire.fireIntervalBase = fire.fireInterval = 2; fire.fireIntervalOffset = 0;
                fire.fireNum = 1; fire.fireNumAtOnce = false; fire.fireAnimeTimeScale = 2.1f;
                fire.fireAnimationStartPosition = 0; fire.fireEventName = "fire";
                fire.fireAnimeClips = "HeadFire"; fire.fireAnimeClipsArray = new() { "HeadFire" }; fire.spliceIdleAnimeClips = "HeadIdle";
                foreach (var check in fire.fireCheckList) check.projectile.Set("projectileName", Key("Projectile", "SuperPea"));
                fire.fireProjectileList = new() { new FireComponentFireProjectileConfig { checkProjectileId = 0, firePosId = 0, speed = 300, dir = 0, offsetLine = 0, fireNumSkip = -1, fireEventNeed = "" } };
                fire.firePosMarkerPaths = new() { root.GetPathTo(marker) };
            }
            var scene = new PackedScene(); if (scene.Pack(root) != Error.Ok) throw new InvalidOperationException("Character packing failed."); Publish("Character", scene);
            var visual = (AdobeAnimateSprite)root.GetNode("SpriteGroup/TransformPoint/PeaShooterSingle").Duplicate();
            foreach (var node in Nodes(visual)) node.Owner = visual;
            var preview = new PackedScene(); if (preview.Pack(visual) != Error.Ok) throw new InvalidOperationException("Preview packing failed."); Publish("CharacterSprite", preview); visual.Free();
            var packet = (TowerDefensePacketConfig)rm.TOWERDEFENSE_PACKETS["PlantPeaShooterSingle"].Duplicate(true);
            packet.saveKey = Key("Packet"); packet.name = "超级机枪射手"; packet.characterConfig = root.config; packet.unlockCheckList = new();
            packet.describe = "七连发；10%概率大招，0.1秒一轮弱追踪扇形编排";
            packet.handbookDescribe = "韧性1000，伤害20×7，单行索敌；大招在1秒窗口内每0.1秒启动30发编排，共300发；组内时差保留，延迟项继续发完。费用250、冷却30秒为本案例适配值。";
            Publish("Packet", packet);
        }
        finally { root.Free(); }
        var bank = (TowerDefensePacketBankData)rm.TOWERDEFENSE_PACKETBANKS["GeneralPlant"].Duplicate(true);
        var gold = bank.category["Gold"].AsGodotArray();
        if (!gold.Any(item => item.AsString() == Key("Packet"))) gold.Add(Key("Packet"));
        bank.category["Gold"] = gold;
        if (!context.Content.Override(new XWModContentId("", "PacketBank", "GeneralPlant"), Variant.From(bank), out var diagnostic)) throw new InvalidOperationException(diagnostic);
    }
}
