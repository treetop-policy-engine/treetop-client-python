from datetime import datetime
from typing import cast

import pytest

from treetop_client.models import (
    Action,
    AuthorizedResponseDetailed,
    AuthorizedResponseBrief,
    ContextValue,
    Decision,
    Group,
    JsonObject,
    QualifiedId,
    PolicyVersion,
    JsonValue,
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
            "policy": [{"literal": "permit (...);", "json": {"effect": "permit"}, "cedar_id": "policy0"}],
            "version": {
                "hash": "abc123",
                "loaded_at": "2025-12-19T00:14:38.577289000Z", "label_set": None, "generation": 0},
        }
    )

    assert resp.decision == Decision.ALLOW
    assert resp.version_hash() == "abc123"
    assert resp.policies[0].literal == "permit (...);"


@pytest.mark.parametrize("label_set", [None, "labels-v2"])
@pytest.mark.parametrize("generation", [0, 7, (1 << 64) - 1])
def test_policy_version_retains_complete_state(label_set: str | None, generation: int):
    wire: JsonObject = {
        "hash": "abc", "loaded_at": "2026-09-05T00:00:00Z",
        "label_set": label_set, "generation": generation}
    version = PolicyVersion.from_api(wire)
    assert version.label_set == label_set
    assert version.generation == generation
    assert version == PolicyVersion.from_api(wire)
    changed: JsonObject = dict(wire, generation=(generation + 1) % (1 << 64))
    assert version != PolicyVersion.from_api(changed)
    for response_type in [AuthorizedResponseBrief, AuthorizedResponseDetailed]:
        response = response_type.from_api({"decision": "Deny", "policy": [], "policy_id": "", "version": wire})
        assert response.version == version


@pytest.mark.parametrize("field", ["hash", "loaded_at", "label_set", "generation"])
def test_policy_version_requires_every_current_field(field: str):
    wire: JsonObject = {"hash":"h", "loaded_at":"2026-09-05T00:00:00Z", "label_set":None, "generation":0}
    del wire[field]
    with pytest.raises((KeyError, ValueError), match=field):
        _ = PolicyVersion.from_api(wire)


@pytest.mark.parametrize("generation", [-1, 1 << 64, True, False, 1.5, "1", None])
def test_policy_version_rejects_invalid_generation(generation: JsonValue):
    with pytest.raises((TypeError, ValueError), match="generation"):
        _ = PolicyVersion.from_api({
            "hash": "abc", "loaded_at": "2026-09-05T00:00:00Z", "generation": generation, "label_set": None})


def test_cached_versions_do_not_conflate_generation_types_or_state():
    wire: JsonObject = {
        "hash": "cached", "loaded_at": "2026-09-05T00:00:00Z",
        "label_set": "labels-v1", "generation": 0}
    original = PolicyVersion.from_api(wire)
    assert original == PolicyVersion.from_api(dict(wire))
    for field, value in [("label_set", "labels-v2"), ("generation", 1),
                         ("hash", "different"), ("loaded_at", "2026-09-06T00:00:00Z")]:
        changed: JsonObject = dict(wire)
        changed[field] = value
        assert PolicyVersion.from_api(changed) != original
    for generation in [False, True]:
        invalid: JsonObject = dict(wire, generation=generation)
        with pytest.raises(ValueError, match="generation"):
            _ = PolicyVersion.from_api(invalid)


@pytest.mark.parametrize("identified_labels", [False, True])
def test_policy_version_subclasses_are_constructed_independently(identified_labels: bool):
    constructed: list[str] = []

    class CustomPolicyVersion(PolicyVersion):
        def __post_init__(self) -> None:
            super().__post_init__()
            constructed.append(self.hash)

    wire: JsonObject = {"hash": "custom", "loaded_at": "2026-09-05T00:00:00Z", "label_set": None, "generation": 0}
    if identified_labels:
        wire.update({"label_set": "labels-v1", "generation": 7})
    first = CustomPolicyVersion.from_api(wire)
    second = CustomPolicyVersion.from_api(wire)
    assert isinstance(first, CustomPolicyVersion)
    assert first == second
    assert first is not second
    assert constructed == ["custom", "custom"]



