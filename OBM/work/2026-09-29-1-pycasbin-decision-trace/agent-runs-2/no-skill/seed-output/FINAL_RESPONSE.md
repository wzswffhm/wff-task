已完成实现。

修改内容：
- 新增 `casbin/trace.py`
  - `TraceRecord`
  - `TraceResult`
  - `PolicyChange`
  - `enforce_traced`
  - `would_change`
- 在 `CoreEnforcer` 上新增：
  - `enforce_traced(*rvals)`
  - `would_change(*rvals, mutations)`
- 在包顶层 `casbin/__init__.py` 导出新增公开类型和函数。
- 为 `SyncedEnforcer` 增加加锁代理方法，确保同步引擎使用新能力时保持线程安全。
- `would_change` 使用隔离沙箱：
  - 不调用适配器；
  - 不通知 watcher；
  - 隔离策略和角色管理器；
  - 保留条件角色管理器上的链接条件函数和参数；
  - 支持普通策略、角色链接、域角色、多级角色和优先级规则。

实际测试：
- `python -m pytest -q`
  - `375 passed in 10.22s`
- `python -m compileall casbin`
  - 通过。

期间全量测试曾出现一次 `FastEnforcer` 性能测试的瞬时波动，单独重跑通过，随后再次全量测试通过。
