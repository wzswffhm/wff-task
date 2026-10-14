# 48 题 Windows 价值分级（甲方 windows-value.json 口径）

## 高（37 题）

| key | task_id | 甲方评价 |
|---|---|---|
| 001 | `windows-computermanagementdsc-scheduledtask-account-006` | DSC计划任务账号映射、内置服务身份和PowerShell资源契约；Windows价值较高，但Set写入行为缺测削弱验证。 |
| 002.1 | `windows-d4-litemonitor-001` | 注册表原生变更通知、键生命周期与Windows空闲CPU约束；Windows价值高。 |
| 002.2 | `windows-d6-0007` | NTFS文件身份、安全描述符和批发布回滚；Windows价值高。 |
| 002.3 | `windows-d6-001` | NTFS DACL继承、受保护对象、硬链接身份和事务计划；Windows价值高。 |
| 002.5 | `windows-d7-choco-upgrade-libdata-001` | Chocolatey升级、lib数据保留及Windows包部署；Windows生态价值高。 |
| 002.6 | `windows-powershell-ads-001` | Zone.Identifier ADS、文件属性/身份、Windows PowerShell 5.1/7及事务回滚；Windows价值高。 |
| 003 | `windows-file-share-classification-002` | Win32共享打开模式、SharingViolation分类和真实文件句柄；Windows价值高。 |
| 006 | `windows-acl-inheritance-001` | NTFS DACL显式/继承ACE转换与父子继承；Windows价值高。 |
| 007 | `win-reparse-002` | Windows junction/reparse、ADS与文件树复制边界；Windows价值高，若干边界漏测。 |
| 008 | `win-job-005` | Windows进程树/Job Object超时清理；Windows价值高，但当前marker观察不足以证明进程终态。 |
| 010 | `win-hardlink-003` | NTFS硬链接、重解析点与安全删除；Windows价值高。 |
| 011 | `win-acl-004` | DACL、ADS与Windows复制元数据；Windows价值高，当前SDDL比较范围有争议。 |
| 015 | `windows/win-registry-atomic-1.5x` | HKCU类型化写入与事务安全；Windows价值高，回滚主要用前置拒绝代替中途故障。 |
| 016 | `windows/win-file-lock-atomic-1.5x` | Windows文件共享锁、原子替换、UNC与journal；Windows价值高，题面核心边界部分未测。 |
| 017 | `windows-junction-boundary-002` | Windows junction与文件/目录symlink边界；Windows价值高。 |
| 018 | `windows-named-event-003` | Windows跨进程命名Event与句柄生命周期；Windows价值高。 |
| 019 | `win-fs-001` | NTFS ACL/ADS/元数据与真实原子替换观察；Windows价值高。 |
| 020 | `windows-named-mutex-002` | Windows命名Mutex、abandoned状态及跨进程互斥；Windows价值高，但释放验证薄弱。 |
| 021 | `windows-named-pipe-framing-001` | Windows NamedPipe消息分帧与总超时；Windows价值高。 |
| 022 | `windows/win-named-pipe-framed-1.5x` | Windows NamedPipeServerStream、帧协议与清理；Windows价值高，隐藏错误文案要求造成争议扣分。 |
| 023 | `windows/win-global-mutex-lease-1.5x` | Windows全局Mutex、租约与abandoned恢复；Windows价值高，异常夹具未可靠保活。 |
| 024 | `windows-ntfs-ads-003` | NTFS备用数据流、独立正文与其他流保留；Windows价值高。 |
| 025 | `windows-registry-default-value-003` | HKCU默认值、空名、类型与相邻子键保留；Windows价值高。 |
| 026 | `win-dpapi-json-protection` | Windows DPAPI CurrentUser与JSON原子写；Windows价值高，作用域验证不足。 |
| 027 | `windows-powershell-hardlink-targets-20261004` | NTFS硬链接名称枚举、Win32缓冲及错误行为；Windows价值高。 |
| 028 | `win-watchdog-deleted-directory-events` | Win32 ReadDirectoryChanges缓冲、删除事件与取消；Windows价值高。 |
| 030 | `windows-dpapi-user-secret-001` | DPAPI用户作用域原生blob、HKCU/用户隔离与安全文件操作；Windows价值高。 |
| 031 | `windows-file-attributes-003` | Windows文件属性、Hidden/System等位保留；Windows价值高。 |
| 034 | `win-cpython-pathext-executable-lookup` | Windows PATHEXT、路径搜索、注册表启动计划及原生argv；Windows价值高。 |
| 036 | `windows-registry-patch-001` | HKCU原生类型、DWORD/QWORD位模式、DACL注入与原子回滚；Windows价值高。 |
| 037 | `windows-hardlink-isolation-002` | NTFS硬链接写入隔离和替换后FileID；Windows价值高。 |
| 038 | `windows-powershell-process-runner-001` | Windows进程参数、双向管道与超时终止树；Windows价值高，部分断言不足以证明完整输出和清理。 |
| 039 | `windows-registry-dword-001` | HKCU DWORD原生类型与数值；Windows价值高，但后补case削弱测量可信度。 |
| 040 | `windows-subprocess-reader-error-005` | CPython Windows线程式subprocess管道错误、超时重试和异常传播；Windows实现分支价值高。 |
| 041 | `windows-atomic-text-replace-001` | Windows共享打开、原子替换、ACL拒绝和junction边界；Windows价值高。 |
| 042 | `win-filesystem-watcher-events` | FileSystemWatcher事件、资源释放与Windows拒绝路径；Windows价值高。 |
| 043 | `windows-hkcu-env-expand-001` | HKCU环境变量REG_EXPAND_SZ/REG_SZ与未展开原文；Windows价值高。 |

## 中（8 题）

| key | task_id | 甲方评价 |
|---|---|---|
| 002.4 | `windows-d6-002` | DOS/UNC/NT命名空间、卷GUID、Windows大小写与设备路径词法；具平台语义价值，但不是全部依赖原生文件系统操作。 |
| 009 | `windows/goshs-sftp-windows-path-0292-v3` | Windows盘符、反斜杠、大小写及SFTP根路径处理；有平台语义价值。 |
| 012 | `windows/agent-orchestrator-persistent-provider-console-5018-v2` | Windows控制台隐藏、子进程管道及启动标志；有Windows价值，但多项静态token检查不足以测真实行为。 |
| 013 | `windows/momentum-windows-launcher-key-0152-v2` | Windows启动器密钥路径与数据目录行为；Windows生态集成价值中等。 |
| 014 | `windows/momentum-windows-launcher-quote-0171-v2` | Windows启动器命令行参数引号与空格路径；有平台语义价值。 |
| 032 | `windows-file-hardlink-001` | NTFS硬链接共享身份；概念具Windows价值，当前内容/mtime测试无法排除symlink替身。 |
| 033 | `windows-file-timestamps-003` | Windows文件时间戳UTC及元数据保留；有平台价值，但现有容差和输入域检查存在问题。 |
| 035 | `windows-file-utf8-bom-001` | PowerShell及Windows编码/BOM差异；价值取决于完整字节行为，当前正文检查不足。 |

## 低（3 题）

| key | task_id | 甲方评价 |
|---|---|---|
| 004 | `wfflab__wchunk-216` | 纯Python字节容器、CRC与流式解析；Windows专属价值低，详见正文问题。 |
| 005 | `wfflab__wfmt-215` | 纯Python字节容器、CRC与流式解析；Windows专属价值低，详见正文问题。 |
| 029 | `windows-directory-marker-001` | 目录marker创建/删除主要是通用文件操作；Windows专属价值偏低。 |
