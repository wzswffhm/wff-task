## 问题定位

对照三个现象，在 `wrotate/` 里找到 4 处缺陷：

1. **`fsutil.move` 用 `os.rename`** —— Windows 上目标已存在时抛 `FileExistsError`（POSIX 才是静默替换），与该函数「目标已存在时也要成功」的文档契约相违背。这就是服务重启后首轮轮转直接失败的原因。
2. **`rotate` 按序号升序搬运** —— `app.log.1 → .2` 会把还没搬走的 `.2` 覆盖掉，世代内容丢失；即使换了 `os.replace` 也只是把「报错」变成「静默丢日志」。
3. **`rotate` 没有回滚** —— 中途失败时已搬走的和没搬的混在一起，序号出现空洞。
4. **`prune` 按文件名字典序排序** —— 且 `sorted(reverse=True)` 后取 `[keep:]`，实际删掉的是**序号最小（最新）**的那些：复现出 `keep=10` 时删 `app.log.1`、留 `app.log.11`。`fsutil.rotation_names` 同样是字典序，与 `Rotator.rotations()` 文档写的「按序号升序」不符。

## 修改内容

**`wrotate/fsutil.py`**
- `move`：`os.rename` → `os.replace`，在 Windows / POSIX 上都以「替换目标」语义完成移动，签名与返回值不变。
- `rotation_names`：改为 `sorted(names, key=rotation_index)`，真正按序号升序。

**`wrotate/rotator.py`**
- `rotate` 重写为事务：先生成计划（按序号升序，返回值顺序与既有实现完全一致），执行时**从最大序号往最小序号**搬，最后才动当前日志，因此每一步的目标序号都已被腾空；任何一步抛异常就调用 `_rollback` 逆向撤销已完成的搬运并重新抛出原异常，成功后才清理备份。
- 新增内部 `_step` / `_backup_name` / `_rollback` / `_drop_backups`：若目标序号上确实还压着残留（例如快照过期、并发产生），残留会先被挪到 `.wrotate-backup` 名上，成功则删除、失败则原样放回，保证回滚不丢数据。该后缀非纯数字，不会被 `rotation_names` 误认成世代。内部暂存刻意走 `os.replace` 而非 `fsutil.move`，以免干扰调用方对 `fsutil.move` 的注入/计数（故障注入测试仍能命中预期的那一步）。
- `prune`：改为按 `fsutil.rotation_index` **降序**排序，删除 `ordered[:max(0, len-keep)]`，即保留序号最小的 `keep` 份、从大到小删掉最老的；`keep` 负数按 0 处理，`keep` 大于现存份数时不删任何东西（原 `[keep:]` 写法在 `keep > len` 时会因负索引误删）。
- `rotate` / `prune` / `rotate_and_prune` / `fsutil.move` 的签名、返回值顺序、`app.log` 不存在时返回 `[]`、以及 `rotate_and_prune` 无可轮转时抛 `RotationError` 的既有语义全部保持不变。

## 验证

仓库自带 4 个测试全部通过。另用一次性脚本（已删除，未留在仓库内）覆盖验收标准：`move` 覆盖已存在目标；残留时各世代正确接力（`.1=current / .2=one / .3=stale`）；序号有空洞；在第 1/2/3/4 步分别注入 `fsutil.move` 故障后目录内容与调用前逐字节一致、全部步骤失败也不留痕迹、残留被覆盖的场景回滚后残留原样归位；`keep=10` 时保留 `app.log.1`~`app.log.10`、删除 15~11；`keep=0` / `keep<0` / `keep>份数`；`rotate_and_prune` 组合；`rotations()` 按序号排序；连续 8 轮轮转内容一直接力正确；不相干文件（`app.log.txt`、`app.logx.1`、`other.log`）不受影响；相对路径可用。工作区最终只有这两个源文件被修改，无临时文件与 `__pycache__` 残留，未改动 `tests/`。
