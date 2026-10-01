"""winstall 的异常层次。

调用方需要能区分三类失败：

* :class:`PlanRejected`  —— 计划阶段就被拒绝，**磁盘与清单必须保持原样**
* :class:`ApplyFailed`   —— 执行阶段失败，**必须已经回滚到执行前的状态**
* 其它 :class:`WInstallError` —— 参数或环境错误
"""


class WInstallError(Exception):
    """所有 winstall 异常的基类。"""


class PlanRejected(WInstallError):
    """计划被拒绝：请求的操作在当前安装状态下不合法。

    抛出此异常时不得对文件系统或清单产生任何影响。
    """

    def __init__(self, reason, message=None):
        self.reason = reason
        super().__init__(message or reason)


class ApplyFailed(WInstallError):
    """执行失败。

    抛出此异常时，产品的载荷目录与清单必须已经回到执行前的状态。
    """

    def __init__(self, action=None, message=None):
        self.action = action
        super().__init__(message or ("apply failed: %s" % (action,)))


class NotInstalled(WInstallError):
    """请求对未安装的产品执行操作。"""
