---
name: pvzhe-release-analyze
description: 分析 PVZHE 已发布 Windows C# 游戏的 PCK、程序集及 Mod 接口，建立无需游戏源码的开发基线；适用于首次准备和游戏升级。
---

# 发布版分析

输入：用户的完整发布目录、本模板、Python 3.11+、.NET 9 SDK。输出：本地 `.work/release.json`、`pck-index.json`、`api.json`、引用 DLL，以及适用于该发布版的兼容判断。

1. 读项目 README 与 `docs/compatibility.md`。确认发布目录内 EXE、PCK、`data_*` 运行时的对应关系；多个 PCK 要指定目标，不能任选。
2. 在模板根目录执行 `python tools/mod.py prepare --game-dir '<发布目录>'`，必要时添加 `--pck '<PCK>'`。工具直接索引 PCK，从发布运行时或包内获取两个编译引用，再反射入口契约及常用服务。不要访问内部源码或要求用户提供源码。
3. 检查三个报告：PCK 格式/引擎/摘要、DLL 来源/摘要、schema 与 runtime API、入口方法。游戏版本取发布 `project.binary`/文件名/实际启动记录，不能将程序集 `1.0.0.0` 误认为游戏版本。
4. 区分已证实接口和未知能力。`api.json` 仅摘要部分类型；新增能力按需分析发布 DLL 的公共类型、配置与资源。若进行反编译，只保留用户本地工作区中的分析材料，不把它加入模板分发。
5. 将证据用于 `pvzhe-mod-develop`。发布更新必须重新准备，不能将旧接口、UID、注册键或 API 版本无条件套用。

验证：prepare 退出码 0，PCK 条目及头部可解析，引用摘要与来源完整，入口契约包含三个生命周期方法。再构建验证发布接口匹配；准备成功不等于 Mod 已运行。

限制：不支持加密/嵌入式/稀疏/差分包；缺少 DLL 或反射接口时报告明确缺失项，不能编写替代宿主接口来伪造兼容。最小模板无须 Godot 编辑器或完整解包工程。
