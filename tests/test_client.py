import asyncio
from datetime import datetime

import httpx
import pytest
from pytest_httpx import HTTPXMock

from treetop_client.client import TreeTopClient
from treetop_client.models import (
    Action,
    Decision,
    QualifiedId,
    Request,
    Resource,
    ResourceAttribute,
    User,
)


@pytest.fixture(autouse=True)
def client_cleanup():
    # ensure singleton reset between tests
    TreeTopClient().close()
    yield
    TreeTopClient().close()


def make_req(id_suffix: str | None = "1") -> Request:
    return Request(
        principal=User(id=QualifiedId(id="alice"), groups=[]),
        action=Action(id=QualifiedId(id="view")),
        resource=Resource(
            kind="Photo",
            id="42",
            attrs={
                "id": ResourceAttribute.new("42"),
            },
        ),
        id=f"check-{id_suffix}" if id_suffix else None,
    )


def metadata_payload(content: str = "...") -> dict[str, object]:
    return {
        "timestamp": "2025-12-19T00:14:38.577289000Z",
        "sha256": "abc123",
        "size": len(content),
        "source": None,
        "refresh_frequency": None,
        "entries": 1,
        "content": content,
    }


def add_health_version_status_responses(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        method="GET",
        url="http://localhost:9999/api/v1/health",
        json={},
        status_code=200,
    )
    httpx_mock.add_response(
        method="GET",
        url="http://localhost:9999/api/v1/version",
        json={
            "version": "v0.0.7",
            "core": {"version": "0.3.0", "cedar": "0.11.0"},
            "policies": {
                "hash": "policyhash",
                "loaded_at": "2025-12-19T00:14:38.577289000Z",
            },
            "schema": {
                "hash": "schemahash",
                "loaded_at": "2025-12-19T00:14:38.577289000Z",
            },
        },
        status_code=200,
    )
    httpx_mock.add_response(
        method="GET",
        url="http://localhost:9999/api/v1/status",
        json={
            "policy_configuration": {
                "allow_upload": False,
                "schema_validation_mode": "permissive",
                "policies": metadata_payload("permit (...);"),
                "labels": metadata_payload("{}"),
                "schema": metadata_payload('{"": {}}'),
            },
            "parallel_configuration": {
                "cpu_count": 8,
                "workers": 8,
                "rayon_threads": 8,
                "par_threshold": 8,
                "allow_parallel": True,
            },
            "request_limits": {
                "max_context_bytes": 16384,
                "max_context_depth": 8,
                "max_context_keys": 64,
            },
            "request_context": {
                "supported": True,
                "schema_backed": False,
                "fallback_reason": "no_schema",
            },
        },
        status_code=200,
    )


def add_download_responses(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        method="GET",
        url="http://localhost:9999/api/v1/policies",
        json={"policies": metadata_payload("permit (...);")},
        status_code=200,
    )
    httpx_mock.add_response(
        method="GET",
        url="http://localhost:9999/api/v1/policies?format=raw",
        text="permit (...);",
        status_code=200,
    )
    httpx_mock.add_response(
        method="GET",
        url="http://localhost:9999/api/v1/schema",
        json={"schema": metadata_payload('{"": {}}')},
        status_code=200,
    )
    httpx_mock.add_response(
        method="GET",
        url="http://localhost:9999/api/v1/schema?format=raw",
        text='{"": {}}',
        status_code=200,
    )


def add_upload_responses(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        method="POST",
        url="http://localhost:9999/api/v1/policies",
        match_headers={
            "Content-Type": "text/plain",
            "X-Upload-Token": "token",
        },
        json={"policies": metadata_payload("permit (...);")},
        status_code=200,
    )
    httpx_mock.add_response(
        method="POST",
        url="http://localhost:9999/api/v1/schema",
        match_headers={"X-Upload-Token": "token"},
        json={"schema": metadata_payload('{"": {}}')},
        status_code=200,
    )


