"""wtask.xmlio —— 任务 XML 的解析与规范化序列化。"""

import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

from .duration import format_duration, parse_duration
from .errors import TaskDefError
from .model import MONTH_NAMES, WEEKDAY_NAMES, Repetition, Task, Trigger
from .schedule import validate_task

#: 受支持的 ``version`` 属性
SUPPORTED_VERSIONS = ("1.0", "1.2")

#: 默认命名空间（序列化时写回）
NS = "http://schemas.microsoft.com/windows/2004/02/mit/task"

DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S"

_DEFAULT_MULTIPLE_INSTANCES = "IgnoreNew"

_TRIGGER_TAGS = ("CalendarTrigger", "TimeTrigger")
_SCHEDULE_TAGS = (
    "ScheduleByDay",
    "ScheduleByWeek",
    "ScheduleByMonth",
    "ScheduleByMonthDayOfWeek",
)
_CALENDAR_ALLOWED = ("StartBoundary", "EndBoundary", "Enabled", "Repetition") + _SCHEDULE_TAGS
_TIME_ALLOWED = ("StartBoundary", "EndBoundary", "Enabled", "Repetition")


# ------------------------------------------------------------------ 解析工具


def _tag(element):
    """去掉命名空间前缀，返回本地标签名。"""
    tag = element.tag
    return tag.split("}", 1)[1] if "}" in tag else tag


def _children(element, name):
    return [child for child in element if _tag(child) == name]


def _one(element, name):
    found = _children(element, name)
    if len(found) > 1:
        raise TaskDefError("schema", "duplicate <%s>" % name)
    return found[0] if found else None


def _text(element, name, required=False):
    child = _one(element, name)
    if child is None:
        if required:
            raise TaskDefError("schema", "missing required <%s>" % name)
        return None
    return (child.text or "").strip()


def _parse_datetime(text, name):
    try:
        return datetime.strptime(text, DATETIME_FORMAT)
    except (TypeError, ValueError):
        raise TaskDefError("range", "invalid datetime in <%s>: %r" % (name, text))


def _parse_bool(text, name):
    value = (text or "").strip().lower()
    if value in ("true", "1"):
        return True
    if value in ("false", "0"):
        return False
    raise TaskDefError("range", "invalid boolean in <%s>: %r" % (name, text))


def _parse_int(text, name):
    try:
        return int((text or "").strip())
    except (TypeError, ValueError):
        raise TaskDefError("range", "invalid integer in <%s>: %r" % (name, text))


def _check_children(element, allowed, where):
    for child in element:
        if _tag(child) not in allowed:
            raise TaskDefError("trigger", "unexpected <%s> inside <%s>" % (_tag(child), where))


def _parse_weekdays(element, name):
    """解析 ``<DaysOfWeek><Monday/>…</DaysOfWeek>``；缺失时返回 ``None``。"""
    holder = _one(element, name)
    if holder is None:
        return None
    days = []
    for child in holder:
        local = _tag(child)
        if local not in WEEKDAY_NAMES:
            raise TaskDefError("trigger", "unknown weekday <%s>" % local)
        days.append(WEEKDAY_NAMES.index(local))
    if not days:
        raise TaskDefError("trigger", "<%s> is empty" % name)
    if len(set(days)) != len(days):
        raise TaskDefError("trigger", "duplicate weekday in <%s>" % name)
    return tuple(sorted(days))


def _parse_months(element):
    holder = _one(element, "Months")
    if holder is None:
        raise TaskDefError("schema", "missing required <Months>")
    months = []
    for child in holder:
        local = _tag(child)
        if local not in MONTH_NAMES:
            raise TaskDefError("trigger", "unknown month <%s>" % local)
        months.append(MONTH_NAMES.index(local) + 1)
    if not months:
        raise TaskDefError("trigger", "<Months> is empty")
    if len(set(months)) != len(months):
        raise TaskDefError("trigger", "duplicate month in <Months>")
    return tuple(sorted(months))


