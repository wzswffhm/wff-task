我们要给应用启动器准备一套用户环境配置，但不能在测试时改掉用户真正的 Environment。请完成 candidate.ps1，参数 -ProfileSubKey 和 -ManifestPath。ProfileSubKey 是 HKCU 下 Software\OutsideHarborEnvProfiles\ 后面的独立应用配置键的完整相对路径，例如 Software\OutsideHarborEnvProfiles\App42；不得写真实 HKCU\Environment 或 HKLM。

清单是 UTF-8 JSON：{"version":1,"variables":[{"name":"CACHE_HOME","value":"%USERPROFILE%\\App Cache","expand":true}]}。name 是非空字符串且不含等号或NUL，value是字符串，expand必须是JSON布尔值。逐项存到ProfileSubKey：expand=true写REG_EXPAND_SZ，false写REG_SZ；value是原始文本，即使带%USERPROFILE%也不能提前展开。旧值即使是DWORD等其他类型，也要迁成清单要求的类型。变量名称大小写按注册表习惯比较，不能留下重复项；空值是合法数据。

全部写完后从注册表读取原生kind和不展开的数据，并返回单个对象：Status="synced"、Written=清单项数、Error=""、Variables数组。数组按清单顺序，每项有Name、Kind（ExpandString或String）、RawValue，必须反映实际存储值。重复执行幂等，原来的其他值和子键（包括空子键）保持不变。空variables成功返回Written=0和空数组，原本不存在的配置键仍然不存在。

先校验整个清单。version不是1、variables不是数组、字段类型错误、重复变量名（不区分大小写）或ProfileSubKey不在上述独立命名空间内，都返回Status="rejected"、Written=0、Variables=[]、非空Error。错误时不能留下前几项修改，也不能创建原本不存在的键。ManifestPath可能包含中文、空格和方括号，请按字面处理。

本题离线运行于真实Windows Server2022 x64 build20348、PowerShell7.5.10。工程里的样例展示启动器环境配置原始文本，不需要广播WM_SETTINGCHANGE，也不改变当前进程环境。只修改candidate.ps1与实现模块，不改清单规避验收。
验收也会在已有数据上检查：每次成功返回的 Variables 中每项 Name、Kind、RawValue 和顺序都应与实际注册表一致；键里已有数据时，前项有效而后项错误也不能修改原值、类型或子键。
