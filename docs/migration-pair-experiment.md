# 两类外部角色迁移实验

2026-10-19。玩家流程只使用用户提供的改版PAK/同包GBK资料与PVZHE 0.30.0发布目录；维护时用内部源码定位问题，再由发布版运行复核。模板src/mod仍是Hello World；本实验项目、图片、DAT及pmod均留在忽略提交的 `.work/migration-examples/`。

## 选择与来源

选取**受伤的向日葵**（生产/恢复）和**僵尸虫子**（低矮快速近战），与此前射击植物不同。核对发布CharacterResource的607项、PCK资源路径及运行时原始/翻译后卡名，未发现这两个名称及对应英文资源身份；原版向日葵和普通僵尸仅作为复用基底。此前狂野机枪案例并非本次“宿主未有内容”的依据。

| 项目 | 受伤的向日葵 | 僵尸虫子 |
| --- | --- | --- |
| GBK名称键 | SUNFLOWERHURT | ZOMBIE_WORM |
| 汉化文件 | NewPlantStrings.txt | NewZombieStrings.txt |
| 动画 | compiled/new/SunFlowerHurt.reanim.compiled | compiled/new/Zombie_worm.reanim.compiled |
| 结构 | 12fps，29帧，14轨，14源图片 | 12fps，54帧，12轨，7源图片 |
| 来源声明 | 初始300/1000；每5秒恢复50；每25秒产出25，满血产出50 | 血量500；非常快；非低矮直线射手不索敌 |
| 宿主复用 | PlantSunFlower、Produce组件及正常卡片种植 | ZombieNormal、GroundMove/Attack/死亡组件、LOW高度 |
| 明确选择 | 费用50、继承冷却7.5秒、受伤/满血图层组绑定 | 只放大根运动X幅度6倍；适配Walk/Eat/Death别名与攻击事件 |

资料文件与PAK同名条目字节一致，严格GBK解码。源改版的产品版本号未独立确认；PAK格式版本0不等于游戏版本。图鉴声明不自动证明原程序实现，费用/速度数值/咬合时序等选择不伪称精确还原。

输入与转换摘要：

```text
PAK:           7a21d1811874ac6800cdca49115bc75b5fb9a1060d6d73142114456d553ccae6
PlantStrings:  cce636b023ead3133b9838327aa579930a85724e052d3fe6e9407cab2776bc66
ZombieStrings: 8399e9071189cbd46bd79cb326e78a6c46e44db6e32642ebb5a288427074dafa
Sunflower src: 77a9576435134880987abfead7deb38bf9ca7c82556576d6e3d34854672e8ad2
Worm src:      b63c12b387eda1d542a8cab04223fbe0c9f3fdbf3a116459fcf5afb0df8007d2
Sunflower DAT: 520764658738fedb9bdff68abdc539e9c298843fb23b1f4d4fc818b3bb73c354
Worm DAT:      5fcf32664809bb24d289dbcc8554d06c313b5e4c380b648cb0315e28aeb1b01b
```

DAT为导出器v2，分别15/8个媒体（各含一个透明控制媒体）。宿主身份见[0.30基线](wiki/0.30.0/overview.md)，Python3.12、Pillow12.3.0、.NET SDK9.0.316。生成只依赖发行DLL，无Godot编辑器、游戏源码项目引用或F3编辑器。

## 可重复准备

按[资料定位](../.agents/skills/pvz-source-identify/SKILL.md)以完整名称查GBK键；按[PAK提取](../.agents/skills/pvz-pak-extract/SKILL.md)从同一PAK提取动画及全部图片依赖。源路径来自本次用户输入，模板不硬编码。

```powershell
$pak = '<用户提供的PAK>'
$properties = '<同版本properties>'
python tools/classic_assets.py --pak $pak research --properties $properties --name '受伤的向日葵' --encoding gbk --out .work/research-sunflower.json
python tools/classic_assets.py --pak $pak research --properties $properties --name '僵尸虫子' --encoding gbk --out .work/research-worm.json
# 核对research候选和原轨道后，分别bundle到本地缓存。
python tools/classic_assets.py --pak $pak bundle --animation 'compiled/new/SunFlowerHurt.reanim.compiled' --out .work/import/sunflower
python tools/classic_assets.py --pak $pak bundle --animation 'compiled/new/Zombie_worm.reanim.compiled' --out .work/import/worm
# sunflower-layer-map.json为UTF-8对象：9→face_hurt_a、10→face_hurt_b、11→face_healthy_a、12→face_healthy_b。
python tools/reanim_dat.py --bundle .work/import/sunflower --layer-map '<映射JSON>' --out .work/import/sunflower-dat
python tools/reanim_dat.py --bundle .work/import/worm --out .work/import/worm-dat
```

每步失败即停，输出绑定源摘要。按[共用复刻方案](../.agents/skills/pvzhe-mod-guide/references/recreation-plan.md)建行为表，再组合plant-create / zombie-create；复用组件、身份发布及入口规则见[内容接入](wiki/0.30.0/content-authoring.md)。不能仅运行转换命令就称角色完成。允许名单只放自己的DLL、两份DAT与自有关卡JSON；不包含原包、宿主DLL、源码和完整资料库。

## 验收与发现

实验Mod为 `local.migration-pair`，独立用户目录，800×450图形模式。正常菜单入口打开自有关卡目录。加载导航用原按钮Pressed信号；植物通过原卡片Plant路径扣费/冷却，普通战斗对象由公开Spawn服务建立对照。分别报告入口与测试生成，不声称系统鼠标种植或人工完整游玩。

