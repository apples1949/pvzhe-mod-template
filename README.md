# PVZHE 最小 Mod 模板

面向玩家与 AI 的 Hello World 项目。以**已发布的 Windows C# 游戏 0.30.0**为基线，编译自己的 C# DLL，并打包为游戏原生 `.pmod`。无需游戏源码，也不分发游戏程序集、贴图或解包内容。

示例启用后，在主菜单左上角显示 `Hello World! · PVZHE Mod`，同时记录初始化、全部 Mod 加载完成与 UI 挂载日志。详细兼容依据与实测记录见 [兼容说明](docs/compatibility.md)。

## 开发环境

- Windows x64；拥有完整的 0.30.0 C# 发布目录（EXE、PCK、`data_PlantsVsZombies_windows_x86_64/`）。其他版本先执行发布版分析，不能默认兼容。
- .NET **9.0 SDK**，最低 9.0.100；`global.json` 允许同一主版本内的最新 feature band。实测 SDK 9.0.316，目标框架 `net9.0`。只装游戏自带运行时不足以编译。
- Python **3.11+**，实测 3.12；核心构建/解包仅使用标准库。可选攻击编辑器及旧版图片位置预览需要 Pillow；游戏内拖拽组件不依赖Python GUI。
- PowerShell；以下命令在模板根目录执行。若系统使用 `py -3`，将 `python` 替换为 `py -3`。

最小示例不需要安装 Godot 编辑器、导出模板或解包完整游戏工程。发布包携带 `GodotSharp.dll` 与 `PlantsVsZombies.dll`，工具直接使用这两个文件作为编译引用。需要编辑场景时，再安装与发布引擎匹配的 Godot .NET 版本；本次发布 PCK 标记为 **4.7.0**。

想将经典版或其他改版角色做成 Mod 时，可用新增的资料定位、PAK提取与reanim导入 Skills；它们按需使用用户自己的素材，不是 Hello World 的依赖。转换图片需要可选 Pillow，命令与实测边界见 [经典素材导入实验](docs/classic-import-experiment.md)。

用户说“复刻某植物”时，AI通过 [植物复刻指导](.agents/skills/pvzhe-plant-recreate/SKILL.md) 统筹属性、外观、行为和可玩验收，先自主调查、补全合理细节，核心分歧才询问。经典PvZ素材工具采用`pvz-*`命名，接入本游戏的制作流程采用`pvzhe-*`；实际近似与验收边界见 [复刻实验](docs/plant-recreation-experiment.md)。非射击植物及外部僵尸的生产、恢复、移动与攻击验证见 [双例迁移实验](docs/migration-pair-experiment.md)，僵尸由 zombie-create 统筹；默认模板不增加这些功能。

常见跨功能制作还做了[社区方向实验](docs/community-mod-experiments.md)：拾取/快捷键、主菜单音乐与自有地图。音频请求由[audio-edit](.agents/skills/pvzhe-audio-edit/SKILL.md)处理，验证范围与局限分别记录，实验不进入默认包。

新增模式入口和独立导航页面由 [mode-create](.agents/skills/pvzhe-mode-create/SKILL.md) 指导；章节/关卡继续由level-create负责。可选 [模式导航配方](examples/ModeNavigation/README.md) 展示章节选关和直接开局两种路线，不加入默认Hello World；边界和运行证据见 [导航实验](docs/mode-navigation-experiment.md)。

[超级机枪射手](examples/SuperGatling/README.md) 是可构建的外部植物案例，包含用户PAK素材准备、独立植物/动画/攻击、原版金色卡池及分离的验收脚本。运行`build --example super-gatling`，来源素材由玩家自行生成且不随仓库分发；默认Hello World无需这些素材。通用发现见[原版卡池与种植](docs/wiki/0.30.0/card-pools.md)。

玩家明确想自己设计弹道/攻击方式时，可用[攻击方案编辑器](docs/attack-preview.md)：草坪与透明角色、单颗弹药/射线、组与可拖时间轴、相对网格偏移、地图触发区域、直线追踪强度及函数预设。方案保存在design/attacks，可继续编辑和恢复草稿，持续等待确认或取消。普通开发不自动打开；预览不代替游戏内命中验收，不影响默认模板。

