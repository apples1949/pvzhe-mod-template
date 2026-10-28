# UI 组件与交互

基线：[0.30.0](overview.md)。状态：MainButton/提示框及选关图卡的创建、程序化事件和画面已实测；确认/输入框、通用战斗按钮真实命中仍待验证。来源：发行 PCK/DLL、HostUi/Smoke；坐标规则由 Godot 接口文档核对。

## 选择原版组件
AI 默认评估复用，玩家无需提出“寻找原版组件”。先理解用途，再选游戏服务、完整场景、场景组合、外观资源，最后才考虑自己提供素材。资源存在、接口公开、运行验证分别记录。

执行 `python tools/catalog.py` 从玩家发布 PCK 和 DLL 生成 `.work/reuse-catalog.json`：场景节点摘要、资源依赖、公开方法/属性/事件、发布摘要。它不复制游戏素材，也不将原始源码当成前置条件。索引未找到依赖或接口变化时先报告/适配，不能跳过检查。

| 内容 | 接入方式 | 可修改内容 | 依赖/生命周期 | 验证边界 |
| --- | --- | --- | --- | --- |
| MainButton | 实例化 `res://Prefab/GUI/Button/MainButton.tscn` | text、Size、布局、Pressed | 原版贴图、字体/标签、AudioManager；场景作用域清理 | FeatureLab 验证创建与事件，画面核验；人工音效另测 |
| DialogBoxTips | DialogManager.Instance.DialogCreate("DialogBoxTips") | text（BBCode） | 宿主弹窗层、暂停/TimeScale；CloseDialog 关闭 | FeatureLab 验证打开、关闭、暂停恢复 |
| DialogBoxChoose | 同管理器创建 "DialogBoxChoose" | text、按钮文字、OnChooseTrue/False | 模态层及关闭；避免叠加 | 发布资源/接口静态确认；交互尚未单独运行验证 |
| DialogBoxInput | 同管理器创建 "DialogBoxInput" | titleText、默认/占位文本、输入上限、确认事件 | 输入焦点、模态层、关闭 | 发布接口静态确认；输入交互尚未单独验证 |
| DialogPopup | 原版通用框架场景 | 内容节点、布局 | 内部命名节点、拖动与关闭 | 适合进一步筛选；不是任意业务框可无条件改造 |
| NinePatchButtonBase | 应选择对应完整具体场景 | text、normal/pressed/hoverTexture、事件/音效 | 子节点和九宫格边距 | 类型公开；具体场景适用性需验证 |
| MainTheme | `res://Asset/Theme/MainTheme.tres` | 应只读引用或复制后局部改动 | 项目字体及样式；共享资源 | 主题存在不等于普通 Button 会自动具有 MainButton 的贴图/音效 |
| MainMenu/BattleHud | XWModPresentationPoints |自己的节点 | owner 容器和场景 Lifetime | v3 示例接入 |
| 原版选关卡片 | LevelChapterConfig/LevelChooseConfig 引用 Texture2D | 章节封面、关卡卡片、背景、建筑 | 宿主 res:// 加载纹理及导入依赖 | FeatureLab 验证可见卡片、有效点击区域、章节/关卡按钮事件 |

不要 `new MainButton()` 后假定它是成品按钮；场景里包含 TextLabel、贴图与脚本。不要只 QueueFree 模态弹窗：DialogBoxBase.CloseDialog 会恢复暂停与 TimeScale。Tips/Choose 的 Init 当前没有通用字段赋值逻辑，必须设置对应公开属性。

复用不等于拷贝：在宿主里加载原版 res:// 场景及依赖，Mod 无需嵌入原版贴图。自己的 JSON/媒体才列进允许名单。编辑共享 Resource/Theme/StyleBox 时先判定共享关系并按需复制，不影响原版实例。

关卡示例引用 `res://Asset/Texture/GUI/TowerDefense/Level/Chapter1/` 下的 Chapter1.png、Chapter1Background.jpg、Chapter1Building.png、Adventure_LEVEL1-1.png。发布 PCK 可能只有对应 .import 与导入产物，这是运行时可加载资源，不应误判原图缺失。章节/关卡 unlockImage 留空会产生看不见且没有有效大小的选择入口；只验证配置能直接启动会漏掉这个问题。卡片图案来自原版，所指向的关卡与存档身份属于本 Mod。

DialogManager 等公开宿主类不是独立稳定 SDK，集中封装在 Adapters 中并记录发布版本。商店、账户、奖励等业务弹窗可能有副作用，不作为通用容器。需要复杂窗口时先组合已验证的组件，验证焦点、关闭、场景切换和分辨率，再将配方提升为已验证。

