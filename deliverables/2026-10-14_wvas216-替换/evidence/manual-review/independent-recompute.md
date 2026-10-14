# 独立复算对照（D18）

冻结公式：`formal_score = 1 当且仅当 run_validity == VALID 且全部必需用例 PASS`；`run_validity = VALID 当且仅当 cases_total > 0 且 invalid == 0`。

必需用例 16 条（F2P 8 / P2P 8）。

| job | 来源 | 复算态 | 复算分 | 落盘 reward.txt | report.formal_score | report 态 | 一致 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ctl-nop-1/wfflab__wvas-216-v1.0.0-delivery__eDRBMZf | controls | VALID | 0 | 0 | 0 | VALID | 是 |
| ctl-nop-2/wfflab__wvas-216-v1.0.0-delivery__7dgm94L | controls | VALID | 0 | 0 | 0 | VALID | 是 |
| ctl-nop-3/wfflab__wvas-216-v1.0.0-delivery__HupfR6n | controls | VALID | 0 | 0 | 0 | VALID | 是 |
| ctl-oracle-1/wfflab__wvas-216-v1.0.0-delivery__fCcYVM9 | controls | VALID | 1 | 1 | 1 | VALID | 是 |
| ctl-oracle-2/wfflab__wvas-216-v1.0.0-delivery__M88fvYy | controls | VALID | 1 | 1 | 1 | VALID | 是 |
| ctl-oracle-3/wfflab__wvas-216-v1.0.0-delivery__AheGWix | controls | VALID | 1 | 1 | 1 | VALID | 是 |
| model-opus-1/wfflab__wvas-216-v1.0.0-delivery__z9HQqBj | model-rounds | VALID | 1 | 1 | 1 | VALID | 是 |
| model-opus-2/wfflab__wvas-216-v1.0.0-delivery__TMNXcxL | model-rounds | VALID | 1 | 1 | 1 | VALID | 是 |
| model-opus-3/wfflab__wvas-216-v1.0.0-delivery__AAAwz9D | model-rounds | VALID | 1 | 1 | 1 | VALID | 是 |
| model-qwen-1/wfflab__wvas-216-v1.0.0-delivery__rB7xeiq | model-rounds | VALID | 1 | 1 | 1 | VALID | 是 |
| model-qwen-2/wfflab__wvas-216-v1.0.0-delivery__mLxMbJu | model-rounds | VALID | 1 | 1 | 1 | VALID | 是 |
| model-qwen-3/wfflab__wvas-216-v1.0.0-delivery__Y5QJMts | model-rounds | VALID | 0 | 0 | 0 | VALID | 是 |

总计 12 个 job，复算与落盘全部一致。