## 初始化、构建

```powershell
dotnet --list-sdks
python --version
$game = 'E:\Daily\Desktop\植物大战僵尸杂交重制版'
python tools/mod.py prepare --game-dir $game
python tools/mod.py build
python tools/mod.py check
```

将 `$game` 换为自己的发布目录。目录内多个 PCK 时，显式添加 `--pck '完整路径.pck'`。准备步骤读取 PCK 目录及 `project.binary`，记录引擎、格式、资源索引与 SHA-256，并通过发布程序集反射提取 Mod 接口信息，全部保存在忽略提交的 `.work/`。它不会读取任何游戏源码路径。prepare还初始化忽略提交的统一版本资源缓存；新增UI资源按需提取并复用，避免每次问答临时解包。见 [资源缓存与预览捕获](docs/resource-cache-and-capture.md)。

构建会核验本地引用摘要、编译入口、验证其实现发布版接口，再按允许名单创建产物：

```text
dist/hello-world.pmod       # ZIP；仅 mod.json、Runtime/ModAssembly.dll
dist/build-info.json        # 本地构建证据；含发布包路径与摘要
```

`.pmod` 是最终分发文件；不是 Godot PCK，也不需要 `--export-pack`。不要把 `dist/build-info.json`、`.work/`、整个发布目录或自己的 `bin/` 当成 Mod 分发。更新游戏后重新运行 `prepare` 与 `build`。

## 创建自己的 Mod 与发布

AI 在新项目主题明确后会拟定稳定的小写 ID，名称依据实际功能建议，例如单个清屏按钮叫“僵尸清屏按钮”，不会默认扩称“工具箱”；作者由你指定。已有 Mod 增加功能不会自动改 ID。模板和 FeatureLab 的默认身份仅用于示例；准备分享时确认 `mod/mod.json` 中的名称、作者和版本，并替换示例 ID。作者最多32个 UTF-16 单元，ID 为1～32个小写字母/数字/`_-.`，版本最多32字符且符合 SemVer（默认 `0.1.0`）。姓名可用中文；Mod 显示名称没有另设32字符上限。

```powershell
python tools/mod.py build --release
python tools/mod.py check --release --mods-dir '<实际目标 Mods 目录>'
```

普通 build/check 校验字段格式但允许示例身份；`--release` 拒绝已知模板身份和占位信息，check 还核对包内清单与当前清单一致。自定义 ID 的输出是 `dist/<id>.pmod`，原示例文件名不变。先完成实际加载和功能验收，再分发该文件。

`--mods-dir` 只读检查目录直接包含的 .pmod 是否有重复 ID，不提供目录时会告知未检查本地冲突；不保证全网唯一。确认同 ID、同文件名的旧包确属当前 Mod 后，可加 `--allow-update` 做升级检查；不同文件名的重复 ID 仍拒绝。具体命名、稳定身份与发布步骤见 [身份与发布规范](.agents/skills/pvzhe-mod-develop/references/identity-and-release.md)。发布检查不代表自动上传。

## 安装与运行

1. 退出游戏。在游戏 Mod 管理界面确认 Mod 目录；默认 Windows 路径为 `%APPDATA%\Godot\app_userdata\植物大战僵尸杂交版\Mods`，不是游戏 EXE 所在目录。
2. 将产物复制进去，或执行：

```powershell
$mods = Join-Path $env:APPDATA 'Godot\app_userdata\植物大战僵尸杂交版\Mods'
python tools/mod.py install --mods-dir $mods
```

3. 正常启动发布版，在 Mod 管理中启用“Hello World 模板”，按界面提示重启。复制文件本身不会启用 Mod；不要手工覆盖现有 `enabled_mods.json`。
4. 进入主菜单，确认左上角文字。查看本次启动的 `logs/godot.log`，应包含：

```text
[Mod:local.hello-world] HELLO_INIT: Hello World!
[Mod:local.hello-world] HELLO_BINARY: <当前 DLL 的 SHA-256>
[ModLoader] package applied: local.hello-world; ...
[Mod:local.hello-world] HELLO_READY: all mods loaded
[Mod:local.hello-world] HELLO_UI: banner mounted
```

