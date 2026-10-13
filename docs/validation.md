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
