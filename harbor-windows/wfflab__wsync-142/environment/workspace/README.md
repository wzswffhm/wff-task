# wsync

`wsync` 把一棵源目录树**镜像**同步到一棵目标目录树：

- 源里有、目标里没有的文件 → 创建
- 两边都有但内容不同的文件 → 更新
- 目标里多出来的文件 → 删除

同步是**确定性**的：同样的输入目录树，永远得到同样的目标目录树。

## 环境

- Python 3.9+
- 无第三方运行时依赖

把仓库根目录加入 `PYTHONPATH` 即可使用：

```powershell
$env:PYTHONPATH = "C:\testbed;$env:PYTHONPATH"
```

## 用法

```python
from wsync import build_plan, sync_tree

plan = build_plan(r"D:\data", r"D:\mirror")      # 只看计划，不动磁盘
for entry in plan.entries[:10]:
    print(entry.action, entry.relpath)

result = sync_tree(r"D:\data", r"D:\mirror")
print("created:", result.created)
print("updated:", result.updated)
print("deleted:", result.deleted)
print("failed :", result.failed)
```

`sync_tree(..., dry_run=True)` 只计算并返回计划，不修改磁盘。

## 结果对象

`SyncResult` 的字段：

| 字段 | 含义 |
|---|---|
| `created` | 本次新建的相对路径 |
| `updated` | 本次覆盖的相对路径 |
| `deleted` | 本次删除的相对路径 |
| `kept` | 内容一致、未改动的相对路径 |
| `failed` | 未能完成的条目：`{"action", "relpath", "error"}` |
| `.ok` | `failed` 为空时为 `True` |

## 运行自带测试

```powershell
python -m pytest -q tests
```
