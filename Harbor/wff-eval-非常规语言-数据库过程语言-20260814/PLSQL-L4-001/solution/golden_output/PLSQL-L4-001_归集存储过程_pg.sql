-- 资金归集日终批处理存储过程（PostgreSQL 14，PL/pgSQL）
-- 由 Oracle 版 pkg_settle.daily_settle 迁移改写，业务逻辑保持一致
-- 表结构见 schema_pg.sql
CREATE OR REPLACE FUNCTION pkg_settle.daily_settle(p_biz_date DATE)
RETURNS void AS $$
DECLARE
    v_flow_id    BIGINT;
    v_batch_no   VARCHAR(20);
    v_total      NUMERIC(20, 2) := 0;
    v_settle_cnt INTEGER := 0;
    v_remark     TEXT := '';
    r            RECORD;
BEGIN
    -- 业务日期校验（原 RAISE_APPLICATION_ERROR）
    IF p_biz_date IS NULL THEN
        RAISE EXCEPTION '业务日期不能为空';
    END IF;

    -- 批次号：TO_CHAR 在 PG 中语法兼容
    v_batch_no := 'JS' || TO_CHAR(p_biz_date, 'YYYYMMDD');

    -- 幂等：清理当日历史数据（参数为 DATE，无需 TRUNC）
    DELETE FROM settle_flow WHERE biz_date = p_biz_date;
    DELETE FROM settle_summary WHERE biz_date = p_biz_date;

    -- 逐账户归集（原显式游标 FOR LOOP → FOR r IN SELECT ... LOOP）
    FOR r IN
        SELECT ba.branch_id, ba.acct_no, COALESCE(ab.balance, 0) AS balance
        FROM branch_account ba
        JOIN account_balance ab ON ba.acct_no = ab.acct_no
        WHERE ab.status = 'ACTIVE'
        ORDER BY ba.branch_id, ba.acct_no
    LOOP
        v_flow_id := nextval('seq_settle_flow_id');
        INSERT INTO settle_flow (flow_id, batch_no, biz_date, branch_id, acct_no, amount, create_time)
        VALUES (v_flow_id, v_batch_no, p_biz_date, r.branch_id, r.acct_no, r.balance, now());
        v_total := v_total + r.balance;
        v_settle_cnt := v_settle_cnt + 1;
    END LOOP;

    -- 归集汇总（原 MERGE INTO ... USING dual → INSERT ... ON CONFLICT）
    INSERT INTO settle_summary (biz_date, amount, flow_cnt, create_time, update_time)
    VALUES (p_biz_date, v_total, v_settle_cnt, now(), now())
    ON CONFLICT (biz_date) DO UPDATE
        SET amount = EXCLUDED.amount,
            flow_cnt = EXCLUDED.flow_cnt,
            update_time = now();

    -- 余额最高的前 3 个账户写入备注（原 ROWNUM <= 3 → LIMIT 3；DECODE → COALESCE）
    FOR r IN
        SELECT ba.branch_id, ba.acct_no, ab.balance
        FROM branch_account ba
        JOIN account_balance ab ON ba.acct_no = ab.acct_no
        WHERE ab.status = 'ACTIVE'
        ORDER BY ab.balance DESC
        LIMIT 3
    LOOP
        v_remark := v_remark || COALESCE(r.branch_id, '') || ':' || r.acct_no || ';';
    END LOOP;

    UPDATE settle_summary
    SET remark = v_remark, update_time = now()
    WHERE biz_date = p_biz_date;

    COMMIT;

EXCEPTION
    WHEN OTHERS THEN
        ROLLBACK;
        INSERT INTO error_log (log_id, proc_name, biz_date, err_msg, create_time)
        VALUES (nextval('seq_error_log_id'), 'DAILY_SETTLE', p_biz_date, SQLERRM, now());
        COMMIT;
        RAISE;
END;
$$ LANGUAGE plpgsql;
