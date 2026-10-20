# 内容接入：资源、角色与地图

基线：[0.30.0 的发行摘要](overview.md)。2026-10-18 验收；具体覆盖见 [Skills 验收记录](../../skill-audit-0.30.0.md)。本页记录发行协议和最小接入方法，不要求游戏源码或 F3 编辑器。新动画转换、伴随脚本、自定义组件和联机仍须专项验证。

## 玩家输入与资源定位

原版卡池接入、自动装卡、失败对照及多格Footprint的边界集中在[卡池与种植](card-pools.md)。完整外部植物案例见[超级机枪](../../../examples/SuperGatling/README.md)，其具体外观/行为证据不扩大为所有角色已验证。

在自己的模板副本 prepare 后，从 PCK 读取三个注册表：

```powershell
python tools/mod.py extract --path Asset/Config/Character/CharacterResource.json Asset/Config/Projectile/ProjectileResource.json Asset/Config/Map/MapResource.json --dependencies
```

`--path` 后一次列多个路径；不要重复参数并假设每次都会累加。注册表分别给出角色的 Scene/Sprite/Packet、投射物键和地图键。它们大量引用 `uid://`；缓存提取未解析的 UID 不等于缺少资源。发行游戏能使用自己的 UID 缓存和 `.remap` 加载导出资源；需要读取实际属性时，可以由自己的托管 Mod 在宿主中加载并记录所需字段，编译仍只引用发行 DLL。原始 `.res/.scn` 不能当文本改写，不需要为此还原整个工程。

下列原版键已用于本轮测试：`PlantPeaShooterSingle`、`ZombieNormal`、卡片 `ZombieNormalBucket`、`PeaDefault`、`Frontlawn`。UID 和路径由匹配发行索引取得，不用本文替代版本核对。

## 两种接入路线

1. **托管注册**：在 `Initialize` 从已加载的宿主资源创建自己的差量，使用 `context.Content.Provide/Override`。只复制内存中的资源，不复制游戏文件进包。基础植物/僵尸复用宿主根类型时可先走这条路线，不强制增加 Companion 类、源生成器或新脚本。
2. **包内原生资源**：自有 `.tres/.tscn` 明确放入 `resources`，用 `contentEntries` 的 `category/key/path` 绑定，或沿当前发行确认的目录推导。相对引用与宿主 `res://` 分开。未给 path 的声明由托管入口完成；文件入包不等于注册。

本轮运行覆盖第一条路线及私有文本资源读取；不据此宣称第二条路线的全部目录、类型或伴随绑定通过。

## 身份必须同时对齐

新内容使用 schema 3，示例声明：

```json
"contentEntries": [
  {"category":"Character","key":"MyPlant"},
  {"category":"CharacterSprite","key":"MyPlant"},
  {"category":"Packet","key":"MyPlant"},
  {"category":"Projectile","key":"MyPea"},
  {"category":"Map","key":"MyMap"}
]
```

`Content.Identity(category, key).RuntimeKey` 得到 `mod/<modid>/<key>`。直接托管注册时，先写好资源内部身份：角色配置 `name`、卡片 `saveKey`、投射物 `name`，再 Provide。卡片的 `characterConfig.name` 必须能找到 Character，卡片或角色键还须能找到 CharacterSprite。不要把本地键、运行键、显示名和原版配置内部名混作一个值。

覆盖原版使用 `Override(new XWModContentId("", category, key), value, out diagnostic)`，保留原版目标身份；清单相应声明 `overrides`，不把相同身份同时放入 legacy 声明和 `contentEntries`。

实际负例：`PROJECTILE_CONFIG["PeaDefault"]` 的原配置内部 `name` 为 `Pea`。直接深复制后用PeaDefault做Override会报 `declares a different internal identity 'Pea'` 并回滚；将副本改名后虽然能注册，原版豌豆仍未必引用它。**先找实际读取键和通道，不为通过校验盲目改名**：本轮这个未被发射源使用的配置值已是53，实际发射/命中仍为20。新投射物则设置自己的运行键。

