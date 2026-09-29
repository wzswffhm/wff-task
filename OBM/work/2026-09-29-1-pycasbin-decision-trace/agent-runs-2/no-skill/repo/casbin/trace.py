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

"""Public helpers for decision tracing and hypothetical policy changes."""

import copy
from collections import namedtuple

from casbin.core_enforcer import EnforceContext
from casbin.effect import Effector, get_effector


TraceRecord = namedtuple("TraceRecord", ["ptype", "rule", "index", "effect"])
TraceResult = namedtuple("TraceResult", ["allowed", "matched", "decisive", "disabled"])
PolicyChange = namedtuple("PolicyChange", ["operation", "section", "ptype", "rule"])

_ADD = "add"
_REMOVE = "remove"
_ALLOW = "allow"
_DENY = "deny"
_INDETERMINATE = "indeterminate"
_VALID_SECTIONS = frozenset(("p", "g"))
_VALID_OPERATIONS = frozenset((_ADD, _REMOVE))


def _effect_name(effect):
    if effect == Effector.ALLOW:
        return _ALLOW
    if effect == Effector.DENY:
        return _DENY
    return _INDETERMINATE


def _trace_enforce(enforcer, *rvals):
    if not enforcer.enabled:
        return TraceResult(True, tuple(), tuple(), True)

    request_values = rvals
    ptype = "p"
    etype = "e"
    mtype = "m"
    rtype = "r"

    if request_values and isinstance(request_values[0], EnforceContext):
        enforce_context = request_values[0]
        rtype = enforce_context.rtype
        ptype = enforce_context.ptype
        etype = enforce_context.etype
        mtype = enforce_context.mtype
        request_values = request_values[1:]

    # Let the normal implementation perform all validation and construct the
    # ordinary set of matcher functions, including RBAC/conditional RBAC helpers.
    if "m" not in enforcer.model.keys():
        raise RuntimeError("model is undefined")
    if "m" not in enforcer.model["m"].keys():
        raise RuntimeError("model is undefined")

    r_tokens = enforcer.model["r"][rtype].tokens
    p_tokens = enforcer.model["p"][ptype].tokens
    if len(r_tokens) != len(request_values):
        raise RuntimeError("invalid request size")

    effect_expression = enforcer.model["e"][etype].value
    effector = get_effector(effect_expression)
    functions = enforcer.fm.get_functions()
    if "g" in enforcer.model.keys():
        for key, ast in enforcer.model["g"].items():
            if len(enforcer.rm_map) != 0 and ast.rm is not None:
                from casbin.util import generate_g_function
                functions[key] = generate_g_function(ast.rm)
            if len(enforcer.cond_rm_map) != 0 and ast.cond_rm is not None:
                from casbin.util import generate_conditional_g_function
                functions[key] = generate_conditional_g_function(ast.cond_rm)

    from casbin.util import util

    exp_string = enforcer.model["m"][mtype].value
    exp_has_eval = util.has_eval(exp_string)
    if not exp_has_eval:
        expression = enforcer._get_expression(exp_string, functions)

    policy_effects = set()
    request_parameters = dict(zip(r_tokens, request_values))
    policies = enforcer.model["p"][ptype].policy
    matched = []
    decisive = tuple()

    if policies:
        for index, pvals in enumerate(policies):
            if len(p_tokens) != len(pvals):
                raise RuntimeError("invalid policy size")

            p_parameters = dict(zip(p_tokens, pvals))
            parameters = dict(request_parameters, **p_parameters)

            if exp_has_eval:
                rule_names = util.get_eval_value(exp_string)
                rules = [util.escape_assertion(p_parameters[rule_name]) for rule_name in rule_names]
                exp_with_rule = util.replace_eval(exp_string, rules)
                expression = enforcer._get_expression(exp_with_rule, functions)

            result = expression.eval(parameters)
            if isinstance(result, bool):
                matcher_matched = result
            elif isinstance(result, float):
                matcher_matched = result != 0
            else:
                raise RuntimeError("matcher result should be bool, int or float")

            if not matcher_matched:
                policy_effects.add(Effector.INDETERMINATE)
                continue

            effect_key = ptype + "_eft"
            if effect_key in parameters:
                effect_value = parameters[effect_key]
                if effect_value == _ALLOW:
                    rule_effect = Effector.ALLOW
                elif effect_value == _DENY:
                    rule_effect = Effector.DENY
                else:
                    rule_effect = Effector.INDETERMINATE
            else:
                rule_effect = Effector.ALLOW

            policy_effects.add(rule_effect)
            record = TraceRecord(ptype, pvals[:], index, _effect_name(rule_effect))
            matched.append(record)

            if effector.intermediate_effect(policy_effects) != Effector.INDETERMINATE:
                decisive = (record,)
                break
    else:
        if exp_has_eval:
            raise RuntimeError("please make sure rule exists in policy when using eval() in matcher")

        parameters = request_parameters.copy()
        for token in enforcer.model["p"][ptype].tokens:
            parameters[token] = ""
        result = expression.eval(parameters)
        if result:
            policy_effects.add(Effector.ALLOW)
        else:
            policy_effects.add(Effector.INDETERMINATE)

    allowed = effector.final_effect(policy_effects) == Effector.ALLOW
    return TraceResult(allowed, tuple(matched), decisive, False)


