# 设置和战斗功能

showKills：bool/default=true/applyMode=immediate/affectsGameplay=false，Get<bool> 读取，TrySave 保存，Changed 刷新界面，作用域清理订阅。bonusSun：int/default=50/min=0/max=500/step=25/applyMode=restart/affectsGameplay=true；必须核对宿主 int 对应的实际运行类型，不擅自将整数视为 double。

新局增量使用 XWModLifecyclePoints.Ready→Game.Economy.Credit。只对新的单人对局发放，Restored 不发放。命令 Accepted/Queued 不等于实际完成；等待返回结果，记录前后余额和增量，异步返回时确认功能仍有效。其他规则优先采用公开服务/扩展点，不直接写全局钱包。
