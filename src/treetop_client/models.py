from __future__ import annotations

import enum
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import ClassVar, Generic, TypeAlias, TypeVar, cast, override

_COLON = re.compile(r":")

JsonPrimitive: TypeAlias = str | int | float | bool | None
JsonObject: TypeAlias = dict[str, "JsonValue"]
JsonArray: TypeAlias = list["JsonValue"]
JsonValue: TypeAlias = JsonPrimitive | JsonObject | JsonArray


def _no_colon(value: str, *, field_name: str) -> None:
    if _COLON.search(value):
        raise ValueError(f"{field_name} may not contain ':' - got {value!r}")


def _expect_str(value: JsonValue | None, *, field_name: str) -> str:
    if isinstance(value, str):
        return value
    raise ValueError(f"{field_name} must be a string, got {type(value).__name__}")


def _expect_int(value: JsonValue | None, *, field_name: str) -> int:
    if isinstance(value, int):
        return value
    raise ValueError(f"{field_name} must be an int, got {type(value).__name__}")


def _expect_bool(value: JsonValue | None, *, field_name: str) -> bool:
    if isinstance(value, bool):
        return value
    raise ValueError(f"{field_name} must be a bool, got {type(value).__name__}")


def _expect_dict(value: JsonValue | None, *, field_name: str) -> JsonObject:
    if isinstance(value, dict):
        return value
    raise ValueError(f"{field_name} must be an object, got {type(value).__name__}")


def _expect_optional_str(value: JsonValue | None, *, field_name: str) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    raise ValueError(f"{field_name} must be a string or null, got {type(value).__name__}")


class Endpoint(enum.Enum):
    HEALTH = "/api/v1/health"
    VERSION = "/api/v1/version"
    STATUS = "/api/v1/status"
    POLICIES = "/api/v1/policies"
    SCHEMA = "/api/v1/schema"
    AUTHORIZE = "/api/v1/authorize"


class Decision(str, enum.Enum):
    ALLOW = "Allow"
    DENY = "Deny"


@dataclass(slots=True, frozen=True)
class QualifiedId:
    id: str
    namespace: list[str] = field(default_factory=list)

    def __post_init__(self):
        _no_colon(self.id, field_name="QualifiedId.id")
        for ns in self.namespace:
            _no_colon(ns, field_name="QualifiedId.namespace element")

    def to_api(self) -> JsonObject:
        return {"id": self.id, "namespace": cast(JsonArray, self.namespace)}

    @override
    def __str__(self) -> str:
        if self.namespace:
            return f"{'::'.join(self.namespace)}::{self.id}"
        return self.id


@dataclass(slots=True, frozen=True)
class Group:
    id: QualifiedId

    def to_api(self) -> JsonObject:
        return self.id.to_api()

    @classmethod
    def new(
        cls,
        id: str,
        namespace: list[str] | None = None,
    ) -> Group:
        """Create a new Group with a QualifiedId."""
        return Group(id=QualifiedId(id=id, namespace=namespace or []))

    @override
    def __str__(self) -> str:
        return str(self.id)


@dataclass(slots=True, frozen=True)
class Action:
    id: QualifiedId

    def to_api(self) -> JsonObject:
        return self.id.to_api()

    @classmethod
    def new(
        cls,
        id: str,
        namespace: list[str] | None = None,
    ) -> Action:
        """Create a new Action."""
        return Action(id=QualifiedId(id=id, namespace=namespace or []))

    @override
    def __str__(self) -> str:
        return str(self.id)


@dataclass(slots=True, frozen=True)
class User:
    id: QualifiedId
    groups: list[Group] = field(default_factory=list)

    def to_api(self) -> JsonObject:
        return {
            **self.id.to_api(),
            "groups": cast(JsonArray, [g.to_api() for g in self.groups]),
        }

    @classmethod
    def new(
        cls,
        id: str,
        namespace: list[str] | None = None,
        groups: list[str] | None = None,
    ) -> User:
        """Create a new User.

        Note that this interface assumes that groups share the same namespace as the user.
        If groups are in a different namespace, you should create the object manually.

        Args:
            id: The user ID.
            namespace: Optional namespace for the user ID.
            groups: Optional list of group IDs. If provided, they will be converted to Group objects
                     with the same namespace as the user.
        Returns:
            A User object with the given ID, namespace, and groups.
        """
        return User(
            id=QualifiedId(id=id, namespace=namespace or []),
            groups=[Group.new(id=g, namespace=namespace or []) for g in groups or []],
        )

    @override
    def __str__(self) -> str:
        return str(self.id)


