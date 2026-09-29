"""Behavioural tests for pycasbin decision tracing and change-impact analysis.

These are the feature (F2P) tests: they must FAIL on the unmodified upstream
baseline (``enforce_traced`` / ``would_change`` do not exist) and PASS once the
feature is implemented.

The tests are deliberately self-contained: every model is declared inline and
every policy is added through the public management API, so nothing here
depends on the upstream ``examples/`` directory.
"""

import pytest

from casbin import Enforcer

try:
    from casbin import PolicyMutation
except ImportError:  # pragma: no cover - only on the unpatched baseline

    class PolicyMutation:  # noqa: D401 - placeholder so the module still imports
        """Placeholder standing in for the missing public type."""

        def __init__(self, *args):
            raise AssertionError("casbin.PolicyMutation is not exported")
from casbin.core_enforcer import EnforceContext


ALLOW_OVERRIDE = "some(where (p_eft == allow))"
DENY_OVERRIDE = "!some(where (p_eft == deny))"
ALLOW_AND_DENY = "some(where (p_eft == allow)) && !some(where (p_eft == deny))"
PRIORITY = "priority(p_eft) || deny"
SUBJECT_PRIORITY = "subjectPriority(p_eft) || deny"

EFFECTS = {
    "allow-override": ALLOW_OVERRIDE,
    "deny-override": DENY_OVERRIDE,
    "allow-and-deny": ALLOW_AND_DENY,
    "priority": PRIORITY,
    "subject-priority": SUBJECT_PRIORITY,
}


WILD_MODEL = """
[request_definition]
r = sub, obj, act

[policy_definition]
p = sub, obj, act, eft

[policy_effect]
e = {effect}

[matchers]
m = r.sub == p.sub && (p.obj == "*" || p.obj == r.obj) && r.act == p.act
"""

PLAIN_MODEL = """
[request_definition]
r = sub, obj, act

[policy_definition]
p = sub, obj, act

[policy_effect]
e = {effect}

[matchers]
m = r.sub == p.sub && (p.obj == "*" || p.obj == r.obj) && r.act == p.act
"""

ROLE_MODEL = """
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

DOMAIN_MODEL = """
[request_definition]
r = sub, dom, obj, act

[policy_definition]
p = sub, dom, obj, act

[role_definition]
g = _, _, _

[policy_effect]
e = some(where (p.eft == allow))

[matchers]
m = g(r.sub, p.sub, r.dom) && r.dom == p.dom && r.obj == p.obj && r.act == p.act
"""

EVAL_MODEL = """
[request_definition]
r = sub, obj, act

[policy_definition]
p = sub_rule, obj, act

[policy_effect]
e = {effect}

[matchers]
m = eval(p.sub_rule) && r.obj == p.obj && r.act == p.act
"""

CONDITIONAL_MODEL = """
[request_definition]
r = sub, dom, obj, act

[policy_definition]
p = sub, dom, obj, act

[role_definition]
g = _, _, _, (_, _)

[policy_effect]
e = some(where (p.eft == allow))

