# Oracle 参考解（判分侧）

- `reference/wpeimg/`：`environment/workspace/wpeimg/` 的完整替换版本；在候选
  运行结束后由评测侧安装到工作区，用于 Golden / Oracle 控制跑。
- `solve.ps1`：安装入口；按 `-ReferenceRoot` → `$env:WPEIMG_REFERENCE_ROOT` →
  `<脚本目录>\reference\wpeimg` → `C:\verifier\wfflab__wpeimg-219\oracle\reference\wpeimg`
  → `C:\solution\reference\wpeimg` 的顺序定位参考实现。
- `README-original.md`：参考实现遵循的权威行为与错误分类判据，含校验和算法。

这些文件**只**用于判分与审计，不进入 Agent 可见题包。
