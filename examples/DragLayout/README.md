# 游戏内拖拽布局示例

可选示例，不进入Hello World。主菜单新增原版样式Hello World按钮与可拖文字：按住中键移动、松开保存；左键按钮打开原版提示框。横向无论拖到哪里都靠右，文字纵向靠底部、按钮纵向靠顶部。发布包保留拖动和反馈，不需Python预览、源码或Godot编辑器。

在模板根目录完成发行prepare后：

```powershell
python tools/mod.py build --example drag-layout
python tools/mod.py check --example drag-layout
python tools/mod.py install --example drag-layout --mods-dir '<自己的Mods目录>'
```

输出dist/drag-layout/drag-layout-demo.pmod。退出游戏再安装，不自动替换其他Mod。此为示例身份，创建自己的Mod时修改ID/名称/作者及Assets/ui-layout.json的modId，遵循身份与发布规范。

DragLayout.csproj显式链接components/RuntimeUi/DragLayout.cs；Entry创建真实UI和场景作用域绑定，Assets/ui-layout.json是可提交的默认布局。玩家覆盖使用宿主Local数据，不随包分发。共享组件有Reset接口供实际Mod设置页调用；本例不新增一组额外测试按钮。

```powershell
python examples/DragLayout/verify.py
# 最终普通包：没有Mod审计参数，仍实际发送中键拖动并检查位置
python examples/DragLayout/verify.py --normal
```

验收在发行副本与隔离用户中构建独立审计程序集，同时加载另一Mod，合成中键/左键输入，检查取消、模态、文字与按钮、父层缩放、运行中窗口改变和拖动中改变、拖到左侧仍右锚定、恢复默认、发布数据保存及同一用户第二进程恢复。协议筛选与导入另由工具测试覆盖。Verification不编入生产DLL；合成夹具开启GuiEmbedSubwindows以独立于桌面指针所在窗口，该设置不进入生产Mod，不能代表原生窗口系统鼠标或手机实机。证据留.work/drag-layout-verification，运行结论以最新记录为准。

使用与反馈筛选命令见[通用协议](../../docs/ui-drag.md)。开发拖动后只有显式导入反馈到该JSON并重建，才更新发布默认；本机保存成功不是已更新默认布局的证明。
