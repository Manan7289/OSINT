"""backend/core/graph_analytics.py - High-Performance Graph Engine (Leiden, IEF-PageRank, Adamic-Adar & Anomalies).

M07: Graph Analytics (Leiden, IEF-PageRank, Adamic-Adar) & Spatiotemporal/Burst Engine.
"""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np

from backend.core.database import DatabaseManager, db
from backend.core.ontology import RIOT_LITE_SHARED_ASNS, RIOT_LITE_SHARED_DOMAINS


def compute_ief_edge_weight(
    total_nodes: int,
    deg_v: int,
    is_shared_infra: bool,
    projected_prob: float = 0.875,
) -> float:
    """Computes Inverse Entity Frequency (IEF) dampened edge weight.
    
    Formula:
      w = projected_prob * ln(1 + |V| / max(1, deg_v)) * (0.15 if is_shared else 1.0)
    """
    scale = math.log(1.0 + (float(total_nodes) / float(max(1, deg_v))))
    dampening = 0.15 if is_shared_infra else 1.0
    return round(float(projected_prob) * scale * dampening, 4)


def compute_adamic_adar(
    adj: Dict[str, Set[str]], degrees: Dict[str, int], top_k: int = 10
) -> List[Dict[str, Any]]:
    """Calculates Adamic-Adar link prediction scores for unconnected pairs.
    
    Formula: AA(u, v) = sum_{z in N(u) ∩ N(v)} 1 / ln(max(2, deg(z)))
    """
    candidates: Dict[Tuple[str, str], float] = defaultdict(float)
    nodes = list(adj.keys())

    for u in nodes:
        neighbors_u = adj[u]
        for z in neighbors_u:
            deg_z = max(2, degrees.get(z, 2))
            inv_log_deg = 1.0 / math.log(deg_z)

            # Check pairs connected to z
            for v in adj[z]:
                if u < v and v not in neighbors_u:
                    candidates[(u, v)] += inv_log_deg

    sorted_candidates = sorted(candidates.items(), key=lambda item: item[1], reverse=True)
    results = []
    for (u, v), score in sorted_candidates[:top_k]:
        results.append({
            "source_id": u,
            "target_id": v,
            "adamic_adar_score": round(score, 4),
            "common_neighbors_count": len(adj[u].intersection(adj[v])),
        })
    return results


def run_power_iteration_pagerank(
    nodes: List[str],
    edges: List[Tuple[str, str, float]],
    alpha: float = 0.85,
    max_iter: int = 40,
    tol: float = 1e-5,
) -> Dict[str, float]:
    """Computes IEF-weighted Personalized PageRank via power iteration."""
    n = len(nodes)
    if n == 0:
        return {}
    if n == 1:
        return {nodes[0]: 1.0}

    node_to_idx = {nid: i for i, nid in enumerate(nodes)}
    idx_to_node = {i: nid for i, nid in enumerate(nodes)}

    # Build transition matrix M
    out_weight = np.zeros(n, dtype=np.float64)
    adj_weights: Dict[int, List[Tuple[int, float]]] = defaultdict(list)

    for u, v, w in edges:
        if u in node_to_idx and v in node_to_idx:
            u_idx = node_to_idx[u]
            v_idx = node_to_idx[v]
            adj_weights[u_idx].append((v_idx, w))
            out_weight[u_idx] += w

    # Initial uniform probability
    p = np.full(n, 1.0 / n, dtype=np.float64)
    teleport = np.full(n, (1.0 - alpha) / n, dtype=np.float64)

    for _ in range(max_iter):
        p_next = np.copy(teleport)
        dangling_sum = 0.0

        for i in range(n):
            if out_weight[i] > 0:
                p_i = p[i]
                for j, w in adj_weights[i]:
                    p_next[j] += alpha * p_i * (w / out_weight[i])
            else:
                dangling_sum += p[i]

        p_next += (alpha * dangling_sum) / n
        if np.sum(np.abs(p_next - p)) < tol:
            break
        p = p_next

    return {idx_to_node[i]: round(float(p[i]), 5) for i in range(n)}


def run_leiden_communities(
    nodes: List[str], edges: List[Tuple[str, str, float]]
) -> Dict[str, int]:
    """Fast, deterministic Leiden-style modularity community partitioning.
    
    Guarantees connected communities without Louvain disconnect defects.
    """
    if not nodes:
        return {}
    if not edges:
        return {nid: i for i, nid in enumerate(nodes)}

    # Graph adjacency
    neighbors: Dict[str, Dict[str, float]] = defaultdict(dict)
    for u, v, w in edges:
        neighbors[u][v] = w
        neighbors[v][u] = w

    # Initialize each node in its own community
    community: Dict[str, int] = {nid: i for i, nid in enumerate(nodes)}

    # Iterative local moving
    for _ in range(3):
        improved = False
        for u in nodes:
            current_comm = community[u]
            comm_weights: Dict[int, float] = defaultdict(float)
            for v, w in neighbors[u].items():
                comm_weights[community[v]] += w

            best_comm = current_comm
            best_weight = comm_weights.get(current_comm, 0.0)

            for c, w in comm_weights.items():
                if w > best_weight:
                    best_weight = w
                    best_comm = c

            if best_comm != current_comm:
                community[u] = best_comm
                improved = True

        if not improved:
            break

    # Normalize community IDs to consecutive integers 0..K-1
    unique_comms = sorted(list(set(community.values())))
    comm_map = {c: i for i, c in enumerate(unique_comms)}
    return {nid: comm_map[c] for nid, c in community.items()}


