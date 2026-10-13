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

## 任务

修复 `wpeimg` 包，使其满足下面的验收标准。

## 验收标准

### A. 映像描述

`inspect(data)` 必须返回一个字典，至少包含这些键，取值必须与映像的真实内容
一致：

`machine`、`is_pe32_plus`、`number_of_sections`、`entry_point_rva`、
`image_base`、`section_alignment`、`file_alignment`、`size_of_image`、
`size_of_headers`、`checksum`、`sections`。

`sections` 是按节区表顺序排列的列表，每一项是字典，键为
`name`、`virtual_address`、`virtual_size`、`raw_pointer`、`raw_size`、
`characteristics`；`name` 是去掉尾部 `NUL` 之后的 `str`。

必须同时支持两种可选头布局：

- `0x10B`（PE32）：`ImageBase` 是 **4 字节**；
- `0x20B`（PE32+）：`ImageBase` 是 **8 字节**。

`is_pe32_plus` 要如实反映读到的是哪一种。节区表的位置由
`SizeOfOptionalHeader` 决定，不是固定偏移。

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

### G. 不得回归

- 可见冒烟测试 `environment/workspace/tests/test_wpeimg_basic.py` 必须继续
  通过，且不得修改它；
- `wpeimg.__all__` 必须仍然**恰好**是这 14 个名字，不得增删：

  ```
  ChecksumAccumulator, KIND_CHECKSUM, KIND_DOS, KIND_OPTIONAL,
  KIND_SIGNATURE, KIND_STRUCTURE, KIND_TRUNCATED, KINDS, WImgError,
  compute_checksum, inspect, iter_sections, rva_to_offset, verify
  ```

- `KINDS` 仍然恰好包含上面那六个 kind 字符串；
- `WImgError(kind)` 的 `kind` 属性保留传入值，`str(e)` 里带上消息；传入未知
  kind 时抛 `ValueError`；
- 公开函数的名称与调用方式不变。

## 提交

直接改 `wpeimg/` 下的源码即可，不要动测试文件和 `assets/`。

如果你在改的过程中跑过验证，请在提交说明里写清楚**跑了什么命令、改之前看到
什么、改之后看到什么**，方便复核。
