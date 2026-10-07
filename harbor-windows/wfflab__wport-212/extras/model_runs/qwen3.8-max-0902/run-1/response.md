## 根因

三处都源于「把 Unix 的 socket 语义照搬到 Windows」：

1. `probe.py` 探测前设置 `SO_REUSEADDR`。Windows 上它不是 TIME_WAIT 重绑，而是允许与已有监听**静默共存** —— 实测：存量监听带 `SO_REUSEADDR` 时，第二个同样带 `SO_REUSEADDR` 的 socket **bind 直接成功**，于是被占端口被报成「空闲」。
2. 同一条 `except OSError: return False` 把所有错误（含 10049 WSAEADDRNOTAVAIL「本机不持有该地址」）都吞成 `False`，配置类故障被伪装成「端口被占」。
3. `listener.py` 也用 `SO_REUSEADDR` 绑定，分配出的监听可被后续进程再绑 → 劫持面。
4. `health.py` 只取 `getaddrinfo(...)[0]`。实测 `localhost` 先返回 `::1`，对仅监听 IPv4 的服务，`::1` 上连接是**超时（1.01s）而非立即拒绝**，活服务被报宕机。

## 修改（仅 `wportalloc/` 下三个实现文件，签名与模块布局不变）

**`probe.py` — `is_port_free`**：改为**排他试探绑定** —— 先 `setsockopt(SOL_SOCKET, SO_EXCLUSIVEADDRUSE, 1)` 再 `bind`，绝不设置 `SO_REUSEADDR`。绑定成功 → `True`；`winerror ∈ {10048, 10013}` → `False`（对端无论用 `SO_REUSEADDR` 还是 `SO_EXCLUSIVEADDRUSE` 都能被真实识别）；其他 `OSError` → 抛 `WPortAllocError("probe", port=..., host=...)` 并 `from exc` 保留原因。`finally` 保证试探 socket 立即关闭。附带：按 host 推断地址族（IPv6 字面量用 `AF_INET6`），默认行为对 IPv4/主机名完全不变。

**`listener.py` — `allocate`**：`AF_INET/SOCK_STREAM`，`bind/listen` 前设置 `SO_EXCLUSIVEADDRUSE`，返回的监听实测无法被第二个 socket 以任何选项再绑（`SO_REUSEADDR` 的尝试失败于 `winerror=10013`）。`winerror ∈ {10048, 10013}` → `PortInUseError(port=..., host=...)`；其他 `OSError` **原样上抛不包装**；任何失败路径都先 `close()`，不留句柄泄漏。

**`health.py` — `check_service`**：按 `getaddrinfo(host, port, type=SOCK_STREAM)` 的**返回顺序逐地址回退**，每个地址各自 `settimeout(timeout)`；任一成功 → `True`（`finally` 立即关闭）；`socket.gaierror` → `False`；全部失败 → `False`。

错误码判定同时看 `winerror` 与 `errno`：实测 Windows 上 `WSAEACCES` 抛出的是 `PermissionError(errno=13, winerror=10013)`（errno 被映射），而 `WSAEADDRINUSE`/`WSAEADDRNOTAVAIL` 的 errno 就是 10048/10049，两者都覆盖才不会误判。

## 验证

在本机 Windows 11 / Python 3.13 真实回环上跑了 29 项一次性断言（脚本已删除，仓库无残留）：`SO_REUSEADDR` 与 `SO_EXCLUSIVEADDRUSE` 两种存量监听下探测均为 `False`；`203.0.113.1` 探测抛 `WPortAllocError(kind="probe", port, host)`；`allocate` 的监听被第二个 `SO_REUSEADDR` socket 绑定时 `winerror=10013`；重复 `allocate` → `PortInUseError`；`allocate` 到不持有地址原样抛 `OSError(10049)`；`check_service("localhost", IPv4-only port)` → `True`（经 `::1` 超时后回退，1.02s）、IPv6-only 服务同样 `True`、不存在主机名 `False`；监听关闭后端口立刻恢复 `True`；accept 往返正常；并用 `gc` 计数确认探测/分配/健康检查三条路径均无 socket 泄漏，用 `setsockopt` 打桩确认探测只设 `-5`（EXCLUSIVE）、从不设 `4`（REUSEADDR）。`tests/test_wport_basic.py` 3 passed。