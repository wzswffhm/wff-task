# wpeimg：PE 映像结构校验与 RVA 映射实现有缺陷

`wpeimg` 是我们镜像巡检工具里负责**读取 Windows PE 映像**的包。给它一份映像
的字节，它要能报出这份映像面向哪种机器、节区怎么排、某个相对虚拟地址
（RVA）落在文件的哪个偏移上，以及映像里记的校验和还对不对。

`assets/` 下有两份冻结样本，它们是唯一的权威依据：

| 样本 | 说明 |
|---|---|
| `amd64-module.bin` | 真实 64 位模块映像 |
| `i386-module.bin` | 32 位控制台映像 |

`docs/FORMAT.md` 是当初写这个包时随手记的草稿，**已经和真实布局对不上**，
不要拿它当依据。

## 现象（仓库 issue #219）

1. **两个样本都过不了 `verify()`**。`verify()` 对 `amd64-module.bin` 和
   `i386-module.bin` 都返回 `False`，`inspect()` 直接抛错。用别的工具看，
   这两份文件本身是好的。
2. **32 位映像的字段明显不对**。`inspect("i386-module.bin")` 报出来的
   `image_base` 是个天文数字，`is_pe32_plus` 也说它是 64 位。
3. **64 位映像的节区整段错位**。同样是 `amd64-module.bin`，报出来的节区名字、
   地址和真实节区对不上。
4. **校验和算不对**。`compute_checksum()` 给出的值和映像里记的、以及系统工具
   给出的值都不一样；改动映像里 `CheckSum` 那四个字节，算出来的值也跟着变。
5. **自相矛盾的映像被放行**。手工把某个节区声明的大小改到超出文件末尾，或者
   让两个节区占同一段地址，`verify()` 照样返回 `True`。
6. **错误分类不准**。节区表被砍掉一半时抛的是 `struct.error`；映像结构已经
   损坏、校验和也不对时，报出来的 `kind` 是 `"checksum"`。
7. **RVA 映射基本没用**。拿一个确定落在节区里的 RVA 去问
   `rva_to_offset()`，返回 `None`。
8. **`iter_sections()` 会把整个映像读进内存**。
9. **映像的目录表读不出来**。`inspect()` 报出来的 `data_directories` 两个样本
   都对不上：32 位那份整张表都错位，64 位那份把没声明的槽位也当成有声明的读了。
10. **带 Authenticode 签名的映像被误判**。`amd64-module.bin` 尾部明明带着一段
    真实的签名数据，`has_authenticode_signature` 却报 `False`。

## 任务

修复 `wpeimg` 包，使其满足下面的验收标准。

## 验收标准

### A. 映像描述

`inspect(data)` 必须返回一个字典，至少包含这些键，取值必须与映像的真实内容
一致：

`machine`、`is_pe32_plus`、`number_of_sections`、`entry_point_rva`、
`image_base`、`section_alignment`、`file_alignment`、`size_of_image`、
`size_of_headers`、`checksum`、`sections`、`data_directories`、
`has_authenticode_signature`。

`sections` 是按节区表顺序排列的列表，每一项是字典，键为
`name`、`virtual_address`、`virtual_size`、`raw_pointer`、`raw_size`、
`characteristics`；`name` 是去掉尾部 `NUL` 之后的 `str`。

必须同时支持两种可选头布局：

- `0x10B`（PE32）：`ImageBase` 是 **4 字节**；
- `0x20B`（PE32+）：`ImageBase` 是 **8 字节**。

`is_pe32_plus` 要如实反映读到的是哪一种。节区表的位置由
`SizeOfOptionalHeader` 决定，不是固定偏移。

### A2. 目录表与 Authenticode 尾部

`data_directories` 是**位置语义**的目录数组，必须按 PE 格式的固定顺序给出，
长度固定为 16，每一项是字典，键为 `name`、`virtual_address`、`size`：

```
0 export        1 import        2 resource      3 exception
4 certificate   5 relocation    6 debug         7 architecture
8 global_ptr    9 tls          10 load_config  11 bound_import
12 iat         13 delay_import 14 clr_runtime  15 reserved
```

规则：

- 数组起始位置随布局变化——PE32 在可选头偏移 **96**，PE32+ 在 **112**；
- 数组长度由可选头里的 `NumberOfRvaAndSizes` 决定，**不是**恒定 16，也**不是**
  由 `SizeOfOptionalHeader` 反推；
- 声明数超过 16 时只取前 16 项；不足 16 时，**未声明的槽位按 `virtual_address`
  与 `size` 都为 0 补齐**，输出长度始终是 16；
- 声明数超出了可选头（`SizeOfOptionalHeader`）或文件本身实际容纳的字节时，
  越界的槽位按 0 处理，**不得抛异常**。

`has_authenticode_signature`（`bool`）表示映像是否**真的**带有 Authenticode
签名数据：

