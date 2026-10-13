# 扩展设计

入口只负责连接生命周期和功能。Hello World 使用宿主 `IXWModRuntimeEntry`、`XWModHookPoints.UiMount` 与 `XWModLifetime`：不复制宿主的 UI 框架，不修改原版文件，不额外实现全局事件总线。

有多个功能时，在 `Features/` 中拆出可释放的功能对象，入口创建它们并交给 `context.Lifetime.Track`。需要复用时再把本地 UI、数据处理等抽到 `Components/`；组件应接受显式宿主上下文/作用域，避免静态持有节点或入口。版本适配放在 `Adapters/`，不在每个功能中散布版本判断。这些目录是扩展约定，初始项目未创建空组件库。

## 复用决策

| 需求 | 优先评估宿主能力 | 模板自行提供的时机 |
| --- | --- | --- |
| 生命周期与清理 | `IXWModRuntimeEntry`、`XWModLifetime` | 业务对象实现 `IDisposable` |
| 主菜单/战斗 UI | 现有 UiMount、v3 Presentation 挂载点及 owner 容器 | 自己的 Label/Control 组合与布局 |
| 游戏机制扩展 | Hooks、版本化扩展点、Content 注册 | 宿主没有公开机制时先分析证据，再封装适配 |
| 设置、进度、媒体 | 已发布的 Settings/Progress/Presentation 服务 | 独立业务逻辑，不复制内部管理器 |

`.work/api.json` 是常用公共类型的反射摘要，不是完整 API 文档。反射工具避免枚举所有宿主类型，以免非必要的第三方依赖阻断最小准备流程；有更深需求时按需分析发布 DLL，记录类型、方法签名和版本，不将源码当作玩家前置条件。

## 资源边界

- 宿主 `res://` 属于已发布 PCK 的虚拟资源空间。引用时使用索引/配置证实的路径和注册键，不能猜路径或跨版本依赖未核验 UID。
- `.pmod` 是 ZIP，加载器将文件提取到私有目录；包内相对路径不会自动成为宿主 `res://`。本示例不依赖任何游戏素材。
- 新素材放 `mod/Assets/`，在 `resources` 中列出。普通文件可由 `context.PackageRoot` 和包内相对路径读取。Godot 场景/资源及角色注册需要按已发布 Content API 和加载器支持的格式处理；不能假设 `ResourceLoader.Load("res://Assets/...")` 自动找到 ZIP 内文件。
- 添加注册内容时同步清单 `provides`、`contentEntries` 等宿主要求，使用带 Mod 命名空间的键；原版覆盖需明确声明、验证冲突及卸载恢复，不作为 Hello World 默认行为。
- 编译引用只留本地 `.work/references/`。自己的额外 DLL 依赖需要重新核对发布版依赖目录协议与加载器，本构建器只支持单 DLL 最小示例，不隐式复制所有依赖。

先通过最小示例的实际加载验证，再一次引入一个功能。验收既包括加载成功，也包括退出/禁用后无残留及场景作用域清理。涉及战斗规则、多人模式等时增加相应功能验证，不把主菜单 Hello World 的验证结果泛化为所有机制可用。