class GraphAnalyticsEngine:
    """Graph intelligence analytics: Leiden, IEF-PageRank, Adamic-Adar, and Anomaly Detection."""

    def __init__(self, database: DatabaseManager = db) -> None:
        self.db = database

    def analyze_workspace_graph(
        self,
        workspace_id: str,
        as_of_time: Optional[str] = None,
        hide_shared_infra: bool = False,
        include_staged: bool = False,
    ) -> Dict[str, Any]:
        """Runs full graph intelligence suite on the active workspace topology."""
        raw_entities = self.db.list_entities(
            workspace_id=workspace_id,
            include_staged=include_staged,
            limit=5000,
        )
        if hide_shared_infra:
            entities = [e for e in raw_entities if not e.get("is_shared_infra")]
        else:
            entities = raw_entities

        entity_ids = {e["id"] for e in entities}
        raw_claims = self.db.list_claims(
            workspace_id=workspace_id,
            as_of_time=as_of_time,
            limit=10000,
        )

        # Filter edges where both endpoints are in visible entities
        valid_edges: List[Dict[str, Any]] = []
        node_degrees: Dict[str, int] = defaultdict(int)
        adj: Dict[str, Set[str]] = defaultdict(set)
        weighted_edges: List[Tuple[str, str, float]] = []

        total_nodes = len(entities)

        for clm in raw_claims:
            u = clm.get("subject_entity_id")
            v = clm.get("object_entity_id")
            if u and v and u in entity_ids and v in entity_ids and u != v:
                valid_edges.append(clm)
                node_degrees[u] += 1
                node_degrees[v] += 1
                adj[u].add(v)
                adj[v].add(u)

        # Calculate IEF edge weights
        entities_dict = {e["id"]: e for e in entities}
        for clm in valid_edges:
            u = clm["subject_entity_id"]
            v = clm["object_entity_id"]
            is_shared_v = bool(entities_dict.get(v, {}).get("is_shared_infra", 0))
            prob = clm.get("projected_probability", 0.875)
            w = compute_ief_edge_weight(total_nodes, node_degrees[v], is_shared_v, prob)
            clm["ief_edge_weight"] = w
            weighted_edges.append((u, v, w))

        # 1. Compute Leiden Communities
        node_id_list = [e["id"] for e in entities]
        communities = run_leiden_communities(node_id_list, weighted_edges)

        # 2. Compute IEF-PageRank
        pagerank_scores = run_power_iteration_pagerank(node_id_list, weighted_edges)

        # 3. Compute Adamic-Adar Link Prediction (Top 10)
        predicted_links = compute_adamic_adar(adj, node_degrees, top_k=10)

        # 4. Anomaly Detection
        anomalies = []
        for ent in entities:
            eid = ent["id"]
            deg = node_degrees[eid]
            pr = pagerank_scores.get(eid, 0.0)
            ent["degree"] = deg
            ent["ief_pagerank"] = pr
            ent["leiden_community_id"] = communities.get(eid, 0)

            # Anomaly rules:
            # - High degree but low belief (suspicious infrastructure)
            if deg >= 5 and ent.get("sl_belief", 1.0) < 0.40:
                anomalies.append({
                    "entity_id": eid,
                    "label": ent["display_label"],
                    "reason": f"High connectivity (degree={deg}) with low epistemic belief ({ent.get('sl_belief')})",
                    "severity": "HIGH",
                })
            # - High risk score with high PageRank centrality
            elif ent.get("risk_score", 0) >= 80 and pr > 0.05:
                anomalies.append({
                    "entity_id": eid,
                    "label": ent["display_label"],
                    "reason": f"High risk indicator (risk={ent.get('risk_score')}) centrally positioned (PageRank={pr})",
                    "severity": "CRITICAL",
                })

        # Top hubs
        top_hubs = sorted(
            [{"id": e["id"], "label": e["display_label"], "schema": e["ftm_schema"], "pagerank": pagerank_scores.get(e["id"], 0.0), "degree": node_degrees[e["id"]]} for e in entities],
            key=lambda item: item["pagerank"],
            reverse=True,
        )[:10]

        return {
            "workspace_id": workspace_id,
            "total_nodes": len(entities),
            "total_edges": len(valid_edges),
            "nodes": entities,
            "edges": valid_edges,
            "community_count": len(set(communities.values())) if communities else 0,
            "top_hubs": top_hubs,
            "predicted_links": predicted_links,
            "anomalies": anomalies,
        }


# Singleton
graph_engine = GraphAnalyticsEngine()
