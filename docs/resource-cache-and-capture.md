# 资源缓存与预览捕获

适用：发布版准备、资源分析和需要原版外观的位置预览。缓存与渲染资料只保存在项目 .work，已由 .gitignore 排除；不进入 pmod、版本控制或模板分发。无需游戏源码，不将解包当作源码还原。

## 开始开发时准备，后续增量复用

`python tools/mod.py prepare --game-dir '<用户发行目录>'` 建立发布引用/索引，同时初始化 `.work/game-cache/<发布身份哈希>/` 和 current.json。最小 Hello World只建立索引，不完整解包游戏。UI项目在用途明确后一次提取所需场景与依赖：

```powershell
python tools/mod.py extract --path 'Prefab/GUI/Button/MainButton.tscn' --dependencies
# 后续同一命令校验并复用，不再写一份临时解包目录
python tools/mod.py extract --path 'Asset/Theme/MainTheme.tres' --dependencies
```

省略 --pck 时使用prepare记录的包，省略 --output 时使用统一缓存；仍支持旧的显式 --pck/--output 原始提取。--dependencies递归跟踪文本中的res://引用，包括.import/.remap及其导入产物。脚本不存在、UID-only、运行时动态加载和编译代码依赖并不保证完整发现；unresolved列表必须保留，按需求继续确认，不能宣布已还原工程。

缓存目录包含index.json、manifest.json和files/。索引记录PCK条目；清单记录PCK SHA-256、宿主DLL SHA-256、引擎/格式、提取器版本、提取文件MD5/SHA-256和请求依赖结果。catalog共用匹配发行身份，不额外复制素材。后续分析从匹配缓存开始，只有缺项才增量提取。

每次缓存访问校验实际PCK及准备引用，运行时目录的DLL来源也需匹配；变化或移动后明确要求prepare。缓存文件再次使用时核对PCK MD5，不静默覆盖被改文件。版本变化使用新目录，旧缓存保留历史；mtime只可作辅助，不决定兼容性。新的prepare不是清空所有旧资源。显式旧式--output提取仍是独立原始提取，不声称已经绑定完整发行身份。

## 打开位置预览之前准备干净背景

在启动测试游戏前就设计捕获分支，不能进入游戏后才发现按钮残留：

1. 明确版本、场景、阶段、布局模式、逻辑画布和待隐藏的Mod组件清单。
2. 在独立测试构建中加入显式捕获参数，正常启动不执行；保存输入/代码/配置身份。到达目标界面，等待布局/动画完成，按首次启动规则处理测试提示。
3. 隐藏清单中的Mod组件，保留宿主按钮、卡槽和相关动态信息；等待绘制后捕获Viewport背景，finally恢复原显隐。
4. 单独渲染组件并记录实际尺寸、留白、状态、文字、字体/主题和坐标映射。背景与组件资料齐全后才打开用户窗口并开始60秒。

“干净”是没有待调整组件残影，不是清除所有原版占位。全屏背景不能证明所有阶段空闲，捕获状态写入context；金币等未显示区域仍可用regions提示。已确认的绝对位置依旧优先，不因提示自动避让。

## 透明组件由宿主渲染优先

截图裁出的按钮可能带原场景像素，PNG扩展名不证明透明；不得用带背景的屏幕裁片冒充独立组件。优先实例化完整原版场景，在透明、独立World2D的SubViewport内绘制，沿用贴图、字体、主题和子节点。简单标签/按钮也可基于缓存素材在Python渲染，但必须确认字体、九宫格、边距和描边；无法准确还原时明确近似，不在Skill里承诺通用自动复刻。

可选辅助代码：[PreviewCapture.cs](../tools/PreviewCapture/PreviewCapture.cs)。把该文件链接/复制进独立测试Mod编译（普通C#静态类，不需Godot源生成器）；不要把编译出的PreviewCapture.dll或宿主DLL加入默认单DLL包。辅助项目仅用于签名编译检查：`dotnet build tools/PreviewCapture -c Release`。

```csharp
// 在显式测试捕获分支、目标场景已就绪时调用；不是默认入口行为。
await ModPreview.PreviewCapture.CaptureBackground(tree, tree.Root,
    new CanvasItem[] { button }, "user://clean-menu.png");
var capture = await ModPreview.PreviewCapture.CaptureComponent(tree,
    ResourceLoader.Load<PackedScene>("res://Prefab/GUI/Button/MainButton.tscn"),
    new Vector2(190, 46), "user://button.png",
    control => ((MainButton)control).text = "Hello World", padding: 8);
// capture.Size是就绪后的实际控件尺寸，可能大于请求的最小尺寸。
// capture.Padding为四边透明留白；capture.ImageSize是PNG整体尺寸。
```

组件预览配置使用实际Size而不是请求尺寸；imagePadding填写同一逻辑坐标单位的留白，编辑器将图片绘制在组件矩形外侧，不把阴影/留白当按钮尺寸。宿主渲染保留alpha；检查空图、透明像素和内容是否可见。辅助代码拒绝全不透明/空图，但不证明所有复杂场景的视觉状态正确。弹窗/业务场景可能需要原管理器或其他服务，不能任意离屏实例化；当前实测仅覆盖MainButton常态及背景隐藏恢复，其他组件按需验证。

## 防止旧预览再次使用

捕获后准备标准位置配置，并绑定当前发行缓存与该测试Mod DLL：

```powershell
python tools/preview_session.py --config '.work/capture/session-input.json' --mod-assembly '<当前测试Mod DLL>' --output '.work/position-session/session.json'
python tools/placement_editor.py --config '.work/position-session/session.json' --output '.work/position-session/result.json'
```

preview_session转换图片路径为本地绝对路径，记录releaseCacheKey和modAssemblySha256；窗口载入时检查当前发布/PCK/DLL与Mod DLL。已有组件变化或游戏更新会拒绝旧预览，必须重新捕获并绑定。配置/实际图片内容摘要另外绑定会话，变更不能恢复旧确认。此绑定只能验证身份，不能替代“图片确实由这次捕获产生”的流程证据；必须保存捕获日志与本次输出，不给陈旧图片重新盖摘要来伪造新捕获。

背景类型、viewport纹理尺寸、窗口黑边与逻辑坐标必须明确；组件留白、标签宽度和最小尺寸同样参与标定。仅当资料准备成功才启动反馈窗口，失败不消耗用户60秒。不修改默认模板入口来自动截图或提示用户。
