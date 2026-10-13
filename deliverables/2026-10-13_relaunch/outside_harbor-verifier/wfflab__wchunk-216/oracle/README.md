# Oracle 参考解（判分侧）

- `reference/wchunk/`：`environment/workspace/wchunk/` 的完整替换版本；在候选运行结束后
  由评测侧安装到工作区，用于 Golden / Oracle 控制跑。
- `solve.ps1`：安装入口；按 `-ReferenceRoot` → `$env:WCHUNK_REFERENCE_ROOT` →
  `C:\solution\reference\wchunk` → 本目录 `reference/wchunk` 的顺序定位参考实现。
- `README-original.md`：返修前的 solution 说明原文，仅供审计比对。

这些文件**只**用于判分与审计，不进入 Agent 可见题包。