def _parse_repetition(holder):
    element = _one(holder, "Repetition")
    if element is None:
        return None
    interval_text = _text(element, "Interval", required=True)
    interval = parse_duration(interval_text)
    if interval <= timedelta(0):
        raise TaskDefError("range", "repetition <Interval> must be positive")
    duration_text = _text(element, "Duration")
    duration = parse_duration(duration_text) if duration_text is not None else None
    if duration is not None and duration <= timedelta(0):
        raise TaskDefError("range", "repetition <Duration> must be positive")
    stop_text = _text(element, "StopAtDurationEnd")
    stop = _parse_bool(stop_text, "StopAtDurationEnd") if stop_text is not None else False
    return Repetition(interval=interval, duration=duration, stop_at_duration_end=stop)


def _parse_calendar(element):
    allowed = _CALENDAR_ALLOWED
    _check_children(element, allowed, "CalendarTrigger")

    start = _parse_datetime(_text(element, "StartBoundary", required=True), "StartBoundary")
    end_text = _text(element, "EndBoundary")
    end = _parse_datetime(end_text, "EndBoundary") if end_text is not None else None
    enabled_text = _text(element, "Enabled")
    enabled = _parse_bool(enabled_text, "Enabled") if enabled_text is not None else True
    repetition = _parse_repetition(element)

    schedules = [child for child in element if _tag(child) in _SCHEDULE_TAGS]
    if not schedules:
        raise TaskDefError("trigger", "<CalendarTrigger> requires exactly one schedule")
    if len(schedules) > 1:
        raise TaskDefError(
            "trigger", "<CalendarTrigger> has %d schedules, expected 1" % len(schedules)
        )
    schedule = schedules[0]
    kind = _tag(schedule)

    if kind == "ScheduleByDay":
        _check_children(schedule, ("DaysInterval",), "ScheduleByDay")
        interval_text = _text(schedule, "DaysInterval")
        days_interval = _parse_int(interval_text, "DaysInterval") if interval_text else 1
        return Trigger(
            type="daily", start=start, end=end, enabled=enabled,
            days_interval=days_interval, repetition=repetition,
        )

    if kind == "ScheduleByWeek":
        _check_children(schedule, ("DaysOfWeek", "WeeksInterval"), "ScheduleByWeek")
        days_of_week = _parse_weekdays(schedule, "DaysOfWeek")
        if days_of_week is None:
            raise TaskDefError("trigger", "<ScheduleByWeek> requires <DaysOfWeek>")
        weeks_text = _text(schedule, "WeeksInterval")
        weeks_interval = _parse_int(weeks_text, "WeeksInterval") if weeks_text else 1
        if not 1 <= weeks_interval <= 52:
            raise TaskDefError("range", "WeeksInterval out of 1..52")
        return Trigger(
            type="weekly", start=start, end=end, enabled=enabled,
            weeks_interval=weeks_interval, days_of_week=days_of_week,
            repetition=repetition,
        )

    if kind == "ScheduleByMonth":
        _check_children(schedule, ("DaysOfMonth", "Months"), "ScheduleByMonth")
        holder = _one(schedule, "DaysOfMonth")
        if holder is None:
            raise TaskDefError("schema", "missing required <DaysOfMonth>")
        days_of_month = tuple(sorted(_parse_int(child.text, "Day") for child in holder))
        if not days_of_month:
            raise TaskDefError("trigger", "<DaysOfMonth> is empty")
        for value in days_of_month:
            if not 1 <= value <= 31:
                raise TaskDefError("range", "Day %d out of 1..31" % value)
        return Trigger(
            type="monthly", start=start, end=end, enabled=enabled,
            days_of_month=days_of_month, months=_parse_months(schedule),
            repetition=repetition,
        )

    # ScheduleByMonthDayOfWeek
    _check_children(schedule, ("Weeks", "DaysOfWeek", "Months"), "ScheduleByMonthDayOfWeek")
    holder = _one(schedule, "Weeks")
    if holder is None:
        raise TaskDefError("schema", "missing required <Weeks>")
    weeks_of_month = tuple(sorted(_parse_int(child.text, "Week") for child in holder))
    if not weeks_of_month:
        raise TaskDefError("trigger", "<Weeks> is empty")
    for value in weeks_of_month:
        if not 1 <= value <= 5:
            raise TaskDefError("range", "Week %d out of 1..5" % value)
    days_of_week = _parse_weekdays(schedule, "DaysOfWeek")
    if days_of_week is None:
        raise TaskDefError("trigger", "<ScheduleByMonthDayOfWeek> requires <DaysOfWeek>")
    return Trigger(
        type="monthly_dow", start=start, end=end, enabled=enabled,
        days_of_week=days_of_week, weeks_of_month=weeks_of_month,
        months=_parse_months(schedule), repetition=repetition,
    )


