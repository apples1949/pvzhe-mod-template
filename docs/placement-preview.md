# 可视化位置输入

默认由 AI 自主完成布局；仅在用户明确想拖动决定位置，或认可用预览解决表达困难时使用 [pvzhe-placement-preview](../.agents/skills/pvzhe-placement-preview/SKILL.md)。窗口采用已确认的简洁样式：画布、多物件拖动、尺寸编辑、布局切换、可关闭占位提示和倒计时。

用户确认的是预览参考画布内的摆放位置，不自动吸附或避让。“绝对”表示玩家选择优先，即使该处有宿主组件也不擅自移位；控件仍须遵循游戏的窗口缩放、锚点和坐标变换。占位边界只作参考，覆盖提示区仍可确认。画布内拖动保证组件完整处于内容区；尺寸编辑不自动移动位置。默认60秒，点击+60秒可延长，窗口关闭等同取消。未确认的拖动超时仍不应用。

## 环境与命令

Python 3.11+，含 tkinter（当前 Tk8.6）。纯色模式没有额外依赖；图片背景/组件贴图需 Pillow，测试环境版本通过本地 GUI 验证，不要求游戏源码或 Godot 编辑器。安装图片依赖：`python -m pip install Pillow`。

```powershell
$env:PYTHONUTF8 = '1'
# 无游戏资源的演示，仍可沿用 tools/placement_demo.py
python tools/placement_editor.py
# 配置包含两个模拟布局与占位提示，均非游戏的正式布局
python tools/placement_editor.py --config examples/PlacementPreview/session.json --output .work/placement-session-01/result.json
# 恢复同配置草稿，重新开始反馈时间并重新确认
python tools/placement_editor.py --config examples/PlacementPreview/session.json --resume .work/placement-session-01/result.json --output .work/placement-session-02/result.json
```

AI 调用时使用新的会话输出目录，stdout/stderr 如需重定向也放该目录；后台启动 shell 使用隐藏窗口，Tk窗口保持可见。工具不是默认开发门禁。配置或图片加载失败退出码2，没有确认结果；不能读取旧输出来替代失败结果。

## 输入协议 schemaVersion=1

完整可运行例子见 [session.json](../examples/PlacementPreview/session.json)。所有图片路径相对配置文件，也支持本地绝对路径；不读取远程URL。背景须为裁剪后的内容区，宽高比与逻辑画布一致。UI按比例缩小预览，坐标一直以原逻辑画布为单位。

| 字段 | 内容 |
| --- | --- |
| schemaVersion | 1 |
| title | 可选窗口标题 |
| context | 可选场景/版本/阶段等会话标记；输出原样保留，不自动推断游戏身份 |
| layouts | 非空布局数组；各布局独立坐标 |
| layouts[].id / label | 稳定且唯一ID、可选显示名称 |
| layouts[].canvas | 整数width/height，100～4096；每个布局可有不同尺寸 |
| background / backgroundColor | 可选本地背景图片、纯色；图片预览不会恢复游戏的动态行为 |
| objects | 非空组件数组；id在布局内唯一，text为名称，x/y/width/height为逻辑矩形 |
| objects[].imagePadding | 可选四边透明留白（逻辑单位，0～128）；图片绘制在组件矩形外侧，不改变控件尺寸 |
| objects[].image | 可选本地PNG等Pillow支持的静态图片；按组件尺寸预览，优先提供对应原版实际外观；没有图片时用模拟组件 |
| regions | 可选占位矩形数组，含label、x/y/width/height；只画边界，不改变用户选择 |

组件最小尺寸20，须完整位于逻辑画布。坐标支持有限数值，禁止NaN/Infinity。背景与组件图片每边最多4096。没有游戏资源时使用纯色模拟，不声称准确还原原版字体、九宫格、交互和动画。自定义素材必须本地合法可用；游戏图片留在.work。

## 输出与恢复

stdout打印一个UTF-8 JSON结果，并原子保存到指定文件。输出含 schemaVersion、sessionId、configSha256、status、confirmed、changed、placementPolicy=absolute、coordinateSpace=canvas-logical-pixels、context、activeLayout、visitedLayouts 和各布局完整组件矩形。

