# -*- coding: utf-8 -*-
"""FIN3-WKN-149 二次返修 —— 收尾小改：
1) TOML 五档锚点改为规范的 `5=` 写法（消除 check_rubrics 的档位锚点 warn）；
2) task.toml 版本 1.0.6 → 1.0.8（与 fix8 批次代号一致；修正 fix7 版本文档与实际包不一致）。
"""
import pathlib
import sys

sys.stdout.reconfigure(encoding='utf-8')
PKG = pathlib.Path(r'C:\Users\Administrator\Desktop\wff-task\harbor-weakness\FIN3-WKN-149')
TOML = PKG / 'tests' / 'rubrics.toml'
TASK = PKG / 'task.toml'

anchors = ['5', '4', '3', '2', '1']
data = TOML.read_bytes()
txt = data.decode('utf-8')
n_anchor = 0
for a in anchors:
    old = f'**{a} = '
    new = f'**{a}='
    c = txt.count(old)
    n_anchor += c
    txt = txt.replace(old, new)
TOML.write_bytes(txt.encode('utf-8'))
print(f'锚点 `**N = ` → `**N=` 共替换 {n_anchor} 处（期望 20）')

t = TASK.read_bytes().decode('utf-8')
old = 'version = "1.0.6"'
new = 'version = "1.0.8"'
print('task.toml version 命中:', t.count(old))
t = t.replace(old, new)
TASK.write_bytes(t.encode('utf-8'))
print('task.toml version → 1.0.8')