def _parse_time(element):
    _check_children(element, _TIME_ALLOWED, "TimeTrigger")
    start = _parse_datetime(_text(element, "StartBoundary", required=True), "StartBoundary")
    end_text = _text(element, "EndBoundary")
    end = _parse_datetime(end_text, "EndBoundary") if end_text is not None else None
    enabled_text = _text(element, "Enabled")
    enabled = _parse_bool(enabled_text, "Enabled") if enabled_text is not None else True
    return Trigger(
        type="time", start=start, end=end, enabled=enabled,
        repetition=_parse_repetition(element),
    )


# ------------------------------------------------------------------ 公共 API


def parse_task_xml(text):
    """把任务 XML 解析为 :class:`~wtask.model.Task`。"""
    if not isinstance(text, (str, bytes)):
        raise TaskDefError("xml", "text must be str or bytes")
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        raise TaskDefError("xml", str(exc))

    if _tag(root) != "Task":
        raise TaskDefError("schema", "root element must be <Task>")

    version = (root.get("version") or "").strip()

    holders = _children(root, "Triggers")
    if not holders:
        raise TaskDefError("structure", "missing <Triggers>")
    if len(holders) > 1:
        raise TaskDefError("schema", "duplicate <Triggers>")

    triggers = []
    for child in holders[0]:
        local = _tag(child)
        if local == "CalendarTrigger":
            triggers.append(_parse_calendar(child))
        elif local == "TimeTrigger":
            triggers.append(_parse_time(child))
        else:
            continue
    if not triggers:
        raise TaskDefError("structure", "<Triggers> is empty")

    fields = {"version": version, "triggers": tuple(triggers)}
    settings = _one(root, "Settings")
    if settings is not None:
        enabled_text = _text(settings, "Enabled")
        if enabled_text is not None:
            fields["enabled"] = _parse_bool(enabled_text, "Enabled")
        limit_text = _text(settings, "ExecutionTimeLimit")
        if limit_text is not None:
            fields["execution_time_limit"] = parse_duration(limit_text)
        policy = _text(settings, "MultipleInstancesPolicy")
        if policy:
            fields["multiple_instances"] = policy
        delay_text = _text(settings, "RandomDelay")
        if delay_text is not None:
            fields["random_delay"] = parse_duration(delay_text)

    task = Task(**fields)
    validate_task(task)
    return task


def _format_datetime(value):
    return value.strftime(DATETIME_FORMAT)


def _weekday_elements(days):
    return "".join("<%s/>" % WEEKDAY_NAMES[day] for day in days)


def _month_elements(months):
    return "".join("<%s/>" % MONTH_NAMES[month - 1] for month in months)