| 检查 | 实际结果与边界 |
| --- | --- |
| 提取/转换/加载 | 两个角色依赖完整；DAT能由发行版加载和显示，实际播放对应片段 |
| 正常卡片路径 | 受伤向日葵初始300，费用扣50，冷却启动；卡片API不代表鼠标命中已测 |
| 恢复与自然生产 | 自然从300每5秒增加50到1000；暂停后墙钟约30.674/55.671/80.670秒产出25/25/50，对应约25秒有效周期；实际来源掉落入账9949→9974→9999→10049 |
| 暂停/恢复 | 通过宿主暂停按钮的切换逻辑打开真实菜单，暂停5.2秒期间恢复次数1→1、生产timer 8.433332→8.433332，关闭恢复 |
| 虫子实际移动 | 修复控制媒体后6秒内约307.12逻辑像素；同条件普通僵尸约67.40，且虫子已停在植物前啃食；不是精确源游戏速度标定 |
| 索敌/命中 | 普通豌豆CanTargetHeight=false、实际发射0；低矮射手true、实际发射4并命中4次，每次损失20 |
| 啃食与死亡 | 自主前进后切Eat，坚果4000→3663.33；伤害命令触发death-committed，0.25秒后死亡片段Death1已推进至46帧，保留死亡表现 |
| 上限/回退/清理 | 修复后300→350；夹具将HP设为950，后续多次恢复保持1000；自然24.993秒产50并入账；受伤1000→900后两组图层与产量回退，ImmediateProduct定向产25并入账；销毁5.5秒无恢复/残留状态（立即生产不冒充自然周期） |
| 波次/换局 | 09轮：JSON波次自然生成500HP虫子，2秒前进125.77；正常卡片分别在第1/5行种植，程序化切回菜单后状态清空，新局重新300→350。11轮再经自己的菜单按钮→目录→章节→可见关卡按钮进入，同样通过波次/换局检查；仍为Pressed信号而非系统鼠标 |
| 普通启动 | 12轮最终包无Mod测试参数加载，正常菜单入口可见，未自动进入关卡或执行验收 |

自然长周期轮在最后被**上限断言正确判为失败**：第15次恢复让1000变成1050。25/25/50的实际产物仍有独立证据，但该轮不能统称全通过。修复上限后对受影响条件定向重验，不再次全跑已经通过的虫子对照。

本地证据按轮独立归档：01静止虫子、02控制采样诊断、03透明控制媒体修复、04暂停入口驱动错误、05裁剪方法缺失、06暂停仍恢复、07自然生产/上限失败；后续轮见下方最终摘要。失败记录保留，报告不读取旧截图充作新结果。

## 回写的通用改进

1. 重复层名不自动合并：按源索引显式映射，保留sourceLayers；同一形态可能要两层组合显示。
2. 控制轨不能用65535空媒体占位：宿主会丢弃，改用有效透明媒体并验证运行采样；旧导出器产物需再转换。原始DAT有矩阵、帧号变化和层名存在都不能证明能移动。
3. 全局PhysicsFrame不保证暂停，CanRunAbility不能替代tree.Paused；恢复接口不自动限制最大血量，满血后和再次受伤必须验。
4. 生产检查区分通知、来源实体、面值与入账；池化对象不保证每次Ready。索敌检查区分谓词、实际发射和命中。
5. 发布.NET有裁剪边界，Enumerable.Sum(long)实测MissingMethodException；启动阶段失败应及时退出诊断，不盲等业务超时。

流程规则集中在mod-guide共用复刻方案、reanim-import和zombie-create；版本事实集中在[生产与移动Wiki](wiki/0.30.0/production-and-locomotion.md)，升级Skill同步核对转换版本、位姿、计时和行为边界。未新增一个包揽所有事情的大Skill，也未把案例参数变成通用默认值。

## 未宣称的能力

不宣称精确恢复源程序数值/逐像素插值、所有射手/爆炸的低矮判定、正式图鉴资料导入、联机、关卡中途存读档、全部地图地形、复杂多体BOSS及其他PAK/reanim变种。本地实验包含LowProbe等测试夹具，不是对外发布成品；正式分享仍需确认署名、入口、资源授权与release检查。退出阶段出现宿主冻结扩展点撤销警告与ObjectDB泄漏提示，保留日志，未将其解释为支持热卸载。

默认Hello World已重新构建；工具40项单元测试通过。最终文档链接、Skill格式及普通启动结果见最终摘要，静态检查不替代上表运行结论。

## 最终摘要与产物身份

08轮定向修复上限及形态；09轮只改变关卡波次/说明后验证自然生成与换局；11轮只补充测试分支的可见选关入口验收，行为实现保持08轮版本；12轮验证11轮同包普通启动。各阶段证据按其产物身份使用，不能称一个旧包通过了之后才修改的内容。

```text
最终pmod SHA256: 316bdab1d44fe3b769fa1acedad68a911ebe4f309ed6ac9913bfbad55f218fd2
最终DLL SHA256:  93be36a21571083d77d5da38b1af136beaf307e86a56707b096b7f1e33293fd8
```

最终包仅5项：mod.json、Runtime/ModAssembly.dll、Assets/level.json、Assets/sunflower.dat、Assets/worm.dat。它是本地双例实验，含验收夹具；模板默认包不包含这些内容。实验工程在 `.work/migration-examples/player`，本机日志/PNG/代码与资源快照/identity.json在 `evidence/08-cap-and-state-pass`、`11-visible-level-entry-pass`、`12-final-normal-pass`，仅供本地复核，不随模板分发。

静态收尾：默认Hello World构建成功，src/mod无差异；40项工具测试通过，26个Skill的frontmatter核对通过，本轮4个相关Skill通过官方格式校验，90份Markdown相对文件链接无缺失。首次校验缺PyYAML/默认GBK读取的问题已用本地忽略目录依赖和Python UTF-8模式解决，未增加玩家Hello World依赖。上述静态检查不替代分项运行结果。
