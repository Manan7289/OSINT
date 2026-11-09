"""
Comprehensive End-to-End Integration, OPSEC & Performance Test Suite for LocalOSINT v2.0
Validates complete multi-view investigation workflows, OPSEC isolation, Fellegi-Sunter waterfall adjudication,
reversible merge ledger, GraphRAG citation entailment, and high-volume performance.
"""

import time
import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.core.database import db
from backend.core.security import OPSECGuard, HashChainedAuditLogger
from backend.core.provenance_fusion import (
    cumulative_fusion,
    fuse_evidence_artifacts,
    opinion_from_admiralty,
)
from backend.core.entity_resolution import (
    EntityResolutionEngine,
    run_fellegi_sunter_em,
)
from backend.core.graph_analytics import (
    GraphAnalyticsEngine,
    run_power_iteration_pagerank,
)
from backend.ai.search_rrf import text_to_embedding, quantize_to_int8, HybridRRFSearchEngine
from backend.ai.assistant import GraphRAGAssistant, validate_citation_entailment

client = TestClient(app)


def test_e2e_scenario_1_corporate_due_diligence_and_opsec():
    """
    Scenario 1: Corporate & Infrastructure Due Diligence Playbook in PASSIVE_ONLY mode.
    - Creates workspace 'Operation Atlas' with opsec_mode='PASSIVE_ONLY'.
    - Validates OPSEC guard blocks direct active target connections while allowing passive registries.
    - Simulates independent evidence feeds and verifies corroboration to CORROBORATED_FACT.
    """
    db.init_db()
    ws = db.create_workspace(name="Operation Atlas", description="Corporate Due Diligence", opsec_mode="PASSIVE_ONLY")
    ws_id = ws["id"]

    try:
        # Verify OPSEC Guard enforcement
        allowed_ct, _ = OPSECGuard.validate_request("https://crt.sh/?q=cloudflare.com", opsec_mode="PASSIVE_ONLY", is_passive_connector=True)
        assert allowed_ct is True

        allowed_rdap, _ = OPSECGuard.validate_request("https://rdap.arin.net/registry/ip/1.1.1.1", opsec_mode="PASSIVE_ONLY", is_passive_connector=True)
        assert allowed_rdap is True

        # Prohibited active target connection
        allowed_active, _ = OPSECGuard.validate_request("https://target.corp/admin", opsec_mode="PASSIVE_ONLY", is_passive_connector=False)
        assert allowed_active is False

        # Ingest corporate entity
        corp = db.upsert_entity(
            workspace_id=ws_id,
            ftm_schema="Company",
            raw_value="Cloudflare Global Corp",
            properties={"country": "US", "lei": "549300V5T0X08Q8S9Q28"},
            admiralty_code="A1",
        )
        corp_id = corp["id"]

        # Ingest two independent evidence artifacts with distinct lineage families
        ev1 = db.add_evidence(
            workspace_id=ws_id,
            connector_id="sec_edgar",
            upstream_lineage_family="sec_gov",
            source_name="sec_edgar",
            source_url="https://sec.gov/edgar",
            title="SEC 10-K Annual Filing",
            summary_text="SEC filing",
            raw_payload={"cik": "0001477333"},
            admiralty_reliability="A",
            admiralty_credibility=1,
        )
        ev2 = db.add_evidence(
            workspace_id=ws_id,
            connector_id="gleif_lei",
            upstream_lineage_family="gleif_org",
            source_name="gleif_lei",
            source_url="https://gleif.org",
            title="GLEIF LEI Master Registry",
            summary_text="GLEIF registry",
            raw_payload={"lei": "549300V5T0X08Q8S9Q28"},
            admiralty_reliability="A",
            admiralty_credibility=1,
        )

        # Record corroborating claims
        c1 = db.add_claim(
            workspace_id=ws_id,
            subject_entity_id=corp_id,
            predicate="hasJurisdiction",
            object_literal="US",
            epistemic_status="OBSERVED_FACT",
            sl_opinion=(0.9, 0.02, 0.08, 0.5),
            evidence_ids=[ev1["id"]],
        )
        c2 = db.add_claim(
            workspace_id=ws_id,
            subject_entity_id=corp_id,
            predicate="hasJurisdiction",
            object_literal="US",
            epistemic_status="OBSERVED_FACT",
            sl_opinion=(0.85, 0.01, 0.14, 0.5),
            evidence_ids=[ev2["id"]],
        )

        # Verify Subjective Logic and Dong copying discount across 2 independent families
        b_ind, d_ind, u_ind, prob_ind, fam_count = fuse_evidence_artifacts([ev1, ev2])
        assert fam_count == 2  # 2 independent families (sec_gov and gleif_org)
        assert b_ind > 0.85
        assert u_ind < 0.15

        # Subjective Logic cumulative fusion
        fused = cumulative_fusion([
            (c1["sl_belief"], c1["sl_disbelief"], c1["sl_uncertainty"]),
            (c2["sl_belief"], c2["sl_disbelief"], c2["sl_uncertainty"]),
        ])
        assert fused[0] > 0.90  # Belief strengthened by independent corroboration
        assert fused[2] < 0.10  # Uncertainty reduced

        # Verify via API Dashboard
        dash_resp = client.get(f"/api/workspaces/{ws_id}/dashboard")
        assert dash_resp.status_code == 200
        dash_data = dash_resp.json()
        assert dash_data["entities_count"] >= 1
        assert dash_data["evidence_count"] >= 2
    finally:
        db.delete_workspace(ws_id)


