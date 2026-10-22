# 网页方案到宿主发射链

输入为匹配发行的recipe/schema19、composition/v2和编译schema5；玩家采用仍需attack-editor真实事务。AI自主生成实验配方不伪造玩家confirmed。可选[AttackLab](../../../../examples/AttackLab/README.md)覆盖网页弹药子集，不是完整schema5解释器。

1. 先查发行已有发射组件、最终弹药配置和BulletField分支。配置足够时只改差量；组合调度不意味着需要重写弹药运动、碰撞、伤害和清理。预览应跟随宿主，不能反过来补一套运动系统。
2. 每组intervalSeconds独立，startDelaySeconds只影响首次，items.time为轮内相对时刻。有限窗口结束后的已排尾弹继续发，来源死亡/离场取消未发任务。对需要目标的攻击，先验证整轮触发条件再排队，不能无目标时排入旧轮尾弹等待未来目标；本来允许无目标发射的角色遵循原设计。若约定保留在途弹药，其重新寻敌不能再受来源存活条件阻断。动态炮口按角色变换接入，固定偏移实验不证明动画挂接。
3. host-guidance-v2的trackingStrength是离散枚举：0首次瞄准，1延迟追踪，2立即追踪。立即追踪复用PeaTrack等配置及宿主运动分支；延迟追踪先保持出射方向，逐颗生成0.5秒后且展开已完成，核验弹药实例身份仍有效，调用BulletField.SetTrackData(index,target)启动原生追踪，之后不再手写速度修正。导出的trackingDelaySeconds决定启动时间，暂停不计时；来源死亡仍处理在途弹药。目标资格排除不可受击、濒死等状态，优先复用宿主查询；尚无目标可等待后续有效目标。到期前碰撞/出界仍由宿主处理，不承诺命中。历史host-guidance-v1不能当成延迟追踪。
4. distanceModel=host-displacement-grid-width-v1下maxTravelCells表示消失距离：传给宿主浮点fireLength，0/空转换为-1不限。checkDistance=地图格宽×fireLength，宿主比较savePos至当前位置距离；内部整数fireLength字段只作不限哨兵，不能据此截断小数。它不是累计路程，也不决定何时开火；攻击触发范围由角色目标检测/发射组件另行定义。排射展开期间关闭命中与距离，结束后重置savePos并恢复，不另写常规距离销毁循环。
5. 投掷复用最终配置和原生catapult链：g=2000、标准H=300，目标发射时快照，默认目标水平偏移还受角色缩放影响。宿主会在传入height上加20，不能重复加。网页不导出catapultSpeedScale，组射速倍率也不作用于投掷；不要以每帧修改z/ySpeed/重力补偿预览。
6. 运行须同步宿主暂停、等待暂停、失焦策略、离场和权限。验证按编译调度、宿主实际运动、真实命中/表现分层；连续预览不复制全部离散积分与槽位回收。差异先定位宿主分支或自身适配，不放宽容差藏错。实验的事实与边界见[报告](../../../../docs/attack-lab-experiment.md)。

编译目标net9不保证裁剪宿主具备全部BCL；使用已验证基础集合和Godot JSON。资源键查发行注册表，不拿内部name代替注册键（如Cabbage与CabbageCatapult）。

首次瞄准逐颗以实际出生点计算发射瞬间的目标方向，出生排列不随目标旋转，trajectory.direction只叠加用户角度偏移；环形不能只旋转整套向外方向充当瞄准。延迟追踪不使用渐进角度修正，网页、Python模型和宿主启动时刻须一致（物理帧量化允许一帧差异），不要把启动延迟当成发射延迟。