[matchers]
m = g(r.sub, p.sub, r.dom) && r.dom == p.dom && r.obj == p.obj && r.act == p.act
"""


class MockSub:
    """A subject carrying attributes, for ``eval()`` matchers."""

    def __init__(self, name, age):
        self.name = name
        self.age = age


def _build(model_text, policies=(), grouping=()):
    enforcer = Enforcer(Enforcer.new_model(text=model_text))
    for row in policies:
        enforcer.add_policy(*row)
    for row in grouping:
        enforcer.add_grouping_policy(*row)
    return enforcer


def _wild(effect, policies, grouping=()):
    return _build(WILD_MODEL.format(effect=effect), policies, grouping)


def _role(effect, policies, grouping=()):
    return _build(ROLE_MODEL.format(effect=effect), policies, grouping)


def _indexes(matches):
    return [m.index for m in matches]


def _effects(matches):
    return [m.effect for m in matches]


# --------------------------------------------------------------------------
# Scenario table.  Every policy below is matched against ("alice", "data1",
# "read"), so "matches" is decided purely by the (p.obj == "*" || ...) clause
# and the early-exit rule of the effector under test.
# --------------------------------------------------------------------------

SCENARIOS = {
    "allow_only": [
        ["alice", "*", "read", "allow"],
        ["alice", "data1", "read", "allow"],
    ],
    "deny_then_allow": [
        ["alice", "*", "read", "deny"],
        ["alice", "data1", "read", "allow"],
    ],
    "allow_then_deny": [
        ["alice", "*", "read", "allow"],
        ["alice", "data1", "read", "deny"],
    ],
    "indeterminate_then_allow": [
        ["alice", "*", "read", "maybe"],
        ["alice", "data1", "read", "allow"],
    ],
    "only_indeterminate": [
        ["alice", "*", "read", "nope"],
    ],
    "deny_only": [
        ["alice", "data1", "read", "deny"],
    ],
    "no_match": [
        ["alice", "data2", "read", "allow"],
    ],
    "indet_indet_deny_indet": [
        ["alice", "*", "read", "aaa"],
        ["alice", "data1", "read", "bbb"],
        ["alice", "data1", "read", "deny"],
        ["alice", "data1", "read", "ccc"],
    ],
}

# name -> (effect -> (allowed, matched indexes, matched effects, decisive indexes))
EXPECTED = {
    "allow_only": {
        "allow-override": (True, [0], ["allow"], [0]),
        "deny-override": (True, [0, 1], ["allow", "allow"], []),
        "allow-and-deny": (True, [0, 1], ["allow", "allow"], []),
        "priority": (True, [0], ["allow"], [0]),
        "subject-priority": (True, [0], ["allow"], [0]),
    },
    "deny_then_allow": {
        "allow-override": (True, [0, 1], ["deny", "allow"], [1]),
        "deny-override": (False, [0], ["deny"], [0]),
        "allow-and-deny": (False, [0], ["deny"], [0]),
        "priority": (False, [0], ["deny"], [0]),
        "subject-priority": (False, [0], ["deny"], [0]),
    },
    "allow_then_deny": {
        "allow-override": (True, [0], ["allow"], [0]),
        "deny-override": (False, [0, 1], ["allow", "deny"], [1]),
        "allow-and-deny": (False, [0, 1], ["allow", "deny"], [1]),
        "priority": (True, [0], ["allow"], [0]),
        "subject-priority": (True, [0], ["allow"], [0]),
    },
    "indeterminate_then_allow": {
        "allow-override": (True, [0, 1], ["indeterminate", "allow"], [1]),
        "deny-override": (True, [0, 1], ["indeterminate", "allow"], []),
        "allow-and-deny": (True, [0, 1], ["indeterminate", "allow"], []),
        "priority": (True, [0, 1], ["indeterminate", "allow"], [1]),
        "subject-priority": (True, [0, 1], ["indeterminate", "allow"], [1]),
    },
    "only_indeterminate": {
        "allow-override": (False, [0], ["indeterminate"], []),
        "deny-override": (True, [0], ["indeterminate"], []),
        "allow-and-deny": (False, [0], ["indeterminate"], []),
        "priority": (False, [0], ["indeterminate"], []),
        "subject-priority": (False, [0], ["indeterminate"], []),
    },
    "deny_only": {
        "allow-override": (False, [0], ["deny"], []),
        "deny-override": (False, [0], ["deny"], [0]),
        "allow-and-deny": (False, [0], ["deny"], [0]),
        "priority": (False, [0], ["deny"], [0]),
        "subject-priority": (False, [0], ["deny"], [0]),
    },
    "no_match": {
        "allow-override": (False, [], [], []),
        "deny-override": (True, [], [], []),
        "allow-and-deny": (False, [], [], []),
        "priority": (False, [], [], []),
        "subject-priority": (False, [], [], []),
    },
    "indet_indet_deny_indet": {
        "allow-override": (False, [0, 1, 2, 3], ["indeterminate", "indeterminate", "deny", "indeterminate"], []),
        "deny-override": (False, [0, 1, 2], ["indeterminate", "indeterminate", "deny"], [2]),
        "allow-and-deny": (False, [0, 1, 2], ["indeterminate", "indeterminate", "deny"], [2]),
        "priority": (False, [0, 1, 2], ["indeterminate", "indeterminate", "deny"], [2]),
        "subject-priority": (False, [0, 1, 2], ["indeterminate", "indeterminate", "deny"], [2]),
    },
}

COMBOS = [(name, effect) for name in SCENARIOS for effect in EFFECTS]


# --------------------------------------------------------------------------
# 1. Consistency with enforce()
# --------------------------------------------------------------------------


@pytest.mark.parametrize("scenario,effect", COMBOS)
def test_traced_allowed_agrees_with_enforce(scenario, effect):
    enforcer = _wild(EFFECTS[effect], SCENARIOS[scenario])
    assert enforcer.enforce_traced("alice", "data1", "read").allowed == enforcer.enforce(
        "alice", "data1", "read"
    )


@pytest.mark.parametrize("scenario,effect", COMBOS)
def test_traced_allowed_matches_expected_table(scenario, effect):
    enforcer = _wild(EFFECTS[effect], SCENARIOS[scenario])
    expected_allowed = EXPECTED[scenario][effect][0]
    assert enforcer.enforce_traced("alice", "data1", "read").allowed is expected_allowed


# --------------------------------------------------------------------------
# 2. matched: which rules the engine observed, in evaluation order
# --------------------------------------------------------------------------


@pytest.mark.parametrize("scenario,effect", COMBOS)
def test_matched_indexes(scenario, effect):
    enforcer = _wild(EFFECTS[effect], SCENARIOS[scenario])
    trace = enforcer.enforce_traced("alice", "data1", "read")
    assert _indexes(trace.matched) == EXPECTED[scenario][effect][1]


@pytest.mark.parametrize("scenario,effect", COMBOS)
def test_matched_effects(scenario, effect):
    enforcer = _wild(EFFECTS[effect], SCENARIOS[scenario])
    trace = enforcer.enforce_traced("alice", "data1", "read")
    assert _effects(trace.matched) == EXPECTED[scenario][effect][2]


@pytest.mark.parametrize("scenario,effect", COMBOS)
def test_matched_rules_are_tuples_of_the_policy_rows(scenario, effect):
    policies = SCENARIOS[scenario]
    enforcer = _wild(EFFECTS[effect], policies)
    trace = enforcer.enforce_traced("alice", "data1", "read")
    for observation in trace.matched:
        assert isinstance(observation.rule, tuple)
        assert list(observation.rule) == policies[observation.index]
        assert observation.ptype == "p"


@pytest.mark.parametrize("scenario,effect", COMBOS)
def test_matched_is_a_tuple(scenario, effect):
    enforcer = _wild(EFFECTS[effect], SCENARIOS[scenario])
    trace = enforcer.enforce_traced("alice", "data1", "read")
    assert isinstance(trace.matched, tuple)
    assert isinstance(trace.decisive, tuple)


# --------------------------------------------------------------------------
# 3. decisive: the rule the engine acted on
# --------------------------------------------------------------------------


@pytest.mark.parametrize("scenario,effect", COMBOS)
def test_decisive_indexes(scenario, effect):
    enforcer = _wild(EFFECTS[effect], SCENARIOS[scenario])
    trace = enforcer.enforce_traced("alice", "data1", "read")
    assert _indexes(trace.decisive) == EXPECTED[scenario][effect][3]


@pytest.mark.parametrize("scenario,effect", COMBOS)
def test_decisive_holds_at_most_one_rule(scenario, effect):
    enforcer = _wild(EFFECTS[effect], SCENARIOS[scenario])
    trace = enforcer.enforce_traced("alice", "data1", "read")
    assert len(trace.decisive) <= 1


@pytest.mark.parametrize("scenario,effect", COMBOS)
def test_decisive_is_a_subset_of_matched(scenario, effect):
    enforcer = _wild(EFFECTS[effect], SCENARIOS[scenario])
    trace = enforcer.enforce_traced("alice", "data1", "read")
    matched_ids = [id(m) for m in trace.matched]
    for observation in trace.decisive:
        assert id(observation) in matched_ids


@pytest.mark.parametrize("scenario,effect", COMBOS)
def test_decisive_rule_has_a_determinate_effect(scenario, effect):
    enforcer = _wild(EFFECTS[effect], SCENARIOS[scenario])
    trace = enforcer.enforce_traced("alice", "data1", "read")
    for observation in trace.decisive:
        assert observation.effect in ("allow", "deny")


# --------------------------------------------------------------------------
# 4. Policy definitions without an _eft token
# --------------------------------------------------------------------------


PLAIN_CASES = [
    ("single_allow", [["alice", "data1", "read"]]),
    ("wildcard_allow", [["alice", "*", "read"]]),
    ("two_allows", [["alice", "*", "read"], ["alice", "data1", "read"]]),
]


@pytest.mark.parametrize("case,policies", PLAIN_CASES)
@pytest.mark.parametrize("effect", sorted(EFFECTS))
def test_without_eft_token_every_match_effect_is_allow(case, policies, effect):
    enforcer = _build(PLAIN_MODEL.format(effect=EFFECTS[effect]), policies)
    trace = enforcer.enforce_traced("alice", "data1", "read")
    assert trace.allowed is True
    assert all(m.effect == "allow" for m in trace.matched)
    assert trace.matched, "expected at least one match"


@pytest.mark.parametrize("effect", sorted(EFFECTS))
def test_without_eft_token_priority_stops_on_first_match(effect):
    policies = [["alice", "*", "read"], ["alice", "data1", "read"]]
    enforcer = _build(PLAIN_MODEL.format(effect=EFFECTS[effect]), policies)
    trace = enforcer.enforce_traced("alice", "data1", "read")
    if effect in ("priority", "subject-priority", "allow-override"):
        assert _indexes(trace.matched) == [0]
        assert _indexes(trace.decisive) == [0]
    else:
        assert _indexes(trace.matched) == [0, 1]
        assert _indexes(trace.decisive) == []


# --------------------------------------------------------------------------
# 5. Empty policy
# --------------------------------------------------------------------------


@pytest.mark.parametrize("effect", sorted(EFFECTS))
def test_empty_policy_truthy_matcher_has_no_attributable_rule(effect):
    model = """
