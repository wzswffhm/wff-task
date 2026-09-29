"""Tests for ``Schema.document_diff``."""

import copy
import inspect

import pytest

from marshmallow import EXCLUDE, RAISE, Schema, fields
from marshmallow.exceptions import ValidationError


class AddressSchema(Schema):
    street = fields.String()
    city = fields.String()
    zip_code = fields.String()


class MemberSchema(Schema):
    name = fields.String()
    age = fields.Integer()


class PersonSchema(Schema):
    name = fields.String()
    age = fields.Integer()
    nickname = fields.String()
    address = fields.Nested(AddressSchema)
    members = fields.Nested(MemberSchema, many=True)
    tags = fields.List(fields.String())
    items = fields.List(fields.Nested(AddressSchema))


class Address:
    def __init__(self, street, city, zip_code):
        self.street = street
        self.city = city
        self.zip_code = zip_code


class Person:
    def __init__(self, name, age, nickname, address):
        self.name = name
        self.age = age
        self.nickname = nickname
        self.address = address


def make_document(**overrides):
    data = {
        "name": "Alice",
        "age": 30,
        "nickname": "Ally",
        "address": {"street": "Main St", "city": "Town", "zip_code": "00000"},
        "members": [
            {"name": "Bob", "age": 10},
            {"name": "Carol", "age": 12},
        ],
        "tags": ["a", "b", "c"],
        "items": [
            {"street": "1st Ave", "city": "City", "zip_code": "11111"},
        ],
    }
    data.update(overrides)
    return data


def test_equal_documents_return_empty_list():
    data = make_document()
    assert PersonSchema().document_diff(data, copy.deepcopy(data)) == []


def test_scalar_change():
    left = make_document()
    right = make_document(age=31)
    assert PersonSchema().document_diff(left, right) == [
        {"op": "change", "path": "age", "left": 30, "right": 31}
    ]


def test_scalar_add_and_remove():
    left = make_document()
    right = make_document()
    del left["nickname"]
    del right["age"]
    assert PersonSchema().document_diff(left, right) == [
        {"op": "remove", "path": "age", "left": 30, "right": None},
        {"op": "add", "path": "nickname", "left": None, "right": "Ally"},
    ]


def test_fields_are_visited_in_schema_declaration_order():
    # Insertion order in the documents deliberately differs from declaration
    # order; diff order must still follow ``schema.fields``.
    left = {
        "tags": ["a"],
        "members": [],
        "address": None,
        "age": 30,
        "name": "Alice",
        "nickname": None,
        "items": [],
    }
    right = {
        "items": [],
        "tags": ["b"],
        "address": None,
        "nickname": None,
        "age": 31,
        "members": [],
        "name": "Alicia",
    }
    records = PersonSchema(partial=True).document_diff(left, right)
    assert [record["path"] for record in records] == ["name", "age", "tags[0]"]


def test_nested_single_change_uses_dotted_path():
    left = make_document()
    right = make_document(
        address={"street": "Side St", "city": "Town", "zip_code": "00000"}
    )
    assert PersonSchema().document_diff(left, right) == [
        {
            "op": "change",
            "path": "address.street",
            "left": "Main St",
            "right": "Side St",
        }
    ]


def test_nested_single_add_and_remove_inside_document():
    left = make_document(
        address={"street": "Main St", "city": "Town"}
    )
    right = make_document(
        address={"street": "Main St", "city": "Town", "zip_code": "00000"}
    )
    assert PersonSchema().document_diff(left, right) == [
        {
            "op": "add",
            "path": "address.zip_code",
            "left": None,
            "right": "00000",
        }
    ]
    assert PersonSchema().document_diff(right, left) == [
        {
            "op": "remove",
            "path": "address.zip_code",
            "left": "00000",
            "right": None,
        }
    ]


def test_nested_single_whole_field_present_on_one_side():
    left = make_document(address=None)
    right = make_document()
    assert PersonSchema().document_diff(left, right) == [
        {
            "op": "change",
            "path": "address",
            "left": None,
            "right": right["address"],
        }
    ]

    left = make_document()
    del left["address"]
    right = make_document()
    assert PersonSchema().document_diff(left, right) == [
        {
            "op": "add",
            "path": "address",
            "left": None,
            "right": right["address"],
        }
    ]
    assert PersonSchema().document_diff(right, left) == [
        {
            "op": "remove",
            "path": "address",
            "left": right["address"],
            "right": None,
        }
    ]


