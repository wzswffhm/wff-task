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

"""Decision tracing and hypothetical policy-change analysis for Casbin."""

import copy
import logging
import re

from casbin.effect import Effector, effect_to_bool
from casbin.model import FunctionMap
from casbin.util import util

ALLOW = "allow"
DENY = "deny"
INDETERMINATE = "indeterminate"


class TracedRule:
    """A policy rule that was evaluated and whose matcher evaluated to true."""

    __slots__ = ("ptype", "rule", "index", "effect")

    def __init__(self, ptype, rule, index, effect):
        self.ptype = ptype
        self.rule = tuple(rule)
        self.index = index
        self.effect = effect

    def __repr__(self):
        return f"TracedRule(ptype={self.ptype!r}, rule={self.rule!r}, index={self.index!r}, effect={self.effect!r})"

    def __eq__(self, other):
        if not isinstance(other, TracedRule):
            return NotImplemented
        return (
            self.ptype == other.ptype
            and self.rule == other.rule
            and self.index == other.index
            and self.effect == other.effect
        )

    def __hash__(self):
        return hash((self.ptype, self.rule, self.index, self.effect))


class EnforcementTrace:
    """The boolean decision together with its traced policy explanation."""

    __slots__ = ("allowed", "matched", "decisive", "disabled")

    def __init__(self, allowed, matched, decisive, disabled):
        object.__setattr__(self, "allowed", allowed)
        object.__setattr__(self, "matched", tuple(matched))
        object.__setattr__(self, "decisive", tuple(decisive))
        object.__setattr__(self, "disabled", disabled)

    def __repr__(self):
        return (
            "EnforcementTrace("
            f"allowed={self.allowed!r}, matched={self.matched!r}, "
            f"decisive={self.decisive!r}, disabled={self.disabled!r})"
        )

    def __setattr__(self, name, value):
        raise AttributeError(f"{type(self).__name__!s} objects are immutable")

    def __delattr__(self, name):
        raise AttributeError(f"{type(self).__name__!s} objects are immutable")

    def __eq__(self, other):
        if not isinstance(other, EnforcementTrace):
            return NotImplemented
        return (
            self.allowed == other.allowed
            and self.matched == other.matched
            and self.decisive == other.decisive
            and self.disabled == other.disabled
        )

    def __hash__(self):
        return hash((self.allowed, self.matched, self.decisive, self.disabled))


class Mutation:
    """A hypothetical add/remove operation for one policy or grouping rule."""

    __slots__ = ("operation", "section", "ptype", "rule")

    def __init__(self, operation, section, ptype, rule):
        operation = operation.lower()
        section = section.lower()
        if operation not in ("add", "remove"):
            raise ValueError("mutation operation must be 'add' or 'remove'")
        if section not in ("p", "g"):
            raise ValueError("mutation section must be 'p' or 'g'")
        object.__setattr__(self, "operation", operation)
        object.__setattr__(self, "section", section)
        object.__setattr__(self, "ptype", ptype)
        object.__setattr__(self, "rule", tuple(rule))

    def __repr__(self):
        return (
            "Mutation("
            f"operation={self.operation!r}, section={self.section!r}, "
            f"ptype={self.ptype!r}, rule={self.rule!r})"
        )

    def __setattr__(self, name, value):
        raise AttributeError(f"{type(self).__name__!s} objects are immutable")

    def __delattr__(self, name):
        raise AttributeError(f"{type(self).__name__!s} objects are immutable")

    def __eq__(self, other):
        if not isinstance(other, Mutation):
            return NotImplemented
        return (
            self.operation == other.operation
            and self.section == other.section
            and self.ptype == other.ptype
            and self.rule == other.rule
        )

    def __hash__(self):
        return hash((self.operation, self.section, self.ptype, self.rule))