def test_health_version_and_status(httpx_mock: HTTPXMock):
    add_health_version_status_responses(httpx_mock)

    client = TreeTopClient()
    assert client.health() is True
    version = client.version()
    assert version.version == "v0.0.7"
    assert version.core.cedar == "0.11.0"
    assert version.schema is not None
    assert version.schema.hash == "schemahash"

    status = client.status()
    assert status.policy_configuration.allow_upload is False
    assert status.policy_configuration.policies is not None
    assert status.policy_configuration.policies.content == "permit (...);"
    assert status.request_context.fallback_reason == "no_schema"


def test_get_policies_and_schema(httpx_mock: HTTPXMock):
    add_download_responses(httpx_mock)

    client = TreeTopClient()
    policies = client.get_policies()
    assert not isinstance(policies, str)
    assert policies.content == "permit (...);"
    assert client.get_policies(raw=True) == "permit (...);"

    schema = client.get_schema()
    assert not isinstance(schema, str)
    assert schema.content == '{"": {}}'
    assert client.get_schema(raw=True) == '{"": {}}'


def test_upload_policies_and_schema(httpx_mock: HTTPXMock):
    add_upload_responses(httpx_mock)

    client = TreeTopClient()
    policy_config = client.upload_policies("permit (...);", upload_token="token")
    assert policy_config.policies is not None
    assert policy_config.policies.content == "permit (...);"

    schema_config = client.upload_schema('{"": {}}', upload_token="token", as_json=True)
    assert schema_config.schema is not None
    assert schema_config.schema.content == '{"": {}}'


def test_async_health_version_and_status(httpx_mock: HTTPXMock):
    add_health_version_status_responses(httpx_mock)

    async def exercise() -> None:
        client = TreeTopClient()
        try:
            assert await client.ahealth() is True

            version = await client.aversion()
            assert version.version == "v0.0.7"
            assert version.core.cedar == "0.11.0"
            assert version.schema is not None
            assert version.schema.hash == "schemahash"

            status = await client.astatus()
            assert status.policy_configuration.allow_upload is False
            assert status.policy_configuration.policies is not None
            assert status.policy_configuration.policies.content == "permit (...);"
            assert status.request_context.fallback_reason == "no_schema"
        finally:
            await client.aclose()

    asyncio.run(exercise())


def test_async_get_policies_and_schema(httpx_mock: HTTPXMock):
    add_download_responses(httpx_mock)

    async def exercise() -> None:
        client = TreeTopClient()
        try:
            policies = await client.aget_policies()
            assert not isinstance(policies, str)
            assert policies.content == "permit (...);"
            assert await client.aget_policies(raw=True) == "permit (...);"

            schema = await client.aget_schema()
            assert not isinstance(schema, str)
            assert schema.content == '{"": {}}'
            assert await client.aget_schema(raw=True) == '{"": {}}'
        finally:
            await client.aclose()

    asyncio.run(exercise())


def test_async_upload_policies_and_schema(httpx_mock: HTTPXMock):
    add_upload_responses(httpx_mock)

    async def exercise() -> None:
        client = TreeTopClient()
        try:
            policy_config = await client.aupload_policies(
                "permit (...);", upload_token="token"
            )
            assert policy_config.policies is not None
            assert policy_config.policies.content == "permit (...);"

            schema_config = await client.aupload_schema(
                '{"": {}}', upload_token="token", as_json=True
            )
            assert schema_config.schema is not None
            assert schema_config.schema.content == '{"": {}}'
        finally:
            await client.aclose()

    asyncio.run(exercise())


# Tests for the new batch authorize endpoint
def test_authorize_single_request_brief(httpx_mock: HTTPXMock):
    """Test authorize endpoint with a single request (brief detail)."""
    httpx_mock.add_response(
        method="POST",
        url="http://localhost:9999/api/v1/authorize",
        json={
            "results": [
                {
                    "index": 0,
                    "id": "check-1",
                    "status": "success",
                    "result": {"decision": "Allow"},
                }
            ],
            "version": {
                "hash": "c82d116854d77bf689c3d15e167764876dffe869c970bc08ab7c5dacd7726219",
                "loaded_at": "2025-12-19T00:14:38.577289000Z",
            },
            "successful": 1,
            "failed": 0,
        },
        status_code=200,
    )
    client = TreeTopClient()
    response = client.authorize(make_req())
    assert len(response) == 1
    assert response.successful == 1
    assert response.failed == 0
    result = response[0]
    assert result.is_success()
    assert result.is_allowed()
    assert result.get_decision() == Decision.ALLOW


