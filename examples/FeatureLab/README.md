# 第 1～4 阶段的功能示例

这是独立的进阶示例，不替换默认 Hello World。所有按钮和提示框来自已安装游戏的场景；包内没有原版图片或 DLL。玩家可以用自然语言提出类似功能，AI 应先读 pvzhe-mod-guide，再进入制作配方。

```powershell
# 首次准备仍使用根目录 README 的 prepare 命令
python tools/catalog.py
python tools/mod.py build --example feature-lab
python tools/mod.py check --example feature-lab
python tools/runtime_test.py --example feature-lab
```

产物在 `dist/feature-lab/feature-lab.pmod`。安装：

```powershell
$mods = Join-Path $env:APPDATA 'Godot\app_userdata\植物大战僵尸杂交版\Mods'
python tools/mod.py install --example feature-lab --mods-dir $mods
```

退出游戏后安装，在 Mod 管理启用“功能开发示例”并重启。主菜单左下角有三个原版样式按钮：说明弹窗、统计开关、示例关卡。示例关卡使用原版地图/火炬坚果卡牌/普通僵尸，两只僵尸一波，起始300阳光；默认简单功能新局增加50阳光。关卡数据属于 Mod，自由编辑 `mod/Assets/level.json` 后重建。

对局右下角显示“本局击杀”。口径是敌方僵尸确认死亡、所有来源；催眠友方、植物和单纯离场不计数，同一实体每个生命阶段一次，复活后再次死亡可再计数。它不是“某玩家造成的击杀”。计数纳入宿主 Battle 数据保存恢复；联机未验证，示例入口只允许单人。

设置在宿主 Mod 管理界面声明，主菜单开关是快捷操作同一设置：`showKills` 即时生效且不影响玩法，`bonusSun` 为0～500、步长25、重启生效的游戏规则。新局事件发放奖励，读档恢复事件不重复发放。

| 文件 | 职责 |
| --- | --- |
| Entry.cs | 初始化功能、主菜单挂载、日志身份 |
| Adapters/HostUi.cs | 原版按钮和提示框接入、正确关闭与作用域清理 |
| Features/KillCounter.cs | 死亡过滤、去重、HUD、Battle 数据 |
| Features/StartingSun.cs | 新局一次性阳光奖励 |
| Features/DemoLevel.cs | 类型化目录、资源身份、现有关卡浏览及启动 |
| mod/mod.json | 独立身份、v3 contentEntries、设置声明 |
| mod/Assets/level.json | 自己创作的 modern Process/Feature 关卡数据 |
| Verification/Smoke.cs | 显式测试参数下的宿主实际运行验收 |

运行工具使用独立用户目录、发布 EXE/PCK 副本，并传入 `--feature-lab-test`。测试执行原版按钮事件，检查弹窗关闭后暂停恢复；切换设置；经过目录、章节和可见关卡卡片的按钮事件进入独立关卡；验证300→350；用宿主 Damage 命令击败真实生成的两只僵尸，验证 HUD=2 和胜利。普通启动不会执行测试伤害。

测试还检查预设火炬坚果实际出现在卡槽中。关卡的 SeedBank 和 PacketBank 两个 Feature 必须配合；只写预设列表不会自动填充卡槽。

日志位于 `.work/runtime-feature-lab/game.log`，报告与截图位于 `dist/feature-lab/`。测试的程序化按钮触发不等于实际鼠标点击或音效人工验收；测试伤害不证明关卡难度平衡。负例、读档、联机与不同分辨率需根据实际制作的功能补充验证。

运行工具会再次启动同一独立存档的游戏进程，确认第一进程保存的 showKills=false、bonusSun=75 在重启后加载。第一进程还确认 bonusSun 保存后提示重启、当前仍为50。第二进程日志在 persistence.log，报告记录 settingsRestartVerified。正常安装时仍使用清单默认值，不会自动改变成这些测试值。

此发布版的 privateResources 不支持 JSON。加载器会对本例自读的 Assets/level.json 留一条非阻断“unsupported package file”诊断；真正的关卡目录由入口注册，不是 JSON 自动注册。这与加载失败不同，已列明其边界。

基础资源和 API 复用依据见 [组件目录](../../docs/reuse-catalog.md)，详细步骤见 [功能配方](../../docs/feature-recipes.md)。不要复制整个示例到 Hello World；按需求选取所需功能。
