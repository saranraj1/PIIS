"""
Unit tests for PIIS Trust Boundary & Cryptographic Governance Architecture.
Validates:
- GOV-M5.5-001 / DEP-M5.5.1-001: Fail-closed production boundaries.
- SigningKeyProvider lifecycle, rotation, and production enforcement.
- TimestampAuthorityProvider RFC 3161 tokens.
- WORMStorageProvider write-once immutability enforcement.
"""

import pytest

from piis.audit.trust_boundary import (
    ExternalKMSProvider,
    ExternalS3ObjectLockProvider,
    LocalDevKeyProvider,
    LocalDevTimestampProvider,
    LocalDevWORMProvider,
    ProductionTrustViolationError,
    RFC3161TimestampProvider,
    TrustBoundaryConfig,
    TrustBoundaryError,
    TrustBoundaryManager,
)


def test_local_dev_key_provider_lifecycle():
    """Verify LocalDevKeyProvider produces 256-bit keys and supports rotation."""
    provider = LocalDevKeyProvider(environment="development")
    key = provider.get_signing_key()
    assert len(key) >= 32
    assert provider.get_key_id() == "piis-local-dev-key-v1"

    new_id, new_key = provider.rotate_key()
    assert new_id == "piis-local-dev-key-v2"
    assert len(new_key) >= 32
    assert new_key != key


def test_local_dev_key_provider_fails_closed_in_production(monkeypatch):
    """Verify LocalDevKeyProvider raises ProductionTrustViolationError in production."""
    monkeypatch.setenv("PIIS_ENVIRONMENT", "production")
    with pytest.raises(ProductionTrustViolationError, match="cannot be initialized in production"):
        LocalDevKeyProvider()


def test_external_kms_provider_lifecycle():
    """Verify ExternalKMSProvider derives keys and validates production ARNs."""
    dev_kms = ExternalKMSProvider(
        key_arn="arn:aws:kms:us-east-1:123456789012:key/test-key",
        environment="development",
    )
    assert len(dev_kms.get_signing_key()) == 32
    rot_id, rot_key = dev_kms.rotate_key()
    assert "rotated" in rot_id

    # In production, invalid or test ARN fails closed
    with pytest.raises(ProductionTrustViolationError, match="Invalid KMS Key ARN"):
        ExternalKMSProvider(
            key_arn="arn:aws:kms:test:12345:key/invalid",
            environment="production",
        )


def test_timestamp_authority_providers():
    """Verify LocalDev and RFC3161 TSA token generation and validation."""
    dev_tsa = LocalDevTimestampProvider(environment="development")
    data_hash = "a" * 64
    token = dev_tsa.generate_timestamp_token(data_hash)
    assert dev_tsa.verify_timestamp_token(token, data_hash) is True
    assert dev_tsa.verify_timestamp_token(token, "b" * 64) is False

    # Production fail-closed
    with pytest.raises(ProductionTrustViolationError, match="cannot be used in production"):
        LocalDevTimestampProvider(environment="production")

    rfc_tsa = RFC3161TimestampProvider(
        tsa_url="https://tsa.telecom.internal/rfc3161",
        environment="production",
    )
    rfc_token = rfc_tsa.generate_timestamp_token(data_hash)
    assert rfc_tsa.verify_timestamp_token(rfc_token, data_hash) is True

    # Insecure HTTP fails closed in production
    with pytest.raises(ProductionTrustViolationError, match="must use HTTPS"):
        RFC3161TimestampProvider(
            tsa_url="http://insecure-tsa.telecom.internal",
            environment="production",
        )


def test_worm_storage_providers():
    """Verify WORM immutable storage prevents overwrite and fails in production."""
    dev_worm = LocalDevWORMProvider(environment="development")
    dev_worm.store_immutable_record("rec-001", b"canonical payload")
    
    # Overwrite fails
    with pytest.raises(TrustBoundaryError, match="already exists and cannot be overwritten"):
        dev_worm.store_immutable_record("rec-001", b"tampered payload")

    # Production fail-closed
    with pytest.raises(ProductionTrustViolationError, match="cannot be used in production"):
        LocalDevWORMProvider(environment="production")

    prod_worm = ExternalS3ObjectLockProvider(
        bucket_name="telecom-compliance-audit-worm",
        environment="production",
    )
    res = prod_worm.store_immutable_record("rec-002", b"audit data")
    assert res["worm_type"] == "S3_OBJECT_LOCK_COMPLIANCE"
    assert prod_worm.verify_immutability("rec-002")["status"] == "LOCKED"


def test_trust_boundary_manager_notarization():
    """Verify TrustBoundaryManager coordinates signing and notarization."""
    mgr = TrustBoundaryManager(TrustBoundaryConfig(environment="development"))
    canonical_jcs = '{"audit_id":"AUD-001","status":"APPROVED"}'
    notarization = mgr.notarize_evaluation_manifest(canonical_jcs)
    assert "signature" in notarization
    assert "timestamp_token" in notarization
    assert notarization["provider_class"] == "LocalDevKeyProvider"


def test_trust_boundary_manager_production_fail_closed():
    """Verify TrustBoundaryManager fails closed in production when enterprise backends missing."""
    with pytest.raises(ProductionTrustViolationError, match="KMS Key ARN must be configured"):
        TrustBoundaryManager(TrustBoundaryConfig(environment="production"))

    with pytest.raises(ProductionTrustViolationError, match="RFC 3161 TSA URL must be configured"):
        TrustBoundaryManager(
            TrustBoundaryConfig(
                environment="production",
                kms_key_arn="arn:aws:kms:us-east-1:123456789012:key/prod-key-1",
            )
        )
