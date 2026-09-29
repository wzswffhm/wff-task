"""契约探针（加强版）：寻找 Agent 实现与参考实现的分歧点。

分歧点 = 契约未被明确覆盖 / 实现自由度大的地方 → 可作为最小硬化靶点。
用法：PYTHONPATH=<含 marshmallow/ 的目录> python3 probe_contract_hard.py
"""
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


class SubSub(Schema):
    c = fields.Int()


class Mid(Schema):
    inner = fields.Nested(SubSub)


class SMany(Schema):
    members = fields.Nested(Sub, many=True)


class SNestList(Schema):
    items = fields.List(fields.Nested(Sub))


class SThree(Schema):
    a = fields.Nested(Mid)


class SMixed(Schema):
    b = fields.Int()
    n = fields.Nested(Sub)
    t = fields.List(fields.Int())


class SScalar(Schema):
    x = fields.Int()


def norm(out):
    return [(r["op"], r["path"], r.get("left"), r.get("right")) for r in out]


def main():
    r = []

    # 1) Nested(many=True) 元素变少 → remove，且下标正确
    r.append(check("H1_many_element_removed", lambda: norm(
        SMany().document_diff({"members": [{"x": 1, "y": 1}, {"x": 2, "y": 2}]},
                              {"members": [{"x": 1, "y": 1}]})
    )))

    # 2) 三层嵌套 → 路径 a.inner.c
    r.append(check("H2_three_level_path", lambda: norm(
        SThree().document_diff({"a": {"inner": {"c": 1}}}, {"a": {"inner": {"c": 2}}})
    )))

    # 3) List(Nested) 元素新增
    r.append(check("H3_list_of_nested_add", lambda: norm(
        SNestList().document_diff({"items": [{"x": 1, "y": 1}]},
                                  {"items": [{"x": 1, "y": 1}, {"x": 5, "y": 6}]})
    )))

    # 4) 混合 schema：输出顺序应等于声明顺序 b, n, t
    r.append(check("H4_mixed_declaration_order", lambda: [p for _, p, _, _ in norm(
        SMixed().document_diff(
            {"t": [1], "n": {"x": 1, "y": 1}, "b": 1},
            {"t": [2], "n": {"x": 1, "y": 9}, "b": 2})
    )]))

    # 5) 顶层字段只在一侧 → remove（right 为 None）
    r.append(check("H5_top_level_remove", lambda: norm(
        SScalar().document_diff({"x": 1}, {})
    )))

    # 6) ignore_fields 在 many 元素内部是否也生效
    r.append(check("H6_ignore_inside_many", lambda: norm(
        SMany().document_diff({"members": [{"x": 1, "y": 1}]},
                              {"members": [{"x": 1, "y": 9}]},
                              ignore_fields=("y",))
    )))

    # 7) 值从 1 变成 None：是 change 还是 remove？（契约歧义点）
    r.append(check("H7_change_to_none", lambda: norm(
        SScalar().document_diff({"x": 1}, {"x": None})
    )))

    # 8) 字段值本来就是 None → 无变化时应为空
    r.append(check("H8_both_none_empty", lambda: norm(
        SScalar().document_diff({"x": None}, {"x": None})
    )))

    print(json.dumps(dict(r), ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
