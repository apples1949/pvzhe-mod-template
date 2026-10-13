# 关卡配置与内容身份

基线：[0.30.0](overview.md)。状态：FeatureLab 的现代关卡配置、独立目录、原版图卡、预设卡槽、两次真实死亡与胜利已实测；其他玩法、失败/恢复/奖励仍按需求另验。来源：发行接口及自己的 DemoLevel/Smoke。

mod/Assets/level.json 使用现代 Process/Feature 结构，在运行入口读包内文件、Json.Parse、TowerDefenseLevelNewConfig.data 初始化。MapName/卡牌/僵尸键来自已发布内容；示例选择 FrontlawnEmpty、PlantFirenut、ZombieNormal。Packet Method=PRESET 跳过选卡并使用预设卡牌，波次 Spawn 的 Line 是从1开始的行编号。任意新地图/卡牌必须重新核验。

预设卡槽同时需要 SeedBank 与 PacketBank（PacketBankName=GeneralPlant）。SeedBank 声明列表；PacketBank 完成预设卡牌进入卡槽的宿主流程。仅添加 SeedBank 可能正常开局却没有可用卡牌。运行验收检查卡槽中实际可见的卡牌及其配置键，不能只检查 JSON 列表。

卡牌配置的 name 可能是本地化键（如 TOWERDEFENSE_PLANT_FIRENUT_NAME），不是注册键 PlantFirenut。运行卡牌也可能复制配置，不能依赖 Resource 实例相同。本例无卡牌覆盖，验收将实际卡牌的 saveKey 与角色内容键和 GetPacketConfigReadOnly("PlantFirenut") 对应字段比较，并等待入场动画后的实际可见状态。不要拿显示名/本地化名冒充内容身份。

关卡 name 是独立 saveKey，不能借用 Level1_1。构造 LevelChooseConfig→LevelChapterConfig→LevelCatalogConfig，普通难度不可缺失，目录键单独命名。通过 Config.TakeOverPath 建立本 Mod 专属 user:// 内存资源身份，再 Content.ProvideLevelCatalog；不保存或覆盖游戏资源文件。宿主在类型化目录转换中保留实际 Resource 对象。

章节和关卡必须提供 unlockImage；同时为章节提供背景与建筑。示例 GD.Load 引用原版第一章资源，不打包图片。验收必须通过可见章节/关卡的按钮进入游戏，不能只调用直达对局的方法。空图标可能没有有效点击范围。

v3 使用 contentEntries 声明 category=Level/key=demo。Content.Provide 的资源运行键包含 mod/owner/key，旧 provides 仅声明 demo 不能当作等价身份；示例已避免这个兼容陷阱。目录浏览与启动身份使用 Content.Identity("Level", "demo").RuntimeKey，而非直接传作者键 demo。0.30.0 的 privateResources 不支持 JSON，不应把 JSON 加进去；此示例自读 JSON，加载器会记录一条 unsupported package file 的非阻断诊断，不能称它已自动注册为资源。

目录浏览使用 XWModLevelSession.SelectCatalog 和 BrowserKey；启动前 CanPlay/TryResolve 校验，身份包含 OwnerModId/CatalogKey/LevelSaveKey/Difficulty，再设置集中适配的宿主启动状态。

自动运行脚本的测试参数只开启验收流程；普通 Mod 不自动击杀僵尸或改用户资料。测试覆盖实际波次、真实角色伤害/死亡/HUD/胜利，难度、自然通关、读档和多人需单独验证。结果不应泛化为这些能力均已验证。

运行代码参考 [DemoLevel](../../../examples/FeatureLab/Features/DemoLevel.cs)，已验证选择流程见 [BATTLE-01](battle-testing.md)。地图、角色、卡牌与原版关卡查询直接从 [内容索引](content-index.md) 开始，不从源码名称猜注册键。
