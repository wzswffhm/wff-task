# 标准 Harbor 五件套骨架（harbor-skeleton）

复制本目录到 `outside_harbor-assets/<task-id>/`，然后按占位符替换。

## 结构

```
<task-id>/
├── task.toml                        # 身份、版本、资源、超时、环境
├── instruction.md                   # Agent 唯一题面
├── environment/
│   ├── Dockerfile                   # 从 base image 派生，依赖锁定，离线可复现
│   └── workspace/                   # 初始工作区（COPY 到 C:\testbed）
├── solution/
│   └── oracle.patch                 # 参考解（仅 Golden 验证，不得泄漏）
└── tests/
    ├── test.ps1                     # 验证入口（patch 回放 → 预检 → 测试 → 评分 → 产物校验）
    ├── grade.py                     # 程序化二值评分 + INVALID 区分
    ├── swelive_spec.json            # 题面/测试元数据（含 F2P/P2P）
    └── test_patch.diff              # 隐藏测试补丁（只含测试代码）
```

## 快速开始

```bash
TASK_ID="<vendor>__<repo>-<pr>"
DEST="outside_harbor-assets/$TASK_ID"

mkdir -p "$DEST"
cp assets/harbor-skeleton/task.toml          "$DEST/task.toml"
cp assets/harbor-skeleton/instruction.md     "$DEST/instruction.md"
mkdir -p "$DEST/environment/workspace" "$DEST/solution" "$DEST/tests"
cp assets/harbor-skeleton/environment/Dockerfile   "$DEST/environment/Dockerfile"
cp assets/harbor-skeleton/tests/test.ps1           "$DEST/tests/test.ps1"
cp assets/harbor-skeleton/tests/grade.py           "$DEST/tests/grade.py"
cp assets/harbor-skeleton/tests/swelive_spec.json  "$DEST/tests/swelive_spec.json"
cp assets/harbor-skeleton/solution/oracle.patch.README.md "$DEST/solution/README.md"

# 替换占位符
grep -rn "<PLACEHOLDER>\|<task-id>\|<package-path>" "$DEST"
```

## 必须替换的占位符

| 占位符 | 出现位置 | 说明 |
|---|---|---|
| `<task-id>` | task.toml 注释 / swelive_spec.json | 目录名 + instance_id + task_hash 三元组的一部分 |
| `<AUTHOR>` | task.toml `[metadata].author_name` | |
| `<REGISTRY>/<NAMESPACE>/<REPO>:<TAG>` | task.toml / Dockerfile / swelive_spec.json | **三处必须一致** |
| `<instance-id-variant>` | Dockerfile `FROM` | base image 的实例变体 |
| `<package-path>` | Dockerfile / test.ps1 / swelive_spec.json | 被测包在 C:\testbed 下的相对路径 |
| `<your-package>` | Dockerfile / test.ps1 | 环境预检要 import 的包 |
| `<TEST_FILES>` | test.ps1 / swelive_spec.json `test_cmds` | 要运行的测试文件列表 |
| `<test id N>` | swelive_spec.json | required 测试的完整 nodeid |
| `<sha>` / `sha256:<digest>` | spec / manifest | 来源 commit 与不可变镜像 Digest |

## 骨架中已固化的正确做法（不要退回去）

1. **二值评分**：`score = 1.0 if resolved else 0.0`，无权重、无部分分
2. **INVALID ≠ 0 分**：缺失/SKIP/解析失败 → **不写** reward 产物 + exit 2
3. **合法 0 分**：候选编译/收集失败（已过环境预检）→ 正常写 reward=0
4. **必需名字缺失不算 failure**：`missing` 单独归类，触发 INVALID
5. **证据六字段**：`run_id / source_commit / image_digest / log_sha256 / spec_sha256 / test_patch_sha256`
6. **基线 commit 不用 wall-clock**
7. **测试名 unwrap**：处理 PowerShell 控制台固定宽度换行（若日志干净可删）
8. **预算护栏**：`SWELIVE_GRADE_BUDGET_SEC` + parser alarm，防正则回溯炸穿 timeout
