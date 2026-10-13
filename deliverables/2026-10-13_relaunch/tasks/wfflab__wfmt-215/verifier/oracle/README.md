# Oracle 参考解（判分侧）

- `reference/wfmt/`：`environment/workspace/wfmt/` 的完整替换版本；在候选运行结束后
  由评测侧安装到工作区，用于 Golden / Oracle 控制跑。
- `solve.ps1`：安装入口；按 `-ReferenceRoot` → `$env:WFMT_REFERENCE_ROOT` →
  `C:\solution\reference\wfmt` → 本目录 `reference/wfmt` 的顺序定位参考实现。
- `oracle.patch`：与 `reference/` 等价的补丁留档，仅供审计比对。

这些文件**只**用于判分与审计，不进入 Agent 可见题包。
