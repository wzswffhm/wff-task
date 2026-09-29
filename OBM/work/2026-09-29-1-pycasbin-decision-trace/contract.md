# 公开契约定稿 — `enforce_traced` / `would_change`

> Task #1 交付物。本题：**pycasbin 决策可解释性 + 策略变更影响分析**。
> 基线 `casbin/pycasbin` @ `bf5a94be899c3eb14e9d9509904a3b38d9f2cf71`（2026-08-13，Apache-2.0）。
> domain = `deepSWE/feature_request`；语言 Python。

---

## 1. 动机（为什么这是真需求而非人造 API）

`Enforcer.enforce()` 只返回布尔。运维场景（"为什么 alice 能读 data1？""我把这条规则删掉会不会出事？"）
在 pycasbin 里**无法回答**：

- `enforce_ex()` 返回 `(bool, explain_rule)`，但 `explain_rule` 是**最后一条被匹配的规则**，
  不是"决定结果的规则"；且它不告诉你**哪些规则参与了求值**、有多少条被跳过。
- 没有"反事实"能力：想知道"删掉某条规则会不会翻转结论"，只能真的改策略再改回来
  （有并发风险 + 会触发 adapter 写 + 会重建角色链接），无法安全试算。

本需求补上这两块能力，且**不得改变** `enforce()` 的任何既有行为。

---

## 2. 新增公开 API

模块 `casbin/trace.py`，并从 `casbin` 顶层导出（经 `casbin/__init__.py`）：

```python
@dataclass(frozen=True)
class PolicyMatch:
    ptype: str          # 例如 "p" / "p2"
    rule: tuple[str, ...]
    index: int          # 该规则在其 ptype 策略列表中的下标（优先级排序之后）
    effect: str         # "allow" | "deny" | "indeterminate"

@dataclass(frozen=True)
class TraceResult:
    allowed: bool
    matched: tuple[PolicyMatch, ...]
    decisive: tuple[PolicyMatch, ...]   # 长度 0 或 1
    disabled: bool

@dataclass(frozen=True)
class PolicyMutation:
    op: str             # "add" | "remove"
    sec: str            # "p" | "g"
    ptype: str
    rule: tuple[str, ...]

class ChangeImpact(NamedTuple):
    changed: bool
    before: bool
    after: bool
```

挂在 `CoreEnforcer` 上的两个方法（因此 `Enforcer` / `SyncedEnforcer` 等自动获得）：

```python
def enforce_traced(self, *rvals) -> TraceResult: ...
def would_change(self, *rvals, mutations) -> ChangeImpact: ...
```

`*rvals` 与 `enforce()` 完全同构：可选的 `EnforceContext` 打头，其后是请求值。

---

## 3. `enforce_traced` 规范性语义

### 3.1 前置

- `allowed` **必须**恒等于同参数下 `enforce()` 的返回值。这是最重要的一致性约束。
- 求值算法与 `core_enforcer.enforce_ex` 的循环**逐步同构**：按 `model["p"][ptype].policy`
  的顺序（即 `load_policy` / `add_policy` 建立的**优先级排序后**顺序）逐条取规则；
  对每条规则用 `_get_expression` 得到的表达式求值；`eval()` 形式（`util.has_eval`）按上游方式
  逐规则替换。

### 3.2 `matched`（参与求值的规则）

按求值顺序记录**被求值且 matcher 为真**的规则（不匹配的规则只加 `INDETERMINATE` 且不算 matched）。
循环在 `self.eft.intermediate_effect(policy_effects) != Effector.INDETERMINATE`
时中断——**中断点那条规则已经计入 `matched`**，其后未求值的规则不计入。

由四种 effector 的 `intermediate_effect` 决定的实际中断条件（实证确认）：

