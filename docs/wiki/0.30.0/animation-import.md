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

## 分体动画：跟随、坐标与动作播放

发行场景实例及DLL核对：豌豆射手/单发豌豆的Head跟随并插入身体`anim_stem`层（本版索引8）；豌豆向日葵使用同名层但索引5。`parentSprite`、`followParentSpriteLayerId`、`insertLayerId`及`usePos`共同参与父精灵对子精灵的位姿更新。层号属于具体动画数据，不是豌豆类通用常量；换DAT后按名称及原始轨道语义重新解析。

宿主`AdobeAnimateSprite.UpdateChild`读取当前挂点位姿，再叠加父精灵offset来定位子精灵；子精灵自身offset继续作用于其图片。头部独立播放不等于脱离身体：攻击时头部切换动作，仍需随身体的挂点移动。把parent清空、跟随设为-1再用固定Position拼齐，只能证明参考帧对位。

接入前记录一张绑定表：部件→原始动作范围→父精灵/真实挂点→参考位姿→局部offset/插层→由谁控制速度及切换。优先复用宿主挂接，缺能力才写局部适配。原始头部坐标已经包含参考挂点时，必须消除这份重复位移；不能直接同时加“完整原始坐标”和“完整当前挂点”。例如超级机枪的挂点是`anim_idle`控制轨，参考位移(37.6,48.7)，其旋转/缩放为单位；案例让宿主提供当前挂点，再用头部offset减掉参考位移。一般旋转/缩放挂点需要求完整参考逆变换，不能推广本例的只减位置。

两个播放契约已沿发行实现确认：

- `clips`和`clipRange`采用`[start,end)`；非循环动作需要包含原始最后一帧，循环末端重复帧由宿主按条件处理。不得未经核对主动减1。超级机枪大招正确范围为[75,87)，此前误填[75,86)导致末帧丢失。
- `SetAnimation(string clipName, bool loop=true, double blendTime=0)`第三参是混合时间，速度另设`timeScale`。从攻击切到其他动作时检查残留速度；同一精灵被原版组件和自有逻辑共同控制时，明确切换顺序、完成事件和返回动作，避免相互抢写。超级机枪案例在大招期间临时暂停自身FireComponent的自动发射，复用其发射点和投射物创建服务，在动作完成后恢复；这是该例的所有权方案，不是所有角色必须修改alive的通用规定。

动画验收先覆盖一个完整待机周期，记录身体挂点变化及头部实际运动，再覆盖完整攻击、特殊动作及返回待机。连续截图/可见播放与位姿、首末帧、速度/完成事件分别取证；帧号推进、伤害通过或单帧拼齐均不能替代。GPU挂接可能不更新普通Node位置时，应核对实际渲染位姿/画面，不强制套用CPU断言。当前案例的修复与验收范围见[超级机枪报告](../../super-gatling-example.md)，旧0.1.0业务验收不证明分体动画正确。

### 场景打包与真实渲染的边界

本版`forceLocalRender`/`forceCpuPoseRender`不是PackedScene的Storage属性；在配置样板上设值再Pack，不能认为后续实例保留。采用这些运行时开关时，检查实际实例及生效时机。超级机枪0.1.2采用持久化的自有metadata识别，在自有角色/预览实例Ready后应用局部绘制；不是要求所有导入角色强制切后端。

节点位置变化与可见部件变化是两类证据。运动验收另取画面中目标本身的位移/关系，绑定本轮包及实际画布；固定夹具可使用经过正反例校准的局部图像探针，不能将场景噪声或内部形变当成整体挂接位移。超级机枪案例在实例Ready应用局部绘制后已通过画面位移及断开挂接对照；默认组合路径内部的唯一原因、CPU位姿是否足够仍未确定。边界和被拒绝的旧画面见[案例记录](../../super-gatling-example.md#011画面结论撤回节点运动不等于渲染运动)。
