# wdl

下载文件归档工具。浏览器与下载器落地的文件在 NTFS 上会带一条
`Zone.Identifier` 备用数据流；归档时要把它带走，发布到内网前再按策略清掉。

```python
from wdl import archive_tree, copy_file, is_blocked, unblock

copy_file(r"C:\Downloads\report.pdf", r"D:\archive\report.pdf")
unblock(r"D:\archive\report.pdf")
```

## 组成

| 模块 | 职责 |
|---|---|
| `wdl.streams` | 备用数据流的读写、存在性与大小 |
| `wdl.archive` | 单文件复制与目录树归档 |
| `wdl.unblock` | 「来自互联网」标记的查询与清除 |

## 约束

- 只用 Python 标准库
- 目标环境为 NTFS
- 断网可运行
