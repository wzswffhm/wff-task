# wrotate

按序号滚动日志文件：`app.log` → `app.log.1` → `app.log.2` ……，并按保留份数删除最老的。

```python
from wrotate import Rotator

Rotator("C:/logs/app.log", keep=7).rotate_and_prune()
```

## 语义

- 每轮转一次，现有轮转的序号都加一
- 保留 `keep` 份轮转，多出来的按**序号**从大到小删除
- 目标序号上已有残留文件时，轮转仍然要成功完成

## 组成

| 模块 | 职责 |
|---|---|
| `wrotate.fsutil` | 移动、删除与轮转文件名的识别 |
| `wrotate.rotator` | `Rotator`：滚动与保留份数整理 |

## 约束

- 只用 Python 标准库
- 目标环境为 Windows
- 断网可运行
