# 内置示例的验证范围

工具支持两种固定示例，不是任意 Mod 的通用场景生成器。先按需求选择自己的验收；参考示例时只取所需功能，不能默认带上三按钮、击杀统计、额外阳光或示例关卡。

| 示例 | 命令 | 证据与边界 |
| --- | --- | --- |
| Hello World | `python tools/runtime_test.py` | dist/verification.json、hello-world.png；.work/runtime/game.log。核对当前 DLL、初始化、ready、标签挂载；不证明按钮交互或战斗功能 |
| FeatureLab | `python tools/runtime_test.py --example feature-lab` | dist/feature-lab/verification.json 和三张截图；.work/runtime-feature-lab/game.log、persistence.log。验证原版提示框、设置、可见选关入口、预设卡槽、阳光、两次真实死亡/HUD与胜利 |

`python tools/mod.py verify --log '<本次日志>'` 对默认示例检查 HELLO_INIT、HELLO_READY、HELLO_UI、package applied 和 DLL 摘要；FeatureLab 加 `--example feature-lab`，使用对应 LAB 标记。输出路径随示例变化，不能拿旧目录中的截图或标记代替当前结果。

FeatureLab 第二进程验证设置重启加载，报告需含 settingsRestartVerified=true。第一进程验证 restart 设置保存后当前值未立刻改变。它没有验证完整战斗读档、全部死亡负例或多人同步。

程序化按钮信号和宿主 Damage 命令用于验证链路；不证明鼠标命中、音效、种植操作、关卡平衡或自然通关。按用户功能补充必要检查，并保持测试行为只在显式测试参数下启用。
