"""tests/test_m01_security.py - Comprehensive Unit Tests for M01.

Validates CryptoVault, TokenBucketRateLimiter, CircuitBreaker, OPSECGuard, and HashChainedAuditLogger.
"""

from __future__ import annotations

import time
import pytest

from backend.core.config import CryptoVault, TokenBucketRateLimiter
from backend.core.security import (
    CircuitBreaker,
    CircuitOpenError,
    OPSECGuard,
    HashChainedAuditLogger,
)


def test_crypto_vault_roundtrip(tmp_path):
    """Test Fernet symmetric encryption and decryption."""
    vault_file = tmp_path / ".vault_key"
    vault = CryptoVault(key_path=vault_file)

    secret = "shodan_live_api_token_1234567890abcdef"
    token = vault.encrypt(secret)
    assert token != secret
    assert isinstance(token, str)

    decrypted = vault.decrypt(token)
    assert decrypted == secret

    # Invalid / corrupt token should safely return empty string
    assert vault.decrypt("invalid_corrupted_token_bytes") == ""
    assert vault.decrypt("") == ""


def test_crypto_vault_key_masking():
    """Test safe API key masking."""
    assert CryptoVault.mask_key("shodan1234567890") == "shod****7890"
    assert CryptoVault.mask_key("short") == "****"
    assert CryptoVault.mask_key("") == ""


def test_token_bucket_rate_limiter():
    """Test token bucket rate limiter exhaustion and refill."""
    limiter = TokenBucketRateLimiter()
    connector = "test_source"

    # RPM = 60 means 1 token per second, capacity = 60
    # First acquire should succeed immediately
    allowed, wait = limiter.acquire(connector, rpm=60)
    assert allowed is True
    assert wait == 0.0

    # Test with very low RPM (1 req per minute) to test exhaustion
    limiter.reset(connector)
    # First token consumed
    allowed1, _ = limiter.acquire(connector, rpm=1)
    assert allowed1 is True

    # Immediate second request should be throttled
    allowed2, wait2 = limiter.acquire(connector, rpm=1)
    assert allowed2 is False
    assert wait2 > 0.0


def test_circuit_breaker_transitions():
    """Test 3-state circuit breaker state machine: CLOSED -> OPEN -> HALF_OPEN -> CLOSED."""
    cb = CircuitBreaker(failure_threshold=3, cooldown_seconds=0.1)
    cid = "api.shodan.io"

    # Starts CLOSED
    assert cb.get_state(cid) == "CLOSED"
    assert cb.can_execute(cid) is True

    # Record 2 failures -> remains CLOSED
    cb.record_failure(cid, status_code=500)
    cb.record_failure(cid, status_code=502)
    assert cb.get_state(cid) == "CLOSED"

    # Record 3rd failure -> trips to OPEN
    cb.record_failure(cid, status_code=503)
    assert cb.get_state(cid) == "OPEN"

    # can_execute should raise CircuitOpenError while OPEN
    with pytest.raises(CircuitOpenError):
        cb.can_execute(cid)

    # Wait for cooldown to elapse
    time.sleep(0.15)

    # Now state should be HALF_OPEN and permit 1 probe
    assert cb.get_state(cid) == "HALF_OPEN"
    assert cb.can_execute(cid) is True

    # Success during HALF_OPEN resets to CLOSED
    cb.record_success(cid)
    assert cb.get_state(cid) == "CLOSED"


def test_opsec_guard_passive_only():
    """Test OPSEC Passive-Only mode validation."""
    # STANDARD mode allows all
    allowed, _ = OPSECGuard.validate_request("https://target.com", opsec_mode="STANDARD")
    assert allowed is True

    # PASSIVE_ONLY blocks active connectors
    allowed_act, reason_act = OPSECGuard.validate_request(
        "https://target.com", opsec_mode="PASSIVE_ONLY", is_passive_connector=False
    )
    assert allowed_act is False
    assert "Active reconnaissance" in reason_act

    # PASSIVE_ONLY blocks direct target connection
    allowed_dir, reason_dir = OPSECGuard.validate_request(
        "https://target.com/api",
        opsec_mode="PASSIVE_ONLY",
        is_passive_connector=True,
        investigated_target="target.com",
    )
    assert allowed_dir is False
    assert "Direct connection to investigated target" in reason_dir

    # PASSIVE_ONLY permits verified aggregators
    allowed_agg, _ = OPSECGuard.validate_request(
        "https://cloudflare-dns.com/dns-query",
        opsec_mode="PASSIVE_ONLY",
        is_passive_connector=True,
        investigated_target="target.com",
    )
    assert allowed_agg is True


def test_hash_chained_audit_logger():
    """Test cryptographic SHA-256 tamper-evident hash chaining."""
    h0 = HashChainedAuditLogger.GENESIS_HASH

    # Entry 1
    h1 = HashChainedAuditLogger.compute_entry_hash(
        h0, 1, "2026-11-08T12:00:00Z", "WORKSPACE_CREATED", "Case Sentinel"
    )
    entry1 = {
        "seq_no": 1,
        "timestamp": "2026-11-08T12:00:00Z",
        "action": "WORKSPACE_CREATED",
        "details": "Case Sentinel",
        "prev_hash": h0,
        "entry_hash": h1,
    }

    # Entry 2
    h2 = HashChainedAuditLogger.compute_entry_hash(
        h1, 2, "2026-11-08T12:01:00Z", "COLLECTOR_RUN", "dns_doh on example.com"
    )
    entry2 = {
        "seq_no": 2,
        "timestamp": "2026-11-08T12:01:00Z",
        "action": "COLLECTOR_RUN",
        "details": "dns_doh on example.com",
        "prev_hash": h1,
        "entry_hash": h2,
    }

    chain = [entry1, entry2]
    is_valid, count, msg = HashChainedAuditLogger.verify_chain(chain)
    assert is_valid is True
    assert count == 2

    # Tampering test: modify details of entry 1
    tampered_chain = [
        dict(entry1, details="Tampered Details"),
        entry2,
    ]
    is_valid_t, bad_idx, err = HashChainedAuditLogger.verify_chain(tampered_chain)
    assert is_valid_t is False
    assert bad_idx == 0
    assert "Tampered record" in err
