"""PowerShell 调用的结果对象。"""


class PSResult(object):
    """一次 PowerShell 调用的结果。"""

    __slots__ = ("exit_code", "stdout", "stderr")

    def __init__(self, exit_code, stdout, stderr=""):
        self.exit_code = int(exit_code)
        self.stdout = stdout
        self.stderr = stderr

    @property
    def ok(self):
        """调用是否成功。"""
        return self.exit_code == 0

    @property
    def output(self):
        """标准输出（去掉首尾空白）。"""
        return self.stdout.strip()

    def __repr__(self):
        return "PSResult(exit_code=%r, ok=%r)" % (self.exit_code, self.ok)


class PSJob(object):
    """一段待执行的 PowerShell 脚本。"""

    def __init__(self, script, name="job"):
        self.script = script
        self.name = name

    def run(self, runner, timeout=None):
        """用 ``runner`` 执行本作业。"""
        return runner(self.script, timeout=timeout)

    def __repr__(self):
        return "PSJob(%r)" % (self.name,)