class ChangeAnalysis:
    """Before/after decisions for a hypothetical mutation sequence."""

    __slots__ = ("before", "after", "changed")

    def __init__(self, before, after, changed):
        object.__setattr__(self, "before", before)
        object.__setattr__(self, "after", after)
        object.__setattr__(self, "changed", changed)

    def __repr__(self):
        return f"ChangeAnalysis(before={self.before!r}, after={self.after!r}, changed={self.changed!r})"

    def __setattr__(self, name, value):
        raise AttributeError(f"{type(self).__name__!s} objects are immutable")

    def __delattr__(self, name):
        raise AttributeError(f"{type(self).__name__!s} objects are immutable")

    def __iter__(self):
        yield self.before
        yield self.after
        yield self.changed

    def __len__(self):
        return 3

    def __getitem__(self, index):
        return (self.before, self.after, self.changed)[index]

    def __eq__(self, other):
        if isinstance(other, ChangeAnalysis):
            return self.before == other.before and self.after == other.after and self.changed == other.changed
        if isinstance(other, tuple):
            return (self.before, self.after, self.changed) == other
        return NotImplemented

    def __hash__(self):
        return hash((self.before, self.after, self.changed))


def _effect_name(parameters, ptype):
    p_eft_key = ptype + "_eft"
    if p_eft_key not in parameters:
        return ALLOW
    eft = parameters[p_eft_key]
    if eft == ALLOW:
        return ALLOW
    if eft == DENY:
        return DENY
    return INDETERMINATE


def _expression(enforcer, expr, functions):
    expr = expr.replace("&&", "and")
    expr = expr.replace("||", "or")
    expr = re.sub(r"!(?!=)", "not ", expr)
    return enforcer._get_expression(expr, functions)


def trace_enforcement(enforcer, *rvals):
    """Evaluate a request and return an :class:`EnforcementTrace`."""
    # Imported here to avoid a module-import cycle (core_enforcer imports this module).
    from casbin.core_enforcer import EnforceContext

    # SyncedEnforcer is a wrapper rather than a CoreEnforcer subclass, while still
    # exposing the same public API.  Trace through its guarded concrete enforcer, but
    # keep disabled handling on the wrapper itself.
    if not hasattr(enforcer, "enabled") and hasattr(enforcer, "_e"):
        if not enforcer._e.enabled:
            return EnforcementTrace(True, (), (), True)
        return trace_enforcement(enforcer._e, *rvals)

    if not enforcer.enabled:
        return EnforcementTrace(True, (), (), True)

    rtype = "r"
    ptype = "p"
    etype = "e"
    mtype = "m"

    functions = copy.copy(enforcer.fm.get_functions())
    if "g" in enforcer.model.keys():
        for key, ast in enforcer.model["g"].items():
            if len(enforcer.rm_map) != 0:
                from casbin.util import generate_g_function

                functions[key] = generate_g_function(ast.rm)
            if len(enforcer.cond_rm_map) != 0:
                from casbin.util import generate_conditional_g_function

                functions[key] = generate_conditional_g_function(ast.cond_rm)

    if rvals and isinstance(rvals[0], EnforceContext):
        context = rvals[0]
        rtype = context.rtype
        ptype = context.ptype
        etype = context.etype
        mtype = context.mtype
        rvals = rvals[1:]

    if "m" not in enforcer.model.keys() or mtype not in enforcer.model["m"].keys():
        raise RuntimeError("model is undefined")

    r_tokens = enforcer.model["r"][rtype].tokens
    p_tokens = enforcer.model["p"][ptype].tokens

    if len(r_tokens) != len(rvals):
        raise RuntimeError("invalid request size")

    exp_string = enforcer.model["m"][mtype].value
    exp_has_eval = util.has_eval(exp_string)
    if not exp_has_eval:
        expression = _expression(enforcer, exp_string, functions)

    policy_effects = set()
    matched = []
    decisive = ()
    r_parameters = dict(zip(r_tokens, rvals))
    policies = enforcer.model["p"][ptype].policy
    policy_len = len(policies)

    def add_effect(effect_name):
        if effect_name == ALLOW:
            policy_effects.add(Effector.ALLOW)
        elif effect_name == DENY:
            policy_effects.add(Effector.DENY)
        else:
            policy_effects.add(Effector.INDETERMINATE)

    if policy_len != 0:
        for i, pvals in enumerate(policies):
            if len(p_tokens) != len(pvals):
                raise RuntimeError("invalid policy size")

            p_parameters = dict(zip(p_tokens, pvals))
            parameters = dict(r_parameters, **p_parameters)

            if exp_has_eval:
                rule_names = util.get_eval_value(exp_string)
                rules = [util.escape_assertion(p_parameters[rule_name]) for rule_name in rule_names]
                exp_with_rule = util.replace_eval(exp_string, rules)
                expression = _expression(enforcer, exp_with_rule, functions)

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

            effect_name = _effect_name(parameters, ptype)
            record = TracedRule(ptype, pvals, i, effect_name)
            matched.append(record)
            add_effect(effect_name)

            if enforcer.eft.intermediate_effect(policy_effects) != Effector.INDETERMINATE:
                decisive = (record,)
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
    return EnforcementTrace(allowed, matched, decisive, False)


