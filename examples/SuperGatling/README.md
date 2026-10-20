# 超级机枪射手案例

案例版本0.1.6沿用0.1.3的动画挂接和动态炮口，接入每轮30发、追踪强度1的扇形编排，按确认的0.1秒间隔在1秒窗口内启动10轮，总共300发、尾部约1.4秒发完。旧0.1.3为300发窄高度平射，历史证据保留；0.1.4曾漏映射攻击间隔，已纠正。本次修改只影响大招，不改普通七连发和10%触发概率。

目标发行：Windows C# **0.30.0 / Godot 4.7.0**。将用户自己的杂交版PAK中的超级机枪射手移植为独立植物，作者沿用原需求指定的“七弦”，ID为`super-gatling-pea`。默认Hello World完全独立。

实现：原版GeneralPlant金色卡池新增卡；血量1000、每轮7枚20伤害豌豆、单行索敌、约2秒一轮；每轮结束10%概率发动大招，其内部每0.1秒启动一轮30发编排。使用原始身体/头部片段及大招片段，不使用网站custom动画。费用250、冷却30秒、原0.1.3的大招炮口Y±4/水平速度300及10批300发是本例适配选择，未声称精确复现源程序。附带“超级机枪体验”主菜单入口及独立预设卡槽关卡，方便检查本体；不替代原版卡池入口。

## 准备和构建

需要根README的Python/.NET及用户自己的目标发行目录；动画转换额外需要Pillow（本次12.3.0）。首次缺少Pillow时安装到自己的Python环境。无需源码、Godot编辑器或F3模组编辑器。

在**模板根目录**执行，将路径换为自己提供的文件：

```powershell
python tools/mod.py prepare --game-dir '<目标发行目录>'
if ($LASTEXITCODE -ne 0) { throw 'prepare失败' }
python examples/SuperGatling/prepare_assets.py --pak '<经典杂交版main.pak>'
if ($LASTEXITCODE -ne 0) { throw '素材准备失败' }
python tools/mod.py build --example super-gatling
if ($LASTEXITCODE -ne 0) { throw '构建失败' }
python tools/mod.py check --example super-gatling
```

输出`dist/super-gatling/super-gatling-pea.pmod`。动画DAT从自己的PAK生成，位于忽略提交的`mod/Assets/animation.dat`；来源、GBK资料、摘要与转换记录在`.work/super-gatling-assets/<PAK摘要>/`。仓库不分发原图、图集或动画。缺少对应素材不会阻止默认Hello World构建；本例需先完成素材准备。来源动作区间不匹配会明确停止，不能无条件套用另一版本动画。

## 安装与使用

按根README确认自己的user://Mods目录，退出游戏后执行：

```powershell
python tools/mod.py install --example super-gatling --mods-dir '<自己的Mods目录>'
```

启用并重启。普通使用在原版选卡金色分类中选择；可用卡数不超过卡槽数时，宿主会自动装卡，不一定出现选卡界面。也可点击主菜单“超级机枪体验”。种植仍需合法落点、足够阳光及冷却就绪。

同ID旧包只能保留一份；若已安装原开发项目的同ID包，先确认是升级并替换，不能并排放两个文件。分享前确认署名/版本、素材分发权限，执行`build/check --release --example super-gatling`及实际验收。GeneralPlant是整资源覆盖，与其他改卡池Mod需核对加载顺序/合并，不保证任意共存。当前案例只承诺单人。

## 可重复验收

```powershell
python examples/SuperGatling/verify.py animation
python examples/SuperGatling/verify.py core
python examples/SuperGatling/verify.py guidance
python examples/SuperGatling/verify.py death
python examples/SuperGatling/verify.py picker
python examples/SuperGatling/verify.py normal
# 只排查原版冒险选关链时：python examples/SuperGatling/verify.py native
```