def _normalize_mutations(mutations):
    if mutations is None:
        return []

    # A single mutation is operation, section, ptype, rule.
    if (
        len(mutations) == 4
        and isinstance(mutations[0], str)
        and isinstance(mutations[1], str)
        and isinstance(mutations[2], str)
    and not isinstance(mutations[3], str)
    ):
        mutations = [mutations]

    normalized = []
    for mutation in mutations:
        operation, section, ptype, rule = mutation
        if operation not in _VALID_OPERATIONS or section not in _VALID_SECTIONS:
            raise ValueError("invalid policy mutation")
        normalized.append(PolicyChange(operation, section, ptype, list(rule)))
    return normalized


def _clone_role_graph_roles(rm):
    old_roles = rm.all_roles
    new_roles = {name: type(role)(name) for name, role in old_roles.items()}
    for name, old_role in old_roles.items():
        new_role = new_roles[name]
        new_role.link_condition_func_map = copy.deepcopy(old_role.link_condition_func_map)
        new_role.link_condition_func_params_map = copy.deepcopy(old_role.link_condition_func_params_map)
        for child in old_role.roles:
            new_role.roles.add(new_roles[child.name])
        for user in old_role.users:
            new_role.users.add(new_roles[user.name])
    return new_roles


def _clone_default_role_manager(rm):
    """Clone the in-repository role managers and their registered predicates."""
    role_manager_class = _RoleManagerClass()
    conditional_role_manager_class = _ConditionalRoleManagerClass()
    domain_manager_class = _DomainManagerClass()
    conditional_domain_manager_class = _ConditionalDomainManagerClass()

    cls = rm.__class__
    clone = cls.__new__(cls)
    clone.__dict__.update(copy.deepcopy(rm.__dict__))

    if isinstance(rm, conditional_domain_manager_class):
        clone.rm_map = {key: _clone_default_role_manager(value) for key, value in rm.rm_map.items()}
    elif isinstance(rm, domain_manager_class):
        clone.rm_map = {key: _clone_default_role_manager(value) for key, value in rm.rm_map.items()}
    elif isinstance(rm, conditional_role_manager_class):
        clone.all_roles = _clone_role_graph_roles(rm)
    elif isinstance(rm, role_manager_class):
        clone.all_roles = _clone_role_graph_roles(rm)
    else:
        # Preserve custom role managers as best as possible without a third-party API.
        return copy.deepcopy(rm)
    return clone


def _RoleManagerClass():
    from casbin.rbac.default_role_manager.role_manager import RoleManager
    return RoleManager


def _ConditionalRoleManagerClass():
    from casbin.rbac.default_role_manager.role_manager import ConditionalRoleManager
    return ConditionalRoleManager


def _DomainManagerClass():
    from casbin.rbac.default_role_manager.role_manager import DomainManager
    return DomainManager


def _ConditionalDomainManagerClass():
    from casbin.rbac.default_role_manager.role_manager import ConditionalDomainManager
    return ConditionalDomainManager


def _restore_conditional_functions(source, target):
    for role in source.all_roles.values():
        for (role_name, domain), fn in role.link_condition_func_map.items():
            target.add_domain_link_condition_func(role.name, role_name, domain, fn)


def _sandbox_copy(enforcer):
    clone = enforcer.__class__.__new__(enforcer.__class__)
    clone.__dict__.update(copy.deepcopy(enforcer.__dict__))

    # The copied Assertion instances intentionally share role managers. Replace
    # them with isolated copies and reconnect assertions and maps.
    clone.rm_map = {}
    clone.cond_rm_map = {}
    if "g" in clone.model.keys():
        for ptype, ast in clone.model["g"].items():
            original_ast = enforcer.model["g"][ptype]
            if original_ast.rm is not None:
                rm_clone = _clone_default_role_manager(original_ast.rm)
                ast.rm = rm_clone
                clone.rm_map[ptype] = rm_clone
            if original_ast.cond_rm is not None:
                cond_clone = _clone_default_role_manager(original_ast.cond_rm)
                ast.cond_rm = cond_clone
                clone.cond_rm_map[ptype] = cond_clone

    clone.adapter = None
    clone.watcher = None
    clone.auto_save = False
    clone.auto_notify_watcher = False
    clone.auto_build_role_links = True
    if hasattr(clone, "enable_cache"):
        clone.enable_cache(False)
    return clone


def _apply_mutation(sandbox, mutation):
    if mutation.section == "p":
        if mutation.operation == _ADD:
            sandbox.add_named_policy(mutation.ptype, mutation.rule[:])
        else:
            sandbox.remove_named_policy(mutation.ptype, mutation.rule[:])
    else:
        if mutation.operation == _ADD:
            sandbox.add_named_grouping_policy(mutation.ptype, mutation.rule[:])
        else:
            sandbox.remove_named_grouping_policy(mutation.ptype, mutation.rule[:])


def would_change(enforcer, *rvals, mutations):
    before = enforcer.enforce(*rvals)
    changes = _normalize_mutations(mutations)
    sandbox = _sandbox_copy(enforcer)
    try:
        for change in changes:
            _apply_mutation(sandbox, change)
        after = sandbox.enforce(*rvals)
    finally:
        # Ensure no accidentally shared resources retain references; the sandbox
        # itself is local and becomes unreachable.
        del sandbox
    return before, after, before != after


def enforce_traced(enforcer, *rvals):
    """module-level convenience wrapper for CoreEnforcer.enforce_traced."""
    return _trace_enforce(enforcer, *rvals)
