# PVZHE 最小 Mod 模板

面向玩家与 AI 的 Hello World 项目。以**已发布的 Windows C# 游戏 0.30.0**为基线，编译自己的 C# DLL，并打包为游戏原生 `.pmod`。无需游戏源码，也不分发游戏程序集、贴图或解包内容。

示例启用后，在主菜单左上角显示 `Hello World! · PVZHE Mod`，同时记录初始化、全部 Mod 加载完成与 UI 挂载日志。详细兼容依据与实测记录见 [兼容说明](docs/compatibility.md)。

## 开发环境

- Windows x64；拥有完整的 0.30.0 C# 发布目录（EXE、PCK、`data_PlantsVsZombies_windows_x86_64/`）。其他版本先执行发布版分析，不能默认兼容。
- .NET **9.0 SDK**，最低 9.0.100；`global.json` 允许同一主版本内的最新 feature band。实测 SDK 9.0.316，目标框架 `net9.0`。只装游戏自带运行时不足以编译。
- Python **3.11+**，实测 3.12；仅使用标准库，无 pip/npm 依赖。
- PowerShell；以下命令在模板根目录执行。若系统使用 `py -3`，将 `python` 替换为 `py -3`。

最小示例不需要安装 Godot 编辑器、导出模板或解包完整游戏工程。发布包携带 `GodotSharp.dll` 与 `PlantsVsZombies.dll`，工具直接使用这两个文件作为编译引用。需要编辑场景时，再安装与发布引擎匹配的 Godot .NET 版本；本次发布 PCK 标记为 **4.7.0**。

## 初始化、构建

```powershell
dotnet --list-sdks
python --version
$game = 'E:\Daily\Desktop\植物大战僵尸杂交重制版'
python tools/mod.py prepare --game-dir $game
python tools/mod.py build
python tools/mod.py check
```

将 `$game` 换为自己的发布目录。目录内多个 PCK 时，显式添加 `--pck '完整路径.pck'`。准备步骤读取 PCK 目录及 `project.binary`，记录引擎、格式、资源索引与 SHA-256，并通过发布程序集反射提取 Mod 接口信息，全部保存在忽略提交的 `.work/`。它不会读取任何游戏源码路径。

构建会核验本地引用摘要、编译入口、验证其实现发布版接口，再按允许名单创建产物：

```text
dist/hello-world.pmod       # ZIP；仅 mod.json、Runtime/ModAssembly.dll
dist/build-info.json        # 本地构建证据；含发布包路径与摘要
```

`.pmod` 是最终分发文件；不是 Godot PCK，也不需要 `--export-pack`。不要把 `dist/build-info.json`、`.work/`、整个发布目录或自己的 `bin/` 当成 Mod 分发。更新游戏后重新运行 `prepare` 与 `build`。

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
| `.agents/skills/` | AI 可发现的四个流程 Skills |
| `docs/` | 兼容证据、扩展原则 |
| `tests/` | PCK 边界与打包隔离检查 |
| `.work/` | 本地引用与分析信息；不提交 |
| `dist/` | 本地构建及验证产物；不提交 |

修改身份时同步清单 `id/name`，修改入口命名空间时同步 `runtimeEntryType`。当前构建器固定类库项目和输出名；若重命名项目，也修改工具中的对应路径。不要改用与宿主同名的程序集。

新增游戏能力先查 `.work/api.json` 和发布资源，优先使用 `XWModRuntimeContext` 提供的 Hooks、Lifetime、Content、Presentation 等能力。订阅在 `Initialize` 建立并纳入宿主生命周期；UI 节点纳入场景作用域，避免切场景残留。入口为普通 C# 类，不继承 Godot 节点，因此最小项目无需 Godot SDK 源生成器。

后续自己的复用组件放入 `src/HelloMod/Components/`，业务能力放入 `Features/`，接入差异放入 `Adapters/`，自己的资源放入 `mod/Assets/`；仅在需要时创建目录。通过 `mod.json.resources` 明确打包新资源，不复制宿主 DLL 或整份解包内容。资源加载与原生 `res://` 路径的区别见 [扩展说明](docs/architecture.md)。

## 给 AI 的入口

项目内 `.agents/skills/` 可由支持项目技能的 AI 工具发现；其他工具直接读取对应 `SKILL.md`。按任务调用：

- `pvzhe-release-analyze`：发布版本、Mod API、兼容证据。
- `pvzhe-pck-extract`：索引、按需提取、资源依赖。
- `pvzhe-mod-develop`：基于发布接口开发、复用宿主能力、构建。
- `pvzhe-mod-verify`：安装、启用、实际运行、收集验证证据。

可直接要求 AI：“读取本项目 Skills，仅使用我的已发布游戏目录，准备并构建 Hello World，再运行独立存档验证。”这些 Skills 和工具都不要求访问内部源码。

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
