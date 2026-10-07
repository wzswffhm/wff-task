修复了 winstall 的三类 Windows 故障，只改动了 winstall/ 下的实现代码（tests/、pyproject.toml、布局均未动）。

## 1. 版本比较按数值（winstall/versions.py）
- 原来把数字部分当**字符串**比较，导致 `1.10.0 < 1.9.0`。现在每段解析为十进制整数（`_decimal`，容错处理前导零/脏段），不足四段右侧补 0：`parse_version("1.2") == [1, 2, 0, 0]`。
- `compare_versions` 逐段按数值比较；预发布标签低于同号正式版，标签内部按 semver 风格分段比较（`beta.10 > beta.9`）；忽略 `+build` 元数据。
- 由此 `plan_transaction` 对任何不高于已安装版本的安装请求（降级/原地重装）抛 `PlanRejected`；规划保持只读，磁盘与清单不变。

## 2. 被占用文件只推迟不失败 + 整体回滚（winstall/transaction.py 重写为事务引擎）
- `_Transaction` 在每个动作生效前记录撤销信息：被覆盖文件的旧内容、新建文件、被删文件内容、新建目录、执行前的清单原始字节。
- **写动作**：目标若是目录 → 立即视为不可延迟失败；先读旧内容做备份（读不出且像共享冲突 → 推迟），再把源复制到 `目标.winstall-part` 后 `os.replace`。`os.replace` 抛出的共享冲突类错误（PermissionError / winerror 5、32、33 / EACCES、EPERM）且目标是已存在普通文件 → **推迟**：文件保持旧内容、临时文件删除、相对路径进 `ApplyResult.deferred` 与清单 `pending_replace`，其余动作照常；对同一份计划再次 `apply_transaction` 即完成替换并清空 `pending_replace`。删除动作被占用时同样推迟（升级丢弃旧文件、卸载场景），清单保留条目等下一次收尾。
- **不可延迟失败**（同名目录占位、父路径被文件占位、源缺失等）：先回滚——被覆盖文件逐字节还原、新建文件删除、被删文件恢复、清单按执行前字节复原（此前无清单则删除）、清理全部 `.winstall-part`、回收本次新建的空目录——再抛 `ApplyFailed`。清单写入也纳入事务（`manifest.write_manifest` 失败时清理自身临时文件）。
- 动作类型/操作类型在执行前统一校验（原 `ValueError` 语义保留，且不再产生半执行状态）。

## 3. 其它
- `winstall/planner.py`：加固 `_check_relpath`，额外拒绝 `..` 段、绝对路径与 `C:` 盘符形式（原先可逃出载荷目录），规划语义与签名不变。
- 验证：`tests/test_winstall_basic.py` 11 项全过；另用真实 Windows 句柄（共享冲突 + `msvcrt` 独占锁）及 monkeypatch `os.replace` 两种方式跑了 110+ 项端到端检查（降级拦截、推迟/重试、目录占位回滚、新建/删除文件复原、清单逐字节还原、无临时残留、作用域隔离、不碰其它产品、规划只读等），全部通过；临时脚本已删除。