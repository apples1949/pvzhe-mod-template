---
name: pvzhe-mod-settings
description: 为 PVZHE Mod 添加持久化设置、显示开关或受限参数，复用宿主设置声明、存储与设置界面，并明确生效时机。
---

# 设置制作

先按 [Wiki 索引](../../../docs/wiki/README.md) 核对发行版本与摘要，再按需读取 [settings-data](../../../docs/wiki/0.30.0/settings-data.md)。匹配基线时沿用已确认的操作路径；仅对缺项、差异或失败点补充分析，不从零遍历游戏。静态确认和待验证内容不能冒充运行验收。

输入：已澄清的可配置内容、范围和生效时机。输出：mod.json 设置声明、读取/保存/变化处理及持久化验证。

读 [设置配方](../../../docs/recipes/settings-and-gameplay.md) 与 FeatureLab 的 mod.json/Entry.cs。优先复用游戏 Mod 管理的设置界面；示例主菜单按钮只是同一设置的快捷入口，不另造配置文件。

1. 声明 key、type、label、default；数值添加 min/max/step。纯显示设置 affectsGameplay=false、applyMode=immediate；修改战斗规则时明确 restart 生效，不能假装保存后立即生效。
2. context.Settings.Get<T> 的 T 与发布版类型相符，核对当前 DLL；TrySave 返回成功与 RestartRequired 都要处理。不要从用户点击次数反推当前保存值。
3. Changed 用于即时刷新，订阅纳入 Lifetime；生命周期结束前解除事件。默认值、保存值、当前有效值是不同状态，重启设置不能把三个值混为一谈。
4. 有上下文就沿用已有功能，不询问用户技术字段。范围/默认值无法合理推断时回到 mod-guide。

验证：默认值正确，保存后即时字段更新，重启值仍在，非法范围被拒绝，restart 字段提示正确，取消/失败不会静默改变行为，禁用后无残留。feature-lab 自动测试实际保存 bool 并检查 HUD 显隐；持久化重启检查由运行工具的第二阶段完成。
