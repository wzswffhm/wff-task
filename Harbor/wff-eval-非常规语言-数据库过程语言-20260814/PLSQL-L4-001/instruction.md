# 遗留存储过程 Oracle→PostgreSQL 迁移改写

## 业务场景与角色
你是某银行核心系统组的数据库工程师，负责国产化"去 O"（去 Oracle）改造。总行决定把核心系统的存量存储过程迁到 PostgreSQL 14，你分到的是资金归集日终批处理 `pkg_settle.daily_settle`。这个过程每天日终把各分行子账户余额归集到总账户，生成归集流水和汇总，出问题要能查到错误记录。它跑了十几年，业务口径不能动，改造后要过评审。

## 可用源文件（/app/input_files/ 只读）
- source_procedure.sql：Oracle 版存储过程源码，含 %TYPE、游标、序列、MERGE、ROWNUM、异常处理等 Oracle 特有语法
- schema_oracle.sql：迁移前 Oracle 表结构与序列定义
- schema_pg.sql：迁移后 PostgreSQL 表结构与序列定义（类型已映射，按这个结构写代码）
- migration_requirements.md：迁移需求说明（业务逻辑要点与交付要求）

## 交付物要求
| 文件名 | 必交 | 格式说明 |
|---|---|---|
| PLSQL-L4-001_归集存储过程_pg.sql | 是 | PostgreSQL PL/pgSQL 存储过程（UTF-8，可执行 DDL） |
| PLSQL-L4-001_迁移说明.md | 是 | 迁移说明文档（UTF-8 Markdown） |

两个文件都放在 /app/output/ 下。

## 业务逻辑要点（改写后必须保持）
- 业务日期为空时报错；
- 先删除当日的 settle_flow 与 settle_summary（幂等，支持重跑）；
- 遍历状态为 ACTIVE 的分行账户，逐笔写 settle_flow（流水号取自序列），同时累加总额与笔数；
- 把总额与笔数按 biz_date 幂等 upsert 到 settle_summary；
- 取余额最高的前 3 个 ACTIVE 账户，把 "分支号:账号;" 追加到 settle_summary.remark；
- 发生异常时回滚并写 error_log（含错误信息），然后重抛。

## 迁移说明要求
迁移说明.md 必须包含一张「Oracle 特有语法 → PostgreSQL 映射」表，逐项说明本次代码中出现的 %TYPE、游标 FOR LOOP、序列 NEXTVAL、SYSDATE、TRUNC(date)、NVL、DECODE、TO_CHAR、MERGE、ROWNUM、RAISE_APPLICATION_ERROR、EXCEPTION WHEN OTHERS、SQLERRM 等语法的处理方式；并列出本次用到的类型映射（如 NUMBER→NUMERIC、VARCHAR2→VARCHAR、VARCHAR2(4000)→TEXT）。

## 硬约束
- 禁止修改 /app/input_files/ 下的任何文件。
- 改写必须基于 schema_pg.sql 的表结构，不得编造不存在的表、列或序列。
- 交付物文件名逐字使用上方表格中的名字，大小写敏感，不得加时间戳、版本号或后缀。
- 业务口径（归集条件、金额计算、清理逻辑、异常处理）必须与源过程一致，不得为简化而改变逻辑。
- 两个文件均使用 UTF-8 编码。