宿主在 Initialize 后检查声明和内容关联；Provide 返回成功不保证整个包通过。要检查 `package applied`、实际注册值和管理诊断，不能仅查自写的“注册成功”日志。结构在启动完成后冻结，不在进入每局时重新 Provide。

## 复用基础角色的最小配方

在 Initialize 取得 `ResourceManager.Instance`，按以下顺序制作一个独立角色。所有新资源、注册与必要字段应在当前 Mod 的失败诊断中可见：

1. `GetCharacterScene(hostKey).Instantiate<TowerDefenseCharacter>()` 得到完整宿主骨架，不从空 Node 拼出基础行为。
2. 对需要修改的 `config` 和 `ComponentSet` 分别 `Duplicate(true)`；只改自己的副本。组件可来自 `ParentSet`，不能只遍历当前层。核对嵌套资源是否仍共享；不修改原版对象来实现本 Mod 的局部效果。
3. 设置 `config.name` 为自己的 Character 运行键，改需求需要的参数。保留原有节点所有权；`new PackedScene().Pack(root)` 检查返回值。注册 Character 后释放临时实例，不加入战斗树来充当正式生成。
4. 注册 CharacterSprite；只需原外观时可直接使用 `GetCharacterSprite(hostKey)`，不复制图集、动画和贴图到包内。
5. 深复制目标原版 `TowerDefensePacketConfig`，设置自己的 `saveKey`、显示信息与 `characterConfig`，注册 Packet。原版的一名角色可能有多张不同护具/朝向卡片，先选准确卡片。
6. **核对解锁条件**：新 Mod 卡不能直接继承 `UnlockConditionLevelFinishConfig` 等原版条件。本轮自有关卡示例的新卡故意无解锁门槛，因此仅将新卡的 `unlockCheckList` 置为空；需要进度解锁时使用 `XWModProgressUnlockCondition`。不能清空原版卡库或修改玩家永久进度作为捷径。
7. 自有关卡的 SeedBank 使用新 Packet 运行键；波次等角色引用使用对应 Character 运行键。测试生成可用 `context.Game.Characters.SpawnAsync(packetKey, column, row)`，它仍检查正式放置条件；这不是卡片点击、扣费或冷却交互的完整验收。

同样的注册键可复用宿主 C# 类型；验收应确认新配置身份和行为，而非强求 `GetType().Name` 是新类名。只有新增托管子类行为确有必要时才调查 CompanionOnly，不能把上述路线的成功当成伴随脚本已验证。

## 已核对的字段与关联

| 功能 | 当前发行字段与注意点 |
| --- | --- |
| 本体血量 | `TowerDefenseCharacterConfig.hitpoints` 与 `hitpointsNearDeath` 分开；本轮新僵尸配置 333，初始实例是 403，不能仅断言实例等于 333。查当前初始化和濒死行为后确定所需口径 |
| 发射 | `FireComponentDefinition.fireInterval` 是 float，`fireNumAtOnce` 是 bool；`fireCheckList` 的 projectile 可为 `FireComponentProjectileSingle`，其 `projectileName`/`projectileData` 决定弹丸。`fireProjectileList` 是生成速度/角度/位置等配置，不能当作子弹注册表 |
| 实际伤害 | 资源索引键、ProjectileDictionary运行数据与创建数据是不同层。PlantPeaShooterSingle本轮实际使用`Pea`，创建数据baseDamage为-1（沿用运行数据），不是写死20。覆盖`PeaDefault`配置不等于覆盖它。明确非负创建伤害值确实也可能覆盖默认值，但须观察后再判断 |
| 护具 | 类型为 `CharacterArmorData`，当前集合是 `armorList`，不是社区线索中的 `armorLists`；槽为 `ArmorSlotConfig`。槽的 `damagePoint=-1` 表示沿用类型数据，自己的非负值才是明确耐久覆盖 |
| 出生护具 | `TowerDefensePacketConfig.initArmor`、角色 `currentArmor`、配置 `armorData` 和媒体/槽一起检查；本轮复用 `ZombieNormalBucket` 的 `Bucket`，新副本槽耐久设为 120。文件存在不代表出生佩戴 |
| 外观复用 | 完整宿主 CharacterSprite 负责动画和部件。对自有实例设置 `sprite.Modulate` 可做轻量颜色变体；是否在当前渲染路径可见要看实图，不等于已验证自有图集/reanim转换 |
| 地图 | `gridNum`、`gridSize`、`gridBeginPos`、`lineUse`、`cellConfig`；单元区域 `TowerDefenseCellConfig.pos` 为 `Vector4I`，用一基、含端点的起止列行。不是名为 tileSize 的通用字段 |

