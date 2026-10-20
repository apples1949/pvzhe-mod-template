# 游戏内拖拽布局

新建Mod自有浮动按钮、HUD或面板时使用[pvzhe-ui-drag](../.agents/skills/pvzhe-ui-drag/SKILL.md)。玩家按住中键移动，松开提交；发布后仍然可用，无60秒窗口或额外确认。普通左键业务保留。适用于自有浮动根控件，不自动接管原版节点、列表项、滑块内部或Container布局子项。

拖动是创建这类UI时的默认能力，不是收到“调整位置”请求后才启用的特殊流程。AI创建、接入并验证后，在首次交付中主动告诉玩家：“按住这个控件上的鼠标中键拖动，松开就会永久保存位置，发布后也可以继续调整。”不询问是否实现拖动能力；自动验收后仍应按[玩家试用交接](../.agents/skills/pvzhe-ui-drag/references/player-layout-review.md)邀请尚未调过位置的玩家试用一次，默认居中弹窗不询问。当前Mod开发任务中，用户的拖动提交就是位置调整反馈：先核对来源身份，再更新项目默认布局并按变化验证，不再要求文字说明“我要换位置”或二次确认；没有开发任务接收的发布环境仅本地保存和输出，不会自行修改工程。

## 组件接入

可选源文件[DragLayout.cs](../components/RuntimeUi/DragLayout.cs)不编译进默认Hello World。自己的csproj显式Compile Include该文件；拷贝到独立Mod工程时保留命名空间或统一调整引用，无需增加游戏DLL到包中。完整例子见[DragLayout](../examples/DragLayout/README.md)。

在Initialize中创建一个DragLayout(context)，完成Data.Declare并输出UI_LAYOUT_READY。在MainMenu/BattleHud的场景回调中创建父Control及自有控件，调用Attach并把返回绑定的Dispose登记到surface.Lifetime。每个控件/场景/布局ID稳定且唯一。父节点必须是自由布局Control、控件属于同一Window viewport；嵌套SubViewport和复杂旋转/交互层需单独适配，不从该例推导已支持。

```csharp
// Initialize：每个Mod运行期一份，声明不能推迟到场景切换时。
var layouts = new ModTemplate.RuntimeUi.DragLayout(context);
// 场景回调：control已经是自由布局parent的直接子节点。
var drag = layouts.Attach(control, parent, "battle", "horizontal", "sweep",
    new ModTemplate.RuntimeUi.Placement(RightInset: 24, VerticalInset: 80, Bottom: true),
    canDrag: () => control.IsVisibleInTree() && !DialogManager.Instance.HasOpenDialogs);
surface.Lifetime.Track(drag.Dispose);
// 自己的设置/菜单入口调用drag.Reset()恢复当前项目默认值。
```

canDrag应按场景包含模态、阶段和编辑权限，不把业务按钮不可用等同于允许穿透拖动。原版场景组件优先复用，输入通过目标GuiInput命中开始，不全局按矩形抢占其他Mod的点击。按下后沿Godot的GUI鼠标捕获接收运动/释放（即使移出原矩形），继续使用控件局部坐标；中键与左键业务分离，送达该控件的Escape、失焦/隐藏/离场取消。滚轮滚动不是中键按下。非鼠标设备及改绑为其他手势需另接输入适配，不宣称触屏已支持。

## 锚定与窗口适配

横向始终右锚定：anchor_left=anchor_right=1。保存rightInset，计算x=parentWidth-controlWidth-rightInset；拖到画面左侧仍是右锚定，不按位置重选锚点、不保存x/parentWidth百分比。纵向保存anchorY=top/bottom与verticalInset，默认沿用该控件已确认策略。起点和边距均为父布局的逻辑像素，允许小数，不取整。

鼠标从控件局部/Window viewport转换到父布局；每次移动使用当前画布变换，包含宿主拉伸和CanvasLayer，不以窗口边框/桌面像素计算。固定逻辑画布整体缩放与实际父尺寸变化分别检查，运行中改变窗口大小不能成为切换锚点或避让的理由。拖动中改变窗口大小仍以当前鼠标位置和抓取偏移计算，不沿用过期窗口倍率。

组件会将显示限制在当前父内容范围内，窗口过小可临时贴边；不因此改写保存的边距，窗口恢复后恢复原布局。用户主动拖动并松开才提交新位置。不会因金币、其他UI或排版建议自动避让。自动布局给初始值；用户拖动后的意图优先。

