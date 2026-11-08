# DATA_FLOW_AND_SCHEMA_DESIGN.md — Bitemporal, Provenance-Aware & FollowTheMoney-Aligned Data Schemas

## 1. Core Data Modeling Principles
To overcome the limitations of flat entity tables, **LocalOSINT v2.0** introduces four foundational schema innovations:
1. **[FollowTheMoney (FtM)](https://github.com/alephdata/followthemoney)-Aligned Typed Entity & Interval Ontology:** Entities (`Organization`, `Company`, `Person`, `LegalEntity`, `Domain`, `IPv4Address`, `AutonomousSystem`, `X509Certificate`, `Vulnerability`, `CryptoWallet`, `Sanction`, `Document`) validate typed multi-valued properties.
2. **Reified Claims (`claims` Table) & Epistemic Stratification ([Eigenius / W3C PROV](https://akkonrad.medium.com/how-do-you-know-that-adding-a-provenance-layer-to-a-supply-chain-knowledge-graph-in-neo4j-0fff700c14fb)):** Instead of overwriting an entity's JSON blob when two sources disagree on an attribute (e.g., HQ location or registrar), every attribute assertion and relationship is backed by a **Claim** carrying an explicit `epistemic_status`:
   - `OBSERVED_FACT` (single direct authoritative capture)
   - `CORROBORATED_FACT` ($\ge 2$ independent lineage families agree; Subjective Logic $b \ge 0.80$)
   - `DERIVED_INFERENCE` (computed via Fellegi-Sunter ER, graph transitivity, or AI synthesis)
   - `ANALYST_HYPOTHESIS` (manual analyst assertion under investigation)
   - `UNVERIFIED_CLAIM` (low-reliability single mention)
3. **Bitemporal Modeling (`observed_at` vs. `valid_from` / `valid_until`):** Separates *transaction time* (when the collector observed the record) from *valid time* (when the domain resolved to that IP, or when a director held office).
4. **Subjective Logic Opinion Tuple ($\omega = (b, d, u, a)$):** Stored directly on entities, claims, and relationships so the UI can filter or color-code by **Belief ($b$)**, **Disbelief / Contradiction ($d$)**, and **Uncertainty ($u$)**.

---

## 2. Stage-by-Stage Data Flow Schemas (Pydantic v2 / JSON Contracts)

### Stage 1 & 2: Collection $\rightarrow$ Raw Provenance Artifact (`RawEvidenceRecord`)
```json
{
  "evidence_id": "ev_01930a8f4c12",
  "workspace_id": "ws_alpha01",
  "connector_id": "gleif_lei",
  "upstream_lineage_family": "GLEIF_LOU_REGISTRY",
  "source_url": "https://api.gleif.org/api/v1/lei-records/5493006MHB84DD0ZWV18",
  "http_status": 200,
  "response_headers_hash": "8f4b2e19...",
  "payload_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "admiralty_reliability": "A",
  "admiralty_credibility": 1,
  "observed_at": "2026-11-08T05:00:00Z",
  "derived_from_evidence_id": null
}
```

### Stage 3, 4 & 5: Validation, Normalization & Extraction $\rightarrow$ `NormalizedExtractionBundle`
```json
{
  "evidence_id": "ev_01930a8f4c12",
  "entities": [
    {
      "temp_id": "tmp_ent_1",
      "ftm_schema": "Company",
      "canonical_key": "lei:5493006mhb84dd0zwv18",
      "display_label": "Cloudflare, Inc.",
      "blocking_keys": ["name:cloudflare", "lei:5493006mhb84dd0zwv18", "jur:us-de"],
      "properties": {
        "leiCode": ["5493006MHB84DD0ZWV18"],
        "jurisdiction": ["US-DE"],
        "hqAddress": ["101 Townsend St, San Francisco, CA 94107, US"]
      }
    }
  ],
  "claims": [
    {
      "subject_temp_id": "tmp_ent_1",
      "predicate": "HAS_JURISDICTION",
      "object_value": "US-DE",
      "epistemic_status": "OBSERVED_FACT",
      "valid_from": "2009-07-01T00:00:00Z",
      "valid_until": null
    }
  ]
}
```

---

## 3. Complete Production SQLite WAL + FTS5 + R*Tree + Vector Schema

```sql
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA foreign_keys = ON;

-- 1. Workspaces (Case Management & TLP Governance)
CREATE TABLE workspaces (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    tlp_marking TEXT DEFAULT 'TLP:CLEAR',
    scope_domains_json TEXT DEFAULT '[]',
    max_pivot_depth INTEGER DEFAULT 2,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- 2. Provenance Evidence Vault (W3C PROV Entities & Lineage DAG)
CREATE TABLE evidence_artifacts (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    connector_id TEXT NOT NULL,
    upstream_lineage_family TEXT NOT NULL,
    source_name TEXT NOT NULL,
    source_url TEXT NOT NULL,
    parent_evidence_id TEXT REFERENCES evidence_artifacts(id), -- W3C PROV wasDerivedFrom
    independence_weight REAL DEFAULT 1.0,                       -- Dong copying discount (0.05..1.0)
    admiralty_reliability TEXT DEFAULT 'B',                     -- A..F
    admiralty_credibility INTEGER DEFAULT 2,                    -- 1..6
    title TEXT NOT NULL,
    summary_text TEXT NOT NULL,
    raw_payload_json TEXT NOT NULL,
    payload_sha256 TEXT NOT NULL,
    simhash_64 INTEGER,                                         -- Near-duplicate document detection
    observed_at TEXT NOT NULL
);
CREATE INDEX idx_ev_ws_sha ON evidence_artifacts(workspace_id, payload_sha256);
CREATE INDEX idx_ev_lineage ON evidence_artifacts(workspace_id, upstream_lineage_family);

-- 3. Canonical Entities (FollowTheMoney-Aligned Nodes)
CREATE TABLE entities (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    ftm_schema TEXT NOT NULL,                                   -- Domain, IPv4Address, Company, Person, Vulnerability...
    canonical_value TEXT NOT NULL,
    display_label TEXT NOT NULL,
    is_staged INTEGER DEFAULT 0,                                -- 1 = in staging triage buffer
    is_shared_infra INTEGER DEFAULT 0,                          -- 1 = RIOT-Lite CDN/Resolver super-node
    -- Subjective Logic Opinion Tuple ω = (b, d, u, a)
    sl_belief REAL DEFAULT 0.70,
    sl_disbelief REAL DEFAULT 0.00,
    sl_uncertainty REAL DEFAULT 0.30,
    sl_base_rate REAL DEFAULT 0.50,
    projected_probability REAL GENERATED ALWAYS AS (sl_belief + sl_base_rate * sl_uncertainty) VIRTUAL,
    -- Risk & Graph Analytics Cache
    risk_score INTEGER DEFAULT 0,
    risk_reasons_json TEXT DEFAULT '[]',
    leiden_community_id INTEGER DEFAULT 0,
    ief_pagerank REAL DEFAULT 0.0,
    -- Spatiotemporal & Properties
    latitude REAL,
    longitude REAL,
    geohash_8 TEXT,
    properties_json TEXT DEFAULT '{}',
    aliases_json TEXT DEFAULT '[]',
    independent_source_count INTEGER DEFAULT 1,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL
);
CREATE UNIQUE INDEX idx_ent_ws_schema_canon ON entities(workspace_id, ftm_schema, canonical_value);
CREATE INDEX idx_ent_geohash ON entities(workspace_id, geohash_8);

-- 4. Entity Blocking Keys Table (For O(N log N) Sorted Neighborhood & MinHash LSH)
CREATE TABLE entity_blocking_keys (
    entity_id TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    workspace_id TEXT NOT NULL,
    pass_type TEXT NOT NULL,                                    -- 'PHONETIC_NAME', 'APEX_DOMAIN', 'CIDR24', 'MINHASH_BAND'
    blocking_key TEXT NOT NULL
);
CREATE INDEX idx_blocking_lookup ON entity_blocking_keys(workspace_id, pass_type, blocking_key);

-- 5. Reified Bitemporal Claims & Relationships (Edges + Attribute Attestations)
CREATE TABLE claims (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    subject_entity_id TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    predicate TEXT NOT NULL,                                    -- e.g., 'RESOLVES_TO', 'OWNS_COMPANY', 'VULNERABLE_TO'
    object_entity_id TEXT REFERENCES entities(id) ON DELETE CASCADE,
    object_literal TEXT,
    epistemic_status TEXT NOT NULL DEFAULT 'OBSERVED_FACT',     -- OBSERVED_FACT, CORROBORATED_FACT, DERIVED_INFERENCE, HYPOTHESIS
    sl_belief REAL DEFAULT 0.75,
    sl_disbelief REAL DEFAULT 0.00,
    sl_uncertainty REAL DEFAULT 0.25,
    ief_edge_weight REAL DEFAULT 1.0,
    valid_from TEXT,                                            -- Bitemporal valid start
    valid_until TEXT,                                           -- Bitemporal valid end
    first_observed_at TEXT NOT NULL,
    last_observed_at TEXT NOT NULL
);
CREATE INDEX idx_claims_graph ON claims(workspace_id, subject_entity_id, object_entity_id, predicate);

-- 6. Claim-to-Evidence Provenance Junction (Many-to-Many Attribution)
CREATE TABLE claim_evidence (
    claim_id TEXT NOT NULL REFERENCES claims(id) ON DELETE CASCADE,
    evidence_id TEXT NOT NULL REFERENCES evidence_artifacts(id) ON DELETE CASCADE,
    stance TEXT DEFAULT 'SUPPORTS',                             -- 'SUPPORTS' or 'CONTRADICTS'
    PRIMARY KEY (claim_id, evidence_id)
);

-- 7. Entity Resolution Audit & Reversible Merge Ledger
CREATE TABLE entity_merge_ledger (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    winner_entity_id TEXT NOT NULL,
    absorbed_entity_snapshot_json TEXT NOT NULL,
    fellegi_sunter_log2_weight REAL NOT NULL,
    match_probability REAL NOT NULL,
    waterfall_explanation_json TEXT NOT NULL,
    merged_by TEXT DEFAULT 'analyst',
    merged_at TEXT NOT NULL
);

-- 8. Full-Text Search (FTS5 BM25) & Spatial R*Tree Virtual Tables
CREATE VIRTUAL TABLE search_index_fts USING fts5(
    record_id UNINDEXED,
    workspace_id UNINDEXED,
    record_kind UNINDEXED,
    title,
    identifiers,
    body_text,
    tokenize = "unicode61 tokenchars '.-_:/@'"
);

CREATE VIRTUAL TABLE spatial_rtree USING rtree(
    rowid,
    min_lat, max_lat,
    min_lon, max_lon
);
```
*(Note: Storing `absorbed_entity_snapshot_json` in `entity_merge_ledger` ensures every entity resolution merge is **100% reversible** if new evidence later proves two merged entities are distinct).*