## 场景接入

Initialize 注册 v3 MainMenu/BattleHud；收到 Root/Lifetime 后实例化自己的控件，把节点及事件清理纳入场景作用域。MainButton 参考 [HostUi](../../../examples/FeatureLab/Adapters/HostUi.cs)；HUD 布局参考 [KillCounter](../../../examples/FeatureLab/Features/KillCounter.cs)。不要用每帧全树搜索来代替挂载点。

**包内场景不能覆盖 `Prefab/` 下的 UI**（用户实机记录，待复核）：资源类别推导只认配置类扩展名，类别表里没有 `Prefab/` 前缀 ⇒ 往包里放一份同名 `.tscn` 只会变成**死文件**，既不会生效也不报错。因此"给设置页/战斗选项框加控件"的唯一可行路线是**运行时注入**：在挂载回调里找到目标节点，`AddChild` 自己的控件，并自己连接信号（游戏脚本只处理它认识的节点）。注入必须**幂等**（按节点名查，已存在就只校准状态），因为这些对话框每次打开都会重新实例化。

提示框从 DialogManager 创建 DialogBoxTips，设置公开 text；不要在业务提示打开时叠加。关闭使用 CloseDialog，并验证暂停/TimeScale及输入恢复。UI节点不携带修改钱包或战斗的权限，按钮业务仍走相应宿主命令。

## UI-01：程序化事件与真实点击分别验收

1. 先确认目标节点、场景作用域、尺寸和 Visible，再发送 Pressed 信号验证事件连接；这一步不验证鼠标能点到。
2. 对真实命中，等待动画/布局结束，检查父层可见性、裁剪、模态、MouseFilter、Disabled，以及其他 GUI 是否覆盖它。
3. 将控件局部坐标转换到用于输入的 Viewport。内部合成输入不是桌面坐标，也不是 Control 的画布 global 坐标。
4. 记录鼠标事件后回调和业务结果。点击失败而信号成功，应报告命中失败；不能以信号兜底后仍宣布“鼠标验收通过”。

以下仅为静态/编译核对过的坐标转换与按下事件示意，不是已实测的完整点击配方；按下/释放配对及同帧或分帧时序须在当前宿主与控件核验：

```csharp
Vector2 center = button.GetGlobalTransformWithCanvas() * (button.Size / 2);
var viewport = button.GetViewport();
viewport.PushInput(new InputEventMouseMotion { Position = center, GlobalPosition = center }, true);
viewport.PushInput(new InputEventMouseButton
{
    ButtonIndex = MouseButton.Left, Pressed = true, Position = center, GlobalPosition = center
}, true);
// 需配对发送相同目标的 Pressed=false，再观察事件、回调及结果。
// 此处未验证释放时序，不规定必须等待一帧或必须同帧发送。
```

button 应为当前有效 Control，事件只送其所属 viewport，不能随意混用根 Window 像素大小和伸缩后的逻辑尺寸。需要边界判断时把局部矩形四角用同一变换映射到 viewport；只判断中心在内还不足以证明完整可见，还需检查裁剪/遮挡。输入诊断与证据分类按 [验证执行策略](../../../.agents/skills/pvzhe-mod-verify/references/verification-strategy.md)，本示例属于宿主合成输入，不代表系统鼠标或人工验收。

