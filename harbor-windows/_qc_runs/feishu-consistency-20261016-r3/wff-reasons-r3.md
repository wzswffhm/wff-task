# 飞书 4 条记录最新快照（r3）

## wsparse-215

- record_id: `reczz28KwEOO3xHy`
- 状态: ['返修待质检']
- 甲方ID: 12
- Qwen / opus: 2/3 / 3/3
- 作业压缩包: `wfflab__wsparse-215-v1.0.0-delivery.zip` 54423465 B token=WRgRbLbrGoiZ7CxpCaKc6HaVnad
- 分数截图: score_summary.png 73821 B

### 返修原因全文

```text
【2026-10-16 本轮质检】
1. 测试把候选模块和隐藏测试一起放进同一个 pytest 进程执行，当前配置没有把候选的权限和评分端分开。这样候选在验证时可以影响同一解释器里的测试和判分。请让候选在受限进程运行，由独立可信端检查结果和写分，并补读写测试/评分目录被拒绝的反例。没有证据表明这批模型已经实际利用了这个漏洞。
证据：tests/run_tests.ps1；environment/Dockerfile；task.toml

2. 评分脚本会把基础设施故障当成普通失败。本轮用原状态映射代码和原聚合器做探针，验证依赖缺失导致一个测试都没收集到时，仍输出 VALID/0。请把这类故障保留为 INVALID、正式分数为空；只有完整有效执行后的功能失败才能记0。探针不是完整Docker实测，也不表示现有模型的0分都已证实是环境错误。
证据：fault-probes/；tests/run_tests.ps1；tests/aggregate_results.ps1

3. 部分测试没有真正验到题面要求：独立 measured 范围未与候选范围比较。原断言探针：实际长度8192、候选错误报8193仍PASS，不能证明真实 extent 完全相等。 请补真实行为/终态断言，保留独立系统观测作为预期，再复验标准解、NOP、错误实现与等价实现。
证据：tests/[test_wsparse_semantics.py](http://test_wsparse_semantics.py)；fault-probes/

4. 本次附件里没有找到作者写测试之前的具体用例设计，以及可核验的造测可见会话，因此94项里的“先设计用例”和“没有看分数循环改测试”还不能判通过。请补原始可见消息/工具记录、时间顺序和预处理说明；不需要交隐藏思考或私密无关会话，也不能事后补写成旧记录。
证据：inventory.json；author-evidence-audit.json

本轮结论：需要返修（已确认缺陷）。状态保持不变。目录和原始主模型分差已检查；GLM/Kimi免跑，不因缺evidence/metadata、source.json或未pin digest驳回。
```

## wvas-216

- record_id: `reczz28KQU8reW2k`
- 状态: ['返修待质检']
- 甲方ID: 11
- Qwen / opus: 2/3 / 3/3
- 作业压缩包: `wfflab__wvas-216-v1.0.0-delivery.zip` 54420063 B token=RWLzbe64voPantxxB0kcEUBMnph
- 分数截图: score_summary.png 74258 B

### 返修原因全文

```text
【2026-10-16 本轮质检】
1. 现在包里的 Task 校验值和12份原始运行记录对不上，现有模型分数还不能直接证明这个交付版本已完成同版本跑分。请保留旧日志，提供可核验的原冻结资产与当前改动对应关系；按当前严格版本规则重新交付时，环境有改动需升版并用新版本的正式记录闭合，不能手改旧日志中的Hash。
证据：normalized-jobs.json；delivery-layout.json；deep-audit.json

2. 测试把候选模块和隐藏测试一起放进同一个 pytest 进程执行，当前配置没有把候选的权限和评分端分开。这样候选在验证时可以影响同一解释器里的测试和判分。请让候选在受限进程运行，由独立可信端检查结果和写分，并补读写测试/评分目录被拒绝的反例。没有证据表明这批模型已经实际利用了这个漏洞。
证据：tests/run_tests.ps1；environment/Dockerfile；task.toml

3. 评分脚本会把基础设施故障当成普通失败。本轮用原状态映射代码和原聚合器做探针，独立fixture在setup阶段报错时，仍输出 VALID/0。请把这类故障保留为 INVALID、正式分数为空；只有完整有效执行后的功能失败才能记0。探针不是完整Docker实测，也不表示现有模型的0分都已证实是环境错误。
证据：fault-probes/；tests/run_tests.ps1；tests/aggregate_results.ps1

4. 部分测试没有真正验到题面要求：只检查返回项属于 regions，没有检查非空背衬项是否全部返回。原断言探针：regions 有背衬项、file_backed_regions=[] 仍 PASS，违反题面 B.4。 请补真实行为/终态断言，保留独立系统观测作为预期，再复验标准解、NOP、错误实现与等价实现。
证据：tests/test_wvas_semantics.py；fault-probes/

5. 本次附件里没有找到作者写测试之前的具体用例设计，以及可核验的造测可见会话，因此94项里的“先设计用例”和“没有看分数循环改测试”还不能判通过。请补原始可见消息/工具记录、时间顺序和预处理说明；不需要交隐藏思考或私密无关会话，也不能事后补写成旧记录。
证据：inventory.json；author-evidence-audit.json

本轮结论：需要返修（已确认缺陷）。状态保持不变。目录和原始主模型分差已检查；GLM/Kimi免跑，不因缺evidence/metadata、source.json或未pin digest驳回。
```

## wcancel-219

