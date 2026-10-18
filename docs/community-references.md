# 社区 Skills 参考与取舍

审阅日期：2026-10-18。来源：[josnil/pvz-hybrid-mod-skills](https://github.com/josnil/pvz-hybrid-mod-skills)，快照提交 `50d2ee426bc217f6b194801b9ffbb97b1aaa9f9f`。这是外部来源评估，不是本模板兼容事实；现已按 [功能提取清单](community-skill-extraction.md) 改写为专职本地Skills。临时外部副本留在忽略目录，不安装或整份分发复合Skills/工具/素材。

仓库README以V0.28为入口，通用Skill另含0.29/0.30及后续个案补充。应按具体条目确认版本和出处，不能仅凭README、相同类名或“铁律”判断适用于本模板的发行摘要。项目采用MIT许可；后续若实际复制代码/文档，应保留对应许可与署名，素材许可另核对。原评估只作概念归纳；后续功能指导已提取改写并保留许可，没有迁入社区工具实现。

详细分析见 [采纳可行性与改造计划](community-adoption.md)：覆盖全部Skills、参考资料和工具族，列出当前快照的缺失环境模块、项目XML及旧验证器问题、逐项改造方案和分阶段完成标准。该文档为静态分析，不表示工具或角色能力已经移植。

| Skill | 主要内容与价值 | 本模板的使用边界 |
| --- | --- | --- |
| [pvz-hybrid-mod-authoring](https://github.com/josnil/pvz-hybrid-mod-skills/blob/50d2ee426bc217f6b194801b9ffbb97b1aaa9f9f/skills/pvz-hybrid-mod-authoring/SKILL.md) | 资源型/托管包、运行时、设置、输入、地图和素材；有生成器与检查工具 | 主文件约4548行，混合版本、发布平台及个案约定，按主题定位，不整份加载进普通功能流程 |
| [pvz-hybrid-plant-authoring](https://github.com/josnil/pvz-hybrid-mod-skills/blob/50d2ee426bc217f6b194801b9ffbb97b1aaa9f9f/skills/pvz-hybrid-plant-authoring/SKILL.md) | 原版基底复用、组件集/发射链、动画资源、卡库/图鉴、插件与验收 | 已提取plant-create及发射/外观等专项指导；角色注册与完整运行链仍待发行核验 |
| [pvz-hybrid-zombie-authoring](https://github.com/josnil/pvz-hybrid-mod-skills/blob/50d2ee426bc217f6b194801b9ffbb97b1aaa9f9f/skills/pvz-hybrid-zombie-authoring/SKILL.md) | 护具、换头/部件、发射点、根运动、素材需求、几何及负向检查 | 已提取zombie-create及护具/发射/外观指导；具体路径、组件与缩放按发行证据核验 |

## 值得吸收的通用做法

- 先评估宿主数据/组件能否满足，再决定是否需要托管代码；复用原版资源与用户自有素材分别处理，不因社区样板包含某功能就默认加入用户Mod。
- 可重复生成的小样板配合产物校验，比反复手改巨型示例更可靠；生成器与最终产物要对应，改变生成器后核对实际包，不只检查源码字符串。
- 对关键检查设计有针对性的负例，确认损坏真实输入/产物时会被拒绝；避免期望值与实现共用同一个被改变量导致假通过。只用于确有风险的检查，不为每个简单函数增加闸门。
- 静态包/入口/资源检查先做，视觉、动画、交互和业务仍由运行证据证明。已知结论、环境限制与待验证分别记录。

这些原则归入现有开发/验证流程，不另设“社区通用Skill”。本轮工具优化为 [可选项目配置](project-configuration.md)，让玩家更换C#项目时不必修改构建器。

## 不直接沿用的约定

不采用其机器绝对路径、必须全量恢复工程/指定唯一解包器、先问齐所有素材字段、默认复制某个大型生成器、必须测试作者的两份构建等工作区约定。本模板Hello World仍只需发行版、按需提取和已准备的DLL引用。

不把每帧轮询、某类API一概不可用、唯一程序集/平台行为等个案推广为所有版本规则；其对安全模式的删除日志/清空缓存操作也不作为默认排障步骤，先保留证据、核对作用域与宿主恢复路径。发布站点、邀请入口、自动安装或删除远程附件不属于制作授权。

有明确功能需求时直接使用已提取的本地Skill，按用户发行版复核接入契约并制作；验证成立后补对应版本Wiki事实。Skill指导可先于完整实测建立，但报告不能将待验证的具体路径、模式或效果包装为成功。
