已完成实现。

修改内容：
- 新增 `casbin/trace.py`
  - `TracedRule`
  - `EnforcementTrace`
  - `Mutation`
  - `ChangeAnalysis`
  - 实现决策追踪与一次性沙箱变更分析。
- 在 `casbin/__init__.py` 顶层导出上述四个公开类型。
- 在 `CoreEnforcer` 上新增：
  - `enforce_traced(*rvals)`
  - `would_change(*rvals, mutations)`
- 追踪逻辑复刻 `enforce_ex` 的求值顺序和不同 effect 家族的中断规则。
- 沙箱中独立复制模型和角色图，同时保留条件角色管理器中的条件函数，不调用适配器、不保存、不通知 watcher。

实际测试结果：
- `python -m compileall casbin`：通过
- `pytest -q tests/test_enforcer.py`：`106 passed`
- `pytest -q`：`375 passed`

另外手动验证了：
- 空 mutation 序列；
- 多级角色继承删除链接；
- domain 角色隔离；
- conditional role manager；
- `EnforceContext` 场景；
- 调用后原引擎策略和角色关系未被污染。
