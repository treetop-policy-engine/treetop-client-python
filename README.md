# TreeTop Client

[![CodSpeed](https://img.shields.io/endpoint?url=https://codspeed.io/badge.json)](https://app.codspeed.io/terjekv/treetop-client-python?utm_source=badge)

Dataclass-based HTTPX client for the [Treetop REST API](https://github.com/terjekv/treetop-rest).
Python ≥ 3.12, zero runtime deps beyond HTTPX.

## Features

- **Unified Batch Authorization Endpoint**: Process multiple authorization requests in a single API call
- **Detail Levels**: Control response verbosity (brief vs. detailed with policy information)
- **Backward Compatible**: Existing code using `check()` and `check_detailed()` continues to work seamlessly
- **Full Async Support**: Async/await support for all API methods
- **Type Safe**: Fully type-hinted dataclasses for requests and responses
- **Version Tracking**: Access policy version information (hash and loaded_at timestamp)
- **v0.0.7 Management API**: Health, version, status, policy, and schema endpoints
- **Request Context**: Pass request-scoped Cedar context attributes during authorization

## Basic Usage (Single Request)

```python
from treetop_client.client import TreeTopClient
from treetop_client.models import (
    Action,
    Decision,
    Request,
    Resource,
    User,
    ResourceAttribute,
    ResourceAttributeType,
)

client = TreeTopClient(base_url=f"http://localhost:{PORT}")

attrs = {}
attrs["ip"] = ResourceAttribute.new("10.0.0.1", ResourceAttributeType.IP)
attrs["name"] = ResourceAttribute.new("myhost.example.com", ResourceAttributeType.STRING)

req = Request(
    principal=User.new("myuser", ["mynamespace"], ["mygroup"]),
    action=Action.new("myaction", ["mynamespace"]),
    resource=Resource.new("Host", id="myhost", attrs=attrs)
)

# Use the check method (wraps batch API internally)
resp = client.check(req)

# Use is_allowed() / is_denied() methods
assert resp.is_allowed()
# Or compare with the Decision enum
assert resp.decision == Decision.ALLOW
```

## Batch Authorization

Send multiple authorization requests in a single API call for better performance:

```python
from treetop_client.client import TreeTopClient
from treetop_client.models import (
    Action,
    Request,
    Resource,
    User,
    ResourceAttribute,
    ResourceAttributeType,
)

client = TreeTopClient(base_url=f"http://localhost:{PORT}")

# Create multiple requests
requests = []
for i in range(3):
    attrs = {"ip": ResourceAttribute.new(f"10.0.0.{i}", ResourceAttributeType.IP)}
    req = Request(
        id=f"request-{i}",  # Optional client-provided correlation ID
        principal=User.new(f"user{i}", ["mynamespace"]),
        action=Action.new("view", ["mynamespace"]),
        resource=Resource.new("Host", id=f"host{i}", attrs=attrs)
    )
    requests.append(req)

# Process all requests in one call (brief detail level)
response = client.authorize(requests)

# Access results
print(f"Successful: {response.successful}, Failed: {response.failed}")
for result in response:
    print(f"Request {result.id}: {result.get_decision()}")

# Look up specific result by ID
result = response.get_by_id("request-0")
if result and result.is_allowed():
    print("Request 0 was allowed!")
```

## Detailed Responses (With Policy Information)

Retrieve matching policy information in your responses:

```python
from treetop_client.client import TreeTopClient
from treetop_client.models import (
    Action,
    Decision,
    Request,
    Resource,
    User,
    ResourceAttribute,
    ResourceAttributeType,
)

client = TreeTopClient(base_url=f"http://localhost:{PORT}")

attrs = {}
attrs["ip"] = ResourceAttribute.new("10.0.0.1", ResourceAttributeType.IP)
attrs["name"] = ResourceAttribute.new("myhost.example.com", ResourceAttributeType.STRING)

req = Request(
    principal=User.new("myuser", ["mynamespace"], ["mygroup"]),
    action=Action.new("myaction", ["mynamespace"]),
    resource=Resource.new("Host", id="myhost", attrs=attrs)
)

# Get detailed response with policy information
resp = client.check_detailed(req)
assert resp.is_allowed()
assert resp.decision == Decision.ALLOW

# Access policy information (if allowed)
# The server returns all matching policies as PermitPolicy objects
policies = list(resp)  # or resp.policies
if policies:
    print(f"First matching policy: {policies[0].literal}")
    print(f"Total matching policies: {len(policies)}")
    print(f"Annotation IDs: {[p.annotation_id for p in policies if p.annotation_id]}")
    print(f"Cedar IDs: {[p.cedar_id for p in policies if p.cedar_id]}")

# Access version information
hash = resp.version_hash()           # SHA-256 hash or None
loaded_at = resp.version_loaded_at() # datetime or None
```

## Batch Detailed Responses

Combine batch processing with detailed responses:

```python
# Create multiple requests
requests = [req1, req2, req3]

# Get batch response with detailed policy information
response = client.authorize_detailed(requests)

for result in response:
    if result.is_success() and result.is_allowed():
        print(f"Decision: {result.get_decision()}")
        
        # Access all matching policies for this result
        policies = result.policies
        if policies:
            print(f"First matching policy: {policies[0].literal}")
            print(f"Total matching policies: {len(policies)}")
        
        print(f"Version hash: {result.version_hash()}")
```

## Async API

All methods have async versions:

```python
# Single request (async)
resp = await client.acheck(req)

# Batch requests (async)
response = await client.aauthorize(requests)

# Detailed batch requests (async)
response = await client.aauthorize_detailed(requests)
```

## Correlation ID

Track requests across services using correlation IDs:

```python
from treetop_client.client import TreeTopClient
from treetop_client.models import (
    Action,
    Request,
    Resource,
    User,
    ResourceAttribute,
    ResourceAttributeType,
)

client = TreeTopClient(base_url=f"http://localhost:{PORT}")

attrs = {}
attrs["ip"] = ResourceAttribute.new("10.0.0.1", ResourceAttributeType.IP)
attrs["name"] = ResourceAttribute.new("myhost.example.com", ResourceAttributeType.STRING)

req = Request(
    principal=User.new("myuser", ["mynamespace"], ["mygroup"]),
    action=Action.new("myaction", ["mynamespace"]),
    resource=Resource.new("Host", id="myhost", attrs=attrs)
)

# Pass correlation ID for tracing
resp = client.check(req, correlation_id="my-correlation-id")
response = client.authorize([req1, req2], correlation_id="batch-trace-id")
```

## Request Context

Pass request-scoped Cedar context values with the same attribute encoding used for resources:

```python
req = Request(
    id="prod-check",
    principal=User.new("alice", ["DNS"], ["admins"]),
    action=Action.new("create_host", ["DNS"]),
    resource=Resource.new(
        "Host",
        id="hostname.example.com",
        attrs={"name": ResourceAttribute.new("hostname.example.com")}
    ),
    context={
        "env": "prod",
        "approved": True,
        "retry_count": 3,
        "roles": ["operator", "reviewer"],
        "ticket": {"type": "String", "value": "CHG-123"},
    },
)
```

Strings, booleans, integers, and lists are encoded as Cedar `String`, `Bool`,
`Long`, and `Set` values. Typed dictionaries may use `String`, `Bool`, `Long`,
`Ip`, or `Set`; invalid tags, nulls, and floating-point numbers raise
`ValueError` before a request is sent.

## Server Metadata and Uploads

```python
assert client.health()

version = client.version()
print(version.version, version.core.version, version.policies.hash)

status = client.status()
print(status.request_context.supported)

policies = client.get_policies()
raw_policies = client.get_policies(raw=True)

schema = client.get_schema()
raw_schema = client.get_schema(raw=True)

client.upload_policies("permit (...);", upload_token="server-token")
client.upload_schema('{"": {}}', upload_token="server-token", as_json=True)
```

## Notes

- `User` namespace and groups are optional; they default to the root namespace if not provided
- `Action` namespace is optional; it defaults to the root namespace if not provided
- Each `Request` can optionally have an `id` field for client-provided correlation IDs in batch operations
- Each `Request` can optionally include a `context` object for v0.0.7 request-context evaluation

## Development

This project uses [uv](https://docs.astral.sh/uv/) for dependency management.

```bash
# Install dependencies (including dev dependencies)
uv sync --extra dev

# Run tests
uv run pytest

# Run integration tests (requires Docker & Docker Compose)
uv run pytest -m integration

# Add a new dependency
uv add package-name

# Add a dev dependency
uv add --dev package-name
```

### Benchmarks

Performance benchmarks live in `benchmarks/` and are measured continuously by
[CodSpeed](https://codspeed.io) on every push and pull request. They cover request
serialization, response parsing and the client code path against a mocked HTTP
transport, so no server is required.

```bash
# Run the benchmarks as plain tests (fast smoke check)
uv run pytest benchmarks

# Measure them locally with the CodSpeed CLI
codspeed run --mode simulation -- uv run pytest benchmarks --codspeed
```
