# Oracle 参考解（判分侧）

- `reference/wlogseg/`：`environment/workspace/wlogseg/` 的完整替换版本；在候选运行结束后
  由评测侧安装到工作区，用于 Golden / Oracle 控制跑。
- `solve.ps1`：安装入口；按 `-ReferenceRoot` → `$env:WLOGSEG_REFERENCE_ROOT` →
  `C:\solution\reference\wlogseg` → 本目录 `reference/wlogseg` 的顺序定位参考实现。
- `README-original.md`：参考实现与 `docs/FORMAT.md` 草稿的差异说明，含错误分类判据。

这些文件**只**用于判分与审计，不进入 Agent 可见题包。
