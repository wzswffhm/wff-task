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
"""Decision tracing and change-impact analysis for pycasbin.

``enforce()`` answers *whether* a request is allowed.  It does not answer
*why*, and it offers no way to ask *what if the policy were different*.  This
module adds those two capabilities without touching the semantics of the
existing enforcement path:

* :func:`enforce_traced` replays the exact decision loop of
  :meth:`CoreEnforcer.enforce_ex` while recording which policy rules the engine
  actually observed, and which rule it stopped on.
* :func:`would_change` re-evaluates a request against a throw-away copy of the
  policy after applying a set of hypothetical mutations.
"""

import copy
from typing import NamedTuple, Optional, Sequence, Tuple

from casbin.effect import Effector, effect_to_bool
from casbin.model.policy_op import PolicyOp
from casbin.util import generate_g_function, generate_conditional_g_function
from casbin.util import util


class PolicyMatch(NamedTuple):
    """A policy rule that the decision loop evaluated to a match."""

    ptype: str
    rule: Tuple[str, ...]
    index: int
    effect: str  # "allow" | "deny" | "indeterminate"

    def __str__(self) -> str:  # pragma: no cover - convenience only
        return "{}[{}] {} eft={}".format(self.ptype, self.index, list(self.rule), self.effect)


class TraceResult(NamedTuple):
    """The outcome of a traced evaluation."""

    allowed: bool
    matched: Tuple[PolicyMatch, ...]
    decisive: Tuple[PolicyMatch, ...]
    disabled: bool


class PolicyMutation(NamedTuple):
    """A hypothetical, not-yet-applied change to the policy."""

    op: str  # "add" | "remove"
    sec: str  # "p" | "g"
    ptype: str
    rule: Tuple[str, ...]


class ChangeImpact(NamedTuple):
    """Answer of :func:`would_change`."""

    changed: bool
    before: bool
    after: bool


_INDETERMINATE = "indeterminate"


def _resolve_context(rvals):
    """Splits an optional leading EnforceContext off the request values.

    Imported lazily to keep this module free of a circular dependency on
    ``casbin.core_enforcer``.
    """
    from casbin.core_enforcer import EnforceContext

    rtype, ptype, mtype = "r", "p", "m"
    if len(rvals) != 0 and isinstance(rvals[0], EnforceContext):
        context = rvals[0]
        rtype = context.rtype
        ptype = context.ptype
        mtype = context.mtype
        rvals = rvals[1:]
    return rtype, ptype, mtype, rvals


def _build_functions(enforcer):
    """Mirrors the function map construction performed by enforce_ex()."""
    functions = enforcer.fm.get_functions()
    if "g" in enforcer.model.keys():
        for key, ast in enforcer.model["g"].items():
            if len(enforcer.rm_map) != 0:
                functions[key] = generate_g_function(ast.rm)
            if len(enforcer.cond_rm_map) != 0:
                functions[key] = generate_conditional_g_function(ast.cond_rm)
    return functions


def _rule_effect(eft_key, parameters):
    """Maps a policy rule to its effect label, following enforce_ex()."""
    if eft_key in parameters.keys():
        raw = parameters[eft_key]
        if raw == "allow":
            return "allow", Effector.ALLOW
        if raw == "deny":
            return "deny", Effector.DENY
        return _INDETERMINATE, Effector.INDETERMINATE
    return "allow", Effector.ALLOW


