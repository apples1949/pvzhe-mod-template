# 功能制作路由

按玩家意图选择入口，不要求玩家报Skill名称。多个独立能力按需组合，但不默认把示例功能都加进去。

| 需求 | 入口 | 边界/组合 |
| --- | --- | --- |
| 按钮/提示/弹窗 | pvzhe-ui-create | 浮动控件组合ui-drag；快捷键另用input-bindings，旧外部位置预览已弃用 |
| 对局信息/统计 | pvzhe-battle-hud | 设置开关组合mod-settings |
| 背景音乐、音效、局部音量 | pvzhe-audio-edit | 区分流键/战斗音乐方案/场景作用域；设置或选择界面按需组合 |
| 设置持久化/热更新 | pvzhe-mod-settings | 不为配置新造完整界面 |
| 在游戏里调整控件位置、发布后继续拖动 | pvzhe-ui-drag | 中键拖动、始终右锚定；按Mod/会话/控件筛选反馈，显式更新项目默认值 |
| 简单对局规则、奖励/控制效果 | pvzhe-gameplay-feature | 新角色基础不是临时规则 |
| 新模式入口、点进去的新页面、页面嵌套/返回 | pvzhe-mode-create | 先区分导航和玩法；特殊规则组合gameplay-feature，章节/关卡组合level-create |
| 新章节、追加关卡、用原版地图做波次/关卡 | pvzhe-level-create | 章节组织见其references/chapters；新网格/地形/背景走map-create |
| 已有资源的伤害、费用、血量等 | pvzhe-resource-edit | 短时局部规则可能组合gameplay-feature；不默认新建角色 |
| 独立新子弹/投射物及命中效果 | pvzhe-projectile-create | 发射节奏走character-fire；修改原子弹字段走resource-edit |
| 新植物 | pvzhe-plant-create | 负责身份/骨架/种植入口；发射/外观按需组合 |
| 新僵尸/复刻其他版本僵尸 | pvzhe-zombie-create | 统筹身份/出现入口与行为依据；复刻组合pvz资料/PAK与reanim导入，护具/发射按需组合 |
| 射速、散射、连射或生成点 | pvzhe-character-fire | 新角色由相应create先建立骨架；单数值差量可由resource-edit完成 |
| 明确要自己在预览里自定义弹道/攻击方式 | pvzhe-attack-editor | 仅此明确意图触发；持续等待确认/取消，随后由character-fire落地，普通报错/不满意不自动打开 |
| 护具、耐久、破甲行为 | pvzhe-character-armor | 本体血量不等于护具；不负责整套BOSS |
| 换肤、动作、换头/部件对齐 | pvzhe-character-skin | 未要求新外观时优先复用宿主；不自动生成美术 |
| 复刻经典PvZ/其他改版已有植物 | pvzhe-plant-recreate | 统筹行为依据、缺项、合理近似与完整验收；组合pvz资料/PAK与PVZHE制作，不在动画阶段结束 |
| 识别经典PvZ/其他改版角色资料与素材 | pvz-source-identify | 与目标引擎无关；需要PAK时用pvz-pak-extract；PVZHE外观接入再用reanim-import |
| 地图背景、行列、道路/地形 | pvzhe-map-create | 验证用关卡由level-create组合 |
| 快捷键、改键、触摸触发 | pvzhe-input-bindings | 业务命令已有或单独实现；持久化组合mod-settings |
| 只有pmod、调已有文本字段 | pvzhe-pmod-patch | 源项目存在优先回改源码；不恢复DLL源码 |
| 构建/发行分析/运行验收 | 原release-analyze、mod-develop、mod-verify | 普通功能不自动触发template-upgrade |

新增社区提取入口是可使用的制作指导，不是已验证的通用生成器。先匹配当前发行、调查本任务契约再实现；有证据缺口标出具体缺项，不因旧“暂缓”提示直接拒绝，也不无条件承诺全部角色/模式支持。实际生成能力和游戏结果由后续构建/运行证据确认。
