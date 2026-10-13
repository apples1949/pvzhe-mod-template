# 对局布局模式与动态占位

基线：[0.30.0](overview.md)。状态：PCK 场景与对应发行 DLL 的方法体静态核对（2026-10-13）；未新增金币拾取/模式切换的 GUI 验收。以下为布局分析输入，不是已验收的通用按钮摆放方案。玩家只需发行版。

## 左下区域不是持续空位

| 宿主内容 | 来源与条件 | 对布局的影响 |
| --- | --- | --- |
| 原版选项 | GUITop/OptionButton；具体结构见 [UI 页](ui.md) | 保留按钮显示与点击区域，不能被新增控件覆盖 |
| 金币显示 CoinBank | Core/TowerDefenseManager/TowerDefenseManager.tscn 的 GUILayer/CoinBank；GUILayer layer=100；实例 Prefab/GUI/CoinBank/CoinBank.tscn | 是独立宿主层，不是 Mod HUD 的普通子节点；加高层不能解决空间冲突 |
| CoinBank 外观 | CoinBankTexture 的基础尺寸167×40；内部有 CoinNumLabel | 查询实际可见子节点及文字范围；根 Control 尺寸不足以代表整体占位 |
| CoinBank 出现 | 发布 DLL CoinBank._Ready 设置 alpha=0；TowerDefenseCoinBase.Collection 调用 ShowCoinBank | 没有拾取时看不到，但不是可永久占用的空位；只判断 Visible 会漏掉透明状态 |
| CoinBank 默认位置 | ShowCoinBank 默认位置(86,557)，alpha=1；非 still 时 timer=5，然后物理处理淡出 | 基础显示范围约x86～253、y557～597（宿主逻辑坐标），紧邻设置右侧；最终屏幕矩形需结合父层/缩放核验 |
| 其他金币显示状态 | ShowCoinBank 可接受其他位置及 still；still 分支停留且关闭自动淡出处理 | 上述矩形不是所有模式的恒定范围，特殊模式/调用点需按支持范围另查 |

普通拾取路径已由发行 DLL 的 Collection→ShowCoinBank 调用及默认参数静态确认。未直接运行拾取流程，不能声称所有金币类型、特殊模式和最终显示范围均已实测。默认保留金币信息区，不因它暂时透明而放入常驻按钮；必要时验证金币出现、连续拾取、淡出及数字变化。

## 卡槽布局模式与窗口尺寸是两个维度

资源：Registry/Battle/Feature/SeedBank/Control/TowerDefenseInGameSeedBank.tscn。包含 PCControl/MobileControl 的布局分支（准确节点名以提取场景为准）；移动卡牌和槽位使用 VFlowContainer。发布 DLL 的 TowerDefenseInGameSeedBank.SetMobileMode 会转移卡牌容器、调用 ApplyMode 并保存 MobilePreset；ApplyMode 切换显示分支，SyncPacketSlots 按槽数更新，后续帧再刷新布局尺寸。

因此，顶部横排与左侧竖排可能在同一窗口尺寸下切换，不是只改分辨率就能覆盖的响应式变化。可见卡牌少不等于占位少；空槽仍属游戏操作空间。卡槽数量、布局重排以及当前关卡配置会改变占位，不能只检查已有卡牌的矩形。

实际开发核对完整容器/槽位、阳光区、铲子、选项、金币、关卡信息/进度及模态覆盖层在目标模式下的范围。支持范围之外的特殊关卡列为未验证，不承诺所有模式。

## 选择位置的顺序

先按 [场景适配](../../../.agents/skills/pvzhe-ui-create/references/scene-fit.md) 建立模式×阶段×动态触发的占位清单，再比较候选位置：

1. 优先沿用宿主操作区的对齐、排列方向和间距；左右并排是候选，上下堆叠也可以，但应形成清楚的组并保留战场空间。
2. 设置右侧须避开金币显示；设置上方须避开竖排卡槽；其他位置须继续核对宿主控件与战场，不把任何一个方向规定为绝对安全。
3. 常驻按钮优先放在各受支持状态均可用的区域，留出完整动态信息区和合理间距。没有共用区域时可按模式选择预先验证的位置，或采用更紧凑的入口；必要时再与用户沟通超出原区域的方案。
4. 避免随金币出现/淡出突然移动正在点击的按钮。使用固定预留优先；确需动态调整时选择稳定切换时机，确保命中与提示一致。默认不改宿主金币位置、卡槽或原按钮来给 Mod 腾地方。

接到布局事件只是重新测量的起点，布局位置需真正更新；只调用显隐 Refresh 不等于重新布局。也不能假设 LayoutChanged 覆盖卡槽模式/槽数变化：核对事件来源与范围，必要时监听对应状态变化或做有限检测，在宿主容器重排完成后重新测量，不每帧扫描整棵树。

验收按 [功能验收](../../../.agents/skills/pvzhe-mod-verify/references/feature-acceptance.md) 覆盖两种布局、目标槽数及金币出现状态，记录具体对象和支持范围；截图作为对应条件的结果证据，不代替结构/行为分析。
