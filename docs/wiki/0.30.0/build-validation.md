# 构建与分阶段验证

基线：[0.30.0](overview.md)。当前 build/check、包身份、两个固定示例已经实测；自定义项目重命名与通用运行场景尚无配置化入口。此限制应明确告知，不要求 AI 为简单功能重写工具链。

## 在最小模板开发自己的 Mod

默认源码是 src/HelloMod、清单在 mod/mod.json。可以保留项目目录、程序集和类名，修改身份与实现；显示名和 Mod ID 不要求等于 C# 类型名。自定义 ID 后产物变成 dist/<id>.pmod。FeatureLab 是单独项目，默认模板不引用它。

build 当前明确支持默认项目和 `--example feature-lab`；若确需重命名目录/程序集，必须同步构建路径与入口检查及受影响测试。避免为单个按钮先搬迁两个示例、全局替换测试路径或将用例期望改成新文件名来掩盖工具缺陷。自定义验收不等于注册一个新的 --example：先保持当前可工作的构建入口，再另设功能验收。

名称、署名、ID、版本及发布模式集中在 [身份与发布规范](../../../.agents/skills/pvzhe-mod-develop/references/identity-and-release.md)。发布检查不能代替当前 DLL 的真实行为验收。

## 构建失败必须停止

```powershell
python tools/mod.py build
if ($LASTEXITCODE -ne 0) { throw '构建失败，停止运行验收' }
python tools/mod.py check
if ($LASTEXITCODE -ne 0) { throw '包检查失败，停止运行验收' }
python tools/runtime_test.py
if ($LASTEXITCODE -ne 0) { throw '运行验收失败，保留日志' }
```

上述最后一行只验默认 Hello World。FeatureLab 三个命令均使用对应 --example。自定义功能的运行入口另设，不能把最后一行当成任意功能测试。

Bash 中过滤输出时使用 pipefail 并检查真实退出码，或者把日志写文件后再阅读；`build | tail ... && run` 可能只检查 tail 的成功，`build; run` 不会在失败时停止。存在旧 pmod 时尤其不能以“测试运行了”证明当前修改已构建。

## 用最早失败阶段定位

| 阶段 | 必须具备的证据 | 失败后的动作 |
| --- | --- | --- |
| 构建 | 编译及入口契约成功，当前包与 DLL 摘要 | 修编译错误；不继续运行旧包 |
| 加载 | package applied、当前初始化与 DLL 摘要、当前日志 | 查清单/接口/依赖，不改 UI 来解决加载错误 |
| 测试前提 | 主菜单或测试对局实际就绪、资料/模态/身份满足 | 查 [启动](startup.md) 和 [操作路径](battle-testing.md)，不认定业务失败 |
| 挂载 | 正确场景的自己的节点、尺寸和可见性 | 查对应挂载点、Lifetime和布局 |
| 交互 | 鼠标事件命中、回调进入 | 按 [UI](ui.md) 区分坐标、遮挡与逻辑；信号成功不替代鼠标成功 |
| 业务 | 状态变化/命令结果/最终死亡或保存结果 | 只分析对应接口语义及数据口径 |

成功日志需要对应当前包、当前初始化和当前步骤；测试失败截取完整异常、状态和截图，不只 tail 最后三行。没有新的证据时不要一遍遍改等待时间或补随机点击。

## 固定工具的覆盖范围

默认 runtime_test 复制发行版到独立用户目录，测试 Hello World 标签；FeatureLab 验证自己的目录/关卡/卡槽、UI事件、设置重启、阳光、死亡/HUD与胜利。完整命令与证据位置见 [示例验证](../../../.agents/skills/pvzhe-mod-verify/references/example-scenarios.md)。通用自定义项目、原版冒险自动进入与真实鼠标命中未由该工具统一实现。

发布版禁用 --main-pack，本机 headless 曾原生崩溃；当前图形 OpenGL 副本路径已实测。退出冻结扩展点撤销和曾出现的 ObjectDB 泄漏诊断不能一概过滤；JSON unsupported 诊断仅在明确自读 JSON 的已知场景可解释为非阻断。具体排查见 [运行排障](../../../.agents/skills/pvzhe-mod-verify/references/runtime-troubleshooting.md)。

最终包除功能测试外，还需不带自定义测试参数的普通加载验收。具体阶段、清单注册契约及测试夹具隔离见 [自定义功能验收](../../../.agents/skills/pvzhe-mod-verify/references/feature-acceptance.md)。通过 Mod 测试关卡只报告该场景，不沿用“原版关卡成功”标签。
