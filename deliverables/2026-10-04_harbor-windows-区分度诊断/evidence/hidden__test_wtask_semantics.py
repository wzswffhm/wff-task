"""隐藏语义测试：逐条覆盖 docs/TASKSCHEMA.md 的契约。"""

from datetime import datetime, timedelta

import pytest

import wtask

HEAD = '<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">'


def _task(body, settings=""):
    return wtask.parse_task_xml(
        HEAD + "<Triggers>" + body + "</Triggers>" + settings + "</Task>"
    )


DAILY_3 = """
<CalendarTrigger>
  <StartBoundary>2026-01-01T08:00:00</StartBoundary>
  <ScheduleByDay><DaysInterval>3</DaysInterval></ScheduleByDay>
</CalendarTrigger>
"""


# --------------------------------------------------------------- FAIL_TO_PASS


def test_daily_interval_anchored_at_start_boundary():
    task = _task(DAILY_3)
    runs = wtask.next_runs(task, datetime(2026, 1, 2, 0, 0, 0), 3)
    assert runs == [
        datetime(2026, 1, 4, 8, 0, 0),
        datetime(2026, 1, 7, 8, 0, 0),
        datetime(2026, 1, 10, 8, 0, 0),
    ]


def test_weekly_honours_weeks_interval():
    task = _task(
        """
<CalendarTrigger>
  <StartBoundary>2026-01-05T09:00:00</StartBoundary>
  <ScheduleByWeek>
    <DaysOfWeek><Monday/></DaysOfWeek>
    <WeeksInterval>2</WeeksInterval>
  </ScheduleByWeek>
</CalendarTrigger>
"""
    )
    runs = wtask.next_runs(task, datetime(2026, 1, 5, 10, 0, 0), 3)
    assert runs == [
        datetime(2026, 1, 19, 9, 0, 0),
        datetime(2026, 2, 2, 9, 0, 0),
        datetime(2026, 2, 16, 9, 0, 0),
    ]


def test_monthly_restricted_to_listed_months():
    task = _task(
        """
<CalendarTrigger>
  <StartBoundary>2026-01-15T06:00:00</StartBoundary>
  <ScheduleByMonth>
    <DaysOfMonth><Day>15</Day></DaysOfMonth>
    <Months><January/><July/></Months>
  </ScheduleByMonth>
</CalendarTrigger>
"""
    )
    runs = wtask.next_runs(task, datetime(2026, 1, 20, 0, 0, 0), 3)
    assert runs == [
        datetime(2026, 7, 15, 6, 0, 0),
        datetime(2027, 1, 15, 6, 0, 0),
        datetime(2027, 7, 15, 6, 0, 0),
    ]


def test_monthly_day_of_week_week_five_means_last_week():
    task = _task(
        """
<CalendarTrigger>
  <StartBoundary>2026-01-01T12:00:00</StartBoundary>
  <ScheduleByMonthDayOfWeek>
    <Weeks><Week>5</Week></Weeks>
    <DaysOfWeek><Friday/></DaysOfWeek>
    <Months><February/></Months>
  </ScheduleByMonthDayOfWeek>
</CalendarTrigger>
"""
    )
    runs = wtask.next_runs(task, datetime(2026, 2, 1, 0, 0, 0), 2)
    assert runs == [
        datetime(2026, 2, 27, 12, 0, 0),
        datetime(2027, 2, 26, 12, 0, 0),
    ]


def test_repetition_stops_before_duration():
    task = _task(
        """
<CalendarTrigger>
  <StartBoundary>2026-01-01T08:00:00</StartBoundary>
  <ScheduleByDay><DaysInterval>1</DaysInterval></ScheduleByDay>
  <Repetition>
    <Interval>PT30M</Interval>
    <Duration>PT1H</Duration>
  </Repetition>
</CalendarTrigger>
"""
    )
    runs = wtask.next_runs(task, datetime(2026, 1, 1, 0, 0, 0), 4)
    assert runs == [
        datetime(2026, 1, 1, 8, 0, 0),
        datetime(2026, 1, 1, 8, 30, 0),
        datetime(2026, 1, 2, 8, 0, 0),
        datetime(2026, 1, 2, 8, 30, 0),
    ]


def test_repetition_respects_end_boundary():
    task = _task(
        """
<CalendarTrigger>
  <StartBoundary>2026-01-01T08:00:00</StartBoundary>
  <EndBoundary>2026-01-01T10:00:00</EndBoundary>
  <ScheduleByDay><DaysInterval>1</DaysInterval></ScheduleByDay>
  <Repetition>
    <Interval>PT1H</Interval>
    <Duration>PT4H</Duration>
  </Repetition>
</CalendarTrigger>
"""
    )
    runs = wtask.next_runs(task, datetime(2026, 1, 1, 0, 0, 0), 5)
    assert runs == [
        datetime(2026, 1, 1, 8, 0, 0),
        datetime(2026, 1, 1, 9, 0, 0),
        datetime(2026, 1, 1, 10, 0, 0),
    ]


def test_disabled_trigger_is_skipped():
    task = _task(
        """
<CalendarTrigger>
  <StartBoundary>2026-01-01T08:00:00</StartBoundary>
  <ScheduleByDay><DaysInterval>1</DaysInterval></ScheduleByDay>
</CalendarTrigger>
<CalendarTrigger>
  <StartBoundary>2026-01-01T09:00:00</StartBoundary>
  <Enabled>false</Enabled>
  <ScheduleByDay><DaysInterval>1</DaysInterval></ScheduleByDay>
</CalendarTrigger>
"""
    )
    runs = wtask.next_runs(task, datetime(2026, 1, 1, 0, 0, 0), 3)
    assert runs == [
        datetime(2026, 1, 1, 8, 0, 0),
        datetime(2026, 1, 2, 8, 0, 0),
        datetime(2026, 1, 3, 8, 0, 0),
    ]


