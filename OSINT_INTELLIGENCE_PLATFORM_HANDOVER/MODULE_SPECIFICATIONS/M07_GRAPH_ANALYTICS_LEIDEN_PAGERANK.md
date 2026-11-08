# M07 — Knowledge Graph Analytics (Leiden + IEF-Weighted PageRank)

- **Target File:** `backend/core/graph_analytics.py`
- **Action:** Retain `leidenalg` Modularity/CPM community detection and Inverse Entity Frequency (IEF) weighted PageRank. Add helper `get_entity_ego_graph(entity_id, hops=2)` so clicking any aircraft, vessel, satellite, camera, or event on the 2D/3D globe immediately populates the Cytoscape.js ego-network in Zone 4.
