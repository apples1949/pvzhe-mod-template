# 模式导航配方（可选）

基线为Windows C# 0.30.0。默认Hello World不引用此目录。示例是托管在MainMenu中的独立页面，并非新注册的SceneManager场景。

路线：主菜单“模式导航实验”→自己的页面→章节选关（宿主目录列表→两章各一关），或直接挑战第二关。页面返回主菜单；从宿主场景回到MainMenu时重建模式页面。两个关卡复用原版地图/卡牌/僵尸，自己的JSON与代码随包，原版图像不随包。

在**独立模板副本**中使用：

1. 将此目录的四个`.cs`文件放入副本`src/HelloMod/`，替换默认Entry（先移除旧Entry.cs内容，不同时编译两份入口）。将此目录`mod/`的内容合并到副本`mod/`，使用对应清单，入口类型为`ModeNavigation.Entry`。不需要修改程序集名或模板构建工具。
2. 用自己的发行目录执行`python tools/mod.py prepare --game-dir '<发行目录>'`，再`python tools/mod.py build`；成功后`python tools/mod.py check`。示例包为`dist/local.mode-navigation.pmod`。参考README安装、启用并重启游戏。
3. 检查两个入口、章节/关卡身份、退回/重进及窗口缩放。演示无自动杀敌或测试启动分支；按正常玩法通关。分享前改成自己的稳定ID、名称/作者，联动更改JSON的Name与示例固定标题/资源缓存前缀，执行release检查。

`ModePage.cs`管理页面和返回意图；`ModeLevels.cs`管理注册和集中启动适配；`ModeBrowserReturn.cs`处理0.30.0宿主浏览根的返回目标；`Entry.cs`组装正常功能。关卡数据在`mod/Assets/`。章节图像来自宿主`res://`，未复制原版内容。

本例为单人、全部开放的结构演示；不实现章节进度门槛、奖励、联机或新的战斗规则。实际验证及输入方式见 [实验报告](../../docs/mode-navigation-experiment.md)，事实与独立场景限制见 [导航Wiki](../../docs/wiki/0.30.0/mode-navigation.md)。