def test_authorize_multiple_requests_brief(httpx_mock: HTTPXMock):
    """Test authorize endpoint with multiple requests (brief detail)."""
    httpx_mock.add_response(
        method="POST",
        url="http://localhost:9999/api/v1/authorize",
        json={
            "results": [
                {
                    "index": 0,
                    "id": "check-1",
                    "status": "success",
                    "result": {"decision": "Allow"},
                },
                {
                    "index": 1,
                    "id": "check-2",
                    "status": "failed",
                    "error": "Evaluation failed: invalid resource",
                },
            ],
            "version": {
                "hash": "c82d116854d77bf689c3d15e167764876dffe869c970bc08ab7c5dacd7726219",
                "loaded_at": "2025-12-19T00:14:38.577289000Z",
            },
            "successful": 1,
            "failed": 1,
        },
        status_code=200,
    )
    client = TreeTopClient()
    requests = [make_req("1"), make_req("2")]
    response = client.authorize(requests)
    assert len(response) == 2
    assert response.successful == 1
    assert response.failed == 1

    result1 = response[0]
    assert result1.is_success()
    assert result1.is_allowed()

    result2 = response[1]
    assert result2.is_failed()
    assert result2.error == "Evaluation failed: invalid resource"

    # Test get_by_id
    found = response.get_by_id("check-1")
    assert found is not None
    assert found.is_allowed()


def test_authorize_detailed(httpx_mock: HTTPXMock):
    """Test authorize_detailed endpoint with detailed response."""
    httpx_mock.add_response(
        method="POST",
        url="http://localhost:9999/api/v1/authorize?detail=full",
        json={
            "results": [
                {
                    "index": 0,
                    "id": "check-1",
                    "status": "success",
                    "result": {
                        "decision": {
                            "Allow": {
                                "policy": [
                                    {
                                        "literal": 'permit (\n    principal == User::"alice",\n    action in [Action::"view"],\n    resource == Photo::"42"\n);',
                                        "json": {
                                            "action": {
                                                "entities": [
                                                    {"id": "view", "type": "Action"}
                                                ],
                                                "op": "in",
                                            },
                                            "conditions": [],
                                            "effect": "permit",
                                            "principal": {
                                                "entity": {
                                                    "id": "alice",
                                                    "type": "User",
                                                },
                                                "op": "==",
                                            },
                                            "resource": {
                                                "entity": {"id": "42", "type": "Photo"},
                                                "op": "==",
                                            },
                                        },
                                    }
                                ],
                                "version": {
                                    "hash": "c82d116854d77bf689c3d15e167764876dffe869c970bc08ab7c5dacd7726219",
                                    "loaded_at": "2025-12-19T15:25:55.384783000Z",
                                },
                            },
                        },
                    },
                }
            ],
            "version": {
                "hash": "c82d116854d77bf689c3d15e167764876dffe869c970bc08ab7c5dacd7726219",
                "loaded_at": "2025-12-19T00:14:38.577289000Z",
            },
            "successful": 1,
            "failed": 0,
        },
        status_code=200,
    )
    client = TreeTopClient()
    response = client.authorize_detailed(make_req())
    assert len(response) == 1
    result = response[0]
    assert result.is_success()
    assert result.is_allowed()
    policies = list(result)
    assert len(policies) > 0
    assert 'principal == User::"alice"' in policies[0].literal
    assert (
        result.version_hash()
        == "c82d116854d77bf689c3d15e167764876dffe869c970bc08ab7c5dacd7726219"
    )
    assert result.version_loaded_at() is not None