Principal = User | Group


class ResourceAttributeType(str, enum.Enum):
    STRING = "String"
    NUMBER = "Long"
    BOOLEAN = "Boolean"
    IP = "Ip"


@dataclass(slots=True, frozen=True)
class ResourceAttribute:
    type: ResourceAttributeType
    value: str

    def to_api(self) -> JsonObject:
        if self.type == ResourceAttributeType.BOOLEAN:
            # Convert "true"/"false" strings to actual booleans for the API
            val = self.value.lower() == "true"
            return {"type": self.type.value, "value": val}
        elif self.type == ResourceAttributeType.NUMBER:
            # Convert numeric strings to actual floats for the API
            val = float(self.value)
            return {"type": self.type.value, "value": val}

        return {"type": self.type.value, "value": self.value}

    @classmethod
    def new(
        cls, value: str, type: ResourceAttributeType | None = None
    ) -> ResourceAttribute:
        """Create a new ResourceAttribute."""
        if type is None:
            type = ResourceAttributeType.STRING

        return cls(type=type, value=value)


ContextValue: TypeAlias = ResourceAttribute | JsonValue


def _context_to_api(context: dict[str, ContextValue]) -> JsonObject:
    result: JsonObject = {}
    for key, value in context.items():
        result[key] = value.to_api() if isinstance(value, ResourceAttribute) else value
    return result


@dataclass(slots=True, frozen=True)
class Resource:
    kind: str
    id: str
    attrs: dict[str, ResourceAttribute]

    def __post_init__(self):
        _no_colon(self.kind, field_name="Resource.kind")
        if not self.attrs:
            raise ValueError("Resource.attrs cannot be empty")

    def to_api(self) -> JsonObject:
        return {
            "kind": self.kind,
            "id": self.id,
            "attrs": {k: v.to_api() for k, v in self.attrs.items()},
        }

    @classmethod
    def new(cls, kind: str, id: str, attrs: dict[str, ResourceAttribute]) -> Resource:
        """Create a new Resource with kind and attributes."""
        return cls(kind=kind, id=id, attrs=attrs)


@dataclass(slots=True, frozen=True)
class Request:
    principal: Principal
    action: Action
    resource: Resource
    id: str | None = None
    context: dict[str, ContextValue] | None = None

    def to_api(self) -> JsonObject:
        # Principal: User already returns {"User": {...}}.
        # Group should be wrapped as {"Group": {...}} here.
        if isinstance(self.principal, User):
            principal_payload: JsonObject = {"User": self.principal.to_api()}
        else:
            principal_payload = {"Group": self.principal.to_api()}
        result: JsonObject = {
            "principal": principal_payload,
            "action": self.action.to_api(),
            "resource": self.resource.to_api(),
        }
        if self.id is not None:
            result["id"] = self.id
        if self.context is not None:
            result["context"] = _context_to_api(self.context)
        return result


def as_api(obj: Request | JsonObject) -> JsonObject:
    return obj.to_api() if isinstance(obj, Request) else obj


@dataclass(slots=True, frozen=True)
class AuthorizedResponseBrief:
    decision: Decision

    _KEYS: ClassVar[tuple[str, ...]] = ("decision",)

    @classmethod
    def from_api(cls, data: JsonObject) -> AuthorizedResponseBrief:
        dec = data.get("decision", data.get("desicion"))
        if dec is None:
            raise KeyError("decision")
        decision = _expect_str(dec, field_name="decision")
        return cls(decision=Decision(decision))

    def is_allowed(self) -> bool:
        return self.decision == Decision.ALLOW

    def is_denied(self) -> bool:
        return self.decision == Decision.DENY


@dataclass(slots=True, frozen=True)
class PermitPolicy:
    literal: str
    json: JsonObject
    annotation_id: str | None = None
    cedar_id: str | None = None

    @classmethod
    def from_api(cls, data: JsonObject) -> PermitPolicy:
        literal = _expect_str(data.get("literal"), field_name="policy literal")
        json_blob = _expect_dict(data.get("json"), field_name="policy json")
        annotation_id = _expect_optional_str(
            data.get("annotation_id"), field_name="annotation_id"
        )
        cedar_id = _expect_optional_str(data.get("cedar_id"), field_name="cedar_id")
        return cls(
            literal=literal,
            json=json_blob,
            annotation_id=annotation_id,
            cedar_id=cedar_id,
        )


