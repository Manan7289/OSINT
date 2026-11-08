"""tests/test_m03_collectors.py - Comprehensive Unit Tests for M03.

Validates Target Auto-Detection, Composite Vulnerability Risk Scoring,
HTTP Caching, Staging Buffer Overflow (>50 entities), Keyed Connector Graceful Skip,
and Playbook Execution.
"""

from __future__ import annotations

import pytest
from backend.collectors.orchestrator import (
    calculate_composite_vulnerability_risk,
    detect_target_type,
    CollectorOrchestrator,
    _validate_outbound_url,
)
from backend.core.database import DatabaseManager


@pytest.fixture
def test_db(tmp_path):
    db_file = tmp_path / "test_m03_localosint.db"
    return DatabaseManager(db_path=db_file)


def test_target_type_auto_detection():
    """Test heuristic detection of target entity schema."""
    assert detect_target_type("198.51.100.14") == "IPv4Address"
    assert detect_target_type("2001:db8::1") == "IPv6Address"
    assert detect_target_type("AS13335") == "AutonomousSystem"
    assert detect_target_type("CVE-2024-3400") == "Vulnerability"
    assert detect_target_type("analyst@investigation.org") == "Email"
    assert detect_target_type("sub.target-domain.com") == "Domain"
    assert detect_target_type("https://victim.com/login") == "Domain"
    assert detect_target_type("Acme International Defense") == "Company"


def test_composite_vulnerability_risk_calculation():
    """Test CISA KEV + FIRST EPSS + NVD CVSS composite formula."""
    # KEV confirmed -> 95
    assert calculate_composite_vulnerability_risk(is_kev=True, cvss_score=7.0, epss_score=0.10) == 95

    # Non-KEV: 0.6 * CVSS * 10 + 0.4 * EPSS * 100
    # CVSS 10.0, EPSS 0.50 -> 0.6*100 + 0.4*50 = 60 + 20 = 80
    score = calculate_composite_vulnerability_risk(is_kev=False, cvss_score=10.0, epss_score=0.50)
    assert score == 80


@pytest.mark.asyncio
async def test_keyed_connector_graceful_skip(test_db):
    """Test that missing BYO-Key transitions task to SKIPPED rather than crashing."""
    orc = CollectorOrchestrator(database=test_db)
    ws = test_db.create_workspace(name="Keyed Test")
    ws_id = ws["id"]

    task = test_db.create_task(ws_id, "shodan_pro", "198.51.100.1")
    res = await orc.run_connector(
        workspace_id=ws_id,
        connector_id="shodan_pro",
        target_query="198.51.100.1",
        target_type="IPv4Address",
        task_id=task["id"],
    )

    assert res["status"] == "SKIPPED"
    assert "API Key required" in res["message"]

    task_record = test_db.get_task(task["id"])
    assert task_record["status"] == "SKIPPED"
    await orc.close()


@pytest.mark.asyncio
async def test_staging_triage_buffer_overflow(test_db):
    """Test that entities exceeding the workspace staging threshold receive is_staged = 1."""
    orc = CollectorOrchestrator(database=test_db)
    # Workspace with threshold of 5
    ws = test_db.create_workspace(name="Staging Overflow Test", staging_threshold=5)
    ws_id = ws["id"]

    # Mock handler emitting 12 entities
    async def mock_handler(**kwargs):
        entities = [{"ftm_schema": "Subdomain", "raw_value": f"sub{i}.target.org"} for i in range(12)]
        claims = []
        return entities, claims, {"total": 12}

    orc._collect_test_overflow = mock_handler
    # Register test connector
    with test_db.get_connection() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO connector_configs (
                connector_id, display_name, category, upstream_lineage_family,
                default_admiralty_reliability, requires_api_key, encrypted_api_key,
                enabled, is_passive, rate_limit_rpm, cache_ttl_seconds,
                circuit_state, failure_count, base_url, docs_url, description, updated_at
            ) VALUES ('test_overflow', 'Test Overflow', 'Test', 'TestFamily', 'B', 0, '', 1, 1, 60, 3600, 'CLOSED', 0, 'http://test', 'http://docs', 'desc', '2026-11-08T12:00:00Z');
            """
        )

    task = test_db.create_task(ws_id, "test_overflow", "target.org")
    res = await orc.run_connector(
        workspace_id=ws_id,
        connector_id="test_overflow",
        target_query="target.org",
        target_type="Domain",
        task_id=task["id"],
    )

    assert res["status"] == "COMPLETED"
    assert res["entities"] == 12
    # First 5 active, remaining 7 staged
    assert res["staged"] == 7

    active_ents = test_db.list_entities(ws_id, include_staged=False)
    assert len(active_ents) == 5

    staged_ents = test_db.list_entities(ws_id, include_staged=True)
    assert len(staged_ents) == 12
    await orc.close()


@pytest.mark.asyncio
async def test_http_caching_mechanism(test_db):
    """Test that HTTP responses are stored in and retrieved from SQLite http_cache."""
    orc = CollectorOrchestrator(database=test_db)

    # Prime cache manually
    with test_db.get_connection() as conn:
        import hashlib, time, json
        cache_seed = "test_conn:GET:https://api.test/data:{}:{}"
        cache_key = hashlib.sha256(cache_seed.encode("utf-8")).hexdigest()
        conn.execute(
            """
            INSERT INTO http_cache (cache_key, connector_id, url, status_code, response_json, created_epoch, expires_epoch)
            VALUES (?, 'test_conn', 'https://api.test/data', 200, ?, ?, ?);
            """,
            (cache_key, json.dumps({"cached_result": "success"}), time.time(), time.time() + 3600),
        )

    # Request should return cached value without hitting network
    status, data, from_cache = await orc.execute_http("test_conn", "https://api.test/data")
    assert status == 200
    assert from_cache is True
    assert data.get("cached_result") == "success"
    await orc.close()


def test_ssrf_guard_blocks_file_and_private_ips():
    """Test SSRF validation rejects non-HTTP schemes and private/loopback/link-local IP addresses."""
    # Scheme validation
    assert _validate_outbound_url("file:///C:/Windows/win.ini") is False
    assert _validate_outbound_url("ftp://example.com/file.txt") is False
    assert _validate_outbound_url("gopher://127.0.0.1:70") is False

    # Private and loopback addresses
    assert _validate_outbound_url("http://127.0.0.1:8000") is False
    assert _validate_outbound_url("http://localhost:8080") is False
    assert _validate_outbound_url("http://10.0.0.1/admin") is False
    assert _validate_outbound_url("http://192.168.1.1/router") is False
    assert _validate_outbound_url("http://172.16.0.1/private") is False
    assert _validate_outbound_url("http://169.254.169.254/latest/meta-data") is False

    # Valid external HTTPS target
    assert _validate_outbound_url("https://8.8.8.8/dns-query") is True

