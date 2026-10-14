# 修复 Windows 子进程文本捕获的解码异常

## 背景

这个工作区包含一份来自 CPython 3.12 分支的 `Lib/subprocess.py`。在 Windows 上，当 `Popen.communicate()` 为多个管道或带超时时使用后台读取线程时，子进程输出的字节如果不能按调用方指定的编码解码，异常可能只停留在线程里，调用方拿到 `None` 或空结果。这样会把真实的编码错误变成后续代码中难以定位的类型错误。

## 目标

只修改 `environment/workspace/Lib/subprocess.py`，修复 Windows 文本模式管道读取的异常传播，同时保留现有的 `subprocess` 公共行为。

## 必须满足的行为

1. **异常从调用方可见。** `Popen(..., stdout=PIPE, stderr=PIPE, encoding="utf-8").communicate()` 遇到不能解码的 stdout 或 stderr 时，必须在调用 `communicate()` 的线程中抛出原始 `UnicodeDecodeError`，异常的 `encoding`、原始字节对象、起止位置和原因保持准确。
2. **覆盖真实的 Windows 读取路径。** stdout、stderr、`STDOUT` 合并管道、设置 `timeout`、同时存在两条管道，以及一条输出正常而另一条输出非法的场景都必须遵守同一契约。子进程应能正常结束，读取管道和读取线程不得遗留。
3. **超时后可继续 communicate。** 第一次调用因 timeout 返回后，调用方可以结束子进程并再次调用 `communicate()`；此前已读数据只能出现一次，随后发生的解码异常必须仍由调用方收到，管道应在最终完成后关闭。
4. **`run()` 继续遵守公共契约。** `subprocess.run()` 在文本捕获遇到非法字节时不得静默返回 `None`；超时、`check=True`、`input`、`bytes` 模式以及 `errors="replace"`、`"ignore"`、`"backslashreplace"` 等既有行为必须继续有效。
5. **保持兼容性。** 不改变 POSIX 分支、公开参数含义、正常文本的换行转换、空输出、非零退出码和未捕获流的返回约定。实现不能依赖网络、修改测试或读取题包外的答案文件。

## 边界和约束

- 仅允许修改 `environment/workspace/Lib/subprocess.py`；不得修改其他环境、测试、参考解或评分文件。
- 运行环境为 固定 Windows Server Core 2004 容器（amd64、zh-CN）、Python 3.12.14、PowerShell 7.6.5；质检主机为 Windows 10 Pro build 19045；测试以真实 Windows 子进程和匿名管道执行，不使用 WSL 或 Linux mock。
- 任务离线运行。允许使用工作区中现有的标准库源文件，不允许下载上游补丁或答案。
- 代码应可重复执行，异常路径也要关闭自己拥有的句柄和管道；不得以固定等待、日志关键词或源码字符串作为功能替代。

## 运行入口

工作目录为 `C:\task`，目标文件为 `C:\task\environment\workspace\Lib\subprocess.py`。你可自行用 Python 构造真实子进程验证公开契约。平台在 Agent 完成后注入独立测试，并通过 `tests/test.bat` 执行；隐藏测试和参考解不随 Agent 工作区提供。

## 用户可见验收

专家可以看到：含非法 UTF-8 字节的真实 Windows 子进程使 `communicate()` 抛出 `UnicodeDecodeError`；同一个进程在 timeout 后再次 communicate 仍能得到正确异常且不重复输出；合法文本、bytes 模式和显式 errors 处理不受影响；测试结束后没有残留读取线程或子进程。

## 加强模式约束

本题还会验证以下组合场景，不能只修复单次 stdout 解码失败：

- stdout 与 stderr 同时发生不同的解码异常时，必须按两个 reader 线程实际完成读取并记录异常的先后顺序，把最先完成的原始异常交给调用线程；不能按固定的 stdout/stderr 优先级决定，也不得产生 reader thread 未处理异常。
- 第一次 `communicate(timeout=...)` 超时后，第二次及后续调用必须保留已读数据、继续传播原始异常，并在最终完成时关闭两个管道。
- `run(check=True)`、带大块 stdin、`encoding="utf-16-le"` 以及显式 `errors="strict"` 的组合必须保持公共 API 契约。
- 读取线程收到继承自 `BaseException` 的异常时也必须关闭自己拥有的管道，不得通过 `threading.excepthook` 泄漏到线程级未处理异常。
- 不能通过固定等待、重启子进程、源码字符串判断或修改测试来通过加强用例。


新增验收：当 stderr 先关闭并产生非法字节、stdout 延后关闭并产生另一种非法字节时，communicate() 必须抛出 stderr 的原始 UnicodeDecodeError；镜像场景中 stdout 先完成时必须抛出 stdout 异常。若第一次 communicate(timeout=...) 在 stderr reader 完成、stdout 尚未完成时超时，第二次 communicate() 仍必须保留并传播 stderr 的首个异常。

新增验收：后台 reader 的 read() 正常返回但其 close() 抛出 BaseException 时，异常也必须由 communicate() 调用线程收到，且不得触发 threading.excepthook 未处理异常。

重复调用契约：同一个 Popen 对象在 communicate() 已完成并抛出异常后，再次调用 communicate() 仍须抛出此前最先记录的原始异常，不能因第一次抛出而丢失异常记录。此要求也适用于从 timeout 恢复后完成的对象。read() 与 close() 产生的异常均适用公开的异常传播与首次记录顺序规则。
