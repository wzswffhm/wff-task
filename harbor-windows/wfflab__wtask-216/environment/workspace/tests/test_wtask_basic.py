"""可见冒烟测试：只覆盖最基础的一条路径。

注意：本文件全绿**不代表调度语义正确**。完整语义见 docs/TASKSCHEMA.md，
判分使用隐藏测试。
"""

from datetime import datetime

import wtask

DAILY_XML = """<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <Triggers>
    <CalendarTrigger>
      <StartBoundary>2026-01-01T08:00:00</StartBoundary>
      <ScheduleByDay>
        <DaysInterval>1</DaysInterval>
      </ScheduleByDay>
    </CalendarTrigger>
  </Triggers>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <ExecutionTimeLimit>PT2H</ExecutionTimeLimit>
  </Settings>
</Task>
"""


def test_parse_minimal_daily_task():
    task = wtask.parse_task_xml(DAILY_XML)
    assert task.version == "1.2"
    assert len(task.triggers) == 1
    trigger = task.triggers[0]
    assert trigger.type == "daily"
    assert trigger.days_interval == 1
    assert trigger.start == datetime(2026, 1, 1, 8, 0, 0)


def test_daily_task_runs_every_day():
    task = wtask.parse_task_xml(DAILY_XML)
    runs = task.next_runs(datetime(2026, 1, 1, 12, 0, 0), 3)
    assert runs == [
        datetime(2026, 1, 2, 8, 0, 0),
        datetime(2026, 1, 3, 8, 0, 0),
        datetime(2026, 1, 4, 8, 0, 0),
    ]


def test_roundtrip_keeps_the_task():
    task = wtask.parse_task_xml(DAILY_XML)
    again = wtask.parse_task_xml(wtask.task_to_xml(task))
    assert again == task
