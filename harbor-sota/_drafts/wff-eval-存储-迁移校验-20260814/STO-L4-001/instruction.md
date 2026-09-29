# 对象存储迁移一致性校验

## 业务场景与角色
你是「云迁」项目组的存储迁移工程师。客户华信集团有约 2.8PB 数据要从自建 Ceph RGW 集群迁到我们新上线的对象存储平台（S3 兼容）。数据复制已由迁移工具完成，但上线评审会前客户要求做一次独立的迁移一致性校验，确认新端数据与旧端完全一致，避免"迁完才发现丢数据"。

旧端 Ceph RGW 已导出完整对象清单 old_manifest.csv（key、size、etag、last_modified 四列）；新端从对象存储 ListObjects 接口也导出了 new_manifest.csv。此外迁移组对 500 个对象做了抽样 ETag 比对，结果在 sample_checksums.json。你的任务是写校验程序，把两端清单与抽样结果比对清楚，输出一份迁移校验报告和一份差异清单，供上线评审会使用。

## 可用源文件（/app/input_files/ 只读）
- old_manifest.csv：旧端对象清单，表头 key,size,etag,last_modified
- new_manifest.csv：新端对象清单，表头 key,size,etag,last_modified
- sample_checksums.json：抽样校验结果，格式 {"sample_size":500,"checked_at":"...","objects":[{"key","old_etag","new_etag","match"}]}

说明：key 是对象在桶里的完整路径；size 是字节数；etag 是内容哈希（32 位小写 hex）；last_modified 是 UTC 时间字符串。

## 交付物要求
| 文件名 | 必交 | 格式说明 |
|---|---|---|
| STO-L4-001_迁移校验报告.json | 是 | UTF-8 JSON，结构见「报告字段要求」 |
| STO-L4-001_迁移差异清单.csv | 是 | UTF-8 CSV，表头 key,object_state,diff_type,old_size,new_size,old_etag,new_etag |

两个文件都放在 /app/output/ 下。

## 比对口径（必须按此口径计算）
- 缺失对象 missing：old_manifest 存在、new_manifest 不存在
- 多余对象 extra：new_manifest 存在、old_manifest 不存在
- 大小不一致 size_mismatch：两端都存在，但 size 不同（内容已变化，etag 也随之不同）
- 校验和不一致 checksum_mismatch：两端都存在、size 相同，但 etag 不同
- 一致 matched：两端都存在，size 和 etag 都相同
- 通过率 pass_rate_percent = matched / old_total * 100，保留 1 位小数

## 报告字段要求
STO-L4-001_迁移校验报告.json 顶层必须包含 task_id、report_generated_at、summary、checks、notes 五个字段。summary 必须包含 old_total、new_total、matched、missing、extra、size_mismatch、checksum_mismatch、pass_rate_percent。checks 必须包含 sample_size、sample_mismatch、sample_pass_rate_percent。notes 用字符串数组，写清每类差异的判定依据。字段名逐字使用上面列出的英文名。

## 差异清单要求
STO-L4-001_迁移差异清单.csv 每个差异对象一行，object_state 取值 missing_in_new / extra_in_new / both，diff_type 取值 missing / extra / size_mismatch / checksum_mismatch，缺哪一侧的值留空字符串。清单总行数必须等于报告里 missing、extra、size_mismatch、checksum_mismatch 之和。

## 硬约束
- 禁止修改 /app/input_files/ 下的任何文件，源文件只读。
- 报告中的数字必须来自清单与抽样结果的真实比对，禁止编造或凭空补数。
- 交付物文件名逐字使用上方表格中的名字，大小写敏感，不得加时间戳、版本号或后缀。
- key 比对区分大小写，禁止 trim、大小写折叠或模糊匹配。
- 若清单本身有矛盾（如同一 key 重复出现），在 notes 里说明并按你的口径处理，不要中断。
- 报告与 CSV 均使用 UTF-8 编码。
