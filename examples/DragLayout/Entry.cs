using Godot;
using PVZHE.ModEditor.ModSystem;
using ModTemplate.RuntimeUi;

namespace DragLayoutDemo;

public sealed partial class Entry : IXWModRuntimeEntry
{
    XWModRuntimeContext context=null!;
    DragLayout layouts=null!;
    internal MainButton? button;
    internal Label? status;
    internal Control? root;
    internal DragBinding? buttonDrag,statusDrag;
    internal int clicks;
    public void Initialize(XWModRuntimeContext value)
    {
        context=value;layouts=new DragLayout(context);
        var config=Json.ParseString(File.ReadAllText(Path.Combine(context.PackageRoot,"Assets","ui-layout.json"))).AsGodotDictionary();
        if(config["modId"].AsString()!=context.ModId)throw new InvalidOperationException("Layout defaults identity mismatch");
        var defaults=config["placements"].AsGodotDictionary();
        context.Lifetime.Track(context.Hooks.Subscribe(XWModPresentationPoints.MainMenu,"drag-demo.menu",(_,surface)=>
        {
            root=surface.Lifetime.TrackNode(new Control{Name="DragDemoRoot",MouseFilter=Control.MouseFilterEnum.Ignore});
            surface.Root.AddChild(root);root.SetAnchorsAndOffsetsPreset(Control.LayoutPreset.FullRect);
            button=surface.Lifetime.TrackNode(GD.Load<PackedScene>("res://Prefab/GUI/Button/MainButton.tscn").Instantiate<MainButton>());
            root.AddChild(button);button.Name="DragDemoHello";button.text="Hello World";button.Position=Vector2.Zero;button.Size=new Vector2(170,46);
            button.TooltipText="按住鼠标中键拖动；左键打开弹窗";
            button.Pressed+=Clicked;
            surface.Lifetime.Track(()=>{if(GodotObject.IsInstanceValid(button))button.Pressed-=Clicked;});
            status=surface.Lifetime.TrackNode(new Label{Name="DragDemoStatus",Text="中键拖动此文字",MouseFilter=Control.MouseFilterEnum.Stop});
            root.AddChild(status);status.Size=new Vector2(190,32);
            buttonDrag=layouts.Attach(button,root,"main-menu","default","hello",Placement.From(defaults["main-menu/default/hello"].AsGodotDictionary()));
            statusDrag=layouts.Attach(status,root,"main-menu","default","status",Placement.From(defaults["main-menu/default/status"].AsGodotDictionary()));
            surface.Lifetime.Track(buttonDrag.Dispose);surface.Lifetime.Track(statusDrag.Dispose);
            StartVerification(root.GetTree());
        }));
    }
    void Clicked()
    {
        clicks++;
        if(DialogManager.Instance.HasOpenDialogs)return;
        var dialog=(DialogBoxTips)DialogManager.Instance.DialogCreate("DialogBoxTips");dialog.text="Hello World";
    }
    partial void StartVerification(SceneTree tree);
    public void OnAllModsLoaded(){}
    public void Shutdown(){}
}