发射/命中事件的 `ProjectileKey` 可能是实际配置内部名：本轮原版发射显示 `Pea`，不是索引中的 `PeaDefault`。先记录事件真实身份和来源，建立与注册表的映射，再过滤；否则会出现“画面明明命中、检查器却没收到”的误判。自有弹丸则以自己的运行name对齐事件。不能据此对所有事件名做无条件字符串替换。

核对实际读取`Pea`后，最小Data通道覆盖在Initialize执行：

```csharp
var original = TowerDefenseProjectileRegistry.ProjectileDictionary[new StringName("Pea")];
var owned = (TowerDefenseProjectileData)original.Duplicate(true);
owned.baseDamage = 53;
if (!context.Content.Override(new XWModContentId("", "Projectile", "Pea"), owned, out var error))
    throw new InvalidOperationException(error);
```

清单声明`"overrides":{"Projectile":["Pea"]}`。此范围是引用该运行数据的发射源；只改某个植物时，改它自己的发射组件副本更合适。创建数据已有显式覆盖时还需按实际链路处理；不能将此例推广为所有弹丸通道相同。

## 地图先校验再入局

深复制 `Frontlawn` 后把 9×5 改为 9×4，必须同步限定 `lineUse` 到 1～4，并调整地形区域的末行；本轮是单一草地区域，不能把简单裁剪推广为任意道路/地形的改法。调用 `TryValidateRuntime(out diagnostic)`，失败在进入对局前停止。

只改行数的实际失败：`default enabled line 5 is outside 1..4`；修正行列表后还须检查 cellConfig，不等下一轮启动再逐个试。通过结构校验后，再检查 `GetMapFeature().config`、边缘格子的存在、正式放置、生成与移动。背景贴图仍可能有原版五行视觉，逻辑改行数不自动生成四行美术，应按用户目标进一步处理。

## 包和验收边界

本轮包只含清单、自有 DLL、自有关卡 JSON 与一个自有文本数值资源；没有宿主图片/DLL、源码引用或 Godot 编辑器依赖。普通启动与测试参数分离。完整覆盖范围、失败证据和未测能力见 [验收记录](../../skill-audit-0.30.0.md)，不要把最小复用链扩称为通用角色/动画 SDK。

## 自有地图背景与缓存模式

社区方向实验将原地图克隆为7×4，使用自己生成的棋盘Texture与克隆场景，不复制原图进包。0.30的GetMapScene(cache: false)会走ResourceLoader CacheMode.Ignore；参数默认值其实为true，而本发行的MapChange相关实际分支显式传false，不能从默认值推断所有调用。即使为PackedScene设置虚拟user://路径并写入mapScene缓存，后续读取仍可能尝试真实文件。曾导致地图加载错误，但战斗阶段已标Running、地图实例为空、坐标缓存为零；这些不是已确认的坐标接口缺陷。

本轮修正为将自有Texture保存到本Mod缓存的.res、PackedScene保存为.scn，保留宿主资源的外部引用，核对ResourceSaver返回值和GetMapScene(false)/GetMapTexture(false)可读，再Provide新地图。正常场景实例和背景必须另验；配置拓扑通过不代表背景加载。实验每次初始化重新生成缓存，若后续改为复用，需绑定宿主与Mod/参数身份，不使用旧同名文件冒充本轮成功。流程和具体结果见[社区方向实验](../../community-mod-experiments.md)。
