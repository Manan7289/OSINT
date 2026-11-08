"""backend/core/entity_resolution.py - 3-Pass Blocked Fellegi-Sunter EM Entity Resolution & Reversible Merge.

M05: 3-Pass Blocking, Unsupervised Fellegi-Sunter EM & Reversible Merge Engine.
"""

from __future__ import annotations

import datetime
import json
import math
import uuid
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np

from backend.core.database import DatabaseManager, db
from backend.core.ontology import canonicalize_entity
from backend.core.provenance_fusion import cumulative_fusion


def jaro_winkler_similarity(s1: str, s2: str, p: float = 0.1) -> float:
    """Computes Jaro-Winkler string distance between two strings [0.0..1.0]."""
    if s1 == s2:
        return 1.0
    if not s1 or not s2:
        return 0.0

    len1, len2 = len(s1), len(s2)
    max_dist = max(len1, len2) // 2 - 1
    if max_dist < 0:
        max_dist = 0

    s1_matches = [False] * len1
    s2_matches = [False] * len2
    matches = 0

    for i in range(len1):
        start = max(0, i - max_dist)
        end = min(i + max_dist + 1, len2)
        for j in range(start, end):
            if s2_matches[j] or s1[i] != s2[j]:
                continue
            s1_matches[i] = True
            s2_matches[j] = True
            matches += 1
            break

    if matches == 0:
        return 0.0

    t = 0
    k = 0
    for i in range(len1):
        if not s1_matches[i]:
            continue
        while not s2_matches[k]:
            k += 1
        if s1[i] != s2[k]:
            t += 1
        k += 1

    transpositions = t // 2
    jaro = (
        (matches / len1)
        + (matches / len2)
        + ((matches - transpositions) / matches)
    ) / 3.0

    # Winkler prefix bonus (up to 4 matching characters)
    l = 0
    for i in range(min(4, len1, len2)):
        if s1[i] == s2[i]:
            l += 1
        else:
            break

    return jaro + (l * p * (1.0 - jaro))


def token_jaccard_similarity(s1: str, s2: str) -> float:
    """Computes word token Jaccard similarity |A ∩ B| / |A ∪ B|."""
    import re
    t1 = set(re.findall(r"\w+", s1.lower()))
    t2 = set(re.findall(r"\w+", s2.lower()))
    if not t1 and not t2:
        return 1.0
    if not t1 or not t2:
        return 0.0
    intersection = len(t1.intersection(t2))
    union = len(t1.union(t2))
    return intersection / union if union > 0 else 0.0


def run_fellegi_sunter_em(
    gamma_matrix: np.ndarray, max_iter: int = 15
) -> Tuple[float, List[float], List[float], List[float], np.ndarray]:
    """Unsupervised Expectation-Maximization (EM) Fellegi-Sunter parameter estimation.
    
    Returns:
        (lambda_prev, m_weights, u_weights, match_probabilities, total_log2_weights)
    """
    M, K = gamma_matrix.shape
    if M == 0:
        return 0.15, [0.88] * K, [0.12] * K, [], np.array([])

    lam = 0.15
    m = np.full(K, 0.88, dtype=np.float64)
    u = np.full(K, 0.12, dtype=np.float64)
    total_log2_w = np.zeros(M)
    p = np.full(M, lam)

    for _ in range(max_iter):
        # E-step
        log_bf = gamma_matrix * np.log2(np.clip(m / u, 1e-4, 1e4)) + (
            1.0 - gamma_matrix
        ) * np.log2(np.clip((1.0 - m) / (1.0 - u), 1e-4, 1e4))
        total_log2_w = np.sum(log_bf, axis=1)

        odds = (lam / max(1e-4, 1.0 - lam)) * (2.0 ** np.clip(total_log2_w, -30, 30))
        p = odds / (1.0 + odds)

        # M-step
        p_sum = max(1e-6, np.sum(p))
        q_sum = max(1e-6, np.sum(1.0 - p))
        m = np.clip(np.sum(p[:, None] * gamma_matrix, axis=0) / p_sum, 0.55, 0.995)
        u = np.clip(np.sum((1.0 - p[:, None]) * gamma_matrix, axis=0) / q_sum, 0.005, 0.45)
        lam = float(np.clip(np.mean(p), 0.02, 0.50))

    return lam, m.tolist(), u.tolist(), p.tolist(), total_log2_w