@dataclass(slots=True, frozen=True)
class PolicyVersion:
    hash: str
    loaded_at: datetime

    @classmethod
    def from_api(cls, data: JsonObject) -> PolicyVersion:
        hash_value = _expect_str(data.get("hash"), field_name="version hash")
        loaded_at_value = _expect_str(data.get("loaded_at"), field_name="version loaded_at")
        return cls(
            hash=hash_value,
            loaded_at=datetime.fromisoformat(loaded_at_value.replace("Z", "+00:00")),
        )


@dataclass(slots=True, frozen=True)
class CoreVersion:
    version: str
    cedar: str

    @classmethod
    def from_api(cls, data: JsonObject) -> CoreVersion:
        return cls(
            version=_expect_str(data.get("version"), field_name="core version"),
            cedar=_expect_str(data.get("cedar"), field_name="core cedar"),
        )


@dataclass(slots=True, frozen=True)
class VersionResponse:
    version: str
    core: CoreVersion
    policies: PolicyVersion
    schema: PolicyVersion | None = None

    @classmethod
    def from_api(cls, data: JsonObject) -> VersionResponse:
        schema_blob = data.get("schema")
        return cls(
            version=_expect_str(data.get("version"), field_name="version"),
            core=CoreVersion.from_api(_expect_dict(data.get("core"), field_name="core")),
            policies=PolicyVersion.from_api(
                _expect_dict(data.get("policies"), field_name="policies")
            ),
            schema=PolicyVersion.from_api(
                _expect_dict(schema_blob, field_name="schema")
            )
            if schema_blob is not None
            else None,
        )


@dataclass(slots=True, frozen=True)
class Metadata:
    timestamp: datetime
    sha256: str
    size: int
    source: JsonObject | None
    refresh_frequency: int | None
    entries: int
    content: str | None = None

    @classmethod
    def from_api(cls, data: JsonObject) -> Metadata:
        source_blob = data.get("source")
        refresh_frequency = data.get("refresh_frequency")
        return cls(
            timestamp=datetime.fromisoformat(
                _expect_str(data.get("timestamp"), field_name="timestamp").replace(
                    "Z", "+00:00"
                )
            ),
            sha256=_expect_str(data.get("sha256"), field_name="sha256"),
            size=_expect_int(data.get("size"), field_name="size"),
            source=_expect_dict(source_blob, field_name="source")
            if source_blob is not None
            else None,
            refresh_frequency=_expect_int(
                refresh_frequency, field_name="refresh_frequency"
            )
            if refresh_frequency is not None
            else None,
            entries=_expect_int(data.get("entries"), field_name="entries"),
            content=_expect_optional_str(data.get("content"), field_name="content"),
        )


@dataclass(slots=True, frozen=True)
class PolicyConfiguration:
    allow_upload: bool | None
    schema_validation_mode: str | None
    policies: Metadata | None
    labels: Metadata | None
    schema: Metadata | None

    @classmethod
    def from_api(cls, data: JsonObject) -> PolicyConfiguration:
        allow_upload = data.get("allow_upload")
        schema_validation_mode = data.get("schema_validation_mode")
        policies = data.get("policies")
        labels = data.get("labels")
        schema = data.get("schema")
        return cls(
            allow_upload=_expect_bool(allow_upload, field_name="allow_upload")
            if allow_upload is not None
            else None,
            schema_validation_mode=_expect_str(
                schema_validation_mode, field_name="schema_validation_mode"
            )
            if schema_validation_mode is not None
            else None,
            policies=Metadata.from_api(_expect_dict(policies, field_name="policies"))
            if policies is not None
            else None,
            labels=Metadata.from_api(_expect_dict(labels, field_name="labels"))
            if labels is not None
            else None,
            schema=Metadata.from_api(_expect_dict(schema, field_name="schema"))
            if schema is not None
            else None,
        )


