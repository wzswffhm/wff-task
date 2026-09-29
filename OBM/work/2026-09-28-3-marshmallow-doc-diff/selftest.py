import sys, os
sys.path.insert(0, os.path.join(os.getcwd(), 'baseline', 'src'))
from marshmallow import Schema, fields


class AddressSchema(Schema):
    street = fields.Str()
    city = fields.Str()


class PersonSchema(Schema):
    name = fields.Str()
    age = fields.Int()
    address = fields.Nested(AddressSchema())
    tags = fields.List(fields.Str())


def main():
    s = PersonSchema()
    left = {"name": "A", "age": 1, "address": {"street": "s1", "city": "c1"}, "tags": ["a", "b"]}
    right = {"name": "B", "age": 1, "address": {"street": "s2", "city": "c1"}, "tags": ["a", "c"]}
    ch = s.document_diff(left, right)
    print("DIFF1:", ch)
    assert [c["path"] for c in ch] == ["name", "address.street", "tags[1]"], ch
    assert ch[0] == {"op": "change", "path": "name", "left": "A", "right": "B"}
    assert ch[1] == {"op": "change", "path": "address.street", "left": "s1", "right": "s2"}
    assert ch[2] == {"op": "change", "path": "tags[1]", "left": "b", "right": "c"}

    # add / remove top-level
    l2 = {"name": "A"}
    r2 = {"name": "A", "age": 5}
    ch2 = s.document_diff(l2, r2)
    print("DIFF2:", ch2)
    assert ch2 == [{"op": "add", "path": "age", "left": None, "right": 5}], ch2

    # identical -> empty
    assert s.document_diff(left, left) == [], "identical should be empty"

    # unknown fields
    l3 = {"name": "A", "extra": 1}
    r3 = {"name": "A", "extra": 2}
    assert s.document_diff(l3, r3) == []  # exclude unknown by default
    ch3 = s.document_diff(l3, r3, include_unknown=True)
    print("DIFF3:", ch3)
    assert ch3 == [{"op": "change", "path": "extra", "left": 1, "right": 2}], ch3

    # ignore_fields
    ch4 = s.document_diff(left, right, ignore_fields=("name",))
    assert [c["path"] for c in ch4] == ["address.street", "tags[1]"], ch4

    # nested add/remove element
    l5 = {"name": "A", "age": 1, "address": {"street": "s", "city": "c"}, "tags": ["a", "b", "c"]}
    r5 = {"name": "A", "age": 1, "address": {"street": "s", "city": "c"}, "tags": ["a"]}
    ch5 = s.document_diff(l5, r5)
    print("DIFF5:", ch5)
    assert any(c["path"] == "tags[1]" and c["op"] == "remove" for c in ch5)
    assert any(c["path"] == "tags[2]" and c["op"] == "remove" for c in ch5)

    # List(Nested) many
    class TeamSchema(Schema):
        members = fields.List(fields.Nested(PersonSchema()))
    ts = TeamSchema()
    l6 = {"members": [{"name": "A", "age": 1, "address": {"street": "s", "city": "c"}, "tags": []}]}
    r6 = {"members": [{"name": "A", "age": 2, "address": {"street": "s", "city": "c"}, "tags": []}]}
    ch6 = ts.document_diff(l6, r6)
    print("DIFF6:", ch6)
    assert ch6 == [{"op": "change", "path": "members[0].age", "left": 1, "right": 2}], ch6

    # Nested(many=True)
    class RootSchema(Schema):
        people = fields.Nested(PersonSchema(), many=True)
    rs = RootSchema()
    l7 = {"people": [{"name": "A", "age": 1, "address": {"street": "s", "city": "c"}, "tags": []}]}
    r7 = {"people": [{"name": "A", "age": 1, "address": {"street": "s", "city": "c"}, "tags": []},
                     {"name": "B", "age": 3, "address": {"street": "t", "city": "d"}, "tags": []}]}
    ch7 = rs.document_diff(l7, r7)
    print("DIFF7:", ch7)
    assert any(c["path"] == "people[1]" and c["op"] == "add" for c in ch7)

    print("SELFTEST DONE OK")


if __name__ == "__main__":
    main()
