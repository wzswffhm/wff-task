# 文件打开失败时要区分共享冲突

请修复工作区里的命令行程序，让它按 Windows 的实际打开结果返回状态。程序从标准输入读一个 JSON 对象，向标准输出写一个 JSON 对象，在 Windows Server 2022/.NET Framework 上运行；不要修改 `build.ps1`。

- R1：请求包含 `path`、`write`、`allowRead`、`allowWrite` 和 `allowDelete`。`write` 为 true 时请求写访问，为 false 时请求读访问。三个 `allow...` 字段分别决定其他句柄是否可以读、写或删除该文件。成功打开时返回 `{"status":"Opened","win32":0}`。
- R2：打开失败时，`win32` 必须是 Windows 返回的原始错误码。错误 32 返回 `SharingViolation`，错误 33 返回 `LockViolation`，错误 2 或 3 返回 `NotFound`，其他错误返回 `Error`。例如，文件或父目录不存在时返回 `NotFound`。
- R3：`allowRead`、`allowWrite` 和 `allowDelete` 各自生效；某一项为 false 时，若已有句柄正在按该项访问文件，新打开请求会因共享冲突失败。不能先换一组共享设置试开，再根据请求伪造结果。
- R4：请求还可以带 `probeRange`，格式为 `{"offset":0,"length":1}`。offset 是非负整数，length 是正整数，且范围不能溢出 64 位；范围无效时返回 `{"status":"Invalid","win32":87}`。有效范围要检查能否临时独占锁定后立即释放，不读写文件内容。若其他进程已锁住与之重叠的字节范围，返回 `LockViolation` 和错误码 33；若未冲突，仍返回 `Opened` 和错误码 0。

通过 stdin/stdout 使用 JSON，正常处理有效请求时进程退出码为 0。JSON 无法解析时返回 `ProtocolError`，退出码为 2。保留现有构建入口。
