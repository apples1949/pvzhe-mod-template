# 社区功能 Skills 提取清单

日期：2026-10-18。依据 [josnil/pvz-hybrid-mod-skills](https://github.com/josnil/pvz-hybrid-mod-skills/tree/50d2ee426bc217f6b194801b9ffbb97b1aaa9f9f)，固定提交 `50d2ee426bc217f6b194801b9ffbb97b1aaa9f9f`。本轮提取并改写功能流程，不安装外部复合Skills、不复制其生成器或素材；MIT署名与许可保留于 [第三方许可](third-party/pvz-hybrid-mod-skills.LICENSE)。

## 制作指导与运行能力分开

下列Skill现在可以用于理解需求、分析发行资源和指导制作，不再仅作为以后研究的外部链接。提取后已补做 [0.30最小路线验收](skill-audit-0.30.0.md)，并将操作事实写入 [内容接入Wiki](wiki/0.30.0/content-authoring.md)；自有动画、伴随脚本、特殊行为等仍须专项验证。不得把“有Skill”写成“有通用生成器或全部能力已验证SDK”。默认Hello World和现有单DLL打包约束保持不变。

具体游戏字段先作为社区提取线索；经过发行DLL/PCK及运行核实的部分已更新到参考资料和Wiki，其余保留待核验。玩家只需发行版和需要时的自有素材，不需要源码或游戏内模组编辑器。

## 新增功能入口

| 玩家表达 | 新Skill | 单一职责 | 社区来源位置（相对其仓库） |
| --- | --- | --- | --- |
| 改某颗子弹伤害、植物费用/冷却 | [pvzhe-resource-edit](../.agents/skills/pvzhe-resource-edit/SKILL.md) | 已有配置定位与最小改动；区别局部实例 | mod-authoring的资源/路径/字段；plant-data-fields |
| 添加一种新子弹 | [pvzhe-projectile-create](../.agents/skills/pvzhe-projectile-create/SKILL.md) | 独立投射物配置、命中与注册；不负责射速 | mod-authoring的投射物配置/覆盖及资源路径章节 |
| 添加一个植物 | [pvzhe-plant-create](../.agents/skills/pvzhe-plant-create/SKILL.md) | 独立身份、骨架与正常入口；专项行为另组合 | plant-authoring及plant-package-and-gates、plant-data-fields |
| 添加一个僵尸 | [pvzhe-zombie-create](../.agents/skills/pvzhe-zombie-create/SKILL.md) | 基础生成、移动、攻击及入口 | zombie-authoring、zombie-package-and-gates、zombie-stats-and-cc |
| 改射速/散射、增加发射能力 | [pvzhe-character-fire](../.agents/skills/pvzhe-character-fire/SKILL.md) | 触发、时序、生成点、弹丸与命中 | plant-fire-pipeline、plant-runtime-plugin、zombie-fire-and-marker |
| 加护具、破甲后暴走 | [pvzhe-character-armor](../.agents/skills/pvzhe-character-armor/SKILL.md) | 护具数据、槽、脱落与状态触发 | zombie-package-and-gates的护具体系、zombie-stats-and-cc |
| 换皮肤、动画、换头或对齐部件 | [pvzhe-character-skin](../.agents/skills/pvzhe-character-skin/SKILL.md) | 素材路线、动画结构和角色局部几何 | plant-skin、zombie-skin-and-head、zombie-asset-requirements及mod-authoring素材章 |
| 新地图、加行/改地形/换背景 | [pvzhe-map-create](../.agents/skills/pvzhe-map-create/SKILL.md) | 地图资源与玩法几何，不负责波次 | mod-authoring地图章及tools/map样板作为设计线索 |
| 添加快捷键、改键或触摸触发 | [pvzhe-input-bindings](../.agents/skills/pvzhe-input-bindings/SKILL.md) | 业务输入入口、设备语义与绑定 | mod-authoring的暂停/输入/手机适配章节 |
| 只有pmod，想调一个已有数值 | [pvzhe-pmod-patch](../.agents/skills/pvzhe-pmod-patch/SKILL.md) | 受限文本补丁与差异/派生包 | plant-pmod-hotpatch及patch_pmod_attrs.py设计 |

表中简写的plant/zombie参考均位于其同名Skill的references中；提取后的执行内容已在本地，普通开发不需要再读取整份社区Skill。

## 复用已有入口，不重复建 Skill

- 设置声明/热更新/草稿冲突→ [mod-settings的状态与保存参考](../.agents/skills/pvzhe-mod-settings/references/state-and-save.md)。
- 暂时控制/减速/禁发射与恢复→ [gameplay-feature的控制效果参考](../.agents/skills/pvzhe-gameplay-feature/references/control-effects.md)。
- 包/资源/角色身份与伴随类型候选协议→ [mod-develop的内容契约](../.agents/skills/pvzhe-mod-develop/references/content-contract.md)，供新入口共用。
- 产物校验、负例、采集/判定/报告分离→继续使用mod-verify；不用每个角色Skill再复制一套测试纪律。

例如“做一个戴铁桶、会发豌豆的僵尸”由guide理解需求，zombie-create负责基础，按需组合armor/fire；未要求新外观时不启动素材制作。“改现有僵尸血量”直接resource-edit，不重新创建僵尸。“做五波白天关”继续level-create，不改地图。

## 内容优化

主Skill保留用途、输入输出、核心步骤与验证；字段链、候选协议、素材与失败诊断置于按需references。不把护具、发射、换肤、BOSS及手机部署同时塞入植物/僵尸入口。多体节BOSS是zombie-create的条件性参考范围，不额外建立未经用户需求支持的大型工具链。

删除作者机器路径、F3/编辑器打开流程、工程标记交付要求、固定生成器复制、双构建环境、平台发布/邀请等约定。默认以MDK项目生成自有代码/配置，构建、安装、启用、发布分离。社区“唯一原因”“永远每帧”“只能某种工具”等表述改为有条件的调查与验收步骤。

源码、程序集、原版资源不成为玩家要提交或分发的内容；素材转换只处理用户明确提供且许可适当的输入。没有迁入外部_env、csproj、DLL或脚本，原快照的缺模块/XML/旧版本规则不传递到模板。

## 提取阶段的检查范围

本轮只提取文档型Skills与路由，不启动游戏、不构建社区项目、不运行其脚本。格式/链接/需求路由检查不能证明新角色或素材管线已经可运行；后续真实制作仍按相应Skill和mod-verify建立功能证据。更早的 [采纳分析](community-adoption.md) 保留其静态证据和工具改造计划，关于“暂不建立制作入口”的计划已由本轮明确提取要求更新。

后续真实验收单独记录于 [发行验收报告](skill-audit-0.30.0.md)，没有反过来将本节的静态审阅描述改成当时已运行。玩家路径只使用模板与发行版；维护者源码查证不成为玩家前置条件。
