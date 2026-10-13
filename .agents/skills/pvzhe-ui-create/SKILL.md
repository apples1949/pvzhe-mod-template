---
name: pvzhe-ui-create
description: 为 PVZHE Mod 制作按钮、提示或确认弹窗及简单界面，默认评估并复用原版场景、字体和交互；接收已澄清的玩家需求。
---

# 基础 UI 制作

先按 [Wiki 索引](../../../docs/wiki/README.md) 核对发行版本与摘要，再按需读取 [ui](../../../docs/wiki/0.30.0/ui.md)。匹配基线时沿用已确认的操作路径；仅对缺项、差异或失败点补充分析，不从零遍历游戏。静态确认和待验证内容不能冒充运行验收。

先经过 pvzhe-mod-guide。输入：明确的位置、用途、文字/内容和交互；输出：UI 功能、必要适配代码及实际交互证据。关键缺项返回需求引导，组件选型由 AI 决定。

1. 读 [复用目录](../../../docs/reuse-catalog.md) 与 [示例说明](../../../examples/FeatureLab/README.md)。需要重新核对时执行 `python tools/catalog.py`，只使用发布包与 DLL。目录存在不代表所有组件已运行验证。
2. 优先调用原版 DialogManager 或实例化 MainButton，参考 `examples/FeatureLab/Adapters/HostUi.cs`。原版资源来自宿主 res://，无需打包复制贴图；不要将 new MainButton() 当成完整场景，它缺少子节点和配置。
3. 新增控件按 [场景适配与宿主共存](references/scene-fit.md) 由匹配 Wiki 或发行场景/行为分析建立控件、阶段、布局模式与动态占位清单（含空卡槽、金币等短暂信息），再明确显示/启用阶段、避让原版控件和模态优先级；截图未显示不能证明区域空闲；挂载不等于战斗开始。再在合适的主菜单/战斗 UI 挂载回调创建节点，用 surface.Lifetime 管理节点和事件，避免反复挂载叠加。业务弹窗不能直接当作通用容器；确认/输入框尚需单独验证。
4. 通用提示/确认框的 Init(Dictionary) 不能假定自动设置字段；当前 Tips 应设置公开 text。正常关闭走 CloseDialog，确保暂停与 TimeScale 恢复；不要只 QueueFree。避免叠加模态弹窗，避免切场景清理覆盖宿主状态。
5. UI 使用本地展示，不借按钮绕过战斗命令的权限/验证。修改共享 Theme/StyleBox 前按需复制；按钮布局、文字、缩放、鼠标过滤和字体须实际检查。

验证：编译、加载；按钮文字和点击音效；点击打开正确内容；关闭恢复交互/暂停；再次打开不重复触发；换场景无残留。`runtime_test.py --example feature-lab` 验证已有提示框配方，不能证明任意自定义界面正确。
