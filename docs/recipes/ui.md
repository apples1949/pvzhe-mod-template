# 原版 UI

主菜单按钮：Initialize 订阅 v3 MainMenu；回调接收 Root/Lifetime；用完整 MainButton 场景实例化，设置 text、位置与大小；连接事件并纳入 Lifetime。不要在每帧查找 UI 或直接修改主菜单现有按钮。

提示框：从 DialogManager 创建 DialogBoxTips，再设置 text；本例拒绝在另一个弹窗打开时叠加；关闭使用 CloseDialog。主菜单切场景或 Mod 卸载时的清理必须与宿主清理协调；不能绕过暂停恢复。确认/输入框可按目录的公开事件接入，但需要新增交互验收。
