请修复 workspace/candidate.ps1 的单实例入口，参数 -Name、-HoldMs、-TimeoutMs。Name 是同一登录会话里的 Windows 命名 mutex 名称，各进程使用完全相同的 Name。获得互斥锁后等待 HoldMs 毫秒，释放锁，返回 Status="entered"；在 TimeoutMs 内未获得锁则返回 Status="busy"。已有持锁进程退出留下 abandoned mutex 时，下一次调用仍应进入并正常释放。不同名字不能相互阻塞，不能终止其他进程。HoldMs 和 TimeoutMs 为 0 到 2000 的整数。调用结束不得残留自己持有的锁。

运行环境是 Windows Server 2022 x64（20348）、PowerShell 7.5.10 和 NTFS，本题离线运行。只修改 workspace/candidate.ps1，保持上述参数入口，不输出额外日志。
