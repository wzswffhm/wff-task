"""Smoke test for the new enforce_traced / would_change API."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "upstream" / "pycasbin"
sys.path.insert(0, str(ROOT))

from casbin import Enforcer, PolicyMutation  # noqa: E402

MODEL = """
[request_definition]
r = sub, obj, act

[policy_definition]
p = sub, obj, act, eft

[role_definition]
g = _, _

[policy_effect]
e = {effect}

[matchers]
m = g(r.sub, p.sub) && (p.obj == "*" || p.obj == r.obj) && r.act == p.act
"""


def build(effect, policies, groups=()):
    m = Enforcer.new_model(text=MODEL.format(effect=effect))
    e = Enforcer(m)
    for row in policies:
        e.add_policy(*row)
    for row in groups:
        e.add_grouping_policy(*row)
    return e


ALLOW_OVERRIDE = "some(where (p_eft == allow))"
DENY_OVERRIDE = "!some(where (p_eft == deny))"
ALLOW_AND_DENY = "some(where (p_eft == allow)) && !some(where (p_eft == deny))"
PRIORITY = "priority(p_eft) || deny"

ROWS = [
    ["alice", "*", "read", "allow"],
    ["alice", "*", "read", "allow2"],
    ["alice", "data1", "read", "deny"],
    ["alice", "data1", "read", "allow"],
]


def show(label, e, req):
    t = e.enforce_traced(*req)
    print(f"[{label}] req={req}")
    print(f"   enforce()={e.enforce(*req)}  traced.allowed={t.allowed}  disabled={t.disabled}")
    print(f"   matched  = {[ (m.index, m.effect) for m in t.matched ]}")
    print(f"   decisive = {[ (m.index, m.effect) for m in t.decisive ]}")
    assert t.allowed == e.enforce(*req), "consistency violated!"
    print()


if __name__ == "__main__":
    for label, eff in [
        ("allow-override", ALLOW_OVERRIDE),
        ("deny-override", DENY_OVERRIDE),
        ("allow-and-deny", ALLOW_AND_DENY),
        ("priority", PRIORITY),
    ]:
        show(label, build(eff, ROWS), ("alice", "data1", "read"))

    print("### deny-first ordering")
    ROWS2 = [
        ["alice", "*", "read", "deny"],
        ["alice", "data1", "read", "allow"],
        ["alice", "data1", "read", "allow2"],
    ]
    for label, eff in [
        ("allow-override", ALLOW_OVERRIDE),
        ("deny-override", DENY_OVERRIDE),
        ("allow-and-deny", ALLOW_AND_DENY),
        ("priority", PRIORITY),
    ]:
        show(label, build(eff, ROWS2), ("alice", "data1", "read"))

    print("### disabled")
    e = build(ALLOW_OVERRIDE, ROWS)
    e.enable_enforce(False)
    t = e.enforce_traced("bob", "data9", "write")
    print("   ", t)

    print()
    print("### would_change")
    e = build(ALLOW_OVERRIDE, [["alice", "data1", "read", "allow"]])
    print("   before:", e.enforce("alice", "data1", "read"))
    imp = e.would_change("alice", "data1", "read", mutations=PolicyMutation("remove", "p", "p", ("alice", "data1", "read", "allow")))
    print("   remove allow ->", imp)
    imp2 = e.would_change("alice", "data1", "read", mutations=PolicyMutation("remove", "p", "p", ("alice", "data9", "read", "allow")))
    print("   remove absent ->", imp2)
    print("   policy intact:", e.get_policy())

    print()
    print("### would_change with g mutation (isolation check)")
    e = build(
        ALLOW_OVERRIDE,
        [["admin", "data1", "read", "allow"]],
        groups=[["alice", "admin"]],
    )
    print("   alice roles:", e.get_roles_for_user("alice"))
    print("   enforce alice:", e.enforce("alice", "data1", "read"))
    imp3 = e.would_change(
        "bob", "data1", "read",
        mutations=PolicyMutation("add", "g", "g", ("bob", "admin")),
    )
    print("   add bob->admin for bob req ->", imp3)
    print("   AFTER: bob roles =", e.get_roles_for_user("bob"))
    print("   AFTER: alice roles =", e.get_roles_for_user("alice"))
    print("   AFTER: grouping policy =", e.get_grouping_policy())
    print("   AFTER: enforce bob =", e.enforce("bob", "data1", "read"))
