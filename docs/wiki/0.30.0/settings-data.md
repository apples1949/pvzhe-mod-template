# 设置与存档

基线：[0.30.0](overview.md)。来源：发布接口、FeatureLab清单/入口/KillCounter与两进程日志。设置默认值、即时显隐与重启生效已实测；Battle数据接口已接入，完整对局保存/恢复未运行验收。

## 设置制作

| 示例 | 清单定义 | 已验证行为 |
| --- | --- | --- |
| showKills | bool，default=true，applyMode=immediate，affectsGameplay=false | Get<bool>读取，TrySave保存，Changed刷新；主菜单和对局显隐即时更新 |
| bonusSun | int，default=50，min=0/max=500/step=25，applyMode=restart，affectsGameplay=true | 保存75后报告RestartRequired，当前有效值仍50；第二真实进程读取75 |

优先使用宿主 Mod 管理的设置界面；自定义按钮是同一设置的快捷入口，不另写一份不关联的配置。保存结果和 RestartRequired都需处理；默认值、已保存值、当前有效值是三个状态，不能混为一谈。Changed订阅用Lifetime解除。整数用发布接口对应的实际 int类型，不擅自改成double。

示例具体字段名仅用于说明，按玩家需求确定默认值、范围和生效时机。非法值拒绝、取消/保存失败等负例未统一实测，不由两次正常保存推导所有异常路径正确。

## 账号、设置与对局数据分开验收

- 用户名提示关闭不等于账号建立；测试目录随机新建，跨进程复用和建档前提见 [启动页](startup.md)。
- Settings保存恢复不证明原版玩家资料或 Battle 读档成立。不要拿 settingsRestartVerified=true 声称全部存档功能可用。
- “本局统计”使用 Battle作用域，不写成账号累计值。KillCounter在Initialize调用 `context.Data.Declare("killCount", 1, codec)`，生命周期Restored用TryRead读取，变化后await WriteBattleAsync并检查结果；具体编解码见 [KillCounter](../../../examples/FeatureLab/Features/KillCounter.cs)。
- 数据schema与ID更改需先分析旧数据兼容和迁移，不直接修改玩家存档。自己的声明与版本号应稳定，宿主身份和author/show name不是同一概念。

完整保存恢复验收需要：建立必要测试资料→在独立对局产生数据→通过宿主保存流程→退出并使用同一 user:// 重启→恢复相同关卡/Mod身份→确认值保留、没有重复计数/重复奖励。当前没有这一流程的完整自动成功证据；不要用手写save.res或换个新目录代替。

运行工具第二进程保存的是同一次 FeatureLab 测试目录；重新运行整个工具会产生新目录。新局Ready与恢复Restored的机制见 [战斗服务](battle-services.md)。

拖拽布局使用Data.Local而非Battle，声明在Initialize、场景内TryRead/TryWrite；0.30同一隔离用户第二进程恢复已由[UI拖动案例](ui.md#自有浮动控件运行时中键拖动)覆盖。仅证明Local布局保存，不扩大为对局读档通过。
