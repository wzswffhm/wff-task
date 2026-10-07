"""wtask.schedule —— 触发时间计算。

本模块只做「给定任务与起始时刻，算出接下来的若干次运行时刻」这件事。
所有计算都在**本地 naive 时间**上进行（不涉及时区与夏令时）。
"""

import calendar
from datetime import datetime, timedelta

from .errors import TaskDefError

#: 主出现扫描的最大跨度（天）。超出该跨度的任务定义视为不可调度。
HORIZON_DAYS = 800

#: ``plan_window`` 一次最多枚举多少次运行。
PLAN_HARD_LIMIT = 20000


# ------------------------------------------------------------------ 日历工具


def _weekday_index(day):
    """Python 的 ``date.weekday()`` 是 Monday=0..Sunday=6；本模块统一用 Sunday=0。"""
    return (day.weekday() + 1) % 7


def _week_start(day):
    """返回 ``day`` 所在周的周一。"""
    return day - timedelta(days=day.weekday())


def _week_index(day):
    """返回 ``day`` 在本月内的周序号（1 起）。"""
    return day.day // 7 + 1


def _weeks_in_month(day):
    """返回 ``day`` 所在月份共有多少个「日历周」（4 或 5）。"""
    days_in_month = calendar.monthrange(day.year, day.month)[1]
    return (days_in_month + 6) // 7


def _match_week(day, wanted):
    """``<Week>`` 匹配。

    1..4 表示第 n 周；**5 表示该月的最后一周**（可能是第 4 周，例如 2 月）。
    """
    index = _week_index(day)
    for w in wanted:
        if index == w:
            return True
    return False


def _day_matches(trigger, day):
    """``day`` 这一天是否是这个触发器的一个主出现日（不看时刻）。"""
    if trigger.type == "daily":
        return day.day % trigger.days_interval == 0

    if trigger.type == "weekly":
        return _weekday_index(day) in trigger.days_of_week

    if trigger.type == "monthly":
        return day.day in trigger.days_of_month

    if trigger.type == "monthly_dow":
        if trigger.months and day.month not in trigger.months:
            return False
        if _weekday_index(day) not in trigger.days_of_week:
            return False
        return _match_week(day, trigger.weeks_of_month)

    if trigger.type == "time":
        return day == trigger.start.date()

    raise TaskDefError("trigger", "unknown trigger type: %r" % (trigger.type,))


# ------------------------------------------------------------------ 出现时刻


def _primary_occurrences(trigger, after):
    """产出主出现时刻（升序，含早于 ``after`` 的，供重复展开使用）。"""
    out = []
    day = trigger.start.date()
    stop = after.date() + timedelta(days=HORIZON_DAYS)
    if trigger.end is not None and trigger.end.date() < stop:
        stop = trigger.end.date()
    tod = trigger.start.time()
    while day <= stop:
        if _day_matches(trigger, day):
            moment = datetime.combine(day, tod)
            if moment >= trigger.start:
                if trigger.end is not None and moment > trigger.end:
                    break
                out.append(moment)
        day += timedelta(days=1)
    return out


def _expand(trigger, occurrence, after, count):
    """把一次主出现展开为若干次实际运行（含 ``<Repetition>``）。"""
    rep = trigger.repetition
    if rep is None:
        return [occurrence] if occurrence > after else []

    runs = []
    step = 0
    while len(runs) < count and step < 100000:
        offset = rep.interval * step
        if rep.duration is not None and offset > rep.duration:
            break
        moment = occurrence + offset
        if moment > after:
            runs.append(moment)
        step += 1
    return runs


# ------------------------------------------------------------------ 公共 API


def next_runs(task, after, count):
    """返回 ``after`` 之后最近的 ``count`` 次运行时刻（升序、去重）。

    * 任务被禁用（``task.enabled`` 为假）时返回空列表；
    * 触发器被禁用（``trigger.enabled`` 为假）时跳过该触发器；
    * 返回的时刻**严格大于** ``after``；不足 ``count`` 次时返回实际数量。
    """
    if not task.enabled:
        return []
    if count <= 0:
        return []

    moments = set()
    for trigger in task.triggers:
        for occurrence in _primary_occurrences(trigger, after):
            moments.update(_expand(trigger, occurrence, after, count))

    return sorted(moments)[:count]


def plan_window(task, start, end):
    """返回位于 ``(start, end]`` 区间内的全部运行时刻（升序、去重）。"""
    if end < start:
        return []
    return [m for m in next_runs(task, start, PLAN_HARD_LIMIT) if m <= end]


def validate_task(task):
    """跨字段一致性校验；不一致时抛 ``TaskDefError``。"""
    for trigger in task.triggers:
        if trigger.end is not None and trigger.end < trigger.start:
            raise TaskDefError(
                "structure",
                "EndBoundary %s is earlier than StartBoundary %s"
                % (trigger.end.isoformat(), trigger.start.isoformat()),
            )
    return task
