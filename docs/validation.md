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
