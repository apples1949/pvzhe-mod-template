# 本地游戏环境验收

2026-10-23，Windows，已声明兼容的0.30.0发行版。此记录验证模板工具的存储与更新流程，不代表已支持下一游戏版本。

| 检查 | 结果与边界 |
| --- | --- |
| 自动测试 | `python -m unittest discover -s tests -v`：184项通过 |
| 两槽轮换 | 合成发行夹具验证三次导入后只保留current/old、回退交换、同版复用、复制/提升失败回滚；最旧槽清理中断时保留新current和完整old，拒绝继续轮换 |
| 兼容判断 | 合成发行验证模板/游戏摘要不匹配及文件篡改拒绝；未拿尚未提供的新游戏冒充真实跨版本验收 |
| 使用者更新 | 本地Git上游/玩家分支验证差异暂存、重叠识别、玩家身份及origin保留、未跟踪文件备份、版本失配阻止record；未自动合并任意玩家Mod |
| 实际准备/构建 | 真实发行重复prepare，发行文件mtime及SHA-256不变；默认Hello World build/check通过 |
| 实际共享运行 | Hello World与AttackLab普通启动均通过；共用current/runtime中123个EXE/DLL文件，第二轮mtime不变；不同包、驱动、存档、日志和还原记录分别保留 |
| 分析隔离 | 实际执行prepare --analyze-only，当前release/api/index及两份编译引用摘要不变 |
| 历史整理/恢复 | 125份可重建PCK已归档；真实505126042字节测试PCK恢复后SHA-256逐字节一致，再整理通过；日志、截图、Mod及旧资源会话保留 |

测试PCK恢复摘要：`b48709d11c1bfc9bcf93376b54ebc054acde682c1e876f2db3540562b6ce7465`。

本次本地文件逻辑总体积约80.902→3.412 GiB，整理后.game约1.272 GiB、.work约2.128 GiB；包含新增共享环境和保留证据，不是新克隆仓库的体积，也不是文件系统物理分配量测量。多PCK同目录的历史个案分开归档，未用一份记录覆盖不同测试包。

本轮可追溯证据在忽略提交的.work/storage-maintenance内：initial-clean.json、real-pack-roundtrip.json、runtime-reuse.json、disk-usage-after.json；工具测试日志为.work/game-storage-tests.log。实际游戏证据为.work/runtime/9a05f5082ca2及.work/attack-lab/normal-55243704/runtime。它们不随模板分发。

日常操作及恢复边界见[环境说明](game-environment.md)。Hello World仍是原最小示例，AttackLab只用于验证共享环境的另一条调用路径，没有增加默认功能。
