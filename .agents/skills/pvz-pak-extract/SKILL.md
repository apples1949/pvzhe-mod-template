---
name: pvz-pak-extract
description: 索引与按需解包用户提供的经典版或改版 PopCap PAK，记录来源摘要并提取 reanim 的图片依赖；不处理 PVZHE 的 Godot PCK。
---

# 经典 PAK 提取

输入：用户提供的 PAK；输出：本地索引、按需原文件与摘要清单。仅在导入经典/改版素材时使用；当前游戏发行 PCK 仍走 pck-extract，不要求每个 Mod 都有 PAK。

1. 使用 `python tools/classic_assets.py --pak '<用户路径>' index --out '.work/classic-cache/index.json'`。工具支持版本0、普通条目、可选整包 XOR F7；其他变种报错后识别格式，不去掉检查强行解包。
2. 以索引中的 `pakSha256` 建立 `.work/classic-cache/<摘要>/`，后续共用该目录；原包变更切换身份，不以文件夹时间判版本。需要中文名定位时组合 [source-identify](../pvz-source-identify/SKILL.md)。
3. 按索引原路径提取：`… extract --path 'properties/NewPlantStrings.txt' 'properties/resources.xml' --out '<缓存>/files'`。文件名来自索引，不假设所有改版都采用这些名称。原始字节保留，中文解码由资料定位负责。
4. 动画确认后：`… bundle --animation '<索引内 compiled/...reanim.compiled>' --out '<缓存>/角色'`。输出 `bundle.json`、`raw-reanim.json` 和 `files/`；按真实 IMAGE 引用收集共享图片，不能只提取与角色同名的图片。
5. 检查未解析图片与摘要。内置 IMAGE_REANIM 路径规则仅覆盖常见独立图片；缺失/歧义时查资源清单中的别名、目录、透明蒙版及图集声明，补全明确映射后再转换，不能静默跳过依赖。

验收：索引完整消费包数据；抽取文件与摘要一致；所需图片无缺项。资源只留忽略提交的缓存/实验工程，模板不附带经典素材。提取成功不代表动画转换或角色行为已成功。后续使用 [reanim-import](../pvzhe-reanim-import/SKILL.md)。
