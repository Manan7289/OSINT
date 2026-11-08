"""tests/test_m02_database.py - Comprehensive Unit Tests for M02.

Validates SQLite WAL Pragmas, FollowTheMoney Canonicalization, Bitemporal Claims,
3-Pass Blocking Key Generation, Staging Buffer, and FTS5 BM25 Search.
"""

from __future__ import annotations

import pytest
from backend.core.database import DatabaseManager
from backend.core.ontology import (
    canonicalize_entity,
    encode_geohash,
    generate_blocking_keys,
)


@pytest.fixture
def test_db(tmp_path):
    db_file = tmp_path / "test_localosint.db"
    mgr = DatabaseManager(db_path=db_file)
    return mgr


def test_sqlite_wal_pragmas(test_db):
    """Test that SQLite WAL mode and expected pragmas are active."""
    with test_db.get_connection() as conn:
        cur = conn.execute("PRAGMA journal_mode;")
        journal_mode = cur.fetchone()[0]
        assert journal_mode.lower() == "wal"

        cur = conn.execute("PRAGMA foreign_keys;")
        foreign_keys = cur.fetchone()[0]
        assert foreign_keys == 1


def test_ftm_canonicalization_and_shared_infra():
    """Test FollowTheMoney entity canonicalization rules and RIOT-Lite shared infrastructure."""
    # Domain canonicalization
    c_dom, lbl_dom, shared_dom = canonicalize_entity("Domain", "HTTPS://Example.ORG./")
    assert c_dom == "example.org"
    assert lbl_dom == "example.org"
    assert shared_dom is False

    # Shared Cloudflare Domain
    c_cf, _, shared_cf = canonicalize_entity("Domain", "sub.pages.dev")
    assert shared_cf is True

    # ASN canonicalization & shared infra
    c_asn, _, shared_asn = canonicalize_entity("AutonomousSystem", "as 13335")
    assert c_asn == "AS13335"
    assert shared_asn is True  # Cloudflare ASN

    # IPv4 normalization & shared DNS
    c_ip, _, shared_ip = canonicalize_entity("IPv4Address", "1.1.1.1")
    assert c_ip == "1.1.1.1"
    assert shared_ip is True

    # Company name suffix stripping
    c_co, lbl_co, _ = canonicalize_entity("Company", "ShadowNet Technologies, Inc.")
    assert "inc" not in c_co
    assert c_co == "shadownet technologies"
    assert lbl_co == "ShadowNet Technologies, Inc."


def test_workspace_lifecycle_and_cascade(test_db):
    """Test workspace creation, entity upsert, and cascade deletion."""
    ws = test_db.create_workspace(name="Op Horizon", tlp_marking="TLP:AMBER")
    ws_id = ws["id"]
    assert ws["name"] == "Op Horizon"

    # Add entity
    ent = test_db.upsert_entity(
        workspace_id=ws_id,
        ftm_schema="Domain",
        raw_value="horizon-target.com",
    )
    assert ent["canonical_value"] == "horizon-target.com"

    # Verify counts
    ws_fetched = test_db.get_workspace(ws_id)
    assert ws_fetched["entity_count"] == 1

    # Cascade delete
    deleted = test_db.delete_workspace(ws_id)
    assert deleted is True
    assert test_db.get_workspace(ws_id) is None
    assert test_db.get_entity(ent["id"]) is None


def test_entity_deduplication_and_blocking_keys(test_db):
    """Test that upserting duplicate canonical entity updates source count and creates 3-pass blocking keys."""
    ws = test_db.create_workspace(name="Deduplication Test")
    ws_id = ws["id"]

    ent1 = test_db.upsert_entity(
        workspace_id=ws_id,
        ftm_schema="Company",
        raw_value="Acme Cyber Defense LLC",
    )
    ent_id = ent1["id"]
    assert ent1["independent_source_count"] == 1

    # Upsert variation of the same company
    ent2 = test_db.upsert_entity(
        workspace_id=ws_id,
        ftm_schema="Company",
        raw_value="ACME Cyber Defense Inc.",
    )
    assert ent2["id"] == ent_id  # Same entity record
    assert ent2["independent_source_count"] == 2

    # Verify 3-pass blocking keys generated
    with test_db.get_connection() as conn:
        cur = conn.execute("SELECT pass_type, blocking_key FROM entity_blocking_keys WHERE entity_id = ?;", (ent_id,))
        keys = cur.fetchall()
        pass_types = {r["pass_type"] for r in keys}
        assert "PHONETIC_SORT" in pass_types
        assert "APEX_PREFIX" in pass_types
        assert "MINHASH_LSH" in pass_types


