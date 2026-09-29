已完成实现。

修改内容：
- 新增 `casbin/trace.py`
  - 定义并实现 `TracedRule`、`TraceResult`、`Mutation`、`ChangeResult`
  - 实现决策追踪 `enforce_traced`
  - 实现一次性沙箱影响分析 `would_change`
  - 支持五类效果、优先级、多级角色、域、条件角色管理器、`EnforceContext`、禁用状态
  - 沙箱内克隆独立角色图，并保留条件函数，不持久化、不通知 watcher
- 在 `casbin/__init__.py` 顶层导出四个公开类型
- 在 `CoreEnforcer` 上挂载：
  - `enforce_traced`
  - `would_change`
- 为 `SyncedEnforcer` 包装层补充同名加锁入口，确保该具体子类也可直接使用
- 未修改 `enforce()`、`enforce_ex()` 或既有管理接口行为

实际测试结果：
- `python -m pytest tests/test_enforcer.py tests/test_management_api.py tests/test_rbac_api.py tests/test_synced_enforcer.py -q`
  - `225 passed`
- `python -m pytest -q`
  - `375 passed`
- 编译检查：
  - `python -m py_compile casbin/trace.py casbin/core_enforcer.py casbin/synced_enforcer.py casbin/__init__.py`
  - 通过。
