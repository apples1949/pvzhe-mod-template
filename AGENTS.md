# 本项目工作约定

这是面向玩家的最小 Mod 模板。只以用户提供的已发布 EXE/PCK/运行时目录作为可重复流程输入；不得要求游戏源码或将游戏内容加入模板、产物或版本控制。

开始工作先读 README 与相关 `.agents/skills/*/SKILL.md`。未安装源码、Godot 编辑器不应阻止 Hello World 构建。`.work/` 与 `dist/` 是本地产物。发布更新先重新 prepare，核验接口再修改代码。优先复用宿主生命周期、扩展点及组件。

更改工具后执行 `python -m unittest discover -s tests -v`。更改入口后 build，再做实际游戏验证；日志/包静态检查不能替代运行结论。保持最小允许名单打包，不能把游戏 DLL 或整个 bin 目录放入 pmod。
