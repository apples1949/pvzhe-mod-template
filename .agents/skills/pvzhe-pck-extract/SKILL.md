---
name: pvzhe-pck-extract
description: 对 PVZHE 发布 PCK 建立资源索引并按需提取配置、资源及依赖信息；用于资源分析，不将解包误当成源码还原。
---

# PCK 按需提取

先按 [Wiki 索引](../../../docs/wiki/README.md) 核对发行版本与摘要，再按需读取 [content-index](../../../docs/wiki/0.30.0/content-index.md)。匹配基线时沿用已确认的操作路径；仅对缺项、差异或失败点补充分析，不从零遍历游戏。静态确认和待验证内容不能冒充运行验收。

输入：目标发布 PCK、提取目标与本地输出目录。输出：保留相对路径且通过 MD5 校验的文件、依赖路径与注册键的分析结果。

1. 先读 README 的 PCK 说明。使用 release-analyze 准备出的 `.work/pck-index.json` 搜索准确路径；不得凭素材名称猜路径。
2. 执行 `python tools/mod.py extract --pck '<包>' --path '<相对路径>' --output '.work/extracted'`。目录批量提取使用 `--prefix '<准确目录/>'`。最小 Hello World 无需提取额外素材。
3. 从文本配置确认资源键、`res://` 路径、UID 和 `.remap` 映射，再提取必要依赖。输出只是 PCK 原始文件；导入纹理、二进制资源、编译脚本可能仍无法直接在编辑器打开。需要转换时先确认匹配版本的工具是否支持，不承诺完整源码还原。
4. 分析 UI 时按 [场景适配的证据顺序](../pvzhe-ui-create/references/scene-fit.md) 跟踪实例依赖、布局、动画及动态显隐；PCK/反射未提供的行为不能从截图猜测。记录所用路径、宿主接口与发布摘要；自己的资源放到 `mod/Assets/`，只把确实属于 Mod 的文件加入 `resources`。宿主资源优先在运行时引用，不能整份复制解包目录到 Mod。

验证：提取退出码 0，每个文件摘要通过；不存在越界路径/重名覆盖。工具允许重复提取相同内容，不同内容拒绝覆盖；游戏升级时使用新的工作输出目录。再次运行 build/check，确认游戏文件没有进入 ZIP。

适用范围：独立、未加密的 Godot PCK v2/v3/v4。遇到不支持格式或校验失败，保留原包并报告，不跳过校验继续开发。