5. 将当前日志交给验证命令：

```powershell
$log = Join-Path $env:APPDATA 'Godot\app_userdata\植物大战僵尸杂交版\logs\godot.log'
python tools/mod.py verify --log $log
```

验证成功生成 `dist/verification.json`，记录包与日志摘要，并核对最后一次初始化的 DLL 摘要是否与当前产物一致。该命令检查运行日志，不代替肉眼检查文字位置。关闭或卸载请通过 Mod 管理禁用并重启，之后可删除对应 `.pmod`。

## 自动运行验证（独立存档）

```powershell
python tools/runtime_test.py
```

该脚本复制发布 EXE、运行时目录及 PCK 到 `.work/runtime/`，在 PCK 副本内修改应用名和用户目录开关，并加入测试专用 GDScript 驱动。驱动等加载页原有 `StartButton` 可见且可用后触发其按钮信号，进入主菜单，等待过渡完成并截图。测试不修改宿主 C# 代码或 Mod 产物。

每次测试在 `%APPDATA%\Godot\app_userdata\PVZHE Mod Template Test <随机标识>` 创建独立数据，路径记录在 `.work/runtime/userdata-path.txt`；不使用原游戏存档。测试会打开一个 OpenGL 游戏窗口，成功截图后自动退出（通常约 20 秒；90 秒为帧数退出上限，120 秒为进程超时）。游戏必须能在此电脑上运行，并且 EXE 与 PCK 同名。预留约 1 GB 磁盘空间。不要同时运行多份测试。

测试仅启用示例，结束时恢复测试目录原有启用状态；日志在 `.work/runtime/game.log`，截图在 `dist/hello-world.png`。新存档会显示用户名弹窗，不影响左上角文字验收，测试不会填写用户资料。此脚本当前只支持 Windows、未加密独立 PCK v4。发布版禁止 `--main-pack` 路径覆盖，故必须复制为同名 EXE/PCK。此版本在本机 `--headless` 会发生原生崩溃，自动测试使用真实图形窗口。测试目录保留供排查，需要时仅删除上述记录指向的测试目录。

用户名提示是独立新存档的预期行为；关闭提示不等于已经建档。涉及交互或保存的验证，按 [首次启动处理](.agents/skills/pvzhe-mod-verify/references/first-run.md) 满足对应前提。内置脚本只验证两个固定示例，自定义 Mod 应按玩家需求补充测试场景。

## 从 PCK 获取开发信息

`prepare` 已生成 `.work/pck-index.json`。按路径查找需要的配置/资源，只提取需要的内容：

```powershell
python tools/mod.py extract --pck '游戏完整路径.pck' --path 'Asset/Config/Save/ConfigInit.json' --output '.work/extracted'
# 或按索引中确认的目录前缀提取
python tools/mod.py extract --pck '游戏完整路径.pck' --prefix 'Asset/Config/Map/' --output '.work/extracted'
```

输出保持资源相对路径并核验 PCK MD5；已存在相同文件可重复执行，不同内容拒绝覆盖。支持独立未加密 PCK v2/v3/v4；遇到嵌入式、加密、稀疏包或差分包会明确失败。解包是原始文件提取，不是还原 Godot 编辑器工程：`.ctex`、`project.binary`、`.gdc` 等仍可能是导入或编译格式，发布包也不保证含 `.cs` 源码。程序集反射、配置与 `.remap` 信息足以完成本示例；更复杂 Mod 应从发布证据核对类型、注册键和资源依赖。

## 目录与开发规范

