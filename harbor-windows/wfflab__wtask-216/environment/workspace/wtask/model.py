"""wtask.model —— 任务 / 触发器数据模型。

星期与月份在模型里用整数表示，与 Task Scheduler 的位掩码顺序一致：

* 星期：``0=Sunday``、``1=Monday`` … ``6=Saturday``（对应位掩码 0x01 … 0x40）
* 月份：``1=January`` … ``12=December``（对应位掩码 0x01 … 0x800）

触发器 ``type`` 取值：

============  ============================================
type          含义
============  ============================================
time          一次性触发（``<TimeTrigger>``）
daily         ``<ScheduleByDay>``
weekly        ``<ScheduleByWeek>``
monthly       ``<ScheduleByMonth>``
monthly_dow   ``<ScheduleByMonthDayOfWeek>``
============  ============================================
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

#: 星期名，索引即模型里的星期编号（0=Sunday）
WEEKDAY_NAMES = (
    "Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday",
)

#: 月份名，索引 + 1 即模型里的月份编号（1=January）
MONTH_NAMES = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)

#: 星期 -> 位掩码
WEEKDAY_BITS = {i: 1 << i for i in range(7)}


@dataclass(frozen=True)
class Repetition:
    """``<Repetition>``：在每次主出现之后再按固定间隔重复若干次。"""

    interval: timedelta
    #: ``None`` 表示「不限时长」（``<Duration>`` 缺省）
    duration: timedelta | None = None
    stop_at_duration_end: bool = False


@dataclass(frozen=True)
class Trigger:
    """单个触发器。"""

    type: str
    start: datetime
    end: datetime | None = None
    enabled: bool = True
    days_interval: int = 1            # ScheduleByDay
    weeks_interval: int = 1           # ScheduleByWeek
    days_of_week: tuple = ()          # ScheduleByWeek / ScheduleByMonthDayOfWeek
    days_of_month: tuple = ()         # ScheduleByMonth
    weeks_of_month: tuple = ()        # ScheduleByMonthDayOfWeek
    months: tuple = ()                # ScheduleByMonth / ScheduleByMonthDayOfWeek
    repetition: Repetition | None = None


@dataclass(frozen=True)
class Task:
    """一个任务：一组触发器 + 设置。"""

    version: str
    triggers: tuple
    enabled: bool = True
    #: ``None`` 表示不限执行时长（``<ExecutionTimeLimit>PT0S</ExecutionTimeLimit>``）
    execution_time_limit: timedelta | None = None
    multiple_instances: str = "IgnoreNew"
    random_delay: timedelta = timedelta(0)

    def next_runs(self, after, count):
        """``wtask.next_runs(self, after, count)`` 的便捷写法。"""
        from .schedule import next_runs

        return next_runs(self, after, count)

    def plan_window(self, start, end):
        """``wtask.plan_window(self, start, end)`` 的便捷写法。"""
        from .schedule import plan_window

        return plan_window(self, start, end)

    def to_xml(self):
        """``wtask.task_to_xml(self)`` 的便捷写法。"""
        from .xmlio import task_to_xml

        return task_to_xml(self)