def _trigger_xml(trigger, indent):
    pad = " " * indent
    inner = " " * (indent + 2)
    name = "TimeTrigger" if trigger.type == "time" else "CalendarTrigger"
    lines = [pad + "<%s>" % name]
    lines.append(inner + "<StartBoundary>%s</StartBoundary>" % _format_datetime(trigger.start))
    if trigger.end is not None:
        lines.append(inner + "<EndBoundary>%s</EndBoundary>" % _format_datetime(trigger.end))
    if not trigger.enabled:
        lines.append(inner + "<Enabled>false</Enabled>")

    if trigger.type == "daily":
        lines.append(inner + "<ScheduleByDay>")
        lines.append(inner + "  <DaysInterval>%d</DaysInterval>" % trigger.days_interval)
        lines.append(inner + "</ScheduleByDay>")
    elif trigger.type == "weekly":
        lines.append(inner + "<ScheduleByWeek>")
        lines.append(
            inner + "  <DaysOfWeek>" + _weekday_elements(trigger.days_of_week) + "</DaysOfWeek>"
        )
        lines.append(inner + "  <WeeksInterval>%d</WeeksInterval>" % trigger.weeks_interval)
        lines.append(inner + "</ScheduleByWeek>")
    elif trigger.type == "monthly":
        lines.append(inner + "<ScheduleByMonth>")
        lines.append(
            inner + "  <DaysOfMonth>"
            + "".join("<Day>%d</Day>" % day for day in trigger.days_of_month)
            + "</DaysOfMonth>"
        )
        lines.append(inner + "  <Months>" + _month_elements(trigger.months) + "</Months>")
        lines.append(inner + "</ScheduleByMonth>")
    elif trigger.type == "monthly_dow":
        lines.append(inner + "<ScheduleByMonthDayOfWeek>")
        lines.append(
            inner + "  <Weeks>"
            + "".join("<Week>%d</Week>" % week for week in trigger.weeks_of_month)
            + "</Weeks>"
        )
        lines.append(
            inner + "  <DaysOfWeek>" + _weekday_elements(trigger.days_of_week) + "</DaysOfWeek>"
        )
        lines.append(inner + "  <Months>" + _month_elements(trigger.months) + "</Months>")
        lines.append(inner + "</ScheduleByMonthDayOfWeek>")

    repetition = trigger.repetition
    if repetition is not None:
        lines.append(inner + "<Repetition>")
        lines.append(inner + "  <Interval>%s</Interval>" % format_duration(repetition.interval))
        if repetition.duration is not None:
            lines.append(
                inner + "  <Duration>%s</Duration>" % format_duration(repetition.duration)
            )
        if repetition.stop_at_duration_end:
            lines.append(inner + "  <StopAtDurationEnd>true</StopAtDurationEnd>")
        lines.append(inner + "</Repetition>")

    lines.append(pad + "</%s>" % name)
    return lines


def task_to_xml(task):
    """把 :class:`~wtask.model.Task` 规范化为 XML 文本。

    规范化规则见 ``docs/TASKSCHEMA.md`` §7：元素与属性顺序固定、缺省值省略、
    日期时间写作 ``YYYY-MM-DDTHH:MM:SS``、时长写成规范形式。
    """
    lines = ['<Task version="%s" xmlns="%s">' % (task.version, NS)]
    lines.append("  <Triggers>")
    for trigger in task.triggers:
        lines.extend(_trigger_xml(trigger, 4))
    lines.append("  </Triggers>")
    lines.append("  <Settings>")
    lines.append(
        "    <MultipleInstancesPolicy>%s</MultipleInstancesPolicy>" % task.multiple_instances
    )
    if not task.enabled:
        lines.append("    <Enabled>false</Enabled>")
    if task.execution_time_limit is not None:
        lines.append(
            "    <ExecutionTimeLimit>%s</ExecutionTimeLimit>"
            % format_duration(task.execution_time_limit)
        )
    if task.random_delay:
        lines.append("    <RandomDelay>%s</RandomDelay>" % format_duration(task.random_delay))
    lines.append("  </Settings>")
    lines.append("</Task>")
    return "\n".join(lines) + "\n"
