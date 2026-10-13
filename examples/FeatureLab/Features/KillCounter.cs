using Godot;
using PVZHE.ModEditor.ModSystem;

namespace FeatureLab.Features;

/// <summary>敌方僵尸确认死亡；每个实体每个生命阶段一次，复活后可再次计数。</summary>
public sealed class KillCounter
{
    private readonly XWModRuntimeContext _context;
    private readonly HashSet<XWModEntityHandle> _counted = new();
    private readonly HashSet<string> _zombieKeys;
    private readonly XWModDataKey<int> _dataKey;
    private Label? _label;
    private bool _ended;
    public int Count { get; private set; }

    public KillCounter(XWModRuntimeContext context)
    {
        _context = context;
        _zombieKeys = ResourceManager.Instance.TOWERDEFENSE_PACKETS.Values
            .OfType<TowerDefensePacketConfig>().Where(p => p.characterConfig is TowerDefenseZombieConfig)
            .Select(p => p.characterConfig.name).ToHashSet(StringComparer.Ordinal);
        _dataKey = context.Data.Declare("killCount", 1,
            new XWModCodec<int>(BitConverter.GetBytes, bytes => BitConverter.ToInt32(bytes.Span), value => value >= 0));
        context.Lifetime.Track(() => _ended = true);
        context.Lifetime.Track(context.Hooks.Subscribe(XWModLifecyclePoints.Ready, "kills.reset", (_, _) => Reset(false)));
        context.Lifetime.Track(context.Hooks.Subscribe(XWModLifecyclePoints.Restored, "kills.restore", (_, _) => Reset(true)));
        context.Lifetime.Track(context.Hooks.Subscribe(XWModCharacterPoints.Lifecycle, "kills.observe", Observe));
        context.Lifetime.Track(context.Hooks.Subscribe(XWModPresentationPoints.BattleHud, "kills.hud", (_, surface) =>
        {
            var label = surface.Lifetime.TrackNode(new Label
            {
                Name = "FeatureLabKillCount", MouseFilter = Control.MouseFilterEnum.Ignore,
                HorizontalAlignment = HorizontalAlignment.Right
            });
            surface.Root.AddChild(label);
            label.AddThemeColorOverride("font_outline_color", Colors.Black);
            label.AddThemeConstantOverride("outline_size", 4);
            label.SetAnchorsAndOffsetsPreset(Control.LayoutPreset.BottomRight);
            label.OffsetLeft = -300; label.OffsetTop = -96; label.OffsetRight = -48; label.OffsetBottom = -60;
            _label = label;
            surface.Lifetime.Track(() => { if (ReferenceEquals(_label, label)) _label = null; });
            Refresh();
            context.Log("LAB_HUD: kill counter mounted");
        }));
        void SettingsChanged(IReadOnlyList<string> _) => Refresh();
        context.Settings.Changed += SettingsChanged;
        context.Lifetime.Track(() => context.Settings.Changed -= SettingsChanged);
    }

    private void Reset(bool restored)
    {
        _counted.Clear();
        Count = restored && _context.Data.TryRead(_dataKey, XWModDataScope.Battle, out int saved, out _) ? saved : 0;
        Refresh();
        _context.Log("LAB_BATTLE: " + (restored ? "restored" : "new round") + "; count=" + Count);
    }

    private void Observe(XWModEventContext eventContext, XWModCharacterLifecycleEvent value)
    {
        if (eventContext.Origin != XWModEventOrigin.Gameplay) return;
        if (value.Phase == "revived") { _counted.Remove(value.Character.Handle); return; }
        if (value.Phase != "death-committed" || value.Character.Camp != (int)TowerDefenseEnum.CHARACTER_CAMP.ZOMBIE
            || !_zombieKeys.Contains(value.Character.ContentKey) || !_counted.Add(value.Character.Handle)) return;
        Count++;
        Refresh();
        _context.Log("LAB_KILL: count=" + Count + "; key=" + value.Character.ContentKey);
        Persist();
    }

    private async void Persist()
    {
        try
        {
            var result = await _context.Data.WriteBattleAsync(_dataKey, Count);
            if (!_ended && !result.Succeeded) _context.Warn("kill count save failed: " + result.Diagnostic);
        }
        catch (Exception error) { if (!_ended) _context.Warn("kill count save failed: " + error.Message); }
    }

    public void Refresh()
    {
        if (!GodotObject.IsInstanceValid(_label)) return;
        _label!.Text = "本局击杀：" + Count;
        _label.Visible = _context.Settings.Get<bool>("showKills");
    }
}