def enforce_traced(enforcer, *rvals):
    """Decides a request and reports how the decision was reached.

    The evaluation order, the early-exit rule and the final effect computation
    are step-for-step identical to :meth:`CoreEnforcer.enforce_ex`, so
    ``enforce_traced(*rvals).allowed`` always equals ``enforce(*rvals)``.
    """
    if not enforcer.enabled:
        return TraceResult(allowed=True, matched=(), decisive=(), disabled=True)

    rtype, ptype, mtype, rvals = _resolve_context(rvals)

    functions = _build_functions(enforcer)

    if "m" not in enforcer.model.keys() or "m" not in enforcer.model["m"].keys():
        raise RuntimeError("model is undefined")

    r_tokens = enforcer.model["r"][rtype].tokens
    p_tokens = enforcer.model["p"][ptype].tokens

    if len(r_tokens) != len(rvals):
        raise RuntimeError("invalid request size")

    exp_string = enforcer.model["m"][mtype].value
    exp_has_eval = util.has_eval(exp_string)
    if not exp_has_eval:
        expression = enforcer._get_expression(exp_string, functions)

    policy = enforcer.model["p"][ptype].policy
    policy_len = len(policy)

    policy_effects = set()
    r_parameters = dict(zip(r_tokens, rvals))

    matched = []
    decisive = ()
    eft_key = ptype + "_eft"

    if policy_len != 0:
        for i, pvals in enumerate(policy):
            if len(p_tokens) != len(pvals):
                raise RuntimeError("invalid policy size")

            p_parameters = dict(zip(p_tokens, pvals))
            parameters = dict(r_parameters, **p_parameters)

            if exp_has_eval:
                rule_names = util.get_eval_value(exp_string)
                rules = [util.escape_assertion(p_parameters[rule_name]) for rule_name in rule_names]
                expression = enforcer._get_expression(util.replace_eval(exp_string, rules), functions)

            result = expression.eval(parameters)

            if isinstance(result, bool):
                if not result:
                    policy_effects.add(Effector.INDETERMINATE)
                    continue
            elif isinstance(result, float):
                if 0 == result:
                    policy_effects.add(Effector.INDETERMINATE)
                    continue
            else:
                raise RuntimeError("matcher result should be bool, int or float")

            label, effect = _rule_effect(eft_key, parameters)
            policy_effects.add(effect)

            observation = PolicyMatch(ptype=ptype, rule=tuple(pvals), index=i, effect=label)
            matched.append(observation)

            if enforcer.eft.intermediate_effect(policy_effects) != Effector.INDETERMINATE:
                decisive = (observation,)
                break
    else:
        if exp_has_eval:
            raise RuntimeError("please make sure rule exists in policy when using eval() in matcher")

        parameters = dict(r_parameters)
        for token in p_tokens:
            parameters[token] = ""

        if expression.eval(parameters):
            policy_effects.add(Effector.ALLOW)
        else:
            policy_effects.add(Effector.INDETERMINATE)

    allowed = effect_to_bool(enforcer.eft.final_effect(policy_effects))
    return TraceResult(allowed=allowed, matched=tuple(matched), decisive=decisive, disabled=False)


def _clone(enforcer):
    """Builds an isolated throw-away copy of ``enforcer``.

    ``Assertion.__deepcopy__`` deliberately keeps ``rm`` / ``cond_rm`` by
    reference, so deep-copying the model alone would leave the sandbox sharing
    live role graphs with the original enforcer.  The role managers are copied
    separately and re-attached, which keeps registered link-condition functions
    alive in the sandbox while leaving the original untouched.
    """
    sandbox = copy.copy(enforcer)
    sandbox.model = copy.deepcopy(enforcer.model)
    sandbox.rm_map = copy.deepcopy(enforcer.rm_map)
    sandbox.cond_rm_map = copy.deepcopy(enforcer.cond_rm_map)

    if "g" in sandbox.model.keys():
        for key, ast in sandbox.model["g"].items():
            ast.rm = sandbox.rm_map.get(key)
            ast.cond_rm = sandbox.cond_rm_map.get(key)

    # A counterfactual must never reach the persistence layer or notify peers.
    sandbox.adapter = None
    sandbox.watcher = None
    sandbox.auto_save = False
    sandbox.auto_notify_watcher = False
    return sandbox


def _apply_mutation(enforcer, mutation):
    """Applies one mutation, mirroring the corresponding management API."""
    sec = mutation.sec
    ptype = mutation.ptype
    rule = list(mutation.rule)

    if mutation.op == "add":
        # add_named_grouping_policy() links the role even when the rule already
        # existed, so the same call pattern is reproduced here.
        enforcer.model.add_policy(sec, ptype, rule)
        if sec == "g" and enforcer.auto_build_role_links:
            rm = enforcer.rm_map.get(ptype)
            if rm is not None:
                enforcer.model.build_incremental_role_links(rm, PolicyOp.Policy_add, "g", ptype, [rule])
            cond_rm = enforcer.cond_rm_map.get(ptype)
            if cond_rm is not None:
                enforcer.model.build_incremental_conditional_role_links(
                    cond_rm, PolicyOp.Policy_add, "g", ptype, [rule]
                )
        return

    if mutation.op == "remove":
        if not enforcer.model.remove_policy(sec, ptype, rule):
            return
        if sec == "g" and enforcer.auto_build_role_links:
            rm = enforcer.rm_map.get(ptype)
            if rm is not None:
                enforcer.model.build_incremental_role_links(rm, PolicyOp.Policy_remove, "g", ptype, [rule])
        return

    raise ValueError("unsupported mutation op: {!r}".format(mutation.op))


def would_change(enforcer, *rvals, mutations):
    """Reports whether hypothetical policy changes flip a request's outcome.

    ``mutations`` is either a single :class:`PolicyMutation` or a sequence of
    them, applied in order to a sandbox copy of the policy.  The enforcer's own
    state is never modified.
    """
    if mutations is None:
        mutations = ()
    elif isinstance(mutations, PolicyMutation):
        mutations = (mutations,)
    else:
        mutations = tuple(mutations)

    before = enforcer.enforce(*rvals)

    if not mutations:
        return ChangeImpact(changed=False, before=before, after=before)

    sandbox = _clone(enforcer)
    for mutation in mutations:
        _apply_mutation(sandbox, mutation)

    after = sandbox.enforce(*rvals)
    return ChangeImpact(changed=before != after, before=before, after=after)
