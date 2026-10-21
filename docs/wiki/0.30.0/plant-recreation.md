# 植物复刻：发射与动作绑定

基线：[0.30.0发行摘要](overview.md)。制作统筹用 [plant-recreate](../../../.agents/skills/pvzhe-plant-recreate/SKILL.md)，资料/PAK属于 `pvz-*`，宿主接入属于 `pvzhe-*`。本页事实来自发行程序集核对和 [复刻实验](../../plant-recreation-experiment.md)，不要求玩家取得源码。

## 先建立行为关系

“原动画已播放”与“植物已复刻”之间还需要：普通入口/卡片、配置与种植、目标判断、攻击时序、弹丸碰撞及可见反馈。来源未说明的参数标为推断或实现选择，不能由图鉴乘法反推出唯一程序。`fireInterval` 配置值不等于实际两次攻击开始间隔，应采集实际时间。

当前发行可复用 `FireComponentDefinition`，自有副本的 `fireProjectileList` 每项支持 `checkProjectileId`、`firePosId`、`speed`、角度制 `dir`、`offsetLine`、`fireNumSkip`、`fireEventNeed`。一条配置表示一个发射项；多个动画事件、`fireNum`与`fireNumAtOnce`会共同影响数量，不能把所有数字同时设为想要的总弹数。

| 路线 | 含义/检查 |
| --- | --- |
| 多角度 | `dir`形成不同速度方向；还要核验跨行命中，不能只看子弹飞向邻行 |
| 行偏移 | `offsetLine`表达进入相邻逻辑行的路线，不能与随机扇形等同；边界夹行可能改变结果，另验 |
| 检测区域 | `checkRayResources`和`checkShapeResources`选择实际检测几何；跨行需匹配检测与目标筛选，不能只改弹道 |
| 发射点 | `spritePath`对应实际动作节点，`firePosMarkerPaths`必须解析为正确Marker2D，并与渲染偏移独立标定 |

运动炮口可复用`AdobeAnimateSlot`：0.30发行`UpdateChild`中，mode=0时以`followSlotId-1`查询层姿态，叠加精灵offset，再用`TranslatedLocal(slot.offset)`变换素材内标定点；useRotate/useScale控制随后保留的插槽基变换。插槽本身不是Marker，将Marker2D作为子节点并把角色相对NodePath写入firePosMarkerPaths，Pack前设置Owner，实例化后核对。超级机枪0.1.3已在此版本实测普通14发及特殊300发出生点跟随嘴部层、水平速度，具体素材点和高度范围见[案例](../../super-gatling-example.md)；不能据此套用其他素材层号或认定所有枪管都同一开口。

出生点Y分布不等于速度Y分布：窄高度平射改变前者，角度扇形改变后者，弹道随距离扩张。`FireComponent.CreateProjectile`静态链先读取Marker的逻辑全局位置，交给BulletField创建；上述案例用同步调用期间的局部标记偏移并在finally恢复，OnBulletSpawned读取实际BulletData核验，另核对画面。该配方限于当前同步创建链，改为延迟队列必须重新确认采样时机。

三行范围不能无条件推广为无限斜射：角度、距离与碰撞共同决定覆盖。严格限制行范围或随机分布需独立设计并验证；本轮最小扇形原型不是已证明全距离只命中三行的通用方案。

### 默认批处理追踪的参考点

