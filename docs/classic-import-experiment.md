# 经典素材导入实验

2026-10-18。目标：把玩家给出的中文名称转换为可追溯的资料与动画输入，并在已发布的 PVZHE 0.30.0 中验证原始分段播放。模板默认 Hello World 不添加本实验功能。

新增入口各负其责：

- [source-identify](../.agents/skills/pvz-source-identify/SKILL.md)：中文名、GBK汉化、图鉴和属性声明定位。
- [pak-extract](../.agents/skills/pvz-pak-extract/SKILL.md)：独立于PCK的PAK索引、按需提取与图片依赖。
- [reanim-import](../.agents/skills/pvzhe-reanim-import/SKILL.md)：原始时间轴转换与行为绑定指导。

角色注册/入口仍由 plant-create / zombie-create 负责，射击由 character-fire 负责，不把这些步骤复制进新Skill。现有guide、skin、plant及版本升级导航已同步。

## 可重复命令

输入路径来自玩家；下面变量填写自己合法持有的源素材位置。仅动画图片转换需要 Pillow，本次为12.3.0；核心Hello World依赖不变。

```powershell
$pak = '<用户提供的main.pak完整路径>'
$properties = '<同版本properties目录；也可以先从PAK提取>'
python tools/classic_assets.py --pak $pak index --out .work/classic-cache/index.json
$pakHash = (Get-Content .work/classic-cache/index.json -Raw | ConvertFrom-Json).pakSha256
$cache = ".work/classic-cache/$pakHash"
python tools/classic_assets.py --pak $pak research --properties $properties --name '狂野机枪射手' --encoding gbk --out "$cache/research.json"
# 从research和索引中核对候选后再执行，不把示例路径当作任意角色的规则。
python tools/classic_assets.py --pak $pak bundle --animation 'compiled/new/WildPea.reanim.compiled' --out "$cache/wildpea"
python -m pip install Pillow==12.3.0
python tools/reanim_dat.py --bundle "$cache/wildpea" --out "$cache/generated"
```

每步检查退出码及产物，失败不继续使用旧包。转换只输出动画数据；如何接入精灵、独立部件、发射及卡片见新Skill的绑定参考。图片/原包/完整图鉴留在忽略提交的缓存，不能随模板发布。

## 这次找到的内容

| 项目 | 本次结果 |
| --- | --- |
| 名称定位 | `NewPlantStrings.txt` 按GBK严格解码，完整名称值命中 `WILDPEA`，不是正文提及或同系僵尸 |
| 资料版本 | 外部文件与PAK内同名文件字节一致；源改版的发行版本号未独立确认，PAK格式版本0不等于游戏版本 |
| 动画候选 | `compiled/new/WildPea.reanim.compiled`；键与文件stem一致，再核对实际轨道与外观 |
| 图鉴声明 | 威力 `20×4×5/2秒`，范围前方三行；另有说明与趣味文案，保留在本地研究JSON |
| 待确定玩法 | 费用、冷却、随机散射角度、连发子间隔、具体出膛帧与特殊判定；不能从这一段文案/动画自动得到 |
| 动画结构 | 12fps、93帧、25条轨道、20张依赖图片；包含普通豌豆和机枪射手共享图片、调色板PNG及大尺寸披风PNG |
| 原始片段 | anim_idle `[4,29)`；anim_head_idle `[29,54)`；anim_shooting `[54,93)`；另保留anim_blink、anim_face等候选 |

`anim_face` 自身有图片，说明 anim_ 前缀不保证是独立的业务动作。身体与头部使用同一数据、不同播放实例和片段，未生成 custom_idle/custom_shoot。本轮v1保留了隐藏层的原始DAT变换，但未验证宿主加载后的控制轨采样；后续虫子实测发现空媒体会被宿主丢弃，已在导出器v2修复，见[后续实验](migration-pair-experiment.md)。本页历史DAT/包摘要仍对应v1，不因修复而改写成已验证的v2产物。

本次输入身份：

```text
PAK SHA256:       7a21d1811874ac6800cdca49115bc75b5fb9a1060d6d73142114456d553ccae6
汉化文件 SHA256:  cce636b023ead3133b9838327aa579930a85724e052d3fe6e9407cab2776bc66
源动画 SHA256:    e57879afcfc4b7810953455e40c27908b5e63484043d25bf28048f7b91423cae
最终DAT SHA256:   0adef231d2ef00f33833e44fed2e7faa813e07ebd947a884c84d2a1d3339e1cf
```

宿主身份见 [0.30基线](wiki/0.30.0/overview.md)。本地原始证据在 `.work/classic-experiment/`；不把机器上的源文件路径写进Skill或转换工具。

## 发行版实验结论

隔离工程位于 `.work/classic-experiment/player`，编译只使用发行版DLL；以 `local.wildpea-lab` 生成实验pmod，由独立用户目录加载。包只含自己的DLL和从用户素材生成的DAT；不进入玩家正常Mods目录，不修改源码工程。测试驱动通过原加载按钮的Pressed信号导航，不声称完成真实鼠标命中。

通过部分：PAK按需提取、GBK精确定位与同包比对、图片依赖完整、DAT读取、媒体/层/帧数量、身体/头部独立推进、可见待机帧变化与切换原始射击片段。实际窗口800×450，参考UI画布1080×600；最后使用默认渲染路径，未启用forceLocalRender/forceCpuPoseRender。

曾出现的空白画面不能算通过：首次用户名弹窗遮挡、实验底板与精灵绘制层级不同分别处理。可读图集和帧推进不足以证明可见；渲染后端切换未解决，调整实验精灵相对底板的层级后显示，最终又用默认后端复核。层级结论限于该预览容器，不推广成所有战斗控件强制升层。

本地记录分别保存失败/诊断轮与最终轮：`evidence/07-final` 绑定包/DLL/DAT身份、夹具与截图，`evidence/08-normal` 记录同包无Mod测试参数的启动，菜单实验入口可见，动画测试未自动执行。最终包SHA256为 `b60eb6ea3b96e0fcd5d3dc6ceec4b7a3a4c5e4491fbc07d4f173c74286a27933`。宿主退出时会记录扩展点撤销需重启的警告；它发生在实验结束清理阶段，未声称支持热卸载。

39项单元测试通过，新增3个Skill格式校验及84份Markdown链接检查通过。新增工具测试覆盖严格GBK、PAK字节/XOR、路径边界、继承零值、末轨字符串、缺图片、DAT落盘独立回读及输入篡改；这些不能代替游戏表现验证。

**未完成/未宣称**：完整可种植狂野机枪植物、三行散射/伤害与时序还原、身体挂点的运动跟随、眨眼调度、正式卡片与图鉴接入、连续帧逐像素等价、其他reanim/PAK变种。本轮验证的是“资料→提取→转换→发行版可见分段动画”这条输入管线，不把借用外观的局部实验称为完整角色移植。

结构事实与后续接入入口集中在 [动画导入Wiki](wiki/0.30.0/animation-import.md)；不把单个角色全部数值写成通用Skill要求。
