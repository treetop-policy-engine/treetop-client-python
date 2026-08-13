"""Shared payload builders for the CodSpeed benchmarks.

The builders here mirror the shapes returned by the Treetop REST API (see
``tests/test_client.py``) so that the benchmarks exercise realistic data.
"""

from __future__ import annotations

from pathlib import Path
from typing import cast

from treetop_client.models import (
    Action,
    ContextValue,
    JsonArray,
    JsonObject,
    Request,
    Resource,
    ResourceAttribute,
    ResourceAttributeType,
    User,
)

_TIMESTAMP = "2025-12-19T00:14:38.577289000Z"

TESTDATA = Path(__file__).resolve().parent.parent / "testdata"


def make_request(index: int = 0, *, with_context: bool = False) -> Request:
    """Build a representative authorization request."""
    context: dict[str, ContextValue] | None = None
    if with_context:
        context = {
            "env": "production",
            "mfa": True,
            "retries": 3,
            "source_ip": ResourceAttribute.new("10.0.0.1", ResourceAttributeType.IP),
            "tags": ["dns", "host", f"batch-{index}"],
            "nested": [{"type": "Long", "value": index}, {"type": "String", "value": "leaf"}],
        }
    return Request(
        principal=User.new(
            f"user-{index}",
            ["DNS"],
            ["admins", "webadmins", "users"],
        ),
        action=Action.new("create_host", ["DNS"]),
        resource=Resource.new(
            "Host",
            f"host-{index}.example.com",
            attrs={
                "name": ResourceAttribute.new(f"host-{index}.example.com"),
                "ip": ResourceAttribute.new("10.0.0.1", ResourceAttributeType.IP),
                "ttl": ResourceAttribute.new("3600", ResourceAttributeType.NUMBER),
                "managed": ResourceAttribute.new("true", ResourceAttributeType.BOOLEAN),
            },
        ),
        id=f"req-{index}",
        context=context,
    )


def make_requests(count: int, *, with_context: bool = False) -> list[Request]:
    return [make_request(i, with_context=with_context) for i in range(count)]


def version_payload() -> JsonObject:
    return {"hash": "policyhash", "loaded_at": _TIMESTAMP}


def policy_payload(index: int = 0) -> JsonObject:
    return {
        "literal": (
            "@id(\"DNS.admins_policy\")\n"
            "permit (\n"
            "    principal in DNS::Group::\"admins\",\n"
            "    action in [DNS::Action::\"create_host\"],\n"
            "    resource\n"
            ");"
        ),
        "json": {
            "effect": "permit",
            "principal": {"op": "in", "entity": {"type": "DNS::Group", "id": "admins"}},
            "action": {"op": "in", "entities": [{"type": "DNS::Action", "id": "create_host"}]},
            "resource": {"op": "All"},
            "conditions": [],
        },
        "annotation_id": f"DNS.admins_policy.{index}",
        "cedar_id": f"policy{index}",
    }


def brief_batch_payload(count: int) -> JsonObject:
    results: JsonArray = [
        {
            "index": i,
            "id": f"req-{i}",
            "status": "success",
            "result": {"decision": "Allow" if i % 3 else "Deny"},
        }
        for i in range(count)
    ]
    return {
        "results": results,
        "version": version_payload(),
        "successful": count,
        "failed": 0,
    }


def detailed_batch_payload(count: int) -> JsonObject:
    results: JsonArray = []
    for i in range(count):
        if i % 3:
            decision: JsonObject = {
                "Allow": {
                    "policy": cast(JsonArray, [policy_payload(i)]),
                    "version": version_payload(),
                }
            }
        else:
            decision = {"Deny": {"version": version_payload()}}
        results.append(
            {
                "index": i,
                "id": f"req-{i}",
                "status": "success",
                "result": {"decision": decision},
            }
        )
    return {
        "results": results,
        "version": version_payload(),
        "successful": count,
        "failed": 0,
    }


def metadata_payload(content: str = "permit (principal, action, resource);") -> JsonObject:
    return {
        "timestamp": _TIMESTAMP,
        "sha256": "abc123",
        "size": len(content),
        "source": {"kind": "file", "path": "/etc/treetop/policies.cedar"},
        "refresh_frequency": 60,
        "entries": 12,
        "content": content,
    }


def status_payload() -> JsonObject:
    return {
        "policy_configuration": {
            "allow_upload": True,
            "schema_validation_mode": "permissive",
            "policies": metadata_payload(),
            "labels": metadata_payload("{}"),
            "schema": metadata_payload('{"": {}}'),
        },
        "parallel_configuration": {
            "cpu_count": 8,
            "workers": 8,
            "rayon_threads": 8,
            "par_threshold": 32,
            "allow_parallel": True,
        },
        "request_limits": {
            "max_context_bytes": 65536,
            "max_context_depth": 8,
            "max_context_keys": 64,
        },
        "request_context": {
            "supported": True,
            "schema_backed": True,
            "fallback_reason": None,
        },
    }


def version_response_payload() -> JsonObject:
    return {
        "version": "v0.0.7",
        "core": {"version": "0.3.0", "cedar": "0.11.0"},
        "policies": version_payload(),
        "schema": {"hash": "schemahash", "loaded_at": _TIMESTAMP},
    }
