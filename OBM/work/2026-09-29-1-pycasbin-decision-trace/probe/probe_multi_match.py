"""Probe 2: multi-match behaviour per effector (early-exit confirmation)."""

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

EFFECTS = {
    "allow-override": "some(where (p_eft == allow))",
    "deny-override": "!some(where (p_eft == deny))",
    "allow-and-deny": "some(where (p_eft == allow)) && !some(where (p_eft == deny))",
    "priority": "priority(p_eft) || deny",
    "subject-priority": "subjectPriority(p_eft) || deny",
}


def run(label, eff, policies, req=("alice", "data1", "read")):
    m = Enforcer.new_model(text=MODEL.format(effect=eff))
    e = Enforcer(m)
    for row in policies:
        e.add_policy(*row)
    seen = []
    orig = ce.SimpleEval.eval

    def spy(self, parameters):
        out = orig(self, parameters)
        seen.append((parameters.get("p_obj"), parameters.get("p_eft"), bool(out)))
        return out

    ce.SimpleEval.eval = spy
    try:
        res, explain = e.enforce_ex(*req)
    finally:
        ce.SimpleEval.eval = orig
    print(f"  [{eff}]")
    print(f"     policies   = {policies}")
    print(f"     eval order = {seen}")
    print(f"     result     = {res}   explain={explain}")
    print()


if __name__ == "__main__":
    print("### ALL rules match (wildcard), order = allow, allow, deny, allow")
    rows = [
        ["alice", "*", "read", "allow"],
        ["alice", "*", "read", "allow2"],
        ["alice", "data1", "read", "deny"],
        ["alice", "data1", "read", "allow"],
    ]
    for label, eff in EFFECTS.items():
        run(label, eff, rows)

    print("### ALL rules match, order = deny, allow, allow")
    rows2 = [
        ["alice", "*", "read", "deny"],
        ["alice", "data1", "read", "allow"],
        ["alice", "data1", "read", "allow2"],
    ]
    for label, eff in EFFECTS.items():
        run(label, eff, rows2)

    print("### indeterminate eft value")
    rows3 = [
        ["alice", "*", "read", "intdeterminate"],
        ["alice", "data1", "read", "allow"],
    ]
    for label, eff in EFFECTS.items():
        run(label, eff, rows3)
