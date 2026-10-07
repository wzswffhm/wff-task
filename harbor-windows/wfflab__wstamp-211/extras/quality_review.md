# 质量自查报告 —— wfflab__wstamp-211

出题人自查（2026-10-02），对照《Windows 专项 Coding Bench 数据采购》验收门禁。

## 1. 结构与身份

- 五件套齐全（task.toml / instruction.md / environment/ / solution/ / tests/）
  + platform_import.json + extras/。
- 身份三元组四处一致：task_id=`wfflab__wstamp-211`、task_version=1.0、
  task_hash=`9a381fd5cce506e25a8e576028ce8dc299bb835e366375554f1e24ad112b2dea`
  （task.toml 注释 / swelive_spec / platform_import / manifest）。
- 镜像引用三处一致：`wfflab/wstamp-windows-bench:wfflab__wstamp-211-v1.0`；
  Digest = PENDING_BUILD（待构建，不阻塞静态验收）。

## 2. 红绿分离（本机实测，真实 Windows 文件系统）

| 副本 | 内容 | 结果 |
|---|---|---|
| A | base + 隐藏测试 | **8 failed（全部 F2P）/ 8 passed（全部 P2P）** |
| B | base + 隐藏测试 + oracle | **19 passed（16 隐藏 + 3 可见）** |

可见测试 test_wstamp_basic.py 在 base 上 3/3 通过（不进入判分）。

## 3. 对照证据（extras/evidence/）

- no-change ×3 = 0.0；golden ×3 = 1.0；clean_room no-change 0.0 / golden 1.0
- 反例 ×3 全 0.0（只比内容 / float 秒精度 / 无属性事务）
- 等价实现 1.0（显式字节流 + chmod 解只读 + 目录时间统一回写）
- L2 回归：nochg 0.0（pytest_rc=1）/ golden 1.0（pytest_rc=0）

## 4. Windows 价值（反事实判定）

换 Linux 后：(1) 只读语义由权限位决定，评测语境 utime 永远成功，属性事务不存在；
(2) 隐藏属性无对应物；(3) st_ctime 是元数据变更时间而非创建时间，created 语义不同；
(4) 属性 API 必须换实现。实现 / 根因 / Evaluator 三者全变，判定「保留」。

## 5. 区分度设计依据（8.2 预判）

选题直接来自多模型运行数据：Qwen3.8-Max-0902 在全部已测题中唯一的失手模式是
wsync-142 的 `test_sync_is_idempotent_and_preserves_source_mtime`（3 轮挂 2 次），
其根因是「同步状态只比较内容、漏掉 mtime 回写」。本题把这一家族做成显式契约
（验收标准第 4 条），并叠加三条同族不变量（目录 mtime 恢复顺序、逐纳秒往返、
属性事务次序），其余考点全部位于 Opus 的已验证可靠区（wencoding-206 v2.0 上
Opus 27/27×3）。红线自查：所有语义均已在 instruction.md 验收标准中显式声明，
无题面未声明要求、无冷门单点陷阱。

## 6. 泄漏检查

- Agent 可见环境 = environment/workspace/，不含 solution/ 与隐藏测试；
- Dockerfile 构建上下文不含答案；baseline commit 仅一个；
- instruction.md 通过泄漏信号扫描（validate_package [题面泄漏] PASS）。
