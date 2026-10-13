# 题面 ↔ required testcase ↔ rubric 映射（wfflab__wlogseg-218 v1.1.0）

| rubric 组 | 权重 | required testcase |
| --- | --- | --- |
| `sample-compatibility` | 0.30 | `f2p-sample-verifies`, `f2p-sample-roundtrip-byte-identical`, `f2p-sample-records-match-expected`, `f2p-empty-sample-roundtrip` |
| `layout-and-alignment` | 0.12 | `f2p-segment-alignment-is-eight-bytes`, `f2p-index-layout-matches-sample` |
| `checksum-semantics` | 0.18 | `f2p-crc-matches-standard-check-value`, `f2p-tampered-payload-is-rejected` |
| `error-classification` | 0.20 | `f2p-truncated-header-reports-truncated`, `f2p-missing-index-reports-truncated`, `f2p-truncated-segment-body-reports-truncated`, `f2p-truncated-stream-reports-truncated`, `f2p-index-offset-inside-header-reports-structure`, `f2p-segment-past-index-reports-structure`, `f2p-index-entry-mismatch-reports-structure`, `f2p-trailing-bytes-reports-structure`, `p2p-bad-magic-reports-magic`, `p2p-bad-version-reports-version`, `p2p-verify-never-raises` |
| `streaming` | 0.10 | `f2p-iter-segments-is-streaming`, `f2p-iter-segments-consumes-every-segment-and-the-tail` |
| `api-and-regression` | 0.10 | `p2p-self-roundtrip-small-segments`, `p2p-empty-payload-roundtrip`, `p2p-generated-data-roundtrip-verified`, `p2p-read-all-matches-unpack`, `p2p-pack-rejects-out-of-range-segment-id` |

## 题面章节 → required

| 题面章节 | required testcase |
| --- | --- |
| （见 `REFIT-2026-10-13.md` §3 的完整双向表） | 全部 26 条 |
| A. 样本兼容（硬门槛） | 见 REFIT §3 |
| B. 段语义 | 见 REFIT §3 |
| C. 段布局与尾部索引 | 见 REFIT §3 |
| D. 校验和 | 见 REFIT §3 |
| E. 错误分类 | 见 REFIT §3 |
| F. 流式读取 | 见 REFIT §3 |
| G. 不得回归 | 见 REFIT §3 |

## 反向：每条 required 的来源

| required | 分组 | 归属 rubric 组 |
| --- | --- | --- |
| `f2p-sample-verifies` | F2P | `sample-compatibility` |
| `f2p-sample-roundtrip-byte-identical` | F2P | `sample-compatibility` |
| `f2p-sample-records-match-expected` | F2P | `sample-compatibility` |
| `f2p-empty-sample-roundtrip` | F2P | `sample-compatibility` |
| `f2p-segment-alignment-is-eight-bytes` | F2P | `layout-and-alignment` |
| `f2p-index-layout-matches-sample` | F2P | `layout-and-alignment` |
| `f2p-crc-matches-standard-check-value` | F2P | `checksum-semantics` |
| `f2p-tampered-payload-is-rejected` | F2P | `checksum-semantics` |
| `f2p-truncated-header-reports-truncated` | F2P | `error-classification` |
| `f2p-missing-index-reports-truncated` | F2P | `error-classification` |
| `f2p-truncated-segment-body-reports-truncated` | F2P | `error-classification` |
| `f2p-truncated-stream-reports-truncated` | F2P | `error-classification` |
| `f2p-index-offset-inside-header-reports-structure` | F2P | `error-classification` |
| `f2p-segment-past-index-reports-structure` | F2P | `error-classification` |
| `f2p-index-entry-mismatch-reports-structure` | F2P | `error-classification` |
| `f2p-trailing-bytes-reports-structure` | F2P | `error-classification` |
| `p2p-bad-magic-reports-magic` | P2P | `error-classification` |
| `p2p-bad-version-reports-version` | P2P | `error-classification` |
| `p2p-verify-never-raises` | P2P | `error-classification` |
| `f2p-iter-segments-is-streaming` | F2P | `streaming` |
| `f2p-iter-segments-consumes-every-segment-and-the-tail` | F2P | `streaming` |
| `p2p-self-roundtrip-small-segments` | P2P | `api-and-regression` |
| `p2p-empty-payload-roundtrip` | P2P | `api-and-regression` |
| `p2p-generated-data-roundtrip-verified` | P2P | `api-and-regression` |
| `p2p-read-all-matches-unpack` | P2P | `api-and-regression` |
| `p2p-pack-rejects-out-of-range-segment-id` | P2P | `api-and-regression` |
