# 存储过程迁移说明

## 概述
本迁移将 Oracle 11g 的 `pkg_settle.daily_settle`（资金归集日终批处理）改写为 PostgreSQL 14 的 PL/pgSQL 函数，业务逻辑保持一致：幂等清理、逐账户归集、汇总 upsert、前 3 大额账户备注、异常回滚并写错误日志。

## Oracle 特有语法 → PostgreSQL 映射表

| Oracle 语法 | 出现位置 | PostgreSQL 映射 | 说明 |
|---|---|---|---|
| `%TYPE`（settle_flow.flow_id%TYPE） | 变量声明 | 直接用 `BIGINT`（也可用 `table.column%TYPE`，PG 同样支持） | 类型一致性由 schema_pg.sql 保证 |
| 显式游标 `CURSOR ... IS SELECT` + 游标 FOR LOOP | cur_acct 归集循环 | `FOR r IN SELECT ... LOOP` | PL/pgSQL 隐式记录，无需显式打开/关闭 |
| 序列 `seq_settle_flow_id.NEXTVAL` | 流水号 | `nextval('seq_settle_flow_id')` | 序列保留，仅调用语法变化 |
| `SYSDATE` | create_time / update_time | `now()` | 返回带时区当前时间 |
| `TRUNC(p_biz_date)` | biz_date 清理/过滤 | 参数为 `DATE` 时直接用 `p_biz_date`；若为 timestamp 用 `CAST(x AS DATE)` 或 `date_trunc('day', x)` | PG 的 TRUNC 仅用于 numeric |
| `NVL(ab.balance, 0)` | 归集查询 | `COALESCE(ab.balance, 0)` | 语义等价 |
| `DECODE(r.branch_id, NULL, '', ...)` | 备注拼接 | `COALESCE(r.branch_id, '')` | 单值判断用 COALESCE 即可；多分支用 CASE WHEN |
| `TO_CHAR(p_biz_date, 'YYYYMMDD')` | 批次号 | `TO_CHAR(p_biz_date, 'YYYYMMDD')` | PG 兼容，语法不变 |
| `MERGE INTO ... USING (SELECT ... FROM dual)` | settle_summary upsert | `INSERT ... ON CONFLICT (biz_date) DO UPDATE` | 按主键幂等 upsert |
| `ROWNUM <= 3`（内联视图） | 前 3 大额账户 | `LIMIT 3` | PG 标准分页/限量语法 |
| `RAISE_APPLICATION_ERROR(-20001, ...)` | 参数校验 | `RAISE EXCEPTION '业务日期不能为空'` | 自定义错误 |
| `EXCEPTION WHEN OTHERS` | 异常处理 | `EXCEPTION WHEN OTHERS` | 语法基本一致 |
| `SQLERRM` | err_msg | `SQLERRM` | PG 兼容，返回错误消息 |
| `RAISE`（重抛） | 异常尾部 | `RAISE` | 语义一致 |
| `PROCEDURE` | 整体形态 | `FUNCTION ... RETURNS void` | PL/pgSQL 常用函数形态；PG11+ 也支持 PROCEDURE，本迁移用 FUNCTION |

## 类型映射表

| Oracle | PostgreSQL |
|---|---|
| NUMBER(20,2) | NUMERIC(20,2) |
| NUMBER | BIGINT / NUMERIC |
| VARCHAR2(n) | VARCHAR(n) |
| VARCHAR2(4000) | TEXT |
| DATE | DATE（纯日期）/ TIMESTAMP（含时间） |
| 序列 | SEQUENCE（保留） |

## 等价性自查
- 归集条件：`status = 'ACTIVE'` 且 `balance > 0` 判定逻辑由 `NVL(ab.balance,0)` + 查询条件保持一致；
- 幂等清理：先 DELETE 当日 settle_flow / settle_summary，再写入，可重跑；
- 汇总口径：总额 = 逐账户累加，笔数 = 循环计数；
- 异常路径：ROLLBACK → 写 error_log（含 SQLERRM）→ RAISE 重抛。
