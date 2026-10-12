# wlogseg

`wlogseg` 是一个分段追加日志容器的读写实现：容器由定长文件头、若干变长段、尾部段索引和尾部校验和组成。写入侧一次性拼装，读取侧支持整体解析与流式解析两种方式。

## 目录

- `wlogseg/` —— 实现代码
- `assets/` —— 产线导出的参考容器，作为格式的权威样本
- `docs/FORMAT.md` —— 格式说明（早期草稿，部分内容已过时）
- `tests/` —— 冒烟测试

## 使用

```python
from wlogseg import pack, unpack, verify, iter_segments

blob = pack([(1, b"alpha"), (2, b"beta")])
assert verify(blob)
assert unpack(blob) == [(1, b"alpha"), (2, b"beta")]
```

## 测试

```bash
python -m pytest tests -q
```
