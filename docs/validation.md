# 实测记录（2026-10-13）

验收基线：Windows x64 发布版 0.30.0 C#、Godot 4.7.0、PCK v4，Python 3.12，.NET SDK 9.0.316。未将游戏源码、发布内容或编译引用加入模板。

| 检查 | 结果与范围 |
| --- | --- |
| 发布信息准备 | 索引 27,426 条目；原 PCK 和引用程序集均记录 SHA-256；公共入口/版本由发布 DLL 反射确认 |
| 按需解包 | 从原 PCK 提取 `Asset/Config/Save/ConfigInit.json`，MD5 校验通过 |
| 编译 | net9.0 类库 Release 构建，0 警告、0 错误；入口与发布接口匹配 |
| 产物 | ZIP 内仅 `mod.json`、`Runtime/ModAssembly.dll`，不含宿主 DLL、源码或游戏资源 |
| 安装 | install 将产物复制到测试 Mods 目录；实际测试在独立用户目录自动启用 |
| 真实运行 | 使用发布 EXE/运行时的副本，原 C# 游戏代码不变；宿主 applied，初始化/ready/UI 回调执行，进程正常退出 |
| 二进制对应 | 运行入口记录自己的 DLL SHA-256，与当前 pmod 内 DLL 对应，避免旧日志误验 |
| 界面 | 游戏渲染截图中主菜单左上角出现 `Hello World! · PVZHE Mod`，Label 不拦截鼠标；新测试存档的姓名弹窗未填写 |
| 干净玩家流程 | 将模板源文件复制到空目录，排除 bin/obj/.work/dist，仅提供发布包；prepare → build → extract → install → runtime test 全部通过 |
| 自动测试 | 7 项通过：三种 PCK 格式、提取重复/拒绝覆盖、路径/符号链接越界、损坏/加密/重名拒绝、宿主误打包拒绝、项目配置编码、旧 DLL 日志与运行错误拒绝 |
| Skills | 四个 SKILL.md 通过 skill-creator 的 quick_validate；验证器所需 PyYAML 仅装在本地临时 venv，不是玩家依赖 |

本地结果位于 `dist/hello-world.pmod`、`dist/verification.json`、`dist/hello-world.png`；原始日志位于 `.work/runtime/game.log`，独立存档路径见 `.work/runtime/userdata-path.txt`。这些生成结果不纳入模板源码分发。

## 已观察的限制

- 发布版不允许 `--main-pack`；真实运行测试需同名 EXE/PCK 的本地副本。
- 本机 headless 在宿主初始化中出现原生 `0xc0000005`；图形 OpenGL 启动正常。
- 游戏退出时，宿主冻结的 Mod 扩展点清理报告“需要重启”警告；堆栈经过宿主的 RegistrationRemoved/RemoveOwner。运行期间 applied 的 diagnostics 为 0，退出代码为 0。验证报告保留关闭后的诊断，不将其包装为完全无警告运行。
- 退出时还观察到一条 `ObjectDB instance was leaked` 警告，归因未确认。最小实例显示与运行验证通过；此处未证明宿主或全部 Mod 的退出阶段没有泄漏。
- 未验证其他游戏版本、Android、多人战斗或完整组件库；本模板为这类扩展保留结构，新增功能需补充相应验收。

## 第 1～4 阶段功能增量

同一发布版基线。新增需求引导、UI、HUD、设置、简单战斗规则及关卡制作 Skills；默认 Hello World 与 FeatureLab 独立构建。植物和新角色行为仍暂缓。

| 检查 | 本轮结果与范围 |
| --- | --- |
| 原版组件 | 完整 MainButton 场景、DialogBoxTips 通过真实宿主创建及事件；原版字体、章节/关卡图卡与背景从 res:// 读取，无素材复制 |
| 弹窗 | 原版按钮打开说明；CloseDialog 关闭后暂停状态恢复；保存界面截图 |
| 设置 | showKills 主菜单切换及对局即时显隐；bonusSun 保存75后当前仍50且提示重启；第二个真实进程读取 bool=false、int=75 |
| 简单规则 | Ready 新局余额300→350，宿主 Economy.Credit 命令完成；不订阅 Restored 发放 |
| 关卡 | 独立目录注册；经过目录、可见章节、可见关卡的原版按钮事件进入；身份对应自己的 saveKey；检查预设火炬坚果实际可见且内容对应；真实生成两只普通僵尸并最终胜利 |
| HUD | 初值0；宿主 Combat.Damage 对真实角色造成伤害，death-committed 两次后显示2；800×450 截图检查锚点、描边、边距 |
| 构建/产物 | Release 0警告0错误；FeatureLab ZIP 仅 mod.json、Runtime/ModAssembly.dll、自己的 Assets/level.json |
| 二进制证据 | 本轮包 SHA-256 为 `c44828b3fb1dc90edcf3ad2d70f76b0e105813a24c28bee9fe03ef55a0b21190`；运行 DLL 摘要与包对应，12个场景标记通过；报告 settingsRestartVerified=true |
| 玩家准备 | 复制干净模板文件到空目录，排除 .work/dist/bin/obj，仅提供发布版：prepare→catalog→feature-lab build→check 通过；该干净副本未另跑 GUI 测试 |
| 基础回归 | 默认 Hello World 重新构建、真实 GUI 运行与截图通过 |
| 工具测试 | 10项通过；新增两种构建身份隔离、JSON允许名单及功能日志必须含场景完成证据的检查 |
| Skills | 10份 SKILL.md 通过 quick_validate 的格式检查；8个需求引导案例供行为回归，不将格式检查等同于所有 AI 的引导行为已验证 |

