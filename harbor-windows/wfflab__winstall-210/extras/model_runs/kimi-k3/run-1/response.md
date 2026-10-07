修复了 winstall 的三类 Windows 事务故障，只改动了 winstall/versions.py 与 winstall/transaction.py，公开 API 形状不变。

1. 版本比较按数值（versions.py 重写）：
   - parse_version 现在把版本号解析为四段十进制整数元组，不足四段补 0，非数字段按 0 处理。
   - compare_versions 先按整数元组逐段比较（1.10.0 > 1.9.0、2.0.0 < 10.0.0、1.2 == 1.2.0），数字段相同再比较预发布标签：空标签（正式版）高于任何预发布标签，标签按点分标识符比较（数字标识符按数值且低于非数字标识符）。由此 plan_transaction 通过 is_upgrade 拒绝一切不高于已安装版本的安装（PlanRejected("downgrade")），规划仍只读。

2. 被占用文件只推迟不失败（transaction.py 重写 apply_transaction）：
   - 写入仍是「同目录 .winstall-part 临时文件 + os.replace 原子替换」，且 finally 中清理临时文件，载荷目录不留残留。
   - os.replace / 删除遇到 PermissionError 或 winerror 5/32/33（共享冲突）时：目标文件保持旧内容不动，相对路径记入 ApplyResult.deferred 与清单该产品的 pending_replace，其余动作照常执行并出现在 applied 中，清单版本号更新为新版本。
   - 每次执行前先根据计划的 files 映射冲刷清单中的 pending_replace：占用解除后对同一计划再次 apply_transaction 即完成替换，deferred 为空、pending_replace 清空。

3. 不可延迟的失败整体回滚：
   - 执行前把将被覆盖/删除的文件逐字节备份到系统临时目录，记录本次新建的文件。
   - 发生非占用类失败（如目标被同名目录占据）时：从备份恢复被覆盖文件、删除本次新建文件（并清理空父目录）、把清单写回执行前的快照、清掉全部临时/备份文件，然后抛 ApplyFailed。
   - 卸载时文件被占用同样 defer：条目保留并记 pending_replace，解除占用后再次执行同一卸载计划即完成删除并移除产品条目。

验证：tests/test_winstall_basic.py 11 项全部通过；并额外一次性验证了验收标准 2–8 的全部场景（数值版本比较、降级拒绝且现场不变、占用 defer + 重放完成、目录冲突回滚后旧内容与版本号恢复、新建文件清除、无 .winstall-part 残留、升级删旧文件、规划只读、不碰其它产品、作用域隔离）。未修改 tests/、pyproject.toml 与安装根布局，未引入第三方依赖。