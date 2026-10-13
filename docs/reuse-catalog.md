# 宿主组件复用目录（0.30.0）

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
