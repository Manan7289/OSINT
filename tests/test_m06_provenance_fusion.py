"""tests/test_m06_provenance_fusion.py - Comprehensive Unit Tests for M06.

Validates Dong Copying Discount, Jøsang Subjective Logic Belief Fusion,
Echo-Chamber Prevention, Conflict Detection, and Epistemic Stratification.
"""

from __future__ import annotations

import pytest
from backend.core.provenance_fusion import (
    averaging_fusion,
    cumulative_fusion,
    determine_epistemic_status,
    fuse_evidence_artifacts,
    opinion_from_admiralty,
    simhash_hamming_distance,
)


def test_simhash_hamming_distance():
    """Test bitwise Hamming distance between 64-bit hex strings."""
    assert simhash_hamming_distance("0000000000000000", "0000000000000000") == 0
    assert simhash_hamming_distance("0000000000000000", "0000000000000001") == 1
    assert simhash_hamming_distance("0000000000000000", "ffffffffffffffff") == 64
    assert simhash_hamming_distance("invalid", "invalid") == 64


def test_subjective_logic_invariants():
    """Verify that b + d + u == 1.0 across all operations."""
    op1 = opinion_from_admiralty("A", 1)  # (0.92, 0.00, 0.08)
    assert round(sum(op1), 2) == 1.0

    op2 = opinion_from_admiralty("B", 2)  # (0.75, 0.05, 0.20)
    assert round(sum(op2), 2) == 1.0

    # Averaging fusion invariant
    avg_op = averaging_fusion([op1, op2])
    assert abs(sum(avg_op) - 1.0) < 1e-3

    # Cumulative fusion invariant
    cum_op = cumulative_fusion([op1, op2])
    assert abs(sum(cum_op) - 1.0) < 1e-3


def test_echo_chamber_dong_discount():
    """CRITICAL TEST: 5 syndicated copies from 1 lineage family MUST NOT inflate confidence.
    
    2 independent authoritative sources (Cumulative Fusion) must yield lower uncertainty
    and higher corroboration than 5 syndicated copies of the same source (Averaging Fusion).
    """
    # 5 syndicated reports from the same upstream family (e.g., 'Syndicated_Newswire')
    syndicated_evidence = [
        {"id": f"ev_{i}", "upstream_lineage_family": "Syndicated_Newswire", "admiralty_reliability": "B", "admiralty_credibility": 2}
        for i in range(5)
    ]
    b_syn, d_syn, u_syn, prob_syn, fam_count_syn = fuse_evidence_artifacts(syndicated_evidence)
    assert fam_count_syn == 1
    # Averaging fusion preserves uncertainty around original single source (u ~ 0.20)
    assert u_syn >= 0.19

    # 2 independent authoritative sources from distinct families ('NIST' and 'CISA')
    independent_evidence = [
        {"id": "ev_nist", "upstream_lineage_family": "NIST", "admiralty_reliability": "A", "admiralty_credibility": 1},
        {"id": "ev_cisa", "upstream_lineage_family": "CISA", "admiralty_reliability": "A", "admiralty_credibility": 1},
    ]
    b_ind, d_ind, u_ind, prob_ind, fam_count_ind = fuse_evidence_artifacts(independent_evidence)
    assert fam_count_ind == 2

    # Cumulative fusion across independent families strictly reduces uncertainty
    assert u_ind < u_syn
    # Belief from 2 independent A1 sources strictly exceeds belief from 5 syndicated copies
    assert b_ind > b_syn


def test_contradiction_and_conflict_detection():
    """Test that conflicting evidence inflates disbelief and demotes to UNVERIFIED_CLAIM."""
    supporting_ev = [
        {"id": "ev_1", "upstream_lineage_family": "Source_Alpha", "admiralty_reliability": "B", "admiralty_credibility": 2}
    ]
    contradicting_ev = [
        {"id": "ev_2", "upstream_lineage_family": "Source_Beta", "admiralty_reliability": "B", "admiralty_credibility": 2}
    ]
    all_ev = supporting_ev + contradicting_ev
    stances = {"ev_1": "SUPPORTS", "ev_2": "CONTRADICTS"}

    b, d, u, p, count = fuse_evidence_artifacts(all_ev, stances=stances)
    assert count == 2
    # Disbelief must be significantly non-zero
    assert d >= 0.25

    # Status must be UNVERIFIED_CLAIM due to conflict
    status = determine_epistemic_status(b, d, u, independent_family_count=count)
    assert status == "UNVERIFIED_CLAIM"


def test_epistemic_stratification_rules():
    """Test 5-state epistemic stratification classification."""
    # Single observation -> OBSERVED_FACT
    assert determine_epistemic_status(b=0.75, d=0.05, u=0.20, independent_family_count=1) == "OBSERVED_FACT"

    # Multi-source corroborated -> CORROBORATED_FACT
    assert determine_epistemic_status(b=0.88, d=0.01, u=0.11, independent_family_count=2) == "CORROBORATED_FACT"

    # Derived inference
    assert determine_epistemic_status(b=0.90, d=0.01, u=0.09, independent_family_count=2, is_inference=True) == "DERIVED_INFERENCE"

    # High uncertainty -> UNVERIFIED_CLAIM
    assert determine_epistemic_status(b=0.30, d=0.10, u=0.60, independent_family_count=1) == "UNVERIFIED_CLAIM"
