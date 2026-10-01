# 修复 Windows 安装事务引擎 winstall

`C:\testbed` 下是纯 Python 包 **winstall**（2.0.0）。它把一个产品的安装 / 升级 / 卸载
当作一次事务来做：先规划（`plan_transaction`），再执行（`apply_transaction`）。
产品的已安装状态记录在安装根的 `installed.json` 清单里。

现场报了下面三类故障，**都只在 Windows 上出现**：

## 故障现象

1. **版本倒退被放行。** 某产品已经装了 `1.10.0`，再安装 `1.9.0` 竟然成功了，
   产品被降级。日志里 `1.10.0` 反而被判成"比 `1.9.0` 旧"。
   产品线使用 `major.minor.build.revision` 四段十进制版本号。

2. **一个文件被占用，整次安装就崩。** 目标文件正被别的进程打开时，
   `apply_transaction` 直接抛出 `PermissionError`，其余文件也没有更新。
   在 Windows 上，别的进程打开着某个文件是常态，这不该让整次安装失败。

3. **失败之后现场被破坏。** 执行到一半失败时，已经被覆盖的文件留在"新版内容"上，
   本次新建的文件也留在盘上，产品目录既不是旧版本也不是新版本。
   清单里还记着旧版本号，磁盘上却是新版本内容。

## 目标

1. **版本比较按数值。** `compare_versions` / `parse_version` 必须把四段版本号
   当十进制整数比较，不足四段补 0；带预发布标签的版本（如 `1.0.0-beta`）
   低于同号正式版。由此 `plan_transaction` 必须拒绝任何**不高于**已安装版本的
   安装请求，抛 `PlanRejected`，且此时磁盘与清单保持原样。

2. **被占用的文件只推迟，不失败。** 目标文件被别的进程打开时：
   - 它保持**旧内容不动**（不得清空、不得半写）
   - 它的相对路径出现在 `ApplyResult.deferred` 里
   - 其余动作照常执行，`ApplyResult.applied` 里包含它们
   - 它的相对路径写进清单该产品的 `pending_replace`
   - 占用解除后，对**同一份计划**再次调用 `apply_transaction` 必须完成替换，
     随后 `deferred` 为空、清单 `pending_replace` 清空
   - 载荷目录里不得残留任何临时文件

3. **不可延迟的失败必须整体回滚。** 例如目标位置已被一个同名目录占据，
   这类失败无法推迟，必须：
   - 把本次事务**已覆盖**的文件逐字节恢复成旧内容
   - 把本次事务**新建**的文件删除
   - 把清单恢复到执行前的状态（含产品版本号）
   - 清掉所有临时文件
   - 并以 `ApplyFailed` 抛出

4. **不改变公开 API 的形状。** `plan_transaction` / `apply_transaction` /
   `Plan` / `Action` / `ApplyResult` 的签名与字段保持不变；
   `apply_transaction` 仍然返回 `ApplyResult(operation, product, version,
   applied, deferred)`。`plan_transaction` 必须保持**只读**：规划阶段不得
   创建目录、写文件或改清单。

## 功能边界

- 只修改 `winstall/` 下的代码
- `tests/` 下是仓库自带的可见回归测试，**不得修改**
- 只用 Python 标准库；目标环境为 Windows；断网可运行

## 约束

- 不得改 `pyproject.toml` 里的包名与版本号
- 不得引入新的第三方依赖
- 不得改动两个作用域（`machine` / `user`）的安装根布局

## 验收标准

1. 可见回归测试 `tests/test_winstall_basic.py` 全部通过。
2. `compare_versions("1.10.0", "1.9.0") == 1`；`compare_versions("2.0.0", "10.0.0") == -1`；
   `compare_versions("1.2", "1.2.0") == 0`；`compare_versions("1.0.0", "1.0.0-beta") == 1`。
3. 已装 `1.10.0` 时规划安装 `1.9.0` 抛 `PlanRejected`；磁盘内容与清单版本号均不变。
4. 目标文件被占用时 `apply_transaction` **不抛异常**；该文件出现在 `deferred` 中，
   内容仍是旧内容；清单版本号已更新为新版本，`pending_replace` 含该文件。
5. 占用解除后对同一计划再次执行：该文件内容变成新内容，`deferred` 为空，
   `pending_replace` 清空。
6. 不可延迟的失败（目标是同名目录）后：被覆盖文件的内容、清单里的版本号
   都回到执行前。
7. 同一次失败后：本次新建的文件不再存在，且载荷目录下没有 `.winstall-part` 残留。
8. 既有行为不回归：干净安装、升级覆盖、升级删除旧文件、卸载、两个作用域互不干扰、
   规划只读、不碰其它产品。
