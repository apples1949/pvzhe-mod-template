# 对局统计

XWModCharacterPoints.Lifecycle 提供角色快照和阶段；死亡用 death-committed，near-death 不是最终死亡，visual-exit 可能只是正常移除。按事件 Origin 区分 Gameplay/SaveRestore/NetworkRestore；按僵尸卡牌的 characterConfig 类型建立角色键集合，再按死亡时敌方阵营过滤。示例集合在初始化生成，未包含的后加载角色需要额外适配，不以名称前缀猜测类型。

实体句柄去重，revived 时开启新生命阶段；Ready 清空新局，Restored 读取宿主 Battle 数据。Data schema 必须在 Initialize 声明，运行时写入用 WriteBattleAsync，并处理结果。HUD 使用 v3 BattleHud 的独立 Root/Lifetime 和底部右侧锚点，标签 MouseFilter=Ignore。其他玩家归因或联机同步属于新的口径/机制，不默认支持。
