"""Behavioral tests for ``Schema.document_diff``.

These are the feature (F2P) tests: they must FAIL on the unmodified upstream
baseline (``document_diff`` does not exist -> AttributeError) and PASS once the
feature is implemented. They are intentionally self-contained (their own
schemas) so they do not depend on the upstream ``tests.base`` fixtures.
"""
import pytest
from marshmallow import Schema, fields


class AddressSchema(Schema):
    street = fields.Str()
    city = fields.Str()


class PersonSchema(Schema):
    name = fields.Str()
    age = fields.Int()
    address = fields.Nested(AddressSchema())
    tags = fields.List(fields.Str())


def _paths(changes):
    return [c["path"] for c in changes]


def test_scalar_change_records_field_path():
    s = PersonSchema()
    left = {"name": "A", "age": 1, "address": {"street": "s1", "city": "c1"}, "tags": ["a", "b"]}
    right = {"name": "B", "age": 1, "address": {"street": "s2", "city": "c1"}, "tags": ["a", "b"]}
    changes = s.document_diff(left, right)
    assert changes == [
        {"op": "change", "path": "name", "left": "A", "right": "B"},
        {"op": "change", "path": "address.street", "left": "s1", "right": "s2"},
    ]


def test_add_remove_top_level_field():
    s = PersonSchema()
    assert s.document_diff({"name": "A"}, {"name": "A", "age": 5}) == [
        {"op": "add", "path": "age", "left": None, "right": 5},
    ]
    assert s.document_diff({"name": "A", "age": 5}, {"name": "A"}) == [
        {"op": "remove", "path": "age", "left": 5, "right": None},
    ]


def test_identical_documents_produce_empty_list():
    s = PersonSchema()
    doc = {"name": "A", "age": 1, "address": {"street": "s", "city": "c"}, "tags": ["a", "b"]}
    assert s.document_diff(doc, doc) == []


def test_nested_change_recurses_with_dotted_path():
    s = PersonSchema()
    left = {"name": "A", "age": 1, "address": {"street": "s1", "city": "c1"}, "tags": []}
    right = {"name": "A", "age": 1, "address": {"street": "s2", "city": "c1"}, "tags": []}
    changes = s.document_diff(left, right)
    assert _paths(changes) == ["address.street"]


def test_list_element_change_uses_index_path():
    s = PersonSchema()
    left = {"name": "A", "age": 1, "address": {"street": "s", "city": "c"}, "tags": ["a", "b"]}
    right = {"name": "A", "age": 1, "address": {"street": "s", "city": "c"}, "tags": ["a", "c"]}
    changes = s.document_diff(left, right)
    assert changes == [
        {"op": "change", "path": "tags[1]", "left": "b", "right": "c"},
    ]


def test_list_element_add_and_remove():
    s = PersonSchema()
    long_ = {"name": "A", "age": 1, "address": {"street": "s", "city": "c"}, "tags": ["a", "b", "c"]}
    short = {"name": "A", "age": 1, "address": {"street": "s", "city": "c"}, "tags": ["a"]}
    add = s.document_diff(short, long_)
    assert any(c["path"] == "tags[1]" and c["op"] == "add" for c in add)
    assert any(c["path"] == "tags[2]" and c["op"] == "add" for c in add)
    remove = s.document_diff(long_, short)
    assert any(c["path"] == "tags[1]" and c["op"] == "remove" for c in remove)
    assert any(c["path"] == "tags[2]" and c["op"] == "remove" for c in remove)


def test_unknown_field_policy_default_excludes():
    s = PersonSchema()
    left = {"name": "A", "extra": 1}
    right = {"name": "A", "extra": 2}
    assert s.document_diff(left, right) == []
    with_unknown = s.document_diff(left, right, include_unknown=True)
    assert with_unknown == [
        {"op": "change", "path": "extra", "left": 1, "right": 2},
    ]


def test_ignore_fields_skips_named_fields():
    s = PersonSchema()
    left = {"name": "A", "age": 1, "address": {"street": "s1", "city": "c"}, "tags": ["a", "b"]}
    right = {"name": "B", "age": 9, "address": {"street": "s2", "city": "c"}, "tags": ["a", "c"]}
    changes = s.document_diff(left, right, ignore_fields=("name", "age"))
    assert _paths(changes) == ["address.street", "tags[1]"]


def test_list_of_nested_compares_element_fields():
    class TeamSchema(Schema):
        members = fields.List(fields.Nested(PersonSchema()))

    s = TeamSchema()
    left = {"members": [{"name": "A", "age": 1, "address": {"street": "s", "city": "c"}, "tags": []}]}
    right = {"members": [{"name": "A", "age": 2, "address": {"street": "s", "city": "c"}, "tags": []}]}
    changes = s.document_diff(left, right)
    assert changes == [
        {"op": "change", "path": "members[0].age", "left": 1, "right": 2},
    ]


def test_nested_many_add_new_element():
    class RootSchema(Schema):
        people = fields.Nested(PersonSchema(), many=True)

    s = RootSchema()
    left = {"people": [{"name": "A", "age": 1, "address": {"street": "s", "city": "c"}, "tags": []}]}
    right = {
        "people": [
            {"name": "A", "age": 1, "address": {"street": "s", "city": "c"}, "tags": []},
            {"name": "B", "age": 3, "address": {"street": "t", "city": "d"}, "tags": []},
        ]
    }
    changes = s.document_diff(left, right)
    assert any(c["path"] == "people[1]" and c["op"] == "add" for c in changes)


def test_diff_accepts_objects_via_dump():
    s = PersonSchema()
    left_obj = {"name": "A", "age": 1, "address": {"street": "s1", "city": "c1"}, "tags": ["a"]}
    right_obj = {"name": "A", "age": 1, "address": {"street": "s2", "city": "c1"}, "tags": ["a"]}
    changes = s.document_diff(left_obj, right_obj)
    assert changes == [{"op": "change", "path": "address.street", "left": "s1", "right": "s2"}]
