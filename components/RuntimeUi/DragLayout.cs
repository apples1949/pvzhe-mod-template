using Godot;
using PVZHE.ModEditor.ModSystem;

namespace ModTemplate.RuntimeUi;

/// <summary>One instance per Mod runtime, declared during Initialize; data is local, not battle save data.</summary>
public sealed class DragLayout
{
    readonly XWModRuntimeContext context;
    readonly XWModDataKey<string> key;
    readonly Godot.Collections.Dictionary placements = new();
    long sequence;
    public string SessionId { get; } = Guid.NewGuid().ToString("N");
    public string BinarySha256 { get; }

    public DragLayout(XWModRuntimeContext context)
    {
        this.context = context;
        using var stream = File.OpenRead(Path.Combine(context.PackageRoot,"Runtime","ModAssembly.dll"));
        BinarySha256 = Convert.ToHexString(System.Security.Cryptography.SHA256.HashData(stream)).ToLowerInvariant();
        key = context.Data.Declare("ui.layout",1,new XWModCodec<string>(System.Text.Encoding.UTF8.GetBytes,
            bytes=>System.Text.Encoding.UTF8.GetString(bytes.Span), value=>value.Length<=60000));
        if(context.Data.TryRead(key,XWModDataScope.Local,out string saved,out _) && !string.IsNullOrEmpty(saved))
        {
            var parsed=Json.ParseString(saved);
            if(parsed.VariantType==Variant.Type.Dictionary)
                foreach(var pair in parsed.AsGodotDictionary())placements[pair.Key]=pair.Value;
            else context.Warn("UI_LAYOUT_DATA_INVALID: expected dictionary");
        }
        context.Log("UI_LAYOUT_READY: "+Json.Stringify(new Godot.Collections.Dictionary{
            {"schemaVersion",1},{"modId",context.ModId},{"sessionId",SessionId},{"binarySha256",BinarySha256}}));
    }

    static string Slot(string scene,string layout,string component)=>scene+"/"+layout+"/"+component;
    public static void CheckId(string value)
    {
        if(string.IsNullOrEmpty(value)||value.Length>80)throw new ArgumentException("Layout ID must contain 1..80 ASCII letters, digits, underscore, dash or dot.");
        foreach(char c in value)if(!char.IsAsciiLetterOrDigit(c)&&c!='_'&&c!='-'&&c!='.')throw new ArgumentException("Invalid layout ID: "+value);
    }
    internal Placement Read(string scene,string layout,string component,Placement fallback)
    {
        var slot=Slot(scene,layout,component);
        if(!placements.TryGetValue(slot,out var v))return fallback;
        if(v.VariantType!=Variant.Type.Dictionary){context.Warn("UI_LAYOUT_DATA_INVALID: "+slot+" expected placement dictionary");return fallback;}
        try{return Placement.From(v.AsGodotDictionary());}
        catch(Exception error){context.Warn("UI_LAYOUT_DATA_INVALID: "+slot+" "+error.Message);return fallback;}
    }
    internal void Commit(string scene,string layout,string component,Placement placement,Vector2 parentSize,Vector2 size,string reason)
    {
        placements[Slot(scene,layout,component)]=placement.ToDictionary();
        bool persisted=context.Data.TryWrite(key,XWModDataScope.Local,Json.Stringify(placements),out var diagnostic);
        if(!persisted)context.Warn("UI_LAYOUT_SAVE_FAILED: "+diagnostic);
        var change=placement.ToDictionary();
        change["schemaVersion"]=1;change["modId"]=context.ModId;change["componentId"]=component;
        change["sceneId"]=scene;change["layoutId"]=layout;change["sessionId"]=SessionId;
        change["binarySha256"]=BinarySha256;change["sequence"]=++sequence;change["reason"]=reason;
        change["coordinateSpace"]="parent-logical-pixels";change["persisted"]=persisted;
        change["parentSize"]=new Godot.Collections.Array{parentSize.X,parentSize.Y};
        change["size"]=new Godot.Collections.Array{size.X,size.Y};
        context.Log("UI_LAYOUT_CHANGED: "+Json.Stringify(change));
    }
    public DragBinding Attach(Control control,Control parent,string scene,string layout,string component,Placement defaults,Func<bool>? canDrag=null)
        =>new(this,control,parent,scene,layout,component,defaults,canDrag);
}

