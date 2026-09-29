# Copyright 2024 The casbin Authors. All Rights Reserved.
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

import copy
import logging
import re

from collections import namedtuple

from casbin.effect import Effector, effect_to_bool
from casbin.model.policy_op import PolicyOp
from casbin.util import util


PolicyMatch = namedtuple("PolicyMatch", ["ptype", "rule", "index", "effect"])
TraceResult = namedtuple("TraceResult", ["allowed", "matched", "decisive", "disabled"])
PolicyMutation = namedtuple("PolicyMutation", ["op", "sec", "ptype", "rule"])
ChangeImpact = namedtuple("ChangeImpact", ["changed", "before", "after"])


_EFFECT_NAME = {
    Effector.ALLOW: "allow",
    Effector.DENY: "deny",
    Effector.INDETERMINATE: "indeterminate",
}


def _get_expression(expr, functions=None):
    # Keep this private evaluator construction identical to CoreEnforcer.enforce_ex.
    expr = expr.replace("&&", "and")
    expr = expr.replace("||", "or")
    expr = re.sub(r"!(?!=)", "not ", expr)

    from casbin.util import SimpleEval

    return SimpleEval(expr, functions)


def enforce_traced(enforcer, *rvals):
    """Return an enforcement decision together with its matched policy trace."""
    if not enforcer.enabled:
        return TraceResult(True, (), (), True)

    rtype = "r"
    ptype = "p"
    etype = "e"
    mtype = "m"

    functions = enforcer.fm.get_functions()

    if "g" in enforcer.model.keys():
        for key, ast in enforcer.model["g"].items():
            if len(enforcer.rm_map) != 0:
                from casbin.util import generate_g_function

                functions[key] = generate_g_function(ast.rm)
            if len(enforcer.cond_rm_map) != 0:
                from casbin.util import generate_conditional_g_function

                functions[key] = generate_conditional_g_function(ast.cond_rm)

    if len(rvals) != 0:
        from casbin.core_enforcer import EnforceContext

        if isinstance(rvals[0], EnforceContext):
            enforce_context = rvals[0]
            rtype = enforce_context.rtype
            ptype = enforce_context.ptype
            etype = enforce_context.etype
            mtype = enforce_context.mtype
            rvals = rvals[1:]

    if "m" not in enforcer.model.keys():
        raise RuntimeError("model is undefined")

    if "m" not in enforcer.model["m"].keys():
        raise RuntimeError("model is undefined")

    r_tokens = enforcer.model["r"][rtype].tokens
    p_tokens = enforcer.model["p"][ptype].tokens

    if len(r_tokens) != len(rvals):
        raise RuntimeError("invalid request size")

    exp_string = enforcer.model["m"][mtype].value
    exp_has_eval = util.has_eval(exp_string)
    if not exp_has_eval:
        expression = _get_expression(exp_string, functions)

    policy_effects = set()
    r_parameters = dict(zip(r_tokens, rvals))
    policy_len = len(enforcer.model["p"][ptype].policy)
    matched = []
    decisive = ()

    if policy_len != 0:
        for i, pvals in enumerate(enforcer.model["p"][ptype].policy):
            if len(p_tokens) != len(pvals):
                raise RuntimeError("invalid policy size")

            p_parameters = dict(zip(p_tokens, pvals))
            parameters = dict(r_parameters, **p_parameters)

            if exp_has_eval:
                rule_names = util.get_eval_value(exp_string)
                rules = [util.escape_assertion(p_parameters[rule_name]) for rule_name in rule_names]
                exp_with_rule = util.replace_eval(exp_string, rules)
                expression = _get_expression(exp_with_rule, functions)

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

            p_eft_key = ptype + "_eft"
            if p_eft_key in parameters.keys():
                eft_value = parameters[p_eft_key]
                if eft_value == "allow":
                    policy_effect = Effector.ALLOW
                elif eft_value == "deny":
                    policy_effect = Effector.DENY
                else:
                    policy_effect = Effector.INDETERMINATE
            else:
                policy_effect = Effector.ALLOW

            policy_effects.add(policy_effect)
            match = PolicyMatch(ptype, tuple(pvals), i, _EFFECT_NAME[policy_effect])
            matched.append(match)

            if enforcer.eft.intermediate_effect(policy_effects) != Effector.INDETERMINATE:
                decisive = (match,)
                break

    else:
        if exp_has_eval:
            raise RuntimeError("please make sure rule exists in policy when using eval() in matcher")

        parameters = r_parameters.copy()
        for token in enforcer.model["p"][ptype].tokens:
            parameters[token] = ""

        result = expression.eval(parameters)
        if result:
            policy_effects.add(Effector.ALLOW)
        else:
            policy_effects.add(Effector.INDETERMINATE)

    final_effect = enforcer.eft.final_effect(policy_effects)
    allowed = effect_to_bool(final_effect)
    return TraceResult(allowed, tuple(matched), decisive, False)


