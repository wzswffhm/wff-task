# 飞书交付附件（解压后）的 QC 静态门禁

| 附件 | 交付目录 | jobs | 模型门禁 | required | 关键错误 |
|---|---|---|---|---|---|
| wfflab__wcancel-219-v1.0.0-delivery | ✔ | ✔ | ✔ | 0 | 无 |
| wfflab__wciocp-220-v1.0.0-delivery | ✔ | ✔ | ✔ | 0 | 无 |
| wfflab__wsparse-215-v1.0.0-delivery | ✔ | ✔ | ✔ | 0 | 无 |
| wfflab__wspawn-218-v1.0.0-delivery | ✘ | ✔ | ✔ | 0 | environment/Dockerfile:13 运行层使用禁止的 Nano Server/Server Core 镜像：mcr.microsoft.com/windows/servercore:ltsc2022@sha256:76cf422c98ca437b308374d0498280541fa42ac7061bb44015a6c8b70cf4db6a |
| wfflab__wvas-216-v1.0.0-delivery | ✔ | ✘ | ✔ | 0 | ctl-nop-1 was run against a different Task checksum；ctl-nop-2 was run against a different Task checksum；ctl-nop-3 was run against a different Task checksum |