def normalize_mutations(mutations):
    """Accept one mutation or a sequence of them and return a tuple of mutations."""
    if mutations is None:
        return ()

    # A single Mutation is not treated as a character/field sequence.
    if isinstance(mutations, Mutation):
        return (mutations,)

    # A bare tuple can also describe one mutation when its fourth field is a rule
    # container; scalar four-tuples remain ambiguous with sequences, so are iterated.
    if isinstance(mutations, tuple) and len(mutations) == 4 and isinstance(mutations[3], (list, tuple)):
        return (Mutation(*mutations),)

    result = []
    for mutation in mutations:
        if isinstance(mutation, Mutation):
            result.append(mutation)
        else:
            result.append(Mutation(*mutation))
    return tuple(result)


def _clone_role_managers(enforcer):
    """Create independent role graphs while retaining callable conditions."""
    rm_map = {}
    cond_rm_map = {}

    def clone_non_domain(rm):
        clone = copy.copy(rm)
        clone.logger = logging.getLogger(rm.logger.name)
        clone.all_roles = {}
        for name, role in rm.all_roles.items():
            role_clone = copy.copy(role)
            role_clone.roles = set(role.roles)
            role_clone.users = set(role.users)
            # Condition functions and configured parameters are retained by reference.
            role_clone.link_condition_func_map = dict(role.link_condition_func_map)
            role_clone.link_condition_func_params_map = dict(role.link_condition_func_params_map)
            clone.all_roles[name] = role_clone
        clone.all_links = copy.deepcopy(rm.all_links)
        return clone

    def remap_role_graph(clone):
        """Map shallow role graph sets from original Role objects onto cloned objects."""
        # The role/user sets initially contain shallow copies of original Role objects.
        def get_role(name):
            if name not in clone.all_roles:
                missing = copy.copy(rm.all_roles[name])
                missing.roles = set(missing.roles)
                missing.users = set(missing.users)
                missing.link_condition_func_map = dict(missing.link_condition_func_map)
                missing.link_condition_func_params_map = dict(missing.link_condition_func_params_map)
                clone.all_roles[name] = missing
            return clone.all_roles[name]

        for role_clone in list(clone.all_roles.values()):
            role_clone.roles = {get_role(r.name) for r in role_clone.roles}
            role_clone.users = {get_role(u.name) for u in role_clone.users}

    for ptype, rm in enforcer.rm_map.items():
        if hasattr(rm, "all_links") and isinstance(getattr(rm, "all_links", None), dict):
            # DomainManager stores links by domain but does not have a materialized
            # all_roles graph of its own.
            clone = copy.copy(rm)
            clone.logger = logging.getLogger(rm.logger.name)
            clone.all_links = {domain: copy.deepcopy(links) for domain, links in rm.all_links.items()}
            clone.rm_map = {}
            # Existing caches may include domains without directly stored links when
            # domain matching is enabled.  Cloning those caches preserves that behavior.
            for domain in set(clone.all_links) | set(rm.rm_map):
                domain_rm = rm.rm_map.get(domain)
                if domain_rm is not None:
                    domain_clone = clone_non_domain(domain_rm)
                    remap_role_graph(domain_clone)
                    clone.rm_map[domain] = domain_clone
        else:
            clone = clone_non_domain(rm)
            remap_role_graph(clone)
        rm_map[ptype] = clone

    for ptype, rm in enforcer.cond_rm_map.items():
        if hasattr(rm, "all_links") and isinstance(getattr(rm, "all_links", None), dict):
            clone = copy.copy(rm)
            clone.logger = logging.getLogger(rm.logger.name)
            clone.all_links = {domain: copy.deepcopy(links) for domain, links in rm.all_links.items()}
            clone.rm_map = {}
            # Existing caches may include domains without directly stored links when
            # domain matching is enabled.  Cloning those caches preserves that behavior.
            for domain in set(clone.all_links) | set(rm.rm_map):
                domain_rm = rm.rm_map.get(domain)
                if domain_rm is not None:
                    domain_clone = clone_non_domain(domain_rm)
                    remap_role_graph(domain_clone)
                    clone.rm_map[domain] = domain_clone
        else:
            clone = clone_non_domain(rm)
            remap_role_graph(clone)
        cond_rm_map[ptype] = clone

    return rm_map, cond_rm_map