自定义弱制导的目标查询须匹配检测几何：同一发行的`FireComponent.FindCatapultTarget`在非checkAllLine分支依赖区域形状，只有射线的单发豌豆基底不能直接复用它。`CheckRayHit(ray,flags,runtimeIndex)`沿原版射线/攻击网格筛选，并写入firstCharacter；若复用须了解该副作用，不修改共享检测资源。超级机枪0.1.6的隔离实测显示投手查询为空、同一射线可得到有效目标，自有有限转向随后生效。该实现以公开GetLogicalGlobalPosition为目标点，不声称与原版私有影子缓存路径完全相同；完整证据及边界见[案例报告](../../super-gatling-example.md#016弱追踪接入)。

匹配基线DLL的`BulletField.ProcessTrackData`调用目标`TowerDefenseCharacter.GetGlobalPositionForPhysicsFrame`，后者取当前影子全局变换原点（有效时）或角色GlobalPosition，缓存于物理帧；该链没有添加“头顶Y-65”，也不是默认取图片包围框/头部插槽。不同角色父变换与自定义弹丸仍须核对，不扩展为所有玩法通用目标点。

有效目标时该链直接用归一化(目标位置-弹丸pos)乘speed作为vel；`LerpAngle(delta*5)`只更新rotation，不能据此给飞行方向加转速上限。无效目标的重选、阵营/高度/碰撞过滤及半径30线段进入判定是另外的宿主行为；网页以普通僵尸真实受击矩形作接触消失预览，不模拟伤害/阵营/高度过滤。自定义限速转弯可作为独立意图，不能标为原版默认追踪。此处为发行IL静态核对，尚未以真实追踪弹丸运行对照。

默认Frontlawn资源的gridBeginPos=(260,75)、gridSize=(80,98)、plantOffset=50已由隔离发行实例读取。`GetMapCellPosCenter`按一基格坐标减1后加半格；`GetMapCellPlantPos`在地图缩放1时Y加plantOffset。第3行参考中心Y=320、植物节点Y=321；透明图内节点不等于脚底，不能将任意Y坐标或图片底边当成行中心。

补充静态核对（同页基线DLL，2026-10-21）：`TowerDefenseCharacter.GetLogicalGlobalPosition()`直接返回角色根节点`GlobalPosition`；`GetMapCellPlantPos`的Y为gridBeginPos.Y+(row-1)×gridSize.Y+plantOffset×地图GlobalScale.Y，不是格中心再加plantOffset。透明素材的imageOrigin标定的是图片内角色根原点，不能替换为嘴部/图片中心。普通追踪使用的物理帧影子缓存原点见上节，不能混同为精灵阴影图的像素中心；本补充未新增宿主运行验收。

### 单发豌豆的预览速度基准

发行隔离对局`capture-0973e9f8`用原版PlantPeaShooterSingle卡片种植，实际Pea弹丸初速度300逻辑单位/秒，物理采样0.4秒位移120；速度字段与位移速度一致。FireComponentDefinition.fireInterval标称1.5秒，5次出弹时刻约[0.6333,2.0,3.4667,4.8333,6.1667]，观察平均约1.3833秒；配置间隔不等于每轮精确实际间隔，单个短样本也不是通用攻速常量。

攻击方案编辑器以该发行标称间隔初始化攻击周期，以实测弹速定义1倍弹速；两者分开绑定摘要和来源，保存方案使用实际秒数/逻辑速度，不因重开自动改写。新发行须重新测量，特殊弹丸/动画/状态修正另验；此基准不证明任意Mod弹道、角色攻速或联机已还原。协议与用法见[攻击方案编辑器](../../attack-web.md)。

### 标准投手抛射

0.30发行`BulletField.TrySpawnFromConfig`普通抛射分支：g=2000，H取最终配置catapultHeight，初始高度z0≥0，T=√(2H/g)+√(2(H+z0)/g)，ySpeed=-√(2gH)，地面速度=(目标快照-地面起点)/T。普通有角色来源时，地面起点Y为角色物理位置Y+20；目标快照另包含目标Scale与spriteGroup.Scale作用的X偏移。最终配置须从实际创建链核验，不能用旧Asset/Config下同名资源的400/600数值代替注册器解析后的配置。

隔离发行运行`corn-baseline/runtime2`，原版PlantCornpult卡片在第1列第3行种植，真实出弹两次均为Kernal，H=300、z0=94.740509、ySpeed=-1095.445115、T=1.176006338秒。地面起点(297.72858,341)，两次目标快照分别(846.09796,321)/(805.5884,321)，地面速度分别(466.298,-17.006712)/(431.85126,-17.006712)。距离改变而飞行时间不变，因此没有固定的“玉米水平弹速”；H是高出出膛高度的上升量，屏幕峰值还受地面Y移动影响。摘要匹配本页发行基线。此轮采集出生参数，未逐帧测量整个飞行，也未覆盖黄油分支。

补充隔离同局`lobber-profiles/runtime`，实际通过三种原版卡片种植并观测出弹：

| 植物 / 弹药 | catapultHeight | 出膛z | catapultTime / 秒 |
| --- | --- | --- | --- |
| PlantCornpult / Kernal | 300 | 94.740509 | 1.176006338 |
| PlantCabbagepult / Cabbage | 300 | 61.734680 | 1.149166387 |
| PlantMelonpult / Melon | 300 | 87.253525 | 1.170019532 |

三者ySpeed均为-1095.445115；相同H/g但出膛高度不同，不能断言时间或屏幕曲线完全相同。此轮各观测至少一次出生，非全投手/黄油/特殊能力的穷举，也未逐帧测量完整飞行。

`ProcessCatapultData`静态核对先ySpeed+=2000*dt，再z-=ySpeed*dt，地面pos+=vel*dt；下降高度及目标距离检查决定碰撞/落地。编辑器默认使用`host_catapult_reference`固定标准H=300/g=2000，每次实际发射按用户炮口相对植物Y+20的高度自动解算T；不向玩家暴露重力/时间，不需点基准按钮。连续轨迹只近似可见形状，不复制离散积分、障碍/目标碰撞或命中判定。新发行升级须复核最终配置、创建公式、坐标/高度和运动分支，不能只比对一个同名资源。

## 导入动作和事件

保留原始时间轴。可以将宿主所需 `BodyIdle`、`HeadIdle`、`HeadFire` 显式映射到原始片段区间，属于别名，不是网站custom_*合成。身体与头部使用独立播放实例，并按[动态挂接契约](animation-import.md#分体动画跟随坐标与动作播放)绑定真实控制轨和参考逆变换；跟随、插层和原点须重新标定，不能沿用另一套素材的层编号。

0.30读取DAT会建立 `EventFrameIndices`。若在加载后给自有数据的 `events` 补写事件，旧的空索引会使事件未派发。本实验在定义发布、精灵实例创建之前补写事件，并将该索引设为null，让宿主按最终表重建；随后验证真实事件、发射与命中。此事实限于该版本，不推广为任意缓存都必须清空。更改已使用资源还涉及定义缓存，不能直接套此初始化配方热改共享宿主数据。

示意（`frame`来自明确的绑定方案，不是通用固定帧）：

```csharp
data.events[frame] = new Godot.Collections.Array {
    new Godot.Collections.Dictionary { { "Command", "fire" }, { "Argument", "" } }
};
data.EventFrameIndices = null;
```

事件只加到需要的动作区间；检查片段开始位置/倍速是否跳过出膛帧。不要同时用事件、连发次数和自写计时重复生成子弹。原始素材没有程序事件时，补写的时点属于接入选择，不能标成原版事实。

## 场景、预览与验收

角色场景与CharacterSprite预览场景分别保持正确根节点及子节点Owner；不能随意将仍属于外部场景根的子树直接Pack成独立预览。更换动画媒体/层数量后核对显隐与替换数组的长度、类型和旧索引；Pack返回成功后仍需实例化/加载检查，不能忽略宿主数组类型错误。

材质/动画offset移动画面，Marker位置未必随之移动；脚底、阴影和实际炮口分别检查。对局、卡槽和图鉴可能使用不同实例，不把一处显示通过扩大为全部入口。只为当前实例修正，不扫描并覆盖所有角色。

最终验收按正常卡片输入、费用/冷却、无目标与邻行目标、实际角度/数量/间隔/伤害及画面分项记录；程序化Spawn仍不是卡片点击证据，宿主合成输入也不是系统鼠标证据。具体覆盖及近似参数保留在实验记录，不写成每个复刻植物的强制数值。

### 炮口参考位置与静态插槽边界

2026-10-21在匹配发行的隔离副本中，沿FireComponentDefinition.firePosMarkerPaths读取角色原生场景，复制包含Marker子树的AdobeAnimateSprite并按原生祖先变换播放待机参考姿态：普通单发豌豆约(26.149,-14.842)、裂荚后头约(-45.686,-15.229)、小喷菇约(14,15.824)，均相对角色根原点。帧/路径及精确浮点数见[网页预设资料](../../../tools/attack_web/origins.json)，运行证据.work/attack-origin-presets/runtime-pose2。仅实例化未播放时的玉米插槽约(27.500,23.625)，不能当实际炮口；既有原生玉米出弹的视觉偏移约(-2.271,-74.741)，来自地面位置扣除z高度，见上文投手证据。

参考姿态不是整段动作绑定，也不保证同类植物通用。GetCharacterSprite提供的纯视觉预制体可能没有角色场景额外添加的Marker；此次用角色场景内原生视觉子树保留这些挂点，不能只按纯视觉实例缺节点断言发行版无炮口。中心半径等编辑器布局建议不属于宿主机制。

### 基础杨桃五向与出弹点

匹配本页0.30发行摘要。发行资源读取确认（2026-10-21）：`Asset/Anime/Character/Plant/Chapter0/Starfruit/Scene/TowerDefensePlantStarfruitComponentSet.tres`内character.fire的fireProjectileList依次为330/270/180/90/30度，speed均500、firePosId依次0～4，checkProjectileId均0；Star弹药，五个firePosMarkerPaths对应`SpriteGroup/TransformPoint/FireMarker`至`FireMarker5`。不能按均匀环形五颗代替。

用发布版ResourceManager.GetCharacterScene("PlantStarfruit")实例化后，累积各Marker到角色根之间的Node2D.Transform，得到参考偏移：约(30,-18)、(1,-28)、(-33,1)、(0,40)、(35,24)。它们是五个不同的场景标记，非单一中心；精确值和路径保存在tools/attack_web/origins.json。此读取未推进角色动画或逐发采集，不能当作任意角色的动态炮口证明。

对照`Other/StarPeater/Scene/TowerDefensePlantStarPeaterFireComponentDefinition.tres`是三项dir=0、speed=300，并非同一五向配方。“杨桃类”名字不保证相同攻击模式，优先核对玩家所指角色的最终发射配置。

证据：本地`.work/attack-starfruit/config-0.tres`、`config-1.tres`、`markers.json`，`runtime/identity.json`和`runtime-markers/identity.json`绑定发行及探针DLL。两次读取标记完成；不是战斗发射/命中验收。网页杨桃样式仅引用五向分布，选择杨桃起点预设才应用五个标记位置，不自动复刻整株行为。


### 追踪弹药屏外回返与接触（0.30发行静态核对）

2026-10-21复核匹配DLL的BulletField：ProcessTrackData目标有效时以GetGlobalPositionForPhysicsFrame为目标，TryGetSegmentCircleEntryPosition(...,30f)进入后调用HitCharacterData(index,target,false)，此分支不检查出界；无有效目标时才在移动后调用IsCollisionRectOutOfBounds/Despawn。主线程追踪分支处理后continue；线程计算分支在trackOpen且target或magneticTarget存在时返回主线程，不预先执行普通出界清理。因此有效目标的这条原生追踪路径允许出界回返，仍受射程、目标有效性、区域效果等约束，不推广到所有弹药/自定义弱转向。来源为同页DLL摘要的IL反编译，证据.work/attack-origin-inspect/BulletField.cs；未新增真实游戏运行验收。网页使用角色实际受击矩形作接触示意，不能将上述追踪专用圆等同角色身体判定。


### 普通僵尸受击矩形（0.30发行运行读取）

2026-10-21通过发行版隔离对局生成ZombieNormal，IsHitBoxEnabled=true、GlobalScale=(1,1)，读取WorldHitRect并减去当帧根位置得到(-18,-37,44,70)。同轮发行场景原型的HitBoxDefinition.TryGetWorldRect(prototype.Transform)结果一致。矩形随影子/物理帧全局变换计算（TowerDefenseCharacter.WorldHitRect），不是Sprite图片包围框；实际游戏还筛选阵营、高度、逻辑行和目标资格。BulletField默认弹药半尺寸(15,15)乘hitBoxScale，SweptCollisionIntersectsRect对目标矩形加弹药半尺寸后作线段裁剪；特殊追踪另有半径30提前命中路径，不能混同。

证据：.work/attack-preview/capture-2d296b0a/runtime/game.log的ATTACK_NATIVE_HITBOX（根860,517，矩形局部-18,-37,44,70），ATTACK_GEOMETRY_target和assessment.json；发行/素材/捕获源码摘要存assets.json与会话provenance。已运行核对读取和几何一致性，未以此声称伤害、穿透或所有弹药真实命中均已验收。换目标或版本需重新捕获匹配定义，不硬套这组数值。
