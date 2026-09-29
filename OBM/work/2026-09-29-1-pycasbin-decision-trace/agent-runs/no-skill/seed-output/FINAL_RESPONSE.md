已完成实现。

修改内容：
- 新增 `casbin/trace.py`
  - `TraceResult`
  - `MatchedRule`
  - `Mutation`
  - `ChangeResult`
  - 追踪求值、匹配规则、决定性规则、禁用状态。
  - 支持一次性沙箱副本中的策略/角色链接增删试算。
  - 隔离普通角色管理器、域角色管理器和条件角色管理器，并保留已注册条件函数。
- 在 `casbin/__init__.py` 导出新增公开类型。
- 在 `CoreEnforcer` 增加：
  - `enforce_traced(*rvals)`
  - `would_change(*rvals, mutations)`
- 在 `SyncedEnforcer` 增加对应加锁包装方法。
- 小幅修正条件角色模型下删除角色策略时错误访问普通角色管理器的问题；不改变普通非条件模型行为。

实际测试：
- `python -m pytest tests/test_enforcer.py -q`：`106 passed`
- `python -m pytest tests/test_enforcer.py tests/test_management_api.py tests/test_rbac_api.py -q`：`220 passed`
- `python -m pytest -q`：`375 passed`
- `python -m compileall casbin -q`：通过。
