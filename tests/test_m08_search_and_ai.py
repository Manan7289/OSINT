"""tests/test_m08_search_and_ai.py - Comprehensive Unit Tests for M08.

Validates 384-d INT8 Vector Quantization, Reciprocal Rank Fusion (k=60),
GraphRAG Subgraph Synthesis, and Post-Generation Citation Entailment Validation.
"""

from __future__ import annotations

import numpy as np
import pytest

from backend.ai.assistant import GraphRAGAssistant, validate_citation_entailment
from backend.ai.search_rrf import (
    HybridRRFSearchEngine,
    dequantize_from_int8,
    quantize_to_int8,
    reciprocal_rank_fusion,
    text_to_embedding,
)
from backend.core.database import DatabaseManager


@pytest.fixture
def test_db(tmp_path):
    db_file = tmp_path / "test_m08_localosint.db"
    return DatabaseManager(db_path=db_file)


def test_int8_quantization_and_cosine_fidelity():
    """Test 384-d float32 vector embedding and INT8 quantization fidelity."""
    text = "Advanced persistent threat group deploying backdoor malware"
    vec_float = text_to_embedding(text)
    assert len(vec_float) == 384
    assert abs(np.linalg.norm(vec_float) - 1.0) < 1e-3

    # Quantize to INT8
    blob, scale = quantize_to_int8(vec_float)
    assert len(blob) == 384
    assert scale > 0.0

    # Dequantize
    vec_reconstructed = dequantize_from_int8(blob, scale)
    # Cosine similarity between original float and dequantized INT8 vector must be > 0.98
    sim = np.dot(vec_float, vec_reconstructed) / (np.linalg.norm(vec_float) * np.linalg.norm(vec_reconstructed))
    assert sim > 0.98


def test_reciprocal_rank_fusion_k60():
    """Test Reciprocal Rank Fusion combines dual rankings correctly."""
    bm25_list = [
        {"record_id": "doc_A", "title": "Doc A"},  # Rank 1
        {"record_id": "doc_B", "title": "Doc B"},  # Rank 2
        {"record_id": "doc_C", "title": "Doc C"},  # Rank 3
    ]
    vec_list = [
        {"record_id": "doc_B", "title": "Doc B"},  # Rank 1
        {"record_id": "doc_A", "title": "Doc A"},  # Rank 2
        {"record_id": "doc_D", "title": "Doc D"},  # Rank 3
    ]

    fused = reciprocal_rank_fusion(bm25_list, vec_list, k=60, top_n=5)
    # doc_A: 1/(60+1) + 1/(60+2) = 1/61 + 1/62 = 0.01639 + 0.01612 = 0.03251
    # doc_B: 1/(60+2) + 1/(60+1) = 0.03251 (tied at top)
    top_ids = [fused[0]["record_id"], fused[1]["record_id"]]
    assert "doc_A" in top_ids
    assert "doc_B" in top_ids

    # Both doc_A and doc_B must beat single-list items (doc_C, doc_D)
    assert fused[0]["rrf_score"] > fused[2]["rrf_score"]
    assert fused[1]["rrf_score"] > fused[3]["rrf_score"]


def test_citation_entailment_validator():
    """Test verification of [ev_xxxx] citation tags against evidence database."""
    valid_ids = {"ev_1234abcd5678", "ev_9876fedc4321"}
    text_with_valid = "Threat group active on C2 [ev_1234abcd5678] with malware payload [ev_9876fedc4321]."
    audit_valid = validate_citation_entailment(text_with_valid, valid_ids)

    assert audit_valid["total_citations"] == 2
    assert audit_valid["citation_integrity_score"] == 1.0
    assert len(audit_valid["hallucinated_citations"]) == 0

    # Text with hallucinated citation
    text_with_hallucination = "Attacker identified [ev_1234abcd5678] and linked to fake record [ev_fake99999999]."
    audit_hallucinated = validate_citation_entailment(text_with_hallucination, valid_ids)

    assert audit_hallucinated["total_citations"] == 2
    assert audit_hallucinated["citation_integrity_score"] == 0.50
    assert "ev_fake99999999" in audit_hallucinated["hallucinated_citations"]


def test_graphrag_report_compilation(test_db):
    """Test deterministic local GraphRAG Subgraph report generation."""
    assistant = GraphRAGAssistant(database=test_db)
    ws = test_db.create_workspace(name="GraphRAG Test")
    ws_id = ws["id"]

    # Seed entities
    ent_domain = test_db.upsert_entity(ws_id, "Domain", "target-c2.net")
    ent_ip = test_db.upsert_entity(ws_id, "IPv4Address", "185.220.101.55")

    # Seed evidence
    ev = test_db.add_evidence(
        workspace_id=ws_id,
        connector_id="dns_doh",
        upstream_lineage_family="Cloudflare",
        source_name="Cloudflare DoH",
        source_url="https://cloudflare-dns.com",
        title="DNS Resolution Report",
        summary_text="Resolved target-c2.net to 185.220.101.55",
        raw_payload={"ip": "185.220.101.55"},
        admiralty_reliability="A",
        admiralty_credibility=1,
    )

    # Seed claim with evidence attachment
    test_db.add_claim(
        workspace_id=ws_id,
        subject_entity_id=ent_domain["id"],
        predicate="RESOLVES_TO",
        object_entity_id=ent_ip["id"],
        epistemic_status="CORROBORATED_FACT",
        evidence_ids=[ev["id"]],
    )

    # Generate report
    report = assistant.generate_and_save_report(
        workspace_id=ws_id,
        title="Operation Sentinel Intelligence Briefing",
        query="target-c2.net",
    )

    assert report["title"] == "Operation Sentinel Intelligence Briefing"
    assert "### 1. Observed & Corroborated Facts" in report["content_markdown"]
    assert "### 4. Citation Verification Audit" in report["content_markdown"]
    assert f"[{ev['id']}]" in report["content_markdown"]

    # Verify audit
    assert report["citation_audit"]["citation_integrity_score"] == 1.0
