---
name: pvzhe-zombie-create
description: 为 PVZHE Mod 新建独立僵尸，复用原版基础行为并组织配置、场景、入口与移动攻击验证；支持外部已有僵尸复刻的行为统筹，护具、发射及外观改造由专门Skill处理。
---

# 创建僵尸

先经mod-guide确定基底行为、出现途径和作用范围；新美术仅在需求需要时澄清。输入：玩法、发行资源和可选自有素材。输出：独立僵尸与必要适配。0.30的宿主骨架复用、新身份、生成/移动/啃食/确认死亡及原护具复用已实测；特殊行为另验，不替代本次需求验收。

复刻经典PvZ/其他改版僵尸时，先组合[pvz-source-identify](../pvz-source-identify/SKILL.md)、PAK提取和reanim-import，按[共用复刻方案](../pvzhe-mod-guide/references/recreation-plan.md)记录依据、适配选择及缺项；不能把动画导入当成复刻完成。

1. 按 [内容契约](../pvzhe-mod-develop/references/content-contract.md) 和 [僵尸骨架](references/zombie-assembly.md) 查基底；先正常移动/啃食/死亡，再加特殊能力。
2. 建立自有Key、配置、卡片（需要时）、场景、组件集、精灵及当前加载器要求的伴随类型；覆盖原对象参数转resource-edit。
3. 新护具组合character-armor，会发射组合character-fire，换头/动画组合character-skin；不要从大型BOSS/投掷样板复制整套行为。
4. 按需求接入自有关卡或可见卡库/图鉴，选择正确阵营和生成条件，不修改原版永久解锁作为入口捷径。
5. 构建并验证新身份和真实基底行为；移动、碰撞、受击、死亡与结算分别观察。具体特殊机制用gameplay-feature，不把所有状态机逻辑写进入口。

验证：实际新类型、正确阵营、能生成/前进/遇植物攻击、表现与伤害对应、离场清理；护具和发射另按对应Skill验，静态声明不证明僵尸可玩。