按顺序执行，上一轮结束后再构建或启动下一轮。仅复核大招间隔/尾部时，可用`python examples/SuperGatling/verify.py cadence`跳过未受影响的普攻选卡链。`animation`采集完整待机/攻击/大招与返回的连续截图，分别检查节点位姿与PNG中的头部位移、断开绑定负例、原始首末帧及完成时序；`core`检查种植/费用/冷却/血量、无同行目标、七连发、300次实际发射、0.1秒轮间隔和约1.4秒延迟尾部与暂停、确认角度/时刻/炮口像素偏移；death单独验证中途死亡取消待发项；`picker`检查少量解锁时自然自动装卡、原版伤害、死亡中断，以及解锁多于槽位后的自然金色选卡和种植，并经原版冒险入口在1-12花盆上种植。后者在**隔离测试用户**中通过宿主接口设置若干关卡完成状态作为前提；不改正式玩家资料，不在生产Mod全解锁。

`normal`检查最终普通包不带Mod测试参数进入体验场景。animation/core/picker/native编译到独立审计程序集，完整测试源码不进入生产DLL；审核输入、包/DLL/发行摘要、完整日志、截图和assessment.json保存于`.work/super-gatling-verification/`。宿主初始化异常立即结束本轮，正常退出但缺结果也判失败。工具判断不替代系统鼠标、自然通关、多人和读档验收。

## 文件职责与边界

verify_animation_frames仅针对本例固定画面做正反例位移判定，其他素材/视角不能直接套用；SpriteRendering在自有实例Ready后应用运行时绘制设置。Entry注册内容、原版卡池覆盖和局部角色生命周期；AnimationData映射原始片段/事件；PowerBurst实现概率和单次编排调度，PowerPattern读取已生成的自有发射数据，PowerGuidance按战斗作用域管理已发弹药，WeakGuidanceMath与编辑器转向响应保持一致；DemoLevel提供独立关卡；prepare_assets只处理用户素材；Verification与verify.py只负责隔离验收。运行事实和本次修复见[案例报告](../../docs/super-gatling-example.md)，通用流程见[卡池Wiki](../../docs/wiki/0.30.0/card-pools.md)。

animation的整体结果见verification-summary.json，运行与图像分项分别在assessment.json和image-assessment.json；两项均通过才算通过。图像探针绑定本例固定镜头、位置及实际800×444 PNG，不适合直接验证任意Mod。

## 继续调整大招

正式设计保存在design/attacks/power.json，当前是6组×5项，每轮30发（复制的重叠组也保留），发射时刻为0/0.25/0.5秒。编辑器确认的0.1秒间隔会真正用于大招内部的轮启动：1秒窗口内启动10轮，原来的0/0.25/0.5秒时差不缩放，各轮重叠，合计300发到约1.4秒结束。原大招触发概率仍为10%，不是每0.1秒重新判一次大招概率。实际出生点仍跟随动画炮口，用户选定像素位置被转换为相对参考炮口的附加位移。

AI先读取pvzhe-attack-preview，按对应Mod/DAT摘要准备透明姿态并载入此方案。确认后将本轮反馈编译成自有运行资源：

```powershell
python examples/SuperGatling/prepare_attack.py --result '<本轮result.json>' --session '<本轮session.json>'
python tools/mod.py build --example super-gatling
python examples/SuperGatling/verify.py core
python examples/SuperGatling/verify.py death
python examples/SuperGatling/verify.py normal
```

prepare_attack是本例的受限适配器：只接入追踪强度0～2、无初始瞄准及行路由/射程限制的直线弹药，验证确认/会话/绑定摘要；不支持的轨迹或触发区域变更会拒绝，不能拿它当成所有攻击方案的通用SDK。运行时不读取Python表达式或本地.work路径。Assets/power-pattern.json随明确允许名单打包；Verification始终排除生产编译。core的具体期望绑定本次每轮30发、0.1秒启动、1秒窗口及延迟尾部编排，后续改方案需同步独立验收期望，不能仅从生成产物读取期望来证明自身正确。

弱追踪专项用`python examples/SuperGatling/verify.py guidance`：独立验证普通弹药不受影响、有限转向和弹速、移动目标、真实伤害、暂停，以及植物死亡只取消待发任务、已发弹药继续运动、退出清理。当前0.1.6选定强度1；0～2的数学映射已对照编辑器，其他强度仍需按需求实测。索敌沿用本体射线，追踪保留已选目标至失效；目标失效且发射者仍存活时重新查询。此实现不宣称所有射线/多目标/跨行角色均可直接复用。
