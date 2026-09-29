"""契约探针：检查 document_diff 是否满足公开契约中【未被现有 F2P 覆盖】的行为。

用法：PYTHONPATH=<含 marshmallow/ 的目录> python3 probe_contract.py
对 Agent 实现与参考实现分别运行，用差异判断“题目太简单”是因为能力足够还是测试太窄。
"""
import copy
import json

from marshmallow import Schema, fields


def check(name, fn):
    try:
        return name, fn()
    except Exception as exc:  # noqa: BLE001
        return name, f"EXC {type(exc).__name__}: {exc}"


class Sub(Schema):
    x = fields.Int()
    y = fields.Int()


class SOrder(Schema):
    b = fields.Int()   # 声明顺序：b 先，a 后
    a = fields.Int()


class SNested(Schema):
    name = fields.Str()
    sub = fields.Nested(Sub)


class SList(Schema):
    tags = fields.List(fields.Int())


def r_paths(out):
    return [r["path"] for r in out]


def main():
    results = []

    # 1) 输出顺序应跟随 schema.fields 声明顺序（b,a），而不是输入字典顺序（a,b）
    results.append(check("01_declaration_order", lambda: r_paths(
        SOrder().document_diff({"a": 1, "b": 1}, {"a": 2, "b": 2})
    )))

    # 2) include_unknown=True 时未知键应纳入比较
    results.append(check("02_include_unknown_true", lambda: [
        (r["op"], r["path"])
        for r in SOrder().document_diff(
            {"a": 1, "b": 1, "z": 1}, {"a": 1, "b": 1, "z": 2}, include_unknown=True
        )
    ]))

    # 3) 内容相同但键插入顺序不同 → 必须空列表
    results.append(check("03_order_insensitive_empty", lambda: r_paths(
        SOrder().document_diff({"a": 1, "b": 2}, {"b": 2, "a": 1})
    )))

    # 4) ignore_fields 应在嵌套层同样生效
    results.append(check("04_ignore_fields_nested", lambda: [
        (r["op"], r["path"])
        for r in SNested().document_diff(
            {"name": "n", "sub": {"x": 1, "y": 1}},
            {"name": "n", "sub": {"x": 1, "y": 9}},
            ignore_fields=("y",),
        )
    ]))

    # 5) 纯函数：不改输入、不改 schema 状态
    def t_purity():
        s = SNested()
        left = {"name": "n", "sub": {"x": 1, "y": 1}}
        right = {"name": "n", "sub": {"x": 1, "y": 2}}
        l0, r0 = copy.deepcopy(left), copy.deepcopy(right)
        before = sorted(s.fields.keys())
        s.document_diff(left, right, include_unknown=True)
        return {
            "left_unchanged": left == l0,
            "right_unchanged": right == r0,
            "fields_unchanged": sorted(s.fields.keys()) == before,
        }

    results.append(check("05_purity", t_purity))

    # 6) List(标量) 按位置产生 add/remove，且 [i] 下标正确
    results.append(check("06_list_scalar_add_remove", lambda: [
        (r["op"], r["path"], r.get("right"))
        for r in SList().document_diff({"tags": [1, 2]}, {"tags": [1, 2, 3]})
    ]))

    print(json.dumps(dict(results), ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
