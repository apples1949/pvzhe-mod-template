# 自定义 C# 项目

默认仍构建 src/HelloMod/HelloMod.csproj，不要求新增配置。只改Mod显示名/ID无需重命名C#项目；确需更换项目目录或程序集名时，在模板根目录增加可提交的 mod-project.json：

```json
{
  "schemaVersion": 1,
  "project": "src/MyMod/MyMod.csproj",
  "assemblyName": "MyMod"
}
```

project是相对模板根目录的实际csproj路径，不能指向仓库外或通过链接越界。assemblyName与项目中的AssemblyName一致，不含.dll；当前配置接受ASCII字母/数字/下划线开头及后续字母/数字/下划线/点/短横线，总长1～128，拒绝宿主同名程序集。配置存在但格式/路径错误时直接失败，不静默回退默认项目。

保持net9.0、Release及默认输出布局 bin/Release/net9.0/<assemblyName>.dll。自定义输出目录、多目标框架、测试配置和多程序集打包不在此配置范围；不能把它当作通用MSBuild参数转发器。项目移动后，检查csproj中 .work/references 的相对引用路径。入口类型发生变化时同步 mod/mod.json 的 runtimeEntryType。

构建命令不变：

```powershell
python tools/mod.py build
if ($LASTEXITCODE -ne 0) { throw '构建失败，停止验收' }
python tools/mod.py check
```

清单和自有资源仍在 mod/，包名仍取Mod ID，包内入口固定 Runtime/ModAssembly.dll。build-info.json记录实际项目和程序集名。配置文件不加入pmod，不改变资源允许名单或身份检查。

FeatureLab、SuperGatling与DragLayout使用各自固定项目，--example不读取该配置。自定义项目选择不等于自定义运行场景：mod.py verify及runtime_test.py的内置CLI仍只提供Hello World/FeatureLab验收；SuperGatling与DragLayout使用各自的verify.py。其他自定义功能按 [验证执行策略](../.agents/skills/pvzhe-mod-verify/references/verification-strategy.md) 定义断言，可复用runtime_test.test的显式自定义采集接口。
