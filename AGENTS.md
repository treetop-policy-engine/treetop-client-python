# Repository guidelines

Prioritize correctness and one strict current project contract over compatibility
in early releases. Remove obsolete aliases and defaults with concrete breaking
migration notes. Keep synchronous and asynchronous methods uniform.

Validate authorization response counts, indices, statuses, and complete versions.
Never treat malformed responses, empty batches, or failed items as authorization.
Keep the version cache bounded and immutable, reject invalid typed keys, and keep
subclass construction uncached. Preserve client transport and token protections.

Run `pytest -m "not integration"`, `pyright`, `basedpyright`, and
`pytest benchmarks`. Run the full integration suite against the exact coordinated
REST release for wire changes. An unavailable or unready integration service
must fail, not silently skip. Run `uv build` and inspect wheel/sdist contents for
package changes. Review performance in CodSpeed without weakening its checks.

Document user-visible changes in `Changelog.md` and `MIGRATION.md`. Use signed
commits and prepare reviewable PRs. Do not merge or release without user approval.
