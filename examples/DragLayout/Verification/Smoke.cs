using Godot;
using ModTemplate.RuntimeUi;

namespace DragLayoutDemo;

public sealed partial class Entry
{
    bool started;
    static void Check(bool value,string message){if(!value)throw new Exception(message);}
    static async Task Wait(SceneTree tree,double seconds)=>await tree.ToSignal(tree.CreateTimer(seconds,true,false,true),SceneTreeTimer.SignalName.Timeout);
    static IEnumerable<Node> Nodes(Node root){foreach(var child in root.GetChildren()){yield return child;foreach(var n in Nodes(child))yield return n;}}
    async Task Until(SceneTree tree,Func<bool> condition,string message)
    {for(int n=0;n<100;n++){if(condition())return;await Wait(tree,.1);}throw new Exception(message);}
    partial void StartVerification(SceneTree tree)
    {
        if(started||context.ModId!="drag-layout-demo"||!OS.GetCmdlineUserArgs().Contains("--drag-audit"))return;
        started=true;_ = Run(tree);
    }
    void Send(SceneTree tree,Vector2 position,MouseButton key,bool pressed)
    {
        if(pressed)tree.Root.PushInput(new InputEventMouseMotion{Position=position,GlobalPosition=position},true);
        tree.Root.PushInput(new InputEventMouseButton{Position=position,GlobalPosition=position,ButtonIndex=key,Pressed=pressed},true);
    }
    void Motion(SceneTree tree,Vector2 position)=>tree.Root.PushInput(new InputEventMouseMotion{
        Position=position,GlobalPosition=position,ButtonMask=MouseButtonMask.Middle},true);
    static Vector2 Center(Control control)=>control.GetGlobalTransformWithCanvas()*(control.Size/2);
    static void Rect(DragBinding drag,Control control,Control parent)
    {
        Check(control.AnchorLeft==1&&control.AnchorRight==1,"intermediate/left horizontal anchor");
        Check(Math.Abs(parent.Size.X-control.Position.X-control.Size.X-drag.Current.RightInset)<.05,"right inset mismatch");
    }
    async Task Run(SceneTree tree)
    {
        try
        {
            // Engine-synthetic GUI dispatch without depending on the desktop pointer's current window.
            // This is a fixture condition, not a production setting or system-mouse claim.
            tree.Root.GuiEmbedSubwindows=true;
            if(!OS.GetCmdlineUserArgs().Contains("--drag-restart"))
            {
                await Until(tree,()=>Nodes(tree.Root).OfType<DialogBoxNewUser>().Any(p=>p.nameLineEdit!=null),"new profile ready");
                var profile=Nodes(tree.Root).OfType<DialogBoxNewUser>().Single();
                profile.nameLineEdit.Text="DragAudit";profile.readyButtonNewUser.EmitSignal(BaseButton.SignalName.Pressed);
            }
            await Until(tree,()=>GameSaveManager.Instance.GetUserCurrent()=="DragAudit"&&!DialogManager.Instance.HasOpenDialogs&&!SceneManager.Instance.isLoading,"profile committed and menu ready");
            Rect(buttonDrag!,button!,root!);
            if(OS.GetCmdlineUserArgs().Contains("--drag-restart"))
            {
                Check(Math.Abs(buttonDrag!.Current.RightInset-177.75f)<.1&&Math.Abs(buttonDrag.Current.VerticalInset-220.25f)<.1,"restart did not restore layout");
                context.Log("DRAG_RESTART_PASS: local layout restored in second process");tree.Quit();return;
            }
            var at=Center(button!);
            tree.Root.NotifyMouseEntered();
            for(int n=0;n<100;n++)
            {
                tree.Root.PushInput(new InputEventMouseMotion{Position=at,GlobalPosition=at},true);
                await Wait(tree,.1);
                var hovered=tree.Root.GuiGetHoveredControl();
                if(n==0)context.Log("DRAG_HIT_DIAGNOSTIC: hovered="+hovered?.GetPath()+" viewport="+tree.Root.GetVisibleRect());
                if(hovered==button||(hovered!=null&&button!.IsAncestorOf(hovered)))break;
                if(n==99)throw new Exception("menu button not actually hittable; hovered="+hovered?.GetPath());
            }
            context.Log("DRAG_INPUT_DIAGNOSTIC: center="+at+" rect="+button!.GetGlobalRect()+" parent="+root!.Size+" window="+tree.Root.Size+" visible="+button.IsVisibleInTree()+" disabled="+button.Disabled);
            await tree.ToSignal(RenderingServer.Singleton,RenderingServer.SignalName.FramePostDraw);
            using(var image=tree.Root.GetTexture().GetImage())image.SavePng("user://drag-before.png");
            var otherButton=Nodes(tree.Root).OfType<MainButton>().Single(b=>b.Name=="DragDemoHello"&&b!=button);
            var otherAt=Center(otherButton);float otherRight=otherButton.OffsetRight;
            Send(tree,otherAt,MouseButton.Middle,true);Motion(tree,otherAt+new Vector2(-20,10));Send(tree,otherAt+new Vector2(-20,10),MouseButton.Middle,false);
            Check(Math.Abs(otherButton.OffsetRight-(otherRight-20))<.1,"other Mod did not independently drag");
            Send(tree,at,MouseButton.Left,true);Send(tree,at,MouseButton.Left,false);
            await Until(tree,()=>clicks==1&&DialogManager.Instance.HasOpenDialogs,"normal left click");
            var dialog=Nodes(tree.Root).OfType<DialogBoxTips>().Single();
            var before=button!.Position;Send(tree,at,MouseButton.Middle,true);Motion(tree,at+new Vector2(-80,20));Send(tree,at,MouseButton.Middle,false);
            Check(!buttonDrag!.Dragging&&button.Position.DistanceTo(before)<.01,"modal allowed drag");
            dialog.CloseDialog();await Wait(tree,.2);

            at=Center(button);Send(tree,at,MouseButton.Middle,true);Check(buttonDrag.Dragging,"middle press did not reach drag handle");
            var target=root!.GetGlobalTransformWithCanvas()*(button.Position+button.Size/2+new Vector2(-110.25f,51.5f));
            Motion(tree,target);Send(tree,target,MouseButton.Middle,false);
            Check(clicks==1,"drag invoked left-click command");
            Check(Math.Abs(buttonDrag.Current.RightInset-134.25f)<.1&&Math.Abs(buttonDrag.Current.VerticalInset-81.5f)<.1,"drag logical offset mismatch");
            Rect(buttonDrag,button,root);
            at=Center(button);Send(tree,at,MouseButton.Middle,true);Send(tree,at,MouseButton.Middle,false);

            var saved=buttonDrag.Current;at=Center(button);Send(tree,at,MouseButton.Middle,true);Motion(tree,at-new Vector2(80,0));buttonDrag.Cancel();
            Send(tree,at,MouseButton.Middle,false);Check(buttonDrag.Current==saved,"cancel changed saved layout");Rect(buttonDrag,button,root);
            root.Scale=new Vector2(.8f,.8f);await Wait(tree,.1);
            at=Center(status!);Send(tree,at,MouseButton.Middle,true);Check(statusDrag!.Dragging,"label is not draggable");
            target=root.GetGlobalTransformWithCanvas()*(status!.Position+status.Size/2+new Vector2(-25.5f,-12.25f));
            Motion(tree,target);Send(tree,target,MouseButton.Middle,false);
            Check(Math.Abs(statusDrag.Current.RightInset-885.5f)<.1&&Math.Abs(statusDrag.Current.VerticalInset-230.25f)<.1,"scaled-parent drag mismatch");
            root.Scale=Vector2.One;

            at=Center(button);Send(tree,at,MouseButton.Middle,true);
            target=root.GetGlobalTransformWithCanvas()*new Vector2(40+button.Size.X/2,251.5f+button.Size.Y/2);
            Motion(tree,target);Send(tree,target,MouseButton.Middle,false);
            Check(button.Position.X<root.Size.X/3,"left-region test prerequisite");Rect(buttonDrag,button,root);
            buttonDrag.Reset();Check(buttonDrag.Current==new Placement(24,30),"reset did not restore defaults");

            at=Center(button);Send(tree,at,MouseButton.Middle,true);
            void Trace(InputEvent e){if(e is InputEventMouseMotion m)context.Log("DRAG_EVENT: motion device="+m.Device+" mask="+m.ButtonMask+" p="+m.Position+" active="+buttonDrag.Dragging);else if(e is InputEventMouseButton b)context.Log("DRAG_EVENT: button="+b.ButtonIndex+" pressed="+b.Pressed+" active="+buttonDrag.Dragging);}
            button.GuiInput+=Trace;
            tree.Root.Size=new Vector2I(1200,700);await Wait(tree,.4);
            var prompts=Nodes(tree.Root).OfType<DialogBoxBase>().ToArray();
            foreach(var prompt in prompts)
            {
                context.Log("DRAG_RESIZE_MODAL: "+prompt.GetType().Name);
                Check(prompt.GetType().Name=="DialogBoxGamePause","unexpected resize modal: "+prompt.GetType().Name);
                tree.Root.GrabFocus();prompt.CloseDialog();
            }
            await Until(tree,()=>!DialogManager.Instance.HasOpenDialogs,"resize modal closed");
            context.Log("DRAG_RESIZE_DIAGNOSTIC: dragging="+buttonDrag.Dragging+" pos="+button.Position+" savedRight="+buttonDrag.Current.RightInset+" parent="+root.Size);
            target=root.GetGlobalTransformWithCanvas()*new Vector2(root.Size.X-button.Size.X-177.75f+button.Size.X/2,220.25f+button.Size.Y/2);
            Motion(tree,target);Send(tree,target,MouseButton.Middle,false);
            context.Log("DRAG_RESIZE_RESULT: dragging="+buttonDrag.Dragging+" pos="+button.Position+" right="+buttonDrag.Current.RightInset+" vertical="+buttonDrag.Current.VerticalInset+" target="+target+" cancellation="+buttonDrag.LastCancellation);
            button.GuiInput-=Trace;
            Check(Math.Abs(buttonDrag.Current.RightInset-177.75f)<.1&&Math.Abs(buttonDrag.Current.VerticalInset-220.25f)<.1,"resize during drag mismatch");
            Rect(buttonDrag,button,root);
            tree.Root.Size=new Vector2I(900,700);await Wait(tree,.3);Rect(buttonDrag,button,root);
            at=Center(button);Send(tree,at,MouseButton.Left,true);Send(tree,at,MouseButton.Left,false);
            await Until(tree,()=>clicks==2,"resized click miss");
            Nodes(tree.Root).OfType<DialogBoxTips>().Single().CloseDialog();await Wait(tree,.2);
            var roundTrip=buttonDrag.Current;buttonDrag.Dispose();
            buttonDrag=layouts.Attach(button,root,"main-menu","default","hello",new Placement(24,30));
            Check(buttonDrag.Current==roundTrip,"scene-style reattach lost saved placement");
            await tree.ToSignal(RenderingServer.Singleton,RenderingServer.SignalName.FramePostDraw);
            using(var image=tree.Root.GetTexture().GetImage())Check(image.SavePng("user://drag-layout.png")==Error.Ok,"screenshot");
            buttonDrag.Dispose();statusDrag.Dispose();
            context.Log("DRAG_AUDIT_PASS: real GUI synthetic input; modal/cancel; label; scaled parent; live window resize; click preserved; data reload; cleanup");
            tree.Quit();
        }
        catch(Exception error){context.Log("AUDIT_TEST_ERROR: "+error);tree.Quit(2);}
    }
}
