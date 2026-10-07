# -*- coding: utf-8 -*-
import sys, openpyxl
for fp in sys.argv[1:]:
    print('#' * 70)
    print('FILE:', fp)
    wb = openpyxl.load_workbook(fp, data_only=True)
    for ws in wb.worksheets:
        print(f'--- sheet: {ws.title}  dims={ws.dimensions} ---')
        for row in ws.iter_rows():
            for c in row:
                v = c.value
                if v is None:
                    continue
                s = str(v).strip()
                if not s:
                    continue
                s = s.replace('\n', ' | ')
                print(f'  {c.coordinate}: {s}')
                if c.comment and c.comment.text:
                    print(f'      [批注] {c.comment.text.strip()[:300]}')