## 本地覆盖与项目默认值

默认值位于自己的Assets/ui-layout.json并随包分发；玩家移动保存在宿主Data的Local作用域，按Mod及scene/layout/component隔离，不写对局Battle存档。Data声明在Initialize，保存使用TryWrite并报告结果；每帧不落盘。取消/无变化释放不输出成功更改；保存失败仍输出实际更改，但persisted=false并记录警告，不能声称下次启动会恢复。Reset输出reason=reset-default并保存当前默认值。

开发时的拖动首先改变当前玩家覆盖；AI需要显式将匹配反馈导入项目默认JSON、构建并验默认分支，才会影响新玩家。只看本机恢复成功不能证明发布默认值已变。重建不删除玩家覆盖，也不自动把其他开发者的拖动写入默认值。

## 反馈协议 schemaVersion=1

宿主context.Log提供前缀，组件不自行拼第二层Mod标签：

```text
[Mod:my-mod] UI_LAYOUT_READY: {"schemaVersion":1,"modId":"my-mod","sessionId":"...","binarySha256":"..."}
[Mod:my-mod] UI_LAYOUT_CHANGED: {"schemaVersion":1,"modId":"my-mod","componentId":"sweep","sceneId":"battle","layoutId":"horizontal","sessionId":"...","sequence":1,"binarySha256":"...","anchorX":"right","anchorY":"bottom","rightInset":24.25,"verticalInset":80.5,"parentSize":[1080,600],"size":[170,46],"coordinateSpace":"parent-logical-pixels","reason":"middle-drag","persisted":true}
```

sessionId每次Mod初始化重新生成，sequence在该运行期单调增加；binarySha256是当前包Runtime/ModAssembly.dll摘要。多个Mod可使用完全相同的字段/事件名，接收方必须同时匹配前缀modId、正文modId、已核实DLL、当前session及目标scene/layout/component。READY只标识来源就绪，不代表用户拖过。不是从“最后一个READY”自动猜目标，不读旧verification.json代替本轮来源。重复事件去重，同序号冲突拒绝，选择最大匹配序号并记录消费游标。

生产环境始终保存和输出，无监听方也不报错、等待或关闭功能。日志不包含个人资料，不提供跨Mod操纵权限；身份筛选用于避免误用，不将第三方任意日志视为可信代码执行输入。

## AI接收与落地

从本轮实际加载包和目标Mod的READY取得sessionId，先核对binarySha256与包内DLL一致，再运行：

```powershell
python tools/ui_layout_feedback.py --log '<本轮game.log>' --mod-id '<目标ModID>' --session-id '<本轮sessionId>' --binary-sha256 '<包内DLL摘要>' --scene-id battle --layout-id horizontal --component-id sweep --after 0 --wait-seconds 60 --output .work/ui-drag/event.json
```

工具只输出匹配事件；无结果返回status=waiting，不修改默认值，不替用户选择；60秒仅限制一次日志等待，不影响游戏里的拖动。当前Mod开发任务收到匹配的用户拖动反馈后，由AI添加--apply-defaults '<自己项目Assets/ui-layout.json>'执行导入，不需要玩家再说一次要改位置；“显式导入”是工具参数要求，不是新增审批。文件必须已声明相同modId/schema及该槽，纵向策略变化拒绝自动导入。只改该槽的锚点/边距，不从反馈修改ID、资源路径或执行任意代码；默认布局作为代码/资源变更重建验证。持久化失败可用于了解本次位置，但应先修复保存问题，不能报告完整验收通过。

验收需要覆盖原版缩放/输入链、无变化和取消不提交、模态优先、多Mod来源、发布普通启动仍可拖动、同一隔离用户第二进程恢复。具体已测版本/方式与证据写[Wiki](wiki/0.30.0/ui.md)，此协议本身不代表全部控件已验证。

输入实现依据[Godot Window输入入口](https://github.com/godotengine/godot/blob/master/scene/main/window.cpp)：window_input先于push_input，不能把其原始坐标与GuiInput局部坐标混用；原版引擎说明仍须与发行运行结果互校。验收合成鼠标时可能需要显式的嵌入窗口输入路由条件，必须仅在夹具设置并记录，不能把该条件写入生产Mod或声称系统鼠标已验证。