def test_authorize_deny(httpx_mock: HTTPXMock):
    """Test authorize endpoint with Deny decision."""
    httpx_mock.add_response(
        method="POST",
        url="http://localhost:9999/api/v1/authorize",
        json={
            "results": [
                {
                    "index": 0,
                    "id": "check-1",
                    "status": "success",
                    "result": {"decision": "Deny"},
                }
            ],
            "version": {
                "hash": "c82d116854d77bf689c3d15e167764876dffe869c970bc08ab7c5dacd7726219",
                "loaded_at": "2025-12-19T00:14:38.577289000Z",
            },
            "successful": 1,
            "failed": 0,
        },
        status_code=200,
    )
    client = TreeTopClient()
    response = client.authorize(make_req())
    assert len(response) == 1
    result = response[0]
    assert result.is_success()
    assert result.is_denied()
    assert result.get_decision() == Decision.DENY


def test_authorize_error(httpx_mock: HTTPXMock):
    """Test authorize endpoint with HTTP error."""
    httpx_mock.add_response(
        method="POST",
        url="http://localhost:9999/api/v1/authorize",
        json={"error": "Invalid request"},
        status_code=400,
    )
    client = TreeTopClient()
    with pytest.raises(httpx.HTTPStatusError):
        _ = client.authorize(make_req())


def test_async_authorize(httpx_mock: HTTPXMock):
    """Test async authorize endpoint."""
    httpx_mock.add_response(
        method="POST",
        url="http://localhost:9999/api/v1/authorize",
        json={
            "results": [
                {
                    "index": 0,
                    "id": "check-1",
                    "status": "success",
                    "result": {"decision": "Allow"},
                }
            ],
            "version": {
                "hash": "c82d116854d77bf689c3d15e167764876dffe869c970bc08ab7c5dacd7726219",
                "loaded_at": "2025-12-19T00:14:38.577289000Z",
            },
            "successful": 1,
            "failed": 0,
        },
        status_code=200,
    )
    client = TreeTopClient()
    import asyncio

    asyncio.set_event_loop(asyncio.new_event_loop())
    response = asyncio.get_event_loop().run_until_complete(
        client.aauthorize(make_req())
    )
    assert len(response) == 1
    result = response[0]
    assert result.is_allowed()


# Backward compatibility tests (old check/check_detailed API)
def test_check_backward_compatibility(httpx_mock: HTTPXMock):
    """Test backward compatibility with old check() method."""
    httpx_mock.add_response(
        method="POST",
        url="http://localhost:9999/api/v1/authorize",
        json={
            "results": [
                {
                    "index": 0,
                    "id": None,
                    "status": "success",
                    "result": {"decision": "Allow"},
                }
            ],
            "version": {
                "hash": "c82d116854d77bf689c3d15e167764876dffe869c970bc08ab7c5dacd7726219",
                "loaded_at": "2025-12-19T00:14:38.577289000Z",
            },
            "successful": 1,
            "failed": 0,
        },
        status_code=200,
    )
    client = TreeTopClient()
    resp = client.check(make_req(id_suffix=None))
    assert resp.is_allowed()
    assert resp.decision == Decision.ALLOW


def test_check_detailed_backward_compatibility(httpx_mock: HTTPXMock):
    """Test backward compatibility with old check_detailed() method."""
    httpx_mock.add_response(
        method="POST",
        url="http://localhost:9999/api/v1/authorize?detail=full",
        json={
            "results": [
                {
                    "index": 0,
                    "id": None,
                    "status": "success",
                    "result": {
                        "decision": {
                            "Allow": {
                                "policy": [
                                    {
                                        "literal": 'permit (\n    principal == User::"alice",\n    action in [Action::"view"],\n    resource == Photo::"42"\n);',
                                        "json": {
                                            "effect": "permit",
                                            "principal": {
                                                "entity": {
                                                    "id": "alice",
                                                    "type": "User",
                                                },
                                                "op": "==",
                                            },
                                            "action": {
                                                "entities": [
                                                    {"id": "view", "type": "Action"}
                                                ],
                                                "op": "in",
                                            },
                                            "resource": {
                                                "entity": {"id": "42", "type": "Photo"},
                                                "op": "==",
                                            },
                                            "conditions": [],
                                        },
                                    }
                                ],
                                "version": {
                                    "hash": "c82d116854d77bf689c3d15e167764876dffe869c970bc08ab7c5dacd7726219",
                                    "loaded_at": "2025-12-16T15:25:55.384783000Z",
                                },
                            },
                        },
                    },
                }
            ],
            "version": {
                "hash": "c82d116854d77bf689c3d15e167764876dffe869c970bc08ab7c5dacd7726219",
                "loaded_at": "2025-12-16T15:25:55.384783000Z",
            },
            "successful": 1,
            "failed": 0,
        },
        status_code=200,
    )
    client = TreeTopClient()
    resp = client.check_detailed(make_req(id_suffix=None))
    assert resp.is_allowed()
    assert resp.decision == Decision.ALLOW
    assert len(resp.policies) > 0
    policies = resp.policies
    assert len(policies) > 0
    assert "alice" in policies[0].literal
    assert (
        resp.version_hash()
        == "c82d116854d77bf689c3d15e167764876dffe869c970bc08ab7c5dacd7726219"
    )
    loaded_at = resp.version_loaded_at()
    assert loaded_at is not None
    assert isinstance(loaded_at, datetime)


