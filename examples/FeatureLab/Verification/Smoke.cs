using Godot;
using PVZHE.ModEditor.ModSystem;
using FeatureLab.Features;

namespace FeatureLab.Verification;

/// <summary>显式 --feature-lab-test 才执行；不改变普通玩家的对局。</summary>
public static class Smoke
{
    private static void Require(bool condition, string message)
    {
        if (!condition) throw new InvalidOperationException(message);
    }

    private static async Task Wait(SceneTree tree, double seconds) =>
        await tree.ToSignal(tree.CreateTimer(seconds, true, false, true), SceneTreeTimer.SignalName.Timeout);

    private static async Task Screenshot(SceneTree tree, string name)
    {
        await tree.ToSignal(RenderingServer.Singleton, RenderingServer.SignalName.FramePostDraw);
        using var image = tree.Root.GetTexture().GetImage();
        Require(image.SavePng("user://" + name + ".png") == Error.Ok, "Screenshot failed: " + name);
    }

    public static async void Run(XWModRuntimeContext context, SceneTree tree, DemoLevel level, KillCounter kills)
    {
        try
        {
            await Wait(tree, 5);
            // 独立测试存档的首次用户名提示，走宿主关闭方法恢复状态，不填写个人信息。
            CloseDialogs(tree.Root);
            await Wait(tree, 0.5);
            var help = tree.Root.FindChild("FeatureLabHelp", true, false) as MainButton;
            Require(help != null, "Help button absent");
            bool pausedBefore = tree.Paused;
            help!.EmitSignal(BaseButton.SignalName.Pressed);
            await Wait(tree, 0.5);
            Require(DialogManager.Instance.HasOpenDialogs, "Original dialog did not open");
            await Screenshot(tree, "ui-dialog");
            CloseDialogs(tree.Root);
            await Wait(tree, 0.3);
            Require(tree.Paused == pausedBefore, "Dialog failed to restore pause state");
            var toggle = tree.Root.FindChild("FeatureLabToggle", true, false) as MainButton;
            Require(toggle != null, "Toggle button absent");
            bool old = context.Settings.Get<bool>("showKills");
            toggle!.EmitSignal(BaseButton.SignalName.Pressed);
            Require(context.Settings.Get<bool>("showKills") == !old, "Immediate setting did not apply");
            toggle.EmitSignal(BaseButton.SignalName.Pressed);
            Require(context.Settings.Get<bool>("showKills") == old, "Setting did not restore");
            level.OpenBrowser();
            await Wait(tree, 4);
            Require(SceneManager.CurrentScene == "LevelChoose", "Mod level browser failed");
            var chooser = Descendants(tree.Root).OfType<LevelChoose>().Single();
            var catalog = chooser.GetNode<VBoxContainer>("ModBrowser/Panel/Scroll/Catalogs")
                .GetChildren().OfType<Button>().Single(x => x.Text.Contains("功能实验关卡"));
            catalog.EmitSignal(BaseButton.SignalName.Pressed);
            await Wait(tree, 1);
            Require(!chooser.GetNode<CanvasLayer>("ModBrowser").Visible, "Catalog did not open");
            var chapterItem = Descendants(chooser).OfType<DragMenuSelectItemChapter>().Single();
            Require(chapterItem.sprite.Texture != null && chapterItem.buttonNode.Size.X > 0, "Invisible chapter entry");
            chapterItem.buttonNode.EmitSignal(BaseButton.SignalName.Pressed);
            await Wait(tree, 1);
            var levelItem = Descendants(chooser).OfType<DragMenuSelectItemlevel>().First(x => x.IsVisibleInTree());
            Require(levelItem.sprite.Texture != null && levelItem.buttonNode.Size.X > 0, "Invisible level entry");
            await Screenshot(tree, "level-browser");
            levelItem.buttonNode.EmitSignal(BaseButton.SignalName.Pressed);
            for (int i = 0; i < 100; i++)
            {
                await Wait(tree, 0.2);
                if (context.Game.TryGetBattle(out var battle) && battle.Running) break;
            }
            Require(context.Game.TryGetBattle(out var running) && running.Running, "Battle did not start");
            Require(TowerDefenseManager.Instance.currentLevelConfig.name == level.Config.name, "Wrong level identity");
            var seedBank = TowerDefenseManager.Instance.GetSeedBankFeature();
            Require(seedBank?.seedBank.packetList.Count == 1, "Preset seed bank must contain one card");
            for (int i = 0; i < 30 && !seedBank!.seedBank.packetList[0].IsVisibleInTree(); i++) await Wait(tree, 0.2);
            context.Log("LAB_TEST_CARD: registeredKey=PlantFirenut; name=" + seedBank!.seedBank.packetList[0].config.name +
                "; visible=" + seedBank.seedBank.packetList[0].IsVisibleInTree());
            var expectedCard = TowerDefenseManager.GetPacketConfigReadOnly("PlantFirenut");
            Require(seedBank!.seedBank.packetList[0].config.saveKey == expectedCard.saveKey &&
                seedBank.seedBank.packetList[0].config.characterConfig.name == expectedCard.characterConfig.name &&
                seedBank.seedBank.packetList[0].IsVisibleInTree(), "Preset card is missing or invisible");
            var hud = tree.Root.FindChild("FeatureLabKillCount", true, false) as Label;
            Require(hud != null && hud.Text.EndsWith("0"), "HUD did not start at zero");
            Require(context.Game.Economy.TryGetBalance(out long balance) && balance == 350, "Starting sun must be 300 + 50");
            context.Log("LAB_TEST_BALANCE: " + balance);
            bool resultObserved = false;
            var handledPauses = new HashSet<ulong>();
            // 订阅在 Initialize 才能建立；结果证据由常驻入口订阅输出，下面读取宿主终态。
            for (int i = 0; i < 180 && kills.Count < 2; i++)
            {
                await Wait(tree, 0.2);
                var prompt = Descendants(tree.Root).OfType<DialogBoxBase>().FirstOrDefault(d => d.GetType().Name == "DialogBoxGamePause");
                if (prompt != null && handledPauses.Add(prompt.GetInstanceId()))
                {
                    Require(handledPauses.Count <= 4, "Repeated environment pause prompts");
                    context.Log("LAB_ENV_PAUSE: known game pause prompt; treePaused=" + tree.Paused);
                    tree.Root.GrabFocus();
                    prompt.CloseDialog();
                }
                if (i == 0) context.Log("LAB_BATTLE_DIAGNOSTIC: treePaused=" + tree.Paused + "; battlePaused=" + (context.Game.TryGetBattle(out var state) && state.Paused) + "; dialogs=" + DialogManager.Instance.HasOpenDialogs);
                foreach (var zombie in context.Game.Characters.Query().Where(x => x.Camp == 1 && !x.Dead && !x.Removing))
                {
                    var damage = await context.Game.Combat.Damage(zombie.Handle, 100000);
                    Require(damage.Succeeded, "Host damage command failed: " + damage.Diagnostic);
                }
            }
            Require(kills.Count == 2, "Expected exactly two committed zombie deaths");
            Require(hud!.Text.EndsWith("2"), "HUD count did not update");
            Require(context.Settings.TrySave(new Dictionary<string, object> { ["showKills"] = false }, out _), "Hide setting failed");
            Require(!hud.Visible, "HUD should hide immediately");
            Require(context.Settings.TrySave(new Dictionary<string, object> { ["showKills"] = true }, out _), "Show setting failed");
            Require(hud.Visible, "HUD should show immediately");
            await Screenshot(tree, "battle-hud");
            for (int i = 0; i < 100; i++)
            {
                await Wait(tree, 0.2);
                if (TowerDefenseManager.CurrentControl?.HasBattleAwarded == true) { resultObserved = true; break; }
            }
            Require(resultObserved, "Level did not reach victory");
            Require(context.Settings.TrySave(new Dictionary<string, object> { ["showKills"] = false, ["bonusSun"] = 75 }, out var saved), "Persistence preparation failed");
            Require(saved.RestartRequired && context.Settings.Get<int>("bonusSun") == 50, "Restart setting applied too early");
            context.Log("LAB_TEST_PASS: UI, settings, catalog, battle, sun, two deaths and victory verified");
            tree.Quit();
        }
        catch (Exception error)
        {
            context.Log("LAB_TEST_ERROR: " + error);
            await Screenshot(tree, "feature-lab-failed");
            tree.Quit(2);
        }
    }

    public static async void RunPersistence(XWModRuntimeContext context, SceneTree tree)
    {
        try
        {
            await Wait(tree, 5);
            Require(!context.Settings.Get<bool>("showKills"), "Bool setting did not survive restart");
            Require(context.Settings.Get<int>("bonusSun") == 75, "Restart setting was not loaded");
            context.Log("LAB_PERSIST_PASS: showKills=false; bonusSun=75 after real process restart");
            tree.Quit();
        }
        catch (Exception error) { context.Log("LAB_TEST_ERROR: " + error); tree.Quit(2); }
    }

    private static void CloseDialogs(Node node)
    {
        foreach (var child in node.GetChildren()) CloseDialogs(child);
        if (node is DialogBoxBase dialog && !dialog.IsQueuedForDeletion()) dialog.CloseDialog();
    }

    private static IEnumerable<Node> Descendants(Node node)
    {
        foreach (var child in node.GetChildren())
        {
            yield return child;
            foreach (var descendant in Descendants(child)) yield return descendant;
        }
    }
}
