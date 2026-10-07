修复了 `wsafename` 在 Windows 目标文件系统上的三类缺陷，仅改动 `wsafename/` 下的实现代码（rules.py / sanitize.py / store.py），未触碰 tests/ 与任何公开签名。

1) 保留设备名判定（rules.py）
- 新增 `device_base_name(name)`：按 Win32 规则只取**第一个点之前**的一段并做 strip+upper 归一。
- `is_reserved` 改为基于该段判定，于是 `CON`、`CON.txt`、`con.tar.gz`、`NUL.log`、`lpt1.tar.gz` 被拒；`console.txt`、`mycon`、`com10.log`、`com0.txt`、`.hidden` 照常放行。
- 新增 `has_trailing_junk(name)`，并让 `is_valid` 对以点/空格结尾（会被 Windows 静默丢弃）的名称返回 False，与「无需净化即可直接使用」的既有语义一致。

2) 落盘名确定性（sanitize.py）
- 净化顺序改为：strip → 替换非法字符 → `rstrip(TRAILING_CHARS)` 去掉尾部点与空格 → 截断到 MAX_SEGMENT_LENGTH（截断后可能再出现尾部点/空格，故再清理一次）→ 校验。
- 因此 `sanitize("report.") == "report"`，`report`/`report.`/`report   ` 收敛到同一落盘名，`list_names()` 只记录一次；`sanitize` 幂等。

3) 明确拒绝不可用名称（sanitize.py + store.py）
- 净化后为空（`"..."`、`"."`、`".."`、纯空白）或净化结果命中保留设备名时抛 `InvalidNameError`，底层 `OSError` 不再透传给调用方。
- `FileStore.save` 在触碰磁盘前完成净化+校验，非法名称时目标目录不会留下任何条目；`load` / `target_path` 对非法名称抛 `InvalidNameError`。
- 查询类操作 `exists` / `delete` 通过内部 `_query_path` 对不可用名称返回 False（保持既有「条目不存在返回 False」语义），`delete` 用 `os.path.basename(path)` 复用已净化的名称。

验证：在 Windows 沙箱中 `python -m pytest tests/ -q` 全部 8 项通过；另外用一次性脚本（已删除）验证了验收标准 1–4：`save("CON.txt"/"NUL.log"/"lpt1.tar.gz"/...)` 均抛 `InvalidNameError` 且目录为空、`sanitize("report.")=="report"` 且连写 `report`/`report.` 后 `list_names()==["report"]`、`save("...")` 抛 `InvalidNameError`、`console.txt`/`mycon`/`com10.log` 正常读写。工作区最终仅有三个实现文件被修改，无残留调试文件或缓存。