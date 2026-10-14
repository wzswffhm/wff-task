我们有个 Windows 用户级工具，需要把少量访问口令保存在本机，现有脚本会把它们直接写成明文。请补好 candidate.ps1 的 Set/Get/Remove 入口，使用当前用户的 Windows DPAPI，保留已有调用约定。

参数是 -Action Set|Get|Remove、-StoreRoot、-Name，以及 Set 时使用的 -Value。StoreRoot 是调用者专用、已经存在的普通本地 NTFS 目录；这里只操作这个目录，不使用个人配置目录、共享目录、注册表或其他数据。每次验收都会传入新的隔离目录。Name 是非空字符串，可包含中文、空格、方括号、斜杠和点号；它是名字，不是文件路径。名字区分大小写，不同名字不能覆盖。Value 是字符串，包括空字符串、中文及换行。

Set 返回一个对象 Status="stored"，同名覆盖；Get 找到时返回 Status="found"、Value 为原字符串，不存在时返回 Status="missing"；Remove 删除已有名字返回 Status="removed"，已不存在返回 Status="missing"。正常调用只输出这一条对象，不输出日志。移除一个名字不能删除其他秘密。不同 StoreRoot 的数据隔离。调用串行执行，不要求并发事务或权限错误处理。

每条秘密在 StoreRoot 中使用一个文件持久化；文件内容就是 DPAPI CurrentUser 保护后的二进制 blob，额外熵使用固定 UTF8 字节串 `OutsideHarbor.SecretStore.v1`。不要给 blob 外包 JSON、Base64 或明文头。文件名由实现选择，但名字到文件的对应应确定、互不冲突。文件路径不能逃出 StoreRoot。目录可以包含别的用户文件，它们的字节不能改变。磁盘上不能写出 Value 的明文或明文临时文件。

Get 遇到损坏的秘密文件时返回 Status="corrupt"、不包含 Value；不能把损坏文件当不存在，不能修改损坏文件或影响其他秘密。Set 只覆盖自己的文件，Remove 只删除自己的文件。验收会用独立 Windows DPAPI 解密器检查原生 blob 和额外熵，而不仅仅检查脚本能自读自写。

只修改 candidate.ps1。环境为 Windows Server 2022 x64 build20348、PowerShell7.5.10、zh-CN、NTFS，离线运行，使用当前Windows登录用户。
