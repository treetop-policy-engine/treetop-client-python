"""Benchmarks for the full client code path against a mocked HTTP transport.

The HTTP layer is mocked with ``pytest-httpx`` so the measurements cover what the
client actually owns: request serialization, header building, JSON encoding and
response parsing.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator

import pytest
from benchmarks.helpers import (
    brief_batch_payload,
    detailed_batch_payload,
    make_requests,
    metadata_payload,
    status_payload,
    user_policies_payload,
    version_response_payload,
)
from pytest_codspeed import BenchmarkFixture
from pytest_httpx import HTTPXMock

from treetop_client.client import TreeTopClient
from treetop_client.models import Decision

BASE_URL = "http://treetop.test"

pytestmark = [
    pytest.mark.benchmark,
    pytest.mark.httpx_mock(
        can_send_already_matched_responses=True,
        assert_all_responses_were_requested=False,
    ),
]


@pytest.fixture
def client() -> Iterator[TreeTopClient]:
    client = TreeTopClient(base_url=BASE_URL)
    yield client
    client.close()


@pytest.fixture
def loop() -> Iterator[asyncio.AbstractEventLoop]:
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


def test_first_sync_request_lifecycle(
    benchmark: BenchmarkFixture,
    httpx_mock: HTTPXMock,
):
    """Measure construction, first sync request, and cleanup together."""

    httpx_mock.add_response(
        method="GET",
        url=f"{BASE_URL}/api/v1/health",
        json={},
    )

    def create_request_and_close() -> bool:
        instance = TreeTopClient(base_url=BASE_URL)
        try:
            return instance.health()
        finally:
            instance.close()

    assert benchmark(create_request_and_close)


@pytest.mark.parametrize("count", [1, 50])
def test_authorize(
    benchmark: BenchmarkFixture,
    httpx_mock: HTTPXMock,
    client: TreeTopClient,
    count: int,
):
    httpx_mock.add_response(
        method="POST",
        url=f"{BASE_URL}/api/v1/authorize",
        json=brief_batch_payload(count),
    )
    requests = make_requests(count, with_context=True)
    response = benchmark(client.authorize, requests)
    assert len(response) == count


@pytest.mark.parametrize("count", [1, 20])
def test_authorize_detailed(
    benchmark: BenchmarkFixture,
    httpx_mock: HTTPXMock,
    client: TreeTopClient,
    count: int,
):
    httpx_mock.add_response(
        method="POST",
        url=f"{BASE_URL}/api/v1/authorize?detail=full",
        json=detailed_batch_payload(count),
    )
    requests = make_requests(count)
    response = benchmark(client.authorize_detailed, requests)
    assert len(response) == count


def test_check(benchmark: BenchmarkFixture, httpx_mock: HTTPXMock, client: TreeTopClient):
    """Single-request compatibility wrapper around the batch endpoint."""
    httpx_mock.add_response(
        method="POST",
        url=f"{BASE_URL}/api/v1/authorize",
        json=brief_batch_payload(1),
    )
    request = make_requests(1)[0]
    result = benchmark(client.check, request)
    assert result.decision == Decision.DENY


def test_async_authorize(
    benchmark: BenchmarkFixture,
    httpx_mock: HTTPXMock,
    client: TreeTopClient,
    loop: asyncio.AbstractEventLoop,
):
    httpx_mock.add_response(
        method="POST",
        url=f"{BASE_URL}/api/v1/authorize",
        json=brief_batch_payload(20),
    )
    requests = make_requests(20)
    response = benchmark(lambda: loop.run_until_complete(client.aauthorize(requests)))
    assert len(response) == 20
    loop.run_until_complete(client.aclose())


def test_status(benchmark: BenchmarkFixture, httpx_mock: HTTPXMock, client: TreeTopClient):
    httpx_mock.add_response(
        method="GET",
        url=f"{BASE_URL}/api/v1/status",
        json=status_payload(),
    )
    status = benchmark(client.status)
    assert status.parallel_configuration.workers == 8


def test_version(benchmark: BenchmarkFixture, httpx_mock: HTTPXMock, client: TreeTopClient):
    httpx_mock.add_response(
        method="GET",
        url=f"{BASE_URL}/api/v1/version",
        json=version_response_payload(),
    )
    version = benchmark(client.version)
    assert version.core.cedar == "0.11.0"


def test_get_policies(
    benchmark: BenchmarkFixture,
    httpx_mock: HTTPXMock,
    client: TreeTopClient,
    cedar_policies: str,
):
    httpx_mock.add_response(
        method="GET",
        url=f"{BASE_URL}/api/v1/policies",
        json={"policies": metadata_payload(cedar_policies)},
    )
    metadata = benchmark(client.get_policies)
    assert metadata is not None


def test_list_policies(
    benchmark: BenchmarkFixture,
    httpx_mock: HTTPXMock,
    client: TreeTopClient,
):
    httpx_mock.add_response(
        method="GET",
        url=f"{BASE_URL}/api/v1/policies/alice?groups=admins&groups=operators&namespaces=DNS",
        json=user_policies_payload(25),
    )
    policies = benchmark(
        client.list_policies,
        "alice",
        groups=["admins", "operators"],
        namespaces=["DNS"],
    )
    assert not isinstance(policies, str)


def test_list_policies_many_filters(
    benchmark: BenchmarkFixture,
    httpx_mock: HTTPXMock,
    client: TreeTopClient,
):
    groups = [f"group-{index}" for index in range(100)]
    namespaces = [f"Namespace-{index}" for index in range(20)]
    query = "&".join(
        [f"groups={group}" for group in groups]
        + [f"namespaces={namespace}" for namespace in namespaces]
    )
    httpx_mock.add_response(
        method="GET",
        url=f"{BASE_URL}/api/v1/policies/alice?{query}",
        json=user_policies_payload(25),
    )
    policies = benchmark(
        client.list_policies,
        "alice",
        groups=groups,
        namespaces=namespaces,
    )
    assert not isinstance(policies, str)


def test_upload_policies(
    benchmark: BenchmarkFixture,
    httpx_mock: HTTPXMock,
    client: TreeTopClient,
    cedar_policies: str,
):
    httpx_mock.add_response(
        method="POST",
        url=f"{BASE_URL}/api/v1/policies",
        json={
            "allow_upload": True,
            "schema_validation_mode": "permissive",
            "policies": metadata_payload(cedar_policies),
            "labels": metadata_payload("{}"),
            "schema": metadata_payload('{"": {}}'),
        },
    )
    configuration = benchmark(client.upload_policies, cedar_policies)
    assert configuration.allow_upload
