# 09 — DATABASE AND DATA MODEL (`M02`)

**Target Repository:** [`https://github.com/Manan7289/OSINT.git`](https://github.com/Manan7289/OSINT.git)  
**Target Files:** `backend/core/database.py`, `backend/core/ontology.py`  
**Engine:** Single-File Local SQLite 3.45+ with `WAL` Mode, `FTS5` Full-Text Search, `R*Tree` Spatial Indexing, and Temporal Track History

---

## 1. Storage Architecture Overview

`LocalOSINT v3.0` retains the zero-external-database philosophy of `Manan7289/OSINT` (`data/osint_command.db`) while expanding the 14 existing tables to **20 tables** to support:
1. High-frequency **4D spatiotemporal trajectory playback** (`geo_tracks`).
2. **Crucix-style Sweep-Delta tracking** (`sweep_runs`, `sweep_deltas`).
3. **Argos-style Sanctions Cross-Referencing & Geofence Alerting** (`sanctions_index`, `geofence_zones`).
4. **Privacy-Preserving Visual Intelligence & Consent-Gated Galleries** (`visual_assets`, `consented_face_gallery`).

### Mandatory SQLite Pragmas (`backend/core/database.py`)
```sql
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA foreign_keys = ON;
PRAGMA temp_store = MEMORY;
PRAGMA mmap_size = 268435456; -- 256 MB memory-mapped I/O
PRAGMA cache_size = -64000;   -- 64 MB page cache
```

---

## 2. Complete 20-Table SQLite DDL Schema

### 2.1 Existing 14 Core Tables (Retained from v2.0)
1. `investigations` — Case workspaces (`investigation_id`, `title`, `description`, `status`, `created_at`).
2. `entities` — Canonical knowledge graph nodes (`entity_id`, `investigation_id`, `entity_type`, `canonical_name`, `aliases_json`, `attributes_json`, `risk_score`, `belief`, `disbelief`, `uncertainty`, `base_rate`, `pagerank_score`, `community_id`, `lat`, `lon`, `first_seen_at`, `last_seen_at`).
3. `edges` — Directed typed relationships (`edge_id`, `investigation_id`, `source_entity_id`, `target_entity_id`, `edge_type`, `weight`, `belief`, `disbelief`, `uncertainty`, `attributes_json`, `created_at`).
4. `sources` — Registered OSINT collectors & NATO Admiralty reliability priors (`source_id`, `name`, `adapter_type`, `admiralty_reliability`, `base_uncertainty`).
5. `raw_observations` — Content-addressable raw responses (`observation_id`, `source_id`, `content_sha256`, `raw_payload_json`, `fetched_at`).
6. `provenance_assertions` — W3C PROV-DM assertion records (`assertion_id`, `subject_id`, `predicate`, `object_value`, `source_id`, `observation_id`, `admiralty_code`, `belief`, `disbelief`, `uncertainty`, `observed_at`).
7. `entity_merges` — Reversible Fellegi-Sunter merge lineage (`merge_id`, `Survivor_entity_id`, `absorbed_entity_id`, `fs_log_weight`, `posterior_prob`, `merged_at`, `is_reverted`).
8. `er_blocking_keys` — Multi-pass blocking keys (`entity_id`, `pass_number`, `blocking_key`).
9. `documents_fts` — `USING fts5(doc_id UNINDEXED, entity_id UNINDEXED, title, body, source_name, tokenize='porter unicode61')`.
10. `embeddings` — 384-D float32 vector blobs (`embedding_id`, `entity_id`, `vector_blob`, `text_snippet`).
11. `spatial_rtree` — `USING rtree(rtree_id, min_lat, max_lat, min_lon, max_lon)`.
12. `spatial_entity_map` — Maps `rtree_id` integer keys to `entity_id` / `track_id`.
13. `collector_cache` — HTTP ETag / TTL response cache (`cache_key`, `source_name`, `response_json`, `fetched_at`, `expires_at`).
14. `audit_log` — Tamper-evident SHA-256 hash chain (`seq_id`, `timestamp`, `actor`, `action`, `target_id`, `details_json`, `prev_hash`, `record_hash`).

### 2.2 New v3.0 Tables (Tables 15–20)

```sql
-- 15. 4D Spatiotemporal Trajectory Archive (Aircraft, Vessels, Satellites, Events)
CREATE TABLE IF NOT EXISTS geo_tracks (
    track_id TEXT PRIMARY KEY,
    entity_id TEXT NOT NULL REFERENCES entities(entity_id) ON DELETE CASCADE,
    layer_type TEXT NOT NULL,            -- AIRCRAFT | VESSEL | SATELLITE | EARTHQUAKE | WILDFIRE | WEATHER | CAMERA | CONFLICT
    lat REAL NOT NULL,
    lon REAL NOT NULL,
    altitude_m REAL DEFAULT 0.0,
    velocity_mps REAL DEFAULT 0.0,
    heading_deg REAL DEFAULT 0.0,
    telemetry_status TEXT NOT NULL,      -- LIVE | DELAYED | ORBITAL_PROPAGATED | HISTORICAL | OFFLINE_BOOTSTRAP
    is_sanctioned INTEGER DEFAULT 0,
    is_military INTEGER DEFAULT 0,
    squawk TEXT DEFAULT NULL,
    metadata_json TEXT DEFAULT '{}',
    observed_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_geo_tracks_time ON geo_tracks(observed_at DESC);
CREATE INDEX IF NOT EXISTS idx_geo_tracks_layer_time ON geo_tracks(layer_type, observed_at DESC);
CREATE INDEX IF NOT EXISTS idx_geo_tracks_entity ON geo_tracks(entity_id, observed_at DESC);

-- 16. Crucix-Style Sweep Runs
CREATE TABLE IF NOT EXISTS sweep_runs (
    sweep_id TEXT PRIMARY KEY,
    investigation_id TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    status TEXT NOT NULL,                -- RUNNING | COMPLETED | PARTIAL_FAILURE
    sources_polled INTEGER DEFAULT 0,
    sources_succeeded INTEGER DEFAULT 0,
    new_entities_count INTEGER DEFAULT 0,
    escalated_count INTEGER DEFAULT 0,
    sanction_matches_count INTEGER DEFAULT 0,
    geofence_alerts_count INTEGER DEFAULT 0,
    escalation_score REAL DEFAULT 0.0,
    summary_briefing_md TEXT DEFAULT ''
);

-- 17. Crucix-Style Sweep Deltas (Granular Changes Between Sweeps)
CREATE TABLE IF NOT EXISTS sweep_deltas (
    delta_id TEXT PRIMARY KEY,
    sweep_id TEXT NOT NULL REFERENCES sweep_runs(sweep_id) ON DELETE CASCADE,
    entity_id TEXT REFERENCES entities(entity_id) ON DELETE SET NULL,
    delta_type TEXT NOT NULL,            -- NEW_ENTITY | ESCALATED_RISK | SANCTION_MATCH_DETECTED | ENTERED_GEOFENCE | AIS_DARK_GAP | RESOLVED_EVENT
    severity TEXT NOT NULL,              -- CRITICAL | HIGH | MEDIUM | LOW | INFO
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    prev_value_json TEXT DEFAULT '{}',
    curr_value_json TEXT DEFAULT '{}',
    lat REAL,
    lon REAL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sweep_deltas_sweep ON sweep_deltas(sweep_id, severity);

-- 18. Argos-Style Sanctions Cross-Reference Index (OFAC SDN)
CREATE TABLE IF NOT EXISTS sanctions_index (
    sanction_id TEXT PRIMARY KEY,
    sdn_name TEXT NOT NULL,
    sdn_type TEXT NOT NULL,              -- VESSEL | AIRCRAFT | ENTITY | INDIVIDUAL
    program TEXT NOT NULL,               -- e.g., IRAN, RUSSIA-EO14024, DPRK, SDGT
    mmsi TEXT,
    imo TEXT,
    icao24 TEXT,
    tail_number TEXT,
    flag_country TEXT,
    remarks TEXT,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sanctions_mmsi ON sanctions_index(mmsi);
CREATE INDEX IF NOT EXISTS idx_sanctions_imo ON sanctions_index(imo);
CREATE INDEX IF NOT EXISTS idx_sanctions_tail ON sanctions_index(tail_number);
CREATE INDEX IF NOT EXISTS idx_sanctions_icao24 ON sanctions_index(icao24);

-- 19. User-Defined Geofence Alert Zones & Notification Rules
CREATE TABLE IF NOT EXISTS geofence_zones (
    geofence_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    polygon_geojson TEXT NOT NULL,       -- GeoJSON Polygon coordinates
    monitored_layers_json TEXT NOT NULL, -- e.g. ["AIRCRAFT", "VESSEL", "EARTHQUAKE", "CONFLICT"]
    min_severity TEXT DEFAULT 'MEDIUM',
    notify_channels_json TEXT DEFAULT '["SSE"]', -- ["SSE", "TELEGRAM", "DISCORD", "WEBHOOK"]
    is_active INTEGER DEFAULT 1,
    created_at TEXT NOT NULL
);

-- 20. Privacy-Preserving Visual Intelligence Assets & Consented Gallery
CREATE TABLE IF NOT EXISTS visual_assets (
    asset_id TEXT PRIMARY KEY,
    investigation_id TEXT NOT NULL,
    entity_id TEXT REFERENCES entities(entity_id) ON DELETE SET NULL,
    filename TEXT NOT NULL,
    sha256_hash TEXT NOT NULL,
    phash_64 TEXT NOT NULL,              -- 16-char hex of 64-bit pHash
    dhash_64 TEXT NOT NULL,              -- 16-char hex of 64-bit dHash
    ahash_64 TEXT NOT NULL,              -- 16-char hex of 64-bit aHash
    width INTEGER NOT NULL,
    height INTEGER NOT NULL,
    laplacian_sharpness REAL NOT NULL,
    quality_grade TEXT NOT NULL,         -- HIGH_SHARPNESS | MODERATE | POOR_BLURRY
    faces_detected INTEGER DEFAULT 0,
    bystanders_blurred INTEGER DEFAULT 1,
    exif_json TEXT DEFAULT '{}',
    c2pa_json TEXT DEFAULT '{}',
    lat REAL,
    lon REAL,
    redacted_image_b64 TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS consented_face_gallery (
    gallery_id TEXT PRIMARY KEY,
    subject_name TEXT NOT NULL,
    consent_purpose TEXT NOT NULL,
    consent_attestation INTEGER NOT NULL CHECK (consent_attestation = 1),
    embedding_blob BLOB NOT NULL,        -- 128-D float32 SFace L2-normalized vector
    image_sha256 TEXT NOT NULL,
    laplacian_sharpness REAL NOT NULL,
    enrolled_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);
```

---

## 3. Entity & Edge Ontology Extensions (`backend/core/ontology.py`)

### 3.1 Supported `EntityType` Enum (14 Types)
- **Existing 9:** `PERSON`, `ORGANIZATION`, `DOMAIN`, `IP_ADDRESS`, `EMAIL`, `USERNAME`, `LOCATION`, `EVENT`, `VULNERABILITY`
- **New 5 (v3.0):**
  10. `AIRCRAFT` (attributes: `icao24`, `callsign`, `origin_country`, `is_military`, `is_sanctioned`, `squawk`, `baro_altitude_m`, `velocity_mps`)
  11. `VESSEL` (attributes: `mmsi`, `imo`, `vessel_name`, `ship_type`, `flag_country`, `is_sanctioned`, `sog_knots`, `cog_deg`, `nav_status`)
  12. `SATELLITE` (attributes: `norad_id`, `sat_name`, `orbit_regime`, `inclination_deg`, `period_min`, `tle_line1`, `tle_line2`)
  13. `CAMERA` (attributes: `camera_id`, `operator`, `stream_url`, `snapshot_url`, `heading_deg`, `road_or_area`)
  14. `VISUAL_ASSET` (attributes: `sha256_hash`, `phash_64`, `quality_grade`, `faces_detected`, `bystanders_blurred`)

### 3.2 Supported `EdgeType` Enum (18 Types)
- **Existing 12:** `RESOLVES_TO`, `HOSTED_ON`, `ISSUED_TO`, `AFFECTS`, `EXPLOITED_BY`, `LOCATED_AT`, `ASSOCIATED_WITH`, `COMMUNICATES_WITH`, `OWNS`, `MENTIONED_IN`, `DERIVED_FROM`, `MERGED_INTO`
- **New 6 (v3.0):**
  13. `SANCTIONED_UNDER` (`AIRCRAFT`/`VESSEL`/`ORGANIZATION` $ightarrow$ `OFAC SDN Program`)
  14. `PROXIMATE_TO_EVENT` (Asset within $50	ext{ km}$ & $2	ext{h}$ of an active `EVENT`)
  15. `POTENTIAL_STS_TRANSFER` (Maritime co-traveler / ship-to-ship rendezvous)
  16. `ENTERED_GEOFENCE` (Asset $ightarrow$ `geofence_zones`)
  17. `VISUALLY_SIMILAR_TO` (`VISUAL_ASSET` $\leftrightarrow$ `VISUAL_ASSET` with $d_H(	ext{pHash}) \le 10$)
  18. `CAPTURED_NEAR` (`VISUAL_ASSET` $ightarrow$ `LOCATION` / `EVENT`)
