# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.0.7] - 2026-07-05

### Added

- Support for Treetop REST v0.0.7:
  - Request-scoped authorization `context` on `Request`
  - `health()` / `ahealth()`
  - `version()` / `aversion()`
  - `status()` / `astatus()`
  - `get_policies()` / `aget_policies()`
  - `upload_policies()` / `aupload_policies()`
  - `get_schema()` / `aget_schema()`
  - `upload_schema()` / `aupload_schema()`
- Typed models for server version, policy metadata, status, request limits, and request context status.

## [0.0.6] - 2026-01-30

### Added

- **New unified batch authorization endpoint** (`POST /api/v1/authorize`):
  - `authorize()` method for synchronous batch processing with brief response details
  - `authorize_detailed()` method for synchronous batch processing with policy information
  - `aauthorize()` method for asynchronous batch processing (brief)
  - `aauthorize_detailed()` method for asynchronous batch processing (detailed)
  - Optional `id` field on `Request` for client-provided request correlation identifiers
  - `AuthorizeResponseBrief` and `AuthorizeResponseDetailed` for typed batch responses
  - `AuthorizeResultBrief` and `AuthorizeResultDetailed` for individual result handling
  - Response iteration, indexing, and `get_by_id()` method for convenient result access
  - Result helper methods: `is_success()`, `is_failed()`, `is_allowed()`, `is_denied()`, `get_decision()`
  - Batch response helper methods: `denied_count()`, `allowed_count()`, `all_allowed()`

### Changed

- **BREAKING**: Legacy single-request endpoints (`/api/v1/check` and `/api/v1/check_detailed`) are no longer used directly
- `check()`, `check_detailed()`, `acheck()`, and `acheck_detailed()` methods now wrap the new batch API for backward compatibility
- Query parameter `detail=full` (instead of separate endpoint) now controls response detail level
- Renamed `CheckResponseBrief` to `AuthorizedResponseBrief` (backward compatibility alias provided)
- Renamed `CheckResponse` to `AuthorizedResponseDetailed` (backward compatibility alias provided)
- Migrated from Poetry to uv for dependency management and build system
- Build backend changed from `poetry-core` to `hatchling`

### Deprecated

- Direct use of `check()` and `check_detailed()` for new code; use `authorize()` and `authorize_detailed()` for batch operations
- Old class names `CheckResponseBrief` and `CheckResponse` (use `AuthorizedResponseBrief` and `AuthorizedResponseDetailed` instead)

## [0.0.5] - 2025-12-19

### Added

- Policy version tracking support (compatible with Treetop REST API ≥ 0.0.12):
  - `PolicyVersion` dataclass with `hash` (SHA-256 of policy text) and `loaded_at` (timezone-aware datetime)
  - `CheckResponse.version` field (optional, `None` for older API versions)
  - `version_hash()` and `version_loaded_at()` helper methods for safe access to version data
- `Decision` enum (`ALLOW`, `DENY`) for type-safe decision handling
- Backward compatibility with Treetop REST API < 0.0.12 (versions without policy tracking)

### Changed

- **BREAKING**: `CheckResponse.decision` and `CheckResponseBrief.decision` now use `Decision` enum instead of string literals
- `PolicyVersion.loaded_at` is now a `datetime` object instead of a string (automatically parses ISO 8601 timestamps)
- Updated README examples to demonstrate `Decision` enum usage and version tracking

## [0.0.4] - 2025-12-04

### Added

- `__str__` methods to `QualifiedId`, `Group`, `Action`, and `User` classes for better string representation.
- Automatic type conversion for `ResourceAttribute`: BOOLEAN values are converted to actual booleans and NUMBER values to floats in API calls.

### Changed

- Updated `Resource.new()` method signature to use `dict[str, ResourceAttribute]` for attributes instead of `dict[str, Any]`.
- Updated README examples to demonstrate the new `ResourceAttribute` API with `ResourceAttributeType`.

## [0.0.3] - 2025-09-01

### Fixed

- Removed debug print statements.
- Updated to the new flatter API format from Treetop Core 0.0.11 onwards. Backwards compatibility is *not* retained.

## [0.0.2] - 2025-07-28

### Added

- This Changelog.
- Support for Correlation IDs in requests.

## [0.0.1] - 2025-07-11

### Added

- Initial release.
