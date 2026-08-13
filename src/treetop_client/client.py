from __future__ import annotations

import contextlib
from collections.abc import Sequence
from typing import Final, cast
from urllib.parse import quote

import httpx

from treetop_client.models import (
    AuthorizedResponseBrief,
    AuthorizedResponseDetailed,
    AuthorizeResponseBrief,
    AuthorizeResponseDetailed,
    Decision,
    Endpoint,
    JsonArray,
    JsonObject,
    JsonValue,
    Metadata,
    PolicyConfiguration,
    Request,
    StatusResponse,
    UserPolicies,
    VersionResponse,
    as_api,
)

_DEFAULT_LIMITS: Final = httpx.Limits(
    max_connections=100,
    max_keepalive_connections=20,
)


class TreeTopClient:
    def __init__(
        self,
        base_url: str = "http://localhost:9999",
        *,
        limits: httpx.Limits | None = None,
        timeout: float | httpx.Timeout = 5.0,
        verify: bool | str = True,
    ):
        self._sync_client: httpx.Client = httpx.Client(
            base_url=base_url,
            limits=limits or _DEFAULT_LIMITS,
            timeout=timeout,
            verify=verify,
        )
        self._async_client: httpx.AsyncClient = httpx.AsyncClient(
            base_url=base_url,
            limits=limits or _DEFAULT_LIMITS,
            timeout=timeout,
            verify=verify,
        )

    def _build_headers(
        self,
        correlation_id: str | None = None,
        upload_token: str | None = None,
        content_type: str | None = None,
    ) -> dict[str, str] | None:
        """Build headers for the request, including a correlation ID if provided."""
        headers: dict[str, str] = {}
        if correlation_id:
            headers["X-Correlation-ID"] = correlation_id
        if upload_token:
            headers["X-Upload-Token"] = upload_token
        if content_type:
            headers["Content-Type"] = content_type
        if not headers:
            return None
        return headers

    def _sync_post(
        self,
        url: str,
        json_body: JsonObject,
        correlation_id: str | None = None,
        params: dict[str, str] | httpx.QueryParams | None = None,
    ) -> httpx.Response:
        """Synchronous POST request to the given URL with JSON body and optional correlation ID."""
        return self._sync_client.post(
            url,
            json=json_body,
            headers=self._build_headers(correlation_id),
            params=params,
        )

    def _sync_get(
        self,
        url: str,
        correlation_id: str | None = None,
        params: dict[str, str] | httpx.QueryParams | None = None,
    ) -> httpx.Response:
        return self._sync_client.get(
            url,
            headers=self._build_headers(correlation_id),
            params=params,
        )

    def _sync_upload(
        self,
        url: str,
        body: str,
        field_name: str,
        upload_token: str | None = None,
        *,
        as_json: bool = False,
    ) -> httpx.Response:
        if as_json:
            return self._sync_client.post(
                url,
                json={field_name: body},
                headers=self._build_headers(upload_token=upload_token),
            )
        return self._sync_client.post(
            url,
            content=body,
            headers=self._build_headers(
                upload_token=upload_token, content_type="text/plain"
            ),
        )

    async def _async_post(
        self,
        url: str,
        json_body: JsonObject,
        correlation_id: str | None = None,
        params: dict[str, str] | httpx.QueryParams | None = None,
    ) -> httpx.Response:
        """Asynchronous POST request to the given URL with JSON body and optional correlation ID."""
        return await self._async_client.post(
            url,
            json=json_body,
            headers=self._build_headers(correlation_id),
            params=params,
        )

    async def _async_get(
        self,
        url: str,
        correlation_id: str | None = None,
        params: dict[str, str] | httpx.QueryParams | None = None,
    ) -> httpx.Response:
        return await self._async_client.get(
            url,
            headers=self._build_headers(correlation_id),
            params=params,
        )

    async def _async_upload(
        self,
        url: str,
        body: str,
        field_name: str,
        upload_token: str | None = None,
        *,
        as_json: bool = False,
    ) -> httpx.Response:
        if as_json:
            return await self._async_client.post(
                url,
                json={field_name: body},
                headers=self._build_headers(upload_token=upload_token),
            )
        return await self._async_client.post(
            url,
            content=body,
            headers=self._build_headers(
                upload_token=upload_token, content_type="text/plain"
            ),
        )

    def livez(self) -> bool:
        """Return True when the v0.0.11 liveness probe succeeds."""
        return self._sync_get(Endpoint.LIVEZ.value).raise_for_status().is_success

    async def alivez(self) -> bool:
        """Return True when the v0.0.11 liveness probe succeeds."""
        resp = await self._async_get(Endpoint.LIVEZ.value)
        return resp.raise_for_status().is_success

    def readyz(self) -> bool:
        """Return readiness, treating the probe's expected 503 as False."""
        resp = self._sync_get(Endpoint.READYZ.value)
        if resp.status_code == 503:
            return False
        return resp.raise_for_status().is_success

    async def areadyz(self) -> bool:
        """Return readiness, treating the probe's expected 503 as False."""
        resp = await self._async_get(Endpoint.READYZ.value)
        if resp.status_code == 503:
            return False
        return resp.raise_for_status().is_success

    def openapi(self) -> JsonObject:
        """Fetch the server's canonical generated OpenAPI document."""
        resp = self._sync_get(Endpoint.OPENAPI.value)
        return cast(JsonObject, resp.raise_for_status().json())

    async def aopenapi(self) -> JsonObject:
        """Fetch the server's canonical generated OpenAPI document."""
        resp = await self._async_get(Endpoint.OPENAPI.value)
        return cast(JsonObject, resp.raise_for_status().json())

    def metrics(self) -> str:
        """Fetch the server's Prometheus metrics exposition."""
        return self._sync_get(Endpoint.METRICS.value).raise_for_status().text

    async def ametrics(self) -> str:
        """Fetch the server's Prometheus metrics exposition."""
        resp = await self._async_get(Endpoint.METRICS.value)
        return resp.raise_for_status().text

    def health(self) -> bool:
        """Return True when the server health endpoint responds with a 2xx status."""
        return self._sync_get(Endpoint.HEALTH.value).raise_for_status().is_success

    async def ahealth(self) -> bool:
        """Return True when the server health endpoint responds with a 2xx status."""
        resp = await self._async_get(Endpoint.HEALTH.value)
        return resp.raise_for_status().is_success

    def version(self) -> VersionResponse:
        """Fetch server, core, policy, and schema version metadata."""
        resp = self._sync_get(Endpoint.VERSION.value)
        return VersionResponse.from_api(cast(JsonObject, resp.raise_for_status().json()))

    async def aversion(self) -> VersionResponse:
        """Fetch server, core, policy, and schema version metadata."""
        resp = await self._async_get(Endpoint.VERSION.value)
        return VersionResponse.from_api(cast(JsonObject, resp.raise_for_status().json()))

    def status(self) -> StatusResponse:
        """Fetch server status and policy configuration metadata."""
        resp = self._sync_get(Endpoint.STATUS.value)
        return StatusResponse.from_api(cast(JsonObject, resp.raise_for_status().json()))

    async def astatus(self) -> StatusResponse:
        """Fetch server status and policy configuration metadata."""
        resp = await self._async_get(Endpoint.STATUS.value)
        return StatusResponse.from_api(cast(JsonObject, resp.raise_for_status().json()))

    def get_policies(self, *, raw: bool = False) -> Metadata | str:
        """Download policies as metadata JSON or raw Cedar DSL."""
        resp = self._sync_get(
            Endpoint.POLICIES.value,
            params={"format": "raw"} if raw else None,
        ).raise_for_status()
        if raw:
            return resp.text
        data = cast(JsonObject, resp.json())
        return Metadata.from_api(cast(JsonObject, data["policies"]))

    async def aget_policies(self, *, raw: bool = False) -> Metadata | str:
        """Download policies as metadata JSON or raw Cedar DSL."""
        resp = (
            await self._async_get(
                Endpoint.POLICIES.value,
                params={"format": "raw"} if raw else None,
            )
        ).raise_for_status()
        if raw:
            return resp.text
        data = cast(JsonObject, resp.json())
        return Metadata.from_api(cast(JsonObject, data["policies"]))

    def upload_policies(
        self,
        policies: str,
        *,
        upload_token: str | None = None,
        as_json: bool = False,
    ) -> PolicyConfiguration:
        """Upload replacement Cedar policies."""
        resp = self._sync_upload(
            Endpoint.POLICIES.value,
            policies,
            "policies",
            upload_token,
            as_json=as_json,
        )
        return PolicyConfiguration.from_api(
            cast(JsonObject, resp.raise_for_status().json())
        )

    async def aupload_policies(
        self,
        policies: str,
        *,
        upload_token: str | None = None,
        as_json: bool = False,
    ) -> PolicyConfiguration:
        """Upload replacement Cedar policies."""
        resp = await self._async_upload(
            Endpoint.POLICIES.value,
            policies,
            "policies",
            upload_token,
            as_json=as_json,
        )
        return PolicyConfiguration.from_api(
            cast(JsonObject, resp.raise_for_status().json())
        )

    def get_schema(self, *, raw: bool = False) -> Metadata | str:
        """Download schema as metadata JSON or raw Cedar schema JSON."""
        resp = self._sync_get(
            Endpoint.SCHEMA.value,
            params={"format": "raw"} if raw else None,
        ).raise_for_status()
        if raw:
            return resp.text
        data = cast(JsonObject, resp.json())
        return Metadata.from_api(cast(JsonObject, data["schema"]))

    async def aget_schema(self, *, raw: bool = False) -> Metadata | str:
        """Download schema as metadata JSON or raw Cedar schema JSON."""
        resp = (
            await self._async_get(
                Endpoint.SCHEMA.value,
                params={"format": "raw"} if raw else None,
            )
        ).raise_for_status()
        if raw:
            return resp.text
        data = cast(JsonObject, resp.json())
        return Metadata.from_api(cast(JsonObject, data["schema"]))

    def upload_schema(
        self,
        schema: str,
        *,
        upload_token: str | None = None,
        as_json: bool = False,
    ) -> PolicyConfiguration:
        """Upload replacement Cedar schema JSON."""
        resp = self._sync_upload(
            Endpoint.SCHEMA.value,
            schema,
            "schema",
            upload_token,
            as_json=as_json,
        )
        return PolicyConfiguration.from_api(
            cast(JsonObject, resp.raise_for_status().json())
        )

    async def aupload_schema(
        self,
        schema: str,
        *,
        upload_token: str | None = None,
        as_json: bool = False,
    ) -> PolicyConfiguration:
        """Upload replacement Cedar schema JSON."""
        resp = await self._async_upload(
            Endpoint.SCHEMA.value,
            schema,
            "schema",
            upload_token,
            as_json=as_json,
        )
        return PolicyConfiguration.from_api(
            cast(JsonObject, resp.raise_for_status().json())
        )

    def list_policies(
        self,
        user: str,
        *,
        groups: Sequence[str] = (),
        namespaces: Sequence[str] = (),
        raw: bool = False,
    ) -> UserPolicies | str:
        """List policies matching a user, optionally as raw Cedar DSL."""
        params = httpx.QueryParams()
        for group in groups:
            params = params.add("groups", group)
        for namespace in namespaces:
            params = params.add("namespaces", namespace)
        if raw:
            params = params.add("format", "raw")
        resp = self._sync_get(
            f"{Endpoint.POLICIES.value}/{quote(user, safe='')}",
            params=params if params else None,
        ).raise_for_status()
        if raw:
            return resp.text
        return UserPolicies.from_api(cast(JsonObject, resp.json()))

    async def alist_policies(
        self,
        user: str,
        *,
        groups: Sequence[str] = (),
        namespaces: Sequence[str] = (),
        raw: bool = False,
    ) -> UserPolicies | str:
        """List policies matching a user, optionally as raw Cedar DSL."""
        params = httpx.QueryParams()
        for group in groups:
            params = params.add("groups", group)
        for namespace in namespaces:
            params = params.add("namespaces", namespace)
        if raw:
            params = params.add("format", "raw")
        resp = (
            await self._async_get(
                f"{Endpoint.POLICIES.value}/{quote(user, safe='')}",
                params=params if params else None,
            )
        ).raise_for_status()
        if raw:
            return resp.text
        return UserPolicies.from_api(cast(JsonObject, resp.json()))

    def authorize(
        self,
        requests: Request | JsonObject | Sequence[Request | JsonObject],
        correlation_id: str | None = None,
    ) -> AuthorizeResponseBrief:
        """Authorize one or more requests (brief detail level). Synchronous version.

        Args:
            requests: A single request or list of requests. Can be Request objects or dictionaries.
            correlation_id: Optional correlation ID for tracing the request.
        Returns:
            An AuthorizeResponseBrief containing the batch results.
        Raises:
            httpx.HTTPStatusError: If the request fails with a non-2xx status code
        """
        request_list: JsonArray
        if isinstance(requests, (Request, dict)):
            request_list = [cast(JsonValue, as_api(requests))]
        else:
            request_list = [cast(JsonValue, as_api(req)) for req in requests]
        resp = self._sync_post(
            Endpoint.AUTHORIZE.value,
            json_body={"requests": request_list},
            correlation_id=correlation_id,
        )
        return AuthorizeResponseBrief.from_api(
            cast(JsonObject, resp.raise_for_status().json())
        )

    def authorize_detailed(
        self,
        requests: Request | JsonObject | Sequence[Request | JsonObject],
        correlation_id: str | None = None,
    ) -> AuthorizeResponseDetailed:
        """Authorize one or more requests (detailed with policy info). Synchronous version.

        Args:
            requests: A single request or list of requests. Can be Request objects or dictionaries.
            correlation_id: Optional correlation ID for tracing the request.
        Returns:
            An AuthorizeResponseDetailed containing the batch results with policy info.
        Raises:
            httpx.HTTPStatusError: If the request fails with a non-2xx status code
        """
        request_list: JsonArray
        if isinstance(requests, (Request, dict)):
            request_list = [cast(JsonValue, as_api(requests))]
        else:
            request_list = [cast(JsonValue, as_api(req)) for req in requests]
        resp = self._sync_post(
            Endpoint.AUTHORIZE.value,
            json_body={"requests": request_list},
            correlation_id=correlation_id,
            params={"detail": "full"},
        )
        return AuthorizeResponseDetailed.from_api(
            cast(JsonObject, resp.raise_for_status().json())
        )

    async def aauthorize(
        self,
        requests: Request | JsonObject | Sequence[Request | JsonObject],
        correlation_id: str | None = None,
    ) -> AuthorizeResponseBrief:
        """Authorize one or more requests (brief detail level). Asynchronous version.

        Args:
            requests: A single request or list of requests. Can be Request objects or dictionaries.
            correlation_id: Optional correlation ID for tracing the request.
        Returns:
            An AuthorizeResponseBrief containing the batch results.
        Raises:
            httpx.HTTPStatusError: If the request fails with a non-2xx status code
        """
        request_list: JsonArray
        if isinstance(requests, (Request, dict)):
            request_list = [cast(JsonValue, as_api(requests))]
        else:
            request_list = [cast(JsonValue, as_api(req)) for req in requests]
        resp = await self._async_post(
            Endpoint.AUTHORIZE.value,
            json_body={"requests": request_list},
            correlation_id=correlation_id,
        )
        return AuthorizeResponseBrief.from_api(
            cast(JsonObject, resp.raise_for_status().json())
        )

    async def aauthorize_detailed(
        self,
        requests: Request | JsonObject | Sequence[Request | JsonObject],
        correlation_id: str | None = None,
    ) -> AuthorizeResponseDetailed:
        """Authorize one or more requests (detailed with policy info). Asynchronous version.

        Args:
            requests: A single request or list of requests. Can be Request objects or dictionaries.
            correlation_id: Optional correlation ID for tracing the request.
        Returns:
            An AuthorizeResponseDetailed containing the batch results with policy info.
        Raises:
            httpx.HTTPStatusError: If the request fails with a non-2xx status code
        """
        request_list: JsonArray
        if isinstance(requests, (Request, dict)):
            request_list = [cast(JsonValue, as_api(requests))]
        else:
            request_list = [cast(JsonValue, as_api(req)) for req in requests]
        resp = await self._async_post(
            Endpoint.AUTHORIZE.value,
            json_body={"requests": request_list},
            correlation_id=correlation_id,
            params={"detail": "full"},
        )
        return AuthorizeResponseDetailed.from_api(
            cast(JsonObject, resp.raise_for_status().json())
        )

    # Compatibility methods for single-request API (wraps batch API)
    def check(
        self, request: Request | JsonObject, correlation_id: str | None = None
    ) -> AuthorizedResponseBrief:
        """Check the given request. Synchronous version (compatibility wrapper).

        This method provides backward compatibility with the old single-request API.
        It wraps the new batch authorize endpoint.

        Args:
            request: The request to check, either as a Request object or a dictionary.
            correlation_id: Optional correlation ID for tracing the request.
        Returns:
            An AuthorizedResponseBrief containing the result of the check.
        Raises:
            httpx.HTTPStatusError: If the request fails with a non-2xx status code
        """
        response = self.authorize(request, correlation_id=correlation_id)
        if not response.results:
            raise ValueError("No results returned from authorize endpoint")
        result = response.results[0]
        if result.status == "failed":
            raise RuntimeError(f"Authorization failed: {result.error}")
        return result.result or AuthorizedResponseBrief(Decision.DENY)

    def check_detailed(
        self, request: Request | JsonObject, correlation_id: str | None = None
    ) -> AuthorizedResponseDetailed:
        """Check the given request with detailed output. Synchronous version (compatibility wrapper).

        This method provides backward compatibility with the old single-request API.
        It wraps the new batch authorize_detailed endpoint.

        Args:
            request: The request to check, either as a Request object or a dictionary.
            correlation_id: Optional correlation ID for tracing the request.
        Returns:
            An AuthorizedResponseDetailed containing the detailed result of the check.
        Raises:
            httpx.HTTPStatusError: If the request fails with a non-2xx status code
        """
        response = self.authorize_detailed(request, correlation_id=correlation_id)
        if not response.results:
            raise ValueError("No results returned from authorize endpoint")
        result = response.results[0]
        if result.status == "failed":
            raise RuntimeError(f"Authorization failed: {result.error}")
        return result.result or AuthorizedResponseDetailed(Decision.DENY, [], None)

    async def acheck(
        self, request: Request | JsonObject, correlation_id: str | None = None
    ) -> AuthorizedResponseBrief:
        """Check the given request. Asynchronous version (compatibility wrapper).

        This method provides backward compatibility with the old single-request API.
        It wraps the new batch aauthorize endpoint.

        Args:
            request: The request to check, either as a Request object or a dictionary.
            correlation_id: Optional correlation ID for tracing the request.
        Returns:
            An AuthorizedResponseBrief containing the result of the check.
        Raises:
            httpx.HTTPStatusError: If the request fails with a non-2xx status code
        """
        response = await self.aauthorize(request, correlation_id=correlation_id)
        if not response.results:
            raise ValueError("No results returned from authorize endpoint")
        result = response.results[0]
        if result.status == "failed":
            raise RuntimeError(f"Authorization failed: {result.error}")
        return result.result or AuthorizedResponseBrief(Decision.DENY)

    async def acheck_detailed(
        self, request: Request | JsonObject, correlation_id: str | None = None
    ) -> AuthorizedResponseDetailed:
        """Check the given request with detailed output. Asynchronous version (compatibility wrapper).

        This method provides backward compatibility with the old single-request API.
        It wraps the new batch aauthorize_detailed endpoint.

        Args:
            request: The request to check, either as a Request object or a dictionary.
            correlation_id: Optional correlation ID for tracing the request.
        Returns:
            An AuthorizedResponseDetailed containing the detailed result of the check.
        Raises:
            httpx.HTTPStatusError: If the request fails with a non-2xx status code
        """
        response = await self.aauthorize_detailed(
            request, correlation_id=correlation_id
        )
        if not response.results:
            raise ValueError("No results returned from authorize endpoint")
        result = response.results[0]
        if result.status == "failed":
            raise RuntimeError(f"Authorization failed: {result.error}")
        return result.result or AuthorizedResponseDetailed(Decision.DENY, [], None)

    def close(self):
        """Close the synchronous client connection."""
        with contextlib.suppress(Exception):
            self._sync_client.close()

    async def aclose(self):
        """Close the asynchronous client connection."""
        await self._async_client.aclose()
        self._sync_client.close()


# For typing convenience
RequestLike = Request | JsonObject