- 取 `certificate` 目录项（索引 4）。它的第一个字段在证书表这一项上是
  **文件偏移**，不是 RVA；
- 该项两个字段任一为 0 → `False`；
- 声明的区间 `[offset, offset + size)` 超出文件范围 → `False`（只是记了个数字，
  文件里没有对应的字节）；
- 否则 → `True`。

映像**尾部多出来的字节是合法的**：真实映像普遍带签名或 overlay，不得因此报错。


### B. 校验和

`compute_checksum(data)` 必须给出与 **Windows 自己的映像校验和**完全相同的
值：即系统库 `imagehlp.dll` 导出的 `MapFileAndCheckSumW` 对同一份文件算出的
那个数。它不是 CRC，也不是简单的字节和。

结果必须是一个确定函数：只取决于传入的字节，对任意输入都成立，不是只对
样本成立。

`imagehlp!MapFileAndCheckSumW` 只作为你**自查时的参照**。实现本身**不得**
调用它，也不得调用 `ctypes`、起子进程、或读写任何进程外资源来得到这个数：
`wpeimg` 只允许依赖 Python 标准库里与操作系统无关的部分。

`ChecksumAccumulator` 是同一算法的增量形式：

- `update(chunk)` 追加一段字节，返回 `self`；
- `value(total_length)` 返回最终校验和（`int`），其中 `total_length` 是整个
  文件的长度；
- 把同样一串字节分块喂进去，`value()` 的结果必须与一次性计算完全相同；
- 累加器只负责它收到的那串字节；把 `CheckSum` 字段替换成 0 是**调用方**的
  事（`compute_checksum` 就负责这件事）。

### C. RVA 映射

`rva_to_offset(data, rva)` 返回该 RVA 对应的**文件偏移**，没有文件字节支撑时
返回 `None`：

- `rva < 0` → `None`；
- `rva < size_of_headers` → 直接返回 `rva`（映像头部在文件里就是从 0 开始
  原样存放的）；
- 否则在所有节区里找满足 `virtual_address <= rva < virtual_address +
  virtual_size` 的那一个：
  - `raw_size` 为 0，或 `rva - virtual_address >= raw_size` → `None`
    （这一段只有虚拟存在，文件里没有对应字节）；
  - 否则返回 `raw_pointer + (rva - virtual_address)`；
- 找不到节区 → `None`。

注意入参是 **RVA**，不是已经加过 `ImageBase` 的虚拟地址。

### D. 结构自检

头部读全之后，必须检查映像自身描述是否自洽。下面每一条被违反都要抛
`WImgError(kind="structure")`：

- 节区声明的文件区间 `raw_pointer + raw_size` 超出文件长度；
- 节区声明了文件字节（`raw_size` 非 0），但 `raw_pointer` 落在
  `SizeOfHeaders` 之内，也就是跟头部区域叠在一起；
- 两个节区的**虚拟**区间重叠；
- 两个节区的**文件**区间重叠；
- 节区 `virtual_address` 没有按 `SectionAlignment` 对齐；
- 节区 `raw_pointer` 没有按 `FileAlignment` 对齐；
- `SizeOfHeaders` 没有按 `FileAlignment` 对齐；
- `SizeOfHeaders` 小于节区表末尾偏移；
- `SizeOfImage` 小于「所有节区 `virtual_address + virtual_size` 的最大值按
  `SectionAlignment` 上取整」的结果。

映像**尾部多出来的字节是合法的**（真实映像普遍带 Authenticode 签名），
不得因为它报错。

### E. 错误分类

所有「结构 / 完整性」问题都必须抛 `WImgError`（而不是 `ValueError` /
`struct.error` / `IndexError`），且 `err.kind` 必须能区分下面六类：

| kind | 含义 |
|---|---|
| `"dos"` | 开头 `0x40` 字节里没有 `MZ` |
| `"signature"` | `e_lfanew` 指向处不是 `PE\0\0` |
| `"optional"` | 可选头幻数既不是 `0x10B` 也不是 `0x20B`，或 `SizeOfOptionalHeader` 装不下可选头 |
| `"truncated"` | 在读完某个必需的定长结构之前，数据就结束了 |
| `"structure"` | 头部齐全，但映像自身描述互相矛盾 |
| `"checksum"` | 结构完好，但记录的校验和与计算值不符 |

这六类 `kind` 是互斥的语义分类：每一个只描述它自己那一行的含义，不能拿别
的行去顶替它。

`CheckSum` 字段为 0 时，跳过校验和检查（视为「未记录」）。

`verify(data)` 是布尔包装：正常返回 `True`，任何问题返回 `False`，
**不得抛异常**（包括 `b""`、`b"MZ"` 这类残缺输入）。

### F. 流式读取

`iter_sections(fileobj)` 必须**惰性**产出节区，且**不得把整个映像读进内存**：
只允许用固定大小的 `read(n)`（`n` 为正整数）向文件对象要数据，禁止
`read()`（无参）、`read(-1)`、`readlines()` 这类整体读取。取第一条节区之前
读取的字节数必须有界。

