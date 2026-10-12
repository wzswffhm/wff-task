# -*- coding: utf-8 -*-
import io
import json

p = r"harbor-weakness\_qc_runs\g4-153\trials\oracle-153\verifier\reward-details.json"
d = json.load(io.open(p, encoding="utf-8"))
rew = d["reward"]
crit = rew["criteria"]
print("details score:", rew.get("score"), "criteria:", len(crit))
tot_pos = sum(c["weight"] for c in crit if not c.get("negate"))
print("pos pool:", tot_pos)
got = sum(c["weight"] * c["value"] for c in crit if not c.get("negate"))
neg = sum(c["weight"] * (1 - c["value"]) for c in crit if c.get("negate"))
print("pos got:", got, "neg penalty:", neg, "=> (got-neg)/pool =", (got - neg) / tot_pos)
print()
for c in crit:
    if c["value"] < 1.0:
        print("### ", c["id"], "value=", c["value"], "weight=", c["weight"],
              "negate=", c.get("negate", False), "raw=", c.get("raw"))
        print((c.get("reasoning") or "")[:1500].replace("\n", " "))
        print()
