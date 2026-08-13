from typing import cast

import pytest

from treetop_client.models import (
    Action,
    AuthorizedResponseDetailed,
    ContextValue,
    Decision,
    Group,
    JsonObject,
    QualifiedId,
    Request,
    Resource,
    ResourceAttribute,
    ResourceAttributeType,
    User,
)


def test_qualified_id_and_group():
    q = QualifiedId(id="alice", namespace=["App"])
    g = Group(id=q)
    u = User(id=q, groups=[g])
    req = Request(
        principal=u,
        action=Action(id=QualifiedId(id="x")),
        resource=Resource(
            kind="Photo",
            id="1",
            attrs={"id": ResourceAttribute.new("1")},
        ),
    )
    api = req.to_api()
    principal = cast(JsonObject, api["principal"])
    user = cast(JsonObject, principal["User"])
    assert user["id"] == "alice"
    assert cast(list[str], user["namespace"]) == ["App"]
    assert user == {
        "id": "alice",
        "namespace": ["App"],
        "groups": [{"id": "alice", "namespace": ["App"]}],
    }


def test_resource_optional_attrs_and_namespaced_kind():
    assert Resource.new("Database::Table", "users").to_api() == {
        "kind": "Database::Table",
        "id": "users",
        "attrs": {},
    }


def test_user_no_colon():
    with pytest.raises(ValueError):
        _ = User(id=QualifiedId(id="bad:user"))


def test_group_no_colon():
    with pytest.raises(ValueError):
        _ = Group(id=QualifiedId(id="bad:group", namespace=["App"]))


def test_action_no_colon():
    with pytest.raises(ValueError):
        _ = Action(id=QualifiedId(id="bad:action"))


def test_user_with_namespace():
    q = QualifiedId(id="alice", namespace=["App"])
    u = User(id=q, groups=[])
    assert u.to_api() == {
        "id": "alice",
        "namespace": ["App"],
        "groups": [],
    }


def test_group_with_namespace():
    g = Group(id=QualifiedId(id="group1", namespace=["App"]))
    assert g.to_api() == {"id": "group1", "namespace": ["App"]}


def test_action_with_namespace():
    q = QualifiedId(id="edit", namespace=["App"])
    a = Action(id=q)
    assert a.to_api() == {"id": "edit", "namespace": ["App"]}


def test_user_new():
    u = User.new(id="alice", namespace=["App"], groups=["group1", "group2"])
    assert u.to_api() == {
        "id": "alice",
        "namespace": ["App"],
        "groups": [
            {"id": "group1", "namespace": ["App"]},
            {"id": "group2", "namespace": ["App"]},
        ],
    }


def test_group_new():
    g = Group.new(id="group1", namespace=["App"])
    assert g.to_api() == {"id": "group1", "namespace": ["App"]}


def test_action_new():
    a = Action.new(id="edit", namespace=["App"])
    assert a.to_api() == {"id": "edit", "namespace": ["App"]}


def test_request_context_serializes_resource_attributes():
    req = Request(
        principal=User.new("alice"),
        action=Action.new("view"),
        resource=Resource.new(
            "Photo",
            "1",
            attrs={"id": ResourceAttribute.new("1")},
        ),
        context={
            "env": ResourceAttribute.new("prod"),
            "retry": ResourceAttribute.new("3", ResourceAttributeType.NUMBER),
            "verified": ResourceAttribute.new(
                "true", ResourceAttributeType.BOOLEAN
            ),
            "raw_string": "direct",
            "raw_bool": False,
            "raw_long": 7,
            "raw_set": ["read", 9, True],
            "ip": {"type": "Ip", "value": "192.0.2.1"},
        },
    )

    assert req.to_api()["context"] == {
        "env": {"type": "String", "value": "prod"},
        "retry": {"type": "Long", "value": 3},
        "verified": {"type": "Bool", "value": True},
        "raw_string": {"type": "String", "value": "direct"},
        "raw_bool": {"type": "Bool", "value": False},
        "raw_long": {"type": "Long", "value": 7},
        "raw_set": {
            "type": "Set",
            "value": [
                {"type": "String", "value": "read"},
                {"type": "Long", "value": 9},
                {"type": "Bool", "value": True},
            ],
        },
        "ip": {"type": "Ip", "value": "192.0.2.1"},
    }


def test_resource_attribute_uses_attr_value_wire_format():
    assert ResourceAttribute.new("true", ResourceAttributeType.BOOLEAN).to_api() == {
        "type": "Bool",
        "value": True,
    }
    assert ResourceAttribute.new("42", ResourceAttributeType.NUMBER).to_api() == {
        "type": "Long",
        "value": 42,
    }


@pytest.mark.parametrize(
    "value",
    [
        None,
        1.5,
        2**63,
        {"type": "Boolean", "value": True},
        {"type": "Bool", "value": 1},
        {"type": "Long", "value": 1.0},
        {"type": "String", "value": True},
        {"type": "Set", "value": "read"},
        {"type": "Unknown", "value": "x"},
        {"type": "String"},
    ],
)
def test_request_context_rejects_invalid_attr_values(value: object):
    req = Request(
        principal=User.new("alice"),
        action=Action.new("view"),
        resource=Resource.new(
            "Photo",
            "1",
            attrs={"id": ResourceAttribute.new("1")},
        ),
        context={"invalid": cast(ContextValue, value)},
    )

    with pytest.raises(ValueError, match=r"context\['invalid'\]"):
        _ = req.to_api()


@pytest.mark.parametrize(
    "attribute",
    [
        ResourceAttribute.new("yes", ResourceAttributeType.BOOLEAN),
        ResourceAttribute.new("1.5", ResourceAttributeType.NUMBER),
        ResourceAttribute.new(str(2**63), ResourceAttributeType.NUMBER),
    ],
)
def test_resource_attribute_rejects_invalid_attr_values(
    attribute: ResourceAttribute,
):
    with pytest.raises(ValueError):
        _ = attribute.to_api()


def test_detailed_response_current_full_shape():
    resp = AuthorizedResponseDetailed.from_api(
        {
            "decision": "Allow",
            "policy": [{"literal": "permit (...);", "json": {"effect": "permit"}}],
            "version": {
                "hash": "abc123",
                "loaded_at": "2025-12-19T00:14:38.577289000Z",
            },
        }
    )

    assert resp.decision == Decision.ALLOW
    assert resp.version_hash() == "abc123"
    assert resp.policies[0].literal == "permit (...);"
