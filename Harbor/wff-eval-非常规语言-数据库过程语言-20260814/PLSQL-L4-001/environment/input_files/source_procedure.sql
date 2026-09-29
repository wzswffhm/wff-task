-- 资金归集日终批处理存储过程（Oracle 11g，遗留系统）
-- 业务：每日日终将各分行子账户余额归集到总账户，生成归集流水 settle_flow、
--      归集汇总 settle_summary，并将余额最高的前 3 个账户写入汇总备注供对账。
-- 表：branch_account 分行账户、account_balance 账户余额、settle_flow 归集流水、
--     settle_summary 归集汇总、error_log 错误日志
CREATE OR REPLACE PROCEDURE pkg_settle.daily_settle (
    p_biz_date IN DATE
) AS
    v_flow_id     settle_flow.flow_id%TYPE;
    v_batch_no    VARCHAR2(20);
    v_total       NUMBER(20, 2) := 0;
    v_settle_cnt  NUMBER := 0;
    v_remark      VARCHAR2(4000);

    CURSOR cur_acct IS
        SELECT ba.branch_id, ba.acct_no, NVL(ab.balance, 0) AS balance
        FROM branch_account ba
        JOIN account_balance ab ON ba.acct_no = ab.acct_no
        WHERE ab.status = 'ACTIVE'
        ORDER BY ba.branch_id, ba.acct_no;

BEGIN
    -- 业务日期校验
    IF p_biz_date IS NULL THEN
        RAISE_APPLICATION_ERROR(-20001, '业务日期不能为空');
    END IF;

    v_batch_no := 'JS' || TO_CHAR(p_biz_date, 'YYYYMMDD');

    -- 幂等：清理当日历史数据
    DELETE FROM settle_flow WHERE biz_date = TRUNC(p_biz_date);
    DELETE FROM settle_summary WHERE biz_date = TRUNC(p_biz_date);

    -- 逐账户归集
    FOR r IN cur_acct LOOP
        v_flow_id := seq_settle_flow_id.NEXTVAL;
        INSERT INTO settle_flow (flow_id, batch_no, biz_date, branch_id, acct_no, amount, create_time)
        VALUES (v_flow_id, v_batch_no, TRUNC(p_biz_date), r.branch_id, r.acct_no, r.balance, SYSDATE);
        v_total := v_total + r.balance;
        v_settle_cnt := v_settle_cnt + 1;
    END LOOP;

    -- 归集汇总（MERGE 幂等 upsert）
    MERGE INTO settle_summary t
    USING (
        SELECT TRUNC(p_biz_date) AS biz_date, v_total AS amount, v_settle_cnt AS flow_cnt
        FROM dual
    ) s
    ON (t.biz_date = s.biz_date)
    WHEN MATCHED THEN
        UPDATE SET t.amount = s.amount, t.flow_cnt = s.flow_cnt, t.update_time = SYSDATE
    WHEN NOT MATCHED THEN
        INSERT (biz_date, amount, flow_cnt, create_time, update_time)
        VALUES (s.biz_date, s.amount, s.flow_cnt, SYSDATE, SYSDATE);

    -- 余额最高的前 3 个账户写入备注（对账用）
    FOR r IN (
        SELECT * FROM (
            SELECT ba.branch_id, ba.acct_no, ab.balance
            FROM branch_account ba
            JOIN account_balance ab ON ba.acct_no = ab.acct_no
            WHERE ab.status = 'ACTIVE'
            ORDER BY ab.balance DESC
        ) WHERE ROWNUM <= 3
    ) LOOP
        v_remark := v_remark || DECODE(r.branch_id, NULL, '', r.branch_id) || ':' || r.acct_no || ';';
    END LOOP;

    UPDATE settle_summary
    SET remark = v_remark, update_time = SYSDATE
    WHERE biz_date = TRUNC(p_biz_date);

    COMMIT;

EXCEPTION
    WHEN OTHERS THEN
        ROLLBACK;
        INSERT INTO error_log (log_id, proc_name, biz_date, err_msg, create_time)
        VALUES (seq_error_log_id.NEXTVAL, 'DAILY_SETTLE', TRUNC(p_biz_date), SQLERRM, SYSDATE);
        COMMIT;
        RAISE;
END daily_settle;
/
