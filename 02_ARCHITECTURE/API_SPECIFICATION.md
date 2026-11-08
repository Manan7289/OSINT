# API_SPECIFICATION.md — Complete FastAPI REST & WebSocket Interface Contract

## 1. Base URL, Versioning & Headers
- **Local Server Address:** `http://127.0.0.1:8000`
- **OpenAPI Interactive Docs:** `http://127.0.0.1:8000/docs`
- **Content-Type:** `application/json` (except `POST /api/collect/document-upload` which accepts `multipart/form-data` and `GET /api/workspaces/{id}/export` which streams `text/csv` or `application/json`).
- **Backward & Forward Route Compatibility:** Expose all routes under `/api/*` (and alias `/api/v2/*` to the same router) so both v1 tests and v2 clients work seamlessly.

---

## 2. Endpoint-by-Endpoint Specification

### 2.1 Health, Diagnostics & System Metrics
- **`GET /api/health`**
  - **Purpose:** Returns system readiness, SQLite WAL status, active connector counts, ONNX Runtime status, and memory footprint.
  - **Response (`200 OK`):**
    ```json
    {
      "status": "healthy",
      "version": "2.0.0",
      "database_wal": true,
      "onnx_available": true,
      "workspace_count": 1,
      "connectors_total": 24,
      "connectors_ready": 18,
      "memory_rss_mb": 94.2,
      "timestamp": "2026-11-08T12:00:00Z"
    }
    ```

### 2.2 Workspaces & Case Management
- **`GET /api/workspaces`** $ightarrow$ Lists all workspaces with entity, claim, staged_entity, evidence, and report counts.
- **`POST /api/workspaces`**
  - **Request Body:**
    ```json
    {
      "name": "Operation Sentinel — Infrastructure Footprint",
      "description": "Investigating ASN, CT logs, and corporate LEI ownership",
      "tlp_marking": "TLP:AMBER",
      "opsec_mode": "PASSIVE_ONLY",
      "scope_domains": ["example.org"],
      "max_pivot_depth": 2
    }
    ```
  - **Response (`200 OK`):** Full workspace object with generated `id` (`ws_...`).
- **`GET /api/workspaces/{workspace_id}`** $ightarrow$ Returns workspace details and summary counts.
- **`DELETE /api/workspaces/{workspace_id}`** $ightarrow$ Deletes workspace, purges FTS5/vector rows, and logs to `audit_logs`.

### 2.3 Entities, Staging Buffer & Bitemporal Claims
- **`GET /api/workspaces/{workspace_id}/entities`**
  - **Query Params:** `ftm_schema` (optional), `q` (optional search string), `include_staged` (`bool`, default `false`), `min_belief` (`float`), `limit` (`int`, default `500`).
- **`POST /api/workspaces/{workspace_id}/entities`** $ightarrow$ Creates/upserts an entity with canonicalization and automatic 3-pass blocking key indexing.
- **`POST /api/workspaces/{workspace_id}/staging/promote`**
  - **Purpose:** Promotes selected (or filtered) staged entities (`is_staged = 1`) into the active visual graph (`is_staged = 0`).
  - **Request Body:** `{"entity_ids": ["ent_1", "ent_2"], "promote_all_above_risk": 50}`
- **`GET /api/workspaces/{workspace_id}/claims`** (Also aliased as **`GET /api/workspaces/{workspace_id}/relationships`**)
  - **Query Params:** `epistemic_status` (optional), `as_of_time` (optional ISO-8601 timestamp for **Bitemporal Time-Travel** filtering where `valid_from <= as_of_time <= valid_until`).
- **`POST /api/workspaces/{workspace_id}/claims`** (Also aliased as **`POST /api/workspaces/{workspace_id}/relationships`**)
  - **Request Body:**
    ```json
    {
      "subject_entity_id": "ent_a",
      "predicate": "RESOLVES_TO",
      "object_entity_id": "ent_b",
      "epistemic_status": "ANALYST_HYPOTHESIS",
      "valid_from": "2025-01-01T00:00:00Z",
      "valid_until": null
    }
    ```

### 2.4 Collection Playbooks, Transforms & Document Forensics
- **`POST /api/collect/workflow`** (Also aliased as **`POST /api/collect/playbook`**)
  - **Request Body:**
    ```json
    {
      "workspace_id": "ws_123",
      "target_query": "example.org",
      "target_type": "AUTO",
      "connectors": ["dns_doh", "rdap_bootstrap", "crtsh_ct", "ripestat_data", "gleif_lei", "cisa_kev", "first_epss"],
      "pivot_depth": 1
    }
    ```
  - **Response (`200 OK`):** Summary of executed tasks, entities discovered, claims created, staged count, and provenance hashes.
