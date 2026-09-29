#!/bin/bash
# Oracle 入口：把参考答案复制到 /app/output
set -euo pipefail
cp -f /solution/golden_output/COB-L4-002_LoanAccrual.java   /app/output/
cp -f /solution/golden_output/COB-L4-002_AccrualResult.txt  /app/output/
cp -f /solution/golden_output/COB-L4-002_MigrationReport.md /app/output/
cp -f /solution/golden_output/COB-L4-002_SummaryByCurrency.txt /app/output/