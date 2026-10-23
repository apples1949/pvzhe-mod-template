---
name: pvzhe-project-update
description: 使用者明确要将已有Mod项目同步到官方模板新版时，获取差异、保护自己的功能与身份，并核对本地游戏是否仍兼容；不负责维护者研究新版游戏并适配模板。
---

# 更新已有项目的模板

输入：玩家Mod项目、目标官方模板分支/提交（缺省main）、本地游戏环境。输出：保留玩家功能的更新、兼容判断、验证记录和template.lock.json。只在明确更新/同步模板时使用，普通开发不自动升级。

1. 先读README、Wiki索引与[环境和升级规则](../../../docs/game-environment.md)。检查Git状态、模板来源、Mod身份和已有功能；记录原HEAD与本地改动。此流程只使用发行版，不询问游戏源码。
2. 执行`python tools/project_update.py plan --ref '<目标ref>'`。工具从已记录的官方来源fetch，在.work/template-updates生成上游文件、差异、本地补丁及未跟踪文件备份，不替换origin、不修改玩家源码。读取plan.json的base/target/overlaps与environment。revision为空可从共同祖先推导；无可靠基线时先补来源，不用当前用户HEAD冒充原模板提交。
3. 逐项审查差异后合并工具、文档、Skills与必要项目配置；有交集时做三方比较，保留用户的代码、资源、Mod名称/作者/ID、设置和攻击设计，不把Hello World重新覆盖回用户项目。保留本地template.lock来源，验收后由record更新，不用上游空revision覆盖。上游删除不等于允许删除用户扩展；不使用reset --hard/clean清场，不直接用git pull合并整套模板。详见环境文档中的分工。
4. 核对新game-compatibility.json与.game/current。匹配则`python tools/mod.py prepare`复用原环境；不匹配先停止构建/运行，询问受支持发行目录或选择兼容现有游戏的模板提交。不得改摘要伪装兼容，也不得转而触发维护者整套适配。更换环境只保留current与old，运行中不轮换。
5. 按实际差异执行工具测试、构建与受影响的Mod功能验收，最终包普通启动；保留失败证据。通过后执行`python tools/project_update.py record --plan '<本轮plan.json>'`记录来源。record只是来源登记，不是验收。报告合并项、玩家改动的保留情况、游戏是否复用及未验范围；不因更新自动提交、推送或发布。

维护者要让模板支持尚未支持的新游戏版本，使用[pvzhe-template-upgrade](../pvzhe-template-upgrade/SKILL.md)；该Skill不能替代使用者项目更新，也不能覆盖本项目业务。
