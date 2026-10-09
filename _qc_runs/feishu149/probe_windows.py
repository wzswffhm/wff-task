# -*- coding: utf-8 -*-
"""对比 rules_windows.csv 两种口径下的历史窗口结果：
   A) 现行 golden：窗口内 10 日组合累计收益为负
   B) CSV 字面：窗口内 10 个交易日组合日收益全部为负
"""
import io, json, pathlib, sys, contextlib

BASE = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-weakness\work_fin-b01_20261005_fix7-149\FIN3-WKN-149")
SRC = BASE / "solution/golden_output/FIN3-WKN-149_reproduce.py"
IN = BASE / "environment/input_files"
OUT = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\_qc_runs\feishu149\outA")
OUT.mkdir(parents=True, exist_ok=True)

code = SRC.read_text(encoding="utf-8")
cut = code.index("# ============================ 12. 图表")
code = code[:cut]

extra = r'''
# ---- 两种口径对比 ----
def build_windows_allneg(months, k=10, topn=20):
    wcur = np.array([W.get(c, 0.0) for c in F])
    pool = []
    for mo in months:
        nmo = pd.Period(str(mo)[:7], 'M') + 1
        cand = idx[idx >= nmo.to_timestamp()]
        if not len(cand):
            continue
        st = cand[0]; pos = idx.get_loc(st); w = idx[pos:pos + k]
        if len(w) < k:
            continue
        sub = ret.loc[w, F]
        pr = sub.values @ wcur
        cum = (1 + sub).prod() - 1
        pool.append((float((1 + pd.Series(pr, index=w)).prod() - 1), w, cum, int((pr < 0).sum())))
    allneg = [x for x in pool if x[3] == k]
    allneg.sort(key=lambda x: x[0])
    kept = allneg[:topn]
    return kept, len(pool), len(allneg)

res = {}
for tag, fn in [('cum_neg', None), ('all_daily_neg', build_windows_allneg)]:
    d = {}
    for sk, months in scen.items():
        if fn is None:
            kept, n_cand, n_neg = build_windows(months)
            rows = [[str(x[1][0].date()), str(x[1][-1].date()), round(x[0], 6)] for x in kept]
        else:
            kept, n_cand, n_neg = fn(months)
            rows = [[str(x[1][0].date()), str(x[1][-1].date()), round(x[0], 6), x[3]] for x in kept]
        d[sk] = dict(n_candidates=n_cand, n_qualified=n_neg, kept=rows)
    res[tag] = d
print("===WINDOW_COMPARE===")
print(json.dumps(res, ensure_ascii=False, indent=1))
'''

buf = io.StringIO()
sys.argv = ["reproduce.py", str(IN), str(OUT)]
g = {"__name__": "__main__", "__file__": str(SRC)}
try:
    with contextlib.redirect_stdout(buf):
        exec(compile(code + extra, str(SRC), "exec"), g)
except Exception as e:
    print("EXEC ERROR:", type(e).__name__, e)
out = buf.getvalue()
tail = out[out.find("===WINDOW_COMPARE==="):] if "===WINDOW_COMPARE===" in out else out[-6000:]
print(tail)
# also print historical window section from normal run
try:
    print("\n=== normal (cum) hist ===")
    print(json.dumps(g["R"]["hist_windows"], ensure_ascii=False, indent=1)[:4000])
except Exception as e:
    print(e)