| effector | 中断条件 |
|---|---|
| `some(where (p_eft == allow))`（allow-override） | 首个**匹配且 eft=allow** 的规则 |
| `!some(where (p_eft == deny))`（deny-override） | 首个**匹配且 eft=deny** 的规则 |
| `some(where (p_eft == allow)) && !some(where (p_eft == deny))` | 首个**匹配且 eft=deny** 的规则 |
| `priority(p_eft) \|\| deny` / `subjectPriority(p_eft) \|\| deny` | 首个**匹配且 eft 确定**的规则 |

注意"匹配且 eft=allow"≠"第一条匹配的规则"：allow-override 下若首条匹配规则是 deny，
循环会**继续**（`intermediate_effect` 返回 INDETERMINATE），该 deny 规则仍进 `matched`。

### 3.3 `effect` 字段

- 策略定义的 token 中存在 `<ptype>_eft` → 取该字段值：
  `"allow"` → `"allow"`；`"deny"` → `"deny"`；**其余任意值** → `"indeterminate"`
  （上游对 `parameters[p_eft_key]` 的 `else` 分支加 `INDETERMINATE`）。
- 策略定义**没有** `<ptype>_eft` token → 一律 `"allow"`（上游 `else: policy_effects.add(ALLOW)`）。
- `effect == "indeterminate"` 的匹配规则**不触发中断**，也不影响 `allowed`。

### 3.4 `decisive`（真正决定了结果的规则，长度 0 或 1）

定义为：**引擎因其效果而中断时，停下来的那条规则**；若引擎从未因效果中断，则为空元组。

| 情形 | `decisive` |
|---|---|
| `allowed=True` 且 effector=allow-override | 首个 `effective` allow 匹配 |
| `allowed=False` 且 effector=allow-override | `()` |
| `allowed=False` 且 effector=deny-override | 首个 deny 匹配 |
| `allowed=True` 且 effector=deny-override | `()`（"因不存在 deny 而放行"） |
| `allowed=False` 且 effector=allow-and-deny | 首个 deny 匹配 |
| `allowed=True` 且 effector=allow-and-deny | `()` |
| effector=priority / subjectPriority（**任何**结果） | 首个 `effective` 匹配 |

`effective` = `effect in ("allow", "deny")`。

### 3.5 退化情形

- **策略列表为空**：上游会以"所有 p token 绑定空串"求值一次 matcher。
  该效果**不归属任何规则** → `matched = ()`、`decisive = ()`，`allowed` 仍按上游效果语义给出
  （allow-override 下 matcher 为真 → `True`）。
- **matcher 引用了不存在的 ptype / 请求长度不符**：与 `enforce()` 抛同样的异常，不做包装。
- **`eval()` matcher + 空策略**：上游抛 `RuntimeError("please make sure rule exists in policy
  when using eval() in matcher")`，原样透传。
- **`enforce` 被禁用**（`enable_enforce(False)`）：`allowed == True`、
  `matched == ()`、`decisive == ()`、`disabled == True`。未禁用时 `disabled == False`。
- **`EnforceContext` 打头**：`ptype` 取 `ctx.ptype`，`matched` 中 `ptype` 字段即为该值；
  effector 仍取 `self.eft`（与 `enforce_ex` 一致，上游如此），不按 `etype` 重选。

### 3.6 非侵入性

`enforce_traced` **不得**修改 `self.model`、`self.rm_map`、`self.cond_rm_map`。
调用前后 `enforce()` 结果、`get_policy()`、`get_grouping_policy()`、`get_roles_for_user()`
必须完全不变。

---

## 4. `would_change` 规范性语义

`would_change(*rvals, mutations)`：
把 `mutations`（单个 `PolicyMutation` 或它们的序列，序列按给定顺序依次施加）
施加到 `self` 的**一次性沙箱副本**上，重新求值，回答"结论是否被翻转"。

返回 `ChangeImpact(changed, before, after)`：
`before = self.enforce(*rvals)`，`after` = 施加全部变更后的沙箱结果，`changed = before != after`。

### 4.1 每种 op 的语义（必须与既有 management API 的语义逐字一致）