def test_check_deny_backward_compatibility(httpx_mock: HTTPXMock):
    """Test backward compatibility with old check() method returning Deny."""
    httpx_mock.add_response(
        method="POST",
        url="http://localhost:9999/api/v1/authorize",
        json={
            "results": [
                {
                    "index": 0,
                    "id": None,
                    "status": "success",
                    "result": {"decision": "Deny"},
                }
            ],
            "version": {
                "hash": "c82d116854d77bf689c3d15e167764876dffe869c970bc08ab7c5dacd7726219",
                "loaded_at": "2025-12-19T00:14:38.577289000Z",
            },
            "successful": 1,
            "failed": 0,
        },
        status_code=200,
    )
    client = TreeTopClient()
    resp = client.check(make_req(id_suffix=None))
    assert resp.is_denied()
    assert resp.decision == Decision.DENY


# Batch query tests with index and ID lookups
def test_batch_authorize_lookup_by_index(httpx_mock: HTTPXMock):
    """Test batch authorize with multiple requests - lookup by index."""
    httpx_mock.add_response(
        method="POST",
        url="http://localhost:9999/api/v1/authorize",
        json={
            "results": [
                {
                    "index": 0,
                    "id": "req-alice-view",
                    "status": "success",
                    "result": {"decision": "Allow"},
                },
                {
                    "index": 1,
                    "id": "req-bob-delete",
                    "status": "success",
                    "result": {"decision": "Deny"},
                },
                {
                    "index": 2,
                    "id": "req-charlie-edit",
                    "status": "success",
                    "result": {"decision": "Allow"},
                },
            ],
            "version": {
                "hash": "abc123",
                "loaded_at": "2025-12-19T00:14:38.577289000Z",
            },
            "successful": 3,
            "failed": 0,
        },
        status_code=200,
    )
    client = TreeTopClient()
    requests = [make_req("1"), make_req("2"), make_req("3")]
    response = client.authorize(requests)

    # Test lookup by index
    assert len(response) == 3
    assert response[0].is_allowed()
    assert response[1].is_denied()
    assert response[2].is_allowed()

    # Verify indexes match
    assert response[0].index == 0
    assert response[1].index == 1
    assert response[2].index == 2


