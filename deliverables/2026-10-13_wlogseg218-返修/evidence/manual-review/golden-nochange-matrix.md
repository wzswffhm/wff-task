# Golden / no-change 逐 testcase 终态矩阵（wfflab__wlogseg-218 v1.1.0）

| testcase | 分组 | oracle-1 | oracle-2 | oracle-3 | nop-1 | nop-2 | nop-3 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `f2p-sample-verifies` | F2P | PASS | PASS | PASS | FAIL | FAIL | FAIL |
| `f2p-sample-roundtrip-byte-identical` | F2P | PASS | PASS | PASS | FAIL | FAIL | FAIL |
| `f2p-sample-records-match-expected` | F2P | PASS | PASS | PASS | FAIL | FAIL | FAIL |
| `f2p-empty-sample-roundtrip` | F2P | PASS | PASS | PASS | FAIL | FAIL | FAIL |
| `f2p-segment-alignment-is-eight-bytes` | F2P | PASS | PASS | PASS | FAIL | FAIL | FAIL |
| `f2p-index-layout-matches-sample` | F2P | PASS | PASS | PASS | FAIL | FAIL | FAIL |
| `f2p-crc-matches-standard-check-value` | F2P | PASS | PASS | PASS | FAIL | FAIL | FAIL |
| `f2p-tampered-payload-is-rejected` | F2P | PASS | PASS | PASS | FAIL | FAIL | FAIL |
| `f2p-truncated-header-reports-truncated` | F2P | PASS | PASS | PASS | FAIL | FAIL | FAIL |
| `f2p-missing-index-reports-truncated` | F2P | PASS | PASS | PASS | FAIL | FAIL | FAIL |
| `f2p-truncated-segment-body-reports-truncated` | F2P | PASS | PASS | PASS | FAIL | FAIL | FAIL |
| `f2p-truncated-stream-reports-truncated` | F2P | PASS | PASS | PASS | FAIL | FAIL | FAIL |
| `f2p-index-offset-inside-header-reports-structure` | F2P | PASS | PASS | PASS | FAIL | FAIL | FAIL |
| `f2p-segment-past-index-reports-structure` | F2P | PASS | PASS | PASS | FAIL | FAIL | FAIL |
| `f2p-index-entry-mismatch-reports-structure` | F2P | PASS | PASS | PASS | FAIL | FAIL | FAIL |
| `f2p-trailing-bytes-reports-structure` | F2P | PASS | PASS | PASS | FAIL | FAIL | FAIL |
| `p2p-bad-magic-reports-magic` | P2P | PASS | PASS | PASS | PASS | PASS | PASS |
| `p2p-bad-version-reports-version` | P2P | PASS | PASS | PASS | PASS | PASS | PASS |
| `p2p-verify-never-raises` | P2P | PASS | PASS | PASS | PASS | PASS | PASS |
| `f2p-iter-segments-is-streaming` | F2P | PASS | PASS | PASS | FAIL | FAIL | FAIL |
| `f2p-iter-segments-consumes-every-segment-and-the-tail` | F2P | PASS | PASS | PASS | FAIL | FAIL | FAIL |
| `p2p-self-roundtrip-small-segments` | P2P | PASS | PASS | PASS | PASS | PASS | PASS |
| `p2p-empty-payload-roundtrip` | P2P | PASS | PASS | PASS | PASS | PASS | PASS |
| `p2p-generated-data-roundtrip-verified` | P2P | PASS | PASS | PASS | PASS | PASS | PASS |
| `p2p-read-all-matches-unpack` | P2P | PASS | PASS | PASS | PASS | PASS | PASS |
| `p2p-pack-rejects-out-of-range-segment-id` | P2P | PASS | PASS | PASS | PASS | PASS | PASS |

结论：Oracle 三次全 PASS 且 score=1；no-change 三次 P2P 全 PASS、F2P 全 FAIL 且 score=0。
