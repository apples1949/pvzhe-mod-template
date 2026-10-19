# 音频键、播放与场景作用域

基线见[0.30摘要](overview.md)，本轮证据见[社区方向实验](../../community-mod-experiments.md)。这里只将分项实测推广到对应条件；自有MP3/OGG导入、所有战斗阶段的音乐切换和真实扬声器听感另验。

## 两层键与公开服务

发行PCK的 `Asset/Config/Audio/AudioResource.json` 将流键关联到资源，例如MainMenu、ZenGarden、ChooseYourSeeds。`Asset/Config/BGM/BGMResource.json` 则是Frontlawn等战斗音乐方案；方案含entry、flag1、drums、win等角色，不是直接播放流名。Frontlawn方案的entry=ChooseYourSeeds、flag1=Grasswalk、drums=GrasswalkDrums；不能把改一个播放流当作完整覆盖全部阶段。

AudioManagerEnum.TYPE的实际成员是MUSIC/SFX；混音总线名本轮为Music。`AudioPlay(stream,type,pos=0,once=true,pauseAlive=false)` 和 `MemberFind(stream,type)` 使用音频流键；AudioPlay的pos为double，但继承Godot AudioStreamPlayer的Play位置为float。先按发布签名区分，不把BGM字样猜成枚举成员。

## 最小场景替换

主菜单展示Hook中建立场景作用域，等待加载完成与原音乐就绪；从AudioManager的MUSIC成员记录原播放器与位置，只停止本次要替换的状态，再播放ZenGarden。设置关闭时，在结果仍由本次替换持有的条件下停止替换并恢复原曲；场景离开释放本作用域，不把主菜单音乐恢复到对局。

SceneManager.ChangeScene默认stopAllAudio=true，切场景可释放原AudioStreamPlayerMember。曾在验收中读取旧引用触发ObjectDisposedException；返回主菜单后重新MemberFind，检查GodotObject.IsInstanceValid，不把同名流的下一次播放当成同一个对象。延迟任务绑定场景代次，不能到下一场景补播。

当前实验覆盖原流、替换流、播放指针推进、设置关闭恢复、进入对局不保留主菜单替换、返回菜单再应用和跨进程设置。具体通过/失败轮以报告为准。它没有解决任意两个音乐Mod争用同一全局流键的所有权；同一批三个独立功能Mod共存成功，也不代表与所有音频Mod兼容。

播放器Playing、有效Stream与播放指针共同证明引擎播放链；不据此声称已经录音或听见扬声器。资源由宿主加载，不把原OGG复制进模板/实验包。
