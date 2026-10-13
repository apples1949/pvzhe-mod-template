# 内容与资源查询

基线：[0.30.0](overview.md)。状态：以下注册表结构、键和场景路径已从发行 PCK 静态核对；列出的 FeatureLab 对象有单独运行证据。不分发原始注册表或素材。

## 直接查询已知注册表

| 问题 | PCK 相对路径 | 数据结构与查询方法 |
| --- | --- | --- |
| 哪些植物/僵尸角色、卡牌存在 | Asset/Config/Character/CharacterResource.json | 顶层为角色键；每项有 Packet 字典、Scene、Sprite。角色与卡牌不是一对一 |
| 地图名可以写什么 | Asset/Config/Map/MapResource.json | 顶层地图注册键→UID；MapName 使用键 |
| 原版目录/章节/关卡是什么 | Asset/Config/Level/LevelResource.json | 目录→Chapter数组→Level数组；每关有 OpenKey、SaveKey、UnlockImage、Level难度字典 |
| 哪些卡牌属于某卡池 | Asset/Config/PacketBank/PacketBankResource.json | 卡池键→Include与Category；Include需跟踪引用池，不能只读一个 Category 就当完整卡池 |
| 新玩家默认数据在哪里 | Asset/Config/Save/ConfigInit.json、KeyInit.json、LevelInit.json | 默认配置/键/进度信息；不是当前玩家存档，不可直接复制来代替建档 |
| 场景节点如何组织 | Scene/MainMenu/MainMenu.tscn、Scene/LevelChoose/LevelChoose.tscn | 文本场景可直接检查 node/type/parent、依赖和属性；脚本文件存在不等于含源码 |

先从 .work/pck-index.json 核对路径，再按需提取：

```powershell
$release = Get-Content .work/release.json -Raw | ConvertFrom-Json
python tools/mod.py extract --pck $release.pck --path 'Asset/Config/Character/CharacterResource.json' 'Asset/Config/Map/MapResource.json' 'Asset/Config/Level/LevelResource.json' 'Asset/Config/PacketBank/PacketBankResource.json' --output '.work/wiki-extracted'
```

PowerShell 可直接查询提取结果，不用重复设计解析器：

```powershell
$characters = Get-Content .work/wiki-extracted/Asset/Config/Character/CharacterResource.json -Raw -Encoding UTF8 | ConvertFrom-Json
$characters.PSObject.Properties.Name | Where-Object { $_ -like '*ZombieNormal*' }
$characters.ZombieNormal.Packet.PSObject.Properties.Name
$characters.PlantFirenut
$maps = Get-Content .work/wiki-extracted/Asset/Config/Map/MapResource.json -Raw -Encoding UTF8 | ConvertFrom-Json
$maps.PSObject.Properties.Name | Where-Object { $_ -like 'Frontlawn*' }
```

## 常用键及区别

- **已实测**：地图 FrontlawnEmpty；卡牌 PlantFirenut；角色与卡牌 ZombieNormal；卡池 GeneralPlant 配合 PRESET。
- **静态确认**：角色 ZombieNormal 包含卡牌 ZombieNormal、ZombieNormalBlackHelmet、ZombieNormalBucket、ZombieNormalCone、ZombieNormalHelmet、ZombieNormalScreendoor、ZombieNormalSpecialHelmet。不能仅靠角色键去重而漏掉卡牌变体。
- `ResourceManager.Instance.TOWERDEFENSE_PACKETS` 是运行时卡牌键→配置；配置的 characterConfig 类型可用于识别角色类别。`TowerDefenseManager.GetPacketConfigReadOnly(key)` 适合只读查询，不把原版共享配置当作自己的可变资源。
- 卡牌 name 可能是本地化文本键；saveKey、角色内容键、卡牌注册键、UID、Mod runtimeKey 分别有不同用途。具体身份比较见 [关卡页](levels.md)。

res:// 路径、UID、.import/.remap 与导入产物需要结合使用；原图不在 PCK、只有 .import 不等于不可加载。不要重建完整编辑器工程或复制宿主图片来解决已经能 res:// 引用的资源。没有对当前需求的证据时只提取所需项目，不从零重新扫描全部 API。

## 按需核对公共接口

prepare 编译 HostProbe 后可运行：

```powershell
dotnet tools/HostProbe/bin/Release/net9.0/HostProbe.dll .work/references --types PVZHE.ModEditor.ModSystem.XWModCombatService PVZHE.ModEditor.ModSystem.XWModCharacterService PVZHE.ModEditor.ModSystem.XWModGameServices LevelChoose
```

输出只包含所指定宿主类型声明的公共成员，不含继承成员或方法体。缺失的方法不能凭 DLL 字符串搜索结果推断可调用；继承成员或 Godot API 需另核对实际类型。公共签名存在也不能证明权限、副作用和事件顺序。

UI 布局分析需要跟踪实际场景、实例 PackedScene、动画轨道、脚本/程序集行为及动态创建入口，不以贴图名或截图判断是否有控件。左下原版选项的已确认结构见 [UI 控件条目](ui.md)；反射结果不含方法体，显隐逻辑缺失时另做对应实现分析并明确待核验。
