# 飞书交付附件 vs 本地题包 一致性比对

| 附件 | 根目录名一致 | ZIP 文件数 | 本地文件数 | 仅飞书有 | 仅本地有 | 内容不同 | 结论 |
|---|---|---|---|---|---|---|---|
| wfflab__wsparse-215-v1.0.0-delivery.zip | ✔ | 273 | 273 | 0 | 0 | 0 | **一致** |
| wfflab__wvas-216-v1.0.0-delivery.zip | ✔ | 259 | 261 | 0 | 2 | 0 | **不一致** |
| wfflab__wspawn-218-v1.0.0-delivery.zip | ✔ | 261 | 261 | 0 | 0 | 2 | **不一致** |
| wfflab__wcancel-219-v1.0.0-delivery.zip | ✔ | 260 | 260 | 0 | 0 | 0 | **一致** |
| wfflab__wciocp-220-v1.0.0-delivery.zip | ✔ | 258 | 258 | 0 | 0 | 0 | **一致** |

## wfflab__wvas-216-v1.0.0-delivery.zip

- 只在飞书里存在：0
- 只在本地存在：2
  - `REFIT-2026-10-14.md`
  - `verifier/WINDOWS_VALUE.md`
- 同名但内容不同：0

## wfflab__wspawn-218-v1.0.0-delivery.zip

- 只在飞书里存在：0
- 只在本地存在：0
- 同名但内容不同：2
  - `environment/Dockerfile`
  - `task.toml`

