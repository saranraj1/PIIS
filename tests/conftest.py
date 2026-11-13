"""Global pytest configuration and test environment initialization for PIIS test suites."""

import os
import pytest

# High-entropy 32-byte test HMAC signing key for isolated test execution
TEST_HMAC_KEY_HEX = "4a8f9c0e2b1d3f5a7e6c8b0d2e4f6a8c1e3b5d7f9a2c4e6b8d0f1a3c5e7b9d1f"


@pytest.fixture(autouse=True)
def setup_test_environment(monkeypatch):
    """Ensure test environment variables are properly configured for all test runs."""
    if "PIIS_AUDIT_HMAC_KEY" not in os.environ:
        monkeypatch.setenv("PIIS_AUDIT_HMAC_KEY", TEST_HMAC_KEY_HEX)
    monkeypatch.setenv("PIIS_ENV", "test")