def test_duration_canonical_form():
    assert wtask.format_duration(timedelta(0)) == "PT0S"
    assert wtask.format_duration(timedelta(hours=2)) == "PT2H"
    assert wtask.format_duration(timedelta(minutes=90)) == "PT1H30M"
    assert wtask.format_duration(timedelta(hours=72)) == "P3D"
    assert wtask.format_duration(timedelta(days=1, hours=2)) == "P1DT2H"
    assert wtask.parse_duration("P1DT2H3M4S") == timedelta(days=1, hours=2, minutes=3, seconds=4)


def test_error_kinds_are_structured():
    with pytest.raises(wtask.TaskDefError) as exc:
        wtask.parse_task_xml("<Task><Triggers>")
    assert exc.value.kind == "xml"

    with pytest.raises(wtask.TaskDefError) as exc:
        _task("<FooTrigger><StartBoundary>2026-01-01T00:00:00</StartBoundary></FooTrigger>")
    assert exc.value.kind == "trigger"

    with pytest.raises(wtask.TaskDefError) as exc:
        wtask.parse_task_xml(
            '<Task version="2.0"><Triggers>' + DAILY_3 + "</Triggers></Task>"
        )
    assert exc.value.kind == "version"

    with pytest.raises(wtask.TaskDefError) as exc:
        _task(
            """
<CalendarTrigger>
  <StartBoundary>2026-01-01T08:00:00</StartBoundary>
  <ScheduleByDay><DaysInterval>0</DaysInterval></ScheduleByDay>
</CalendarTrigger>
"""
        )
    assert exc.value.kind == "range"

    with pytest.raises(wtask.TaskDefError) as exc:
        _task(
            """
<CalendarTrigger>
  <StartBoundary>2026-01-01T08:00:00</StartBoundary>
  <ScheduleByWeek>
    <DaysOfWeek><Monday/></DaysOfWeek>
    <WeeksInterval>many</WeeksInterval>
  </ScheduleByWeek>
</CalendarTrigger>
"""
        )
    assert exc.value.kind == "range"


def test_execution_time_limit_zero_means_unlimited():
    task = _task(
        DAILY_3,
        '<Settings><ExecutionTimeLimit>PT0S</ExecutionTimeLimit></Settings>',
    )
    assert task.execution_time_limit is None

    task2 = _task(
        DAILY_3,
        '<Settings><ExecutionTimeLimit>PT2H</ExecutionTimeLimit></Settings>',
    )
    assert task2.execution_time_limit == timedelta(hours=2)


# --------------------------------------------------------------- PASS_TO_PASS


def test_parse_simple_daily_fields():
    task = _task(DAILY_3)
    assert task.version == "1.2"
    assert task.enabled is True
    assert task.multiple_instances == "IgnoreNew"
    assert len(task.triggers) == 1
    trigger = task.triggers[0]
    assert trigger.type == "daily"
    assert trigger.days_interval == 3
    assert trigger.start == datetime(2026, 1, 1, 8, 0, 0)
    assert trigger.enabled is True


def test_time_trigger_fires_once():
    task = _task(
        """
<TimeTrigger>
  <StartBoundary>2026-03-01T05:30:00</StartBoundary>
</TimeTrigger>
"""
    )
    runs = wtask.next_runs(task, datetime(2026, 1, 1, 0, 0, 0), 5)
    assert runs == [datetime(2026, 3, 1, 5, 30, 0)]


def test_default_daily_interval_is_one():
    task = _task(
        """
<CalendarTrigger>
  <StartBoundary>2026-01-01T07:00:00</StartBoundary>
  <ScheduleByDay/>
</CalendarTrigger>
"""
    )
    assert task.triggers[0].days_interval == 1
    runs = wtask.next_runs(task, datetime(2026, 1, 1, 8, 0, 0), 3)
    assert runs == [
        datetime(2026, 1, 2, 7, 0, 0),
        datetime(2026, 1, 3, 7, 0, 0),
        datetime(2026, 1, 4, 7, 0, 0),
    ]


def test_disabled_task_has_no_runs():
    task = _task(
        DAILY_3, "<Settings><Enabled>false</Enabled></Settings>"
    )
    assert task.enabled is False
    assert wtask.next_runs(task, datetime(2026, 1, 1, 0, 0, 0), 3) == []


def test_plan_window_is_bounded_and_sorted():
    task = _task(
        """
<CalendarTrigger>
  <StartBoundary>2026-01-01T07:00:00</StartBoundary>
  <ScheduleByDay/>
</CalendarTrigger>
"""
    )
    runs = wtask.plan_window(task, datetime(2026, 1, 2, 0, 0, 0), datetime(2026, 1, 5, 0, 0, 0))
    assert runs == [
        datetime(2026, 1, 2, 7, 0, 0),
        datetime(2026, 1, 3, 7, 0, 0),
        datetime(2026, 1, 4, 7, 0, 0),
    ]


def test_roundtrip_of_simple_daily_task():
    task = _task(
        DAILY_3,
        "<Settings><ExecutionTimeLimit>PT2H</ExecutionTimeLimit></Settings>",
    )
    text = wtask.task_to_xml(task)
    assert wtask.parse_task_xml(text) == task
    assert wtask.task_to_xml(wtask.parse_task_xml(text)) == text