def test_batch_authorize_lookup_by_id(httpx_mock: HTTPXMock):
    """Test batch authorize with multiple requests - lookup by ID."""
    httpx_mock.add_response(
        method="POST",
        url="http://localhost:9999/api/v1/authorize",
        json={
            "results": [
                {
                    "index": 0,
                    "id": "req-alice-view",
                    "status": "success",
                    "result": {"decision": "Allow"},
                },
                {
                    "index": 1,
                    "id": "req-bob-delete",
                    "status": "success",
                    "result": {"decision": "Deny"},
                },
                {
                    "index": 2,
                    "id": "req-charlie-edit",
                    "status": "success",
                    "result": {"decision": "Allow"},
                },
            ],
            "version": {
                "hash": "abc123",
                "loaded_at": "2025-12-19T00:14:38.577289000Z",
            },
            "successful": 3,
            "failed": 0,
        },
        status_code=200,
    )
    client = TreeTopClient()
    requests = [make_req("1"), make_req("2"), make_req("3")]
    response = client.authorize(requests)

    # Test lookup by ID
    alice_result = response.get_by_id("req-alice-view")
    assert alice_result is not None
    assert alice_result.is_allowed()
    assert alice_result.id == "req-alice-view"

    bob_result = response.get_by_id("req-bob-delete")
    assert bob_result is not None
    assert bob_result.is_denied()
    assert bob_result.id == "req-bob-delete"

    charlie_result = response.get_by_id("req-charlie-edit")
    assert charlie_result is not None
    assert charlie_result.is_allowed()
    assert charlie_result.id == "req-charlie-edit"

    # Test lookup of non-existent ID
    nonexistent = response.get_by_id("req-nonexistent")
    assert nonexistent is None


def test_batch_authorize_detailed_lookup_by_index(httpx_mock: HTTPXMock):
    """Test batch authorize_detailed with multiple requests - lookup by index."""
    httpx_mock.add_response(
        method="POST",
        url="http://localhost:9999/api/v1/authorize?detail=full",
        json={
            "results": [
                {
                    "index": 0,
                    "id": "req-1",
                    "status": "success",
                    "result": {
                        "decision": {
                            "Allow": {
                                "policy": [
                                    {
                                        "literal": "permit (...);",
                                        "json": {
                                            "effect": "permit",
                                        },
                                    }
                                ],
                                "version": {
                                    "hash": "hash1",
                                    "loaded_at": "2025-12-19T00:14:38.577289000Z",
                                },
                            }
                        }
                    },
                },
                {
                    "index": 1,
                    "id": "req-2",
                    "status": "success",
                    "result": {
                        "decision": {
                            "Deny": {
                                "version": {
                                    "hash": "hash2",
                                    "loaded_at": "2025-12-19T00:14:38.577289000Z",
                                }
                            }
                        }
                    },
                },
            ],
            "version": {
                "hash": "abc123",
                "loaded_at": "2025-12-19T00:14:38.577289000Z",
            },
            "successful": 2,
            "failed": 0,
        },
        status_code=200,
    )
    client = TreeTopClient()
    requests = [make_req("1"), make_req("2")]
    response = client.authorize_detailed(requests)

    # Test lookup by index
    assert len(response) == 2
    assert response[0].is_allowed()
    policies = response[0].policies
    assert len(policies) > 0
    assert response[0].version_hash() == "hash1"

    assert response[1].is_denied()
    assert len(response[1].policies) == 0
    assert response[1].version_hash() == "hash2"


def test_batch_authorize_detailed_lookup_by_id(httpx_mock: HTTPXMock):
    """Test batch authorize_detailed with multiple requests - lookup by ID."""
    httpx_mock.add_response(
        method="POST",
        url="http://localhost:9999/api/v1/authorize?detail=full",
        json={
            "results": [
                {
                    "index": 0,
                    "id": "photo-allow",
                    "status": "success",
                    "result": {
                        "decision": {
                            "Allow": {
                                "policy": [
                                    {
                                        "literal": "permit (...);",
                                        "json": {
                                            "effect": "permit",
                                        },
                                    }
                                ],
                                "version": {
                                    "hash": "hash1",
                                    "loaded_at": "2025-12-19T00:14:38.577289000Z",
                                },
                            }
                        }
                    },
                },
                {
                    "index": 1,
                    "id": "video-deny",
                    "status": "success",
                    "result": {
                        "decision": {
                            "Deny": {
                                "version": {
                                    "hash": "hash2",
                                    "loaded_at": "2025-12-19T00:14:38.577289000Z",
                                }
                            }
                        }
                    },
                },
            ],
            "version": {
                "hash": "abc123",
                "loaded_at": "2025-12-19T00:14:38.577289000Z",
            },
            "successful": 2,
            "failed": 0,
        },
        status_code=200,
    )
    client = TreeTopClient()
    requests = [
        Request(
            principal=User(id=QualifiedId(id="alice"), groups=[]),
            action=Action(id=QualifiedId(id="view")),
            resource=Resource(
                kind="Photo",
                id="42",
                attrs={"id": ResourceAttribute.new("42")},
            ),
            id="photo-allow",
        ),
        Request(
            principal=User(id=QualifiedId(id="bob"), groups=[]),
            action=Action(id=QualifiedId(id="view")),
            resource=Resource(
                kind="Video",
                id="99",
                attrs={"id": ResourceAttribute.new("99")},
            ),
            id="video-deny",
        ),
    ]
    response = client.authorize_detailed(requests)

    # Test lookup by ID
    photo_result = response.get_by_id("photo-allow")
    assert photo_result is not None
    assert photo_result.is_allowed()
    policies = photo_result.policies
    assert len(policies) > 0
    assert photo_result.version_hash() == "hash1"

    video_result = response.get_by_id("video-deny")
    assert video_result is not None
    assert video_result.is_denied()
    assert len(video_result.policies) == 0
    assert video_result.version_hash() == "hash2"


