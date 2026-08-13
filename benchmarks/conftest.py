"""Fixtures shared by the CodSpeed benchmarks."""

from __future__ import annotations

import pytest

from benchmarks.helpers import TESTDATA


@pytest.fixture(scope="session")
def cedar_policies() -> str:
    """Raw Cedar policy document used as an upload/download payload."""
    return (TESTDATA / "dns.cedar").read_text()
