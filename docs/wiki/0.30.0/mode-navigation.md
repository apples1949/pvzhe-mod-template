# 模式入口与页面导航

基线：[0.30.0](overview.md)。来源：用户发行PCK、发布程序集元数据及局部IL；运行范围见 [独立实验](../../mode-navigation-experiment.md)。本页不依赖游戏源码。

## 三种不同含义

模式入口是玩家进入一组内容的路径；章节/关卡是内容组织；战斗Process/Feature才涉及战斗流程/能力。新增按钮或目录不会自动创造新的胜负规则。`context.Modes`的公开GetState/RequestOutcomeEvaluation也不是菜单模式或场景注册接口。

原生层级为`LevelCatalogConfig.chapterList → LevelChapterConfig.levelList → LevelChooseConfig`。章节列表没有递归章节字段；任意深度导航应由自己的页面数据组织，叶子关联合法关卡。目录普通选择仍需提供图卡，详细数据契约见 [关卡](levels.md)。

## 选择宿主还是自己的页面

1. 只需选关时，用已有`LevelChoose`及ProvideLevelCatalog，不额外造一个仅有“继续”的页面。
2. 需要说明、不同路线或多级分类时，可在`XWModPresentationPoints.MainMenu`提供的Root/Lifetime中托管自己的Control/PackedScene。它是自己的导航页面，宿主CurrentScene仍为MainMenu。页面管理显示/返回，进入宿主选关或战斗时由场景Lifetime销毁。
3. 真正通过SceneManager加载的独立场景需要额外契约。本发行`SceneManager.TryStartThreadedSceneLoad`先查私有SCENES字典，再检查路径存在并请求线程加载。`ChangeScene`会清理对象、操作历史、音频及加载页；随便传新名字会被拒绝。局部IL没有证明Mod提供了公开场景注册能力，不能据此臆造`category=Scene`。直接替换SceneTree.CurrentScene的完整兼容性本轮未验证。

自己的页面可有多级路由，不必每级都切换宿主场景。模式页不属于宿主sceneStack，勿手动塞入页面名。需要独立SceneManager场景时继续调查，不把本页的托管页面路线宣称为该能力。

## 入口、启动与返回

主菜单挂载后创建原版`MainButton.tscn`，设置Position/Size，使用场景作用域管理。完整页面示例采用低于DialogManager.DialogLayer（100）的CanvasLayer（示例10）和全屏接收鼠标的Control，原版贴图仍引用res://；页关闭后释放整棵子树。并非所有新页面都必须采用该层级值。

章节路线：`SelectCatalog(owner,runtimeKey)`→`Global.currentLevelChoose=BrowserKey`→`ChangeScene("LevelChoose")`。此路线仍有宿主Mod目录选择层，SelectCatalog不等于已验证“跳过目录列表”。不想要这层时应另做对应选择页面，而不是宣称已直接进入章节。

直接路线：CanPlay、单人检查、完整`XWModLevelIdentity`、TryResolve、Select，再集中设置currentLevelConfig/currentLevelId/enterLevelMode并进入TowerDefense；见 [ModeLevels.cs](../../../examples/ModeNavigation/ModeLevels.cs)。关卡仍需注册在自己的目录中，直接路线只省略选择界面。

自己的“返回模式页”保存路由意图，新的MainMenu挂载时重建页面；不持有旧场景节点。关闭页面清除该意图并恢复入口。进入浏览/对局后不保留覆盖层，重复进入不能叠加。

本版context.Lifetime在初始化后冻结；挂载回调中再向它Track清理项会停止本Mod展示。延后注册的树监听清理使用Initialize预建的CreateChildScope；页面/选关实例仍用surface.Lifetime或Presentation.CreateSceneScope。此约束由发行IL及模式实验的冻结错误确认，不能把动态清理项误作可随时登记的初始化结构。

发行LevelChoose.Back的局部IL显示：Mod浏览根返回时Clear LevelSession，随后按内部FromManagement分支选择场景；本发行false分支是LevelEditorStage，true分支是MainMenu。不能按字段名字猜方向。实验直接打开浏览器后，原生Back确实进入了编辑器场景，未完成自己的返回路线。

MDK页面路线因此使用 [ModeBrowserReturn.cs](../../../examples/ModeNavigation/ModeBrowserReturn.cs) 对自己发起的LevelChoose实例做有限适配：Ready后仅替换该实例BackButton中原版choose.Back订阅，在ModBrowser目录列表可见时清理自己的LevelSession并回MainMenu；内层返回仍委托choose.Back，保留其他订阅，作用域结束清理/恢复。该适配不能推广成修改全部选关页面；不读写私有导航字段。程序化ChangeScene("MainMenu")仍只证明重挂载/路由恢复，不证明胜利弹窗或暂停菜单退出的每条路径。

## 运行边界

最小配方见 [ModeNavigation](../../../examples/ModeNavigation/README.md)。固定层级之外的自有深层导航、进度解锁/奖励、联机、自定义战斗Process和任意独立场景加载需按需求另验。验收必须区分按钮回调、GUI命中与系统鼠标，输入方式不能在报告中混写。
