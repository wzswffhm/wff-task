# wtextio

工具链在 Windows 上生成文本、在别处消费它。本库把编码选择集中到一处。

```python
from wtextio import read_text, write_text

write_text("report.csv", "名称,数量\n螺丝,12\n")
read_text("report.csv")
```

## 组成

| 模块 | 职责 |
|---|---|
| `wtextio.codec` | 编码别名与默认策略 |
| `wtextio.writer` | 文本写入与追加 |
| `wtextio.reader` | 文本读回与 BOM 探测 |

## 约束

- 只用 Python 标准库
- 默认编码为 UTF-8，不随平台变化
- 落盘换行固定为 CRLF
- 断网可运行