@dataclass(slots=True, frozen=True)
class ParallelConfiguration:
    cpu_count: int
    workers: int
    rayon_threads: int
    par_threshold: int
    allow_parallel: bool

    @classmethod
    def from_api(cls, data: JsonObject) -> ParallelConfiguration:
        return cls(
            cpu_count=_expect_int(data.get("cpu_count"), field_name="cpu_count"),
            workers=_expect_int(data.get("workers"), field_name="workers"),
            rayon_threads=_expect_int(
                data.get("rayon_threads"), field_name="rayon_threads"
            ),
            par_threshold=_expect_int(
                data.get("par_threshold"), field_name="par_threshold"
            ),
            allow_parallel=_expect_bool(
                data.get("allow_parallel"), field_name="allow_parallel"
            ),
        )


@dataclass(slots=True, frozen=True)
class RequestLimits:
    max_context_bytes: int
    max_context_depth: int
    max_context_keys: int

    @classmethod
    def from_api(cls, data: JsonObject) -> RequestLimits:
        return cls(
            max_context_bytes=_expect_int(
                data.get("max_context_bytes"), field_name="max_context_bytes"
            ),
            max_context_depth=_expect_int(
                data.get("max_context_depth"), field_name="max_context_depth"
            ),
            max_context_keys=_expect_int(
                data.get("max_context_keys"), field_name="max_context_keys"
            ),
        )


@dataclass(slots=True, frozen=True)
class RequestContextStatus:
    supported: bool
    schema_backed: bool
    fallback_reason: str | None

    @classmethod
    def from_api(cls, data: JsonObject) -> RequestContextStatus:
        return cls(
            supported=_expect_bool(data.get("supported"), field_name="supported"),
            schema_backed=_expect_bool(
                data.get("schema_backed"), field_name="schema_backed"
            ),
            fallback_reason=_expect_optional_str(
                data.get("fallback_reason"), field_name="fallback_reason"
            ),
        )


@dataclass(slots=True, frozen=True)
class StatusResponse:
    policy_configuration: PolicyConfiguration
    parallel_configuration: ParallelConfiguration
    request_limits: RequestLimits
    request_context: RequestContextStatus

    @classmethod
    def from_api(cls, data: JsonObject) -> StatusResponse:
        return cls(
            policy_configuration=PolicyConfiguration.from_api(
                _expect_dict(
                    data.get("policy_configuration"), field_name="policy_configuration"
                )
            ),
            parallel_configuration=ParallelConfiguration.from_api(
                _expect_dict(
                    data.get("parallel_configuration"),
                    field_name="parallel_configuration",
                )
            ),
            request_limits=RequestLimits.from_api(
                _expect_dict(data.get("request_limits"), field_name="request_limits")
            ),
            request_context=RequestContextStatus.from_api(
                _expect_dict(data.get("request_context"), field_name="request_context")
            ),
        )