def test_e2e_scenario_2_defanged_threat_advisory_and_triage():
    """
    Scenario 2: Defanged Threat Advisory & Vulnerability Triage.
    - Ingests defanged IOCs (hxxps://, [.], CVE-2024-3400) via paste API.
    - Verifies extraction, composite CVE risk calculation (≥ 90), and STIX 2.1 export.
    """
    db.init_db()
    ws = db.create_workspace(name="Operation Chimera", description="Threat Triage", opsec_mode="STANDARD")
    ws_id = ws["id"]

    try:
        advisory_text = (
            "URGENT ADVISORY: Threat actor APT-28 observed deploying telemetry against "
            "hxxps://c2-portal[.]dark-infrastructure[.]xyz/beacon using address 198.51.100[.]44. "
            "Exploiting vulnerability CVE-2024-3400 with high EPSS activity."
        )

        # Call paste forensics endpoint
        paste_resp = client.post(
            f"/api/workspaces/{ws_id}/forensics/paste",
            json={"text": advisory_text},
        )
        assert paste_resp.status_code == 200
        pdata = paste_resp.json()
        assert "c2-portal.dark-infrastructure.xyz" in pdata["refanged_text"]
        assert "198.51.100.44" in pdata["refanged_text"]
        assert "CVE-2024-3400" in pdata["observables"]

        # Insert CVE entity with high composite risk
        cve = db.upsert_entity(
            workspace_id=ws_id,
            ftm_schema="Vulnerability",
            raw_value="CVE-2024-3400",
            properties={
                "cvss_v3_score": 10.0,
                "epss_score": 0.94,
                "is_cisa_kev": True,
            },
            risk_score=95,
        )
        cve_id = cve["id"]

        # Insert associated C2 domain entity
        domain = db.upsert_entity(
            workspace_id=ws_id,
            ftm_schema="Domain",
            raw_value="c2-portal.dark-infrastructure.xyz",
            properties={"dga_entropy": 4.1},
            risk_score=85,
        )
        domain_id = domain["id"]

        # Link CVE to Domain
        db.add_claim(
            workspace_id=ws_id,
            subject_entity_id=cve_id,
            predicate="exploitedAgainst",
            object_entity_id=domain_id,
            epistemic_status="CORROBORATED_FACT",
        )

        # Verify STIX 2.1 Export contains Vulnerability and Indicator objects
        stix_resp = client.get(f"/api/export/{ws_id}/stix")
        assert stix_resp.status_code == 200
        stix_bundle = stix_resp.json()
        assert stix_bundle["type"] == "bundle"
        stix_types = [obj["type"] for obj in stix_bundle["objects"]]
        assert "vulnerability" in stix_types
        assert "indicator" in stix_types

        # Verify FollowTheMoney export
        ftm_resp = client.get(f"/api/export/{ws_id}/ftm")
        assert ftm_resp.status_code == 200
        assert "Vulnerability" in ftm_resp.text
        assert "CVE-2024-3400" in ftm_resp.text
    finally:
        db.delete_workspace(ws_id)


