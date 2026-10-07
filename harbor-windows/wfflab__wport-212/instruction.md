# wportalloc：端口池分配器的 Windows 绑定语义缺陷

`wportalloc` 是部署在 Windows 服务器上的服务端口池分配器，负责
「探测空闲端口 → 分配给新服务实例 → 对外提供健康探测」。它对外承诺
**探测结果真实、分配出的监听独占、健康探测可信**，但现网反馈
（仓库 issue #212）三件事同时出问题：

1. 明明被存量服务占着的端口，`is_port_free` 却报告「空闲」，分配器把
   端口再发给新服务后，新服务要么启动崩溃（WSAEADDRINUSE），要么和
   存量服务**静默共存**——部分连接被吞到另一个 socket 上；
2. `allocate` 返回的监听可以被后续进程用 `SO_REUSEADDR` 再绑一次
   （Windows 上这是劫持，不是 Unix 式的 TIME_WAIT 重绑）；
3. 运维用 `check_service("localhost", port)` 做健康检查，服务明明活着
   却被报成宕机。

你的任务：修复 `wportalloc` 包，使它满足下文验收标准中的每一条语义。
所有语义都是**本题已声明的契约**，不需要你猜测额外行为。

## 工作区

```
wportalloc/
  errors.py      # WPortAllocError（kind 标记）/ PortInUseError
  probe.py       # is_port_free
  listener.py    # allocate
  health.py      # check_service
tests/
  test_wport_basic.py   # 可见的冒烟测试
```

## 背景事实（Windows 特有，契约的直接依据）

- **`SO_REUSEADDR` 在 Windows 上不是 Unix 语义**。Unix 上它用于
  TIME_WAIT 重绑；Windows 上它允许**第二个 socket 与已有监听共存**
  （只要对端也设置了 `SO_REUSEADDR`），连接投递结果不确定——这是
  劫持面，不是重放面。生产集群里的服务大多是跨平台代码，普遍带着
  Unix 习惯设置了 `SO_REUSEADDR`。
- **`SO_EXCLUSIVEADDRUSE`** 是 Windows 上表达「独占」的正确选项：
  设置后，其他进程的任何绑定（包括 `SO_REUSEADDR` 的）都会失败。
- 本机已实测的绑定错误码：对已监听端口做绑定，失败于
  **WSAEADDRINUSE(10048)** 或 **WSAEACCES(10013)**；绑定到本机不持有
  的地址（如 TEST-NET-3 的 203.0.113.1）失败于
  **WSAEADDRNOTAVAIL(10049)**。
- **`localhost` 在 Windows 上优先解析为 `::1`**（`getaddrinfo` 的
  第一个结果），对仅监听 IPv4 的服务，`::1` 上的连接尝试会**超时**
  （不是立即拒绝）。逐地址回退是唯一可靠的探活方式。
- NTFS/回环上不存在 Unix 式 TIME_WAIT 妨碍：socket 关闭后立即重新
  绑定同一端口是可靠的，探测不得依赖 `SO_REUSEADDR` 来「绕过」
  任何东西。

## 验收标准（全部为已声明契约）

1. **`is_port_free(port, host="127.0.0.1") -> bool`**：用**排他试探
   绑定**探测——试探 socket 必须设置 `SO_EXCLUSIVEADDRUSE` 后
   `bind`：
   - 绑定成功 → `True`，且 socket 必须立即关闭；
   - 绑定失败于 `winerror` ∈ {10048, 10013} → `False`（端口被占，
     无论对端用了什么 socket 选项）；
   - 其他 `OSError`（如 10049）→ 抛 `WPortAllocError(kind="probe")`
     （`port`、`host` 填入实参），不得吞成 `False`。
   - 对「持有 `SO_REUSEADDR` 的存量监听」必须返回 `False`——探测
     结果不得因对端的 socket 选项而失真。

2. **`allocate(port, host="127.0.0.1", backlog=16) -> socket`**：创建
   `AF_INET`/`SOCK_STREAM` 监听 socket：
   - socket 必须设置 `SO_EXCLUSIVEADDRUSE` 后再 `bind`/`listen`，
     返回的监听**不可被第二个 socket 以任何选项再绑**（防劫持）；
   - `bind` 失败于 `winerror` ∈ {10048, 10013} → 抛
     `PortInUseError`（`port`、`host` 填入实参）；
   - 其他 `OSError` 原样向上抛，不得包装。

3. **`check_service(host, port, timeout=1.0) -> bool`**：按
   `getaddrinfo(host, port, type=SOCK_STREAM)` 的**返回顺序**逐个
   地址尝试连接，每个地址的连接超时为 `timeout`：
   - 任一地址连接成功 → `True`（连接 socket 立即关闭，不留泄漏）；
   - `getaddrinfo` 失败（`socket.gaierror`，如主机名不存在）→
     `False`；
   - 全部地址都失败 → `False`。
   - 特别地：`host="localhost"` 时 Windows 先返回 `::1`，对仅监听
     IPv4 的服务必须靠**逐地址回退**探活。

4. **不回归**：空闲端口的探测/分配、分配后 accept 连接、监听关闭后
   端口立刻恢复为「空闲」、对 IPv4 直连地址（127.0.0.1）的正常探活
   ——这些既有行为必须全部保持。

5. **边界**：不得改动公开 API 的签名与模块布局；不得在探测/健康检查
   中留下未关闭的 socket。

## 测试

- 判分只跑 `tests/test_wport_semantics.py`（隐藏测试）。
- 任何一条 required 失败 → 本题 0 分；全部通过 → 1 分。
- 测试在真实 Windows 回环网络上运行，socket 选项用真实 bind 行为校验。