def test_batch_authorize_mixed_success_and_failure(httpx_mock: HTTPXMock):
    """Test batch authorize with both successful and failed results."""
    httpx_mock.add_response(
        method="POST",
        url="http://localhost:9999/api/v1/authorize",
        json={
            "results": [
                {
                    "index": 0,
                    "id": "req-ok",
                    "status": "success",
                    "result": {"decision": "Allow"},
                },
                {
                    "index": 1,
                    "id": "req-error",
                    "status": "failed",
                    "error": "Invalid resource kind",
                },
                {
                    "index": 2,
                    "id": "req-ok2",
                    "status": "success",
                    "result": {"decision": "Deny"},
                },
            ],
            "version": {
                "hash": "abc123",
                "loaded_at": "2025-12-19T00:14:38.577289000Z",
            },
            "successful": 2,
            "failed": 1,
        },
        status_code=200,
    )
    client = TreeTopClient()
    requests = [make_req("1"), make_req("2"), make_req("3")]
    response = client.authorize(requests)

    # Verify counts
    assert response.successful == 2
    assert response.failed == 1
    assert len(response) == 3

    # Test lookup by index with error
    assert response[0].is_success()
    assert response[0].is_allowed()

    assert response[1].is_failed()
    assert response[1].error == "Invalid resource kind"
    assert response[1].result is None

    assert response[2].is_success()
    assert response[2].is_denied()

    # Test lookup by ID
    found_ok = response.get_by_id("req-ok")
    assert found_ok is not None
    assert found_ok.is_allowed()

    found_error = response.get_by_id("req-error")
    assert found_error is not None
    assert found_error.is_failed()

    found_ok2 = response.get_by_id("req-ok2")
    assert found_ok2 is not None
    assert found_ok2.is_denied()


def test_batch_authorize_iteration(httpx_mock: HTTPXMock):
    """Test iterating over batch authorize results."""
    httpx_mock.add_response(
        method="POST",
        url="http://localhost:9999/api/v1/authorize",
        json={
            "results": [
                {
                    "index": 0,
                    "id": "req-1",
                    "status": "success",
                    "result": {"decision": "Allow"},
                },
                {
                    "index": 1,
                    "id": "req-2",
                    "status": "success",
                    "result": {"decision": "Deny"},
                },
                {
                    "index": 2,
                    "id": "req-3",
                    "status": "success",
                    "result": {"decision": "Allow"},
                },
            ],
            "version": {
                "hash": "abc123",
                "loaded_at": "2025-12-19T00:14:38.577289000Z",
            },
            "successful": 3,
            "failed": 0,
        },
        status_code=200,
    )
    client = TreeTopClient()
    requests = [make_req("1"), make_req("2"), make_req("3")]
    response = client.authorize(requests)

    # Test iteration
    decisions = [result.get_decision() for result in response]
    assert decisions == [Decision.ALLOW, Decision.DENY, Decision.ALLOW]

    # Test iteration with filter
    allowed_count = sum(1 for result in response if result.is_allowed())
    assert allowed_count == 2
