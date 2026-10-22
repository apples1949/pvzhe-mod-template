# 命名模板与自动恢复

右上输入名称后保存，在工作项目根目录 `.attack-templaates/` 生成 JSON；目录名按约定保留此拼写并参与 Git。名称按 UTF-8 URI 编码，固定 `t-` 前缀避开 Windows 保留名；超长编码用摘要缩短。保存按钮附近气泡显示保存成功和绝对路径，停留6秒后淡出；顶部空间不足时展示在按钮下方。加载模板为一次性菜单，只列出实际模板，保存及加载后均不保留选中状态，可连续加载同一模板。同名每次保存都询问覆盖，加载过同名模板也不例外；覆盖带旧内容摘要，其他窗口更新后需重新确认。

加载只替换当前编辑设计，保留当前角色和会话身份，重新生成图层 ID；不会直接应用到游戏。仅查看会话可加载试调，但不能写项目模板。重置恢复直线单发、豌豆正，清空名称与预览状态，不删除命名模板或正式方案。

页面改动后 400ms 防抖写入 localStorage，保存整个图层树、当前编辑项、选择、折叠、模板名称、目标位置、播放开关和侧栏滚动位置。实时模拟中的弹药和时间不保存，恢复时从零预览。未完成的小数文本不是有效配置，恢复最近有效参数。页面刷新会恢复未采用调整；localStorage 以浏览器 origin 隔离，换端口/浏览器不共享。跨服务或项目长期保存使用命名模板；已有服务器草稿恢复仍通过 `--recover`。正式源方案、角色或游戏基准变动后不复用旧本地草稿。仅查看单独保存，结束查看/采用/取消后清除此会话草稿。存储失败会提示，离页时尝试同步补写。

## 交换契约

文件外壳为 `format: pvzhe.attack-template`、`schemaVersion: 1`，必含 `id/name/createdAt/updatedAt/reference/design/extensions`。

- `design` 是既有 `pvzhe.attack-composition` v2（也可读取受支持的单项 recipe/schema19）。它是可编辑的唯一设计来源，保存所有组、图层及参数，不把编译结果当原始设计。
- `reference` 记录 `presetDllSha256`、坐标与单位：原点为植物根节点的逻辑像素；画面 Y 向下；角度单位度、0°向右顺时针。`speedBaseline=300` 为当前普通豌豆参考逻辑像素/秒，界面射速倍率乘此基准；时间为秒，消失距离以地图格宽换算出弹点至当前位置的直线距离，0不限；不是攻击触发范围。版本变更需重新核验，不能仅改摘要绕过。
- `extensions` 为带命名空间的扩展对象，保存时保留；未来改变必需语义要提升 schemaVersion，不能把未知必需字段静默当成默认值。当前不支持的新版本明确拒绝。

AI 使用模板时先验证 envelope 与匹配的发行基准，再读取 `design`。叶子攻击独立循环；非投掷射速乘祖先倍率，投掷忽略射速倍率；攻击频率倍率相乘后除入叶子 intervalSeconds，祖先与自身 startDelaySeconds 相加作为首次启动延迟。shotDelaySeconds 是同轮相邻弹药间隔，不能误用作每轮额外间隔。树结构/范围经现有 validate_recipe 校验，compile_recipe 编译为 schema5 发射计划。空组可保存，全部为空不能采用。

模板不描述伤害、穿透、爆炸、触发判定、实际弹药资源或游戏代码绑定，这些由 AI 根据用户需求及发行契约实现。加载模板后仍须走当前 session/transaction 的 confirmed → attack_recipe check/export → character-fire 映射、运行验收与 bind；模板保存、localStorage 或手工 JSON 本身均不是玩家采用证据。预览中的追踪映射及投掷运动是有边界的模型，不能冒充所有原版行为。

当前网页编译输出的`distanceModel=host-displacement-grid-width-v1`与`guidance.model=host-guidance-v2`是语义标识。`maxTravelCells`沿用编译字段名，但在此模型下表示宿主消失距离，并非累计路程；传给宿主浮点`fireLength`，不另写距离销毁循环。投掷不输出时间缩放；立即追踪直接交给宿主；延迟追踪显式导出trackingDelaySeconds=0.5，计时到期后调用宿主SetTrackData。

网页编译的`trigger={kind:inherited,selection:inherited-target}`明确继承角色的宿主攻击触发条件，不导出虚构的默认九格单行检测范围。预览中目标存在不等同该目标在游戏内可触发攻击。

首次瞄准的当前导出不含launch.aimFrame：launch.offset保留排列，guidance.initialAim=true；trajectory.direction只表示用户角度偏移。落地逐颗以目标快照减实际出生点得到基础方向，再叠加该偏移。离散枚举0/1/2分别是首次瞄准/延迟追踪/立即追踪；延迟从每颗生成起计时（包含展开），展开完成后才允许启动，不是发射时延或转向强度。历史host-guidance-v1仍表示旧弱转向，不可静默当成延迟追踪。旧含aimFrame的编译文件仍按原含义读取。