def test_policy_version_passes_identified_labels_as_keywords():
    class KeywordVersion(PolicyVersion):
        def __init__(self, *, hash: str, loaded_at: datetime,
                     label_set: str | None = None, generation: int = 0):
            super().__init__(hash=hash, loaded_at=loaded_at,
                             label_set=label_set, generation=generation)

    wire: JsonObject = {"hash": "modern", "loaded_at": "2026-09-05T00:00:00Z",
                        "label_set": "labels", "generation": 7}
    version = KeywordVersion.from_api(wire)
    assert isinstance(version, KeywordVersion)
    assert version.label_set == "labels"
    assert version.generation == 7


@pytest.mark.parametrize("decision", [{"Allow":{"policy":[]}}, {"Deny":{}}, None])
def test_old_decision_shapes_and_typo_alias_are_rejected(decision: JsonValue):
    wire: JsonObject = {"decision":decision, "desicion":"Allow", "policy_id":"p", "policy":[],
                        "version":{"hash":"h","loaded_at":"2026-09-05T00:00:00Z","label_set":None,"generation":0}}
    for response_type in [AuthorizedResponseBrief, AuthorizedResponseDetailed]:
        with pytest.raises(ValueError, match="decision"):
            _ = response_type.from_api(wire)


@pytest.mark.parametrize("field,value", [("successful",0), ("failed",1), ("index",1), ("generation",1)])
def test_batch_rejects_inconsistent_current_metadata(field: str, value: int):
    from treetop_client.models import AuthorizeResponseBrief
    version: JsonObject = {"hash":"h","loaded_at":"2026-09-05T00:00:00Z","label_set":None,"generation":0}
    result_version: JsonObject = dict(version)
    entry: JsonObject = {"index":0,"status":"success","result":{"decision":"Allow","policy_id":"p","version":result_version}}
    batch: JsonObject = {"results":[entry],"version":version,"successful":1,"failed":0}
    if field == "index":
        entry[field] = value
    elif field == "generation":
        result_version[field] = value
    else:
        batch[field] = value
    with pytest.raises(ValueError, match="batch"):
        _ = AuthorizeResponseBrief.from_api(batch)


def test_all_allowed_rejects_empty_and_failed_batches():
    from treetop_client.models import AuthorizeResponseBrief
    version: JsonObject = {"hash":"h","loaded_at":"2026-09-05T00:00:00Z","label_set":None,"generation":0}
    empty = AuthorizeResponseBrief.from_api({"results":[],"version":version,"successful":0,"failed":0})
    failed = AuthorizeResponseBrief.from_api({"results":[{"index":0,"status":"failed","error":"evaluation failed"}],"version":version,"successful":0,"failed":1})
    assert not empty.all_allowed()
    assert not failed.all_allowed()


def test_schema_revision_is_distinct_from_authorization_generation():
    from treetop_client.models import SchemaVersion

    revision = SchemaVersion.from_api({"hash": "schema", "loaded_at": "2026-09-06T00:00:00Z"})
    assert revision.hash == "schema"
    for missing in ["hash", "loaded_at"]:
        data: JsonObject = {"hash": "schema", "loaded_at": "2026-09-06T00:00:00Z"}
        del data[missing]
        with pytest.raises(KeyError):
            _ = SchemaVersion.from_api(data)


@pytest.mark.parametrize("decision,policy_id", [("Allow", ""), ("Deny", "permit")])
def test_brief_decision_rejects_inconsistent_policy_id(decision: str, policy_id: str):
    with pytest.raises(ValueError):
        _ = AuthorizedResponseBrief.from_api({"decision": decision, "policy_id": policy_id,
            "version": {"hash":"h", "loaded_at":"2026-09-06T00:00:00Z", "label_set":None, "generation":0}})