当前结果在 `dist/feature-lab/feature-lab.pmod`、`verification.json`、`ui-dialog.png`、`level-browser.png`、`battle-hud.png`；两轮日志在 `.work/runtime-feature-lab/game.log`、`persistence.log`。

本轮仍保留宿主退出时冻结扩展点清理警告；运行阶段未观察到错误。加载器对自读 JSON 的 applied diagnostics=1，该版本不支持 JSON privateResources，不是关卡自动注册；目录由入口调用宿主 API 注册。不能据此声称完全无诊断加载。

Battle 数据保存/恢复已接入，但完整保存退出后读档、复活/催眠/重复死亡等负例、多分辨率、真实鼠标点击与音效、自然通关和难度平衡、多人同步尚未完成运行验收。确认/输入框仅完成发布资源和接口调查，不能宣称它们已具备与 Tips 相同的验证程度。

## 身份与发布检查增量

命名规则纳入 manifest_policy.py，build/check/install/verify 的包流程执行基础字段检查。`build/check --release` 增加已知示例占位信息拒绝；check --release 核对当前清单与产物一致，--mods-dir 只读检查目录直接包含的 pmod ID，--allow-update 仅允许显式确认的同 ID、同文件名升级。

- 16项工具测试通过：新增字段长度/字符集、严格 SemVer、示例与发布模式区分、自定义 ID 产物命名、重复 ID/升级和过期清单拒绝。
- 在独立模板副本中实际完成默认 build/check，确认默认示例的 release 检查失败；将清单换成虚构测试身份后完成 build --release 与空 Mods 目录的 check --release，产物文件名对应 ID。测试署名仅用于本地测试，不修改默认模板，也不上传。
- 原 Hello World 与 FeatureLab 包通过新版基础检查；11份 Skills 格式及文档链接检查通过。

本轮不改运行入口/游戏行为，没有重新进行 GUI 验收；发布字段通过也不代替功能验收。32字符与 SemVer 为模板规范，不声称所有宿主版本有相同约束；作者采用保守 UTF-16 长度口径。占位检测无法证明真实署名或用户确认，本地 ID 扫描也无法证明全球唯一。

## 版本化 Wiki 整理（2026-10-13）

新增 docs/wiki 的 0.30.0 基线与八个主题页，将复用组件、旧配方和首次启动正文集中到 Wiki；旧文件保留导航。AGENTS、README 和功能 Skills 按需路由，模板升级流程要求同步 Wiki 及重新标记验证状态。

- 从本地已准备的 0.30.0 发行 PCK 按需提取角色、地图、关卡及卡池四份注册表，MD5 校验通过；查询 ZombieNormal 的七种卡牌和 FrontlawnEmpty 注册 UID 成功。
- UI 局部坐标到 Viewport 的示例，用该发行版 GodotSharp.dll 与 net9.0 编译通过，0警告0错误；这只验证签名，不证明真实鼠标命中。
- 本轮仅修改文档与 Skills，不改入口或工具；既有 GUI 结果保留原验收范围，没有重新进行 GUI 验收。原版完整冒险选关、建档自动化、完整 Battle 保存恢复等仍标为待验证。

## 场景合理性与验收指导补强（2026-10-13）

依据后续自定义 Mod 开发记录的反馈，补充需求默认约束、命名范围、UI阶段/避让/模态、自定义功能正负向验收、普通启动与测试夹具隔离、Wiki因果证据规则。主 Skills 通过按需参考文件接入，不新增清屏专用 Skill，也不改 Hello World、FeatureLab 或引用 Mod 的实现。

本轮为文档与 Skills 更新，未新增 GUI 运行证据。通用战斗按钮的完整阶段验收仍待实现验证；没有将引用 Mod 的高层/光标个案结论提升为模板通用规则。需求案例用于人工审阅行为预期，不宣称所有 AI 已通过执行回归。

检查结果：11份 Skills 通过 quick_validate；42份文档的129个本地链接目标全部存在；git diff --check 通过。未修改工具/入口，因此本轮未重新构建或运行 GUI。

## UI 结构与阶段证据补强（2026-10-13）

