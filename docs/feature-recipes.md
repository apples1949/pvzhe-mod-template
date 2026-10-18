# 功能制作配方索引

先经 pvzhe-mod-guide 理解需求，再读取对应制作 Skill 和 [版本化 Wiki](wiki/README.md) 中当前功能所需的主题。资料基于 0.30.0 发布 DLL/PCK，不要求游戏源码。

| 需求 | 按需读取 |
| --- | --- |
| 原版按钮、提示弹窗及生命周期 | [UI 配方](wiki/0.30.0/ui.md) |
| 对局展示、死亡统计及 Battle 数据 | [HUD 配方](wiki/0.30.0/battle-services.md) |
| 设置、生效时机和简单战斗命令 | [设置与规则配方](wiki/0.30.0/settings-data.md) |
| 关卡配置、内容身份、选关图卡与预设卡槽 | [关卡配方](wiki/0.30.0/levels.md) |
| 资源覆盖、基础角色、子弹、护具和地图 | [内容接入配方](wiki/0.30.0/content-authoring.md) |
| 首次启动用户名提示、独立存档 | [首次启动处理](wiki/0.30.0/startup.md) |
| 加载、界面、资源和退出异常 | [运行排障](../.agents/skills/pvzhe-mod-verify/references/runtime-troubleshooting.md) |

社区功能已拆为本地专职Skills，路由与来源见 [功能提取清单](community-skill-extraction.md)：资源数值、新投射物、新植物/僵尸、发射、护具、角色外观、地图、输入绑定和pmod补丁。它们是MDK制作指导，不依赖游戏内模组编辑器；具体资源/角色接入仍须按发行核验，未将外部案例直接升级为本版本实测事实。

[FeatureLab](../examples/FeatureLab/README.md) 提供可选实现及验证证据。其固定功能和测试参数不是通用开发默认要求；按玩家目标选取必要实现，为新功能建立自己的验收。
