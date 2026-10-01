# winstall

Windows 上的**事务化**安装引擎：把一次安装 / 升级 / 卸载当成一个事务来做，
要么全部生效，要么回到执行前的状态。

```python
from winstall import plan_transaction, apply_transaction

plan = plan_transaction("install", "demo", "2.4.0",
                        {"bin/demo.exe": "stage/bin/demo.exe",
                         "etc/demo.ini": "stage/etc/demo.ini"},
                        scope="machine")
result = apply_transaction(plan)
print(result.version, result.deferred)
```

## 安装布局

两个作用域互相独立，互不干扰：

| 作用域 | 安装根 |
|---|---|
| `machine` | `%ProgramData%\WInstall` |
| `user` | `%LOCALAPPDATA%\WInstall` |

```
<root>/
    installed.json                    # 清单：每个产品当前版本与文件列表
    products/
        <product>/
            payload/                  # 已安装文件；升级时原地覆盖
```

## 语义

- `plan_transaction(operation, product, version=None, files=None, scope="machine", root=None)`
  - `operation` 取 `"install"` 或 `"uninstall"`
  - `files` 是 `{载荷内相对路径: 源文件路径}`
  - **只读**：规划阶段不得创建目录、写文件或改清单
  - 不合法时抛 `PlanRejected`，此时磁盘与清单必须保持原样
- `apply_transaction(plan)` 返回 `ApplyResult(operation, product, version, applied, deferred)`
  - `applied` 是已生效的相对路径
  - `deferred` 是**被推迟**的相对路径（见下）
- 写入是原子替换：先写同目录临时文件，再替换目标

## 被占用的文件

Windows 上别的进程可能正打开着某个文件。这种情况下**不能**替换它，
但也不该让整次安装失败：该文件保持旧内容不动，记进结果的 `deferred`，
并写进清单的 `pending_replace`，由下一次执行完成替换。

## 约束

- 只用 Python 标准库
- 目标环境为 Windows
- 断网可运行
