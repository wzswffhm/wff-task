# wregconfig

在 Windows 注册表里读写应用配置。

```python
import winreg
from wregconfig import ConfigStore

legacy = ConfigStore(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Vendor\App", view="32")
legacy.read("InstallPath")
```

## 为什么需要 view

64 位 Windows 把 `HKLM\SOFTWARE` 按视图分开存放：32 位程序写入的键实际落在
`Wow6432Node` 之下。要读取老版本（32 位）程序留下的配置，就必须显式访问
32 位视图。

## 组成

| 模块 | 职责 |
|---|---|
| `wregconfig.views` | 视图名称与访问标志 |
| `wregconfig.store` | `ConfigStore`：读、写、删值，以及删除整节 |

## 约束

- 只用 Python 标准库（`winreg`）
- 目标环境为 64 位 Windows
- 断网可运行
