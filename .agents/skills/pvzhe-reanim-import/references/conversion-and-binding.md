# 转换与行为绑定

## 工具边界

`tools/classic_assets.py` 用确定的长度字段解析常见 PC `reanim.compiled`：zlib 包装、轨道表、44字节变换记录与逐帧 image/font/text 字符串。检查魔数、解压长度、边界与末尾消费；`-10000` 表示继承，零值不应丢失。不要用正则猜最后一条轨道的结束位置。

`tools/reanim_dat.py` 需要 Pillow（本次12.3.0；标准 RGBA/调色板 PNG 均处理），生成内嵌 RGBA 图集的 `animation.dat`、辅助预览 `atlas.png` 和 `conversion.json`。只将 DAT 等实际使用产物纳入自己的 Mod 资源允许名单，原始 PAK、报告与整套缓存不打包。

支持等长轨道、独立图片、无文本、可见 cel 为0的普通骨架变换；原始浮点与图片切换前向继承，矩阵含旋转/斜切、缩放和透明度。导出器v2给无图控制层及 f<0 的隐藏帧分配有效的全透明1×1媒体，保留位姿供宿主采样。不能使用65535空媒体代替：0.30加载时会丢弃对应元素，原DAT有矩阵也不能证明运行时挂点存在。v1产物涉及控制轨时重新转换并重验。图片缺失/歧义、文本/字体、f>0 的图集格和非等长轨道报错，按实际任务补适配。重复层名先报错；调查原始索引和用途后，用 `--layer-map <UTF-8 JSON>` 显式指定索引→唯一名称（如 `{"9":"face_hurt_a","10":"face_hurt_b"}`），不静默合并/丢层；conversion.json记录原名、索引和新名。蒙版/资源别名须在上游补全，不用丢图方式降级。

原始 anim_ 轨道的激活首尾范围导出为 `[start,end)`，不会剪掉整条时间轴末帧或自动去重；有间断的标记也保留原全时间轴。不是所有 anim_ 都是可调用动作。事件表为空，因为动画记录本身不能证明游戏何时发射；应在行为绑定时明确添加或复用实际组件的触发方式。

两引擎连续帧插值可能不同：reanim角度/缩放插值与宿主矩阵插值不能视为逐像素相同。整数帧通过后，还要检查动作中段，避免夸称无损。DAT的宿主读取事实见 [0.30动画导入](../../../../docs/wiki/0.30.0/animation-import.md)。

## 绑定最小清单

| 项目 | 需要确认 |
| --- | --- |
| 身体与头部 | 各自动作范围、时钟、显隐/插层；共用数据不等于共用播放帧 |
| 跟随与原点 | 选哪个真实轨道作为挂点，源参考位姿的逆变换、宿主 offset 与父层如何组合；禁止盲抄另一角色的层编号或偏移 |
| 射击 | 组件需要的 Idle/Fire 名称、出膛点、事件或定时方式、是否分体；从行为事实选方案 |
| 其他动作 | 眨眼/受击/消化等由需要触发的逻辑绑定，未知片段保留 |
| 形态与移动 | 同一形态可能包含多张叠层，按组切换而非每形态只留一层；根运动需验证加载后实际位姿、循环位移与动作切换，见[生产与移动](../../../../docs/wiki/0.30.0/production-and-locomotion.md) |
| 缩放 | 素材尺寸、源矩阵比例与游戏逻辑大小分别处理，不对每张图重复乘固定比例 |
| 注册与入口 | Character、CharacterSprite、Packet和组件的自有键一致；卡片预览与对局分别验 |

例如豌豆类可以复用宿主分体模型，但必须将新动作名和实际层索引重新绑定。不能把身体和头部直接串行播放后声称是原版待机，也不能因同屏叠加一张完整图就认为运动时跟随已完成。

运行时可从发布程序集确认 `AdobeAnimateData.SetAnimeFileForModImport(path)` + `InitForModImport(path)`，然后检查 `HasPackedRuntimeData()`、frameMax、clips、媒体与层数量；赋给已有宿主 `AdobeAnimateSpriteBase` 进行分段播放，不要求F3编辑器或原工程。不要在全Mod生命周期冻结后异步 TrackNode；在展示Hook中先通过 surface.Lifetime 建容器，再由容器持有后续子节点。

最小读取示意（清单中声明自己的 `Assets/animation.dat`，path用当前包根目录组合）：

```csharp
var data = new AdobeAnimateData();
data.SetAnimeFileForModImport(Path.Combine(context.PackageRoot, "Assets", "animation.dat"));
data.InitForModImport();
if (!data.HasPackedRuntimeData()) throw new InvalidDataException("Animation not loaded");
// 数据共享，播放实例分开；别把身体和头的clip混成一条。
body.flashAnimeData = data;
head.flashAnimeData = data;
body.SetAnimation("anim_idle", true, 1);
head.SetAnimation("anim_head_idle", true, 1);
```

这里使用原始片段名。接入复用组件时，可以显式增加宿主需要的片段别名指向对应帧区间；别名不是重新合成的时间轴。示意没有实现跟随、眨眼调度、出膛或角色注册，不直接当完整植物代码。

需要补写动作事件并接入完整植物时，按 [0.30绑定配方](../../../../docs/wiki/0.30.0/plant-recreation.md) 核对事件索引、实际派发与组件消费；行为方案由plant-recreate统筹。转换输出的空事件表是待绑定边界，不是要求用户自行提供完整技术实现。

该播放方式已作局部实验，不替代角色行为验收，也不默认强制开启 forceLocalRender/forceCpuPoseRender。只有默认路径出现可定位故障才针对该实例试对应后端，保留对照证据。

动画帧推进但看不到时，先分开核对图集/矩形/透明度、显示状态与目标区域、实际CanvasLayer/Z和宿主绘制挂载点；不透明预览底板也可能盖住独立提交的精灵，子节点加入顺序不保证跨绘制路径的先后。用当前条件的图像对照判断，再决定局部层级或渲染后端。提高层级只适用于该预览容器，不作为战斗UI越过模态层的通用规则。
