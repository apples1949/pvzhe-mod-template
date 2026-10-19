# 对局与常用操作路径

基线：[0.30.0](overview.md)。来源：自己的 DemoLevel/Smoke 代码及成功运行记录；原版场景结构来自发行 PCK。以下路径状态分别记录，不能互相代替验收。

## BATTLE-01：已实测的 Mod 测试关卡入口

用途：先验证用户战斗功能，避免把原版进度、教程和冒险 UI 当成业务测试的前提。输入是自己的已注册单人关卡、主菜单已就绪；完整可执行参考为 [DemoLevel](../../../examples/FeatureLab/Features/DemoLevel.cs) 与 [Smoke](../../../examples/FeatureLab/Verification/Smoke.cs)。测试夹具可保持在独立示例/测试分支，不应自动加入用户发布功能。

| 步骤 | 操作与完成条件 |
| --- | --- |
| 准备 | 按 [关卡配方](levels.md) 解析自己的现代 JSON、校验并 ProvideLevelCatalog；身份必须是本 Mod |
| 开目录 | DemoLevel.OpenBrowser 设置宿主 Mod 目录身份，再 ChangeScene("LevelChoose")；等待该场景与目录控件实际存在 |
| 选目录 | 在 LevelChoose 的 `ModBrowser/Panel/Scroll/Catalogs` 中找到目标目录按钮，选择后确认 ModBrowser 隐藏 |
| 选章节 | 在该目录生成的 DragMenuSelectItemChapter 中选择目标项；确认其 sprite.Texture 与 buttonNode 的有效大小 |
| 选关卡 | 等章节过渡完成，选择可见的 DragMenuSelectItemlevel.buttonNode；不要混用隐藏平铺容器中的副本 |
| 等战斗 | `context.Game.TryGetBattle(out var battle) && battle.Running`；同时核对 currentLevelConfig.name 与自己的关卡 name |
| 验业务 | 等所需角色/卡牌实际存在，操作待测功能，再检查最终状态与截图 |

实测场景：FrontlawnEmpty、PlantFirenut 预设卡牌、两只 ZombieNormal；默认阳光300加奖励50后为350，死亡计数0→2，最终 victory。以上选关按钮用 Pressed 信号触发，证明宿主事件与身份链路，未证明真实鼠标命中。内置命令：`python tools/runtime_test.py --example feature-lab`。

直接 DemoLevel.Launch 是现有代码分支，但当前实测走目录按钮链路，不把直达分支标为已验证入口。自定义功能先建立最小夹具，通过后再验证用户要求的原版关卡范围；夹具通过不能证明全部原版模式适用。

## BATTLE-02：原版冒险选关，结构已确认，完整运行待验证

发行 PCK 中 MainMenu 的 `Background/MenuTexture/AdventureButton` 是 TextureButton；LevelChoose 中有章节项、关卡项和难度选项。原版配置见 `Asset/Config/Level/LevelResource.json`，Adventure 首关 SaveKey=Level1_1，Normal/Difficult/Ultimate 分别是配置项，不是三种不同的进入按钮。

正确的待验收顺序是：满足新玩家/进度前提→主菜单选择冒险→等待 LevelChoose→选择章节→等章节相机/布局过渡完成→确认当前难度和目标关卡配置→选择关卡→等待 battle.Running。每一步记录状态与关键数据，不以睡眠时长代替成功条件。

| 结构定位 | 作用及限制 |
| --- | --- |
| `GUI/OptionButton/Transform/Button` | 选关选项入口的内部 Button；外层不是普通 Button |
| `OptionGUI/LevelTexture/Difficult/NormalTexture/NormalButton` | 难度选项；没有证据表明按它会启动关卡，不能将选难度等同开战 |
| `GUI/GUIFollow/Choose/LevelMenu` | 转盘式关卡容器 |
| `GUI/GUIFollow/Choose/LevelMenuFlatten/ScrollContainer/MarginContainer/LevelContainer` | 平铺副本；其存在/大小非零不代表当前可点击 |
| `GUI/GUIFollow` | CanvasLayer，follow_viewport_enabled=true；点击坐标按 [UI 配方](ui.md) 转换 |

独立新目录下曾发生 LevelChoose.Select 的 KeyNotFoundException，但没有记录具体缺失键，根因尚未确认。不能宣称必然是用户名、难度或存档造成；先记录所选章节/关卡数据、难度键、模态和场景状态。没有成功证据前，不照搬反复点击、修改转盘或直接全局切场景的试错代码。

## BATTLE-03：暂停、恢复、退出与返回

静态确认的场景是 `Prefab/GUI/DialogBox/DialogBoxGeneral/DialogBoxGamePause/DialogBoxGamePause.tscn`、`Prefab/GUI/DialogBox/MenuDialog/DialogBattlePause/DialogBattlePause.tscn`，不是可随意打开的通用提示框。宿主战斗快照具有 Paused。[双例迁移实验](../../migration-pair-experiment.md)通过实际currentControl.buttonPause.ButtonPressed切换路径打开DialogBattlePause，再CloseDialog恢复；生产与自有恢复在暂停5.2秒内不推进。此为宿主控件事件/状态路径，未验系统鼠标。实验还覆盖程序化返回菜单释放作用域与重开；保存退出及读档仍待验证。

人工验收应使用实际游戏菜单：暂停后确认模拟暂停，继续后恢复；退出后确认 BattleHud 场景作用域释放，再返回菜单/开新局检查无残留。对“保存并退出”先满足资料与存档前提并另验读档。不要用 tree.Quit 证明返回菜单正常，也不要仅修改 tree.Paused 假装实现完整宿主暂停流程。

失败停在战斗前，报告测试前提失败；没有进入业务断言时不能认定伤害、统计或按钮业务已失败。
