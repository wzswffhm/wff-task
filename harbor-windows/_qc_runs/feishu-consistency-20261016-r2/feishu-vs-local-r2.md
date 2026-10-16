# 飞书交付附件 vs 本地题包：逐文件 SHA256 比对（2026-10-16 复核 r2）

| 附件 | ZIP 文件数 | 本地文件数 | 根目录名匹配 | ZIP 独有 | 本地独有 | 同名异内容 | 结论 |
|---|---|---|---|---|---|---|---|
| `wfflab__wcancel-219-v1.0.0-delivery.zip` | 260 | 260 | True | 0 | 0 | 0 | **一致** |
| `wfflab__wciocp-220-v1.0.0-delivery.zip` | 258 | 258 | True | 0 | 0 | 0 | **一致** |
| `wfflab__wsparse-215-v1.0.0-delivery.zip` | 273 | 273 | True | 0 | 0 | 0 | **一致** |
| `wfflab__wspawn-218-v1.0.0-delivery.zip` | 261 | 261 | True | 0 | 0 | 0 | **一致** |
| `wfflab__wvas-216-v1.0.0-delivery.zip` | 259 | 259 | True | 0 | 0 | 0 | **一致** |

ZIP SHA256：
- `wfflab__wcancel-219-v1.0.0-delivery.zip` → `0ebe199eeaef5761e8d3267611847930d6b08a1676b2a0ffded6a97c863a29e4`
- `wfflab__wciocp-220-v1.0.0-delivery.zip` → `d637d595533368b3679243cf65cf4b5a73da6d9fd4b93b39f66331156a4bd4d9`
- `wfflab__wsparse-215-v1.0.0-delivery.zip` → `a83f3622468897fada1b54507729c9d9a96b5f285a431b187f1b203beba787ef`
- `wfflab__wspawn-218-v1.0.0-delivery.zip` → `f02055cbddfc8b12be2dd393cea5a0cb40a07b57008b4080c93000a152e149f4`
- `wfflab__wvas-216-v1.0.0-delivery.zip` → `edea432cacf6b3f6701f6182a1de18261795b0c98214ce30565d6da5c3efe446`

差异明细：
