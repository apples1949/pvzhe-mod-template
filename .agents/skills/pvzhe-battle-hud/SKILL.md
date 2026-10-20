---
name: pvzhe-battle-hud
description: 为 PVZHE 对局制作信息展示与统计，例如右下角击杀数；处理统计口径、生命周期、保存恢复与原版风格 HUD。
---

# 对局统计与 HUD

先按 [Wiki 索引](../../../docs/wiki/README.md) 核对发行版本与摘要，再按需读取 [battle-services](../../../docs/wiki/0.30.0/battle-services.md)。匹配基线时沿用已确认的操作路径；仅对缺项、差异或失败点补充分析，不从零遍历游戏。静态确认和待验证内容不能冒充运行验收。

输入：经过 mod-guide 的展示位置、统计口径、范围和恢复要求。输出：统计逻辑、HUD 和行为验证；纯展示不应修改游戏规则。

读 [战斗配方](../../../docs/recipes/battle-hud.md) 和 `examples/FeatureLab/Features/KillCounter.cs`。该例按已发布僵尸卡牌配置识别僵尸类型、按死亡时阵营过滤，观察 character.lifecycle.v3 的 death-committed；不是玩家击杀归因器。

1. 区分确认死亡、near-death、destroyed/visual-exit、复活与读档。不要用离场事件计杀。先明确“所有死亡”或“玩家击杀”，后者需要额外来源归因配方，不能复用例子却宣称已支持。
2. Initialize 建立订阅和数据 schema。新局 Ready 重置，Restored 从 Battle 数据恢复，忽略 SaveRestore/NetworkRestore 的伪新增事件。以实体身份和生命阶段去重，复活后再死亡是否计数应符合需求。
3. 在 BattleHud 挂载点建立右下角 Label，用宿主场景作用域清理和锚点布局，不遍历全树每帧找节点。展示用宿主字体；文字无需强行套装饰背景。设置变化即时刷新可见性。
4. 需要保存时使用 context.Data 的 Battle schema 与宿主存档流程；不要把“本局”写成整个账号的累计值。当前示例支持单人；联机范围和同步应另行验证。

验证：初值0，普通敌方僵尸死亡+1，植物/催眠友方/正常移除不增加，重复通知不重复，复活规则符合口径，新局重置，实际保存读档保留，分辨率改变锚点正确，显示开关立即生效。示例自动测试覆盖两次真实死亡和 HUD 更新，完整负例及读档要按功能另测并如实报告。

创建浮动HUD时即组合[pvzhe-ui-drag](../pvzhe-ui-drag/SKILL.md)支持中键拖动、右锚定与本地位置保存；统计Battle数据与布局Local数据分开，拖动能力发布后保留。首次交付主动告知“按住控件上的鼠标中键拖动，松开永久保存位置”，不等玩家提出调整；开发中匹配的拖动反馈按ui-drag直接定型默认布局。
