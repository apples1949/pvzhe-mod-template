# 护具数据与状态对应

源自社区僵尸包/护具资料，见 [清单](../../../../docs/community-skill-extraction.md)。0.30已核对 `CharacterArmorData.armorList`（不是armorLists）→ArmorSlotConfig→卡片initArmor/角色currentArmor→精灵媒体/状态；最小耐久覆盖与实测边界见 [版本配方](../../../../docs/wiki/0.30.0/content-authoring.md)。

- damagePoint等耐久字段与角色hitpoints分开；0.30槽damagePoint=-1沿用护具类型数据，不等于负耐久。只改自己深复制的槽；flags按当前枚举解析，不能把一个整数推广为所有护具类型。
- 槽名可能参与ArmorHitpointsEmpty及状态切换，重命名需沿调用关系检查；复用原版槽通常比新建媒体协议简单，但并非无条件兼容。
- 包内护具资源引用和宿主res://引用分开，角色出生时是否佩戴不能仅凭护具文件存在推断。
- 多层护具要定义伤害顺序、溢出、特殊攻击和表现；本体死亡/离场后不继续触发状态变更。

验收覆盖：有护具/无护具、恰好耗尽/超额伤害、重复通知、脱落可见性及后续行为。仅验证一个普通护具，不宣称无敌/盾牌/BOSS机制全部支持。
