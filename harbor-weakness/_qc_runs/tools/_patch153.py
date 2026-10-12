import io

p = r"harbor-weakness\_qc_runs\tools\gen_153_data.py"
src = io.open(p, encoding="utf-8").read()
pairs = [
    ('prices[max_sec["sec_code"]]', "unit_price(max_sec, prices)"),
    ('prices[rows[0]["sec_code"]]', "unit_price(rows[0], prices)"),
    ('prices[rows[1]["sec_code"]]', "unit_price(rows[1], prices)"),
    ('prices[l["sec"]["sec_code"]]', 'unit_price(l["sec"], prices)'),
    ('prices[s["sec_code"]]', "unit_price(s, prices)"),
]
for a, b in pairs:
    print(a, src.count(a))
    src = src.replace(a, b)
io.open(p, "w", encoding="utf-8", newline="\n").write(src)
