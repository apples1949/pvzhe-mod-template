# 攻击方案映射实验

这是可选的单人实验 Mod，不改变 Hello World。复用发行版的豌豆射手、普通僵尸、弹药与草坪，包含八个模组关卡；不分发游戏素材，也不需要源码、外部动画或网页交互。玩家自行使用时先在仓库根目录按主 README prepare 发行版。

| 关卡 | 设计重点 |
| --- | --- |
| straight | 直线、0.4秒周期、2.5格宿主消失距离 |
| fan | 5发、40°、逐颗0.1秒；0.25秒新一轮，尾弹重叠 |
| ring | 6发、55像素半径、30°锚点旋转、120°运动方向偏转 |
| parallel | 5发、40像素间隔、0.15秒展开、逐颗0.07秒 |
| starfruit | 原版五向及中心预设的五个出弹偏移 |
| homing | 首次瞄准、延迟追踪/立即追踪三层；移动目标、延迟尾弹、来源死亡 |
| lob | 两层原生投掷，错开0.25秒；组射速倍率不改变弹道 |
| nested | 两层嵌套倍率、独立周期、相加启动延迟、禁用层及空组 |

## 构建与运行

```powershell
python examples/AttackLab/verify.py build
```

输出路径由 `RUN_DIR` 打印，包为该目录下 `attack-lab.pmod`。打包会核验发行引用、编译所有设计与计划一致、检查入口和允许名单。安装到已确认的游戏 Mods 目录并启用重启，从游戏原生模组关卡目录选择实验关卡，种植预置的豌豆射手。只有实验关卡内的豌豆射手接管发射；其他关卡不受影响。宿主扩展点注册在启动时冻结，禁用或升级后重启。联机不接管自定义发射。

## 无人工交互的验收

以下命令必须串行，使用独立用户目录和发行副本，不修改日常存档、不安装到日常 Mods。主菜单、选关、种植、暂停等使用宿主业务/API或信号，不是系统鼠标验收。

```powershell
python examples/AttackLab/verify.py first
python examples/AttackLab/verify.py second
python examples/AttackLab/verify.py normal
# 只排查受影响项
python examples/AttackLab/verify.py nested
python examples/AttackLab/verify.py homing
# 分项补采，避免重复整个场景组
python examples/AttackLab/verify.py first --only-case ring
# 六个新增边界场景：小数距离、立即/延迟追踪重新寻敌、投掷快照、无目标尾弹与暂停
python examples/AttackLab/verify.py boundaries
# 来源死亡后的在途延迟追踪（只跑这一项）
python examples/AttackLab/verify.py weak-owner
# 离线重判，不启动游戏；路径取本次 RUN_DIR/runtime
python examples/AttackLab/verify.py assess --run '<本轮runtime目录>'
```

`first/second` 分开覆盖八个场景，避免发行测试帧数限制截断整轮；不是重复执行同一用例。每轮独立快照包含 C#、recipe、plan、包和发行/驱动摘要。测试代码在 `Verification/`，通过 partial 观察点只编入独立审计 DLL；生产 DLL 不保留自动开局、逐帧采样、历史弹药数组或验收入口。`normal` 使用生产 DLL 且不带 Mod 测试参数，只确认普通启动与注册，不冒充人工关卡导航。

## 文件与边界

- `design/`：AI主动生成的八份可编辑 composition v2；不是伪造的玩家网页确认。
- `mod/Assets/`：对应 schema5 编译结果及最小关卡。设计变化后用 `tools.attack_web.compile_recipe` 重新生成，构建拒绝过期计划。
- `PlanRunner.cs`：网页直线/抛物线弹药子集的示例适配器，包含独立组调度、展开、延迟启动宿主追踪；原生追踪、消失距离和投掷交给宿主；不是任意 schema5 的通用SDK。
- `Entry.cs`：弹药副本、原生关卡目录及对局作用域；不覆盖共享原版配置。
- `Verification/`、`verify.py`：采集、离线判断和正常启动检查。

本例使用植物根坐标的固定逻辑像素，未绑定随动画移动的炮口。迁移到运动部件植物时必须另接动态 Marker，不能把本例当作炮口挂接已验收。触发条件仅采用实验场景内存在可攻击僵尸，不代表任意植物的攻击范围、状态机或原版动画。碰撞、伤害和销毁由宿主处理；网页只编辑发射方案，不描述命中效果。

投掷不提供额外运动时间倍率；与原生追踪及浮点fireLength一样，优先复用宿主。延迟追踪从每颗生成起0.5秒后调用宿主SetTrackData；之前保持出射方向，之后完全使用宿主追踪，不重写碰撞/伤害。内部case名weak-retarget/命令weak-owner仅为既有测试标识，不再代表弱转向。密集组合观察到宿主交换删除造成的单步未移动现象，详见[实测报告](../../docs/attack-lab-experiment.md)；不修改游戏程序集，不掩盖连续预览与实际离散运动的区别。

新增边界配方与断言位于Verification/boundary_plans.py、Boundaries.cs及boundary_check.py。实际采集与离线业务判断分离；边界测试资源只在相应用例的审计包中存在。无目标不排入未触发轮次；来源死亡取消待发，保留在途弹药的独立寻敌。它们不替代角色本身的原生攻击触发条件。

密集普通弹药的逐帧轨迹按场景分别保存，只有缺失位移与实际生命周期事件对应时才归为宿主离散处理差异；不全局扩大容差。长延迟循环压缩为等差待发序列，保留数量/时刻和取消条件；正式示例不保留逐帧采集缓冲。