| 路径 | 职责 |
| --- | --- |
| `mod/mod.json` | 包身份、入口与 API 声明；资源显式允许名单 |
| `src/HelloMod/Entry.cs` | 生命周期入口、宿主挂载点订阅 |
| `src/HelloMod/HelloMod.csproj` | 普通 .NET 类库；宿主引用不复制到输出 |
| `tools/mod.py`、`tools/pck.py` | 发布包准备、解包、构建、安装、日志验证 |
| `tools/HostProbe/` | 仅反射发布程序集，不调用游戏入口 |
| `tools/runtime_test.py` | 独立发布副本的实际游戏验证 |
| `.agents/skills/` | 需求引导、发布准备、制作、验证与版本迁移 Skills；详细参考按需读取 |
| `docs/`、`docs/wiki/` | 兼容证据、扩展原则与按版本组织的游戏操作知识 |
| `tests/` | PCK 边界与打包隔离检查 |
| `.work/` | 本地引用与分析信息；不提交 |
| `dist/` | 本地构建及验证产物；不提交 |

修改身份时同步清单 `id/name`，修改入口命名空间时同步 `runtimeEntryType`。默认类库项目和输出名保持不变；若确需重命名，可用根目录 mod-project.json 选择项目与程序集，无需修改工具，见 [自定义项目配置](docs/project-configuration.md)。不要改用与宿主同名的程序集。

新增游戏能力先查 `.work/api.json` 和发布资源，优先使用 `XWModRuntimeContext` 提供的 Hooks、Lifetime、Content、Presentation 等能力。订阅在 `Initialize` 建立并纳入宿主生命周期；UI 节点纳入场景作用域，避免切场景残留。入口为普通 C# 类，不继承 Godot 节点，因此最小项目无需 Godot SDK 源生成器。

后续自己的复用组件放入 `src/HelloMod/Components/`，业务能力放入 `Features/`，接入差异放入 `Adapters/`，自己的资源放入 `mod/Assets/`；仅在需要时创建目录。通过 `mod.json.resources` 明确打包新资源，不复制宿主 DLL 或整份解包内容。资源加载与原生 `res://` 路径的区别见 [扩展说明](docs/architecture.md)。

## 给 AI 的入口

[开发 Wiki](docs/wiki/README.md) 集中记录 0.30.0 的启动状态、测试关卡入口、原版组件与鼠标坐标、战斗服务、资源注册表、设置和构建验收路径。AI 先匹配版本，再按任务查阅，避免重复从零分析。每页标明运行实测、静态确认及待验证边界；功能流程仍由 Skills 引导。

玩家提出功能需求时，AI 先使用 **pvzhe-mod-guide** 理解意图和上下文。缺少影响用途、位置或行为且无法合理推断的信息时询问；原版组件选择、资源路径和技术接入由 AI 处理。无需玩家主动要求复用组件或知道 Skill 名称。

既有制作Skills覆盖UI、HUD、设置、简单规则和关卡。社区功能已拆为资源修改、植物/僵尸创建、发射、护具、角色外观、投射物、地图、输入绑定和pmod补丁十个入口；清单与职责见 [功能提取](docs/community-skill-extraction.md)。这些指导直接用于MDK开发，不依赖游戏内模组编辑器；新增资源/角色链路仍需按发行契约与实际运行验收，不能仅因Skill存在就声称全部能力已验证。

基础复用路径的 [0.30内容接入配方](docs/wiki/0.30.0/content-authoring.md) 已有独立发行版运行证据；按 [覆盖矩阵](docs/skill-audit-0.30.0.md) 区分已测与自有动画、新脚本等待专项验证能力，默认模板仍保持Hello World。

可直接描述：“帮我加个按钮”（AI 会问位置和用途），“在对局右下角显示本局击杀数”（AI 判断组件并澄清必要口径），“让这个统计能关闭”（AI 沿用上下文并接入设置）。引导案例见 [.agents/skills/pvzhe-mod-guide/references/scenarios.md](.agents/skills/pvzhe-mod-guide/references/scenarios.md)。

完整进阶实现见 [FeatureLab](examples/FeatureLab/README.md)，复用事实见 [组件目录](docs/reuse-catalog.md)，操作配方见 [功能配方](docs/feature-recipes.md)。默认 Hello World 保持独立：

```powershell
python tools/catalog.py                          # 从发布包/DLL生成复用资料，不复制素材
python tools/mod.py build --example feature-lab
python tools/runtime_test.py --example feature-lab
```