[request_definition]
r = sub, obj, act

[policy_definition]
p = sub, obj, act, eft

[policy_effect]
e = {effect}

[matchers]
m = r.sub == "root"
""".format(effect=EFFECTS[effect])
    enforcer = Enforcer(Enforcer.new_model(text=model))
    trace = enforcer.enforce_traced("root", "data1", "read")
    assert trace.allowed is True
    assert trace.allowed == enforcer.enforce("root", "data1", "read")
    assert trace.matched == ()
    assert trace.decisive == ()
    assert trace.disabled is False


@pytest.mark.parametrize("effect", sorted(EFFECTS))
def test_empty_policy_matcher_referencing_p_uses_empty_tokens(effect):
    model = """
[request_definition]
r = sub, obj, act

[policy_definition]
p = sub, obj, act, eft

[policy_effect]
e = {effect}

[matchers]
m = r.sub == p.sub
""".format(effect=EFFECTS[effect])
    enforcer = Enforcer(Enforcer.new_model(text=model))
    trace = enforcer.enforce_traced("alice", "data1", "read")
    assert trace.allowed == enforcer.enforce("alice", "data1", "read")
    assert trace.matched == ()
    assert trace.decisive == ()
    expected = {
        "allow-override": False,
        "deny-override": True,
        "allow-and-deny": False,
        "priority": False,
        "subject-priority": False,
    }[effect]
    assert trace.allowed is expected


# --------------------------------------------------------------------------
# 6. Disabled enforcement
# --------------------------------------------------------------------------


@pytest.mark.parametrize("effect", sorted(EFFECTS))
def test_disabled_enforcer_reports_bypass(effect):
    enforcer = _wild(EFFECTS[effect], [["alice", "data1", "read", "deny"]])
    enforcer.enable_enforce(False)
    trace = enforcer.enforce_traced("alice", "data1", "read")
    assert trace.allowed is True
    assert trace.disabled is True
    assert trace.matched == ()
    assert trace.decisive == ()


@pytest.mark.parametrize("effect", sorted(EFFECTS))
def test_disabled_enforcer_does_not_validate_request_shape(effect):
    enforcer = _wild(EFFECTS[effect], [["alice", "data1", "read", "allow"]])
    enforcer.enable_enforce(False)
    trace = enforcer.enforce_traced("alice", "data1", "read", "extra")
    assert trace.allowed is True
    assert trace.disabled is True


@pytest.mark.parametrize("effect", sorted(EFFECTS))
def test_enabled_enforcer_marks_disabled_false(effect):
    enforcer = _wild(EFFECTS[effect], [["alice", "data1", "read", "allow"]])
    assert enforcer.enforce_traced("alice", "data1", "read").disabled is False


# --------------------------------------------------------------------------
# 7. Roles and role hierarchies
# --------------------------------------------------------------------------


def test_direct_role_membership_is_traced():
    enforcer = _role(
        ALLOW_OVERRIDE,
        [["admin", "data1", "read", "allow"]],
        grouping=[["alice", "admin"]],
    )
    trace = enforcer.enforce_traced("alice", "data1", "read")
    assert trace.allowed is True
    assert _indexes(trace.matched) == [0]
    assert _indexes(trace.decisive) == [0]


def test_role_without_membership_produces_empty_trace():
    enforcer = _role(
        ALLOW_OVERRIDE,
        [["admin", "data1", "read", "allow"]],
        grouping=[["bob", "admin"]],
    )
    trace = enforcer.enforce_traced("alice", "data1", "read")
    assert trace.allowed is False
    assert trace.matched == ()
    assert trace.decisive == ()


@pytest.mark.parametrize("depth", [1, 2, 3, 4])
def test_multi_level_role_hierarchy(depth):
    chain = ["alice"] + ["role%d" % i for i in range(depth)] + ["admin"]
    grouping = [[chain[i], chain[i + 1]] for i in range(len(chain) - 1)]
    enforcer = _role(ALLOW_OVERRIDE, [["admin", "data1", "read", "allow"]], grouping=grouping)
    trace = enforcer.enforce_traced("alice", "data1", "read")
    assert trace.allowed is True
    assert _indexes(trace.matched) == [0]
    assert _indexes(trace.decisive) == [0]


def test_role_hierarchy_beyond_max_level_is_not_matched():
    # The default role manager only walks 10 levels; a 12-hop chain must not match.
    chain = ["alice"] + ["r%d" % i for i in range(12)] + ["admin"]
    grouping = [[chain[i], chain[i + 1]] for i in range(len(chain) - 1)]
    enforcer = _role(ALLOW_OVERRIDE, [["admin", "data1", "read", "allow"]], grouping=grouping)
    trace = enforcer.enforce_traced("alice", "data1", "read")
    assert trace.allowed is False
    assert trace.matched == ()


DOMAIN_CASES = [
    ("same_domain", ("alice", "domain1", "data1", "read"), True, [0]),
    ("other_domain", ("alice", "domain2", "data1", "read"), False, []),
    ("unknown_user", ("bob", "domain1", "data1", "read"), False, []),
    ("unknown_object", ("alice", "domain1", "data9", "read"), False, []),
    ("unknown_action", ("alice", "domain1", "data1", "write"), False, []),
]


@pytest.mark.parametrize("case,req,expected_allowed,expected_matched", DOMAIN_CASES)
def test_domain_scoped_role_links(case, req, expected_allowed, expected_matched):
    enforcer = _build(
        DOMAIN_MODEL,
        [["admin", "domain1", "data1", "read"]],
        grouping=[["alice", "admin", "domain1"]],
    )
    trace = enforcer.enforce_traced(*req)
    assert trace.allowed is expected_allowed
    assert trace.allowed == enforcer.enforce(*req)
    assert _indexes(trace.matched) == expected_matched
    assert _indexes(trace.decisive) == expected_matched


def test_domain_roles_are_isolated_between_domains():
    enforcer = _build(
        DOMAIN_MODEL,
        [["admin", "domain1", "data1", "read"], ["admin", "domain2", "data1", "read"]],
        grouping=[["alice", "admin", "domain1"], ["bob", "admin", "domain2"]],
    )
    # alice only holds admin inside domain1, bob only inside domain2
    assert _indexes(enforcer.enforce_traced("alice", "domain1", "data1", "read").matched) == [0]
    assert enforcer.enforce_traced("alice", "domain2", "data1", "read").matched == ()
    assert _indexes(enforcer.enforce_traced("bob", "domain2", "data1", "read").matched) == [1]
    assert enforcer.enforce_traced("bob", "domain1", "data1", "read").matched == ()


# --------------------------------------------------------------------------
# 8. eval() matchers
# --------------------------------------------------------------------------


def test_eval_matcher_reports_the_rule_that_matched():
    enforcer = _build(
        EVAL_MODEL.format(effect=ALLOW_OVERRIDE),
        [["r.sub.age > 18 && r.sub.age < 60", "/data1", "read"]],
    )
    trace = enforcer.enforce_traced(MockSub("bob", 30), "/data1", "read")
    assert trace.allowed is True
    assert _indexes(trace.matched) == [0]
    assert _indexes(trace.decisive) == [0]
    assert trace.matched[0].rule == ("r.sub.age > 18 && r.sub.age < 60", "/data1", "read")


def test_eval_matcher_false_rule_is_not_matched():
    enforcer = _build(
        EVAL_MODEL.format(effect=ALLOW_OVERRIDE),
        [["r.sub.age > 18 && r.sub.age < 60", "/data1", "read"]],
    )
    trace = enforcer.enforce_traced(MockSub("alice", 70), "/data1", "read")
    assert trace.allowed is False
    assert trace.matched == ()
    assert trace.decisive == ()


EVAL_TWO_RULES = [
    ["r.sub.age > 18", "/data1", "read"],
    ["r.sub.age > 60", "/data1", "read"],
]


def test_eval_matcher_selects_between_two_rules():
    enforcer = _build(EVAL_MODEL.format(effect=ALLOW_AND_DENY), EVAL_TWO_RULES)
    trace = enforcer.enforce_traced(MockSub("alice", 70), "/data1", "read")
    assert _indexes(trace.matched) == [0, 1]
    assert trace.allowed is True
    assert _indexes(trace.decisive) == []


def test_eval_matcher_with_priority_takes_first_rule():
    enforcer = _build(EVAL_MODEL.format(effect=PRIORITY), EVAL_TWO_RULES)
    trace = enforcer.enforce_traced(MockSub("alice", 70), "/data1", "read")
    assert _indexes(trace.matched) == [0]
    assert _indexes(trace.decisive) == [0]
    assert trace.allowed is True


# --------------------------------------------------------------------------
# 9. EnforceContext
# --------------------------------------------------------------------------


MULTI_MODEL = """
[request_definition]
r = sub, obj, act
r2 = sub, obj, act

