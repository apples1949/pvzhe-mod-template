# 新植物的原版卡池与可种植链

基线：[0.30.0](overview.md)。来源为发行DLL、PCK及[超级机枪案例](../../super-gatling-example.md)。已测范围：GeneralPlant/Gold新增卡、自然自动装卡与自然选卡两条分支、正式卡片Plant扣费/冷却；原版所有关卡/多人和其他卡库不在范围内。

## 注册卡片和进入卡池是两步

Character/CharacterSprite/Packet的独立身份按[内容接入](content-authoring.md)对齐。注册Packet不会自动将其插入GeneralPlant。案例在Initialize深复制`ResourceManager.Instance.TOWERDEFENSE_PACKETBANKS["GeneralPlant"]`，将自己的Packet运行键追加到副本`category["Gold"]`，通过`Content.Override(new XWModContentId("", "PacketBank", "GeneralPlant"), ...)`提交，并在清单声明`overrides.PacketBank=["GeneralPlant"]`。

不要在每次主菜单回调直接改宿主共享Array，也不要为了新卡可用清空原版卡片的解锁条件。案例仅清除自己新增卡继承的解锁条件；原版卡是否已解锁仍由玩家进度决定。这里的覆盖单位是整个GeneralPlant资源，其他Mod也覆盖它时需核对加载顺序和合并方式；没有实测就不能承诺任意Mod自动共存。

## skipPacketChoose不必然异常

发行`TowerDefenseBattleFeaturePacketBank.PacketBankInit`在CHOOSE分支取`packetBankData.GetUnlockPacket().Count`并与`TowerDefenseManager.Instance.seedbankPacketMax`比较。可用卡数量不超过容量时，自动装卡并跳过选择；多于容量才需要选卡。这是数量分支，不能称为“Mod关卡一律跳过”。

本例隔离新用户：3张已解锁、7槽→skip=true，新卡已在卡槽且可种；设置若干原版关卡完成状态作为独立测试前提后：18张、7槽→skip=false，金色列表包含新卡，选择确认后可种。后者的资料前提只存在于夹具，生产Mod不写玩家进度或开启debug全解锁。

PRESET有意跳过选择，适合先验证植物本体；CHOOSE验证普通获得流程。它们应分别验收，不能因为最终需要选卡就让本体测试无限等待选择界面，也不能用PRESET通过冒充普通入口完成。

## 选择界面存在不等于已经能确认

`SceneManager.isLoading=false`、`packetList.Count>0`仅分别说明加载状态与列表构造，不能证明入场流程已进入等待选择。发行`TowerDefenseBattleProcessWave.GameEntry`先做入场/相机等步骤，再显示卡库并订阅`OnChooseOver`等待完成；`RockButtonPressed`在种子卡数量大于0时发出完成事件。过早调用可能发生在订阅之前，随后仍停在选卡。

案例原版1-12的定向测试等待卡库在树中可见、入场动画结束，并只读确认Wave的完成事件监听已建立，再选择、等卡片进入种子卡槽、确认；未强改阶段或重复发送确认。反射监听仅为本版本测试诊断，生产Mod不依赖该私有细节。常规玩家交互优先核对真实可见、可用按钮及阶段。

原版关卡还可能带对话、教程与预先种植：1-11有戴夫对话；1-12配置预置1～3列花盆，案例在(2,3)花盆上种植。不能因`FrontlawnEmpty`名称/截图推断所有关卡地形等价，也不能将这些原生前提当成新植物失效。只为当前验证目的选择合适关卡，所需存档前提留在隔离夹具。

## 种植失败先确认哪一层失败

| 层 | 首先读取的证据 | 避免的错误推断 |
| --- | --- | --- |
| 关卡初始化 | 完整日志最早错误、实际场景节点、Map及相关Feature实例 | Running=true就认为所有组件成功 |
| 地图/落点 | 目标格实际类型、植物允许的plantGridType/plantCover、格内对象及地图限制 | 凭背景判断能否种植；将集合Count当成格子类型 |
| 资料/卡池 | 实际用户、GetUnlockPacket、槽数、当前卡库与分类 | skip=true就是配置坏了；强改skip来制造选卡 |
| 卡槽/交互 | 选卡是否完成、实际卡片身份、可用/冷却/锁定及模态 | 手动改lock/alive等状态等同正常开局 |
| 新角色 | 同一有效格先用原版控制卡，再用新卡；完整骨架/配置/组件关系 | 所有Spawn失败都归因于注册；返回一个对象就算已入局 |

`GetMapPlantGrid().Count`只是集合大小。需要目标格信息时记录具体格与配置，不给数值臆造枚举含义。截图中的裸地也不能代替逻辑条件分析。

`GetShovel("false")`或`MowerInit→GetPacket("false")`首先是对应关卡资源引用/解析错误；检查旧/新配置类、JSON结构与该子系统字段。它不是新植物名错误的证据。现代Process/Feature示例使用TowerDefenseLevelNewConfig；不要在排查卡池时随意切为旧配置类并删减原版JSON。

## 普通单格植物无需Footprint注册

`XWModPlantPlacementService.Register`处理新的多格占位，本版Width要求2～64，且只在Initialize注册本Mod自己的新Packet。它不是所有植物获得种植资格的通用步骤。案例单格植物不调用它仍能正常种植；不能从“正式生成/放置条件不满足”的概括诊断直接推导缺少Footprint。

## 验收方式

案例的卡片Plant走宿主业务路径并检查扣费/冷却；选卡调用原生PacketChoose/RockButtonPressed，分别记录为程序化业务/按钮路径。系统鼠标及所有地图的点击适配仍需另验。新用户通过原版用户名框的公开字段和确认按钮建立，仅关闭提示不能证明建档；C#字段名不是find_child节点名，详见[startup](startup.md)。

局部失败不重跑整个发现流程：先恢复最小有效夹具，做原版/新卡对照，再只重验该层。配方与可重复命令见[SuperGatling](../../../examples/SuperGatling/README.md)，测试夹具不进入生产DLL。