public readonly record struct Placement(float RightInset,float VerticalInset,bool Bottom=false)
{
    public void Validate()
    {
        if(!float.IsFinite(RightInset)||!float.IsFinite(VerticalInset)||Math.Abs(RightInset)>100000||Math.Abs(VerticalInset)>100000)
            throw new ArgumentException("Invalid logical layout offset.");
    }
    public Godot.Collections.Dictionary ToDictionary()=>new(){
        {"anchorX","right"},{"anchorY",Bottom?"bottom":"top"},{"rightInset",RightInset},{"verticalInset",VerticalInset}};
    public static Placement From(Godot.Collections.Dictionary value)
    {
        foreach(var field in new[]{"anchorX","anchorY","rightInset","verticalInset"})
            if(!value.ContainsKey(field))throw new ArgumentException("Missing placement field: "+field);
        foreach(var field in new[]{"rightInset","verticalInset"})
            if(value[field].VariantType!=Variant.Type.Float&&value[field].VariantType!=Variant.Type.Int)throw new ArgumentException("Invalid numeric placement field: "+field);
        if(value["anchorX"].AsString()!="right")throw new ArgumentException("Horizontal anchor must be right.");
        string y=value["anchorY"].AsString();
        if(y!="top"&&y!="bottom")throw new ArgumentException("Invalid vertical anchor.");
        var result=new Placement(value["rightInset"].AsSingle(),value["verticalInset"].AsSingle(),y=="bottom");
        result.Validate();return result;
    }
}

/// <summary>Free-positioned UI in its Window viewport; no reparenting or host input-map changes.</summary>
public sealed class DragBinding : IDisposable
{
    readonly DragLayout owner;
    readonly Control control,parent;
    readonly Window window;
    readonly string scene,layout,component;
    readonly Placement defaults;
    readonly Func<bool> allowed;
    readonly Control.MouseFilterEnum previousFilter;
    Placement saved;
    Vector2 grab;
    bool disposed,applying;
    public bool Dragging { get; private set; }
    public string LastCancellation { get; private set; }="";
    public Placement Current=>saved;

