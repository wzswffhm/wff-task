# 直接 Harbor Windows 标准题包结构

本结构取自 `harbor-record-33-direct-jobs-20261010.zip`，原包 SHA-256 为
`10c1504ef3f93c2fe0a4416a0eff3cda3e3e4fa177b74d48d0c0f8c5126b9361`。
后续质检和出题打包统一使用本结构，不使用 Demo 的平台包装目录。

```text
<zip-stem>/
  task.toml
  instruction.md
  environment/
    adapter.toml
    Dockerfile
    prepare.ps1
    validate_environment.ps1
    run.ps1
    restore.ps1
    cleanup.ps1
    workspace/
    assets/                    # 按任务需要
  solution/
    README.md
    solve.ps1 或 solve.bat
    reference/                 # 按任务需要
  tests/
    test.ps1
    run_tests.ps1
    aggregate_results.ps1
    judge.toml
    rubric.json
    required_testcases.json
    verifier/                  # 实际测试工程/脚本
  jobs/
    config.json
    lock.json
    result.json
    job.log
    <14 个 Harbor job 目录>/
```

14 个 job 必须由 job 内部元数据识别，随机目录名不是模型或 Agent 身份。数量固定为
Qwen 3、Opus 3、GLM 1、Kimi 1、Oracle 3、NOP 3。

用户口头所称“13 个文件夹”与明细相加不一致；质检以明细和参考包为准，固定检查 14 个 job。不得用泛化的“每模型次数不足”单独返修，但少于这 14 个原生 job 属于标准目录/证据缺件。

模型 job：

```text
<job>/
  config.json
  lock.json
  result.json
  trial.log
  agent/
    model-result.json
    trajectory.jsonl
  artifacts/
    manifest.json
  verifier/
    result.json
    reward.txt
    test-stdout.txt
    verifier.log
    trx/                       # 存在测试运行记录时保留
```

Oracle job 在共同文件外增加 `agent/oracle.txt` 和
`agent/qc-oracle-application.json`。NOP job 可以没有 `agent/`，但其他共同文件不能缺失。

ZIP 名称去掉 `.zip` 后必须与唯一最外层文件夹完全一致。`jobs/` 是运行证据，不属于
Harbor Task checksum 的生产题目内容；重新运行时先复制 Task 内容并排除旧 `jobs/`，新结果
写到新的证据目录，避免旧轨迹污染。

`evidence/`、`metadata/` 不是标准根目录必需项；缺少它们不失败。`tests/required_testcases.json` 少于 5 条失败，5–27 条正常，超过 27 条只提示人工复核。
