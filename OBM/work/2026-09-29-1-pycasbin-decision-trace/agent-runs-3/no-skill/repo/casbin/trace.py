# Copyright 2021 The casbin Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Decision tracing and hypothetical policy impact analysis."""

import copy
import logging
from collections import namedtuple

from casbin.effect import Effector, effect_to_bool, get_effector
from casbin.model.policy_op import PolicyOp
from casbin.util import util


PolicyMatch = namedtuple("PolicyMatch", ["ptype", "rule", "index", "effect"])
TraceResult = namedtuple("TraceResult", ["allowed", "matched", "decisive", "disabled"])
PolicyMutation = namedtuple("PolicyMutation", ["op", "sec", "ptype", "rule"])
ChangeImpact = namedtuple("ChangeImpact", ["changed", "before", "after"])


def _normalize_mutations(mutations):
    if isinstance(mutations, PolicyMutation):
        mutation_list = [mutations]
    else:
        mutation_list = list(mutations)

    normalized = []
    for mutation in mutation_list:
        if not isinstance(mutation, PolicyMutation):
            raise TypeError("mutations must contain PolicyMutation objects")
        if mutation.op not in ("add", "remove"):
            raise ValueError("PolicyMutation.op must be 'add' or 'remove'")
        if mutation.sec not in ("p", "g"):
            raise ValueError("PolicyMutation.sec must be 'p' or 'g'")
        normalized.append(mutation._replace(rule=list(mutation.rule)))
    return normalized


def _clone_role_manager(rm):
    """Clone a role manager without invoking Assertion's reference-sharing deepcopy."""
    # The default managers supplied by this package are copied structurally.  A
    # custom manager remains usable when it provides its own copy support; the
    # fallback is a shallow copy so stateless custom managers keep working.
    if hasattr(rm, "clone"):
        return rm.clone()

    try:
        return copy.deepcopy(rm)
    except Exception:
        return copy.copy(rm)


def _clone_for_sandbox(enforcer):
    """
    Create a transient enforcer while preserving model objects and registered
    condition functions, but deliberately detach the copied model from the
    original role-manager graph.
    """
    sandbox = enforcer.__class__.__new__(enforcer.__class__)
    sandbox.__dict__.update(enforcer.__dict__)
    sandbox.logger = logging.getLogger("casbin.trace.sandbox")
    sandbox.model = copy.deepcopy(enforcer.model)
    sandbox.fm = copy.copy(enforcer.fm)
    sandbox.fm.fm = dict(enforcer.fm.get_functions())
    sandbox.watcher = None
    sandbox.adapter = None
    sandbox.auto_save = False
    sandbox.auto_notify_watcher = False

    sandbox.rm_map = {ptype: _clone_role_manager(rm) for ptype, rm in enforcer.rm_map.items()}
    sandbox.cond_rm_map = {
        ptype: _clone_role_manager(rm) for ptype, rm in enforcer.cond_rm_map.items()
    }

    # Connect copied assertions to their detached role graphs. The default
    # managers were structurally cloned, including condition functions and
    # request parameters, so no text/model serialization is involved.
    if "g" in sandbox.model.keys():
        for ptype, assertion in sandbox.model["g"].items():
            if ptype in sandbox.rm_map:
                assertion.rm = sandbox.rm_map[ptype]
            if ptype in sandbox.cond_rm_map:
                assertion.cond_rm = sandbox.cond_rm_map[ptype]

    return sandbox