明确场景/实例/动态创建与行为分析在先、运行截图与交互验证在后的证据流程；同步 UI/PCK/验证 Skills、Wiki 维护规则、升级 Skill 与兼容报告。发行 0.30.0 PCK 中提取 TowerDefenseControlNew.tscn 的 MD5 校验通过，确认 GUITop/OptionButton、实例来源、左下布局、layer=3、默认隐藏和 autoSize。这些为静态结构证据，未新增 GUI 或完整阶段行为验收，最终尺寸及条件仍待核验。未修改引用 Mod 或工具/入口。

## 动态金币占位与卡槽布局资料（2026-10-13）

新增 battle-layout Wiki，UI/验证指导及模板升级资料同步布局模式、槽数、动态触发与窗口尺寸的独立覆盖要求。仅分析匹配发行资料，未修改入口/工具或引用 Mod。

发行 PCK 提取 CoinBank、TowerDefenseManager、SeedBank 场景，MD5 校验通过；发布 DLL 方法体静态确认 CoinBank 初始透明，Collection 调用 ShowCoinBank，默认位置86/557、alpha=1、非still停留5秒后淡出；显示框基础尺寸167×40，宿主父层100。SeedBank.SetMobileMode/ApplyMode 静态确认卡牌容器迁移、模式显示切换及 MobilePreset 保存。自己的分析程序和原始证据仅留在 .work，未分发游戏代码。

未新增 GUI 验收；实际金币拾取与布局切换的完整显示/命中矩形仍待运行核验，不将静态范围当成所有窗口/模式的最终坐标，也不保证任一候选按钮位置已安全。

## 可视化位置输入工具（2026-10-13）

新增 placement_editor.py、独立会话模型及 pvzhe-placement-preview，沿用简洁GUI并保留 placement_demo.py入口。输入支持多个布局/组件、本地背景与组件图片、可关闭占位提示；返回绝对逻辑矩形，取消/超时不应用，恢复需相同配置并重新确认。用户绝对位置优先规则接入AGENTS与制作/验收指导。

24项工具测试通过；隐藏Tk拖动/尺寸自检通过；本地生成的模拟PNG背景与按钮图在1080×600缩小预览下测试坐标映射、两个布局切换、确认/取消及1秒实际计时超时关闭通过。GUI用的是模拟资料，没有游戏截图/素材或运行业务，不能据此声称游戏位置适配通过。

12份Skills格式、45份文档的151个本地链接及git diff --check通过。计划完成后已删除临时plan.md；长期输入协议与使用步骤归入docs/placement-preview.md。

## 玩家自选位置的交互验证（2026-10-13）

隔离测试 Mod 的真实主菜单背景和按钮预览用于位置输入，玩家确认后将对应绝对矩形换算回游戏逻辑坐标；更新后的 Viewport 纹理坐标与确认矩形差异小于0.05像素，合成鼠标打开、Hello World内容、宿主关闭恢复和再次打开通过。模板入口/清单未改，游戏图片、测试代码与产物仅留在.work。引导Skill新增玩家位置不满意时主动用“在画面里直接拖动按钮，自己选位置”的措辞询问；已有同意直接执行。坐标说明补充窗口黑边与Viewport纹理原点的区别。

## 发布资源缓存与透明预览（2026-10-13）

prepare 初始化按 PCK/发布 DLL/引擎/提取器摘要隔离的本地缓存，extract 默认增量提取并校验复用；背景捕获和透明组件渲染作为显式测试辅助代码提供，不接入默认入口。制作、解包、预览、版本升级 Skills 与 Wiki 同步指向资源缓存及捕获协议。

- 30项工具测试通过，包括依赖闭包、重复复用、缓存篡改拒绝、发行变化隔离及 Mod DLL 变化导致旧预览拒绝。12份 Skills 格式、46份文档的165个本地链接和 git diff --check 通过。
- 对本地0.30.0发行版重新 prepare/build/check 通过；MainButton依赖首次提取6个文件，重复请求 extracted=0/reused=6。默认入口、项目文件及清单摘要与前轮一致，pmod仍仅包含 mod.json 与 Runtime/ModAssembly.dll。
- 独立测试 Mod 在真实宿主中先隐藏目标按钮捕获背景，再在独立透明 SubViewport 渲染完整 MainButton 场景，最后验证鼠标点击、Hello World、关闭及再次打开通过。输出PNG为207×62，alpha范围0至255；捕获后恢复按钮显隐。代码签名编译0警告0错误，绑定新捕获及当前DLL后的隐藏Tk拖动/尺寸自检通过。

本轮Tk自检结果由测试产生，未作为玩家确认应用。当前透明渲染运行证据仅覆盖MainButton常态，不证明弹窗、复杂业务组件或所有状态均可直接离屏实例化。缓存依赖扫描不保证发现UID-only及运行时动态依赖；摘要绑定不能替代本次捕获日志。游戏素材、图片、测试实现与产物均保留在忽略目录，未进入模板分发。