def _sandbox_enforcer(enforcer):
    """Build an in-memory sandbox whose model and role graphs are independent."""
    sandbox = object.__new__(type(enforcer))
    sandbox.__dict__.update(enforcer.__dict__)
    sandbox.logger = logging.getLogger(enforcer.logger.name)

    # Deep-copy model data.  Assertion deliberately shares RMs, so replace those below.
    sandbox.model = copy.deepcopy(enforcer.model)

    # A fresh function map avoids sharing mutable custom-function registries.
    sandbox.fm = FunctionMap.load_function_map()
    for name, fn in enforcer.fm.get_functions().items():
        sandbox.fm.add_function(name, fn)

    sandbox.rm_map, sandbox.cond_rm_map = _clone_role_managers(enforcer)

    # Point every assertion at the cloned graph appropriate to it.
    if "g" in sandbox.model.keys():
        for ptype, ast in sandbox.model["g"].items():
            ast.rm = sandbox.rm_map.get(ptype)
            ast.cond_rm = sandbox.cond_rm_map.get(ptype)

    sandbox.adapter = None
    sandbox.watcher = None
    sandbox.auto_save = False
    sandbox.auto_notify_watcher = False
    return sandbox


def _apply_mutation(sandbox, mutation):
    if mutation.section == "p":
        rule = list(mutation.rule)
        if mutation.operation == "add":
            sandbox.add_named_policy(mutation.ptype, rule)
        else:
            sandbox.remove_named_policy(mutation.ptype, rule)
    else:
        rule = list(mutation.rule)
        if mutation.operation == "add":
            sandbox.add_named_grouping_policy(mutation.ptype, rule)
        else:
            sandbox.remove_named_grouping_policy(mutation.ptype, rule)


def analyze_would_change(enforcer, *rvals, mutations):
    """Apply hypothetical mutations in a sandbox and compare the request decision."""
    before = enforcer.enforce(*rvals)
    mutation_sequence = normalize_mutations(mutations)

    target = enforcer
    if not hasattr(enforcer, "enabled") and hasattr(enforcer, "_e"):
        target = enforcer._e

    sandbox = _sandbox_enforcer(target)
    for mutation in mutation_sequence:
        _apply_mutation(sandbox, mutation)

    after = sandbox.enforce(*rvals)
    return ChangeAnalysis(before, after, before != after)
