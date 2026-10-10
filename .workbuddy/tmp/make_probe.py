# -*- coding: utf-8 -*-
"""在容器内真实渲染 chart02，检测 x 轴刻度标签是否重叠。

做法：读取金标 reproduce.py 源码，在保存 chart02 之前插入一段 bbox 检查代码，
写入临时脚本后交给容器执行。
"""
import pathlib
import re

SRC = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-weakness\work_fin-b01_20261006_fix6-150\FIN3-WKN-150\solution\golden_output\FIN3-WKN-150_reproduce.py")
DST = pathlib.Path(r"C:\Users\Administrator\.wff-creds\w150\src\FIN3-WKN-150_reprobe.py")

code = SRC.read_text(encoding="utf-8")
anchor = "save(fig, 'FIN3-WKN-150_chart02_收入与利润口径还原.png')"
assert code.count(anchor) == 1, code.count(anchor)

probe = """fig.canvas.draw()
_r = fig.canvas.get_renderer()
_bs = [t.get_window_extent(renderer=_r) for t in ax.get_xticklabels()]
_ov = []
for _i in range(len(_bs) - 1):
    _a, _b = _bs[_i], _bs[_i + 1]
    _ox = min(_a.x1, _b.x1) - max(_a.x0, _b.x0)
    _oy = min(_a.y1, _b.y1) - max(_a.y0, _b.y0)
    if _ox > 0 and _oy > 0:
        _ov.append((steps[_i][0], steps[_i + 1][0], round(_ox, 1), round(_oy, 1)))
print('XTICK-LABEL-OVERLAP:', _ov if _ov else 'none')
print('XTICK-COUNT:', len(_bs))
"""
code = code.replace(anchor, probe + anchor)
DST.write_text(code, encoding="utf-8")
print("written", DST)
