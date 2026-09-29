已完成实现，主要修改：

- 新增 `casbin/trace.py`
  - 定义并导出：
    - `PolicyMatch(ptype, rule, index, effect)`
    - `TraceResult(allowed, matched, decisive, disabled)`
    - `PolicyMutation(op, sec, ptype, rule)`
    - `ChangeImpact(changed, before, after)`
  - 实现决策追踪，按 `enforce_ex()` 的实际求值顺序记录匹配规则，并依据五种效果族正确处理中断规则。
  - 实现一次性沙箱试算，隔离策略与角色管理器；支持普通/域/条件角色管理器，并保留已注册的条件函数。
- 修改 `casbin/core_enforcer.py`
  - 在 `CoreEnforcer` 上新增：
    - `enforce_traced(*rvals)`
    - `would_change(*rvals, mutations=...)`
- 修改 `casbin/__init__.py`
  - 从包顶层导出四个新增公开类型。

实际测试结果：

- `python -m pytest tests/test_enforcer.py -q`：`106 passed`
- `python -m pytest tests/test_management_api.py tests/test_rbac_api.py tests/test_synced_enforcer.py -q`：`119 passed`
- 针对核心相关测试组合运行：`225 passed`
- `python -m compileall casbin`：通过
- 全量测试 `python -m pytest -q`：`374 passed, 1 failed`
  - 唯一失败为 `tests/test_fast_enforcer.py::TestFastEnforcer.test_performance` 的性能倍率断言，属耗时波动；单独运行 `python -m pytest tests/test_fast_enforcer.py -q` 时 `5 passed`。
