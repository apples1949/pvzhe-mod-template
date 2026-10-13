# 0.30.0 基线与阅读方法

适用：Windows x64 C# 发布版；2026-10-13 的发行静态检查、模板实测。不是官方 SDK 文档。玩家只需完整发行版，源码不是前置条件。

| 项目 | 基线 |
| --- | --- |
| 游戏 | 发布标识0.30.0；project.binary 标记0.30.0.0 |
| Godot / PCK | Godot 4.7.0，真实运行4.7 stable mono；未加密独立 PCK v4，27,426条目 |
| .NET | 游戏 net9.0；开发实测 SDK 9.0.316，模板允许同主版本 feature band |
| Mod | manifest schema v3，宿主 runtime API v3；默认 Hello World 使用 API v1，FeatureLab 使用 v3 |
| PCK SHA-256 | `36e013ce4852dd6eb17b04c61ac2c37b97b3643475cf4ca9a1f8c85d5ff7f282` |
| PlantsVsZombies.dll SHA-256 | `e31986ec8fd26f349bd29cd5444e6649b76f3f722d13a6695b0ce089cd2e51d1` |

上述摘要是发行身份，不是可以替代源码的文件内容。自己的 `.work/release.json` 与本表不同，先检查是否另一个发布变体/版本，不能直接认定所有路径仍适用。

## 证据入口

- [兼容说明](../../compatibility.md)与[实测记录](../../validation.md)：历史基线和已覆盖行为。
- `python tools/mod.py prepare --game-dir '<用户发行目录>'`：发行摘要、PCK索引、API摘要、编译引用，保存于本地 .work。
- `python tools/catalog.py`：原版 UI 场景依赖与选定类型公共成员，输出 .work/reuse-catalog.json。它是按需摘要，不是全部宿主 API。
- [FeatureLab](../../../examples/FeatureLab/README.md)：UI、HUD、设置、阳光和现代关卡的可选实现；不自动成为用户 Mod 的功能。

入口 `IXWModRuntimeEntry` 是普通托管类，提供 Initialize、OnAllModsLoaded、Shutdown。Initialize 适合声明数据和注册钩子，不表示主菜单或对局已可用；场景节点在对应 Presentation 回调创建。按 [启动](startup.md) 与 [对局路径](battle-testing.md) 等待实际状态。

先读 [Wiki 索引](../README.md) 中与需求对应的页，沿用已确认事实；只对空白和冲突部分提取 PCK 或反射接口。未运行的接口、资源和代码分支不提升为已实测能力。