- record_id: `reczz28N2IGu9XmA`
- 状态: ['返修待质检']
- 甲方ID: None
- Qwen / opus: 1/3 / 3/3
- 作业压缩包: `wfflab__wcancel-219-v1.0.0-delivery.zip` 54420405 B token=SxwFblbU7oP9dfxGj4ucaMiGnJh
- 分数截图: score_summary.png 73328 B

### 返修原因全文

```text
【2026-10-16 本轮质检】
1. 测试把候选模块和隐藏测试一起放进同一个 pytest 进程执行，当前配置没有把候选的权限和评分端分开。这样候选在验证时可以影响同一解释器里的测试和判分。请让候选在受限进程运行，由独立可信端检查结果和写分，并补读写测试/评分目录被拒绝的反例。没有证据表明这批模型已经实际利用了这个漏洞。
证据：tests/run_tests.ps1；environment/Dockerfile；task.toml

2. 评分脚本会把基础设施故障当成普通失败。本轮用原状态映射代码和原聚合器做探针，验证依赖缺失导致一个测试都没收集到时，仍输出 VALID/0。请把这类故障保留为 INVALID、正式分数为空；只有完整有效执行后的功能失败才能记0。探针不是完整Docker实测，也不表示现有模型的0分都已证实是环境错误。
证据：fault-probes/；tests/run_tests.ps1；tests/aggregate_results.ps1

3. 部分测试没有真正验到题面要求：只验取消数量及没有 timeout，没有要求 cancelled 终态。原断言探针中 wait 返回 completed 仍PASS，未验证题面所需真实取消。 请补真实行为/终态断言，保留独立系统观测作为预期，再复验标准解、NOP、错误实现与等价实现。
证据：tests/test_wcancel_semantics.py；fault-probes/

4. 本次附件里没有找到作者写测试之前的具体用例设计，以及可核验的造测可见会话，因此94项里的“先设计用例”和“没有看分数循环改测试”还不能判通过。请补原始可见消息/工具记录、时间顺序和预处理说明；不需要交隐藏思考或私密无关会话，也不能事后补写成旧记录。
证据：inventory.json；author-evidence-audit.json

本轮结论：需要返修（已确认缺陷）。状态保持不变。目录和原始主模型分差已检查；GLM/Kimi免跑，不因缺evidence/metadata、source.json或未pin digest驳回。
```

## wciocp-220

- record_id: `reczz28NUOrl6Foj`
- 状态: ['返修待质检']
- 甲方ID: None
- Qwen / opus: 1/3 / 3/3
- 作业压缩包: `wfflab__wciocp-220-v1.0.0-delivery.zip` 54576334 B token=GQ2cbIazfovdVDx8r45ctJnYnRf
- 分数截图: score_summary.png 74865 B

### 返修原因全文

```text
【2026-10-16 本轮质检】
1. 测试把候选模块和隐藏测试一起放进同一个 pytest 进程执行，当前配置没有把候选的权限和评分端分开。这样候选在验证时可以影响同一解释器里的测试和判分。请让候选在受限进程运行，由独立可信端检查结果和写分，并补读写测试/评分目录被拒绝的反例。没有证据表明这批模型已经实际利用了这个漏洞。
证据：tests/run_tests.ps1；environment/Dockerfile；task.toml

2. 评分脚本会把基础设施故障当成普通失败。本轮用原状态映射代码和原聚合器做探针，验证依赖缺失导致一个测试都没收集到时，仍输出 VALID/0。请把这类故障保留为 INVALID、正式分数为空；只有完整有效执行后的功能失败才能记0。探针不是完整Docker实测，也不表示现有模型的0分都已证实是环境错误。
证据：fault-probes/；tests/run_tests.ps1；tests/aggregate_results.ps1

3. 部分测试没有真正验到题面要求：只检查 close 后拒绝新调用；close 前没有 pending read，未覆盖题面F的取消挂起读取和 cancelled 终态。；重复close路径没有挂起读取，不能补足题面F取消终态的覆盖。；场景是空队列timeout后再提交新读，没有验证超时期间已入队完成项不会被丢弃。 请补真实行为/终态断言，保留独立系统观测作为预期，再复验标准解、NOP、错误实现与等价实现。
证据：tests/test_wciocp_semantics.py；deep-audit.json

4. 本次附件里没有找到作者写测试之前的具体用例设计，以及可核验的造测可见会话，因此94项里的“先设计用例”和“没有看分数循环改测试”还不能判通过。请补原始可见消息/工具记录、时间顺序和预处理说明；不需要交隐藏思考或私密无关会话，也不能事后补写成旧记录。
证据：inventory.json；author-evidence-audit.json

5. 本轮真实Windows容器跑完三轮Oracle和三轮NOP后，第三轮NOP的 p2p-keys-distinguish-handles-on-one-port 失败：两次take没有交出第二个句柄的完成项，预期键0x22，实际为None。这个用例目前标为P2P，不能宣称基线三轮P2P稳定全过。请核对重复完成项的目标缺陷与用例分组，按真实功能修正/澄清后复验，不能删掉用例来凑通过。
证据：local-controls/runs.json；local-controls/jobs/wfflab__wciocp-220-nop-3/；tests/test_wciocp_semantics.py:178

本轮结论：需要返修（已确认缺陷）。状态保持不变。目录和原始主模型分差已检查；GLM/Kimi免跑，不因缺evidence/metadata、source.json或未pin digest驳回。
```

