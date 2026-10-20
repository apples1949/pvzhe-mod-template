---
name: pvzhe-reanim-import
description: 将已识别的经典 reanim.compiled 与依赖图片转换成 PVZHE 动画数据，并指导原始分段、独立部件及行为绑定；不把网站预览合成动画当成游戏契约。
---

# 导入经典动画

输入：pak-extract 的 bundle 或同等可追溯素材、匹配的 PVZHE 发行版、角色行为目标。输出：转换数据、显式绑定方案与分项验证。结构转换不等于角色已完成。

1. 检查 `bundle.json` 的来源摘要、图片依赖与原始轨道，保留 `raw-reanim.json`。不使用网站生成的 custom_idle/custom_shoot 替代原始帧，也不把网站用来防散架的合成当作游戏机制。
2. 对 0.30 已核对的 DAT 路线，安装可选 Pillow 后执行 `python tools/reanim_dat.py --bundle '<角色缓存>' --out '<本地生成目录>'`。工具保留全时间轴、控制层、透明度、原始图片切换及 anim_ 标记范围；具体能力/限制见 [转换与绑定](references/conversion-and-binding.md)。其他格式不改后缀冒充支持。
3. 先检查转换报告，区分动作标记与真正的行为动作；`anim_face` 等有图片的轨道也会以 anim_ 开头。不要把全部候选片段都变成玩家可用动作。身体/头部独立播放、插层与跟随由场景/控制逻辑接入，不自动拼成一条新长动画。
4. 按 [character-skin](../pvzhe-character-skin/SKILL.md) 匹配发行版的宿主精灵与组件。按[版本绑定配方](../../../docs/wiki/0.30.0/animation-import.md#分体动画跟随坐标与动作播放)明确原始片段→宿主动作、部件/跟随点及参考逆变换、发射时序/事件、原点与缩放；未知额外片段保留未绑定状态，不猜造技能。
5. 先用隔离 Mod 在发行游戏中加载生成 DAT、采样动画推进与可见表现，再接入完整角色与正常入口；按 plant-create / zombie-create 负责注册，character-fire 负责发射。模板 Hello World 不添加实验功能，原素材与实验包不进入版本控制。

验收分开记录：解码与依赖、DAT加载、静态图层/透明度、连续帧与部件跟随、动作切换/事件、角色业务、卡片/图鉴等实际入口。未测部分明确写出，单帧或帧号推进不证明整个角色还原成功。当前例证见 [导入实验](../../../docs/classic-import-experiment.md)。
