# wpublish

把构建产物发布到 Windows 共享目录，并把 NTFS 访问权限摆正。

```python
from wpublish import publish, audit

publish(r"D:\build\out", r"\\fileserver\pub\release-42", "BUILTIN\\Users")
audit(r"\\fileserver\pub\release-42", "BUILTIN\\Users")   # -> []
```

发布后的目录应当对访问者**只读**，并且这个限制必须覆盖整个子树。

## 组成

| 模块 | 职责 |
|---|---|
| `wpublish.icacls` | 调用并解析 `icacls`：列出、添加与移除访问控制项 |
| `wpublish.rights` | 有效权限判定 |
| `wpublish.publish` | 发布流程与发布后审计 |

## 约束

- 只用 Python 标准库（通过命令行调用系统自带的 `icacls`）
- 目标文件系统为 NTFS
- 断网可运行
