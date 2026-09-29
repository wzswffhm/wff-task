已完成实现。

修改内容：
- 新增 `casbin/trace.py`：
  - 定义并实现不可变类型：
    - `PolicyMatch(ptype, rule, index, effect)`
    - `TraceResult(allowed, matched, decisive, disabled)`
    - `PolicyMutation(op, sec, ptype, rule)`
    - `ChangeImpact(changed, before, after)`
  - 实现决策追踪逻辑，保持与 `enforce_ex()` 相同的求值、异常和效果中断语义。
  - 实现一次性沙箱试算，独立复制模型和角色管理器/条件角色管理器，避免污染真实引擎，同时保留条件函数。
- 在 `casbin/__init__.py` 顶层导出四个公开类型。
- 在 `CoreEnforcer` 上新增：
  - `enforce_traced(*rvals)`
  - `would_change(*rvals, mutations)`
- 为 `SyncedEnforcer` 增加对应加锁转发方法。

实际测试结果：
- `python -m compileall casbin`：通过
- 重点相关测试：
  - `284 passed in 7.05s`
- 全量测试：
  - `375 passed in 8.65s`
