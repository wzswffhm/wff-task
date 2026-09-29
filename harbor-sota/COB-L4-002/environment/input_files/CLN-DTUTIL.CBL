       >>SOURCE FORMAT FREE
       IDENTIFICATION DIVISION.
       PROGRAM-ID. CLN-DTUTIL.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-IX     PIC 9(03).
       01  WS-JX     PIC 9(03).
       01  WS-DOW    PIC 9(01).
       01  WS-BUSY   PIC X(01).
       LINKAGE SECTION.
       01  LS-FROM-DATE   PIC 9(08).
       01  LS-STEP-COUNT  PIC 9(03).
       01  LS-HOLIDAYS.
           05  LS-HOL OCCURS 100.
               10  LS-HOL-DATE PIC 9(08).
       01  LS-HOL-COUNT    PIC 9(03).
       01  LS-RESULT-DATE  PIC 9(08).
       PROCEDURE DIVISION USING LS-FROM-DATE LS-STEP-COUNT
                               LS-HOLIDAYS LS-HOL-COUNT
                               LS-RESULT-DATE.
           MOVE LS-FROM-DATE TO LS-RESULT-DATE
           PERFORM VARYING WS-IX FROM 1 BY 1
                     UNTIL WS-IX > LS-STEP-COUNT
               MOVE "N" TO WS-BUSY
               PERFORM UNTIL WS-BUSY = "Y"
                   ADD 1 TO LS-RESULT-DATE
                   PERFORM 1000-CHECK
               END-PERFORM
           END-PERFORM
           GOBACK.
       1000-CHECK.
           COMPUTE WS-DOW =
               FUNCTION MOD(
                   FUNCTION INTEGER-OF-DATE(LS-RESULT-DATE) - 1, 7)
           IF WS-DOW < 5
               MOVE "Y" TO WS-BUSY
           ELSE
               MOVE "N" TO WS-BUSY
           END-IF
           IF WS-BUSY = "Y"
               PERFORM VARYING WS-JX FROM 1 BY 1
                         UNTIL WS-JX > LS-HOL-COUNT
                   IF LS-HOL-DATE(WS-JX) = LS-RESULT-DATE
                       MOVE "N" TO WS-BUSY
                   END-IF
               END-PERFORM
           END-IF.