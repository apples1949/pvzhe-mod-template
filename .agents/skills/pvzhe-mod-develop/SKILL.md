---
name: pvzhe-mod-develop
description: 基于 PVZHE 已发布程序集开发并构建最小 C# pmod，评估宿主能力复用及后续组件扩展；用于入口、资源及功能修改。
---

# 开发与构建

玩家功能请求先经 pvzhe-mod-guide，再读具体制作 Skill；本 Skill 负责共同编译/打包流程。默认最小模板是开发起点，FeatureLab 是可选参考，只取需求所需实现，不默认加入其按钮、统计、规则和关卡。只有构建该示例时命令加 `--example feature-lab`，输出 dist/feature-lab。

输入：发布分析结果、已澄清需求、模板。输出：满足需求的 Mod 变更、对应 pmod 与本地构建证据；自定义身份与入口需同步修改清单。

新建独立 Mod 或准备分发时读 [身份与发布规范](references/identity-and-release.md)。创建时确定合规且稳定的 ID，发布前确认用户署名/显示名称/版本；build/check 均执行基础字段校验，分发使用 `--release` 加严检查。

1. 读 README、`docs/architecture.md`、`.work/api.json`。缺少发布证据先 prepare。编译引用只能来自用户发布包，不引用源码工程或复制宿主实现。
2. 最小入口为普通类 `HelloMod.Entry : IXWModRuntimeEntry`。在 `Initialize` 建立功能与订阅，通过宿主 Lifetime 管理订阅，通过 UI 挂载回调的场景作用域管理节点；`Shutdown` 释放本地引用，避免静态节点/跨场景残留。
3. 先评估宿主 Hooks、Content、Settings、Presentation、Progress 等公开能力；只有不足时才新增本地组件。需要时使用 Features/Components/Adapters 分层，不为 Hello World预建完整库。引用 `res://` 必须由发布索引证实；包内相对文件不会自动加入宿主资源空间。
4. 修改 `mod/mod.json` 时核对唯一 ID、类型全名、schema/API 版本、运行时 required 策略；添加资源显式列入 `resources`。新增第三方 DLL、多程序集或 Godot 节点脚本超出当前单 DLL 构建器，需要先核对发布协议并扩展工具，不能将 bin 整包复制。
5. 执行 `python tools/mod.py build` 与 `python tools/mod.py check`。工具从明确允许名单组包；源文件、宿主 DLL、PCK 和本机报告必须留在包外。

验证：编译无错误；入口通过发布程序集的接口/公开无参构造检查；ZIP 根部为 mod.json，入口位于 Runtime/ModAssembly.dll。工具修改还需 `python -m unittest discover -s tests -v`。最后按 mod-verify 实际运行，不能以构建成功代替游戏验证。