def test_bitemporal_claims_time_travel(test_db):
    """Test bitemporal claim filtering based on occurrence time (valid_from / valid_until)."""
    ws = test_db.create_workspace(name="Bitemporal Test")
    ws_id = ws["id"]

    ent_domain = test_db.upsert_entity(ws_id, "Domain", "historical-host.org")
    ent_ip = test_db.upsert_entity(ws_id, "IPv4Address", "192.0.2.1")

    # Claim active only during 2024
    claim = test_db.add_claim(
        workspace_id=ws_id,
        subject_entity_id=ent_domain["id"],
        predicate="RESOLVES_TO",
        object_entity_id=ent_ip["id"],
        valid_from="2024-01-01T00:00:00Z",
        valid_until="2024-12-31T23:59:59Z",
    )

    # Time-travel queries
    # Query in mid-2024: claim should be visible
    claims_2024 = test_db.list_claims(ws_id, as_of_time="2024-06-15T12:00:00Z")
    assert len(claims_2024) == 1
    assert claims_2024[0]["id"] == claim["id"]

    # Query in 2025: claim should be expired / filtered out
    claims_2025 = test_db.list_claims(ws_id, as_of_time="2025-03-01T00:00:00Z")
    assert len(claims_2025) == 0

    # Query in 2023: claim was not yet valid
    claims_2023 = test_db.list_claims(ws_id, as_of_time="2023-05-01T00:00:00Z")
    assert len(claims_2023) == 0


def test_staging_buffer_and_promotion(test_db):
    """Test that staged entities are separated from visual graph and promoted correctly."""
    ws = test_db.create_workspace(name="Staging Test")
    ws_id = ws["id"]

    # Add 2 staged entities and 1 unstaged entity
    ent1 = test_db.upsert_entity(ws_id, "Subdomain", "a.example.org", is_staged=1, risk_score=20)
    ent2 = test_db.upsert_entity(ws_id, "Subdomain", "b.example.org", is_staged=1, risk_score=85)
    ent3 = test_db.upsert_entity(ws_id, "Subdomain", "c.example.org", is_staged=0, risk_score=10)

    # Default list excludes staged
    active = test_db.list_entities(ws_id, include_staged=False)
    assert len(active) == 1
    assert active[0]["id"] == ent3["id"]

    # Promote high-risk staged entities (risk >= 50)
    promoted = test_db.promote_staged_entities(ws_id, min_risk=50)
    assert promoted == 1

    active_after = test_db.list_entities(ws_id, include_staged=False)
    assert len(active_after) == 2
    active_ids = {e["id"] for e in active_after}
    assert ent2["id"] in active_ids
    assert ent1["id"] not in active_ids


def test_fts5_bm25_search(test_db):
    """Test SQLite FTS5 BM25 search across entities and evidence."""
    ws = test_db.create_workspace(name="Search Test")
    ws_id = ws["id"]

    test_db.upsert_entity(
        ws_id,
        "Vulnerability",
        "CVE-2024-3400",
        display_label="CVE-2024-3400 PAN-OS Command Injection",
    )

    ev = test_db.add_evidence(
        workspace_id=ws_id,
        connector_id="nvd_cve_v2",
        upstream_lineage_family="NIST",
        source_name="NVD",
        source_url="https://nvd.nist.gov/vuln/detail/CVE-2024-3400",
        title="NVD Report on CVE-2024-3400",
        summary_text="Palo Alto Networks PAN-OS GlobalProtect command injection zero-day exploited in wild",
        raw_payload={"cve_id": "CVE-2024-3400"},
    )

    # Search exact technical indicator
    results = test_db.search_fts(ws_id, "CVE-2024-3400")
    assert len(results) >= 1
    record_ids = {r["record_id"] for r in results}
    assert ev["id"] in record_ids


def test_geohash_encoding():
    """Test pure-Python Geohash-8 encoding."""
    # Paris approx (48.8584, 2.2945)
    gh = encode_geohash(48.8584, 2.2945, precision=8)
    assert len(gh) == 8
    assert gh.startswith("u09t")