为兼容已有会话，保留 placementPolicy=absolute；它表示在所选参考画布中忠实落地、不自动避让，不指定TopLeft锚点、固定屏幕像素或取消宿主缩放。context应记录参考画布、背景来源、目标父层与已确认的缩放/锚点策略，不能仅由x/y推断布局关系。

- confirmed：仅点击确认产生；未拖动也可确认当前方案。
- cancelled：取消或关闭，只保留草稿。
- timeout：时间耗尽，message为“用户还未输入”，有修改时为“用户还未输入（未确认）”。

只有confirmed才应用。未访问布局仍输出其初始/恢复矩形，visitedLayouts用于区分覆盖；不能声称全部布局由用户逐一调整。配置摘要绑定模式、背景/组件声明及图片内容摘要（assetSha256）；配置或图片内容变更拒绝恢复，重新准备会话。恢复既往confirmed结果也不会继承确认，新会话仍需用户确认。同路径图片被修改也会拒绝恢复，需重新准备会话，不将旧背景下的位置确认当成新图确认。

## 忠实落地

AI应记录结果对应的布局、阶段和逻辑画布，将其中的绝对矩形换算到目标父节点的实际坐标空间。窗口预览尺寸和游戏逻辑坐标不同，不能直接按截图像素硬编码。背景裁剪/相机/CanvasLayer若无法明确映射，先解决标定，不猜坐标。特别区分 Viewport 纹理截图与完整窗口截图：GetScreenTransform可能包含黑边/窗口偏移，纹理图的原点不包含这些边缘；根据实际背景来源转换，不能把完整窗口坐标直接套入纹理图。

落实坐标前核对宿主同类控件的父层、锚点、偏移及拉伸策略，优先沿用相同的坐标体系。固定逻辑画布随窗口整体缩放时，保留画布内坐标并继承画布变换；宿主父容器随窗口改变尺寸时，依据其锚点策略由确认矩形计算偏移。TopLeft可用于确实固定的逻辑画布，但不是通用落地方案；不能为了让offset等于x/y就改掉宿主布局关系，也不能未经依据把坐标除以画布宽高改为百分比定位。

例如参考画布1080×600，按钮x=908、y=115、170×46，参考右边距为2。若匹配宿主采用右侧锚点，则参考容器宽1080时横向offset为-172至-2；容器变化后保持这套宿主锚点关系。若宿主是固定1080逻辑画布整体缩放，则保留908/115并随画布缩放。两者在参考画布相同，缩放行为由宿主证据决定，不能仅凭截图认定右锚点或向用户索要技术参数。

确认后不因金币显隐或卡槽占位自行重排、跳位或建立避让关系；这些仅在用户明确要求时实施。窗口适配与避让是不同责任，前者默认保留。对应布局的运行验收先把最终矩形还原到参考画布与确认值比对，再检查至少两种窗口尺寸（其中一种不同宽高比），验证显示、宿主相对关系、黑边映射及实际点击；不同窗口的屏幕矩形不要求与参考数值逐像素相同。发现占位冲突如实说明，不改变用户摆放意图。其他未经用户确认的布局保持原规则或说明未覆盖。

## 验证与范围

`python -m unittest discover -s tests -v` 包含确认/超时/取消、绝对重叠保留、模式独立坐标、恢复和倒计时测试。`python tools/placement_editor.py --self-test --output .work/placement-editor/self-test.json` 在隐藏Tk窗口测试拖动与尺寸；输出是测试结果，不能当用户确认。GUI验证覆盖图片背景/组件、1080×600缩小预览坐标映射、两个布局切换和真实计时关闭；不替代游戏中的还原与业务验收。

## 游戏外观预览准备

先按 [资源缓存与捕获](resource-cache-and-capture.md) 准备干净背景与独立透明组件，绑定当前版本/Mod DLL后再开窗口。不要用含原场景像素的裁片冒充透明PNG。正式捕获会话应由 tools/preview_session.py 产生previewProvenance，载入时拒绝过期发行或组件构建；模拟示例不要求游戏身份。imagePadding须采用对应画布的逻辑单位，尺寸采用捕获返回的实际Size而不是PNG整体尺寸。
