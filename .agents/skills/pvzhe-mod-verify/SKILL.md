---
name: pvzhe-mod-verify
description: 安装、启用并实际运行验证 PVZHE pmod，收集包摘要、日志与界面证据；适用于 Hello World 验收和发布前检查。
---

# 安装与验证

输入：已构建 pmod、与编译引用匹配的发布游戏、目标 Mod 目录或独立测试副本。输出：安装结果、实际运行日志、包/日志摘要和界面检查结论。

1. 先 build/check。优先执行 `python tools/runtime_test.py`：复制发布 EXE/运行时/PCK，仅在副本修改用户目录并加入测试专用驱动；驱动按已有 StartButton 的可见/启用状态进入主菜单，截图后退出。不改变 Mod 包和宿主 C# 代码。测试数据路径记录在 `.work/runtime/userdata-path.txt`。
2. Windows、未加密独立 PCK v4 才支持此自动测试；必须使用可用图形环境。发布版禁止 `--main-pack`，本机 headless 原生崩溃不能当成 Mod 错误；读取 `.work/runtime/stdout.log` 与退出码区分宿主启动、资源加载及 Mod 错误。
3. 常规安装时退出游戏，用 `python tools/mod.py install --mods-dir '<确认的 user://Mods>'` 复制包。该命令保留不同旧包的摘要备份，不修改启用配置。在游戏 Mod 管理启用并重启。用户目录通常在 APPDATA/Godot/app_userdata/游戏名，不能默认使用 EXE 目录。
4. 使用本次启动日志执行 `python tools/mod.py verify --log '<日志>'`。必须看到 package applied、HELLO_INIT、HELLO_READY、HELLO_UI；检查最后一次初始化后的错误，不能用旧启动标记证明当前构建。核对被安装包与构建包摘要一致。
5. 打开 `dist/hello-world.png` 或观察主菜单，确认文字可见、未阻挡点击。日志成功只证明回调执行；截图/观察用于布局验收。必要时在独立环境再次运行，确认切场景和禁用重启后无残留。

验证输出：`dist/verification.json`、当前日志、图像及简洁实测说明。把编译、静态包检查、真实加载、视觉检查分别报告。若任一环节未完成，应明确未验证项及原因，不生成假成功结论。发布版退出时的冻结扩展点撤销警告属于需要核验的宿主诊断，保留并注明，不一概过滤所有警告。

停止条件：启动超时/崩溃或不兼容时报告日志与退出码，不反复修改原存档或绕过校验；更复杂功能补充专门的游戏行为验证。