    internal DragBinding(DragLayout owner,Control control,Control parent,string scene,string layout,string component,Placement defaults,Func<bool>? allowed)
    {
        foreach(var id in new[]{scene,layout,component})DragLayout.CheckId(id);
        defaults.Validate();
        if(control.GetParent()!=parent||parent is Container)throw new ArgumentException("Use a free-positioned Control parent, not a Container.");
        window=control.GetWindow();
        if(control.GetViewport()!=window)throw new ArgumentException("Nested SubViewport input needs a separate adapter.");
        this.owner=owner;this.control=control;this.parent=parent;this.scene=scene;this.layout=layout;this.component=component;
        this.defaults=defaults;this.allowed=allowed??(()=>!DialogManager.Instance.HasOpenDialogs);
        saved=owner.Read(scene,layout,component,defaults);
        previousFilter=control.MouseFilter;
        if(previousFilter==Control.MouseFilterEnum.Ignore)control.MouseFilter=Control.MouseFilterEnum.Stop;
        control.GuiInput+=Gui;
        window.FocusExited+=LostFocus;control.VisibilityChanged+=Visibility;
        parent.Resized+=Resize;control.Resized+=Resize;control.TreeExiting+=Dispose;
        Apply();
    }
    Vector2 Local(Vector2 viewport)=>parent.GetGlobalTransformWithCanvas().AffineInverse()*viewport;
    bool Usable()=>!disposed&&GodotObject.IsInstanceValid(control)&&control.IsVisibleInTree()&&allowed();
    Vector2 Clamp(Vector2 position)=>new(Math.Clamp(position.X,0,Math.Max(0,parent.Size.X-control.Size.X)),Math.Clamp(position.Y,0,Math.Max(0,parent.Size.Y-control.Size.Y)));
    void Gui(InputEvent input)
    {
        // Godot retains GUI mouse focus until the pressed button is released,
        // including movement outside the original rectangle. All positions here
        // are control-local, not raw WindowInput pixels before viewport stretch.
        if(!Dragging)
        {
            if(input is not InputEventMouseButton {ButtonIndex:MouseButton.Middle,Pressed:true} down||!Usable())return;
            grab=Local(control.GetGlobalTransformWithCanvas()*down.Position)-control.Position;
            Dragging=true;control.AcceptEvent();return;
        }
        if(!Usable()){CancelWith("inactive-or-modal");return;}
        if(input is InputEventKey {Pressed:true,Keycode:Key.Escape}){control.AcceptEvent();Cancel();return;}
        if(input is InputEventMouseMotion motion)
        {
            if((motion.ButtonMask&MouseButtonMask.Middle)==0){CancelWith("button-mask-"+motion.Device);return;}
            control.Position=Clamp(Local(control.GetGlobalTransformWithCanvas()*motion.Position)-grab);control.AcceptEvent();
        }
        else if(input is InputEventMouseButton {ButtonIndex:MouseButton.Middle,Pressed:false} mouse)
        {
            control.Position=Clamp(Local(control.GetGlobalTransformWithCanvas()*mouse.Position)-grab);Dragging=false;control.AcceptEvent();
            var next=new Placement(parent.Size.X-control.Position.X-control.Size.X,
                saved.Bottom?parent.Size.Y-control.Position.Y-control.Size.Y:control.Position.Y,saved.Bottom);
            if(Math.Abs(next.RightInset-saved.RightInset)>.01f||Math.Abs(next.VerticalInset-saved.VerticalInset)>.01f)
            {saved=next;owner.Commit(scene,layout,component,saved,parent.Size,control.Size,"middle-drag");}
            Apply();
        }
        else if(input is InputEventMouseButton)control.AcceptEvent();
    }
    void Resize(){if(!applying&&!Dragging)Apply();}
    void Visibility(){if(!control.IsVisibleInTree())CancelWith("hidden");}
    void LostFocus()=>CancelWith("focus-exited");
    void CancelWith(string reason){if(disposed)return;LastCancellation=reason;Dragging=false;Apply();}
    public void Cancel()=>CancelWith("caller");
    public void Reset()
    {
        if(disposed)return;
        Dragging=false;saved=defaults;Apply();owner.Commit(scene,layout,component,saved,parent.Size,control.Size,"reset-default");
    }
    void Apply()
    {
        if(disposed||applying)return;applying=true;
        try
        {
            var position=Clamp(new Vector2(parent.Size.X-control.Size.X-saved.RightInset,
                saved.Bottom?parent.Size.Y-control.Size.Y-saved.VerticalInset:saved.VerticalInset));
            control.AnchorLeft=control.AnchorRight=1;
            control.AnchorTop=control.AnchorBottom=saved.Bottom?1:0;
            control.Position=position;
        }
        finally{applying=false;}
    }
    public void Dispose()
    {
        if(disposed)return;Cancel();disposed=true;
        if(GodotObject.IsInstanceValid(control))
        {control.GuiInput-=Gui;control.VisibilityChanged-=Visibility;control.Resized-=Resize;control.TreeExiting-=Dispose;control.MouseFilter=previousFilter;}
        if(GodotObject.IsInstanceValid(parent))parent.Resized-=Resize;
        if(GodotObject.IsInstanceValid(window))window.FocusExited-=LostFocus;
    }
}