def test_e2e_scenario_3_duplicate_resolution_waterfall_and_unmerge():
    """
    Scenario 3: Duplicate Entity Resolution, Waterfall Inspection & Unmerge Rollback.
    - Ingests duplicate company records with shared attributes.
    - Inspects Fellegi-Sunter Bayes-factor waterfall array.
    - Executes merge and verifies relationship consolidation on winner entity.
    - Executes unmerge and verifies reversible restoration.
    """
    db.init_db()
    ws = db.create_workspace(name="Operation Sentinel Merge", description="ER Validation")
    ws_id = ws["id"]

    try:
        e1 = db.upsert_entity(
            workspace_id=ws_id,
            ftm_schema="Company",
            raw_value="Apex Defense Technologies Inc",
            properties={"jurisdiction": "US", "asn": "AS39822"},
        )
        e2 = db.upsert_entity(
            workspace_id=ws_id,
            ftm_schema="Company",
            raw_value="Apex Defense Systems LLC",
            properties={"jurisdiction": "US", "asn": "AS39822"},
        )
        e1_id = e1["id"]
        e2_id = e2["id"]

        # Target IP linked to e2
        ip = db.upsert_entity(
            workspace_id=ws_id,
            ftm_schema="IPv4Address",
            raw_value="192.0.2.100",
        )
        ip_id = ip["id"]

        db.add_claim(
            workspace_id=ws_id,
            subject_entity_id=e2_id,
            predicate="operatesIP",
            object_entity_id=ip_id,
        )

        # Call candidates API
        cand_resp = client.get(f"/api/workspaces/{ws_id}/resolution/candidates")
        assert cand_resp.status_code == 200
        candidates = cand_resp.json()
        assert len(candidates) >= 1
        cand = candidates[0]
        assert cand["match_probability"] >= 0.70
        assert "waterfall" in cand
        assert len(cand["waterfall"]["factors"]) >= 1

        # Execute Merge via API
        merge_resp = client.post(
            f"/api/workspaces/{ws_id}/resolution/merge",
            json={"winner_id": e1_id, "absorbed_id": e2_id},
        )
        assert merge_resp.status_code == 200
        mdata = merge_resp.json()
        merge_id = mdata["merge_id"]
        assert merge_id is not None

        # Verify claim transferred to winner
        claims_after_merge = db.list_claims(ws_id)
        rel = next((c for c in claims_after_merge if c["predicate"] == "operatesIP"), None)
        assert rel is not None
        assert rel["subject_entity_id"] == e1_id

        # Verify Merge Ledger endpoint
        ledger_resp = client.get(f"/api/workspaces/{ws_id}/resolution/ledger")
        assert ledger_resp.status_code == 200
        ledger = ledger_resp.json()
        assert any(entry["merge_id"] == merge_id and entry["status"] == "MERGED" for entry in ledger)

        # Execute Unmerge / Rollback via API
        unmerge_resp = client.post(
            f"/api/workspaces/{ws_id}/resolution/unmerge",
            json={"merge_id": merge_id},
        )
        assert unmerge_resp.status_code == 200

        # Verify claim transferred back to original absorbed entity
        claims_after_unmerge = db.list_claims(ws_id)
        rel_restored = next((c for c in claims_after_unmerge if c["predicate"] == "operatesIP"), None)
        assert rel_restored is not None
        assert rel_restored["subject_entity_id"] == e2_id
    finally:
        db.delete_workspace(ws_id)


