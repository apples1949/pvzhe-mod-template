# 构建与分阶段验证

基线：[0.30.0](overview.md)。当前 build/check、包身份、两个固定示例已经实测；自定义项目可通过mod-project.json选择，通用运行场景仍无配置化入口。此限制应明确告知，不要求 AI 为简单功能重写工具链。自定义验收和失败重验按 [验证执行策略](../../../.agents/skills/pvzhe-mod-verify/references/verification-strategy.md) 拆分采集、判定及报告；该流程指导不表示固定示例工具已提供通用用例选择器。

## 在最小模板开发自己的 Mod

默认源码是 src/HelloMod、清单在 mod/mod.json。可以保留项目目录、程序集和类名，修改身份与实现；显示名和 Mod ID 不要求等于 C# 类型名。自定义 ID 后产物变成 dist/<id>.pmod。FeatureLab 是单独项目，默认模板不引用它。

build默认构建HelloMod，支持根目录mod-project.json选择项目/程序集，见 [项目配置](../../project-configuration.md)；`--example feature-lab`仍使用独立固定项目。重命名时同步csproj引用和清单入口，非法配置直接失败。避免为单个按钮先搬迁两个示例、全局替换测试路径或将用例期望改成新文件名来掩盖工具缺陷。自定义验收不等于注册一个新的 --example：先保持当前可工作的构建入口，再另设功能验收。

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

Bash 中过滤输出时使用 pipefail 并显式失败即停止/检查每条命令的真实退出码，或者把日志写文件后再阅读；pipefail本身不阻止分号后的命令执行；`build | tail ... && run` 可能只检查 tail 的成功，`build; run` 不会在失败时停止。存在旧 pmod 时尤其不能以“测试运行了”证明当前修改已构建。

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

## 加载前提与启用清单（用户实机记录，本模板待复核）

状态：以下来自用户对更早版本的核对与实机；本模板的运行工具已自动处理启用写回，但"为什么装了却没加载"的排查顺序值得先记住。

- 宿主只扫描 Mod 目录**顶层的 `.pmod` 文件**，不递归；把工程目录当 Mod 放进去不会加载。
- 启用状态在单独的启用清单里按**清单 id** 记账；文件缺失或内容为空 ⇒ **一个 Mod 都不加载**。所以"包放进去了但游戏里没有"先查加载前提，不要先怀疑包结构或反复重打包。
- 手工覆盖启用清单容易和宿主自己的写入打架；测试驱动改了启用状态后要恢复原状，别把测试残留留给玩家目录。

**`package applied` 行的字段怎么看**：该行通常还带包内资源数、运行时入口、回调数与诊断计数，另有一行"N/N packages"与回滚汇总。角色包里的配置/卡片/组件集属于该包自带的资源，不一定进宿主注册表 ⇒ **资源数偏小不等于失败**。诊断非空必须逐条归类，未知诊断保留原样，不能为了让结论好看就当成可忽略。

**产物与安装态对账**（改代码后行为没变时先查这一层）：编译产物与包内同名文件必须比摘要；装机后再从包里取出 DLL 复核一次摘要——这是"新代码真的进包"的唯一证据，日志文案和构建成功都不算。另外解包缓存可能复用旧内容，换了版本要连缓存一起更新；判断"跑的是不是新版本"看部署 DLL 的摘要或特征串。

## 发布运行时的裁剪边界

0.30随游戏发布的.NET经过裁剪。用完整SDK编译成功不保证所有BCL方法运行时存在；双例实验中的 `Enumerable.Sum(IEnumerable<long>)` 与超级机枪夹具中的双序列 `Enumerable.Zip` 重载 在首次进入方法时抛出MissingMethodException。此前捕获工具也遇到Path.GetFullPath和System.Text.Json的缺失，不能把一个方法可用推广为整个命名空间可用。按实际调用点用宿主可用能力或简单循环替代，检查首次执行与日志；不把完整系统DLL塞进pmod绕过。JIT可能在方法体try进入前就失败，验收驱动应同时观察宿主presentation/初始化失败诊断，有限退出，不等待业务标记到全局超时。

## 固定工具的覆盖范围

默认 runtime_test 复制发行版到独立用户目录，测试 Hello World 标签；FeatureLab 验证自己的目录/关卡/卡槽、UI事件、设置重启、阳光、死亡/HUD与胜利。完整命令与证据位置见 [示例验证](../../../.agents/skills/pvzhe-mod-verify/references/example-scenarios.md)。自定义采集可显式提供包、驱动和业务结果，复用隔离运行/错误门禁；[超级机枪案例](../../super-gatling-example.md)有原版冒险业务调用配方。任意自定义Mod场景与真实鼠标命中仍未由工具统一实现。

发布版禁用 --main-pack，本机 headless 曾原生崩溃；当前图形 OpenGL 副本路径已实测。退出冻结扩展点撤销和曾出现的 ObjectDB 泄漏诊断不能一概过滤；JSON unsupported 诊断仅在明确自读 JSON 的已知场景可解释为非阻断。具体排查见 [运行排障](../../../.agents/skills/pvzhe-mod-verify/references/runtime-troubleshooting.md)。

最终包除功能测试外，还需不带自定义测试参数的普通加载验收。具体阶段、清单注册契约及测试夹具隔离见 [自定义功能验收](../../../.agents/skills/pvzhe-mod-verify/references/feature-acceptance.md)。通过 Mod 测试关卡只报告该场景，不沿用“原版关卡成功”标签。

## 查询发布接口时减少猜测

prepare/build已生成HostProbe后，使用 `dotnet tools/HostProbe/bin/Release/net9.0/HostProbe.dll .work/references --types AudioManager 'AudioManagerEnum+TYPE'`。保留原methods字符串，methodDetails补充isStatic、参数名、类型、out、optional和默认值，enumValues显示真实名称和值。大类型可添加 `--member CoinCreate` 限定成员名片段（保留匹配重载），避免将海量JSON输出截断后当作完整数据。只有类型片段时使用 `--find-types Coin`；结果的loaderErrors非空表示部分类型因缺依赖未加载，匹配结果仍可用于下一步查询，空匹配不能当作完整不存在证明。查询不会执行宿主游戏逻辑，公共签名不证明行为。

新增元数据用不含游戏内容的小程序集集成测试验证；独立临时目录构建，不与正在验收的Mod共享bin。部分编译错误是调用者未核对签名造成，不能全部归为模板缺陷；保留信息并沿实际编译诊断修正。