输出在 `dist/feature-lab/`；测试用两次独立进程核验 UI、设置保存/重启、关卡启动、真实僵尸死亡/HUD和胜利。只使用自己的 JSON 配置与 DLL，以及宿主场景/注册键引用。具体边界见示例说明。

项目内 `.agents/skills/` 可由支持项目技能的 AI 工具发现；其他工具直接读取对应 `SKILL.md`。按任务调用：

- `pvzhe-release-analyze`：发布版本、Mod API、兼容证据。
- `pvzhe-pck-extract`：索引、按需提取、资源依赖。
- `pvzhe-mod-develop`：基于发布接口开发、复用宿主能力、构建。
- `pvzhe-mod-verify`：安装、启用、实际运行、收集验证证据。
- `pvzhe-template-upgrade`：仅在明确要求将旧模板适配新版游戏时使用；对比新旧机制，同步模板、工具、文档、版本化 Wiki 及受影响 Skills。见 [升级 Skill](.agents/skills/pvzhe-template-upgrade/SKILL.md)。

可直接要求 AI：“读取本项目 Skills，仅使用我的已发布游戏目录，准备并构建 Hello World，再运行独立存档验证。”这些 Skills 和工具都不要求访问内部源码。

维护者升级模板可要求：“游戏已更新，请使用 pvzhe-template-upgrade 将旧模板适配到我提供的新版发行目录（或游戏项目源码目录）。”没有路径时 AI 会询问，源码只是可选内部分析输入；只有源码而缺少发行版时，不能宣称已完成发布运行兼容验收。普通玩家开发、首次准备和一般排错不会自动触发此迁移。

## 检查与排错

```powershell
python -m unittest discover -s tests -v
```

- 找不到引用：检查发布版 C# `data_*` 目录或 PCK 中是否含 DLL，重新 `prepare`。
- .NET SDK 不匹配：安装 9.0 SDK；不要只修改目标框架绕过宿主要求。
- Mod 未出现：核对 `user://Mods`、清单在 ZIP 根目录、扩展名为 `.pmod`。
- 已出现但未加载：检查启用状态并重启，查看 `ModLoader` 诊断；不要仅以“文件已复制”判定成功。
- 入口加载失败：检查清单类型全名、API 版本、编译引用和游戏版本，确认 ZIP 内没有 `GodotSharp.dll` 或 `PlantsVsZombies.dll`。
- 实际运行失败：保留当前日志、退出码与发布摘要；构建成功只说明编译与打包通过。测试窗口运行需要可用图形环境，不能用静态检查冒充运行验证。

默认用户目录规则参考 [Godot 官方数据路径说明](https://docs.godotengine.org/en/stable/tutorials/io/data_paths.html)。本模板是基于发布包实测的社区示例，不是官方 SDK。

## 游戏内拖拽布局

新增自有浮动控件默认接入[pvzhe-ui-drag](.agents/skills/pvzhe-ui-drag/SKILL.md)：按住鼠标中键拖动、松开保存，发布后仍可调整。横向始终右锚定，沿宿主逻辑画布适配窗口缩放；位置更改带Mod/控件/场景/会话及DLL身份反馈，AI开发时只采用目标Mod的记录。玩家本地覆盖和项目默认布局分开，初始位置仍由AI合理安排。AI首次交付组件就会主动告知中键拖动可永久保存位置，不必先提出换位置；开发过程中收到属于当前Mod/控件的拖动反馈后，AI会更新项目默认布局。

可复用组件、反馈工具和接入协议见[游戏内拖拽布局](docs/ui-drag.md)，可构建案例见[DragLayout](examples/DragLayout/README.md)。默认Hello World不增加拖动、截图或其他功能；旧[pvzhe-placement-preview](.agents/skills/pvzhe-placement-preview/SKILL.md)已弃用，保留工具与历史文档供明确要求的旧流程使用。

自定义功能的运行用例与失败重验见 [验证执行策略](.agents/skills/pvzhe-mod-verify/references/verification-strategy.md)。AI应说明每轮目标，按变更选择用例；报告修复使用已采集证据离线复核，不反复启动完整游戏流程。