`GetGlobalRect()` 返回所在画布的矩形，不保证是屏幕坐标。LevelChoose 的 GUIFollow 为跟随 viewport 的 CanvasLayer；曾把负Y当作出屏导致错误排查。依据：[Control.get_global_rect](https://docs.godotengine.org/en/stable/classes/class_control.html#class-control-method-get-global-rect)、[CanvasItem.get_global_transform_with_canvas](https://docs.godotengine.org/en/stable/classes/class_canvasitem.html#class-canvasitem-method-get-global-transform-with-canvas)。同样，`IsVisibleInTree()` 和非零大小不能证明命中可用。

Window 不继承 CanvasItem，不能照搬 `tree.Root.GetViewportRect()`；使用控件对应的 viewport，并核对当前发布 GodotSharp 的 API。不要从编译错误跳过到旧包运行。

## 战斗操作的显示与共存

状态：设计约束与已公开接口的适配指引；通用战斗按钮的完整阶段/避让实现尚未运行验收。BattleHud 提供挂载位置和场景作用域，不自动管理选卡→战斗→结算的显示状态；TryGetBattle 的 Running/Paused 是已知观察入口，具体边界需按功能验证，不能将单个标志当作全部模态/结算判定。

按 [场景适配](../../../.agents/skills/pvzhe-ui-create/references/scene-fit.md) 创建状态表、刷新可见/启用状态，并保留命令入口检查。关卡左下已有原版选项时，在邻近空位布局且验证原选项仍可用；不将固定边距或 Layer=100 当作通用配方。坐标与输入方式按上文区分，命中失败先定位原因；升层后须复验宿主暂停/模态优先级。

FeatureLab 的 PRESET 关卡跳过选卡，因此它通过不能验证“选卡阶段隐藏按钮”。需要此行为时另设有选卡阶段的场景或实际原版关卡，分别保留准备与战斗证据。

## 已知左下控件：布局前必须考虑

状态：以下结构由本基线发行 PCK 提取并静态核对（2026-10-13）；阶段变化/最终命中矩形仍须按目标功能核验，不以源码参考或截图代替发行行为验收。

| 项目 | 发行结构证据 |
| --- | --- |
| 场景 | res://Scene/TowerDefesne/TowerDefenseNew/TowerDefenseControlNew.tscn（目录拼写为 TowerDefesne） |
| 原版选项 | GUITop/OptionButton；根节点导出 optionButton 指向该节点 |
| 实例 | res://Prefab/GUI/Button/SpriteBrightButton/SpriteBrightButton.tscn；不是普通 BaseButton，需继续定位点击子节点 |
| 位置与层 | 父级 GUITop 为 CanvasLayer，layer=3；OptionButton anchor_top/bottom=1，offset_left=4、top=-56、right=139、bottom=75，scale=(0.4,0.4) |
| 默认与动态 | visible=false、autoSize=true；这不表示战斗时不存在，也不能把偏移直接当成最终按钮矩形 |

从 [内容索引](content-index.md) 的提取入口获取该场景和实例依赖，再追踪显隐/autoSize/阶段逻辑，记录运行时尺寸及同坐标空间矩形。选卡截图或 PRESET 测试关卡的一次截图不能证明左下区域无原版按钮。具体步骤见 [布局证据顺序](../../../.agents/skills/pvzhe-ui-create/references/scene-fit.md)。

对局摆放位置还须核对 [布局模式与动态占位](battle-layout.md)：金币拾取会显示设置右侧信息区，另一卡槽布局可能占用设置上方。不要把左右/上下方向固定为安全方案。

新增自有浮动控件使用[游戏内拖拽布局](../../ui-drag.md)：中键拖动、始终右锚定、发布后保存及带来源反馈。默认位置先分析宿主共存，玩家拖动后不自动避让。旧外部placement-preview已弃用；下段透明捕获配方仅在明确需要旧预览或其他资源捕获时读取。

原版外观的位置预览优先使用完整组件的透明SubViewport渲染，字体/贴图来自当前发布环境；开启测试前准备隐藏目标组件后的背景捕获。0.30.0 MainButton常态透明输出已通过独立测试，不能泛化为全部弹窗/复杂组件均可离屏渲染。实现和缓存规则见 [资源缓存与捕获](../../resource-cache-and-capture.md)。

## 组件字段真相（来自用户实机记录，本模板待复核）

状态：以下条目来自用户自己十几个 Mod 的实机调试（同系列发行，非本模板本轮实测）。**使用前先用当前发行场景/DLL 核对一次**，核对通过再升级为已实测；与本页其他实测结论冲突时以运行证据为准。

| 组件 | 记录内容 | 不按此写的后果 |
| --- | --- | --- |
| MainButton 文字 | 走 `[Export] public string text`（默认值 `"Test"`）；`_Ready()` 与每次布局刷新都会用它回写子 Label | 直接改子 `Label.Text` 会被覆盖回 `"Test"` |
| MainButton 根类型 | `TextureButton`；按 `BaseButton` 接（本页实测已确认根类型） | 按 `Button` 转换得到 null，退化成无外观按钮 |
| `DialogManager` | 全局命名空间下的 `[GlobalClass]` 类型；`DialogCreate(name, data = null)` 为两参（第二参有默认值） | 猜命名空间、或按单参调用会编译失败/找不到类型 |
| `LevelChoose.Select(int id)` | 既选章节也选关卡，并会写入全局当前关卡 id | 当成"只选关卡"用会造成章节/关卡身份错位 |
| `Tree.SetSelected` | Godot 4 签名是 `(TreeItem, int column)` | 写 `SetSelected(item, true)` 报 CS1503（bool→int） |
| `Godot.Collections.Dictionary` | **不是** `GodotObject` | `IsObjectValid(dict)` 一类写法直接 CS1503 |
| SeedBank 相关节点 | **类名 ≠ 节点名**；按名字 `FindChild` 找不到，需按类型名递归 | 按节点名查找永远为空 |

宿主类仍按本页约定集中封装在 Adapters 并记录发布版本，不散落到业务代码。

## 命中判定的坐标系（规则已核对，对照日志待复核）

状态：坐标系结论与 Godot 接口文档一致（`Control.get_global_rect`、`get_global_transform_with_canvas`）；"三种写法只有一种对"的对照来自用户实机日志，本模板未重跑。这是排查"看得见但点不动"的顺序，不是唯一实现要求。

| 写法 | 结果 | 原因 |
| --- | --- | --- |
| `ctl.GetGlobalRect().HasPoint(viewport.GetMousePosition())` | 否 | 前者只含祖先 Node2D/Control 变换，**不含 viewport 的 canvas 变换**；后者是窗口像素 |
| `ctl.GetRect().HasPoint(ctl.GetLocalMousePosition())` | 否 | `GetRect()` = `Rect2(position, size)`，含控件在父容器里的位置；与"控件自身坐标系"原点不同 |
| `new Rect2(Vector2.Zero, ctl.Size).HasPoint(ctl.GetLocalMousePosition())` | 可用 | 局部鼠标配零原点矩形，同一坐标系 |

排查方式：把 `GetLocalMousePosition()` 与控件矩形**一起打印**，能直接看出"明明在矩形里为什么 false"。另注意 `CanvasLayer` 没有 `GetCanvasTransform()`（只有 `CanvasItem` 有）；跨 CanvasLayer 定位要用 `GetGlobalTransformWithCanvas()` 自行变换。命中失败仍先按 UI-01 区分坐标、遮挡、MouseFilter、Disabled 与业务回调。

## MainButton实例的默认局部偏移

发行 `Prefab/GUI/Button/MainButton.tscn` 的根类型为TextureButton，默认offset_left=-58、top=-23、right=59、bottom=23；它不是普通Button。通用观察器以BaseButton识别按钮，不能只枚举Button而漏掉这个实例。

定位需同时核对父层锚点和实例自己的局部矩形。容器按左上角定位时，HostUi示例会显式设置button.Position；漏做这步会保留prefab默认偏移。SetAnchorsAndOffsetsPreset后的Position赋值与相对增加也不同。不要先把固定(-58,-23)归因于相机，或直接添加CanvasLayer/每帧反向补偿；先查看发行场景的实际属性。主菜单本轮仍沿用宿主层，DialogManager的DialogLayer在发行场景为100，普通Mod界面不应越过模态层。

本轮菜单先用节点数判通过，截图与四角断言发现出屏，修复后按[社区方向实验](../../community-mod-experiments.md)验证。边界与命中使用控件所属viewport及其四角，IsVisibleInTree/数量只能证明节点状态；未测试MoreGame等菜单子状态，不将普通主菜单结论推广为全部页面。


## 自有浮动控件：运行时中键拖动

模板组件与协议见[ui-drag](../../ui-drag.md)，案例[DragLayout](../../../examples/DragLayout/README.md)。不修改原版输入映射或共享UI资源；目标GuiInput命中后沿GUI鼠标捕获接收运动/释放，事件位置是控件局部坐标，先变换到所属父Control。横向始终AnchorLeft=AnchorRight=1，保存父布局逻辑右边距；不会以左侧区域为由改左锚定。生产代码没有Mod测试参数开关。

0.30发行隔离验收1afe423a同时加载drag-layout-demo和drag-layout-other，两者均通过真实GUI派发的引擎合成中键输入产生各自CHANGED。目标Mod共5条有效变更：按钮拖动、缩放父层下文字拖动、拖到左侧仍右锚定、恢复默认及窗口调整中的拖动；取消/无变化/模态不增加提交。最终目标右边距177.75、顶部偏移220.25；同一用户第二真实进程恢复并通过DRAG_RESTART_PASS。内置Local读写和右锚点映射在这些条件下实测，不代表任意Container、SubViewport、战斗阶段、原生系统鼠标或触屏已测。

夹具为避免桌面指针所在窗口影响内部鼠标命中，设置GuiEmbedSubwindows=true；该条件不进入生产Mod。首次失败包括加载遮罩/原生窗口合成输入路由、延迟出现的用户名框：SceneManager.isLoading=false且暂时无弹窗不能证明建档完成。等待用户名框出现、确认建档及实际GUI命中后才开始验收；不把后续弹窗造成的取消误判为缩放算法失效。错误记录保留.work/drag-layout-verification，不将这些对照写成唯一根因推断。最终普通包验收和摘要见[验证记录](../../validation.md)。
