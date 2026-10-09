# wchunk：容器格式实现与样本不兼容

`wchunk` 是我们采集器落盘用的**分块容器格式**实现：一个文件由「文件头 +
若干条记录 + 尾部校验和」组成，每条记录携带一个整数 `tag` 和一段二进制
`payload`。外部还有一批已经落盘的历史文件（例如
`assets/sample.wchk`），下游解析器正是按它们实现的。

## 现象（仓库 issue #216）

1. **读不了真实样本**：`wchunk.verify(open("assets/sample.wchk","rb").read())`
   返回 `False`；`unpack()` 抛错或返回明显错误的结果。而**我们自己**
   `pack()` 出来的文件又能被自己 `unpack()` 读回来——所以可见冒烟测试
   一直是绿的，问题被掩盖了。
2. **无法原样回写**：即便勉强解析出样本，`pack(unpack(sample))` 得到的字节
   与原文件**不一致**（下游按字节 hash 做增量同步，不一致就等于损坏）。
3. **校验和对不上**：`compute_crc()` 的返回值与公开标准不符——拿它算常见
   测试向量得到的值和任何标准 32 位 CRC 都对不上。
4. **容器长度对不上**：生成的容器与样本在**同样的记录集合**下长度不同，
   下游按字节偏移解析，长度不一致就整体错位。
5. **结构错误分类不准**：截断、被篡改的文件有时抛 `WChunkError` 却给出
   错误的 `kind`，有时干脆被当成正常数据读完。

## 任务

修复 `wchunk` 包，使其满足下列**验收标准**。请注意：仓库里的
`docs/FORMAT.md` 是**早期草稿**，与真实布局已经不一致；
`assets/` 下的样本才是唯一权威依据。

## 验收标准

### A. 样本兼容（硬门槛）

- `verify(sample)` 必须为 `True`（`sample` = `assets/sample.wchk` 的全部字节）；
- `pack(unpack(sample)) == sample`，**逐字节一致**；
- 零记录样本 `assets/sample_empty.wchk` 同样要能 `verify` 通过并原样回写。

### B. 记录语义

- `unpack(data)` 返回 `[(tag, payload), ...]`，按文件中的顺序；
- `tag` 是非负整数，`payload` 是 `bytes`（空 `payload` 合法）；
- `pack(records)` 接受同构的 `(tag, payload)` 序列，产出的容器必须能被
  `unpack` 与 `iter_records` 正确读回。

### C. 记录布局

- 记录区的字节布局必须与**样本的实际字节**一致，而不是以草稿的描述为准；
- 对同一组记录，`pack()` 产出的容器长度必须与真实布局规律一致。

### D. 校验和

- 容器尾部的校验和必须与样本一致，且必须是某个**通用的 32 位 CRC 变体**
  ——即：它是数据的一个确定函数，对任意输入（而不只是样本）都成立；
- 校验和的覆盖范围必须包含**文件头与全部记录**；
- 被篡改过**内容**的容器，`verify()` 必须返回 `False`。

### E. 错误分类

所有「结构 / 完整性」问题都必须抛 `WChunkError`（而不是
`ValueError` / `struct.error` / `IndexError` 等），且 `err.kind` 需能区分
问题类别：

| kind | 含义 |
|---|---|
| `"magic"` | 魔数不匹配 |
| `"version"` | 版本号不受支持 |
| `"truncated"` | 数据在读到完整结构之前就结束了 |
| `"structure"` | 结构自相矛盾（如记录区长度与记录数不符） |
| `"checksum"` | 尾部校验和对不上 |

`verify(data)` **不得抛异常**：任何问题都返回 `False`。

### F. 流式读取

- `iter_records(fileobj)` 必须**惰性**产出记录，且**不得把整个容器读进
  内存**：只允许用固定大小的 `read(n)`（`n` 为正整数）向文件对象要数据，
  禁止 `read()`（无参）、`read(-1)`、`readlines()` 之类的整体读取。
- 取完最后一条记录后，仍要校验尾部校验和；校验失败抛
  `WChunkError(kind="checksum")`。

### G. 不得回归

- 可见冒烟测试 `tests/test_wchunk_basic.py` 必须继续通过；
- 公开 API 的名称与签名保持不变（`pack` / `unpack` / `verify` /
  `iter_records` / `read_all` / `compute_crc` / `WChunkError` 等）。

## 提交

直接修改 `wchunk/` 下的源码即可，无需改测试文件。