def test_nested_many_element_change_uses_bracket_path():
    left = make_document()
    right = make_document(
        members=[
            {"name": "Bob", "age": 11},
            {"name": "Carol", "age": 12},
        ]
    )
    assert PersonSchema().document_diff(left, right) == [
        {"op": "change", "path": "members[0].age", "left": 10, "right": 11}
    ]


def test_nested_many_added_and_removed_elements_do_not_shift_into_changes():
    left = make_document(members=[{"name": "Bob", "age": 10}])
    right = make_document(
        members=[
            {"name": "Bob", "age": 10},
            {"name": "Carol", "age": 12},
        ]
    )
    assert PersonSchema().document_diff(left, right) == [
        {
            "op": "add",
            "path": "members[1]",
            "left": None,
            "right": {"name": "Carol", "age": 12},
        }
    ]
    assert PersonSchema().document_diff(right, left) == [
        {
            "op": "remove",
            "path": "members[1]",
            "left": {"name": "Carol", "age": 12},
            "right": None,
        }
    ]


def test_nested_many_equal_returns_empty_list():
    data = make_document()
    assert PersonSchema().document_diff(data, copy.deepcopy(data)) == []


def test_list_scalar_position_comparison():
    left = make_document(tags=["a", "b", "c"])
    right = make_document(tags=["a", "x", "c", "d"])
    assert PersonSchema().document_diff(left, right) == [
        {"op": "change", "path": "tags[1]", "left": "b", "right": "x"},
        {"op": "add", "path": "tags[3]", "left": None, "right": "d"},
    ]

    right = make_document(tags=["a"])
    assert PersonSchema().document_diff(left, right) == [
        {"op": "remove", "path": "tags[1]", "left": "b", "right": None},
        {"op": "remove", "path": "tags[2]", "left": "c", "right": None},
    ]


def test_list_of_nested_recurses():
    left = make_document(
        items=[{"street": "1st Ave", "city": "City", "zip_code": "11111"}]
    )
    right = make_document(
        items=[
            {"street": "1st Ave", "city": "City", "zip_code": "11111"},
            {"street": "2nd Ave", "city": "City", "zip_code": "22222"},
        ]
    )
    assert PersonSchema().document_diff(left, right) == [
        {
            "op": "add",
            "path": "items[1]",
            "left": None,
            "right": {"street": "2nd Ave", "city": "City", "zip_code": "22222"},
        }
    ]

    right = make_document(
        items=[{"street": "3rd Ave", "city": "City", "zip_code": "11111"}]
    )
    assert PersonSchema().document_diff(left, right) == [
        {
            "op": "change",
            "path": "items[0].street",
            "left": "1st Ave",
            "right": "3rd Ave",
        }
    ]


def test_unknown_keys_ignored_by_default():
    left = make_document(extra=1)
    right = make_document(extra=2)
    assert PersonSchema().document_diff(left, right) == []


def test_unknown_keys_included_when_requested():
    left = make_document(extra=1)
    right = make_document(extra=2)
    assert PersonSchema().document_diff(left, right, include_unknown=True) == [
        {"op": "change", "path": "extra", "left": 1, "right": 2}
    ]

    left = make_document()
    right = make_document(only_on_right=3)
    assert PersonSchema().document_diff(left, right, include_unknown=True) == [
        {"op": "add", "path": "only_on_right", "left": None, "right": 3}
    ]

    left = make_document(only_on_left=3)
    right = make_document()
    assert PersonSchema().document_diff(left, right, include_unknown=True) == [
        {"op": "remove", "path": "only_on_left", "left": 3, "right": None}
    ]


def test_unknown_keys_appear_after_declared_fields():
    # Declared field ``age`` changes as well; it must precede the unknown key.
    left = make_document(extra=1)
    right = make_document(age=31, extra=2)
    assert [
        record["path"]
        for record in PersonSchema().document_diff(
            left, right, include_unknown=True
        )
    ] == ["age", "extra"]


def test_ignore_fields_skips_declared_fields():
    left = make_document()
    right = make_document(age=31, nickname="Ace")
    assert PersonSchema().document_diff(
        left, right, ignore_fields=("age",)
    ) == [{"op": "change", "path": "nickname", "left": "Ally", "right": "Ace"}]


def test_ignore_fields_skips_whole_nested_field():
    left = make_document()
    right = make_document(
        address={"street": "Elsewhere", "city": "Else", "zip_code": "99999"}
    )
    assert (
        PersonSchema().document_diff(left, right, ignore_fields=("address",))
        == []
    )


