请修复 workspace/candidate.ps1，参数为 -Name、-Action Wait|Signal、-TimeoutMs。使用当前登录会话的 Windows 命名事件：Signal 应创建或打开事件并置为 signaled，返回 Status="signaled"；Wait 在超时内收到信号返回 Status="signaled"，否则返回 Status="timeout"。必须释放句柄，不得终止其他进程，Name 不同的事件不能相互影响。

事件采用手动重置语义；Wait 不消费信号。测试及调用方会在需要跨进程共享期间持有该事件的句柄，事件寿命随最后一个句柄关闭而结束。TimeoutMs 为 0 到 5000 毫秒。

真实环境：Windows Server 2022 x64（20348）、PowerShell 7.5.10、NTFS。只修改工作区 candidate.ps1，保持参数入口；离线运行，不输出额外日志。
