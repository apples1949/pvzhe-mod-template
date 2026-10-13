using Godot;
using PVZHE.ModEditor.ModSystem;

namespace FeatureLab.Adapters;

/// <summary>0.30.0 的原版 UI 接口适配；资源仍来自宿主 PCK。</summary>
public static class HostUi
{
    public const string MainButtonPath = "res://Prefab/GUI/Button/MainButton.tscn";

    public static MainButton AddButton(Control parent, XWModLifetime scope,
        string name, string text, Vector2 position, Action pressed)
    {
        var scene = ResourceLoader.Load<PackedScene>(MainButtonPath)
            ?? throw new InvalidOperationException("Released MainButton scene is unavailable.");
        var button = scope.TrackNode(scene.Instantiate<MainButton>());
        button.Name = name;
        button.text = text;
        parent.AddChild(button);
        button.Position = position;
        button.Size = new Vector2(190, 46);
        button.Pressed += pressed;
        scope.Track(() => { if (GodotObject.IsInstanceValid(button)) button.Pressed -= pressed; });
        return button;
    }

    public static DialogBoxTips ShowTips(XWModLifetime scope, string text)
    {
        var dialog = DialogManager.Instance?.DialogCreate("DialogBoxTips") as DialogBoxTips
            ?? throw new InvalidOperationException("Released dialog service is unavailable.");
        dialog.text = text;
        // 正常关闭要走宿主 CloseDialog：QueueFree 不会恢复暂停/TimeScale。
        scope.Track(() =>
        {
            if (GodotObject.IsInstanceValid(dialog) && !dialog.IsQueuedForDeletion()) dialog.CloseDialog();
        });
        return dialog;
    }
}
