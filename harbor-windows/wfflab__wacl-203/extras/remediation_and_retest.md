# remediation_and_retest —— wfflab__wacl-203

本文件记录本题生产过程中实际发生的问题、根因、整改动作与复验结论。

## 骨架级共性整改（适用于本题）

| # | 项 | 内容 |
|---|---|---|
| B1 | 验证入口把「测试失败」误判为「候选级故障」 | 骨架 `test.ps1` 原写 `if ($testRc -ne 0)`；pytest 返回 1 表示存在测试失败（候选的合法 0 分），`> 1` 才是中断/收集失败。已在本目录统一改为 `if ($testRc -gt 1)`。 |
| B2 | log_parser 不兼容多行 JSON | `pytest-json-report` 默认缩进输出，骨架正则只认单行。已统一改为 `json.JSONDecoder().raw_decode(log.strip()[log.find('{'):])`，并容忍尾随的 `CANDIDATE_FAILURE` 行。 |

> 上述两项为**骨架级**问题，在本目录所有题目中一次性修正；题 wfflab__wsync-142 已单独记录过同样两项。

## 本题迭代记录

本轮未执行测试，故无复验记录。


## 遗留整改（不计入本轮验收）

| # | 问题 | 状态 |
|---|---|---|
| R-1 | 镜像未构建，`image_digest` 待回填 | 待平台侧 `docker build` 后回填 |
| R-2 | 对照验证未执行（no-change ×3 / Golden ×3 / 反例 / 等价实现） | 按出题方要求本轮不跑；待平台 harness 执行 |
| R-3 | 多模型区分度验证未执行 | 按出题方要求本轮不跑；待平台 harness 回填分数后执行 |

> 上述三项补齐后，须重新执行所有受影响环节，并升级 `task_version`。

## 2026-10-03 缺陷修复（模型验证发现）

**触发**：首轮模型验证（Qwen×3 / Opus×3）两模型同一条 P2P `test_audit_on_untouched_tree_is_not_empty` 三轮 consistently 失败；本机用 base+oracle 复测，oracle 同样挂——判定为测试缺陷而非模型弱点。

**根因**：测试从全新目录的默认 ACL 里找持 `W` 权限字母的主体，但默认 ACE 只有 F/RX 等字母，`principal_for` 恒为 `None`；另有判分环境 `PYTHONUTF8=1` 下 `icacls` GBK 输出解码崩溃的隐患（判定环境无该变量，未触发）。

**修复**：测试改为 `grant(TEST_SID, "(W)", recursive=True)` 后确定性取证；同时把 `test_explicit_aces_exclude_inherited` 重写为「父目录授权 + 子目录断言继承项被排除」的可观测形式（原写法在 base 上因临时目录无 `(I)` 标志而平凡通过，F2P 标签失真）。

**实测**（本机 2026-10-03，PYTHONUTF8=0）：base 1 失败（即新 F2P）/19 通过；oracle 20/20 通过。旧 model_runs 已归档至 `extras/archive/model-runs-pre-fix-20261003/`，身份哈希重算。
