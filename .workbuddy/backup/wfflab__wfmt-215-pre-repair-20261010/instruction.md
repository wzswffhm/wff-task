# wfmt：容器格式实现与样本不兼容

`wfmt` 是我们采集器落盘用的**记录容器格式**实现：一个文件由「文件头 +
若干条记录 + 尾部校验和」组成，每条记录携带一个整数 `tag` 和一段二进制
`payload`。外部还有一批已经落盘的历史文件（例如
`assets/sample.wfmt`），下游解析器正是按它们实现的。

## 现象（仓库 issue #215）

1. **读不了真实样本**：`wfmt.verify(open("assets/sample.wfmt","rb").read())`
   返回 `False`；`unpack()` 抛错或返回明显错误的结果。而**我们自己**
   `pack()` 出来的文件又能被自己 `unpack()` 读回来——所以可见冒烟测试
   一直是绿的，问题被掩盖了。
2. **无法原样回写**：即便勉强解析出样本，`pack(unpack(sample))` 得到的字节
   与原文件**不一致**（下游按字节 hash 做增量同步，不一致就等于损坏）。
3. **校验和对不上**：`compute_crc()` 的返回值与公开标准不符——拿它算常见
   测试向量得到的值和任何标准 32 位 CRC 都对不上。
4. **大文件爆内存**：`iter_records()` 读一个几百 MB 的容器时会把整份数据
   读进内存（OOM），它本该是流式的。
5. **损坏文件不报错**：截断、被篡改的文件有时抛出 `ValueError` /
   `struct.error` 之类的临时异常，有时直接被当成正常数据处理。

## 任务

修复 `wfmt` 包，使其满足下列**验收标准**。请注意：仓库里的
`docs/FORMAT.md` 是**早期草稿**，与真实布局已经不一致；
`assets/` 下的样本才是唯一权威依据。

## 验收标准

### A. 样本兼容（硬门槛）

- `verify(sample)` 必须为 `True`（`sample` = `assets/sample.wfmt` 的全部字节）；
- `pack(unpack(sample)) == sample`，**逐字节一致**；
- 零记录样本 `assets/sample_empty.wfmt` 同样要能 `verify` 通过并原样回写。

### B. 记录语义

- `unpack(data)` 返回 `[(tag, payload), ...]`，按文件中的顺序；
- `tag` 是非负整数，`payload` 是 `bytes`（空 `payload` 合法）；
- `pack(records)` 接受同构的 `(tag, payload)` 序列，产出的容器必须能被
  `unpack` 与 `iter_records` 正确读回。

### C. 校验和

- 容器尾部的校验和必须与样本一致，且必须是某个**通用的 32 位 CRC 变体**
  ——即：它是数据的一个确定函数，对任意输入（而不只是样本）都成立。
- 被篡改过**内容**的容器，`verify()` 必须返回 `False`。

### D. 错误分类

所有「结构 / 完整性」问题都必须抛 `WFormatError`（而不是
`ValueError` / `struct.error` / `IndexError` 等），且 `err.kind` 需能区分
问题类别：

| kind | 含义 |
|---|---|
| `"magic"` | 魔数不匹配 |
| `"version"` | 版本号不受支持 |
| `"truncated"` | 数据在读到完整结构之前就结束了 |
| `"structure"` | 结构自相矛盾（如记录数与实际长度不符） |
| `"varint"` | 变长整数编码非法 |
| `"checksum"` | 尾部校验和对不上 |

`verify(data)` **不得抛异常**：任何问题都返回 `False`。

### E. 流式读取

- `iter_records(fileobj)` 必须**惰性**产出记录，且**不得把整个容器读进
  内存**：只允许用固定大小的 `read(n)`（`n` 为正整数）向文件对象要数据，
  禁止 `read()`（无参）、`read(-1)`、`readlines()` 之类的整体读取。
- 取完最后一条记录后，仍要校验尾部校验和；校验失败抛
  `WFormatError(kind="checksum")`。

### F. 不得回归

- 可见冒烟测试 `tests/test_wfmt_basic.py` 必须继续通过；
- 公开 API 的名称与签名保持不变（`pack` / `unpack` / `verify` /
  `iter_records` / `read_all` / `WFormatError` 等）。

## 提交

直接修改 `wfmt/` 下的源码即可，无需改测试文件。
