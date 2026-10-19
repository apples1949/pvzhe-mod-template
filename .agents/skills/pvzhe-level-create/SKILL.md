---
name: pvzhe-level-create
description: 为 PVZHE Mod 创建章节与独立关卡，组织目录、选关图卡、配置、身份及胜负验证；模式页面由mode-create负责，不负责新增植物。
---

# 关卡制作

先按 [Wiki 索引](../../../docs/wiki/README.md) 核对发行版本与摘要，再按需读取 [levels](../../../docs/wiki/0.30.0/levels.md)、[battle-testing](../../../docs/wiki/0.30.0/battle-testing.md)。匹配基线时沿用已确认的操作路径；仅对缺项、差异或失败点补充分析，不从零遍历游戏。静态确认和待验证内容不能冒充运行验收。

输入：经过 mod-guide 澄清的地图/玩法、难度或波次、选卡规则、结束条件与奖励意图。输出：自己的关卡 JSON、目录注册与可进入的入口。

已有地图上的波次与选卡留在本Skill；新增背景/网格/道路/地形转pvzhe-map-create，需新角色时组合plant-create或zombie-create。

新建/追加章节或多关卡时读 [章节组织](references/chapters.md)；新模式入口、独立页面及直达/嵌套路线组合 [mode-create](../pvzhe-mode-create/SKILL.md)。章节是关卡组织层，不等于新的战斗玩法。

1. 读 [关卡配方](../../../docs/recipes/levels.md)、FeatureLab 的 Assets/level.json 与 DemoLevel.cs。用发布索引、配置和 DLL 核对 MapName、卡牌/僵尸键及波次结构；不要求源码。玩家无需自行提供注册键。
2. 使用独立 Name/saveKey、目录键和 Mod 身份。name 必须与目录 SaveKey 一致，不复制原版进度/解锁/奖励逻辑。示例使用 modern Process/Feature JSON 与 TowerDefenseLevelNewConfig，不混用旧配置字段。
3. JSON 包含自己的数据，资源用宿主注册键引用，不复制游戏贴图。构建器通过 resources 允许名单打包；JSON 不是可以单独注册为关卡的 Resource，入口需解析、初始化并发布目录。
4. 优先使用 Content.ProvideLevelCatalog 和类型化章节/选择配置；检查 XWModLevelValidation 与 TryResolve。目录需要资源身份，示例用专属 user:// 内存资源路径，依赖映射由宿主处理。
5. 接入现有关卡浏览页面。启动时携带 OwnerModId/CatalogKey/LevelSaveKey/Difficulty，通过集中适配代码校验并设置宿主启动状态，避免在每个按钮散布全局字段修改。单人示例不能自动延伸到联机。
6. 核对宿主浏览入口与卡槽的实际可用性：提供可见选关图卡、检查预设卡槽依赖。具体缺图、空卡槽及身份误用的处理集中在关卡配方，不以直达对局代替普通选择流程。

验证：目录显示、身份匹配、配置校验、进入正确地图、预设/选卡正确、波次生成、胜利/失败、退出、进度独立与读档。自动测试使用宿主 Damage 命令击败真实生成的两只僵尸，只证明启动/事件/结算链路；不证明难度平衡或玩家自然通关。