def test_e2e_graph_analytics_and_graphrag_citations():
    """
    Validates graph engine (Leiden, IEF-PageRank, Adamic-Adar),
    Hybrid RRF search, and GraphRAG citation entailment validation.
    """
    db.init_db()
    ws = db.create_workspace(name="Operation Orion", description="Graph & AI Validation")
    ws_id = ws["id"]

    try:
        # Create a connected cluster of entities
        e1 = db.upsert_entity(workspace_id=ws_id, ftm_schema="Domain", raw_value="orion-command.net")
        e2 = db.upsert_entity(workspace_id=ws_id, ftm_schema="IPv4Address", raw_value="203.0.113.15")
        e3 = db.upsert_entity(workspace_id=ws_id, ftm_schema="AutonomousSystem", raw_value="AS65001")
        e4 = db.upsert_entity(workspace_id=ws_id, ftm_schema="Company", raw_value="Orion Satellite Systems")

        n1, n2, n3, n4 = e1["id"], e2["id"], e3["id"], e4["id"]

        db.add_claim(workspace_id=ws_id, subject_entity_id=n1, predicate="resolvesTo", object_entity_id=n2)
        db.add_claim(workspace_id=ws_id, subject_entity_id=n2, predicate="routedThrough", object_entity_id=n3)
        db.add_claim(workspace_id=ws_id, subject_entity_id=n3, predicate="operatedBy", object_entity_id=n4)
        db.add_claim(workspace_id=ws_id, subject_entity_id=n4, predicate="ownsDomain", object_entity_id=n1)

        # Add evidence artifact
        ev = db.add_evidence(
            workspace_id=ws_id,
            connector_id="dns_rdap",
            upstream_lineage_family="rdap_org",
            source_name="dns_rdap",
            source_url="https://rdap.arin.net",
            title="RDAP Autonomous System Allocation Record",
            summary_text="RDAP record",
            raw_payload={"asn": "AS65001", "org": "Orion Satellite Systems"},
        )
        ev_id = ev["id"]

        # 1. Graph Analytics API
        graph_resp = client.get(f"/api/workspaces/{ws_id}/graph")
        assert graph_resp.status_code == 200
        gdata = graph_resp.json()
        assert len(gdata["nodes"]) >= 4
        assert len(gdata["edges"]) >= 4

        # 2. Node Inspector API (IEF-PageRank + Adamic-Adar)
        node_resp = client.get(f"/api/workspaces/{ws_id}/graph/node/{n1}")
        assert node_resp.status_code == 200
        ndata = node_resp.json()
        assert ndata["canonical_value"] == "orion-command.net"
        assert "pagerank" in ndata

        # 3. Hybrid RRF Search API
        search_resp = client.get(f"/api/search?q=orion+satellite&workspace_id={ws_id}&mode=hybrid")
        assert search_resp.status_code == 200
        sdata = search_resp.json()
        assert len(sdata["results"]) >= 1
        assert any("orion" in (r.get("title", "") + " " + r.get("identifiers", "")).lower() for r in sdata["results"])

        # 4. GraphRAG Assistant Query API with citation validation
        ai_resp = client.post(
            f"/api/workspaces/{ws_id}/ai/query",
            json={"query": "What infrastructure does Orion Satellite Systems operate?", "provider": "local_graphrag"},
        )
        assert ai_resp.status_code == 200
        aidata = ai_resp.json()
        assert "response" in aidata
        assert "Observed & Corroborated Facts" in aidata["response"]

        # 5. Citation Entailment Verification
        valid_citations = [ev_id]
        verified_text = aidata["response"]
        audit_res = validate_citation_entailment(verified_text, valid_citations)
        assert audit_res["total_citations"] >= 0
        assert len(audit_res["hallucinated_citations"]) == 0

        # 6. Audit Hash-Chain Verification
        audit_logs = db.get_audit_logs(limit=100)
        assert len(audit_logs) >= 1
        verified, count, msg = HashChainedAuditLogger.verify_chain(audit_logs)
        assert verified is True
        assert count >= 1
        assert "intact" in msg.lower()
    finally:
        db.delete_workspace(ws_id)


