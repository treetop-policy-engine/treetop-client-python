# Breaking 0.1.0 migration

Upgrade all services and clients to the coordinated contract. Early releases
prioritize correctness over compatibility; old response formats are rejected.

## Authorization and operations

Replace `check(request)` with `authorize(request)` and inspect the returned batch
item's status before using its result. Use `authorize_detailed`, `aauthorize`, and
`aauthorize_detailed` for the corresponding operations. A single request returns
the same batch shape as multiple requests. The old single-result wrappers are
removed. Use `livez`/`alivez`, `readyz`/`areadyz`, and `openapi`/`aopenapi`;
`health`/`ahealth` and the server's legacy health/OpenAPI routes are removed.

Responses require canonical decision strings, detailed policy arrays, complete
status metadata, and all four version fields: `hash`, `loaded_at`, nullable
`label_set`, and unsigned 64-bit `generation`. Batch items must have consecutive
indices, consistent status and counts, and exactly the enclosing version. Parsing
errors are errors; never turn them into allow decisions. `all_allowed()` is false
for empty batches or any failed item. Custom `PolicyVersion` subclasses must
accept all four fields and are not interned.

## Declared label targets

Configurations now use this rule shape:

```json
{
  "target": {"resource_type": "App::Host", "attribute": "labels"},
  "field": "name",
  "patterns": [{"name": "prod", "regex": "^prod"}]
}
```

Replace `kind`/`output` with the explicit target. Each exact Cedar resource type
and attribute tuple has one owner. Distinct types can reuse attribute names.
Sanitization follows that same scope: constrain resource types in policies before
trusting derived labels. Set bundle/module manifests to format 2, rebuild archives,
and re-sign them. Format 1 and old label syntax are rejected.

## Coordinated verification

CI runs the full integration suite against the immutable REST 0.1.0 release image
pinned in its workflow. Release Core, Bundle, and REST before Python 0.1.0.

Schema revisions use `SchemaVersion` with required `hash` and `loaded_at`,
separately from policy/label generations. REST and Core version strings are
package versions without a `v` prefix.

Require one response per submitted request with the same ID. Reject inconsistent
Allow/Deny policy IDs or arrays, missing permit Cedar IDs, and missing metadata
content instead of filling legacy defaults.