[policy_definition]
p = sub, obj, act, eft
p2 = sub, obj, act, eft

[role_definition]
g = _, _

[policy_effect]
e = some(where (p_eft == allow))
e2 = some(where (p_eft == allow))

[matchers]
m = g(r.sub, p.sub) && r.obj == p.obj && r.act == p.act
m2 = r2.sub == p2.sub && r2.obj == p2.obj && r2.act == p2.act
"""


def _multi_enforcer():
    enforcer = Enforcer(Enforcer.new_model(text=MULTI_MODEL))
    enforcer.add_named_policy("p", "alice", "data1", "read", "allow")
    enforcer.add_named_policy("p2", "alice", "data2", "read", "allow")
    enforcer.add_named_policy("p2", "bob", "data2", "read", "deny")
    return enforcer


MULTI_CASES = [
    ("default_p", "p", ("alice", "data1", "read"), True, [0]),
    ("default_p_miss", "p", ("alice", "data2", "read"), False, []),
    ("named_p2_hit", "p2", ("alice", "data2", "read"), True, [0]),
    ("named_p2_deny", "p2", ("bob", "data2", "read"), False, [1]),
]


@pytest.mark.parametrize("case,ptype,req,expected_allowed,expected_matched", MULTI_CASES)
def test_enforce_context_selects_the_named_policy(case, ptype, req, expected_allowed, expected_matched):
    enforcer = _multi_enforcer()
    if ptype == "p":
        trace = enforcer.enforce_traced(*req)
    else:
        context = EnforceContext("r2", "p2", "e2", "m2")
        trace = enforcer.enforce_traced(context, *req)
    assert trace.allowed is expected_allowed
    assert _indexes(trace.matched) == expected_matched


@pytest.mark.parametrize("ptype,req", [("p", ("alice", "data1", "read")), ("p2", ("alice", "data2", "read"))])
def test_enforce_context_ptype_is_reported_on_matches(ptype, req):
    enforcer = _multi_enforcer()
    if ptype == "p":
        trace = enforcer.enforce_traced(*req)
    else:
        trace = enforcer.enforce_traced(EnforceContext("r2", "p2", "e2", "m2"), *req)
    assert trace.matched
    assert all(m.ptype == ptype for m in trace.matched)


def test_new_enforce_context_helper_matches_manual_construction():
    enforcer = _multi_enforcer()
    trace = enforcer.enforce_traced(enforcer.new_enforce_context("2"), "alice", "data2", "read")
    assert trace.allowed is True
    assert _indexes(trace.matched) == [0]


# --------------------------------------------------------------------------
# 10. Error propagation
# --------------------------------------------------------------------------


def test_invalid_request_size_raises_runtime_error():
    enforcer = _wild(ALLOW_OVERRIDE, [["alice", "data1", "read", "allow"]])
    with pytest.raises(RuntimeError):
        enforcer.enforce_traced("alice", "data1")


def test_too_many_request_values_raises_runtime_error():
    enforcer = _wild(ALLOW_OVERRIDE, [["alice", "data1", "read", "allow"]])
    with pytest.raises(RuntimeError):
        enforcer.enforce_traced("alice", "data1", "read", "write")


def test_eval_matcher_with_empty_policy_raises_runtime_error():
    enforcer = _build(EVAL_MODEL.format(effect=ALLOW_OVERRIDE), [])
    with pytest.raises(RuntimeError):
        enforcer.enforce_traced(MockSub("alice", 30), "/data1", "read")


# --------------------------------------------------------------------------
# 11. Tracing must not disturb the enforcer
# --------------------------------------------------------------------------


def test_tracing_does_not_change_the_policy():
    policies = SCENARIOS["indet_indet_deny_indet"]
    enforcer = _wild(ALLOW_AND_DENY, policies)
    before = enforcer.get_policy()
    enforcer.enforce_traced("alice", "data1", "read")
    assert enforcer.get_policy() == before


def test_tracing_does_not_change_role_links():
    enforcer = _role(
        ALLOW_OVERRIDE,
        [["admin", "data1", "read", "allow"]],
        grouping=[["alice", "admin"]],
    )
    enforcer.enforce_traced("alice", "data1", "read")
    assert enforcer.get_roles_for_user("alice") == ["admin"]
    assert enforcer.get_users_for_role("admin") == ["alice"]


# --------------------------------------------------------------------------
# 12. would_change: hypothetical policy edits
# --------------------------------------------------------------------------


def _impact(enforcer, req, *mutations):
    return enforcer.would_change(*req, mutations=list(mutations))


def _remove(sec, ptype, rule):
    return PolicyMutation("remove", sec, ptype, tuple(rule))


def _add(sec, ptype, rule):
    return PolicyMutation("add", sec, ptype, tuple(rule))


def test_would_change_reports_before_changed_and_after():
    enforcer = _wild(ALLOW_OVERRIDE, [["alice", "data1", "read", "allow"]])
    impact = _impact(
        enforcer,
        ("alice", "data1", "read"),
        _remove("p", "p", ["alice", "data1", "read", "allow"]),
    )
    assert impact.changed is True
    assert impact.before is True
    assert impact.after is False
    assert impact.before == enforcer.enforce("alice", "data1", "read")


def test_would_change_removing_the_only_grant_flips_access():
    enforcer = _wild(ALLOW_OVERRIDE, [["alice", "data1", "read", "allow"]])
    impact = _impact(
        enforcer,
        ("alice", "data1", "read"),
        _remove("p", "p", ["alice", "data1", "read", "allow"]),
    )
    assert impact.after is False


REMOVE_NOOP_CASES = [
    ("absent_rule", [["alice", "data1", "read", "allow"]], ["bob", "data1", "read", "allow"]),
    ("other_object", [["alice", "data1", "read", "allow"]], ["alice", "data9", "read", "allow"]),
    ("other_action", [["alice", "data1", "read", "allow"]], ["alice", "data1", "write", "allow"]),
    ("other_subject", [["alice", "data1", "read", "allow"]], ["bob", "data9", "write", "allow"]),
]


@pytest.mark.parametrize("case,policies,removed", REMOVE_NOOP_CASES)
def test_would_change_removing_an_unrelated_rule_is_a_noop(case, policies, removed):
    enforcer = _wild(ALLOW_OVERRIDE, policies)
    impact = _impact(enforcer, ("alice", "data1", "read"), _remove("p", "p", removed))
    assert impact.changed is False
    assert impact.before is True
    assert impact.after is True


def test_would_change_removing_a_duplicate_second_allow_still_grants():
    policies = [["alice", "*", "read", "allow"], ["alice", "data1", "read", "allow"]]
    enforcer = _wild(DENY_OVERRIDE, policies)
    impact = _impact(enforcer, ("alice", "data1", "read"), _remove("p", "p", policies[0]))
    assert impact.changed is False
    assert impact.before is True
    assert impact.after is True


def test_would_change_adding_a_grant_flips_a_denial():
    enforcer = _wild(ALLOW_OVERRIDE, [["bob", "data1", "read", "allow"]])
    impact = _impact(enforcer, ("alice", "data1", "read"), _add("p", "p", ["alice", "data1", "read", "allow"]))
    assert impact.changed is True
    assert impact.before is False
    assert impact.after is True


def test_would_change_adding_a_deny_flips_a_grant():
    enforcer = _wild(ALLOW_AND_DENY, [["alice", "data1", "read", "allow"]])
    impact = _impact(enforcer, ("alice", "data1", "read"), _add("p", "p", ["alice", "data1", "read", "deny"]))
    assert impact.changed is True
    assert impact.before is True
    assert impact.after is False


def test_would_change_adding_a_deny_is_ignored_by_allow_override():
    enforcer = _wild(ALLOW_OVERRIDE, [["alice", "data1", "read", "allow"]])
    impact = _impact(enforcer, ("alice", "data1", "read"), _add("p", "p", ["alice", "data1", "read", "deny"]))
    assert impact.changed is False
    assert impact.after is True


def test_would_change_adding_a_duplicate_rule_is_a_noop():
    policies = [["alice", "data1", "read", "allow"]]
    enforcer = _wild(ALLOW_OVERRIDE, policies)
    impact = _impact(enforcer, ("alice", "data1", "read"), _add("p", "p", policies[0]))
    assert impact.changed is False
    assert impact.after is True


def test_would_change_with_no_mutations_is_a_noop():
    enforcer = _wild(ALLOW_OVERRIDE, [["alice", "data1", "read", "allow"]])
    impact = enforcer.would_change("alice", "data1", "read", mutations=[])
    assert impact.changed is False
    assert impact.before is True
    assert impact.after is True


def test_would_change_accepts_a_bare_mutation():
    enforcer = _wild(ALLOW_OVERRIDE, [["alice", "data1", "read", "allow"]])
    impact = enforcer.would_change(
        "alice", "data1", "read", mutations=_remove("p", "p", ["alice", "data1", "read", "allow"])
    )
    assert impact.changed is True
    assert impact.after is False


def test_would_change_applies_mutations_in_order():
    policies = [["alice", "data1", "read", "allow"]]
    allow = _add("p", "p", policies[0])
    drop = _remove("p", "p", policies[0])

    # remove-then-add: the rule is gone, then re-added -> still granted
    enforcer_a = _wild(ALLOW_OVERRIDE, policies)
    impact_a = _impact(enforcer_a, ("alice", "data1", "read"), drop, allow)
    assert impact_a.after is True
    assert impact_a.changed is False

    # add-then-remove: the add is a duplicate no-op, then the rule is removed
    enforcer_b = _wild(ALLOW_OVERRIDE, policies)
    impact_b = _impact(enforcer_b, ("alice", "data1", "read"), allow, drop)
    assert impact_b.after is False
    assert impact_b.changed is True


def test_would_change_combines_multiple_mutations():
    enforcer = _wild(ALLOW_AND_DENY, [["alice", "data1", "read", "allow"]])
    impact = _impact(
        enforcer,
        ("alice", "data1", "read"),
        _add("p", "p", ["bob", "data1", "read", "allow"]),
        _add("p", "p", ["alice", "data1", "read", "deny"]),
    )
    assert impact.changed is True
    assert impact.after is False


def test_would_change_priority_model_reveals_the_next_rule():
    policies = [
        ["alice", "*", "read", "allow"],
        ["alice", "data1", "read", "deny"],
    ]
    enforcer = _wild(PRIORITY, policies)
    impact = _impact(enforcer, ("alice", "data1", "read"), _remove("p", "p", policies[0]))
    assert impact.before is True
    assert impact.after is False
    assert impact.changed is True


def test_would_change_priority_model_ignores_lower_priority_removal():
    policies = [
        ["alice", "*", "read", "allow"],
        ["alice", "data1", "read", "deny"],
    ]
    enforcer = _wild(PRIORITY, policies)
    impact = _impact(enforcer, ("alice", "data1", "read"), _remove("p", "p", policies[1]))
    assert impact.before is True
    assert impact.after is True
    assert impact.changed is False


def test_would_change_invalid_operation_is_rejected():
    enforcer = _wild(ALLOW_OVERRIDE, [["alice", "data1", "read", "allow"]])
    with pytest.raises(ValueError):
        _impact(enforcer, ("alice", "data1", "read"), PolicyMutation("replace", "p", "p", ("a", "b", "c", "d")))


# --------------------------------------------------------------------------
# 13. would_change must not disturb the enforcer
# --------------------------------------------------------------------------


# (case, policies, (op, sec, ptype, rule)) -- kept as plain data so the module
# still imports when the feature is missing.
SANDBOX_MUTATIONS = [
    ("remove_grant", [["alice", "data1", "read", "allow"]], ("remove", "p", "p", ["alice", "data1", "read", "allow"])),
    ("add_grant", [["bob", "data1", "read", "allow"]], ("add", "p", "p", ["alice", "data1", "read", "allow"])),
    ("add_deny", [["alice", "data1", "read", "allow"]], ("add", "p", "p", ["alice", "data1", "read", "deny"])),
    ("absent_rule", [["alice", "data1", "read", "allow"]], ("remove", "p", "p", ["bob", "data9", "write", "deny"])),
]


@pytest.mark.parametrize("case,policies,spec", SANDBOX_MUTATIONS)
def test_would_change_leaves_the_policy_untouched(case, policies, spec):
    enforcer = _wild(ALLOW_OVERRIDE, policies)
    before = enforcer.get_policy()
    impact = _impact(enforcer, ("alice", "data1", "read"), PolicyMutation(*spec))
    assert impact.before == enforcer.enforce("alice", "data1", "read")
    assert enforcer.get_policy() == before


@pytest.mark.parametrize("case,policies,spec", SANDBOX_MUTATIONS)
def test_would_change_before_matches_enforce(case, policies, spec):
    enforcer = _wild(ALLOW_OVERRIDE, policies)
    assert _impact(enforcer, ("alice", "data1", "read"), PolicyMutation(*spec)).before == enforcer.enforce(
        "alice", "data1", "read"
    )


def test_would_change_does_not_notify_the_watcher():
    class RecordingWatcher:
        def __init__(self):
            self.calls = 0

        def update(self):
            self.calls += 1

        def update_for_add_policy(self, *args):
            self.calls += 1

        def update_for_remove_policy(self, *args):
            self.calls += 1

        def update_for_save_policy(self, *args):
            self.calls += 1

    enforcer = _wild(ALLOW_OVERRIDE, [["alice", "data1", "read", "allow"]])
    watcher = RecordingWatcher()
    enforcer.set_watcher(watcher)
    _impact(enforcer, ("alice", "data1", "read"), _remove("p", "p", ["alice", "data1", "read", "allow"]))
    assert watcher.calls == 0


# --------------------------------------------------------------------------
# 14. would_change on role links
# --------------------------------------------------------------------------


def test_would_change_adding_a_grouping_rule_grants_access():
    enforcer = _role(ALLOW_OVERRIDE, [["admin", "data1", "read", "allow"]])
    assert enforcer.enforce("alice", "data1", "read") is False
    impact = _impact(enforcer, ("alice", "data1", "read"), _add("g", "g", ["alice", "admin"]))
    assert impact.before is False
    assert impact.after is True
    assert impact.changed is True


def test_would_change_removing_a_grouping_rule_revokes_access():
    enforcer = _role(ALLOW_OVERRIDE, [["admin", "data1", "read", "allow"]], grouping=[["alice", "admin"]])
    assert enforcer.enforce("alice", "data1", "read") is True
    impact = _impact(enforcer, ("alice", "data1", "read"), _remove("g", "g", ["alice", "admin"]))
    assert impact.changed is True
    assert impact.after is False


def test_would_change_grouping_edit_is_invisible_to_the_enforcer():
    enforcer = _role(ALLOW_OVERRIDE, [["admin", "data1", "read", "allow"]], grouping=[["alice", "admin"]])
    grouping_before = enforcer.get_grouping_policy()
    _impact(enforcer, ("bob", "data1", "read"), _add("g", "g", ["bob", "admin"]))
    assert enforcer.get_roles_for_user("bob") == []
    assert enforcer.get_roles_for_user("alice") == ["admin"]
    assert enforcer.get_users_for_role("admin") == ["alice"]
    assert enforcer.get_grouping_policy() == grouping_before
    assert enforcer.enforce("bob", "data1", "read") is False
    assert enforcer.enforce("alice", "data1", "read") is True


def test_would_change_removing_absent_grouping_rule_is_a_noop():
    enforcer = _role(ALLOW_OVERRIDE, [["admin", "data1", "read", "allow"]], grouping=[["alice", "admin"]])
    impact = _impact(enforcer, ("alice", "data1", "read"), _remove("g", "g", ["carol", "admin"]))
    assert impact.changed is False
    assert impact.after is True


def test_would_change_grouping_respects_role_hierarchy():
    enforcer = _role(
        ALLOW_OVERRIDE,
        [["admin", "data1", "read", "allow"]],
        grouping=[["dev", "admin"]],
    )
    impact = _impact(enforcer, ("alice", "data1", "read"), _add("g", "g", ["alice", "dev"]))
    assert impact.changed is True
    assert impact.after is True


DOMAIN_MUTATION_CASES = [
    ("grant_in_domain", ("bob", "domain1", "data1", "read"), ("add", "g", "g", ["bob", "admin", "domain1"]), True),
    ("revoke_in_domain", ("alice", "domain1", "data1", "read"), ("remove", "g", "g", ["alice", "admin", "domain1"]), True),
    ("grant_in_wrong_domain", ("bob", "domain2", "data1", "read"), ("add", "g", "g", ["bob", "admin", "domain2"]), False),
    ("unrelated_grant", ("bob", "domain1", "data1", "read"), ("add", "g", "g", ["carol", "admin", "domain1"]), False),
]


@pytest.mark.parametrize("case,req,spec,expected_changed", DOMAIN_MUTATION_CASES)
def test_would_change_domain_scoped_grouping(case, req, spec, expected_changed):
    enforcer = _build(
        DOMAIN_MODEL,
        [["admin", "domain1", "data1", "read"], ["admin", "domain2", "data2", "read"]],
        grouping=[["alice", "admin", "domain1"]],
    )
    impact = _impact(enforcer, req, PolicyMutation(*spec))
    assert impact.changed is expected_changed
    assert impact.before == enforcer.enforce(*req)


def test_would_change_on_named_policy_with_enforce_context():
    enforcer = _multi_enforcer()
    context = EnforceContext("r2", "p2", "e2", "m2")
    assert enforcer.enforce(context, "bob", "data2", "read") is False

    # Removing the matching deny changes nothing under allow-override.
    noop = enforcer.would_change(
        context, "bob", "data2", "read", mutations=_remove("p", "p2", ["bob", "data2", "read", "deny"])
    )
    assert noop.before is False
    assert noop.after is False
    assert noop.changed is False

    # Granting bob an explicit allow flips the decision.
    impact = enforcer.would_change(
        context, "bob", "data2", "read", mutations=_add("p", "p2", ["bob", "data2", "read", "allow"])
    )
    assert impact.before is False
    assert impact.after is True
    assert impact.changed is True

    assert enforcer.get_named_policy("p2") == [
        ["alice", "data2", "read", "allow"],
        ["bob", "data2", "read", "deny"],
    ]
    assert enforcer.enforce(context, "bob", "data2", "read") is False


# --------------------------------------------------------------------------
# 15. Conditional role managers survive the sandbox
# --------------------------------------------------------------------------


def _conditional_enforcer(tmp_path, condition_allows):
    model_path = tmp_path / "conditional_model.conf"
    policy_path = tmp_path / "conditional_policy.csv"
    model_path.write_text(CONDITIONAL_MODEL, encoding="utf-8")
    policy_path.write_text(
        "p, data2_admin, domain2, data2, read\n"
        "g, alice, data2_admin, domain2, p1, p2\n",
        encoding="utf-8",
    )
    enforcer = Enforcer(str(model_path), str(policy_path))
    enforcer.add_named_domain_link_condition_func(
        "g", "alice", "data2_admin", "domain2", lambda a, b: condition_allows
    )
    enforcer.set_named_domain_link_condition_func_params("g", "alice", "data2_admin", "domain2", "p1", "p2")
    return enforcer


def test_conditional_role_link_gates_the_decision(tmp_path):
    denied = _conditional_enforcer(tmp_path, False)
    assert denied.enforce("alice", "domain2", "data2", "read") is False
    assert denied.enforce_traced("alice", "domain2", "data2", "read").matched == ()

    allowed = _conditional_enforcer(tmp_path, True)
    assert allowed.enforce("alice", "domain2", "data2", "read") is True
    assert _indexes(allowed.enforce_traced("alice", "domain2", "data2", "read").matched) == [0]


def test_would_change_keeps_registered_link_conditions(tmp_path):
    enforcer = _conditional_enforcer(tmp_path, False)
    assert enforcer.enforce("alice", "domain2", "data2", "read") is False

    impact = _impact(
        enforcer,
        ("alice", "domain2", "data2", "read"),
        _add("p", "p", ["bob", "domain2", "data2", "read"]),
    )
    # The sandbox must still honour the registered, always-false condition, so
    # alice stays denied and nothing changes.
    assert impact.before is False
    assert impact.after is False
    assert impact.changed is False


def test_would_change_leaves_conditional_enforcer_intact(tmp_path):
    enforcer = _conditional_enforcer(tmp_path, False)
    grouping_before = enforcer.get_grouping_policy()
    _impact(
        enforcer,
        ("bob", "domain2", "data2", "read"),
        _add("g", "g", ["bob", "data2_admin", "domain2", "p1", "p2"]),
    )
    assert enforcer.enforce("alice", "domain2", "data2", "read") is False
    assert enforcer.enforce("bob", "domain2", "data2", "read") is False
    assert enforcer.get_grouping_policy() == grouping_before
    assert grouping_before == [["alice", "data2_admin", "domain2", "p1", "p2"]]