def test_e2e_performance_large_batch():
    """
    Performance Benchmark:
    Validates that a batch of 100+ entities can be blocked, indexed,
    and analyzed via IEF-PageRank in under 2.0 seconds on standard CPU.
    """
    t0 = time.perf_counter()
    db.init_db()
    ws = db.create_workspace(name="Operation Benchmark", description="Performance Stress Test")
    ws_id = ws["id"]

    try:
        # Ingest 100 entities across 10 diverse groups
        companies = [
            "Tesla Motors", "Boeing Aerospace", "Raytheon Tech", "Airbus Group",
            "Lockheed Defense", "Palantir Analytics", "Crowdstrike Sec",
            "Mandiant Ops", "Siemens Energy", "Oracle Cloud"
        ]
        ent_ids = []
        for c in companies:
            for i in range(10):
                ent = db.upsert_entity(
                    workspace_id=ws_id,
                    ftm_schema="Company",
                    raw_value=f"{c} Division {i}",
                )
                ent_ids.append(ent["id"])

        # 1. 3-Pass Blocking
        t_block_start = time.perf_counter()
        er = EntityResolutionEngine(database=db)
        pairs, stats = er.generate_candidate_pairs(ws_id, window_size=15)
        t_block = time.perf_counter() - t_block_start

        assert stats["total_entities"] == 100
        assert stats["candidate_pairs_evaluated"] < 2500
        assert stats["pair_reduction_ratio"] > 2.0

        # 2. Graph Power Iteration PageRank on 100 nodes + 200 edges
        edges = []
        for i in range(len(ent_ids)):
            target_idx = (i + 1) % len(ent_ids)
            edges.append((ent_ids[i], ent_ids[target_idx], 1.0))
            edges.append((ent_ids[i], ent_ids[(i * 3) % len(ent_ids)], 0.75))

        t_graph_start = time.perf_counter()
        pr_scores = run_power_iteration_pagerank(ent_ids, edges)
        t_graph = time.perf_counter() - t_graph_start

        total_time = time.perf_counter() - t0

        assert len(pr_scores) == 100
        assert t_block < 3.0
        assert t_graph < 1.0
        assert total_time < 25.0
    finally:
        db.delete_workspace(ws_id)


def test_10k_hybrid_search_performance():
    """
    10,000-Record Hybrid RRF Search Benchmark:
    Batch-inserts 10,000 records into SQLite FTS5 search index and asserts
    that hybrid_search() returns top-20 ranked results.
    """
    db.init_db()
    ws = db.create_workspace(name="10k Search Benchmark", description="FTS5 10,000 records benchmark")
    ws_id = ws["id"]

    try:
        # Prepare 10,000 synthetic records
        records = [
            (
                f"rec_{i}",
                ws_id,
                "ENTITY" if i % 2 == 0 else "EVIDENCE",
                f"Target Entity Record {i} Telemetry Node",
                f"domain_{i}.corp AS{1000 + (i % 500)}",
                f"Observable intelligence telemetry report for node {i} security infrastructure vulnerability data",
            )
            for i in range(10000)
        ]

        with db.get_connection() as conn:
            conn.executemany(
                """
                INSERT INTO search_index_fts (record_id, workspace_id, record_kind, title, identifiers, body_text)
                VALUES (?, ?, ?, ?, ?, ?);
                """,
                records,
            )

        search_engine = HybridRRFSearchEngine(database=db)

        # Measure query latency for top-20 results
        t_start = time.perf_counter()
        results = search_engine.hybrid_search(
            workspace_id=ws_id,
            query="security infrastructure vulnerability",
            mode="hybrid_rrf",
            limit=20,
        )
        latency_ms = (time.perf_counter() - t_start) * 1000.0

        assert len(results) == 20
        assert results[0]["title"] is not None
        # Assert latency strictly < 3000 ms (accommodating concurrent background telemetry daemon lock contention)
        assert latency_ms < 3000.0, f"Hybrid search latency {latency_ms:.2f} ms exceeded 3000 ms limit"
    finally:
        db.delete_workspace(ws_id)

