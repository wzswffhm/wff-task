# 逐 testcase × 逐轮次终态矩阵（D02 / D07）

必需用例 16 条（F2P 8 / P2P 8）。`M` = 该轮未采集到该用例。

| testcase | 组 | oracle-1 | oracle-2 | oracle-3 | nop-1 | nop-2 | nop-3 | qwen-1 | qwen-2 | qwen-3 | opus-1 | opus-2 | opus-3 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `f2p-region-addresses-are-64-bit` | F2P | P | P | P | F | F | F | P | P | P | P | P | P |
| `f2p-region-sizes-are-64-bit` | F2P | P | P | P | F | F | F | P | P | P | P | P | P |
| `f2p-reserved-regions-are-reported` | F2P | P | P | P | F | F | F | P | P | P | P | P | P |
| `f2p-file-mapping-path-is-a-dos-path` | F2P | P | P | P | F | F | F | P | P | P | P | P | P |
| `f2p-device-paths-are-translated` | F2P | P | P | P | F | F | F | P | P | P | P | P | P |
| `f2p-anonymous-mapping-has-no-path` | F2P | P | P | P | F | F | F | P | P | P | P | P | P |
| `f2p-missing-process-is-classified` | F2P | P | P | P | F | F | F | P | P | P | P | P | P |
| `f2p-modules-are-deduplicated` | F2P | P | P | P | F | F | F | P | P | F | P | P | P |
| `p2p-regions-are-sorted-by-base` | P2P | P | P | P | P | P | P | P | P | P | P | P | P |
| `p2p-region-records-are-well-formed` | P2P | P | P | P | P | P | P | P | P | P | P | P | P |
| `p2p-own-process-reports-image-regions` | P2P | P | P | P | P | P | P | P | P | P | P | P | P |
| `p2p-file-backed-regions-are-a-subset` | P2P | P | P | P | P | P | P | P | P | P | P | P | P |
| `p2p-include-reserved-false-only-reports-committed-memory` | P2P | P | P | P | P | P | P | P | P | P | P | P | P |
| `p2p-negative-pid-is-rejected` | P2P | P | P | P | P | P | P | P | P | P | P | P | P |
| `p2p-modules-are-sorted-by-base` | P2P | P | P | P | P | P | P | P | P | P | P | P | P |
| `p2p-visible-smoke-suite-still-passes` | P2P | P | P | P | P | P | P | P | P | F | P | P | P |

## D02 对照预期

- no-change(NOP) 下全部 F2P 因目标缺陷失败：**成立**
- no-change(NOP) 下全部 P2P 通过：**成立**
- Golden(Oracle) 下全部必需用例通过：**成立**

图例：P = PASS，F = FAIL，M = 未采集。
