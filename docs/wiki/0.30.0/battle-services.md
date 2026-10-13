# 战斗服务与生命周期

基线：[0.30.0](overview.md)。来源：发布 DLL 公共接口、KillCounter/StartingSun/Smoke。普通僵尸伤害与死亡、HUD更新、新局阳光增量已实测；通用必杀、玩家归因及联机未验证。

## 战斗操作入口

| 需求 | 已知入口 | 结果与边界 |
| --- | --- | --- |
| 当前对局是否运行 | context.Game.TryGetBattle(out snapshot)，Running/Paused | 等正确对局身份后观察；UI挂载不等于 Running |
| 查询角色 | context.Game.Characters.Query() | 返回快照；Handle、ContentKey、Camp、Column、Row、Hitpoints、Dead、Removing，不是可直接写入的节点 |
| 伤害角色 | await context.Game.Combat.Damage(handle, amount) | FeatureLab 对 ZombieNormal 施加100000伤害后观察到 death-committed；检查结果 Succeeded/Diagnostic和实际最终状态 |
| 查询/增加阳光 | Game.Economy.TryGetBalance(out long)、await Credit(amount) | 新局300→350已实测；不要直接写全局钱包 |
| 角色阶段通知 | Hooks.Subscribe(XWModCharacterPoints.Lifecycle, ...) | death-committed用于确认死亡，revived用于复活；near-death/visual-exit不等同击杀 |
| 关卡/对局阶段 | XWModLifecyclePoints.Ready、Restored、Result | 新局、恢复、结算分别处理，不以一个事件涵盖全部状态 |

Initialize 注册钩子并纳入 context.Lifetime，场景 UI 用 surface.Lifetime；异步命令返回时确认原作用范围仍有效。实体句柄应来自当前快照，不保留过期节点/句柄跨局复用。Queued/Accepted 不等于完成，命令完成也不等于已证明目标最终死亡。

## 识别“僵尸”与统计口径

Camp 是阵营：NOONE=-1、PLANT=0、ZOMBIE=1、ALL=2（发布枚举静态确认）。阵营不自动等于物种，也不代表造成击杀的玩家。示例从 TOWERDEFENSE_PACKETS 中 characterConfig 为 TowerDefenseZombieConfig 的项目收集角色键，再结合死亡时敌方 Camp 过滤；不要凭 Zombie 名称前缀猜类型。

普通敌方僵尸的确认死亡计数已实测。催眠友方、植物、复活、重复通知和恢复事件的完整负例未实测；当前实现的规则不能包装为全部对象都已验证。初始化生成的集合也未包含后来动态注册的新角色，相关需求需额外适配。

death-committed 按实体身份/生命阶段去重，revived后是否再次计数由用户口径决定。Event Origin 区分 Gameplay、SaveRestore、NetworkRestore；示例仅计 Gameplay，Ready新局重置，Restored读 Battle 数据。保存接口与未验证的完整读档边界见 [设置/数据](settings-data.md)。

“秒杀全屏”还需明确敌方还是含友方、当前场上还是视口内、是否包括离场/将来生成对象及单人/联机。巨大伤害不能直接保证无敌/特殊机制角色死亡，需观察实际死状态或通知。不存在已确认的通用 KillAll 或 Kill 接口时不能凭空调用。可以用 [测试对局](battle-testing.md) 验普通目标，再扩展范围测试。

## 新局阳光配方

Initialize 订阅 Ready，回调限定新的单人对局，读取设置参数，记录原余额→await Economy.Credit→检查返回→记录最终余额。不订阅 Restored 发奖，避免恢复重复获益；示例只验证了新局增量，完整读档不重复发奖仍需对相应功能验收。

对应代码：[StartingSun](../../../examples/FeatureLab/Features/StartingSun.cs)、[KillCounter](../../../examples/FeatureLab/Features/KillCounter.cs)、[Smoke](../../../examples/FeatureLab/Verification/Smoke.cs)。金额50是示例，不能当成玩家要求的默认奖励。
