"""Benchmarks for request serialization and response parsing."""

from __future__ import annotations

import pytest
from benchmarks.helpers import (
    brief_batch_payload,
    detailed_batch_payload,
    make_request,
    make_requests,
    metadata_payload,
    status_payload,
    user_policies_payload,
    version_response_payload,
)
from pytest_codspeed import BenchmarkFixture

from treetop_client.models import (
    AuthorizeResponseBrief,
    AuthorizeResponseDetailed,
    Metadata,
    StatusResponse,
    User,
    UserPolicies,
    VersionResponse,
    as_api,
)

pytestmark = pytest.mark.benchmark


def test_request_to_api(benchmark: BenchmarkFixture):
    request = make_request()
    payload = benchmark(request.to_api)
    assert payload["id"] == "req-0"


def test_request_to_api_with_context(benchmark: BenchmarkFixture):
    request = make_request(with_context=True)
    payload = benchmark(request.to_api)
    assert "context" in payload


def test_request_build(benchmark: BenchmarkFixture):
    """Construct a request from scratch, including field validation."""
    request = benchmark(make_request, 1, with_context=True)
    assert request.id == "req-1"


def test_user_new_many_groups(benchmark: BenchmarkFixture):
    groups = [f"group-{i}" for i in range(200)]
    user = benchmark(User.new, "alice", ["DNS"], groups)
    assert len(user.groups) == 200


@pytest.mark.parametrize("count", [1, 100])
def test_batch_to_api(benchmark: BenchmarkFixture, count: int):
    requests = make_requests(count, with_context=True)
    payloads = benchmark(lambda: [as_api(req) for req in requests])
    assert len(payloads) == count


@pytest.mark.parametrize("count", [1, 100])
def test_authorize_response_brief_from_api(benchmark: BenchmarkFixture, count: int):
    payload = brief_batch_payload(count)
    response = benchmark(AuthorizeResponseBrief.from_api, payload)
    assert len(response) == count


@pytest.mark.parametrize("count", [1, 50])
def test_authorize_response_detailed_from_api(benchmark: BenchmarkFixture, count: int):
    payload = detailed_batch_payload(count)
    response = benchmark(AuthorizeResponseDetailed.from_api, payload)
    assert len(response) == count


def test_authorize_response_aggregates(benchmark: BenchmarkFixture):
    response = AuthorizeResponseDetailed.from_api(detailed_batch_payload(100))

    def aggregate() -> tuple[int, int, bool]:
        return (
            response.allowed_count(),
            response.denied_count(),
            response.all_allowed(),
        )

    allowed, denied, _ = benchmark(aggregate)
    assert allowed + denied == 100


def test_authorize_response_get_by_id(benchmark: BenchmarkFixture):
    response = AuthorizeResponseBrief.from_api(brief_batch_payload(100))
    result = benchmark(response.get_by_id, "req-99")
    assert result is not None


def test_status_response_from_api(benchmark: BenchmarkFixture):
    payload = status_payload()
    status = benchmark(StatusResponse.from_api, payload)
    assert status.request_context.supported


def test_version_response_from_api(benchmark: BenchmarkFixture):
    payload = version_response_payload()
    version = benchmark(VersionResponse.from_api, payload)
    assert version.version == "v0.0.7"


def test_user_policies_from_api(benchmark: BenchmarkFixture):
    payload = user_policies_payload(25)
    policies = benchmark(UserPolicies.from_api, payload)
    assert len(policies.matches) == 25


def test_metadata_from_api(benchmark: BenchmarkFixture):
    payload = metadata_payload()
    metadata = benchmark(Metadata.from_api, payload)
    assert metadata.entries == 12
