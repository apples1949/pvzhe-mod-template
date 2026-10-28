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

## 读运行时数值的口径（用户实机记录，本模板待复核）

状态：以下来自用户写 HUD/显示类 Mod 时的实机探针定案，版本早于 0.30 发行；本模板只验证了快照查询与阶段通知。用于"组件取得到、数值就是读不到/恒为零"类问题。

- **组件有两套体系**：一套是"定义/包装列表"，一套是"运行时组件表"。在错的那套里按类型找会**恒为空且不报错**——先确认自己查的是哪一套。
- **字段类型可能不是标量**：例如计时类组件把"运行中/等待时长/当前进度"存成**按计时器名索引的字典**；按标量读取会永远不命中，且不抛异常。键名来自各组件定义资源。
- **真实数据可能在定义资源上**：实例字段为空容器时，配置值在组件定义里，访问器属性常声明在基类上；按字段名在派生类里找会找不到。

纪律：写判据前先打一条"字段类型 + 原始值"的诊断日志（把值 `ToString()` 出来看类型），再决定怎么读；成员查找要带上静态与非公开标志。不要按字段名猜语义——名字相近的字段常是另一种口径。

## 全局事件总线（用户实机记录，本模板待复核）

除上文 Hooks 之外，宿主还有一条全局事件总线（单例节点，并注册进运行期注册表），事件覆盖角色生成/受击、对局开始/失败/胜利、暂停状态、界面切换、波次开始等。

要挂"某个角色被生成"这类需求，**优先订阅事件**再用回调里的对象判断类型/阵营/格位，而不是每帧扫描注册表或全树找节点；每帧扫描既贵又容易漏掉池化对象。事件清单按当前发行核对，不当成稳定 SDK；回调里要自行确认对象仍有效、仍在当前对局作用域内。

## 识别“僵尸”与统计口径

Camp 是阵营：NOONE=-1、PLANT=0、ZOMBIE=1、ALL=2（发布枚举静态确认）。阵营不自动等于物种，也不代表造成击杀的玩家。示例从 TOWERDEFENSE_PACKETS 中 characterConfig 为 TowerDefenseZombieConfig 的项目收集角色键，再结合死亡时敌方 Camp 过滤；不要凭 Zombie 名称前缀猜类型。

普通敌方僵尸的确认死亡计数已实测。催眠友方、植物、复活、重复通知和恢复事件的完整负例未实测；当前实现的规则不能包装为全部对象都已验证。初始化生成的集合也未包含后来动态注册的新角色，相关需求需额外适配。

death-committed 按实体身份/生命阶段去重，revived后是否再次计数由用户口径决定。Event Origin 区分 Gameplay、SaveRestore、NetworkRestore；示例仅计 Gameplay，Ready新局重置，Restored读 Battle 数据。保存接口与未验证的完整读档边界见 [设置/数据](settings-data.md)。

“秒杀全屏”还需明确敌方还是含友方、当前场上还是视口内、是否包括离场/将来生成对象及单人/联机。巨大伤害不能直接保证无敌/特殊机制角色死亡，需观察实际死状态或通知。不存在已确认的通用 KillAll 或 Kill 接口时不能凭空调用。可以用 [测试对局](battle-testing.md) 验普通目标，再扩展范围测试。

## 新局阳光配方

Initialize 订阅 Ready，回调限定新的单人对局，读取设置参数，记录原余额→await Economy.Credit→检查返回→记录最终余额。不订阅 Restored 发奖，避免恢复重复获益；示例只验证了新局增量，完整读档不重复发奖仍需对相应功能验收。

对应代码：[StartingSun](../../../examples/FeatureLab/Features/StartingSun.cs)、[KillCounter](../../../examples/FeatureLab/Features/KillCounter.cs)、[Smoke](../../../examples/FeatureLab/Verification/Smoke.cs)。金额50是示例，不能当成玩家要求的默认奖励。

## 阳光收取与金币不同

0.30普通阳光为TowerDefenseSun（继承TowerDefenseSunBase），本轮活动组名Sun；调用原对象Collection后，要等待收取补间入账，再验证余额与CollectionCredited。收取开始isCollect=true不等于余额已到账，池化/离场后引用需核对有效性。金币为TowerDefenseCoinBase→TowerDefenseGroundItemBase，不属于SunBase；不能用枚举SunBase来证明金币没有生成。

发行CoinCreate(pos,num,...)的num是金额，按1000/50/10拆分，传1不会产生金币；这是本轮局部IL分析与有效10金额运行对照的结论，不把num一律解释为数量。具体拾取助手的键入/暂停、白名单、入账和设置边界见[社区方向实验](../../community-mod-experiments.md)。本轮仅单人，未证明不同账号所有权/联机收取。
