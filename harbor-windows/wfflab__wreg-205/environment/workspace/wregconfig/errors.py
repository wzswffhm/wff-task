"""wregconfig 使用的异常类型。"""


class WRegError(Exception):
    """本库所有异常的基类。"""


class ConfigError(WRegError):
    """配置项缺失或不可用。"""