### F2. Authenticode 签名内容

`signature_info(data)` 是**新增**的公开函数：给它一份映像的全部字节，它要说明
证书表里到底装了什么。证书表那个目录项指向一条 `WIN_CERTIFICATE` 记录，记录体
是一段 PKCS#7 `SignedData` 的 DER 数据。返回值必须是字典，至少包含这些键：

| 键 | 含义 |
|---|---|
| `present` | `bool`：证书表**真的**存在且能被文件字节支撑 |
| `offset` | 证书表在文件里的起始偏移（无签名时 `0`） |
| `size` | 证书表声明的大小（无签名时 `0`） |
| `declared_length` | `WIN_CERTIFICATE.dwLength`（无签名时 `0`） |
| `revision` | `WIN_CERTIFICATE.wRevision` |
| `certificate_type` | `WIN_CERTIFICATE.wCertificateType` |
| `content_type` | PKCS#7 `ContentInfo` 的 contentType **OID 点号字符串**；不是 PKCS#7 时为 `None` |
| `digest_algorithms` | `SignedData.digestAlgorithms` 里的算法**名称**列表 |
| `certificate_count` | `SignedData` 里携带的证书条数 |
| `signer_count` | `SignedData.signerInfos` 里的签名者条数 |

规则：

- 没有证书表、或证书表区间落在文件之外 → 所有字段取「无签名」值
  （`present=False`、计数为 `0`、`content_type=None`、列表为空），**不得抛异常**；
- `WIN_CERTIFICATE` 的 `dwLength` 小于 8、或大于证书表区间长度 → 抛
  `WImgError(kind="structure")`（记录自称的长度与文件对不上）；
- `wCertificateType` 不是 `0x0002`（PKCS#7 SignedData）时：`present` 仍为
  `True`，但 `content_type` 为 `None`、计数为 `0`，**不去解析**记录体；
- `digest_algorithms` 按 `SignedData` 中出现的顺序，用这些**通用名称**表示算法：
  `sha1`、`sha256`、`sha384`、`sha512`、`rsa`、`sha256WithRSA`、`sha1WithRSA`、
  `ec`、`ecdsaWithSHA256`；遇到表里没有的 OID 时原样给出点号字符串；
- `content_type` 必须按 OID 的值段解析成点号形式（`1.2.840.113549.1.7.2` 这种），
  不是十六进制也不是原始字节；
- 解析必须**自己完成**：不得依赖 `ctypes`、`subprocess`，也不得引入标准库以外的
  ASN.1 库。

### F3. 判分会拿真实 Windows 系统服务来对照

这一节不是新的实现要求，而是**告诉你判据从哪里来**，免得你把力气花在猜常量上：

- **映像校验和的权威值在判分时向 Windows 系统库现取**：判分侧会调用
  `imagehlp!MapFileAndCheckSumW`，对照的对象包括**判分时现场构造的映像变体**
  （在样本的节区数据上改字节、再按系统库给的值重写 `CheckSum`）。因此
  `compute_checksum()` 必须对**任意**输入成立，背下样本上那个数字没有用。
- **流式读取会在真实 Windows 文件句柄上测**：判分侧用
  `kernel32!CreateFileW` 打开映像，把该句柄接到 `iter_sections()` 上，并核对
  「取到第一条节区之前读取的字节数」在文件尾部被放大 8 倍后**完全不变**。
- 调用系统库的是**判分侧**。你的实现仍然**不得**导入 `ctypes` / `subprocess`
  或任何第三方 ASN.1 / PE 库——「契约由 Windows 定义」与「实现必须自包含」
  是两条独立要求，都要满足。

### G. 不得回归

- 可见冒烟测试 `environment/workspace/tests/test_wpeimg_basic.py` 必须继续
  通过，且不得修改它；
- `wpeimg.__all__` 必须仍然**恰好**是这 15 个名字，不得增删：

  ```
  ChecksumAccumulator, KIND_CHECKSUM, KIND_DOS, KIND_OPTIONAL,
  KIND_SIGNATURE, KIND_STRUCTURE, KIND_TRUNCATED, KINDS, WImgError,
  compute_checksum, inspect, iter_sections, rva_to_offset, signature_info,
  verify
  ```

- `KINDS` 仍然恰好包含上面那六个 kind 字符串；
- `WImgError(kind)` 的 `kind` 属性保留传入值，`str(e)` 里带上消息；传入未知
  kind 时抛 `ValueError`；
- 公开函数的名称与调用方式不变。

## 提交

直接改 `wpeimg/` 下的源码即可，不要动测试文件和 `assets/`。

如果你在改的过程中跑过验证，请在提交说明里写清楚**跑了什么命令、改之前看到
什么、改之后看到什么**，方便复核。
