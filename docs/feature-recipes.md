# 功能制作配方索引

先经 pvzhe-mod-guide 理解需求，再读取对应制作 Skill 和 [版本化 Wiki](wiki/README.md) 中当前功能所需的主题。资料基于 0.30.0 发布 DLL/PCK，不要求游戏源码。

| 需求 | 按需读取 |
| --- | --- |
| 原版按钮、提示弹窗及生命周期 | [UI 配方](wiki/0.30.0/ui.md) |
| 对局展示、死亡统计及 Battle 数据 | [HUD 配方](wiki/0.30.0/battle-services.md) |
| 设置、生效时机和简单战斗命令 | [设置与规则配方](wiki/0.30.0/settings-data.md) |
| 关卡配置、内容身份、选关图卡与预设卡槽 | [关卡配方](wiki/0.30.0/levels.md) |
| 首次启动用户名提示、独立存档 | [首次启动处理](wiki/0.30.0/startup.md) |
| 加载、界面、资源和退出异常 | [运行排障](../.agents/skills/pvzhe-mod-verify/references/runtime-troubleshooting.md) |

[FeatureLab](../examples/FeatureLab/README.md) 提供可选实现及验证证据。其固定功能和测试参数不是通用开发默认要求；按玩家目标选取必要实现，为新功能建立自己的验收。
