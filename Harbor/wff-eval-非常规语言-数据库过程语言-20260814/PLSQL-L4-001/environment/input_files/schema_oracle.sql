-- Oracle 11g 表结构（迁移前）
CREATE TABLE branch_account (
    branch_id    VARCHAR2(10)  NOT NULL,
    acct_no      VARCHAR2(32)  NOT NULL,
    account_type VARCHAR2(10),
    CONSTRAINT pk_branch_account PRIMARY KEY (acct_no)
);

CREATE TABLE account_balance (
    acct_no     VARCHAR2(32)  NOT NULL,
    balance     NUMBER(20, 2) DEFAULT 0,
    status      VARCHAR2(10)  DEFAULT 'ACTIVE',
    update_time DATE,
    CONSTRAINT pk_account_balance PRIMARY KEY (acct_no)
);

CREATE TABLE settle_flow (
    flow_id     NUMBER        NOT NULL,
    batch_no    VARCHAR2(20),
    biz_date    DATE,
    branch_id   VARCHAR2(10),
    acct_no     VARCHAR2(32),
    amount      NUMBER(20, 2),
    create_time DATE,
    CONSTRAINT pk_settle_flow PRIMARY KEY (flow_id)
);

CREATE TABLE settle_summary (
    biz_date    DATE          NOT NULL,
    amount      NUMBER(20, 2),
    flow_cnt    NUMBER,
    remark      VARCHAR2(4000),
    create_time DATE,
    update_time DATE,
    CONSTRAINT pk_settle_summary PRIMARY KEY (biz_date)
);

CREATE TABLE error_log (
    log_id      NUMBER        NOT NULL,
    proc_name   VARCHAR2(100),
    biz_date    DATE,
    err_msg     VARCHAR2(4000),
    create_time DATE,
    CONSTRAINT pk_error_log PRIMARY KEY (log_id)
);

CREATE SEQUENCE seq_settle_flow_id START WITH 100001 INCREMENT BY 1;
CREATE SEQUENCE seq_error_log_id START WITH 1 INCREMENT BY 1;
