       >>SOURCE FORMAT FREE
       IDENTIFICATION DIVISION.
       PROGRAM-ID. CLN-LOANACCR.
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT MSTR-FILE ASSIGN TO "ACCOUNT_MASTER.DAT"
               ORGANIZATION IS LINE SEQUENTIAL.
           SELECT TRAN-FILE ASSIGN TO "TRAN_HISTORY.DAT"
               ORGANIZATION IS LINE SEQUENTIAL.
           SELECT RATE-FILE ASSIGN TO "RATE_ADJ.DAT"
               ORGANIZATION IS LINE SEQUENTIAL.
           SELECT SCHD-FILE ASSIGN TO "SCHEDULE.DAT"
               ORGANIZATION IS LINE SEQUENTIAL.
           SELECT CAL-FILE  ASSIGN TO "CALENDAR.DAT"
               ORGANIZATION IS LINE SEQUENTIAL.
           SELECT PROC-FILE ASSIGN TO "PROC_DATE.TXT"
               ORGANIZATION IS LINE SEQUENTIAL.
           SELECT OUT-FILE  ASSIGN TO "COB-L4-002_AccrualResult.txt"
               ORGANIZATION IS LINE SEQUENTIAL.
           SELECT FX-FILE   ASSIGN TO "FX_RATE.DAT"
               ORGANIZATION IS LINE SEQUENTIAL.
           SELECT OUT2-FILE ASSIGN TO "COB-L4-002_SummaryByCurrency.txt"
               ORGANIZATION IS LINE SEQUENTIAL.
       DATA DIVISION.
       FILE SECTION.
       FD  MSTR-FILE.
       01  MSTR-REC.
           COPY CLN-MASTER.
       FD  TRAN-FILE.
       01  TRAN-REC.
           COPY CLN-TRAN.
       FD  RATE-FILE.
       01  RATE-REC.
           COPY CLN-RATE.
       FD  SCHD-FILE.
       01  SCHD-REC.
           COPY CLN-SCHED.
       FD  CAL-FILE.
       01  CAL-REC.
           COPY CLN-CAL.
       FD  PROC-FILE.
       01  PROC-REC.
           05  PROC-DATE-FIELD PIC X(08).
       FD  FX-FILE.
       01  FX-REC.
           05  FX-CCY     PIC X(04).
           05  FX-EFF     PIC 9(08).
           05  FX-RATE    PIC 9(08).
       FD  OUT-FILE.
       01  OUT-REC PIC X(220).
       FD  OUT2-FILE.
       01  OUT2-REC PIC X(220).
       WORKING-STORAGE SECTION.
       01  WS-FLAGS.
           05  WS-EOF-M  PIC X VALUE "N".
           05  WS-EOF-T  PIC X VALUE "N".
           05  WS-EOF-R  PIC X VALUE "N".
           05  WS-EOF-S  PIC X VALUE "N".
           05  WS-EOF-C  PIC X VALUE "N".
           05  WS-EOF-FX PIC X VALUE "N".
       01  WS-DATES.
           05  WS-RUN    PIC 9(08).
           05  WS-CUR    PIC 9(08).
           05  WS-CI     PIC 9(08).
           05  WS-RI     PIC 9(08).
           05  WS-NI     PIC 9(08).
           05  WS-ND     PIC 9(08).
       01  WS-CNTS.
           05  WS-I      PIC 9(03).
           05  WS-J      PIC 9(03).
           05  WS-K      PIC 9(03).
           05  WS-TCNT   PIC 9(03).
           05  WS-RCNT   PIC 9(03).
           05  WS-SCNT   PIC 9(03).
           05  WS-CCNT   PIC 9(03).
           05  WS-GP     PIC 9(03).
       01  WS-ACCT      PIC X(10).
       01  WS-PREV      PIC X(10) VALUE LOW-VALUES.
       01  WS-MONEY.
           05  WS-PRIN  PIC 9(12)V99.
           05  WS-AN    PIC 9(12)V99.
           05  WS-AP    PIC 9(12)V99.
           05  WS-POST  PIC 9(12)V99.
           05  WS-RPY   PIC 9(12)V99.
           05  WS-FEE   PIC 9(12)V99.
           05  WS-LFE   PIC 9(12)V99.
           05  WS-OVD   PIC 9(12)V99.
           05  WS-BASE  PIC 9(12)V99.
           05  WS-DAILY PIC 9(12)V99.
           05  WS-PAY   PIC 9(12)V99.
           05  WS-TAKE  PIC 9(12)V99.
       01  WS-RATES.
           05  WS-MARG  PIC 9V99.
           05  WS-EFF   PIC 9(02)V9(4).
           05  WS-PEN   PIC 9(02)V9(5).
           05  WS-DIV   PIC 9(03).
       01  WS-SW      PIC X(01).
       01  WS-ME      PIC X(01).
       01  WS-CLSD    PIC X(01).
       01  WS-TRAN-TBL.
           05  WS-TR OCCURS 300.
               10  WS-TR-VD  PIC 9(08).
               10  WS-TR-CD  PIC X(04).
               10  WS-TR-AM  PIC S9(12)V99.
       01  WS-RATE-TBL.
           05  WS-RT OCCURS 60.
               10  WS-RT-DT  PIC 9(08).
               10  WS-RT-RT  PIC 9(02)V9(4).
       01  WS-SCHD-TBL.
           05  WS-SC OCCURS 300.
               10  WS-SC-DUE  PIC 9(08).
               10  WS-SC-OVD  PIC 9(08).
               10  WS-SC-REM  PIC 9(12)V99.
       01  WS-FX-TBL.
           05  WS-FX OCCURS 40.
               10  WS-FX-DT  PIC 9(08).
               10  WS-FX-RT  PIC 9(08).
       01  WS-FXCNT  PIC 9(03).
       01  WS-FX-OPEN PIC 9(08).
       01  WS-AMT-FX  PIC S9(12)V99.
       01  WS-HOL-TBL.
           05  WS-HOL OCCURS 100.
               10  WS-HOL-DT  PIC 9(08).
       01  WS-TOTS.
           05  WS-T-N    PIC 9(03).
           05  WS-T-PRIN PIC 9(12)V99.
           05  WS-T-AN   PIC 9(12)V99.
           05  WS-T-AP   PIC 9(12)V99.
           05  WS-T-POST PIC 9(12)V99.
           05  WS-T-RPY  PIC 9(12)V99.
           05  WS-T-OVD  PIC 9(12)V99.
           05  WS-T-FEE  PIC 9(12)V99.
           05  WS-T-LFE  PIC 9(12)V99.
       01  WS-T2.
           05  WS-T2-N    PIC 9(03).
           05  WS-T2-PRIN PIC 9(12)V99.
           05  WS-T2-AN   PIC 9(12)V99.
           05  WS-T2-AP   PIC 9(12)V99.
           05  WS-T2-POST PIC 9(12)V99.
           05  WS-T2-RPY  PIC 9(12)V99.
           05  WS-T2-OVD  PIC 9(12)V99.
           05  WS-T2-FEE  PIC 9(12)V99.
           05  WS-T2-LFE  PIC 9(12)V99.
       01  WS-CNY-ED.
           05  WS-CN-N    PIC 9(03).
           05  WS-CN-PRIN PIC 9(12).99.
           05  WS-CN-AN   PIC 9(12).99.
           05  WS-CN-AP   PIC 9(12).99.
           05  WS-CN-ACC  PIC 9(12).99.
           05  WS-CN-POST PIC 9(12).99.
           05  WS-CN-RPY  PIC 9(12).99.
           05  WS-CN-OVD  PIC 9(12).99.
           05  WS-CN-FEE  PIC 9(12).99.
           05  WS-CN-LFE  PIC 9(12).99.
       01  WS-CN-NUM.
           05  WS-CN-NUM-N    PIC 9(03).
           05  WS-CN-NUM-PRIN PIC 9(12)V99.
           05  WS-CN-NUM-AN   PIC 9(12)V99.
           05  WS-CN-NUM-AP   PIC 9(12)V99.
           05  WS-CN-NUM-ACC  PIC 9(12)V99.
           05  WS-CN-NUM-POST PIC 9(12)V99.
           05  WS-CN-NUM-RPY  PIC 9(12)V99.
           05  WS-CN-NUM-OVD  PIC 9(12)V99.
           05  WS-CN-NUM-FEE  PIC 9(12)V99.
           05  WS-CN-NUM-LFE  PIC 9(12)V99.
       01  WS-T-ED.
           05  WS-T-PRIN-E PIC 9(12).99.
           05  WS-T-AN-E   PIC 9(12).99.
           05  WS-T-AP-E   PIC 9(12).99.
           05  WS-T-ACC-E  PIC 9(12).99.
           05  WS-T-POST-E PIC 9(12).99.
           05  WS-T-RPY-E  PIC 9(12).99.
           05  WS-T-OVD-E  PIC 9(12).99.
           05  WS-T-FEE-E  PIC 9(12).99.
           05  WS-T-LFE-E  PIC 9(12).99.
       01  WS-T2-ED.
           05  WS-T2-PRIN-E PIC 9(12).99.
           05  WS-T2-AN-E   PIC 9(12).99.
           05  WS-T2-AP-E   PIC 9(12).99.
           05  WS-T2-ACC-E  PIC 9(12).99.
           05  WS-T2-POST-E PIC 9(12).99.
           05  WS-T2-RPY-E  PIC 9(12).99.
           05  WS-T2-OVD-E  PIC 9(12).99.
           05  WS-T2-FEE-E  PIC 9(12).99.
           05  WS-T2-LFE-E  PIC 9(12).99.
       01  WS-OUT-LINE.
           05  WS-O-ACCT   PIC X(10).
           05  FILLER      PIC X VALUE "|".
           05  WS-O-NAME   PIC X(24).
           05  FILLER      PIC X VALUE "|".
           05  WS-O-PROD   PIC X(04).
           05  FILLER      PIC X VALUE "|".
           05  WS-O-PRIN   PIC 9(12).99.
           05  FILLER      PIC X VALUE "|".
           05  WS-O-AN     PIC 9(12).99.
           05  FILLER      PIC X VALUE "|".
           05  WS-O-AP     PIC 9(12).99.
           05  FILLER      PIC X VALUE "|".
           05  WS-O-ACC    PIC 9(12).99.
           05  FILLER      PIC X VALUE "|".
           05  WS-O-POST   PIC 9(12).99.
           05  FILLER      PIC X VALUE "|".
           05  WS-O-RPY    PIC 9(12).99.
           05  FILLER      PIC X VALUE "|".
           05  WS-O-OVD    PIC 9(12).99.
           05  FILLER      PIC X VALUE "|".
           05  WS-O-FEE    PIC 9(12).99.
           05  FILLER      PIC X VALUE "|".
           05  WS-O-LFE    PIC 9(12).99.
           05  FILLER      PIC X VALUE "|".
           05  WS-O-BASIS  PIC X(04).
           05  FILLER      PIC X VALUE "|".
           05  WS-O-STAT   PIC X(01).
       PROCEDURE DIVISION.
       MAIN.
           PERFORM 1000-INIT
           PERFORM UNTIL WS-EOF-M = "Y"
               READ MSTR-FILE
                   AT END MOVE "Y" TO WS-EOF-M
               END-READ
               IF WS-EOF-M NOT = "Y"
                   PERFORM 2000-ACCT
               END-IF
           END-PERFORM
           PERFORM 9000-SUMMARY
           PERFORM 9100-CLOSE
           STOP RUN.
       1000-INIT.
           OPEN INPUT MSTR-FILE TRAN-FILE RATE-FILE SCHD-FILE
                CAL-FILE PROC-FILE FX-FILE
                OUTPUT OUT-FILE OUT2-FILE
           READ PROC-FILE
           MOVE PROC-DATE-FIELD TO WS-RUN
           MOVE ZERO TO WS-T-N WS-T-PRIN WS-T-AN WS-T-AP WS-T-POST
                        WS-T-RPY WS-T-OVD WS-T-FEE WS-T-LFE
           MOVE ZERO TO WS-T2-N WS-T2-PRIN WS-T2-AN WS-T2-AP WS-T2-POST
                        WS-T2-RPY WS-T2-OVD WS-T2-FEE WS-T2-LFE
           MOVE "N" TO WS-EOF-M WS-EOF-T WS-EOF-R WS-EOF-S WS-EOF-C
           MOVE "N" TO WS-EOF-FX
           PERFORM 1100-LOAD-CAL
           PERFORM 1100-LOAD-FX.
       1100-LOAD-CAL.
           PERFORM UNTIL WS-EOF-C = "Y"
               READ CAL-FILE
                   AT END MOVE "Y" TO WS-EOF-C
               END-READ
               IF WS-EOF-C NOT = "Y"
                   ADD 1 TO WS-CCNT
                   MOVE CL-HOLIDAY TO WS-HOL-DT(WS-CCNT)
               END-IF
           END-PERFORM.
       1100-LOAD-FX.
           MOVE ZERO TO WS-FXCNT
           PERFORM UNTIL WS-EOF-FX = "Y"
               READ FX-FILE
                   AT END MOVE "Y" TO WS-EOF-FX
               END-READ
               IF WS-EOF-FX NOT = "Y"
                   ADD 1 TO WS-FXCNT
                   MOVE FX-EFF  TO WS-FX-DT(WS-FXCNT)
                   MOVE FX-RATE TO WS-FX-RT(WS-FXCNT)
               END-IF
           END-PERFORM.
       2000-ACCT.
           MOVE ZERO TO WS-PRIN WS-AN WS-AP WS-POST WS-RPY
                        WS-FEE WS-LFE WS-TCNT WS-RCNT WS-SCNT
           MOVE "N" TO WS-CLSD
           MOVE 1 TO WS-FX-OPEN
           IF ACCT-CURRENCY = "USD"
               PERFORM VARYING WS-K FROM 1 BY 1
                         UNTIL WS-K > WS-FXCNT
                   IF WS-FX-DT(WS-K) <= ACCT-OPEN-DATE
                       MOVE WS-FX-RT(WS-K) TO WS-FX-OPEN
                   END-IF
               END-PERFORM
           END-IF
           COMPUTE WS-PRIN ROUNDED =
               ACCT-PRINCIPAL * WS-FX-OPEN / 10000
           PERFORM 2100-LOAD-TRAN
           PERFORM 2200-LOAD-RATE
           PERFORM 2300-LOAD-SCHD
           COMPUTE WS-CI = FUNCTION INTEGER-OF-DATE(ACCT-OPEN-DATE)
           COMPUTE WS-RI = FUNCTION INTEGER-OF-DATE(WS-RUN)
           PERFORM VARYING WS-CI FROM WS-CI BY 1
                     UNTIL WS-CI > WS-RI
               COMPUTE WS-CUR = FUNCTION DATE-OF-INTEGER(WS-CI)
               PERFORM 3000-DAY-TRAN
               PERFORM 4000-OVD
               PERFORM 5000-ACCR
           END-PERFORM
           PERFORM 8000-DETAIL
           PERFORM 8100-ADD-TOT.
       2100-LOAD-TRAN.
           MOVE ACCT-NO TO WS-ACCT
           IF WS-PREV = WS-ACCT
               PERFORM 2110-PENDING
           END-IF
           PERFORM UNTIL WS-EOF-T = "Y"
               READ TRAN-FILE
                   AT END MOVE "Y" TO WS-EOF-T
               END-READ
               IF WS-EOF-T = "Y"
                   EXIT PERFORM
               END-IF
               IF TR-ACCT-NO NOT = WS-ACCT
                   MOVE TR-ACCT-NO TO WS-PREV
                   EXIT PERFORM
               END-IF
               ADD 1 TO WS-TCNT
               MOVE TR-VALUE-DATE TO WS-TR-VD(WS-TCNT)
               MOVE TR-CODE       TO WS-TR-CD(WS-TCNT)
               MOVE TR-AMOUNT     TO WS-TR-AM(WS-TCNT)
           END-PERFORM.
       2110-PENDING.
           ADD 1 TO WS-TCNT
           MOVE TR-VALUE-DATE TO WS-TR-VD(WS-TCNT)
           MOVE TR-CODE       TO WS-TR-CD(WS-TCNT)
           MOVE TR-AMOUNT     TO WS-TR-AM(WS-TCNT).
       2200-LOAD-RATE.
           PERFORM UNTIL WS-EOF-R = "Y"
               READ RATE-FILE
                   AT END MOVE "Y" TO WS-EOF-R
               END-READ
               IF WS-EOF-R = "Y"
                   EXIT PERFORM
               END-IF
               IF RT-ACCT-NO > WS-ACCT
                   EXIT PERFORM
               END-IF
               IF RT-ACCT-NO = WS-ACCT
                   ADD 1 TO WS-RCNT
                   MOVE RT-EFF-DATE TO WS-RT-DT(WS-RCNT)
                   MOVE RT-NEW-RATE TO WS-RT-RT(WS-RCNT)
               END-IF
           END-PERFORM.
       2300-LOAD-SCHD.
           COMPUTE WS-GP = ACCT-GRACE-DAYS + 1
           PERFORM UNTIL WS-EOF-S = "Y"
               READ SCHD-FILE
                   AT END MOVE "Y" TO WS-EOF-S
               END-READ
               IF WS-EOF-S = "Y"
                   EXIT PERFORM
               END-IF
               IF SC-ACCT-NO > WS-ACCT
                   EXIT PERFORM
               END-IF
               IF SC-ACCT-NO = WS-ACCT
                   ADD 1 TO WS-SCNT
                   MOVE SC-DUE-DATE  TO WS-SC-DUE(WS-SCNT)
                   COMPUTE WS-SC-REM(WS-SCNT) ROUNDED =
                       SC-PRINCIPAL * WS-FX-OPEN / 10000
                   CALL 'CLN-DTUTIL' USING WS-SC-DUE(WS-SCNT)
                                           WS-GP
                                           WS-HOL-TBL
                                           WS-CCNT
                                           WS-SC-OVD(WS-SCNT)
               END-IF
           END-PERFORM.
       3000-DAY-TRAN.
           PERFORM VARYING WS-I FROM 1 BY 1
                     UNTIL WS-I > WS-TCNT
               IF WS-TR-VD(WS-I) = WS-CUR
                   EVALUATE WS-TR-CD(WS-I)
                       WHEN "DISB"
                           COMPUTE WS-AMT-FX ROUNDED =
                               WS-TR-AM(WS-I) * WS-FX-OPEN / 10000
                           ADD WS-AMT-FX TO WS-PRIN
                       WHEN "RPAY"
                           COMPUTE WS-AMT-FX ROUNDED =
                               WS-TR-AM(WS-I) * WS-FX-OPEN / 10000
                           COMPUTE WS-PAY = - WS-AMT-FX
                           PERFORM 3100-POOL-P
                           PERFORM 3100-POOL-F
                           PERFORM 3100-POOL-L
                           PERFORM 3100-POOL-N
                           PERFORM 3200-PRIN
                       WHEN "PINT"
                           ADD WS-TR-AM(WS-I) TO WS-POST
                           ADD WS-TR-AM(WS-I) TO WS-PRIN
                           MOVE ZERO TO WS-AN WS-AP
                       WHEN "FEE"
                           COMPUTE WS-AMT-FX ROUNDED =
                               WS-TR-AM(WS-I) * WS-FX-OPEN / 10000
                           ADD WS-AMT-FX TO WS-FEE
                       WHEN "LFE"
                           COMPUTE WS-AMT-FX ROUNDED =
                               WS-TR-AM(WS-I) * WS-FX-OPEN / 10000
                           ADD WS-AMT-FX TO WS-LFE
                       WHEN "CLSE"
                           ADD WS-PRIN TO WS-RPY
                           MOVE ZERO TO WS-PRIN WS-AN WS-AP
                           PERFORM VARYING WS-J FROM 1 BY 1
                                     UNTIL WS-J > WS-SCNT
                               MOVE ZERO TO WS-SC-REM(WS-J)
                           END-PERFORM
                           MOVE "Y" TO WS-CLSD
                   END-EVALUATE
               END-IF
           END-PERFORM.
       3100-POOL-P.
           IF WS-PAY > ZERO AND WS-AP > ZERO
               IF WS-PAY >= WS-AP
                   SUBTRACT WS-AP FROM WS-PAY
                   MOVE ZERO TO WS-AP
               ELSE
                   SUBTRACT WS-PAY FROM WS-AP
                   MOVE ZERO TO WS-PAY
               END-IF
           END-IF.
       3100-POOL-N.
           IF WS-PAY > ZERO AND WS-AN > ZERO
               IF WS-PAY >= WS-AN
                   SUBTRACT WS-AN FROM WS-PAY
                   MOVE ZERO TO WS-AN
               ELSE
                   SUBTRACT WS-PAY FROM WS-AN
                   MOVE ZERO TO WS-PAY
               END-IF
           END-IF.
       3100-POOL-F.
           IF WS-PAY > ZERO AND WS-FEE > ZERO
               IF WS-PAY >= WS-FEE
                   SUBTRACT WS-FEE FROM WS-PAY
                   MOVE ZERO TO WS-FEE
               ELSE
                   SUBTRACT WS-PAY FROM WS-FEE
                   MOVE ZERO TO WS-PAY
               END-IF
           END-IF.
       3100-POOL-L.
           IF WS-PAY > ZERO AND WS-LFE > ZERO
               IF WS-PAY >= WS-LFE
                   SUBTRACT WS-LFE FROM WS-PAY
                   MOVE ZERO TO WS-LFE
               ELSE
                   SUBTRACT WS-PAY FROM WS-LFE
                   MOVE ZERO TO WS-PAY
               END-IF
           END-IF.
       3200-PRIN.
           IF WS-PAY > ZERO
               SUBTRACT WS-PAY FROM WS-PRIN
               ADD WS-PAY TO WS-RPY
               PERFORM VARYING WS-J FROM 1 BY 1
                         UNTIL WS-J > WS-SCNT OR WS-PAY = ZERO
                   IF WS-SC-REM(WS-J) > ZERO
                       IF WS-PAY >= WS-SC-REM(WS-J)
                           SUBTRACT WS-SC-REM(WS-J) FROM WS-PAY
                           MOVE ZERO TO WS-SC-REM(WS-J)
                       ELSE
                           SUBTRACT WS-PAY FROM WS-SC-REM(WS-J)
                           MOVE ZERO TO WS-PAY
                       END-IF
                   END-IF
               END-PERFORM
           END-IF.
       4000-OVD.
           MOVE ZERO TO WS-OVD
           PERFORM VARYING WS-J FROM 1 BY 1
                     UNTIL WS-J > WS-SCNT
               IF WS-SC-REM(WS-J) > ZERO
                   IF WS-CUR >= WS-SC-OVD(WS-J)
                       ADD WS-SC-REM(WS-J) TO WS-OVD
                   END-IF
               END-IF
           END-PERFORM.
       5000-ACCR.
           MOVE "N" TO WS-SW
           IF WS-CLSD = "Y"
               MOVE "Y" TO WS-SW
           END-IF
           IF (ACCT-STATUS = "N" OR "L")
              AND ACCT-STATUS-DATE NOT = ZERO
              AND WS-CUR >= ACCT-STATUS-DATE
               MOVE "Y" TO WS-SW
           END-IF
           IF WS-SW = "N"
               PERFORM 5100-RATE
               COMPUTE WS-BASE = WS-PRIN - WS-OVD
               IF WS-BASE < ZERO
                   MOVE ZERO TO WS-BASE
               END-IF
               IF WS-BASE > ZERO
                   IF ACCT-BASIS = "B30D"
                       COMPUTE WS-NI = WS-CI + 1
                       COMPUTE WS-ND =
                           FUNCTION DATE-OF-INTEGER(WS-NI)
                       IF WS-CUR(5:2) NOT = WS-ND(5:2)
                           MOVE "Y" TO WS-ME
                       ELSE
                           MOVE "N" TO WS-ME
                       END-IF
                       IF WS-ME = "Y"
                           COMPUTE WS-DAILY ROUNDED =
                               WS-BASE * WS-EFF / 12 / 100
                           ADD WS-DAILY TO WS-AN
                       END-IF
                   ELSE
                       IF ACCT-BASIS = "A365"
                           MOVE 365 TO WS-DIV
                       ELSE
                           MOVE 360 TO WS-DIV
                       END-IF
                       COMPUTE WS-DAILY ROUNDED =
                           WS-BASE * WS-EFF / WS-DIV / 100
                       ADD WS-DAILY TO WS-AN
                   END-IF
               END-IF
               IF WS-OVD > ZERO
                   COMPUTE WS-DAILY ROUNDED =
                       WS-OVD * WS-PEN / 365 / 100
                   ADD WS-DAILY TO WS-AP
               END-IF
           END-IF.
       5100-RATE.
           MOVE ACCT-ANNUAL-RATE TO WS-EFF
           PERFORM VARYING WS-K FROM 1 BY 1
                     UNTIL WS-K > WS-RCNT
               IF WS-RT-DT(WS-K) <= WS-CUR
                   MOVE WS-RT-RT(WS-K) TO WS-EFF
               END-IF
           END-PERFORM
           EVALUATE TRUE
               WHEN WS-PRIN <= 50000
                   MOVE 1.00 TO WS-MARG
               WHEN WS-PRIN <= 200000
                   MOVE 0.50 TO WS-MARG
               WHEN OTHER
                   MOVE 0.00 TO WS-MARG
           END-EVALUATE
           IF WS-EFF NOT = ZERO
               COMPUTE WS-EFF = WS-EFF + WS-MARG
           END-IF
           COMPUTE WS-PEN = WS-EFF * 1.5.
       8000-DETAIL.
           MOVE ACCT-NO      TO WS-O-ACCT
           MOVE ACCT-NAME    TO WS-O-NAME
           MOVE ACCT-PRODUCT TO WS-O-PROD
           MOVE WS-PRIN      TO WS-O-PRIN
           MOVE WS-AN        TO WS-O-AN
           MOVE WS-AP        TO WS-O-AP
           COMPUTE WS-O-ACC  = WS-AN + WS-AP
           MOVE WS-POST      TO WS-O-POST
           MOVE WS-RPY       TO WS-O-RPY
           MOVE WS-OVD       TO WS-O-OVD
           MOVE WS-FEE       TO WS-O-FEE
           MOVE WS-LFE       TO WS-O-LFE
           MOVE ACCT-BASIS   TO WS-O-BASIS
           IF WS-CLSD = "Y"
               MOVE "C" TO WS-O-STAT
           ELSE
               MOVE ACCT-STATUS TO WS-O-STAT
           END-IF
           MOVE WS-OUT-LINE  TO OUT-REC
           WRITE OUT-REC.
       8100-ADD-TOT.
           ADD 1 TO WS-T-N
           ADD WS-PRIN TO WS-T-PRIN
           IF ACCT-CURRENCY = "USD"
               ADD 1 TO WS-T2-N
               ADD WS-PRIN TO WS-T2-PRIN
               ADD WS-AN   TO WS-T2-AN
               ADD WS-AP   TO WS-T2-AP
               ADD WS-POST TO WS-T2-POST
               ADD WS-RPY  TO WS-T2-RPY
               ADD WS-OVD  TO WS-T2-OVD
               ADD WS-FEE  TO WS-T2-FEE
               ADD WS-LFE  TO WS-T2-LFE
           END-IF
           ADD WS-AN   TO WS-T-AN
           ADD WS-AP   TO WS-T-AP
           ADD WS-POST TO WS-T-POST
           ADD WS-RPY  TO WS-T-RPY
           ADD WS-OVD  TO WS-T-OVD
           ADD WS-FEE  TO WS-T-FEE
           ADD WS-LFE  TO WS-T-LFE.
       9000-SUMMARY.
           MOVE WS-T-PRIN TO WS-T-PRIN-E
           MOVE WS-T-AN   TO WS-T-AN-E
           MOVE WS-T-AP   TO WS-T-AP-E
           COMPUTE WS-T-ACC-E = WS-T-AN + WS-T-AP
           MOVE WS-T-POST TO WS-T-POST-E
           MOVE WS-T-RPY  TO WS-T-RPY-E
           MOVE WS-T-OVD  TO WS-T-OVD-E
           MOVE WS-T-FEE  TO WS-T-FEE-E
           MOVE WS-T-LFE  TO WS-T-LFE-E
           MOVE SPACES TO OUT-REC
           STRING "TOTAL|ACCTS=" WS-T-N
                  "|PRINCIPAL=" WS-T-PRIN-E
                  "|NORMAL="   WS-T-AN-E
                  "|PENALTY="  WS-T-AP-E
                  "|ACCRUED="  WS-T-ACC-E
                  "|POSTED="   WS-T-POST-E
                  "|REPAID="   WS-T-RPY-E
                  "|OVERDUE="  WS-T-OVD-E
                  "|FEES="     WS-T-FEE-E
                  "|LATEFEES=" WS-T-LFE-E
               INTO OUT-REC
           END-STRING
           WRITE OUT-REC.
           PERFORM 9050-SUMMARY2.
       9050-SUMMARY2.
           MOVE WS-T2-PRIN TO WS-T2-PRIN-E
           MOVE WS-T2-AN   TO WS-T2-AN-E
           MOVE WS-T2-AP   TO WS-T2-AP-E
           COMPUTE WS-T2-ACC-E = WS-T2-AN + WS-T2-AP
           MOVE WS-T2-POST TO WS-T2-POST-E
           MOVE WS-T2-RPY  TO WS-T2-RPY-E
           MOVE WS-T2-OVD  TO WS-T2-OVD-E
           MOVE WS-T2-FEE  TO WS-T2-FEE-E
           MOVE WS-T2-LFE  TO WS-T2-LFE-E
           MOVE SPACES TO OUT2-REC
           STRING "CURRENCY=USD|ACCTS=" WS-T2-N
                  "|PRINCIPAL=" WS-T2-PRIN-E
                  "|NORMAL="   WS-T2-AN-E
                  "|PENALTY="  WS-T2-AP-E
                  "|ACCRUED="  WS-T2-ACC-E
                  "|POSTED="   WS-T2-POST-E
                  "|REPAID="   WS-T2-RPY-E
                  "|OVERDUE="  WS-T2-OVD-E
                  "|FEES="     WS-T2-FEE-E
                  "|LATEFEES=" WS-T2-LFE-E
               INTO OUT2-REC
           END-STRING
           WRITE OUT2-REC
           COMPUTE WS-CN-NUM-N = WS-T-N - WS-T2-N
           COMPUTE WS-CN-NUM-PRIN = WS-T-PRIN - WS-T2-PRIN
           COMPUTE WS-CN-NUM-AN = WS-T-AN - WS-T2-AN
           COMPUTE WS-CN-NUM-AP = WS-T-AP - WS-T2-AP
           COMPUTE WS-CN-NUM-ACC = (WS-T-AN + WS-T-AP) - (WS-T2-AN + WS-T2-AP)
           COMPUTE WS-CN-NUM-POST = WS-T-POST - WS-T2-POST
           COMPUTE WS-CN-NUM-RPY = WS-T-RPY - WS-T2-RPY
           COMPUTE WS-CN-NUM-OVD = WS-T-OVD - WS-T2-OVD
           COMPUTE WS-CN-NUM-FEE = WS-T-FEE - WS-T2-FEE
           COMPUTE WS-CN-NUM-LFE = WS-T-LFE - WS-T2-LFE
           MOVE WS-CN-NUM-N    TO WS-CN-N
           MOVE WS-CN-NUM-PRIN TO WS-CN-PRIN
           MOVE WS-CN-NUM-AN   TO WS-CN-AN
           MOVE WS-CN-NUM-AP   TO WS-CN-AP
           MOVE WS-CN-NUM-ACC  TO WS-CN-ACC
           MOVE WS-CN-NUM-POST TO WS-CN-POST
           MOVE WS-CN-NUM-RPY  TO WS-CN-RPY
           MOVE WS-CN-NUM-OVD  TO WS-CN-OVD
           MOVE WS-CN-NUM-FEE  TO WS-CN-FEE
           MOVE WS-CN-NUM-LFE  TO WS-CN-LFE
           MOVE SPACES TO OUT2-REC
           STRING "CURRENCY=CNY|ACCTS=" WS-CN-N
                  "|PRINCIPAL=" WS-CN-PRIN
                  "|NORMAL="   WS-CN-AN
                  "|PENALTY="  WS-CN-AP
                  "|ACCRUED="  WS-CN-ACC
                  "|POSTED="   WS-CN-POST
                  "|REPAID="   WS-CN-RPY
                  "|OVERDUE="  WS-CN-OVD
                  "|FEES="     WS-CN-FEE
                  "|LATEFEES=" WS-CN-LFE
               INTO OUT2-REC
           END-STRING
           WRITE OUT2-REC
           MOVE SPACES TO OUT2-REC
           STRING "TOTAL|ACCTS=" WS-T-N
                  "|PRINCIPAL=" WS-T-PRIN-E
                  "|NORMAL="   WS-T-AN-E
                  "|PENALTY="  WS-T-AP-E
                  "|ACCRUED="  WS-T-ACC-E
                  "|POSTED="   WS-T-POST-E
                  "|REPAID="   WS-T-RPY-E
                  "|OVERDUE="  WS-T-OVD-E
                  "|FEES="     WS-T-FEE-E
                  "|LATEFEES=" WS-T-LFE-E
               INTO OUT2-REC
           END-STRING
           WRITE OUT2-REC.
       9100-CLOSE.
           CLOSE MSTR-FILE TRAN-FILE RATE-FILE SCHD-FILE
                 CAL-FILE PROC-FILE FX-FILE OUT-FILE OUT2-FILE.