- **`POST /api/collect/document-text`**
  - **Purpose:** Runs Tier-1 (Defang + Regex + Aho-Corasick) and Tier-2 (ONNX GLiNER) extraction on pasted unstructured text/headers.
- **`POST /api/collect/document-upload`**
  - **Purpose:** Accepts PDF, DOCX, XLSX, Image (JPEG/PNG/TIFF/WebP), or HTML/TXT files, computes SHA-256 + SimHash-64, extracts author/software/EXIF metadata and embedded observables, and links them into the graph.

### 2.5 Entity Resolution (Fellegi-Sunter EM, Waterfall & Reversible Merge)
- **`GET /api/workspaces/{workspace_id}/entity-resolution`**
  - **Query Params:** `min_probability` (`float`, default `0.50`), `run_em` (`bool`, default `true`).
  - **Response (`200 OK`):**
    ```json
    {
      "workspace_id": "ws_123",
      "blocking_stats": {"total_entities": 240, "candidate_pairs_evaluated": 612, "pair_reduction_ratio": 46.8},
      "candidates": [
        {
          "entity_a_id": "ent_1",
          "entity_a_label": "ShadowNet Security Inc",
          "entity_b_id": "ent_2",
          "entity_b_label": "ShadowNet Security LLC",
          "fellegi_sunter_log2_weight": 6.42,
          "match_probability": 0.938,
          "classification": "CONFIRMED_MATCH",
          "waterfall_factors": [
            {"feature": "name_jaro_winkler", "value_a": "shadownet security", "value_b": "shadownet security", "log2_bayes_factor": 4.15},
            {"feature": "shared_asn", "value_a": "AS13335", "value_b": "AS13335", "log2_bayes_factor": 1.42},
            {"feature": "shared_country", "value_a": "US", "value_b": "US", "log2_bayes_factor": 0.85}
          ]
        }
      ],
      "merge_history": []
    }
    ```
- **`POST /api/workspaces/{workspace_id}/entity-resolution/merge`**
  - **Request Body:** `{"primary_entity_id": "ent_1", "duplicate_entity_id": "ent_2"}`
- **`POST /api/workspaces/{workspace_id}/entity-resolution/unmerge/{merge_id}`**
  - **Purpose:** Reverts a previous merge using the snapshot stored in `entity_merge_ledger`.

### 2.6 Graph Analytics, Spatiotemporal Clustering & Provenance Fusion
- **`GET /api/workspaces/{workspace_id}/graph`**
  - **Query Params:** `as_of_time` (optional ISO timestamp), `hide_shared_infra` (`bool`, default `false`), `include_staged` (`bool`, default `false`).
  - **Response (`200 OK`):** Nodes (with `leiden_community_id`, `ief_pagerank`, `sl_belief`, `sl_uncertainty`, `risk_score`), Edges (with `epistemic_status`, `ief_edge_weight`), `top_hubs`, `predicted_links` (Adamic-Adar top 10), and `anomalies` (Isolation Forest + DGA entropy).
- **`GET /api/workspaces/{workspace_id}/geospatial`**
  - **Response (`200 OK`):** Geolocated points + **Haversine HDBSCAN spatial clusters** (`cluster_id`, centroid lat/lon, radius_km, member count).
- **`GET /api/workspaces/{workspace_id}/timeline`**
  - **Response (`200 OK`):** Chronological events + **Kleinberg / Poisson Z-score burst intervals** (`burst_windows`).
- **`GET /api/workspaces/{workspace_id}/evidence`**
  - **Response (`200 OK`):** W3C PROV evidence artifacts with `upstream_lineage_family`, `independence_weight`, `admiralty_rating`, and `payload_sha256`.

### 2.7 Hybrid RRF Search, GraphRAG AI Assistant, Reports & Multi-Format Export
- **`GET /api/workspaces/{workspace_id}/search`**
  - **Query Params:** `q` (search query), `mode` (`hybrid_rrf`, `bm25`, `semantic`), `limit` (`int`, default `50`).
- **`POST /api/ai/query`**
  - **Response (`200 OK`):** Epistemically stratified Markdown answer (`Observed & Corroborated Facts`, `Graph-Derived Inferences`, `Contradictions & Gaps`, `Citation Verification Audit`).
- **`POST /api/reports/generate`** & **`GET /api/workspaces/{workspace_id}/reports`**
- **`GET /api/workspaces/{workspace_id}/export?format={json|csv|stix|ftm|prov}`**

### 2.8 Connectors, Tasks, Vault & Audit Ledger
- **`GET /api/connectors`** & **`PUT /api/connectors/{connector_id}`**
- **`GET /api/tasks`**
- **`GET /api/settings`** & **`PUT /api/settings`** (includes hash-chain verification status of `audit_logs`).
