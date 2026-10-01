# wsafename —— 上传服务把 Windows 保留设备名当成普通文件名

## 背景

`wsafename` 是上传服务用来把用户提交的名称净化后落盘的库。同一套代码在 Linux 上传节点上跑了很久都正常，迁到 Windows 文件服务器之后开始出现丢文件与建不出文件的事故。

## 现象

1. 用户上传名为 `CON.txt`、`lpt1.log` 的文件时，净化函数判定名称合法并放行；落盘时要么抛异常中断整批上传，要么写进一个既不是文件也不是目录的目标，之后再也读不出来。

2. `report.` 与 `report` 会被当成两个不同的名称记录在案，但磁盘上只会出现一个条目，导致清单与实际内容对不上。

3. 名为 `...` 或只有空白的输入会一路走到写盘阶段才失败，抛出的是底层 OSError，调用方无法区分「名称非法」与「磁盘故障」。

## 目标

让 `wsafename` 在上述这些真实的 Windows 场景下都能给出正确结果：

1. 保留设备名的判定必须按 Win32 规则只看**第一个点之前**的那一段：`CON`、`CON.txt`、`con.tar.gz` 都要被拒绝，而 `console.txt`、`mycon`、`com10.log` 必须照常允许。

2. 落盘名称必须是确定的：净化阶段就把 Windows 会静默丢弃的尾部点与空格去掉，让 `report.` 与 `report` 得到同一个落盘名。

3. 净化后不再剩下可用字符的名称必须被明确拒绝，抛出 `InvalidNameError`，不得把底层错误直接透传给调用方。

## 功能边界

- **需要支持**
  - `FileStore.save` / `load` / `delete` / `list_names` / `target_path` 在 Windows 目标文件系统上的行为
  - `sanitize` 对上述三类输入的确定性输出
- **不需要处理**
  - 路径分隔符、UNC 与超过 MAX_PATH 的超长路径
  - 权限提升与 UAC
  - 多进程同时写入同一个名称

## 约束

- 目标环境：Windows Server 2022（x64），Python 3.12
- 只允许使用 Python 标准库，**不得引入新的第三方运行时依赖**
- 不得改变 `sanitize` / `is_valid` / `is_reserved` / `FileStore` 的公开签名与既有语义
- 不得修改或删除仓库自带的测试，不得为了通过而放宽既有行为
- 必须保持断网可运行

## 允许修改范围

`wsafename/` 包内的源码。`tests/` 下只允许新增测试文件，不得改动既有测试。

## 验收标准（用户可见）

1. 以 `CON.txt`、`NUL.log`、`lpt1.tar.gz` 等名称调用 `save` 时抛 `InvalidNameError`，且目标目录里不会出现任何条目。

2. `sanitize("report.")` 返回 `"report"`；先写 `report` 再写 `report.` 之后，`list_names()` 只包含一个名称。

3. `save("...")` 抛 `InvalidNameError`。

4. `console.txt`、`mycon`、`com10.log` 这类含保留字片段、但基名并不保留的名称照常可用。
