# 题面 ↔ required testcase ↔ rubric 映射（wfflab__wpeimg-219 v1.4.0）

| rubric 组 | 权重 | required testcase |
| --- | --- | --- |
| `sample-description` | 0.23 | `f2p-amd64-sample-inspects`, `f2p-i386-sample-inspects` |
| `checksum-semantics` | 0.14 | `f2p-checksum-matches-authoritative-values`, `f2p-checksum-ignores-the-stored-field`, `f2p-accumulator-matches-authoritative-values` |
| `windows-live-services` | 0.12 | `f2p-checksum-matches-a-live-windows-query`, `f2p-checksum-matches-live-queries-across-variants`, `f2p-iter-sections-reads-a-real-windows-file-handle`, `f2p-iter-sections-is-bounded-on-a-real-handle` |
| `rva-translation` | 0.10 | `f2p-rva-inside-headers-maps-to-itself`, `f2p-rva-inside-a-section-maps-into-the-file`, `f2p-rva-in-an-uninitialised-tail-has-no-backing`, `f2p-rva-outside-every-section-has-no-backing` |
| `error-classification` | 0.16 | `f2p-truncated-section-table-reports-truncated`, `f2p-unknown-optional-magic-reports-optional`, `f2p-section-past-end-of-file-reports-structure`, `f2p-overlapping-virtual-sections-reports-structure`, `f2p-overlapping-file-ranges-reports-structure`, `f2p-unaligned-section-reports-structure`, `f2p-undersized-size-of-image-reports-structure`, `f2p-structure-is-reported-before-checksum`, `f2p-verify-rejects-every-structural-variant`, `p2p-non-mz-prefix-reports-dos`, `p2p-missing-pe-signature-reports-signature`, `p2p-mismatched-checksum-reports-checksum` |
| `data-directories` | 0.07 | `f2p-data-directories-follow-the-pe-order`, `f2p-data-directories-use-the-layout-specific-offset`, `f2p-data-directories-respect-declared-count`, `f2p-data-directories-ignore-slots-the-header-cannot-hold` |
| `authenticode-detection` | 0.05 | `f2p-authenticode-signature-detection`, `f2p-authenticode-signature-requires-backing-bytes`, `f2p-trailing-bytes-are-not-a-structural-error` |
| `signature-decoding` | 0.05 | `f2p-signature-info-describes-the-real-signed-data`, `f2p-signature-info-without-a-certificate-table`, `f2p-signature-info-skips-non-pkcs7-records`, `f2p-signature-info-rejects-a-length-that-cannot-hold`, `f2p-signature-info-is-offline-and-standard-library-only` |
| `streaming` | 0.05 | `f2p-iter-sections-does-not-slurp-the-stream` |
| `api-and-regression` | 0.03 | `p2p-verify-never-raises`, `p2p-negative-rva-has-no-backing`, `p2p-public-surface-is-unchanged`, `p2p-accumulator-matches-one-shot-helper`, `p2p-package-has-no-external-dependencies` |

## 题面章节 → required

| 题面章节 | required testcase |
| --- | --- |
| （见 `REFIT-2026-10-13.md` §3 的完整双向表） | 全部 43 条 |
| A. 映像描述 | 见 REFIT §3 |
| B. 校验和 | 见 REFIT §3 |
| C. RVA 映射 | 见 REFIT §3 |
| D. 结构自检 | 见 REFIT §3 |
| E. 错误分类 | 见 REFIT §3 |
| F. 流式读取 | 见 REFIT §3 |
| G. 不得回归 | 见 REFIT §3 |

## 反向：每条 required 的来源

| required | 分组 | 归属 rubric 组 |
| --- | --- | --- |
| `f2p-amd64-sample-inspects` | F2P | `sample-description` |
| `f2p-i386-sample-inspects` | F2P | `sample-description` |
| `f2p-checksum-matches-authoritative-values` | F2P | `checksum-semantics` |
| `f2p-checksum-ignores-the-stored-field` | F2P | `checksum-semantics` |
| `f2p-accumulator-matches-authoritative-values` | F2P | `checksum-semantics` |
| `f2p-checksum-matches-a-live-windows-query` | F2P | `windows-live-services` |
| `f2p-checksum-matches-live-queries-across-variants` | F2P | `windows-live-services` |
| `f2p-iter-sections-reads-a-real-windows-file-handle` | F2P | `windows-live-services` |
| `f2p-iter-sections-is-bounded-on-a-real-handle` | F2P | `windows-live-services` |
| `f2p-rva-inside-headers-maps-to-itself` | F2P | `rva-translation` |
| `f2p-rva-inside-a-section-maps-into-the-file` | F2P | `rva-translation` |
| `f2p-rva-in-an-uninitialised-tail-has-no-backing` | F2P | `rva-translation` |
| `f2p-rva-outside-every-section-has-no-backing` | F2P | `rva-translation` |
| `f2p-truncated-section-table-reports-truncated` | F2P | `error-classification` |
| `f2p-unknown-optional-magic-reports-optional` | F2P | `error-classification` |
| `f2p-section-past-end-of-file-reports-structure` | F2P | `error-classification` |
| `f2p-overlapping-virtual-sections-reports-structure` | F2P | `error-classification` |
| `f2p-overlapping-file-ranges-reports-structure` | F2P | `error-classification` |
| `f2p-unaligned-section-reports-structure` | F2P | `error-classification` |
| `f2p-undersized-size-of-image-reports-structure` | F2P | `error-classification` |
| `f2p-structure-is-reported-before-checksum` | F2P | `error-classification` |
| `f2p-verify-rejects-every-structural-variant` | F2P | `error-classification` |
| `p2p-non-mz-prefix-reports-dos` | P2P | `error-classification` |
| `p2p-missing-pe-signature-reports-signature` | P2P | `error-classification` |
| `p2p-mismatched-checksum-reports-checksum` | P2P | `error-classification` |
| `f2p-data-directories-follow-the-pe-order` | F2P | `data-directories` |
| `f2p-data-directories-use-the-layout-specific-offset` | F2P | `data-directories` |
| `f2p-data-directories-respect-declared-count` | F2P | `data-directories` |
| `f2p-data-directories-ignore-slots-the-header-cannot-hold` | F2P | `data-directories` |
| `f2p-authenticode-signature-detection` | F2P | `authenticode-detection` |
| `f2p-authenticode-signature-requires-backing-bytes` | F2P | `authenticode-detection` |
| `f2p-trailing-bytes-are-not-a-structural-error` | F2P | `authenticode-detection` |
| `f2p-signature-info-describes-the-real-signed-data` | F2P | `signature-decoding` |
| `f2p-signature-info-without-a-certificate-table` | F2P | `signature-decoding` |
| `f2p-signature-info-skips-non-pkcs7-records` | F2P | `signature-decoding` |
| `f2p-signature-info-rejects-a-length-that-cannot-hold` | F2P | `signature-decoding` |
| `f2p-signature-info-is-offline-and-standard-library-only` | F2P | `signature-decoding` |
| `f2p-iter-sections-does-not-slurp-the-stream` | F2P | `streaming` |
| `p2p-verify-never-raises` | P2P | `api-and-regression` |
| `p2p-negative-rva-has-no-backing` | P2P | `api-and-regression` |
| `p2p-public-surface-is-unchanged` | P2P | `api-and-regression` |
| `p2p-accumulator-matches-one-shot-helper` | P2P | `api-and-regression` |
| `p2p-package-has-no-external-dependencies` | P2P | `api-and-regression` |