def enforce_traced(self, *rvals):
    """Return the enforce decision together with matched and decisive rules."""
    disabled = not self.enabled
    if disabled:
        result = TraceResult(True, (), (), True)
        return result

    rtype = "r"
    ptype = "p"
    etype = "e"
    mtype = "m"

    functions = self.fm.get_functions()

    if "g" in self.model.keys():
        for key, ast in self.model["g"].items():
            if key in self.cond_rm_map:
                from casbin.util import generate_conditional_g_function
                functions[key] = generate_conditional_g_function(self.cond_rm_map[key])
            elif key in self.rm_map:
                from casbin.util import generate_g_function
                functions[key] = generate_g_function(self.rm_map[key])

    request_values = rvals
    from casbin.core_enforcer import EnforceContext
    if len(request_values) != 0 and isinstance(request_values[0], EnforceContext):
        enforce_context = request_values[0]
        rtype = enforce_context.rtype
        ptype = enforce_context.ptype
        etype = enforce_context.etype
        mtype = enforce_context.mtype
        request_values = request_values[1:]

    # Keep the same validation points and exceptions as CoreEnforcer.enforce_ex.
    if "m" not in self.model.keys():
        raise RuntimeError("model is undefined")
    if "m" not in self.model["m"].keys():
        raise RuntimeError("model is undefined")

    r_tokens = self.model["r"][rtype].tokens
    p_tokens = self.model["p"][ptype].tokens

    if len(r_tokens) != len(request_values):
        raise RuntimeError("invalid request size")

    exp_string = self.model["m"][mtype].value
    exp_has_eval = util.has_eval(exp_string)
    if not exp_has_eval:
        expression = self._get_expression(exp_string, functions)

    policy_effects = set()
    r_parameters = dict(zip(r_tokens, request_values))
    matched = []
    decisive = ()

    effect_expr = self.model["e"][etype].value
    effector = get_effector(effect_expr) if effect_expr != self.model["e"]["e"].value else self.eft

    policy_list = self.model["p"][ptype].policy
    policy_len = len(policy_list)

    if policy_len != 0:
        for i, pvals in enumerate(policy_list):
            if len(p_tokens) != len(pvals):
                raise RuntimeError("invalid policy size")

            p_parameters = dict(zip(p_tokens, pvals))
            parameters = dict(r_parameters, **p_parameters)

            if exp_has_eval:
                rule_names = util.get_eval_value(exp_string)
                rules = [util.escape_assertion(p_parameters[rule_name]) for rule_name in rule_names]
                exp_with_rule = util.replace_eval(exp_string, rules)
                expression = self._get_expression(exp_with_rule, functions)

            result = expression.eval(parameters)

            if isinstance(result, bool):
                if not result:
                    policy_effects.add(Effector.INDETERMINATE)
                    continue
            elif isinstance(result, float):
                if result == 0:
                    policy_effects.add(Effector.INDETERMINATE)
                    continue
            else:
                raise RuntimeError("matcher result should be bool, int or float")

            eft_key = ptype + "_eft"
            if eft_key in parameters.keys():
                raw_effect = parameters[eft_key]
                if raw_effect == "allow":
                    effect = "allow"
                    policy_effects.add(Effector.ALLOW)
                elif raw_effect == "deny":
                    effect = "deny"
                    policy_effects.add(Effector.DENY)
                else:
                    effect = "indeterminate"
                    policy_effects.add(Effector.INDETERMINATE)
            else:
                effect = "allow"
                policy_effects.add(Effector.ALLOW)

            match = PolicyMatch(ptype, list(pvals), i, effect)
            matched.append(match)

            if effector.intermediate_effect(policy_effects) != Effector.INDETERMINATE:
                decisive = (match,)
                break
    else:
        if exp_has_eval:
            raise RuntimeError("please make sure rule exists in policy when using eval() in matcher")

        parameters = r_parameters.copy()
        for token in self.model["p"][ptype].tokens:
            parameters[token] = ""

        expression.eval(parameters)

    final_effect = effector.final_effect(policy_effects)
    allowed = effect_to_bool(final_effect)
    result = TraceResult(allowed, tuple(matched), tuple(decisive), False)
    return result


def would_change(self, *rvals, mutations):
    """Apply mutations in an isolated copy and compare the resulting decision."""
    before = self.enforce(*rvals)
    mutation_list = _normalize_mutations(mutations)

    if not mutation_list:
        result = ChangeImpact(False, before, before)
        return result

    sandbox = _clone_for_sandbox(self)
    for mutation in mutation_list:
        if mutation.sec == "p":
            if mutation.op == "add":
                sandbox.add_named_policy(mutation.ptype, mutation.rule)
            else:
                sandbox.remove_named_policy(mutation.ptype, mutation.rule)
        else:
            # Conditional role definitions do not occupy rm_map, and the
            # existing named grouping API assumes the opposite manager type.
            # Invoke the assertion-level behavior directly to preserve all
            # manager side effects without changing the upstream API.
            conditional = mutation.ptype in sandbox.cond_rm_map
            manager = sandbox.cond_rm_map[mutation.ptype] if conditional else sandbox.rm_map[mutation.ptype]
            exists = sandbox.model.has_policy("g", mutation.ptype, mutation.rule)

            if mutation.op == "add":
                if not exists:
                    sandbox.model.add_policy("g", mutation.ptype, mutation.rule)
                if conditional:
                    sandbox.model.build_incremental_conditional_role_links(
                        manager, PolicyOp.Policy_add, "g", mutation.ptype, [mutation.rule]
                    )
                elif exists:
                    pass
                else:
                    sandbox.model.build_incremental_role_links(
                        manager, PolicyOp.Policy_add, "g", mutation.ptype, [mutation.rule]
                    )
            elif exists:
                sandbox.model.remove_policy("g", mutation.ptype, mutation.rule)
                if conditional:
                    sandbox.model.build_incremental_conditional_role_links(
                        manager, PolicyOp.Policy_remove, "g", mutation.ptype, [mutation.rule]
                    )
                else:
                    sandbox.model.build_incremental_role_links(
                        manager, PolicyOp.Policy_remove, "g", mutation.ptype, [mutation.rule]
                    )

    after = sandbox.enforce(*rvals)
    result = ChangeImpact(before != after, before, after)
    return result