@dataclass(slots=True, frozen=True)
class AuthorizedResponseDetailed:
    # Either decision == Decision.DENY (empty policies list) or Decision.ALLOW with policies
    decision: Decision
    policies: list[PermitPolicy]
    version: PolicyVersion | None = None

    @classmethod
    def from_api(cls, data: JsonObject) -> AuthorizedResponseDetailed:
        def parse_version(blob: JsonValue | None) -> PolicyVersion | None:
            if blob is None:
                return None
            return PolicyVersion.from_api(_expect_dict(blob, field_name="version"))

        def parse_policies(blob: JsonValue, *, context: str) -> list[PermitPolicy]:
            if isinstance(blob, list):
                if not blob:
                    raise ValueError(f"{context} has empty policy list: {data!r}")
                policies: list[PermitPolicy] = []
                for entry in blob:
                    policy_dict = _expect_dict(entry, field_name="policy")
                    policies.append(PermitPolicy.from_api(policy_dict))
                return policies
            if isinstance(blob, dict):
                return [PermitPolicy.from_api(blob)]
            raise ValueError(f"{context} has malformed policy: {blob!r}")

        dec = data.get("decision", data.get("desicion"))  # Temporary typo support
        if dec is None:
            raise KeyError("decision")

        if isinstance(dec, str):
            # 1) Is it a simple Deny (old format)?
            if dec == Decision.DENY.value:
                version = parse_version(data.get("version"))
                return cls(decision=Decision.DENY, policies=[], version=version)

            # 1b) Is it a simple Allow with top-level policy/version?
            if dec == Decision.ALLOW.value:
                if "policy" not in data:
                    raise ValueError(f"Allow decision missing policy: {data!r}")
                policies = parse_policies(data["policy"], context="Allow decision")
                version = parse_version(data.get("version"))
                return cls(
                    decision=Decision.ALLOW,
                    policies=policies,
                    version=version,
                )
            raise ValueError(f"Unrecognized decision value: {dec!r}")

        # 2) Is it a Deny with version (new format)?
        if isinstance(dec, dict) and Decision.DENY.value in dec:
            deny_dict = _expect_dict(dec[Decision.DENY.value], field_name="deny decision")
            version = parse_version(deny_dict.get("version"))
            return cls(
                decision=Decision.DENY,
                policies=[],
                version=version,
            )

        # 3) If it's a dict with an "Allow" key, pull the policies and optional version
        if isinstance(dec, dict) and Decision.ALLOW.value in dec:
            allow_dict = _expect_dict(dec[Decision.ALLOW.value], field_name="allow decision")

            if "policy" not in allow_dict:
                raise ValueError(f"Allow decision missing policy: {dec!r}")

            policies = parse_policies(allow_dict["policy"], context="Allow decision")
            version = parse_version(allow_dict.get("version"))
            return cls(
                decision=Decision.ALLOW,
                policies=policies,
                version=version,
            )

        # 4) Otherwise it's malformed
        raise ValueError(f"Unrecognized decision shape: {dec!r}")

    def is_allowed(self) -> bool:
        return self.decision == Decision.ALLOW

    def is_denied(self) -> bool:
        return self.decision == Decision.DENY

    def __iter__(self):
        """Iterate over matching policies."""
        return iter(self.policies)

    def __len__(self) -> int:
        """Return the number of matching policies."""
        return len(self.policies)

    def __getitem__(self, index: int) -> PermitPolicy:
        """Return a matching policy by index."""
        return self.policies[index]

    def version_hash(self) -> str | None:
        """Return the policy version hash if available, otherwise None."""
        return self.version.hash if self.version else None

    def version_loaded_at(self) -> datetime | None:
        """Return the policy version loaded_at timestamp if available, otherwise None."""
        return self.version.loaded_at if self.version else None


# Generic type variables for authorization results and responses
ResultT = TypeVar(
    "ResultT", bound="AuthorizedResponseBrief | AuthorizedResponseDetailed"
)
T = TypeVar("T", bound="AuthorizeResultBrief | AuthorizeResultDetailed")


@dataclass(slots=True, frozen=True)
class AuthorizeResultBase(Generic[ResultT]):
    """Base class for a single result from the authorize endpoint."""

    index: int
    id: str | None
    status: str
    result: ResultT | None = None
    error: str | None = None

    def is_success(self) -> bool:
        """Check if this result is successful."""
        return self.status == "success"

    def is_failed(self) -> bool:
        """Check if this result failed."""
        return self.status == "failed"

    def get_decision(self) -> Decision | None:
        """Get the decision if successful, otherwise None."""
        return self.result.decision if self.result is not None else None

    def is_allowed(self) -> bool:
        """Check if the decision is Allow."""
        return self.result.is_allowed() if self.result is not None else False

    def is_denied(self) -> bool:
        """Check if the decision is Deny."""
        return self.result.is_denied() if self.result is not None else False


@dataclass(slots=True, frozen=True)
class AuthorizeResultBrief(AuthorizeResultBase[AuthorizedResponseBrief]):
    """A single result from the authorize endpoint (brief detail level)."""

    @classmethod
    def from_api(cls, data: JsonObject) -> AuthorizeResultBrief:
        index = _expect_int(data.get("index"), field_name="index")
        result_id = _expect_optional_str(data.get("id"), field_name="id")
        status = _expect_str(data.get("status"), field_name="status")
        error = _expect_optional_str(data.get("error"), field_name="error")

        result = None
        if status == "success" and "result" in data:
            result_blob = _expect_dict(data.get("result"), field_name="result")
            result = AuthorizedResponseBrief.from_api(result_blob)

        return cls(index=index, id=result_id, status=status, result=result, error=error)