def test_ignore_fields_apply_at_every_nesting_level():
    left = make_document(
        members=[
            {"name": "Bob", "age": 10},
            {"name": "Carol", "age": 12},
        ]
    )
    right = make_document(
        age=99,
        members=[
            {"name": "Bob", "age": 11},
            {"name": "Carol", "age": 99},
        ],
    )
    assert PersonSchema().document_diff(
        left, right, ignore_fields=("age",)
    ) == []


def test_ignore_fields_also_skip_unknown_keys():
    left = make_document(extra=1)
    right = make_document(extra=2)
    assert (
        PersonSchema().document_diff(
            left, right, include_unknown=True, ignore_fields=("extra",)
        )
        == []
    )


def test_non_mapping_inputs_are_dumped_first():
    schema = PersonSchema()
    left = Person(
        "Alice", 30, "Ally", Address("Main St", "Town", "00000")
    )
    right = Person(
        "Alice", 31, "Ally", Address("Main St", "Town", "00000")
    )
    assert schema.document_diff(left, right) == [
        {"op": "change", "path": "age", "left": 30, "right": 31}
    ]
    # Mixing a dumpable object with a dict.
    assert schema.document_diff(schema.dump(left), right) == [
        {"op": "change", "path": "age", "left": 30, "right": 31}
    ]


def test_document_diff_is_pure():
    schema = PersonSchema()
    left = make_document()
    right = make_document(age=31)
    left_before = copy.deepcopy(left)
    right_before = copy.deepcopy(right)
    fields_before = copy.deepcopy(schema.fields)

    schema.document_diff(left, right)
    schema.document_diff(left, right, include_unknown=True)
    schema.document_diff(left, right, ignore_fields=("age",))

    assert left == left_before
    assert right == right_before
    assert schema.fields.keys() == fields_before.keys()
    # Calling the diff does not alter dump output.
    assert schema.dump(
        Person("Alice", 30, "Ally", Address("Main St", "Town", "00000"))
    ) == schema.dump(
        Person("Alice", 30, "Ally", Address("Main St", "Town", "00000"))
    )


def test_data_key_used_for_lookup_but_field_name_used_for_path():
    class DataKeySchema(Schema):
        full_name = fields.String(data_key="fullName")

    schema = DataKeySchema()
    assert schema.document_diff(
        {"fullName": "Alice"}, {"fullName": "Bob"}
    ) == [
        {"op": "change", "path": "full_name", "left": "Alice", "right": "Bob"}
    ]


def test_dump_load_validate_behavior_unchanged():
    schema = PersonSchema()
    person = Person(
        "Alice", 30, "Ally", Address("Main St", "Town", "00000")
    )
    dumped = schema.dump(person)
    # ``members``/``tags``/``items`` are absent on the object and therefore
    # omitted from the dump, as with any marshmallow serialization.
    assert dumped == {
        "name": "Alice",
        "age": 30,
        "nickname": "Ally",
        "address": {
            "street": "Main St",
            "city": "Town",
            "zip_code": "00000",
        },
    }
    loaded = schema.load(
        {
            "name": "Bob",
            "age": "42",
            "nickname": "Bobby",
            "address": {
                "street": "Oak Ave",
                "city": "Ville",
                "zip_code": "12345",
            },
            "members": [{"name": "Dan", "age": "18"}],
            "tags": ["x"],
            "items": [],
        }
    )
    assert loaded["age"] == 42
    assert loaded["members"] == [{"name": "Dan", "age": 18}]

    errors = schema.validate({"name": "Eve", "age": "not-an-int"})
    assert "age" in errors

    # Default unknown policy is untouched: document_diff does not flip it.
    assert schema.unknown is RAISE
    with pytest.raises(ValidationError):
        schema.load({"name": "Eve", "unexpected": True})

    schema_exclude = PersonSchema(unknown=EXCLUDE)
    assert schema_exclude.load({"name": "Eve", "unexpected": True}) == {
        "name": "Eve"
    }


def test_document_diff_signature():
    sig = inspect.signature(Schema.document_diff)
    assert list(sig.parameters) == [
        "self",
        "left",
        "right",
        "include_unknown",
        "ignore_fields",
    ]
    assert sig.parameters["include_unknown"].default is False
    assert sig.parameters["ignore_fields"].default == ()
    assert sig.parameters["include_unknown"].kind is inspect.Parameter.KEYWORD_ONLY
    assert sig.parameters["ignore_fields"].kind is inspect.Parameter.KEYWORD_ONLY
    assert sig.parameters["left"].kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
