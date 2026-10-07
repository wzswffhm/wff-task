修复了 wpublish 中导致「只读发布未覆盖整棵子树」的三处缺陷，并顺带修正了让判定失效的 icacls 输出解析问题。全部改动仅限 `wpublish/` 包内源码，`tests/` 未做任何改动，仓库内没有留下临时文件。

1) `wpublish/publish.py` —— 发布动作现在真正覆盖整棵子树
   - `deny(dst_dir, principal, READONLY_SPEC, recursive=True)`：加上 `/T`，发布时已存在的各级子目录拿到**显式**拒绝项；根/子目录上的 `(OI)(CI)` 继承标志保证发布之后新建的文件与目录自动继承同一条拒绝项。
   - 实测发现 `icacls /T` 只会让**文件**继承父目录的项、文件自身拿不到显式拒绝项，因此发布流程再走一遍目录树，对每个已存在的文件按 `READONLY_FILE_SPEC`（`(RX)`，文件不能带继承标志）补一条显式拒绝项。
   - 新增公开常量 `READONLY_FILE_SPEC`，并把 `READONLY_SPEC` 的注释改成与「下发拒绝项 + 继承标志」的实际用法一致。签名与返回值语义未变。

2) `wpublish/rights.py` —— `can_write` 遵守显式拒绝优先
   - 原实现把 deny 集合丢弃（`allow, _deny = ...`），只要存在允许项就返回可写。现在与 `can_read` 同构：`deny & WRITE_RIGHTS` 命中即返回 `False`，哪怕同时存在 `(M)`/`(F)` 允许项。
   - 主体比较增加容错：去掉字面 SID 的 `*` 前缀并统一大小写，避免 `*S-1-5-32-546` 与回显形式被判成两个主体。

3) `wpublish/icacls.py` —— 显式项与继承项分开，主体名解析正确
   - `list_explicit_aces` 不再直接返回 `list_aces`，而是过滤掉 icacls 标记为 `(I)` 的继承项，审计报表不会再把父目录继承来的权限当成本目录的「显式授予」。
   - `parse_aces` 修掉一个会让判定全线失灵的问题：icacls 把首条 ACE 与目标路径打印在同一行（`C:\dir BUILTIN\Users:(RX)`），原来会把路径一起吃进主体名，导致首条（通常是拒绝项）永远匹配不上。现按续行 ACE 的对齐列剥离路径前缀（路径或主体名含空格都正确），只有一条 ACE 时退化为取冒号前最后一个词；同时支持 `(RX,WD)` 这类逗号分隔的权限组合。
   - `run` 的报错信息补上 stderr，便于排错；`deny` 文档说明 `recursive`/`/T` 的作用。

4) `wpublish/__init__.py` —— 导出新增的 `READONLY_FILE_SPEC`（纯增量，未改动既有导出）。

验证（Windows + 真实 icacls，未新增任何测试文件，全部用一次性命令执行）：仓库自带 7 个测试全部通过；五条验收标准逐条实测通过——已存在的目录/文件都带显式拒绝项、发布后新建的文件与目录继承到拒绝项、允许项与拒绝项并存时 `can_write` 为 `False`、`list_explicit_aces` 不含继承项、`audit` 对刚发布完的目录返回 `[]`；另外确认 `audit` 仍能检出未发布目录中被单独授写的文件（没有放宽既有行为）。