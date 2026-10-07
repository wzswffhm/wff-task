# winpipe：命名管道服务框架的 Windows 语义缺陷

`winpipe` 是同一台 Windows 主机上进程间通信（IPC）的底座，用命名管道
（named pipe）在「服务端」与「客户端」之间搬运**带边界的分帧消息**。它对外
承诺：连接握手可靠、消息边界不丢不并、错误分类准确。但现网反馈
（仓库 issue #214）报告了三类故障：

1. **握手误判**：只要客户端比服务端先完成打开（在真实高并发场景下很常见），
   `PipeServer.accept()` 就抛「连接失败」，可实际上连接已经建立；
2. **消息粘连/截断**：连续发送的多条消息在接收端被合并成一条，或一条消息被
   拆成两半返回——上层协议解析彻底错位；
3. **错误分类错误**：管道实例被占满时客户端立刻崩溃（而不是按预算等待重试）；
   非法管道名、对端断开也都没有按契约分类。

你的任务：修复 `winpipe` 包，使它的行为满足下文**每一条验收标准**。
所有语义都是本题已声明的契约，**不需要猜测额外行为**。

## 工作区

```
winpipe/
  __init__.py    # 导出 PipeServer / PipeClient / WPipeError / PipeBusyError
  errors.py      # WPipeError(kind=...) / PipeBusyError
  native.py      # kernel32 命名管道 ctypes 薄封装（原样暴露 Win32 结果）
  server.py      # PipeServer
  client.py      # PipeClient
tests/
  test_wpipe_basic.py   # 可见冒烟测试（只覆盖最基础往返）
```

`instruction.md` 末尾的「验收标准」是判分依据。`native.py` 是薄封装层，
它的契约已经正确，**通常不需要修改**（但允许你按需调整实现，只要对外
行为不变）。

## 背景事实（Windows 命名管道，均为本题实测语义）

- **管道名的规范形式**是 `\\.\pipe\<name>`。`\\.\pipe\foo` 与
  `\\.\pipe\FOO` 指向**同一个**管道（名字大小写不敏感）；`\\localhost\pipe\foo`
  与 `\\.\pipe\foo` 等价。名字不以 `\\.\pipe\` 开头时 `CreateNamedPipe`
  失败并置 `ERROR_INVALID_NAME (123)`。
- **客户端可以先连接**：服务端 `CreateNamedPipe` 之后，实例即进入「等待连接」
  状态，客户端 `CreateFile` 会成功。此时服务端调用 `ConnectNamedPipe` 会
  **返回 `FALSE` 且 `GetLastError() == ERROR_PIPE_CONNECTED (535)`——这表示
  连接已经就绪，而不是失败**。只有其它错误码才是真失败。
- **实例用尽时**：客户端 `CreateFile` 失败并置 `ERROR_PIPE_BUSY (231)`。
  正确做法是用 `WaitNamedPipe` 等待，而不是立刻放弃；等待超时后
  `WaitNamedPipe` 失败并置 `ERROR_SEM_TIMEOUT (121)`。
- **创建第 N 个实例（N>1）成功时**，`GetLastError()` 可能仍为
  `ERROR_ALREADY_EXISTS (183)`——句柄是有效的，**不能因为它而判定创建失败**。
- **对端关闭后**服务端 `ReadFile` 失败并置 `ERROR_BROKEN_PIPE (109)`；
  非阻塞（`PIPE_NOWAIT`）管道空读失败并置 `ERROR_NO_DATA (232)`。
- `PeekNamedPipe` 返回管道中可读字节数，且**不消费**数据。

## 验收标准

### A. 消息分帧（wire format）

应用层消息采用**长度前缀分帧**：

```
+----------------+---------------------------+
| 4 字节 LE 长度  |  payload（该长度字节）      |
+----------------+---------------------------+
```

- 长度是 payload 的字节数，小端无符号 32 位整数（`struct.pack("<I", n)`）。
- payload 可以为空（长度为 0），此时帧恰好是 4 个字节。
- 管道以**字节模式**创建（`message_mode=False`，默认值）；不得依赖
  「每条 `WriteFile` 恰好一次 `ReadFile`」这种不可靠假设。
- **一个帧可能跨多次底层读到达，多个帧也可能在一次底层读中一起到达**，
  接收端必须按长度前缀正确拆分与拼装。

### B. `PipeServer`

- `PipeServer(name, instances=1, buffer_size=4096, message_mode=False)`。
- `name` 的校验与规范化在 `create_instance()` 中进行：
  - 接受 `foo` 与 `\\.\pipe\foo` 两种写法，并规范化为 `\\.\pipe\foo`；
  - `name` 为空、含有 `/` 或 `\`（规范形式之外）、或含有码位小于 `0x20`
    的字符时，抛 `WPipeError` 且 `kind == "name"`。
- `create_instance(first_instance=False)`：创建实例，返回句柄。
  第二次起创建同名的后续实例（`instances > 1`）时必须成功——
  **不得因为 `GetLastError() == 183` 而报错**。真正失败时抛
  `WPipeError(kind="connection")`。
- `accept()`：等待并接受一个客户端。
  - 客户端已在 `ConnectNamedPipe` 之前完成连接时（`ERROR_PIPE_CONNECTED`），
    `accept()` 必须**成功返回 `True`**；
  - 其它失败抛 `WPipeError(kind="connection")`。
- `read_frame()`：读取**恰好一条**完整消息并返回其 payload（`bytes`）。
  - 跨底层读到达的半包必须缓冲拼装；一次底层读里的多帧必须能逐条返回；
  - 对端已经关闭（`ERROR_BROKEN_PIPE` / `ERROR_NO_DATA`）时返回 `None`，
    而不是抛异常。
- `write_frame(payload)`：按 A 的格式发送一条消息。
- `read_raw()` / `write_raw(data)`：不分帧的原始读写（保持既有行为）。
- `pending_bytes()`：返回当前可读字节数（不消费）。
- `close()`：断开并关闭实例，**幂等**（重复调用不抛异常）。

### C. `PipeClient`

- `PipeClient(name, timeout_ms=5000, buffer_size=4096)`。
- `connect()`：
  - 打开成功即返回 `True`；
  - 若失败原因是 `ERROR_PIPE_BUSY (231)`，必须在 `timeout_ms` 预算内用
    `WaitNamedPipe` 等待实例释放并重试；预算耗尽后抛 `PipeBusyError`
    （它是 `WPipeError` 的子类，`kind == "busy"`）；
  - 其它失败抛 `WPipeError(kind="connection")`。
- `send(payload)`：按 A 的格式发送一条消息。
- `recv()`：读取一条完整消息并返回 payload（`bytes`）；对端关闭时返回 `None`。
- `send_bytes(data)` / `recv_raw()`：不分帧的原始读写（保持既有行为）。
- `close()`：关闭句柄，**幂等**。

### D. 不得回归

- 原始字节往返（`send_bytes` / `read_raw`、`write_raw` / `recv_raw`）
  的行为保持不变；
- 单条小消息、以及总长超过 `buffer_size` 的消息都必须完整往返；
- `close()` 重复调用不抛异常。

## 提交

直接修改 `winpipe/` 下的源码即可，无需改测试文件。
