# r3：飞书最新附件 vs 本地题包（逐文件 SHA256）与身份复核

| 包 | ZIP 文件数 | 本地文件数 | 仅本地 | 仅 ZIP | 异内容 | 与飞书一致 | jobs 身份一致 |
|---|---|---|---|---|---|---|---|
| `wfflab__wcancel-219-v1.0.0-delivery` | 260 | 260 | 0 | 0 | 0 | ✔ | ✔ |
| `wfflab__wciocp-220-v1.0.0-delivery` | 258 | 258 | 0 | 0 | 0 | ✔ | ✔ |
| `wfflab__wsparse-215-v1.0.0-delivery` | 273 | 273 | 0 | 0 | 0 | ✔ | ✔ |
| `wfflab__wvas-216-v1.0.0-delivery` | 259 | 259 | 0 | 0 | 0 | ✔ | ✘ |

## 身份（Harbor dirhash）

### wfflab__wcancel-219-v1.0.0-delivery

- 包当前 dirhash: `032b0ec7a141687a9031d1bd56f088ccea44a819096f5f5e53de7f9d0df9b702`
- jobs 记录: `['032b0ec7a141687a9031d1bd56f088ccea44a819096f5f5e53de7f9d0df9b702']`
- 12 份 job 逐条: `['032b0ec7a141687a9031d1bd56f088ccea44a819096f5f5e53de7f9d0df9b702']`（12 条）
- 结论: 一致

### wfflab__wciocp-220-v1.0.0-delivery

- 包当前 dirhash: `6c1284079453799bc49c249ed06c8aee66139625d9c9bba3f45f88943d10a87c`
- jobs 记录: `['6c1284079453799bc49c249ed06c8aee66139625d9c9bba3f45f88943d10a87c']`
- 12 份 job 逐条: `['6c1284079453799bc49c249ed06c8aee66139625d9c9bba3f45f88943d10a87c']`（12 条）
- 结论: 一致

### wfflab__wsparse-215-v1.0.0-delivery

- 包当前 dirhash: `a7fbb55b9980ea46b247f4d79e49edca734440361d3446c30a57936feead4edb`
- jobs 记录: `['a7fbb55b9980ea46b247f4d79e49edca734440361d3446c30a57936feead4edb']`
- 12 份 job 逐条: `['a7fbb55b9980ea46b247f4d79e49edca734440361d3446c30a57936feead4edb']`（12 条）
- 结论: 一致

### wfflab__wvas-216-v1.0.0-delivery

- 包当前 dirhash: `80ae0a3db4c9f9141003f6a9be8f15b3d047f846c48623a820cb5fe5fcfead8a`
- jobs 记录: `['253161fb10921f9744388a4530f5559dd1f828c8660516d8249ac91c7b6b0306']`
- 12 份 job 逐条: `['253161fb10921f9744388a4530f5559dd1f828c8660516d8249ac91c7b6b0306']`（12 条）
- 结论: **不一致 → 甲方 jobs 门禁会 FAIL**

