# wtask 工作区

Windows 计划任务（Task Scheduler）调度语义引擎的纯 Python 子集实现。
它把任务 XML 解析成模型，并计算「接下来什么时候运行」。

```
wtask/
  errors.py     # TaskDefError（kind 标记）
  duration.py   # ISO-8601 时长解析 / 规范化
  model.py      # Task / Trigger / Repetition 数据模型
  schedule.py   # 触发时刻计算（next_runs / plan_window）
  xmlio.py      # 任务 XML 解析与规范化序列化
tests/
  test_wtask_basic.py     # 可见冒烟测试（只覆盖最基础的一条路径）
docs/
  TASKSCHEMA.md           # ★ 权威规格：完整语义都在这里
```

## 运行可见测试

```
python -m pytest tests\test_wtask_basic.py
```

可见冒烟测试只验证「一份最简单的每日任务能被解析并算出运行时刻」，
**它全绿不代表调度语义正确**。

## 权威规格

所有语义（四种日程、重复、边界、时长规范形式、规范化序列化、错误分类）
以 `docs/TASKSCHEMA.md` 为准。下游按该文件验收。

## 注意事项

* 公共 API 的名称与签名是冻结契约，修复时不要改动。
* 不要修改 `tests/` 下的测试文件。
* 判分使用隐藏测试，覆盖 `docs/TASKSCHEMA.md` 的每一节。
