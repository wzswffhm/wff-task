"""wtask.errors —— 结构化任务定义错误。"""


class TaskDefError(Exception):
    """任务定义错误。

    ``kind`` 是本模块的公共契约，取值只能是 :data:`KINDS` 中的一种：

    ===========  ====================================================
    kind         含义
    ===========  ====================================================
    ``xml``      XML 本身无法解析（语法错误）
    ``schema``   结构不符合 Task 模式（根元素不对、必填子元素缺失或重复）
    ``version``  ``version`` 属性不受支持
    ``trigger``  触发器元素未知，或触发器内部自相矛盾
    ``range``    取值越界（日 / 月 / 周 / 间隔 / 日期时间文本非法）
    ``duration`` ISO-8601 时长文本非法
    ``structure`` 跨字段矛盾（例如 ``EndBoundary`` 早于 ``StartBoundary``）
    ===========  ====================================================
    """

    KINDS = ("xml", "schema", "version", "trigger", "range", "duration", "structure")

    def __init__(self, kind, message=""):
        if kind not in self.KINDS:
            raise ValueError("unknown TaskDefError kind: %r" % (kind,))
        self.kind = kind
        self.message = message
        super().__init__("[%s] %s" % (kind, message) if message else "[%s]" % kind)
