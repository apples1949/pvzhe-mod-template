# 设置与存档

基线：[0.30.0](overview.md)。来源：发布接口、FeatureLab清单/入口/KillCounter与两进程日志。设置默认值、即时显隐与重启生效已实测；Battle数据接口已接入，完整对局保存/恢复未运行验收。

## 设置制作

| 示例 | 清单定义 | 已验证行为 |
| --- | --- | --- |
| showKills | bool，default=true，applyMode=immediate，affectsGameplay=false | Get<bool>读取，TrySave保存，Changed刷新；主菜单和对局显隐即时更新 |
| bonusSun | int，default=50，min=0/max=500/step=25，applyMode=restart，affectsGameplay=true | 保存75后报告RestartRequired，当前有效值仍50；第二真实进程读取75 |

优先使用宿主 Mod 管理的设置界面；自定义按钮是同一设置的快捷入口，不另写一份不关联的配置。保存结果和 RestartRequired都需处理；默认值、已保存值、当前有效值是三个状态，不能混为一谈。Changed订阅用Lifetime解除。整数用发布接口对应的实际 int类型，不擅自改成double。

示例具体字段名仅用于说明，按玩家需求确定默认值、范围和生效时机。非法值拒绝、取消/保存失败等负例未统一实测，不由两次正常保存推导所有异常路径正确。

## 设置声明字段速查（用户实机记录，本模板待复核）

状态：下表字段名与默认值来自用户十几个 Mod 的实机调试（同系列发行），**本模板只用 showKills/bonusSun 两项验证过**（见上表）。声明前先用发行清单解析/设置页实际渲染核对一次，再据此写 mod.json。

| 需求 | 写法 | 不按此写的后果 |
| --- | --- | --- |
| 配置项显示名 | `"label": "中文名"` | 写成 `"name"` 时设置页不显示预期文字 |
| 改完立即生效 | `"applyMode": "immediate"` | 默认是 `restart`，用户会认为"改了没效果" |
| 战斗中也能保存 | `"affectsGameplay": false` | 默认 `true`，战斗中被拒绝保存 |
| 分组标签 | `"group": "<名>"` | 留空则宿主显示"未分组" |
| 合法 `type` | `bool` / `int` / `float` / `string` / `enum` / `multienum` / `text` / `richtext` / `color` | 写别的类型无法渲染 |
| 联动显隐/启用 | `visibleWhen` / `enabledWhen`，形如 `{key, op, value}` | 只能自己写代码监听，容易漏同步 |
| 多选上限 | `multienum` 配 `minSelected` / `maxSelected` | 无上限时玩家可全选，业务侧要多判一层 |
| **没有图片类型** | `text` / `richtext` 是**只读展示**（`IsDisplay`） | 想在设置页放"演示图"只能退化为文字＋链接 |

读取一律 `Get<object>(key)` 再自行转换：`Get<T>` 类型不符会抛 `InvalidCastException`，缺键抛 `KeyNotFoundException`，而实际值类型可能是 `bool` / `long` / `string` / `System.Text.Json.JsonElement`。这两条属于用户记录的异常症状，本模板未复现。

`applyMode`/`affectsGameplay` 的生效语义仍以本页上表两个已实测示例为准；"默认值"是从用户记录归纳的，写清单时显式声明比依赖默认值安全。

## 账号、设置与对局数据分开验收

- 用户名提示关闭不等于账号建立；测试目录随机新建，跨进程复用和建档前提见 [启动页](startup.md)。
- Settings保存恢复不证明原版玩家资料或 Battle 读档成立。不要拿 settingsRestartVerified=true 声称全部存档功能可用。
- “本局统计”使用 Battle作用域，不写成账号累计值。KillCounter在Initialize调用 `context.Data.Declare("killCount", 1, codec)`，生命周期Restored用TryRead读取，变化后await WriteBattleAsync并检查结果；具体编解码见 [KillCounter](../../../examples/FeatureLab/Features/KillCounter.cs)。
- 数据schema与ID更改需先分析旧数据兼容和迁移，不直接修改玩家存档。自己的声明与版本号应稳定，宿主身份和author/show name不是同一概念。

完整保存恢复验收需要：建立必要测试资料→在独立对局产生数据→通过宿主保存流程→退出并使用同一 user:// 重启→恢复相同关卡/Mod身份→确认值保留、没有重复计数/重复奖励。当前没有这一流程的完整自动成功证据；不要用手写save.res或换个新目录代替。

运行工具第二进程保存的是同一次 FeatureLab 测试目录；重新运行整个工具会产生新目录。新局Ready与恢复Restored的机制见 [战斗服务](battle-services.md)。

拖拽布局使用Data.Local而非Battle，声明在Initialize、场景内TryRead/TryWrite；0.30同一隔离用户第二进程恢复已由[UI拖动案例](ui.md#自有浮动控件运行时中键拖动)覆盖。仅证明Local布局保存，不扩大为对局读档通过。
