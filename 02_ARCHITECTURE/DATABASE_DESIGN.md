# DATABASE_DESIGN.md — Implementation-Ready SQLite WAL + FTS5 + R*Tree + Vector Schema

## 1. Database Engine & Connection Pragmas
LocalOSINT uses **SQLite 3.40+** (`data/localosint.db`) as its single-file ACID transactional core, paired with **FTS5** for BM25 lexical search, **R*Tree** for 2D geospatial bounding-box queries, **NumPy / `sqlite-vec`** for 384-d INT8 embeddings, and **[DuckDB](https://duckdb.org/)** for analytical aggregations.

Every SQLite connection opened by `DatabaseManager.get_connection()` MUST execute:
```sql
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA foreign_keys = ON;
PRAGMA temp_store = MEMORY;
PRAGMA mmap_size = 268435456; -- 256 MB mmap
PRAGMA cache_size = -32000;   -- 32 MB page cache
PRAGMA busy_timeout = 15000;
```

---

## 2. Complete SQL DDL Schema (14 Core Tables & Virtual Indices)

```sql
-- TABLE 1: workspaces (Investigation Case Isolation)
CREATE TABLE IF NOT EXISTS workspaces (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    tlp_marking TEXT NOT NULL DEFAULT 'TLP:CLEAR',
    opsec_mode TEXT NOT NULL DEFAULT 'STANDARD', -- 'STANDARD' or 'PASSIVE_ONLY'
    scope_domains_json TEXT NOT NULL DEFAULT '[]',
    max_pivot_depth INTEGER NOT NULL DEFAULT 2,
    staging_threshold INTEGER NOT NULL DEFAULT 50,
    tags_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- TABLE 2: evidence_artifacts (W3C PROV Immutable Provenance Vault)
CREATE TABLE IF NOT EXISTS evidence_artifacts (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    connector_id TEXT NOT NULL,
    upstream_lineage_family TEXT NOT NULL,
    source_name TEXT NOT NULL,
    source_url TEXT NOT NULL,
    parent_evidence_id TEXT REFERENCES evidence_artifacts(id) ON DELETE SET NULL,
    independence_weight REAL NOT NULL DEFAULT 1.0,
    admiralty_reliability TEXT NOT NULL DEFAULT 'B',
    admiralty_credibility INTEGER NOT NULL DEFAULT 2,
    http_status INTEGER DEFAULT 200,
    response_headers_json TEXT NOT NULL DEFAULT '{}',
    title TEXT NOT NULL,
    summary_text TEXT NOT NULL,
    raw_payload_json TEXT NOT NULL DEFAULT '{}',
    payload_sha256 TEXT NOT NULL,
    simhash_64 TEXT NOT NULL DEFAULT '0000000000000000',
    observed_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ev_ws_sha ON evidence_artifacts(workspace_id, payload_sha256);
CREATE INDEX IF NOT EXISTS idx_ev_ws_lineage ON evidence_artifacts(workspace_id, upstream_lineage_family);

-- TABLE 3: entities (FollowTheMoney-Aligned Canonical Nodes)
CREATE TABLE IF NOT EXISTS entities (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    ftm_schema TEXT NOT NULL, -- Domain, Subdomain, IPv4Address, IPv6Address, AutonomousSystem, Company, Organization, Person, Email, Vulnerability, Service, X509Certificate, CryptoWallet, Location, Document, NewsArticle, GitHubProfile
    canonical_value TEXT NOT NULL,
    display_label TEXT NOT NULL,
    is_staged INTEGER NOT NULL DEFAULT 0,
    is_shared_infra INTEGER NOT NULL DEFAULT 0,
    sl_belief REAL NOT NULL DEFAULT 0.75,
    sl_disbelief REAL NOT NULL DEFAULT 0.00,
    sl_uncertainty REAL NOT NULL DEFAULT 0.25,
    sl_base_rate REAL NOT NULL DEFAULT 0.50,
    projected_probability REAL NOT NULL DEFAULT 0.875,
    admiralty_code TEXT NOT NULL DEFAULT 'B2',
    risk_score INTEGER NOT NULL DEFAULT 0,
    risk_reasons_json TEXT NOT NULL DEFAULT '[]',
    leiden_community_id INTEGER NOT NULL DEFAULT 0,
    ief_pagerank REAL NOT NULL DEFAULT 0.0,
    degree_centrality REAL NOT NULL DEFAULT 0.0,
    latitude REAL,
    longitude REAL,
    geohash_8 TEXT DEFAULT '',
    location_label TEXT DEFAULT '',
    properties_json TEXT NOT NULL DEFAULT '{}',
    aliases_json TEXT NOT NULL DEFAULT '[]',
    tags_json TEXT NOT NULL DEFAULT '[]',
    independent_source_count INTEGER NOT NULL DEFAULT 1,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_ent_ws_schema_canon ON entities(workspace_id, ftm_schema, canonical_value);
CREATE INDEX IF NOT EXISTS idx_ent_ws_staged ON entities(workspace_id, is_staged);
CREATE INDEX IF NOT EXISTS idx_ent_ws_geohash ON entities(workspace_id, geohash_8);

-- TABLE 4: entity_blocking_keys (Multi-Pass Sorted Neighborhood & MinHash LSH Index)
CREATE TABLE IF NOT EXISTS entity_blocking_keys (
    entity_id TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    pass_type TEXT NOT NULL, -- 'PHONETIC_SORT', 'APEX_PREFIX', 'MINHASH_LSH'
    blocking_key TEXT NOT NULL,
    PRIMARY KEY (entity_id, pass_type, blocking_key)
);
CREATE INDEX IF NOT EXISTS idx_block_ws_pass_key ON entity_blocking_keys(workspace_id, pass_type, blocking_key);

-- TABLE 5: claims (Reified Bitemporal Edges & Attribute Attestations)
CREATE TABLE IF NOT EXISTS claims (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    subject_entity_id TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    predicate TEXT NOT NULL,
    object_entity_id TEXT REFERENCES entities(id) ON DELETE CASCADE,
    object_literal TEXT DEFAULT '',
    epistemic_status TEXT NOT NULL DEFAULT 'OBSERVED_FACT', -- OBSERVED_FACT, CORROBORATED_FACT, DERIVED_INFERENCE, ANALYST_HYPOTHESIS, UNVERIFIED_CLAIM
    sl_belief REAL NOT NULL DEFAULT 0.75,
    sl_disbelief REAL NOT NULL DEFAULT 0.00,
    sl_uncertainty REAL NOT NULL DEFAULT 0.25,
    sl_base_rate REAL NOT NULL DEFAULT 0.50,
    projected_probability REAL NOT NULL DEFAULT 0.875,
    ief_edge_weight REAL NOT NULL DEFAULT 1.0,
    attributes_json TEXT NOT NULL DEFAULT '{}',
    valid_from TEXT,
    valid_until TEXT,
    first_observed_at TEXT NOT NULL,
    last_observed_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_claims_ws_subj_obj ON claims(workspace_id, subject_entity_id, object_entity_id, predicate);
CREATE INDEX IF NOT EXISTS idx_claims_ws_epistemic ON claims(workspace_id, epistemic_status);

-- TABLE 6: claim_evidence (Many-to-Many Claim-to-Provenance Junction)
CREATE TABLE IF NOT EXISTS claim_evidence (
    claim_id TEXT NOT NULL REFERENCES claims(id) ON DELETE CASCADE,
    evidence_id TEXT NOT NULL REFERENCES evidence_artifacts(id) ON DELETE CASCADE,
    stance TEXT NOT NULL DEFAULT 'SUPPORTS', -- 'SUPPORTS' or 'CONTRADICTS'
    PRIMARY KEY (claim_id, evidence_id)
);

-- TABLE 7: entity_merge_ledger (Reversible Fellegi-Sunter Entity Resolution Audit Trail)
CREATE TABLE IF NOT EXISTS entity_merge_ledger (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    winner_entity_id TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    absorbed_entity_id TEXT NOT NULL,
    absorbed_entity_snapshot_json TEXT NOT NULL,
    repointed_claims_json TEXT NOT NULL DEFAULT '[]',
    fellegi_sunter_log2_weight REAL NOT NULL,
    match_probability REAL NOT NULL,
    waterfall_explanation_json TEXT NOT NULL DEFAULT '[]',
    is_reverted INTEGER NOT NULL DEFAULT 0,
    merged_at TEXT NOT NULL,
    reverted_at TEXT
);

-- TABLE 8: timeline_events (Chronological & Kleinberg Burst Events)
CREATE TABLE IF NOT EXISTS timeline_events (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    entity_id TEXT REFERENCES entities(id) ON DELETE SET NULL,
    evidence_id TEXT REFERENCES evidence_artifacts(id) ON DELETE SET NULL,
    event_time TEXT NOT NULL,
    event_type TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'INFO',
    burst_z_score REAL NOT NULL DEFAULT 0.0,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    source_name TEXT NOT NULL,
    source_url TEXT NOT NULL,
    latitude REAL,
    longitude REAL
);
CREATE INDEX IF NOT EXISTS idx_tl_ws_time ON timeline_events(workspace_id, event_time);

-- TABLE 9: vector_embeddings (INT8 Quantized 384-d Semantic Embeddings)
CREATE TABLE IF NOT EXISTS vector_embeddings (
    record_id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    record_kind TEXT NOT NULL, -- 'ENTITY' or 'EVIDENCE'
    text_hash TEXT NOT NULL,
    vector_int8_blob BLOB NOT NULL,
    scale_factor REAL NOT NULL DEFAULT 1.0,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_vec_ws ON vector_embeddings(workspace_id, record_kind);

-- TABLE 10: search_index_fts (SQLite FTS5 BM25 Technical Index)
CREATE VIRTUAL TABLE IF NOT EXISTS search_index_fts USING fts5(
    record_id UNINDEXED,
    workspace_id UNINDEXED,
    record_kind UNINDEXED,
    title,
    identifiers,
    body_text
);

-- TABLE 11: spatial_rtree (SQLite R*Tree 2D Geospatial Index)
CREATE VIRTUAL TABLE IF NOT EXISTS spatial_rtree USING rtree(
    id,
    min_lat, max_lat,
    min_lon, max_lon
);

-- TABLE 12: connector_configs (24 Connectors + Fernet Encrypted API Vault + Circuit Breaker State)
CREATE TABLE IF NOT EXISTS connector_configs (
    connector_id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    category TEXT NOT NULL,
    upstream_lineage_family TEXT NOT NULL,
    default_admiralty_reliability TEXT NOT NULL DEFAULT 'B',
    requires_api_key INTEGER NOT NULL DEFAULT 0,
    encrypted_api_key TEXT NOT NULL DEFAULT '',
    enabled INTEGER NOT NULL DEFAULT 1,
    is_passive INTEGER NOT NULL DEFAULT 1,
    rate_limit_rpm INTEGER NOT NULL DEFAULT 30,
    cache_ttl_seconds INTEGER NOT NULL DEFAULT 3600,
    circuit_state TEXT NOT NULL DEFAULT 'CLOSED', -- CLOSED, OPEN, HALF_OPEN
    failure_count INTEGER NOT NULL DEFAULT 0,
    base_url TEXT NOT NULL,
    docs_url TEXT NOT NULL,
    description TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- TABLE 13: tasks & reports
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    connector_id TEXT NOT NULL,
    target_query TEXT NOT NULL,
    target_type TEXT NOT NULL,
    pivot_depth INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL, -- QUEUED, RUNNING, COMPLETED, FAILED, SKIPPED
    progress INTEGER NOT NULL DEFAULT 0,
    entities_found INTEGER NOT NULL DEFAULT 0,
    claims_found INTEGER NOT NULL DEFAULT 0,
    staged_count INTEGER NOT NULL DEFAULT 0,
    error_message TEXT DEFAULT '',
    result_summary_json TEXT NOT NULL DEFAULT '{}',
    started_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS reports (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    report_type TEXT NOT NULL DEFAULT 'COMPREHENSIVE',
    tlp_marking TEXT NOT NULL DEFAULT 'TLP:CLEAR',
    content_markdown TEXT NOT NULL,
    citation_audit_json TEXT NOT NULL DEFAULT '{}',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

-- TABLE 14: http_cache, audit_logs & app_settings
CREATE TABLE IF NOT EXISTS http_cache (
    cache_key TEXT PRIMARY KEY,
    connector_id TEXT NOT NULL,
    url TEXT NOT NULL,
    status_code INTEGER NOT NULL,
    response_json TEXT NOT NULL,
    created_epoch REAL NOT NULL,
    expires_epoch REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id TEXT PRIMARY KEY,
    seq_no INTEGER NOT NULL,
    timestamp TEXT NOT NULL,
    action TEXT NOT NULL,
    workspace_id TEXT DEFAULT '',
    actor TEXT NOT NULL DEFAULT 'local_analyst',
    details TEXT NOT NULL,
    prev_hash TEXT NOT NULL,
    entry_hash TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS app_settings (
    setting_key TEXT PRIMARY KEY,
    setting_value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

---

## 3. Data Retention, Deletion & Migration Strategy
1. **Cascade Deletion & Workspace Purge:** Deleting a workspace (`DELETE FROM workspaces WHERE id = ?`) automatically cascades across `entities`, `claims`, `evidence_artifacts`, `entity_blocking_keys`, `entity_merge_ledger`, `timeline_events`, `vector_embeddings`, `tasks`, and `reports`, and explicitly purges matching `workspace_id` rows in `search_index_fts`, followed by `PRAGMA wal_checkpoint(TRUNCATE);`.
2. **Idempotent Schema Migrations:** `DatabaseManager.init_db()` checks `PRAGMA user_version;`. If `user_version < 2`, it executes non-destructive `ALTER TABLE` / `CREATE TABLE IF NOT EXISTS` migrations and increments `PRAGMA user_version = 2;`.
