"""wtask.duration —— ISO-8601 时长（Task Scheduler 风格）的解析与规范化。

接受的文本形如 ``P3D`` / ``PT72H`` / ``P1DT2H3M4S`` / ``PT0S``。
秒以外的部分必须是整数（本题不支持小数秒）。
"""

import re
from datetime import timedelta

from .errors import TaskDefError

_DUR_RE = re.compile(
    r"^P(?:(?P<d>\d+)D)?"
    r"(?:T(?:(?P<h>\d+)H)?(?:(?P<m>\d+)M)?(?:(?P<s>\d+)S)?)?$"
)


def parse_duration(text):
    """把 ISO-8601 时长文本解析为 ``datetime.timedelta``。

    非法文本抛 ``TaskDefError(kind="duration")``。
    """
    if not isinstance(text, str):
        raise TaskDefError("duration", "duration must be text, got %r" % (text,))
    raw = text.strip()
    if not raw:
        raise TaskDefError("duration", "empty duration")
    m = _DUR_RE.match(raw)
    if m is None:
        raise TaskDefError("duration", "invalid ISO-8601 duration: %r" % (text,))
    if raw in ("P", "PT"):
        raise TaskDefError("duration", "duration has no components: %r" % (text,))
    return timedelta(
        days=int(m.group("d") or 0),
        hours=int(m.group("h") or 0),
        minutes=int(m.group("m") or 0),
        seconds=int(m.group("s") or 0),
    )


def format_duration(value):
    """把 ``timedelta`` 写成 ISO-8601 文本。

    只写非零分量，零时长写作 ``PT0S``。
    """
    if not isinstance(value, timedelta):
        raise TaskDefError("duration", "format_duration expects timedelta")
    total = int(value.total_seconds())
    if total < 0:
        raise TaskDefError("duration", "negative duration is not representable")
    if total == 0:
        return "PT0S"
    hours, rem = divmod(total, 3600)
    minutes, seconds = divmod(rem, 60)
    out = "PT"
    if hours:
        out += "%dH" % hours
    if minutes:
        out += "%dM" % minutes
    if seconds:
        out += "%dS" % seconds
    return out
