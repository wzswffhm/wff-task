"""wtask —— Windows 计划任务（Task Scheduler）调度语义引擎。

公共 API（名称与签名是冻结契约）：

============================  ==========================================
``parse_task_xml(text)``      解析任务 XML -> ``Task``
``task_to_xml(task)``         ``Task`` -> 规范化 XML 文本
``next_runs(task, after, n)`` ``after`` 之后最近的 n 次运行时刻
``plan_window(task, s, e)``   ``(s, e]`` 内的全部运行时刻
``validate_task(task)``       跨字段一致性校验
``parse_duration(text)``      ISO-8601 时长文本 -> ``timedelta``
``format_duration(td)``       ``timedelta`` -> 规范 ISO-8601 文本
``TaskDefError``              结构化错误（``.kind`` 见 ``errors`` 模块）
``Task`` / ``Trigger`` / ``Repetition``  数据模型
============================  ==========================================
"""

from .duration import format_duration, parse_duration
from .errors import TaskDefError
from .model import MONTH_NAMES, WEEKDAY_BITS, WEEKDAY_NAMES, Repetition, Task, Trigger
from .schedule import HORIZON_DAYS, next_runs, plan_window, validate_task
from .xmlio import NS, SUPPORTED_VERSIONS, parse_task_xml, task_to_xml

__all__ = [
    "TaskDefError",
    "Task",
    "Trigger",
    "Repetition",
    "WEEKDAY_NAMES",
    "MONTH_NAMES",
    "WEEKDAY_BITS",
    "parse_task_xml",
    "task_to_xml",
    "next_runs",
    "plan_window",
    "validate_task",
    "parse_duration",
    "format_duration",
    "SUPPORTED_VERSIONS",
    "NS",
    "HORIZON_DAYS",
]
