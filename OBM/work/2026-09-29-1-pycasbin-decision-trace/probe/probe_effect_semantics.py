"""Probe: empirically confirm pycasbin effector semantics before freezing the
public contract for `enforce_traced` / `would_change`.

Run:
  <venv>/python.exe probe_effect_semantics.py   (see sys.path bootstrap below)
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "upstream" / "pycasbin"
sys.path.insert(0, str(ROOT))

import casbin.core_enforcer as ce  # noqa: E402
from casbin import Enforcer  # noqa: E402

MODEL = """
[request_definition]
r = sub, obj, act

[policy_definition]
p = sub, obj, act, eft

[policy_effect]
e = {effect}

[matchers]
m = r.sub == p.sub && (p.obj == "*" || p.obj == r.obj) && r.act == p.act
"""

ROWS = [
    ["alice", "data1", "read", "allow"],
    ["alice", "data2", "read", "allow"],
    ["alice", "data3", "read", "deny"],
    ["alice", "data4", "read", "allow"],
]

EFFECTS = {
    "allow-override": "some(where (p_eft == allow))",
    "deny-override": "!some(where (p_eft == deny))",
    "allow-and-deny": "some(where (p_eft == allow)) && !some(where (p_eft == deny))",
    "priority": "priority(p_eft) || deny",
}


def build(effect, policies):
    m = Enforcer.new_model(text=MODEL.format(effect=effect))
    e = Enforcer(m)
    for row in policies:
        e.add_policy(*row)
    return e


def probe(label, effect, policies, req):
    e = build(effect, policies)
    seen = []
    orig = ce.SimpleEval.eval

    def spy(self, parameters):
        out = orig(self, parameters)
        seen.append((parameters.get("p_obj"), bool(out)))
        return out

    ce.SimpleEval.eval = spy
    try:
        res, explain = e.enforce_ex(*req)
    finally:
        ce.SimpleEval.eval = orig

    print(f"[{label}] effect={effect!r}")
    print(f"    policies        = {policies}")
    print(f"    request         = {req}")
    print(f"    eval order      = {seen}")
    print(f"    enforce_ex      = ({res}, explain={explain})")
    print(f"    enforce         = {e.enforce(*req)}")
    print()


if __name__ == "__main__":
    print("#" * 78)
    print("# CASE A: allow, allow, deny, allow  -> request alice/data1/read")
    print("#" * 78)
    for label, eff in EFFECTS.items():
        probe(label, eff, ROWS, ("alice", "data1", "read"))

    print("#" * 78)
    print("# CASE B: deny first -> deny, allow, allow, allow")
    print("#" * 78)
    rows_b = [
        ["alice", "data0", "read", "deny"],
        ["alice", "data1", "read", "allow"],
        ["alice", "data2", "read", "allow"],
        ["alice", "data3", "read", "allow"],
    ]
    for label, eff in EFFECTS.items():
        probe(label, eff, rows_b, ("alice", "data1", "read"))

    print("#" * 78)
    print("# CASE C: single deny only -> request alice/data1/read")
    print("#" * 78)
    rows_c = [["alice", "data0", "read", "deny"]]
    for label, eff in EFFECTS.items():
        probe(label, eff, rows_c, ("alice", "data1", "read"))

    print("#" * 78)
    print("# CASE D: no eft column at all (implicit allow)")
    print("#" * 78)
    MODEL_NOEFT = MODEL.replace("p = sub, obj, act, eft", "p = sub, obj, act")
    for label, eff in EFFECTS.items():
        m = Enforcer.new_model(text=MODEL_NOEFT.format(effect=eff))
        e = Enforcer(m)
        for row in [["alice", "data1", "read"], ["alice", "data2", "read"]]:
            e.add_policy(*row)
        print(f"[{label}] policy without eft -> enforce={e.enforce('alice', 'data1', 'read')}")
    print()

    print("#" * 78)
    print("# CASE E: disabled enforcer")
    print("#" * 78)
    e = build(EFFECTS["allow-override"], [["alice", "data1", "read", "allow"]])
    e.enable_enforce(False)
    print(f"    enforce={e.enforce('bob', 'data9', 'write')}  enforce_ex={e.enforce_ex('bob', 'data9', 'write')}")