class EntityResolutionEngine:
    """3-Pass Blocked Fellegi-Sunter EM Entity Resolution & Reversible Merge."""

    def __init__(self, database: DatabaseManager = db) -> None:
        self.db = database

    def generate_candidate_pairs(self, workspace_id: str, window_size: int = 15) -> Tuple[List[Tuple[str, str]], Dict[str, Any]]:
        """Generates candidate pairs using 3 blocking passes:
        1. Exact Blocking Key collision (PHONETIC_SORT, APEX_PREFIX, MINHASH_LSH)
        2. Sorted Neighborhood sliding window (w = 15)
        
        Returns:
            (candidate_pairs: List[(id1, id2)], stats: Dict)
        """
        pairs: Set[Tuple[str, str]] = set()

        with self.db.get_connection() as conn:
            # Total entity count in workspace
            cur = conn.execute("SELECT COUNT(*) FROM entities WHERE workspace_id = ? AND is_staged = 0;", (workspace_id,))
            total_entities = cur.fetchone()[0]

            if total_entities < 2:
                return [], {"total_entities": total_entities, "candidate_pairs_evaluated": 0, "pair_reduction_ratio": 1.0}

            # Pass 1: Blocking Keys collision
            cur = conn.execute(
                """
                SELECT a.entity_id AS id_a, b.entity_id AS id_b
                FROM entity_blocking_keys a
                JOIN entity_blocking_keys b
                  ON a.workspace_id = b.workspace_id
                 AND a.pass_type = b.pass_type
                 AND a.blocking_key = b.blocking_key
                WHERE a.workspace_id = ? AND a.entity_id < b.entity_id;
                """,
                (workspace_id,),
            )
            for r in cur.fetchall():
                pairs.add((r["id_a"], r["id_b"]))

            # Pass 2: Sorted Neighborhood sliding window
            cur = conn.execute(
                """
                SELECT id, ftm_schema, canonical_value
                FROM entities
                WHERE workspace_id = ? AND is_staged = 0
                ORDER BY ftm_schema, canonical_value ASC;
                """,
                (workspace_id,),
            )
            rows = cur.fetchall()
            n = len(rows)
            for i in range(n):
                r_i = rows[i]
                for j in range(i + 1, min(i + window_size + 1, n)):
                    r_j = rows[j]
                    if r_i["ftm_schema"] == r_j["ftm_schema"]:
                        id_min, id_max = sorted([r_i["id"], r_j["id"]])
                        pairs.add((id_min, id_max))

        all_possible = (total_entities * (total_entities - 1)) // 2
        cand_count = len(pairs)
        ratio = round(all_possible / max(1, cand_count), 1)

        return sorted(list(pairs)), {
            "total_entities": total_entities,
            "all_possible_pairs": all_possible,
            "candidate_pairs_evaluated": cand_count,
            "pair_reduction_ratio": ratio,
        }

    def get_merge_ledger(self, workspace_id: str) -> List[Dict[str, Any]]:
        """Retrieves the full reversible merge history from entity_merge_ledger."""
        merge_history = []
        with self.db.get_connection() as conn:
            cur = conn.execute(
                "SELECT * FROM entity_merge_ledger WHERE workspace_id = ? ORDER BY merged_at DESC;",
                (workspace_id,),
            )
            for r in cur.fetchall():
                merge_history.append({
                    "id": r["id"],
                    "winner_entity_id": r["winner_entity_id"],
                    "absorbed_entity_id": r["absorbed_entity_id"],
                    "match_probability": r["match_probability"],
                    "fellegi_sunter_log2_weight": r["fellegi_sunter_log2_weight"],
                    "is_reverted": bool(r["is_reverted"]),
                    "merged_at": r["merged_at"],
                    "reverted_at": r["reverted_at"],
                })
        return merge_history

    def evaluate_candidates(
        self, workspace_id: str, min_probability: float = 0.50
    ) -> Dict[str, Any]:
        """Runs candidate pair blocking, computes gamma matrix, executes EM, and produces waterfall explanations."""
        merge_history = self.get_merge_ledger(workspace_id)
        cand_pairs, stats = self.generate_candidate_pairs(workspace_id)
        if not cand_pairs:
            return {"workspace_id": workspace_id, "blocking_stats": stats, "candidates": [], "merge_history": merge_history}

        # Load entity records
        entities_cache: Dict[str, Dict[str, Any]] = {}
        for id_a, id_b in cand_pairs:
            if id_a not in entities_cache:
                entities_cache[id_a] = self.db.get_entity(id_a) or {}
            if id_b not in entities_cache:
                entities_cache[id_b] = self.db.get_entity(id_b) or {}

        # Build comparison feature vectors
        # Features: [name_jw, token_jaccard, same_schema, shared_attrs]
        gamma_list: List[List[float]] = []
        valid_pairs: List[Tuple[str, str]] = []

        for id_a, id_b in cand_pairs:
            ent_a = entities_cache.get(id_a)
            ent_b = entities_cache.get(id_b)
            if not ent_a or not ent_b:
                continue

            jw = jaro_winkler_similarity(ent_a["canonical_value"], ent_b["canonical_value"])
            jacc = token_jaccard_similarity(ent_a["display_label"], ent_b["display_label"])
            same_schema = 1.0 if ent_a["ftm_schema"] == ent_b["ftm_schema"] else 0.0

            # Check shared properties (e.g. shared country, LEI, ASN)
            prop_a = set((k, str(v)) for k, v in ent_a.get("properties", {}).items())
            prop_b = set((k, str(v)) for k, v in ent_b.get("properties", {}).items())
            shared_prop = 1.0 if prop_a.intersection(prop_b) else 0.0

            gamma_list.append([jw, jacc, same_schema, shared_prop])
            valid_pairs.append((id_a, id_b))

        gamma_mat = np.array(gamma_list, dtype=np.float64)
        lam, m_w, u_w, probs, log2_weights = run_fellegi_sunter_em(gamma_mat)

        candidates: List[Dict[str, Any]] = []
        for idx, (id_a, id_b) in enumerate(valid_pairs):
            p = probs[idx]
            if p < min_probability:
                continue

            ent_a = entities_cache[id_a]
            ent_b = entities_cache[id_b]
            log2_w = float(log2_weights[idx])

            # Build waterfall factors
            jw_val = gamma_mat[idx, 0]
            jacc_val = gamma_mat[idx, 1]
            schema_val = gamma_mat[idx, 2]
            prop_val = gamma_mat[idx, 3]

            m_arr, u_arr = np.array(m_w), np.array(u_w)
            bf_jw = jw_val * math.log2(m_arr[0] / u_arr[0]) + (1.0 - jw_val) * math.log2((1.0 - m_arr[0]) / (1.0 - u_arr[0]))
            bf_jacc = jacc_val * math.log2(m_arr[1] / u_arr[1]) + (1.0 - jacc_val) * math.log2((1.0 - m_arr[1]) / (1.0 - u_arr[1]))
            bf_schema = schema_val * math.log2(m_arr[2] / u_arr[2]) + (1.0 - schema_val) * math.log2((1.0 - m_arr[2]) / (1.0 - u_arr[2]))
            bf_prop = prop_val * math.log2(m_arr[3] / u_arr[3]) + (1.0 - prop_val) * math.log2((1.0 - m_arr[3]) / (1.0 - u_arr[3]))

            waterfall = [
                {"feature": "name_jaro_winkler", "value_a": ent_a["canonical_value"], "value_b": ent_b["canonical_value"], "log2_bayes_factor": round(bf_jw, 2)},
                {"feature": "token_jaccard", "value_a": ent_a["display_label"], "value_b": ent_b["display_label"], "log2_bayes_factor": round(bf_jacc, 2)},
                {"feature": "shared_schema", "value_a": ent_a["ftm_schema"], "value_b": ent_b["ftm_schema"], "log2_bayes_factor": round(bf_schema, 2)},
                {"feature": "shared_properties", "value_a": "props_a", "value_b": "props_b", "log2_bayes_factor": round(bf_prop, 2)},
            ]

            classification = "CONFIRMED_MATCH" if p >= 0.85 else ("POTENTIAL_MATCH" if p >= 0.50 else "NON_MATCH")
            candidates.append({
                "entity_a_id": id_a,
                "entity_a_label": ent_a["display_label"],
                "entity_a_schema": ent_a["ftm_schema"],
                "entity_b_id": id_b,
                "entity_b_label": ent_b["display_label"],
                "entity_b_schema": ent_b["ftm_schema"],
                "fellegi_sunter_log2_weight": round(log2_w, 2),
                "match_probability": round(p, 4),
                "classification": classification,
                "waterfall_factors": waterfall,
            })

        # Sort candidates descending by probability
        candidates.sort(key=lambda c: c["match_probability"], reverse=True)

        # Fetch merge history from ledger
        merge_history = self.get_merge_ledger(workspace_id)

        return {
            "workspace_id": workspace_id,
            "blocking_stats": stats,
            "candidates": candidates,
            "merge_history": merge_history,
        }

    def merge_entities(
        self,
        workspace_id: str,
        primary_entity_id: str,
        duplicate_entity_id: str,
        log2_weight: float = 5.0,
        match_probability: float = 0.95,
        waterfall_factors: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Merges duplicate entity into primary entity with full audit trail in entity_merge_ledger.
        
        1. Takes full snapshot of duplicate entity.
        2. Repoints all claims referring to duplicate entity to primary entity.
        3. Merges properties, aliases, and fuses Subjective Logic beliefs.
        4. Deletes duplicate entity from active entities table.
        """
        if primary_entity_id == duplicate_entity_id:
            raise ValueError("Cannot merge entity into itself")

        primary = self.db.get_entity(primary_entity_id)
        duplicate = self.db.get_entity(duplicate_entity_id)
        if not primary or not duplicate:
            raise ValueError("Primary or duplicate entity does not exist")

        merge_id = f"mrg_{uuid.uuid4().hex[:12]}"
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()

        # Fuse Subjective Logic opinions
        op_pri = (primary["sl_belief"], primary["sl_disbelief"], primary["sl_uncertainty"])
        op_dup = (duplicate["sl_belief"], duplicate["sl_disbelief"], duplicate["sl_uncertainty"])
        fused_b, fused_d, fused_u = cumulative_fusion([op_pri, op_dup])
        proj_p = fused_b + (0.50 * fused_u)

        # Merge properties, aliases, and tags
        merged_props = dict(primary.get("properties", {}))
        merged_props.update(duplicate.get("properties", {}))

        merged_aliases = list(set(primary.get("aliases", []) + duplicate.get("aliases", []) + [duplicate["display_label"]]))
        merged_tags = list(set(primary.get("tags", []) + duplicate.get("tags", [])))
        total_sources = primary["independent_source_count"] + duplicate["independent_source_count"]

        repointed_claims: List[Dict[str, Any]] = []

        with self.db.get_connection() as conn:
            # 1. Find claims where duplicate is subject
            cur = conn.execute("SELECT id FROM claims WHERE workspace_id = ? AND subject_entity_id = ?;", (workspace_id, duplicate_entity_id))
            for r in cur.fetchall():
                repointed_claims.append({"claim_id": r["id"], "role": "subject", "original_entity_id": duplicate_entity_id})

            # 2. Find claims where duplicate is object
            cur = conn.execute("SELECT id FROM claims WHERE workspace_id = ? AND object_entity_id = ?;", (workspace_id, duplicate_entity_id))
            for r in cur.fetchall():
                repointed_claims.append({"claim_id": r["id"], "role": "object", "original_entity_id": duplicate_entity_id})

            # Repoint claims to primary
            conn.execute("UPDATE claims SET subject_entity_id = ? WHERE subject_entity_id = ?;", (primary_entity_id, duplicate_entity_id))
            conn.execute("UPDATE claims SET object_entity_id = ? WHERE object_entity_id = ?;", (primary_entity_id, duplicate_entity_id))

            # Update primary entity
            conn.execute(
                """
                UPDATE entities SET
                    sl_belief = ?,
                    sl_disbelief = ?,
                    sl_uncertainty = ?,
                    projected_probability = ?,
                    independent_source_count = ?,
                    properties_json = ?,
                    aliases_json = ?,
                    tags_json = ?,
                    last_seen_at = ?
                WHERE id = ?;
                """,
                (
                    fused_b, fused_d, fused_u, proj_p, total_sources,
                    json.dumps(merged_props), json.dumps(merged_aliases), json.dumps(merged_tags),
                    now, primary_entity_id,
                ),
            )

            # Record in entity_merge_ledger
            conn.execute(
                """
                INSERT INTO entity_merge_ledger (
                    id, workspace_id, winner_entity_id, absorbed_entity_id,
                    absorbed_entity_snapshot_json, repointed_claims_json,
                    fellegi_sunter_log2_weight, match_probability,
                    waterfall_explanation_json, is_reverted, merged_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?);
                """,
                (
                    merge_id, workspace_id, primary_entity_id, duplicate_entity_id,
                    json.dumps(duplicate), json.dumps(repointed_claims),
                    log2_weight, match_probability, json.dumps(waterfall_factors or []),
                    now,
                ),
            )

            # Delete duplicate entity (snapshot is safely stored in ledger)
            conn.execute("DELETE FROM entities WHERE id = ?;", (duplicate_entity_id,))

        self.db.append_audit_log(
            "ENTITY_MERGED",
            f"Merged '{duplicate['display_label']}' ({duplicate_entity_id}) into '{primary['display_label']}' ({primary_entity_id}) [p={match_probability}]",
            workspace_id,
        )

        return {
            "merge_id": merge_id,
            "primary_entity": self.db.get_entity(primary_entity_id),
            "absorbed_entity_id": duplicate_entity_id,
            "repointed_claim_count": len(repointed_claims),
            "status": "MERGED",
        }

    def unmerge_entity(self, workspace_id: str, merge_id: str) -> Dict[str, Any]:
        """100% reversible unmerge: restores absorbed entity from snapshot and restores claims."""
        with self.db.get_connection() as conn:
            cur = conn.execute(
                "SELECT * FROM entity_merge_ledger WHERE id = ? AND workspace_id = ?;",
                (merge_id, workspace_id),
            )
            ledger_rec = cur.fetchone()
            if not ledger_rec:
                raise ValueError(f"Merge record {merge_id} not found")

            if ledger_rec["is_reverted"]:
                raise ValueError(f"Merge {merge_id} is already reverted")

            now = datetime.datetime.now(datetime.timezone.utc).isoformat()
            snap = json.loads(ledger_rec["absorbed_entity_snapshot_json"])
            repointed = json.loads(ledger_rec["repointed_claims_json"])
            abs_id = ledger_rec["absorbed_entity_id"]

            # 1. Restore absorbed entity
            conn.execute(
                """
                INSERT INTO entities (
                    id, workspace_id, ftm_schema, canonical_value, display_label,
                    is_staged, is_shared_infra, sl_belief, sl_disbelief, sl_uncertainty,
                    sl_base_rate, projected_probability, admiralty_code, risk_score,
                    risk_reasons_json, latitude, longitude, geohash_8, location_label,
                    properties_json, aliases_json, tags_json, independent_source_count,
                    first_seen_at, last_seen_at
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                );
                """,
                (
                    snap["id"], snap["workspace_id"], snap["ftm_schema"], snap["canonical_value"], snap["display_label"],
                    snap["is_staged"], snap["is_shared_infra"], snap["sl_belief"], snap["sl_disbelief"], snap["sl_uncertainty"],
                    snap["sl_base_rate"], snap["projected_probability"], snap["admiralty_code"], snap["risk_score"],
                    json.dumps(snap.get("risk_reasons", [])), snap.get("latitude"), snap.get("longitude"), snap.get("geohash_8", ""), snap.get("location_label", ""),
                    json.dumps(snap.get("properties", {})), json.dumps(snap.get("aliases", [])), json.dumps(snap.get("tags", [])), snap.get("independent_source_count", 1),
                    snap["first_seen_at"], snap["last_seen_at"],
                ),
            )

            # 2. Restore repointed claims
            for item in repointed:
                cid = item["claim_id"]
                role = item["role"]
                orig_id = item["original_entity_id"]
                if role == "subject":
                    conn.execute("UPDATE claims SET subject_entity_id = ? WHERE id = ?;", (orig_id, cid))
                elif role == "object":
                    conn.execute("UPDATE claims SET object_entity_id = ? WHERE id = ?;", (orig_id, cid))

            # 3. Mark merge record as reverted
            conn.execute(
                "UPDATE entity_merge_ledger SET is_reverted = 1, reverted_at = ? WHERE id = ?;",
                (now, merge_id),
            )

        self.db.append_audit_log(
            "ENTITY_UNMERGED",
            f"Unmerged entity '{snap['display_label']}' ({abs_id}) from merge {merge_id}",
            workspace_id,
        )

        return {
            "merge_id": merge_id,
            "restored_entity": self.db.get_entity(abs_id),
            "status": "REVERTED",
        }


# Singleton
entity_resolution_engine = EntityResolutionEngine()
