using PVZHE.ModEditor.ModSystem;

namespace FeatureLab.Features;

/// <summary>只对全新单人对局增加一次阳光；读档不会再次发放。</summary>
public sealed class StartingSun
{
    private readonly XWModRuntimeContext _context;
    private readonly XWModEconomyService _economy;
    private bool _ended;

    public StartingSun(XWModRuntimeContext context)
    {
        _context = context;
        _economy = context.Game.Economy;
        context.Lifetime.Track(() => _ended = true);
        context.Lifetime.Track(context.Hooks.Subscribe(XWModLifecyclePoints.Ready, "sun.bonus", (_, _) => Apply()));
    }

    private async void Apply()
    {
        if (Global.IsMultiplayerMode) return;
        try
        {
            int amount = _context.Settings.Get<int>("bonusSun");
            _economy.TryGetBalance(out long before);
            var result = await _economy.Credit(amount);
            if (_ended) return;
            if (!result.Succeeded) throw new InvalidOperationException(result.Diagnostic);
            _economy.TryGetBalance(out long after);
            _context.Log($"LAB_BONUS: amount={amount}; before={before}; after={after}");
        }
        catch (Exception error) { if (!_ended) _context.Warn("starting sun failed: " + error.Message); }
    }
}
