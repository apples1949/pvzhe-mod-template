# 外部动画导入

基线：[0.30.0发行摘要](overview.md)。流程入口：[资料定位](../../../.agents/skills/pvz-source-identify/SKILL.md)、[PAK提取](../../../.agents/skills/pvz-pak-extract/SKILL.md)、[reanim导入](../../../.agents/skills/pvzhe-reanim-import/SKILL.md)。本页记录结构契约与局部实验，不代表通用角色转换SDK。原始游戏素材不附带于模板。

## 两种资源包不能混用

PVZHE发行资源是 Godot PCK，由 mod.py prepare/extract 和 game-cache 管理。经典版/其他改版的 PopCap PAK 是额外的用户输入，由 classic_assets.py 处理；它的哈希与 PVZHE PCK/DLL 身份分别记录。外部 properties 也绑定文件字节摘要和编码，同名目录不代表同版本。

GBK 汉化块可以建立“中文名称→字符串键→英文动画候选”的关系。只有完整名称值命中才认为是命名条目；正文提及、僵尸变体和同名重复须区分。不同改版的键与文件名不保证相同，必要时沿 resources.xml 的路径/别名继续查。图鉴声明是玩法线索，不能替代程序时序依据。

## 当前 DAT 契约

已核对发布程序集的 `AdobeAnimateData`、`AdobeAnimateSpriteBase` 及加载接口。内部结构研究用于维护工具，玩家侧工具不读取源码，也不依赖F3编辑器。

| 段 | 0.30读取形式 |
| --- | --- |
| 基本信息 | little-endian float32帧率、uint16帧数 |
| 内嵌图集 | uint16宽/高、uint64字节数、宽×高×4原始RGBA字节 |
| 媒体 | uint16数量；UTF-8 Pascal字符串（uint32字节长度）与4个float32矩形值 |
| 层/帧 | uint16层数；每层名称、逐帧uint16元素数；每元素uint16媒体ID、6个float32矩阵分量、uint32颜色RGBA |
| 片段 | uint16数量；名称与uint16起止帧，工具明确使用半开区间 |
| 事件 | uint16事件帧数量；帧位置、事件数量、Command/Argument字符串 |

**控制轨修正**：宿主打包运行数据时跳过媒体ID65535的空元素，导致原始矩阵仍在、可采样位姿却丢失。导出器v2改用有效全透明1×1媒体保留控制轨；虫子根运动已有发行版对照证据，见[生产与移动](production-and-locomotion.md)。旧v1产物不能因帧数/层名正确就认定挂点可用，应重新转换、验证实际采样。宿主独立部件、挂点、渲染路径仍须核对。转换工具生成原始时间轴和原始 anim_ 候选，不创建网站 custom_idle/custom_shoot，也不凭空生成 fire 事件。

## 发行版加载与验收边界

`SetAnimeFileForModImport(path)` 设置来源，`InitForModImport(path)` 读取资源。检查 `HasPackedRuntimeData()`、frameMax、clips、layerDictionary、mediaDictionary；`TryReadEmbeddedAtlasImage` 可核验图集可读。生成数据可以赋给宿主精灵类；仅调用这些接口成功仍不证明可见绘制。

狂野机枪射手的提取、转换、运行结果和未覆盖内容见 [实验记录](../../classic-import-experiment.md)。渲染、跟随和业务结论按该记录的实际范围使用；不要拿仅复用原版外观的旧结果证明外部动画已完成。新增来源或引擎版本变化时补做对应结构、可见帧、动作切换和组件事件验证。

重复原始层名用 `--layer-map` 按索引明确重命名，转换报告保留来源关系；不自动去重。受伤向日葵的两组脸部各有两层，切形态必须按组处理，完整案例见[双例迁移实验](../../migration-pair-experiment.md)。
