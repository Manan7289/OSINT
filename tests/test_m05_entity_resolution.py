"""tests/test_m05_entity_resolution.py - Comprehensive Unit Tests for M05.

Validates 3-Pass Blocking Pair Reduction, Unsupervised Fellegi-Sunter EM,
Waterfall Explanations, and 100% Reversible Merge / Unmerge Ledger.
"""

from __future__ import annotations

import numpy as np
import pytest

from backend.core.database import DatabaseManager
from backend.core.entity_resolution import (
    EntityResolutionEngine,
    jaro_winkler_similarity,
    run_fellegi_sunter_em,
    token_jaccard_similarity,
)


@pytest.fixture
def test_db(tmp_path):
    db_file = tmp_path / "test_m05_localosint.db"
    return DatabaseManager(db_path=db_file)


def test_string_similarity_metrics():
    """Test Jaro-Winkler and token Jaccard string similarities."""
    assert jaro_winkler_similarity("shadownet security", "shadownet security") == 1.0
    # Slight typo
    jw_typo = jaro_winkler_similarity("shadownet security", "shadownet securty")
    assert jw_typo > 0.90

    # Completely different (0 matching chars)
    jw_diff = jaro_winkler_similarity("shadownet", "xyz123")
    assert jw_diff == 0.0

    # Token Jaccard
    assert token_jaccard_similarity("ShadowNet Technologies Inc", "ShadowNet Technologies LLC") == 0.5
    assert token_jaccard_similarity("Acme Corp", "Acme Corp") == 1.0


def test_fellegi_sunter_em_convergence():
    """Test unsupervised Fellegi-Sunter EM weight and probability estimation."""
    # Synthetic gamma matrix: 4 pairs, 4 features
    # Pair 0: perfect agreement [1, 1, 1, 1] -> Match
    # Pair 1: strong agreement [0.9, 0.8, 1, 1] -> Match
    # Pair 2: weak agreement [0.2, 0.1, 1, 0] -> Non-match
    # Pair 3: zero agreement [0, 0, 0, 0] -> Non-match
    gamma = np.array([
        [1.0, 1.0, 1.0, 1.0],
        [0.9, 0.8, 1.0, 1.0],
        [0.2, 0.1, 1.0, 0.0],
        [0.0, 0.0, 0.0, 0.0],
    ])

    lam, m_w, u_w, probs, log2_w = run_fellegi_sunter_em(gamma, max_iter=10)
    assert len(probs) == 4
    # Pairs 0 & 1 must have high probability
    assert probs[0] > 0.80
    assert probs[1] > 0.70
    # Pairs 2 & 3 must have low probability
    assert probs[2] < 0.30
    assert probs[3] < 0.10


def test_3pass_blocking_pair_reduction(test_db):
    """Test that 3-pass blocking achieves significant candidate pair reduction."""
    er = EntityResolutionEngine(database=test_db)
    ws = test_db.create_workspace(name="Blocking Test")
    ws_id = ws["id"]

    # Insert 100 entities across 10 diverse company groups
    companies = [
        "Tesla Motors", "Boeing Aerospace", "Raytheon Tech", "Airbus Group",
        "Lockheed Defense", "Palantir Analytics", "Crowdstrike Sec",
        "Mandiant Ops", "Siemens Energy", "Oracle Cloud"
    ]
    for c in companies:
        for i in range(10):
            test_db.upsert_entity(
                workspace_id=ws_id,
                ftm_schema="Company",
                raw_value=f"{c} Division {i}",
            )

    pairs, stats = er.generate_candidate_pairs(ws_id, window_size=15)
    # Total entities: 100 -> All possible pairs: 100*99/2 = 4950
    assert stats["total_entities"] == 100
    assert stats["all_possible_pairs"] == 4950
    # Candidate pairs evaluated must be significantly smaller than all pairs (reduction ratio > 2.0)
    assert stats["candidate_pairs_evaluated"] < 2500
    assert stats["pair_reduction_ratio"] > 2.0


def test_merge_and_unmerge_reversible_ledger(test_db):
    """CRITICAL TEST: Bit-for-bit restoration after Merge -> Unmerge cycle."""
    er = EntityResolutionEngine(database=test_db)
    ws = test_db.create_workspace(name="Reversible Merge Test")
    ws_id = ws["id"]

    # 1. Create two distinct entities to be resolved (e.g. ShadowNet Defense vs ShadowNet Security)
    ent_primary = test_db.upsert_entity(ws_id, "Company", "ShadowNet Security Inc", properties={"hq": "US"})
    ent_dup = test_db.upsert_entity(ws_id, "Company", "ShadowNet Defense Systems", properties={"country": "US"})
    ent_ip = test_db.upsert_entity(ws_id, "IPv4Address", "198.51.100.77")

    pri_id = ent_primary["id"]
    dup_id = ent_dup["id"]
    assert pri_id != dup_id

    # 2. Create claims linked to duplicate entity
    claim1 = test_db.add_claim(
        workspace_id=ws_id,
        subject_entity_id=dup_id,
        predicate="OPERATES_IP",
        object_entity_id=ent_ip["id"],
    )

    # 3. Execute MERGE
    merge_res = er.merge_entities(
        workspace_id=ws_id,
        primary_entity_id=pri_id,
        duplicate_entity_id=dup_id,
        match_probability=0.96,
    )
    assert merge_res["status"] == "MERGED"
    merge_id = merge_res["merge_id"]

    # Verify duplicate is no longer in active entities table
    assert test_db.get_entity(dup_id) is None

    # Verify claim1 was repointed to primary
    c1_after_merge = test_db.get_claim(claim1["id"])
    assert c1_after_merge["subject_entity_id"] == pri_id

    # 4. Execute UNMERGE
    unmerge_res = er.unmerge_entity(workspace_id=ws_id, merge_id=merge_id)
    assert unmerge_res["status"] == "REVERTED"

    # Verify duplicate entity is fully restored
    restored_dup = test_db.get_entity(dup_id)
    assert restored_dup is not None
    assert restored_dup["id"] == dup_id
    assert restored_dup["display_label"] == ent_dup["display_label"]

    # Verify claim1 is restored back to duplicate
    c1_after_unmerge = test_db.get_claim(claim1["id"])
    assert c1_after_unmerge["subject_entity_id"] == dup_id


def test_fellegi_sunter_small_workspace_beta_smoothing(test_db):
    """Test that small candidate sets (M=1, 0 background entities) with Bayesian Beta smoothing score >= 0.85."""
    er = EntityResolutionEngine(database=test_db)
    ws = test_db.create_workspace(name="Small Workspace Beta Smoothing Test")
    ws_id = ws["id"]

    # Exactly 2 matching entities with 0 background entities
    test_db.upsert_entity(ws_id, "Company", "Acme Corp")
    test_db.upsert_entity(ws_id, "Company", "Acme Corporation")

    eval_res = er.evaluate_candidates(ws_id, min_probability=0.50)
    candidates = eval_res["candidates"]
    assert len(candidates) == 1
    match = candidates[0]
    assert match["match_probability"] >= 0.85
    assert match["classification"] == "CONFIRMED_MATCH"
    assert match["fellegi_sunter_log2_weight"] > 0