@dataclass(slots=True, frozen=True)
class AuthorizeResultDetailed(AuthorizeResultBase[AuthorizedResponseDetailed]):
    """A single result from the authorize endpoint (detailed level)."""

    @classmethod
    def from_api(cls, data: JsonObject) -> AuthorizeResultDetailed:
        index = _expect_int(data.get("index"), field_name="index")
        result_id = _expect_optional_str(data.get("id"), field_name="id")
        status = _expect_str(data.get("status"), field_name="status")
        error = _expect_optional_str(data.get("error"), field_name="error")

        result = None
        if status == "success" and "result" in data:
            result_blob = _expect_dict(data.get("result"), field_name="result")
            result = AuthorizedResponseDetailed.from_api(result_blob)

        return cls(index=index, id=result_id, status=status, result=result, error=error)

    @property
    def policies(self) -> list[PermitPolicy]:
        """Return matching policies. Empty list for failed or Deny results."""
        return self.result.policies if self.result is not None else []

    def __iter__(self):
        """Iterate over matching policies."""
        return iter(self.policies)

    def __len__(self) -> int:
        """Return the number of matching policies."""
        return len(self.policies)

    def __getitem__(self, index: int) -> PermitPolicy:
        """Return a matching policy by index."""
        return self.policies[index]

    def version_hash(self) -> str | None:
        """Return the policy version hash if available, otherwise None."""
        return self.result.version_hash() if self.result is not None else None

    def version_loaded_at(self) -> datetime | None:
        """Return the policy version loaded_at timestamp if available, otherwise None."""
        return self.result.version_loaded_at() if self.result is not None else None


@dataclass(slots=True, frozen=True)
class AuthorizeResponseBase(Generic[T]):
    """Base class for batch responses from the authorize endpoint."""

    results: list[T]
    version: PolicyVersion
    successful: int
    failed: int

    def __iter__(self):
        """Iterate over results."""
        return iter(self.results)

    def __len__(self):
        """Return the number of results."""
        return len(self.results)

    def __getitem__(self, index: int) -> T:
        """Get result by index."""
        return self.results[index]

    def get_by_id(self, request_id: str) -> T | None:
        """Get result by client-provided request ID."""
        for result in self.results:
            if result.id == request_id:
                return result
        return None

    def denied_count(self) -> int:
        """Return the number of denied results."""
        return sum(1 for r in self.results if r.is_success() and r.is_denied())

    def allowed_count(self) -> int:
        """Return the number of allowed results."""
        return sum(1 for r in self.results if r.is_success() and r.is_allowed())

    def all_allowed(self) -> bool:
        """Check if all successful results are allowed."""
        return all(r.is_allowed() for r in self.results if r.is_success())


@dataclass(slots=True, frozen=True)
class AuthorizeResponseBrief(AuthorizeResponseBase[AuthorizeResultBrief]):
    """Batch response from the authorize endpoint (brief detail level)."""

    @classmethod
    def from_api(cls, data: JsonObject) -> AuthorizeResponseBrief:
        results_blob = data.get("results")
        results: list[AuthorizeResultBrief] = []
        if isinstance(results_blob, list):
            for entry in results_blob:
                result_dict = _expect_dict(entry, field_name="result entry")
                results.append(AuthorizeResultBrief.from_api(result_dict))
        version = PolicyVersion.from_api(_expect_dict(data.get("version"), field_name="version"))
        successful = _expect_int(data.get("successful", 0), field_name="successful")
        failed = _expect_int(data.get("failed", 0), field_name="failed")

        return cls(
            results=results, version=version, successful=successful, failed=failed
        )


@dataclass(slots=True, frozen=True)
class AuthorizeResponseDetailed(AuthorizeResponseBase[AuthorizeResultDetailed]):
    """Batch response from the authorize endpoint (detailed level)."""

    @classmethod
    def from_api(cls, data: JsonObject) -> AuthorizeResponseDetailed:
        results_blob = data.get("results")
        results: list[AuthorizeResultDetailed] = []
        if isinstance(results_blob, list):
            for entry in results_blob:
                result_dict = _expect_dict(entry, field_name="result entry")
                results.append(AuthorizeResultDetailed.from_api(result_dict))
        version = PolicyVersion.from_api(_expect_dict(data.get("version"), field_name="version"))
        successful = _expect_int(data.get("successful", 0), field_name="successful")
        failed = _expect_int(data.get("failed", 0), field_name="failed")

        return cls(
            results=results, version=version, successful=successful, failed=failed
        )
