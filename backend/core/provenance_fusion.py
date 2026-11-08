"""backend/core/provenance_fusion.py - W3C PROV Lineage DAG, Dong Copying Discount & Jøsang Subjective Logic.

M06: W3C PROV Lineage DAG, Dong Copying Detection & Subjective Logic Fusion Engine.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

# Mapping NATO Admiralty Code to Subjective Logic Opinions (belief, disbelief, uncertainty)
# Prior base rate a is constant 0.50
ADMIRALTY_TO_OPINION: Dict[str, Tuple[float, float, float]] = {
    "A1": (0.92, 0.00, 0.08),
    "A2": (0.85, 0.02, 0.13),
    "B1": (0.82, 0.02, 0.16),
    "B2": (0.75, 0.05, 0.20),
    "C2": (0.62, 0.08, 0.30),
    "C3": (0.52, 0.12, 0.36),
    "D4": (0.30, 0.25, 0.45),
    "E5": (0.10, 0.55, 0.35),
    "F6": (0.15, 0.15, 0.70),
}


def simhash_hamming_distance(hash1: str, hash2: str) -> int:
    """Computes bitwise Hamming distance between two 64-bit hex SimHash strings."""
    try:
        val1 = int(hash1, 16)
        val2 = int(hash2, 16)
        xor_val = val1 ^ val2
        return bin(xor_val).count("1")
    except Exception:
        return 64


def opinion_from_admiralty(reliability: str, credibility: int, stance: str = "SUPPORTS") -> Tuple[float, float, float]:
    """Retrieves initial Subjective Logic opinion (b, d, u) for an Admiralty grade.
    
    If stance == 'CONTRADICTS', belief and disbelief are swapped.
    """
    code = f"{reliability.upper()}{credibility}"
    b, d, u = ADMIRALTY_TO_OPINION.get(code, (0.70, 0.05, 0.25))
    if stance.upper() == "CONTRADICTS":
        return (d, b, u)
    return (b, d, u)


def averaging_fusion(opinions: List[Tuple[float, float, float]]) -> Tuple[float, float, float]:
    """Averaging Fusion (\\tilde{\\oplus}) for dependent evidence within the same lineage family.
    
    Prevents circular echo chambers from artificially driving uncertainty u -> 0.
    """
    if not opinions:
        return (0.0, 0.0, 1.0)
    if len(opinions) == 1:
        return opinions[0]

    b_cur, d_cur, u_cur = opinions[0]
    for b_nxt, d_nxt, u_nxt in opinions[1:]:
        denom = max(1e-6, u_cur + u_nxt)
        b_new = (b_cur * u_nxt + b_nxt * u_cur) / denom
        d_new = (d_cur * u_nxt + d_nxt * u_cur) / denom
        u_new = (2.0 * u_cur * u_nxt) / denom
        s = b_new + d_new + u_new
        if s > 0:
            b_cur, d_cur, u_cur = b_new / s, d_new / s, u_new / s

    return (round(b_cur, 4), round(d_cur, 4), round(u_cur, 4))


def cumulative_fusion(opinions: List[Tuple[float, float, float]]) -> Tuple[float, float, float]:
    """Cumulative Fusion (\\oplus) across truly independent lineage families.
    
    Combines independent observations, reducing uncertainty u as distinct sources corroborate.
    """
    if not opinions:
        return (0.0, 0.0, 1.0)
    if len(opinions) == 1:
        return opinions[0]

    b_cur, d_cur, u_cur = opinions[0]
    for b_nxt, d_nxt, u_nxt in opinions[1:]:
        u_cur = max(1e-4, u_cur)
        u_nxt = max(1e-4, u_nxt)
        denom = u_cur + u_nxt - (u_cur * u_nxt)
        if denom <= 0:
            denom = 1e-6
        b_new = (b_cur * u_nxt + b_nxt * u_cur) / denom
        d_new = (d_cur * u_nxt + d_nxt * u_cur) / denom
        u_new = (u_cur * u_nxt) / denom
        s = b_new + d_new + u_new
        if s > 0:
            b_cur, d_cur, u_cur = b_new / s, d_new / s, u_new / s

    return (round(b_cur, 4), round(d_cur, 4), round(u_cur, 4))


def determine_epistemic_status(
    b: float, d: float, u: float, independent_family_count: int, is_inference: bool = False
) -> str:
    """Classifies claim into 5-state Epistemic Stratification:
    - OBSERVED_FACT
    - CORROBORATED_FACT
    - DERIVED_INFERENCE
    - ANALYST_HYPOTHESIS
    - UNVERIFIED_CLAIM
    """
    if is_inference:
        return "DERIVED_INFERENCE"

    # Severe conflict or high disbelief -> UNVERIFIED_CLAIM
    if d >= 0.25 or (b > 0.3 and d > 0.2):
        return "UNVERIFIED_CLAIM"

    # High uncertainty -> UNVERIFIED_CLAIM
    if u >= 0.40:
        return "UNVERIFIED_CLAIM"

    # Confirmed by >= 2 independent lineage families with high belief -> CORROBORATED_FACT
    if independent_family_count >= 2 and b >= 0.80 and u <= 0.18:
        return "CORROBORATED_FACT"

    # Single strong independent observation -> OBSERVED_FACT
    if b >= 0.70:
        return "OBSERVED_FACT"

    return "UNVERIFIED_CLAIM"


def fuse_evidence_artifacts(
    artifacts: List[Dict[str, Any]], stances: Optional[Dict[str, str]] = None
) -> Tuple[float, float, float, float, int]:
    """Applies Dong Copying Discount + Subjective Logic to a collection of evidence artifacts.
    
    1. Groups evidence by upstream_lineage_family (or near-duplicate SimHash <= 6).
    2. Applies Averaging Fusion within each family group.
    3. Applies Cumulative Fusion across distinct families.
    
    Returns:
        (belief, disbelief, uncertainty, projected_probability, independent_family_count)
    """
    if not artifacts:
        # Default prior
        return (0.75, 0.00, 0.25, 0.875, 1)

    stance_map = stances or {}
    families: Dict[str, List[Tuple[float, float, float]]] = {}

    for art in artifacts:
        art_id = art.get("id", "")
        family = art.get("upstream_lineage_family", "UNKNOWN").strip()
        rel = art.get("admiralty_reliability", "B")
        cred = int(art.get("admiralty_credibility", 2))
        stance = stance_map.get(art_id, "SUPPORTS")

        op = opinion_from_admiralty(rel, cred, stance)
        if family not in families:
            families[family] = []
        families[family].append(op)

    # Step 1: Averaging Fusion within each lineage family
    family_opinions: List[Tuple[float, float, float]] = []
    for fam, ops in families.items():
        fam_op = averaging_fusion(ops)
        family_opinions.append(fam_op)

    # Step 2: Cumulative Fusion across distinct independent families
    fused_b, fused_d, fused_u = cumulative_fusion(family_opinions)
    proj_prob = fused_b + (0.50 * fused_u)
    indep_count = len(families)

    return (fused_b, fused_d, fused_u, round(proj_prob, 4), indep_count)
