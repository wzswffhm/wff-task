-- PostgreSQL 14 表结构（迁移后，类型已按 PG 规范映射）
CREATE TABLE branch_account (
    branch_id    VARCHAR(10)  NOT NULL,
    acct_no      VARCHAR(32)  NOT NULL,
    account_type VARCHAR(10),
    PRIMARY KEY (acct_no)
);

CREATE TABLE account_balance (
    acct_no      VARCHAR(32)   NOT NULL,
    balance      NUMERIC(20, 2) DEFAULT 0,
    status       VARCHAR(10)   DEFAULT 'ACTIVE',
    update_time  TIMESTAMP,
    PRIMARY KEY (acct_no)
);

CREATE TABLE settle_flow (
    flow_id      BIGINT        NOT NULL,
    batch_no     VARCHAR(20),
    biz_date     DATE,
    branch_id    VARCHAR(10),
    acct_no      VARCHAR(32),
    amount       NUMERIC(20, 2),
    create_time  TIMESTAMP,
    PRIMARY KEY (flow_id)
);

CREATE TABLE settle_summary (
    biz_date     DATE          NOT NULL,
    amount       NUMERIC(20, 2),
    flow_cnt     INTEGER,
    remark       TEXT,
    create_time  TIMESTAMP,
    update_time  TIMESTAMP,
    PRIMARY KEY (biz_date)
);

CREATE TABLE error_log (
    log_id       BIGINT        NOT NULL,
    proc_name    VARCHAR(100),
    biz_date     DATE,
    err_msg      TEXT,
    create_time  TIMESTAMP,
    PRIMARY KEY (log_id)
);

CREATE SEQUENCE seq_settle_flow_id START WITH 100001;
CREATE SEQUENCE seq_error_log_id START WITH 1;
