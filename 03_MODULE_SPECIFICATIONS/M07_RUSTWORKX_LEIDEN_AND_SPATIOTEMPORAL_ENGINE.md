# M07 — Graph Analytics (Leiden, IEF-PageRank, Adamic-Adar) & Spatiotemporal/Burst Engine

## 1. Module Name & Identifier
- **Module Title:** M07 — Graph Analytics (Leiden, IEF-PageRank, Adamic-Adar) & Spatiotemporal/Burst Engine
- **Target File Path(s):** `backend/core/graph_analytics.py, backend/core/spatiotemporal.py`

## 2. Purpose
Executes high-speed graph community detection, super-node dampened centrality, missing-link prediction, Haversine HDBSCAN spatial clustering, Kleinberg temporal burst detection, and Isolation Forest node anomaly scoring.

## 3. User-Facing Functionality
Powers View 4 (Relationship Graph), View 6 (Timeline & Burst View), and View 7 (Geospatial Cluster Map).

## 4. Internal Responsibilities
Constructs an in-memory weighted graph (using `rustworkx` when installed, with automatic NumPy/SciPy sparse matrix fallback), applies Inverse Entity Frequency (IEF) edge weights to dampen RIOT-Lite super-nodes (`AS13335`, major registrars), runs Leiden modularity + local refinement, computes Personalized PageRank and Adamic-Adar scores, clusters lat/lon coordinates via Haversine HDBSCAN, and computes Poisson Z-scores on timeline buckets.

## 5. Inputs
`workspace_id: str`, `as_of_time: Optional[str]`, `hide_shared_infra: bool`.

## 6. Outputs
Graph payload (`nodes`, `edges`, `communities`, `top_hubs`, `predicted_links`, `anomalies`), `GeoClusterPayload`, and `TimelineBurstPayload`.

## 7. Required Algorithms & Mathematical Formulations
1. **IEF Edge Weighting:** $w(u,v) = c(u,v) \cdot \log(1 + |V| / \text{deg}(v)) \cdot (0.15 \text{ if shared\_infra else } 1.0)$.
2. **Leiden Community Detection ([Traag et al., 2019](https://arxiv.org/abs/1810.08473)).**
3. **Personalized PageRank (Power Iteration, $\alpha=0.85$).**
4. **Adamic-Adar Link Prediction:** $AA(u,v) = \sum_{z \in \Gamma(u)\cap\Gamma(v)} \frac{1}{\log|\Gamma(z)|}$.
5. **Haversine Great-Circle HDBSCAN / Hierarchical Density Clustering (`scipy` / `scikit-learn`).**
6. **Poisson / Kleinberg Temporal Burst Z-Score.**

## 8. Dependencies
`numpy`, `scipy`, `rustworkx` (optional accelerator), `M02`, `M06`.

## 9. Backend Integration
Backs `/api/workspaces/{id}/graph`, `/geospatial`, and `/timeline`.

## 10. Frontend Integration
Feeds Sigma.js WebGL / Cytoscape.js graph view, HDBSCAN map polygons, and timeline burst highlights.

## 11. Data Storage Requirements
Caches `leiden_community_id` and `ief_pagerank` on `entities`.

## 12. Error-Handling Requirements
Handles empty graphs (0 nodes or 0 edges) and single-point geospatial sets gracefully.

## 13. Security, OPSEC & Privacy Requirements
Read-only analytical computation over workspace-scoped records.

## 14. Testing Requirements
`tests/test_m07_graph_spatiotemporal.py`: Verify connected Leiden communities, super-node dampening, Adamic-Adar predictions, Haversine clustering, and timeline burst detection.

## 15. Dependencies on Other Modules
Depends on `M02`, `M06`.

## 16. Completion & Acceptance Criteria
All tests in `test_m07_graph_spatiotemporal.py` pass.