| op | sec | 语义 |
|---|---|---|
| `add` | `p` | 等价 `add_policy(sec, ptype, rule)`：规则已存在 → 无操作；否则追加，并在该 ptype 存在优先级 token 时做与 `Policy.add_policy` 相同的优先级插入。 |
| `remove` | `p` | 等价 `remove_policy(sec, ptype, rule)`：规则不存在 → 无操作。 |
| `add` | `g` | 等价 `add_grouping_policy` 的**全部副作用**：写入策略 **且** 为 `rm_map[ptype]`（含 `cond_rm_map[ptype]`）增量建立角色链接。 |
| `remove` | `g` | 等价 `remove_grouping_policy` 的**全部副作用**：移除策略 **且** 删除角色链接。 |

- 规则比较按**元素逐一相等**（`list(rule)` 与策略中存储的 list 比较）。
- `mutations` 为空序列 → `after == before`，`changed == False`。
- 对 `g` 的变更必须真正影响后续 `g(...)` 的求值结果——即角色链接要真的重建/增量更新。
- **声明式**：`would_change` 只回答"会不会变"，不持久化、不通知 watcher、不调用 adapter。

### 4.2 沙箱隔离（关键陷阱）

`Assertion.__deepcopy__` 明确**按引用共享** `rm` / `cond_rm`（源码注释说明这是刻意为之）。
因此 `copy.deepcopy(self.model)` **不会**隔离角色管理器：若实现按此路子走，
对 `g` 的变更会污染真实 enforcer 的角色图。

要求：`would_change` 返回后，`self` 的以下状态必须与调用前**逐字相同**：

- `enforce(*rvals)`
- `get_policy()` / `get_grouping_policy()`（内容与顺序）
- `get_roles_for_user(u)` / `get_users_for_role(r)` / `has_role_for_user(u, r)`
- `get_roles_for_user_in_domain(u, d)`（域模型）
- 条件角色管理器上已注册的 link-condition 函数仍然生效

即：**条件角色管理器（`g = _, _, (_, _)` 之类的参数化模型）上注册的链接条件必须存活到沙箱里**，
沙箱里的 `g` 变更后仍按原条件判定。

---

## 5. 难度来源（题面难度锚点，勿写入 instruction）

1. 四种 effector 的中断语义互不相同，且"首条匹配"≠"触发中断的那条"。
2. `matched` 的边界是"被求值且匹配"，不是"到中断点为止"。
3. `decisive` 对 deny-override / allow-and-deny 的 **allowed=True 时为空**，但对 priority **永不为空**。
4. `effect` 的 indeterminate 分支（无 eft token / 非法 eft 值）都不触发中断。
5. **沙箱隔离陷阱**：`Assertion.__deepcopy__` 共享 rm，必须自己造独立角色图。
6. 条件角色管理器的 link-condition 闭包要存活（文本往返序列化会丢）。
7. 空策略路径（matcher 以空 p token 求值）不归属任何规则。
8. 一致性不变量 `allowed == enforce(...)` 覆盖全部矩阵。

---

## 6. 反例：为什么 `decisive` 不定义为"移除后翻转的最小集合"

曾考虑 `decisive = 使结论翻转的极小移除集`。该定义在 allow-and-deny 下**不是 `matched` 的子集**：

```
p, allow, data1, read, allow      # r0 匹配
p, deny,  data1, read, deny       # r1 匹配（引擎在此中断）
p, deny2, data1, read, deny       # r2 未被求值（不在 matched 中）
```

`matched = [r0, r1]`，`allowed=False`。只移除 r1 → 引擎继续走到 r2 → 仍是 deny，**不翻转**；
必须同时移除 `{r1, r2}` 才翻转，而 `r2 ∉ matched`。该定义还会引入极小割的歧义性与组合爆炸。
故采用 §3.4 的"引擎据其效果中断的那条规则"定义：唯一、O(1)、与引擎行为一一对应。
