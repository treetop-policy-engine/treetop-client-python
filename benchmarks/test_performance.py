import pytest

from treetop_client.models import (
    Action,
    AuthorizeResponseBrief,
    JsonObject,
    Request,
    Resource,
    ResourceAttribute,
    ResourceAttributeType,
    User,
)

pytestmark = pytest.mark.benchmark


def _request(index: int) -> Request:
    return Request(
        id=f"request-{index}",
        principal=User.new(
            f"user-{index}", ["DNS"], ["admins", "operators", "users"]
        ),
        action=Action.new("create_host", ["DNS"]),
        resource=Resource.new(
            "Host",
            f"host-{index}.example.com",
            attrs={
                "name": ResourceAttribute.new(f"host-{index}.example.com"),
                "ip": ResourceAttribute.new(
                    f"192.0.2.{index % 254 + 1}", ResourceAttributeType.IP
                ),
            },
        ),
        context={
            "environment": "production",
            "approved": True,
            "retry_count": index,
            "roles": ["operator", "reviewer"],
        },
    )


REQUESTS = [_request(index) for index in range(128)]
VERSION: JsonObject = {
    "hash": "c82d116854d77bf689c3d15e167764876dffe869c970bc08ab7c5dacd7726219",
    "loaded_at": "2025-12-19T00:14:38.577289000Z",
}
BRIEF_RESPONSE: JsonObject = {
    "results": [
        {
            "index": index,
            "id": f"request-{index}",
            "status": "success",
            "result": {
                "decision": "Allow" if index % 2 == 0 else "Deny",
                "policy_id": "DNS.admins" if index % 2 == 0 else "",
                "version": VERSION,
            },
        }
        for index in range(128)
    ],
    "version": VERSION,
    "successful": 128,
    "failed": 0,
}


def test_serialize_authorization_batch_128() -> None:
    serialized = [request.to_api() for request in REQUESTS]
    assert len(serialized) == 128


def test_parse_brief_authorization_response_128() -> None:
    response = AuthorizeResponseBrief.from_api(BRIEF_RESPONSE)
    assert len(response) == 128
    assert response.allowed_count() == 64