def _copy_role_manager(rm):
    """Deep-copy a role graph without invoking code outside of this repository."""
    return copy.deepcopy(rm)


def _sandbox_enforcer(enforcer):
    """Create an isolated one-shot enforcer with independent model and role graphs."""
    sandbox = object.__new__(enforcer.__class__)
    sandbox.__dict__.update(enforcer.__dict__)
    sandbox.logger = logging.getLogger(enforcer.logger.name)
    sandbox.fm = copy.copy(enforcer.fm)
    sandbox.model = copy.copy(enforcer.model)
    sandbox.model.model = copy.deepcopy(enforcer.model.model)
    sandbox.rm_map = {}
    sandbox.cond_rm_map = {}
    sandbox.adapter = None
    sandbox.watcher = None

    if "g" not in sandbox.model.keys():
        return sandbox

    for ptype, ast in sandbox.model["g"].items():
        if enforcer.rm_map.get(ptype) is not None:
            rm = _copy_role_manager(enforcer.rm_map[ptype])
            sandbox.rm_map[ptype] = rm
            ast.rm = rm

        if enforcer.cond_rm_map.get(ptype) is not None:
            cond_rm = _copy_role_manager(enforcer.cond_rm_map[ptype])
            sandbox.cond_rm_map[ptype] = cond_rm
            ast.cond_rm = cond_rm

    return sandbox


def _normalize_mutations(mutations):
    if isinstance(mutations, PolicyMutation):
        mutations = [mutations]
    else:
        mutations = list(mutations)

    for mutation in mutations:
        if mutation.op not in ("add", "remove"):
            raise ValueError("mutation op must be 'add' or 'remove'")
        if mutation.sec not in ("p", "g"):
            raise ValueError("mutation sec must be 'p' or 'g'")
    return mutations


def _apply_mutation(sandbox, mutation):
    op, sec, ptype, rule = mutation
    rule = list(rule)
    policy_op = PolicyOp.Policy_add if op == "add" else PolicyOp.Policy_remove

    if op == "add":
        added = sandbox.model.add_policy(sec, ptype, rule)
        if not added:
            return
    else:
        removed = sandbox.model.remove_policy(sec, ptype, rule)
        if not removed:
            return

    if sec == "g":
        if ptype in sandbox.rm_map:
            sandbox.model.build_incremental_role_links(
                sandbox.rm_map[ptype], policy_op, "g", ptype, [rule]
            )
        if ptype in sandbox.cond_rm_map:
            sandbox.model.build_incremental_conditional_role_links(
                sandbox.cond_rm_map[ptype], policy_op, "g", ptype, [rule]
            )


def would_change(enforcer, *rvals, mutations):
    """Apply mutations to an isolated copy and report whether the decision changes."""
    before = enforcer.enforce(*rvals)
    mutations = _normalize_mutations(mutations)

    sandbox = _sandbox_enforcer(enforcer)
    for mutation in mutations:
        _apply_mutation(sandbox, mutation)

    after = sandbox.enforce(*rvals)
    return ChangeImpact(before != after, before, after)
