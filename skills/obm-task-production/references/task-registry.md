# OBM 题目登记表

本文件规定项目内多窗口、多进程生产题目时的共享登记方式。登记表属于内部材料，不进入正式题包。

## 位置

每个项目只使用一个登记表：

```text
./work/task-registry.json
./work/task-registry.lock
```

执行命令前进入当前项目根目录，并统一使用 `--root .`。所有窗口必须打开同一个项目根目录。不能在各自候选目录中维护独立清单，也不能依赖对话记忆判断是否重复。

`OBM_SKILL_DIR` 指向当前安装的 `obm-task-production` skill 目录。项目可以位于任意位置，登记表不得保存项目根目录之外的路径。

## 开始生产前

先同步已有题包：

```bash
"$OBM_PYTHON" "$OBM_SKILL_DIR/scripts/task_registry.py" sync \
  --root .
```

再读取登记表，检查所有 `reserved`、`candidate` 和 `packaged` 项。比较题目目标、上游仓库、主要能力类型、场景摘要和场景指纹。登记表的精确指纹只能发现相同材料，不能代替场景语义去重。

候选场景明确后，必须在创建正式工作目录前执行原子占位：

```bash
"$OBM_PYTHON" "$OBM_SKILL_DIR/scripts/task_registry.py" reserve \
  --root . \
  --benchmark deepSWE \
  --slug example-short-name \
  --repository owner/repository \
  --base-commit 0123456789abcdef0123456789abcdef01234567 \
  --capability-type concurrency-and-scheduling \
  --scene-summary "One concise description of the new task state model." \
  --scene-profile ./work/candidates/example-short-name/scene-profile.json \
  --reference-task related-deepswe-task
```

命令在同一文件锁内同步现有 proposal、检查相同 slug 和场景指纹，并把项目历史最大尾号加一后写入登记表。日期只取创建当天，尾号不会因日期变化而重置。返回的 `reservation_id` 是后续更新该记录的唯一标识。不能先运行只读的 `next_task_id.py` 再自行创建目录，因为多个窗口可能读到相同编号。

命令返回的 `similar_entries_for_review` 是同仓库或同能力类型的既有题。必须阅读这些记录并完成场景语义比较。存在实质重复时，把记录设为 `rejected` 或 `abandoned`，然后更换场景重新占位。

## 状态

- `reserved`：编号和候选场景已占位，尚未完成场景去重；
- `candidate`：场景去重为 `distinct`，正在生产；
- `packaged`：正式题包已经生成；
- `rejected`：候选没有通过原创性或可行性检查；
- `abandoned`：主动停止，不再占用相同 slug 和指纹。

更新示例：

```bash
"$OBM_PYTHON" "$OBM_SKILL_DIR/scripts/task_registry.py" update \
  --root . \
  --reservation-id UUID-FROM-RESERVE \
  --status candidate

"$OBM_PYTHON" "$OBM_SKILL_DIR/scripts/task_registry.py" update \
  --root . \
  --reservation-id UUID-FROM-RESERVE \
  --status packaged \
  --package-path ./output/deepSWE_YYYY-MM-DD-N-name
```

发生改题时，如果目标、状态模型、失败恢复或 verifier 行为发生实质变化，应废弃旧占位并为新场景重新占位，不能继续沿用旧场景指纹。

## 已有题和冲突

`sync` 会从当前项目根目录向下扫描已有的 `proposal.json` 并回填登记表。登记表中的 `paths` 字段始终保存项目内相对路径。它也会报告重复的日期编号。已有编号冲突不会被自动重命名或删除；后续编号会跳过已出现的最大编号。

登记表防止的是项目共享文件系统中的重复生产。它不能取代全量 benchmark 去重、同能力族人工复核或改名测试。最终只有 `scene-overlap-review.md` 结论为 `distinct` 的候选才能进入 `candidate`。
