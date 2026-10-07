## 问题定位

在真实 Windows（沙箱即 Windows，Python 3.9/MSC）上复现了三类事故：

1. `rules.is_reserved()` 用 `name.strip().upper() in RESERVED_BASE_NAMES` 整体比较，漏掉了 Win32「只看第一个点之前的基名」规则，导致 `CON.txt`、`NUL.log`、`lpt1.tar.gz` 被判定合法；实测 `open(root/'con.txt','wb')` 会成功写进 CON 设备（目录里出现一个读不回来的条目）。
2. `sanitize()` 没有去掉 Windows 会静默丢弃的尾部点/空格（`rules.TRAILING_CHARS` 定义了却没人用），实测写 `report.` 落盘成 `report`，于是 `report.`/`report` 被记成两个名字、磁盘上只有一个条目。
3. `...`、纯空白这类输入净化后为空却仍继续走到写盘阶段，抛出底层 `PermissionError`，调用方无法区分「名称非法」与「磁盘故障」。

## 修改内容（仅 `wsafename/` 内源码）

- **`rules.py`**
  - 新增 `device_base_name(name)`：取第一个 `.` 之前的段并去首尾空白，即 Win32 实际比较的那一段。
  - `is_reserved()` 改为按该基名忽略大小写比较：`CON`/`CON.txt`/`con.tar.gz`/`CON .txt` → True；`console.txt`/`mycon`/`com10.log`/`lpt10`/`.hidden` → False（`RESERVED_BASE_NAMES` 内容未动）。
  - 新增 `has_trailing_chars()`，`is_valid()` 增加「以点或空格结尾即不可直接使用」的判断。
- **`sanitize.py`**：处理顺序变为 去首尾空白 → 替换非法字符 → `rstrip(" .")` → 截断到 255 后**再次** `rstrip(" .")`（截断可能把点/空格暴露到末尾）→ 空结果抛 `InvalidNameError` → 结果是保留设备名也抛 `InvalidNameError`（符合其既有文档「净化结果不可用时抛 InvalidNameError」）。`sanitize("report.") == "report"`，`sanitize("...")`/`sanitize("   ")`/`sanitize("CON.txt")` 抛 `InvalidNameError`。
- **`store.py`**：`save` 在触碰磁盘前完成净化+校验（非法名称不会留下任何条目，磁盘故障才会抛 OSError）；`exists`/`delete` 对不可用名称保持既有的 `False` 语义（而不是把 InvalidNameError 透传出去）；`load`/`target_path` 对非法名称抛 `InvalidNameError`；`delete` 不再重复调用 sanitize。
- **`__init__.py`**：附加导出 `TRAILING_CHARS`、`has_trailing_chars`、`device_base_name`（纯增量，未改动任何既有导出与签名）。

## 验证

- 仓库自带测试 `tests/`（未改动）8 passed。
- 一次性脚本（未落盘到仓库）在 Windows 上验证全部验收标准：`save("CON.txt"/"NUL.log"/"lpt1.tar.gz"/"..."/"   ")` 均抛 `InvalidNameError` 且 `os.listdir(root) == []`、`list_names() == []`；`save("report")` + `save("report.")` 后 `list_names() == ["report"]` 且磁盘只有一个条目；`console.txt`/`mycon`/`com10.log`/中文名照常读写删除。
- 仅使用标准库，无新增依赖；工作区无临时文件/缓存残留。