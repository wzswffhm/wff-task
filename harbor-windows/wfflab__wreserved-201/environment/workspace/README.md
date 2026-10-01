# wsafename

上传服务用于把用户提交的名称转换成 Windows 目标文件系统上安全的名称，并落盘。

```python
from wsafename import FileStore, sanitize

sanitize("report:2024.csv")        # -> 'report_2024.csv'

store = FileStore("C:/uploads")
store.save("Report Final.PDF", b"...")
store.list_names()
```

## 组成

| 模块 | 职责 |
|---|---|
| `wsafename.rules` | 名称规则：非法字符、保留设备名、长度上限 |
| `wsafename.sanitize` | 把任意输入转换成安全的单个路径段 |
| `wsafename.store` | `FileStore`：写入、读回、枚举与删除 |

## 约束

- 只用 Python 标准库
- 只接受**单个路径段**作为名称；含路径分隔符的输入会被当作非法字符处理
- 断网可运行
