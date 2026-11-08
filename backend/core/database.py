"""backend/core/database.py - SQLite WAL, FTS5, R*Tree & Relational Property Graph Storage.

M02: Bitemporal SQLite WAL/FTS5/R*Tree & FollowTheMoney Storage Engine.
"""

from __future__ import annotations

import datetime
import json
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Tuple

from backend.core.config import DB_PATH, vault
from backend.core.ontology import (
    canonicalize_entity,
    encode_geohash,
    generate_blocking_keys,
)
from backend.core.security import HashChainedAuditLogger

SCHEMA_SQL = """
-- TABLE 1: workspaces (Investigation Case Isolation)
CREATE TABLE IF NOT EXISTS workspaces (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    tlp_marking TEXT NOT NULL DEFAULT 'TLP:CLEAR',
    opsec_mode TEXT NOT NULL DEFAULT 'STANDARD',
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
    ftm_schema TEXT NOT NULL,
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
    pass_type TEXT NOT NULL,
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
    epistemic_status TEXT NOT NULL DEFAULT 'OBSERVED_FACT',
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
    stance TEXT NOT NULL DEFAULT 'SUPPORTS',
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
    record_kind TEXT NOT NULL,
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

-- TABLE 12: connector_configs
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
    circuit_state TEXT NOT NULL DEFAULT 'CLOSED',
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
    status TEXT NOT NULL,
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

-- TABLE 15: geo_tracks (4D Spatiotemporal Trajectory Archive)
CREATE TABLE IF NOT EXISTS geo_tracks (
    track_id TEXT PRIMARY KEY,
    entity_id TEXT,
    layer_type TEXT NOT NULL,
    lat REAL NOT NULL,
    lon REAL NOT NULL,
    altitude_m REAL DEFAULT 0.0,
    velocity_mps REAL DEFAULT 0.0,
    heading_deg REAL DEFAULT 0.0,
    telemetry_status TEXT NOT NULL,
    is_sanctioned INTEGER DEFAULT 0,
    is_military INTEGER DEFAULT 0,
    squawk TEXT DEFAULT NULL,
    metadata_json TEXT DEFAULT '{}',
    observed_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_geo_tracks_time ON geo_tracks(observed_at DESC);
CREATE INDEX IF NOT EXISTS idx_geo_tracks_layer_time ON geo_tracks(layer_type, observed_at DESC);
CREATE INDEX IF NOT EXISTS idx_geo_tracks_entity ON geo_tracks(entity_id, observed_at DESC);

-- TABLE 16: sweep_runs (Crucix-Style Sweep Runs)
CREATE TABLE IF NOT EXISTS sweep_runs (
    sweep_id TEXT PRIMARY KEY,
    investigation_id TEXT NOT NULL DEFAULT 'default',
    started_at TEXT NOT NULL,
    completed_at TEXT,
    status TEXT NOT NULL,
    sources_polled INTEGER DEFAULT 0,
    sources_succeeded INTEGER DEFAULT 0,
    new_entities_count INTEGER DEFAULT 0,
    escalated_count INTEGER DEFAULT 0,
    sanction_matches_count INTEGER DEFAULT 0,
    geofence_alerts_count INTEGER DEFAULT 0,
    escalation_score REAL DEFAULT 0.0,
    summary_briefing_md TEXT DEFAULT ''
);

-- TABLE 17: sweep_deltas (Granular Changes Between Sweeps)
CREATE TABLE IF NOT EXISTS sweep_deltas (
    delta_id TEXT PRIMARY KEY,
    sweep_id TEXT NOT NULL REFERENCES sweep_runs(sweep_id) ON DELETE CASCADE,
    entity_id TEXT,
    delta_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    prev_value_json TEXT DEFAULT '{}',
    curr_value_json TEXT DEFAULT '{}',
    lat REAL,
    lon REAL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sweep_deltas_sweep ON sweep_deltas(sweep_id, severity);

-- TABLE 18: sanctions_index (Argos-Style OFAC SDN Cross-Reference)
CREATE TABLE IF NOT EXISTS sanctions_index (
    sanction_id TEXT PRIMARY KEY,
    sdn_name TEXT NOT NULL,
    sdn_type TEXT NOT NULL,
    program TEXT NOT NULL,
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

-- TABLE 19: geofence_zones (User-Defined Geofence Alert Zones)
CREATE TABLE IF NOT EXISTS geofence_zones (
    geofence_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    polygon_geojson TEXT NOT NULL,
    monitored_layers_json TEXT NOT NULL DEFAULT '["AIRCRAFT", "VESSEL", "EARTHQUAKE", "CONFLICT"]',
    min_severity TEXT DEFAULT 'MEDIUM',
    notify_channels_json TEXT DEFAULT '["SSE"]',
    is_active INTEGER DEFAULT 1,
    created_at TEXT NOT NULL
);

-- TABLE 20: visual_assets & consented_face_gallery (Privacy-Preserving Visual Studio)
CREATE TABLE IF NOT EXISTS visual_assets (
    asset_id TEXT PRIMARY KEY,
    investigation_id TEXT NOT NULL DEFAULT 'default',
    entity_id TEXT,
    filename TEXT NOT NULL,
    sha256_hash TEXT NOT NULL,
    phash_64 TEXT NOT NULL,
    dhash_64 TEXT NOT NULL,
    ahash_64 TEXT NOT NULL,
    width INTEGER NOT NULL,
    height INTEGER NOT NULL,
    laplacian_sharpness REAL NOT NULL,
    quality_grade TEXT NOT NULL,
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
    embedding_blob BLOB NOT NULL,
    image_sha256 TEXT NOT NULL,
    laplacian_sharpness REAL NOT NULL,
    enrolled_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);
"""

DEFAULT_CONNECTORS = [
    # 18 Keyless Public Connectors
    ("dns_doh", "Cloudflare DoH DNS", "Network & DNS", "Cloudflare", "A", 0, 1, 1, 60, "https://cloudflare-dns.com/dns-query", "https://developers.cloudflare.com/1.1.1.1/encryption/dns-over-https/", "Authoritative DNS resolution (A, AAAA, MX, NS, TXT) via Cloudflare DoH"),
    ("rdap_bootstrap", "IANA / RIR RDAP", "Registry & WHOIS", "ICANN_RIR", "A", 0, 1, 1, 30, "https://rdap.org", "https://about.rdap.org/", "Authoritative registration data (IP, ASN, Domain ownership)"),
    ("crtsh_ct", "crt.sh Certificate Transparency", "Certificates & Infrastructure", "Sectigo_crtsh", "A", 0, 1, 1, 20, "https://crt.sh", "https://crt.sh", "Subdomain and SAN certificate discovery via public CT logs"),
    ("ripestat_data", "RIPEstat BGP & Routing", "Network & Routing", "RIPE_NCC", "A", 0, 1, 1, 30, "https://stat.ripe.net/data", "https://stat.ripe.net/docs/data_api", "BGP routing, routing status, ASN prefixes, and WHOIS data"),
    ("urlscan_public", "urlscan.io Public Search", "Web & Telemetry", "urlscan_io", "B", 0, 1, 1, 30, "https://urlscan.io/api/v1", "https://urlscan.io/docs/api/", "Historical public website scans, DOM snapshots, and IP connections"),
    ("shodan_internetdb", "Shodan InternetDB", "Vulnerability & Ports", "Shodan", "B", 0, 1, 1, 60, "https://internetdb.shodan.io", "https://internetdb.shodan.io", "Keyless open ports, CPEs, hostnames, and known CVE tags"),
    ("nvd_cve_v2", "NIST NVD CVE v2", "Vulnerability & Threat", "NIST", "A", 0, 1, 1, 10, "https://services.nvd.nist.gov/rest/json/cves/2.0", "https://nvd.nist.gov/developers/vulnerabilities", "Authoritative CVE vulnerability descriptions, CVSS v3.1 metrics, and CPEs"),
    ("cisa_kev", "CISA Known Exploited Vulns", "Vulnerability & Threat", "CISA", "A", 0, 1, 1, 10, "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json", "https://www.cisa.gov/known-exploited-vulnerabilities-catalog", "Authoritative catalog of confirmed in-the-wild exploited CVEs"),
    ("first_epss", "FIRST.org EPSS", "Vulnerability & Threat", "FIRST_org", "A", 0, 1, 1, 30, "https://api.first.org/data/v1/epss", "https://www.first.org/epss/api", "Exploit Prediction Scoring System probability and percentile"),
    ("abusech_threatfox", "Abuse.ch ThreatFox", "Threat Intelligence", "Abuse_ch", "B", 0, 1, 1, 30, "https://threatfox-api.abuse.ch/api/v1/", "https://threatfox.abuse.ch/api/", "Community threat intelligence indicators of compromise (IOCs)"),
    ("abusech_urlhaus", "Abuse.ch URLhaus", "Threat Intelligence", "Abuse_ch", "B", 0, 1, 1, 30, "https://urlhaus-api.abuse.ch/v1/", "https://urlhaus.abuse.ch/api/", "Malicious URLs associated with malware distribution"),
    ("abusech_bazaar", "Abuse.ch MalwareBazaar", "Threat Intelligence", "Abuse_ch", "B", 0, 1, 1, 30, "https://mb-api.abuse.ch/api/v1/", "https://bazaar.abuse.ch/api/", "Malware sample hashes, file types, signatures, and YARA tags"),
    ("gleif_lei", "GLEIF Corporate LEI", "Corporate & Due Diligence", "GLEIF", "A", 0, 1, 1, 30, "https://api.gleif.org/api/v1", "https://www.gleif.org/en/lei-data/gleif-api", "Global Legal Entity Identifier Level 1 identity and Level 2 parent/child ownership"),
    ("sec_edgar", "SEC EDGAR Financials", "Corporate & Due Diligence", "SEC_Gov", "A", 0, 1, 1, 10, "https://data.sec.gov", "https://www.sec.gov/edgar/sec-api-documentation", "U.S. public corporate ownership, CIK numbers, and 10-K/10-Q filings"),
    ("opensanctions", "OpenSanctions Watchlists", "Sanctions & Compliance", "OpenSanctions", "A", 0, 1, 1, 30, "https://api.opensanctions.org", "https://www.opensanctions.org/docs/api/", "Global sanctions lists, politically exposed persons (PEPs), and FollowTheMoney records"),
    ("wikidata_sparql", "Wikidata Knowledge Graph", "Knowledge Graph", "Wikimedia", "B", 0, 1, 1, 30, "https://query.wikidata.org/sparql", "https://www.wikidata.org/wiki/Wikidata:SPARQL_query_service", "Structured entities, corporate parents, founders, and identifiers"),
    ("openalex_orgs", "OpenAlex Academic & Orgs", "Scholarly & Corporate", "OurResearch", "B", 0, 1, 1, 30, "https://api.openalex.org/institutions", "https://docs.openalex.org/", "Research institutions, corporate research divisions, and scientific affiliations"),
    ("wayback_cdx", "Internet Archive Wayback CDX", "Historical & Archive", "InternetArchive", "B", 0, 1, 1, 30, "https://web.archive.org/cdx/search/cdx", "https://archive.org/help/wayback_api.php", "Historical website snapshots, archived URL paths, and mime types"),
    ("gdelt_doc_v2", "GDELT 2.0 Global News", "Media & Events", "GDELT", "B", 0, 1, 1, 20, "https://api.gdeltproject.org/api/v2/doc/doc", "https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/", "Global multilingual news coverage, tone, and timeline spikes"),
    ("github_rest", "GitHub Public REST", "Code & Developer", "GitHub", "B", 0, 1, 1, 30, "https://api.github.com", "https://docs.github.com/en/rest", "Public GitHub profiles, organizations, and source code repositories"),
    ("nominatim_osm", "OpenStreetMap Nominatim", "Geospatial", "OpenStreetMap", "A", 0, 1, 1, 30, "https://nominatim.openstreetmap.org", "https://nominatim.org/release-docs/latest/api/Overview/", "Forward and reverse geocoding for geographic location resolution"),
    ("local_doc_forensics", "Local Document Forensics", "Local File Forensics", "LocalHost", "A", 0, 0, 1, 120, "local://forensics", "https://github.com/Manan7289/OSINT", "Local file metadata, EXIF, pypdf, python-docx, and embedded IOC extraction"),
    # 6 Optional Keyed Connectors
    ("shodan_pro", "Shodan Pro API", "Vulnerability & Network", "Shodan", "A", 1, 0, 1, 60, "https://api.shodan.io", "https://developer.shodan.io/", "Full Shodan search queries, vulnerability history, and banners (BYO Key)"),
    ("virustotal_v3", "VirusTotal v3 API", "Threat Intelligence", "Google_VT", "A", 1, 0, 1, 15, "https://www.virustotal.com/api/v3", "https://developers.virustotal.com/reference/overview", "Multi-engine malware verdicts, passive DNS resolutions, and threat actor tags (BYO Key)"),
    ("greynoise_comm", "GreyNoise Community", "Threat Intelligence", "GreyNoise", "B", 1, 0, 1, 30, "https://api.greynoise.io/v3/community", "https://docs.greynoise.io/", "Internet-wide scan noise vs. targeted malicious actor classification (BYO Key)"),
    ("securitytrails_pdns", "SecurityTrails Passive DNS", "DNS & History", "SecurityTrails", "A", 1, 0, 1, 20, "https://api.securitytrails.com/v1", "https://docs.securitytrails.com/", "Historical DNS records, current WHOIS, and domain associations (BYO Key)"),
    ("censys_v2", "Censys Search v2", "Network & Certificates", "Censys", "A", 1, 0, 1, 20, "https://search.censys.io/api/v2", "https://search.censys.io/api", "Internet-wide host and TLS certificate attack surface search (BYO Key)"),
    ("alienvault_otx", "AlienVault OTX", "Threat Intelligence", "AT_T_Cyber", "B", 1, 0, 1, 30, "https://otx.alienvault.com/api/v1", "https://otx.alienvault.com/api", "Crowdsourced Open Threat Exchange pulses and IOC correlation (BYO Key)"),
]

DEFAULT_SETTINGS = [
    ("opsec_mode", "STANDARD"),
    ("offline_mode", "false"),
    ("ai_provider", "local_graphrag"),
    ("staging_threshold", "50"),
    ("user_agent", "LocalOSINT-Workstation/2.0 (Defensive-Research; +http://localhost:8000)"),
]


class DatabaseManager:
    """ACID SQLite WAL + FTS5 + R*Tree Data Access Layer."""

    def __init__(self, db_path: Path | str = DB_PATH) -> None:
        self.db_path = Path(db_path).resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self.init_db()

    @contextmanager
    def get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Provides an isolated connection with WAL pragmas."""
        with self._lock:
            conn = sqlite3.connect(
                str(self.db_path),
                timeout=15.0,
                check_same_thread=False,
            )
            conn.row_factory = sqlite3.Row
            # Execute mandatory pragmas
            conn.execute("PRAGMA journal_mode = WAL;")
            conn.execute("PRAGMA synchronous = NORMAL;")
            conn.execute("PRAGMA foreign_keys = ON;")
            conn.execute("PRAGMA temp_store = MEMORY;")
            conn.execute("PRAGMA mmap_size = 268435456;")
            conn.execute("PRAGMA cache_size = -32000;")
            conn.execute("PRAGMA busy_timeout = 15000;")
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

    def init_db(self) -> None:
        """Initializes database tables, indices, default connectors, and app settings."""
        with self.get_connection() as conn:
            conn.executescript(SCHEMA_SQL)
            # Set schema version
            conn.execute("PRAGMA user_version = 2;")

            # Seed default connectors if empty
            cur = conn.execute("SELECT COUNT(*) FROM connector_configs;")
            if cur.fetchone()[0] == 0:
                now = datetime.datetime.now(datetime.timezone.utc).isoformat()
                for c in DEFAULT_CONNECTORS:
                    cid, dname, cat, lineage, rel, req_key, enabled, is_pass, rpm, base_url, docs_url, desc = c
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO connector_configs (
                            connector_id, display_name, category, upstream_lineage_family,
                            default_admiralty_reliability, requires_api_key, encrypted_api_key,
                            enabled, is_passive, rate_limit_rpm, cache_ttl_seconds,
                            circuit_state, failure_count, base_url, docs_url, description, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, '', ?, ?, ?, 3600, 'CLOSED', 0, ?, ?, ?, ?);
                        """,
                        (cid, dname, cat, lineage, rel, req_key, enabled, is_pass, rpm, base_url, docs_url, desc, now),
                    )

            # Seed default app settings
            now = datetime.datetime.now(datetime.timezone.utc).isoformat()
            for k, v in DEFAULT_SETTINGS:
                conn.execute(
                    "INSERT OR IGNORE INTO app_settings (setting_key, setting_value, updated_at) VALUES (?, ?, ?);",
                    (k, v, now),
                )

    # -------------------------------------------------------------------------
    # Workspaces
    # -------------------------------------------------------------------------

    def create_workspace(
        self,
        name: str,
        description: str = "",
        tlp_marking: str = "TLP:CLEAR",
        opsec_mode: str = "STANDARD",
        scope_domains: Optional[List[str]] = None,
        max_pivot_depth: int = 2,
        staging_threshold: int = 50,
        tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        import uuid
        ws_id = f"ws_{uuid.uuid4().hex[:12]}"
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        scope_json = json.dumps(scope_domains or [])
        tags_json = json.dumps(tags or [])

        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO workspaces (
                    id, name, description, tlp_marking, opsec_mode,
                    scope_domains_json, max_pivot_depth, staging_threshold,
                    tags_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    ws_id, name, description, tlp_marking, opsec_mode,
                    scope_json, max_pivot_depth, staging_threshold,
                    tags_json, now, now,
                ),
            )
        self.append_audit_log("WORKSPACE_CREATED", f"Workspace '{name}' created ({tlp_marking})", ws_id)
        return self.get_workspace(ws_id)

    def get_workspace(self, workspace_id: str) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            cur = conn.execute("SELECT * FROM workspaces WHERE id = ?;", (workspace_id,))
            row = cur.fetchone()
            if not row:
                return None
            res = dict(row)
            res["scope_domains"] = json.loads(res.pop("scope_domains_json"))
            res["tags"] = json.loads(res.pop("tags_json"))

            # Enrich counts
            ent_cur = conn.execute("SELECT COUNT(*) FROM entities WHERE workspace_id = ? AND is_staged = 0;", (workspace_id,))
            res["entity_count"] = ent_cur.fetchone()[0]

            staged_cur = conn.execute("SELECT COUNT(*) FROM entities WHERE workspace_id = ? AND is_staged = 1;", (workspace_id,))
            res["staged_entity_count"] = staged_cur.fetchone()[0]

            claim_cur = conn.execute("SELECT COUNT(*) FROM claims WHERE workspace_id = ?;", (workspace_id,))
            res["claim_count"] = claim_cur.fetchone()[0]

            ev_cur = conn.execute("SELECT COUNT(*) FROM evidence_artifacts WHERE workspace_id = ?;", (workspace_id,))
            res["evidence_count"] = ev_cur.fetchone()[0]

            rep_cur = conn.execute("SELECT COUNT(*) FROM reports WHERE workspace_id = ?;", (workspace_id,))
            res["report_count"] = rep_cur.fetchone()[0]

            return res

    def list_workspaces(self) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cur = conn.execute("SELECT id FROM workspaces ORDER BY created_at DESC;")
            ids = [r["id"] for r in cur.fetchall()]
        return [self.get_workspace(wid) for wid in ids if wid]

    def delete_workspace(self, workspace_id: str) -> bool:
        with self.get_connection() as conn:
            # Purge FTS rows explicitly before cascade delete
            conn.execute("DELETE FROM search_index_fts WHERE workspace_id = ?;", (workspace_id,))
            cur = conn.execute("DELETE FROM workspaces WHERE id = ?;", (workspace_id,))
            deleted = cur.rowcount > 0

        if deleted:
            try:
                with self.get_connection() as conn:
                    conn.execute("PRAGMA wal_checkpoint(PASSIVE);")
            except Exception:
                pass
            self.append_audit_log("WORKSPACE_DELETED", f"Workspace {workspace_id} purged", workspace_id)
        return deleted

    # -------------------------------------------------------------------------
    # Entities
    # -------------------------------------------------------------------------

    def upsert_entity(
        self,
        workspace_id: str,
        ftm_schema: str,
        raw_value: str,
        display_label: Optional[str] = None,
        is_staged: int = 0,
        sl_opinion: Optional[Tuple[float, float, float, float]] = None,
        admiralty_code: str = "B2",
        risk_score: int = 0,
        risk_reasons: Optional[List[str]] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        location_label: str = "",
        properties: Optional[Dict[str, Any]] = None,
        aliases: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        canonical_value: Optional[str] = None,
    ) -> Dict[str, Any]:
        import uuid
        auto_canon, auto_label, is_shared = canonicalize_entity(ftm_schema, raw_value)
        canon_val = canonical_value if canonical_value is not None else auto_canon
        final_label = display_label or auto_label
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()

        b, d, u, a = sl_opinion or (0.75, 0.00, 0.25, 0.50)
        proj_prob = b + (a * u)

        geohash_val = encode_geohash(latitude, longitude) if (latitude is not None and longitude is not None) else ""
        prop_json = json.dumps(properties or {})
        alias_json = json.dumps(aliases or [])
        tags_json = json.dumps(tags or [])
        reasons_json = json.dumps(risk_reasons or [])

        with self.get_connection() as conn:
            cur = conn.execute(
                "SELECT id, independent_source_count, first_seen_at FROM entities WHERE workspace_id = ? AND ftm_schema = ? AND canonical_value = ?;",
                (workspace_id, ftm_schema, canon_val),
            )
            existing = cur.fetchone()

            if existing:
                ent_id = existing["id"]
                src_count = existing["independent_source_count"] + 1
                conn.execute(
                    """
                    UPDATE entities SET
                        display_label = ?,
                        risk_score = MAX(risk_score, ?),
                        independent_source_count = ?,
                        last_seen_at = ?,
                        properties_json = ?
                    WHERE id = ?;
                    """,
                    (final_label, risk_score, src_count, now, prop_json, ent_id),
                )
            else:
                ent_id = f"ent_{uuid.uuid4().hex[:12]}"
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
                        ent_id, workspace_id, ftm_schema, canon_val, final_label,
                        is_staged, 1 if is_shared else 0, b, d, u,
                        a, proj_prob, admiralty_code, risk_score,
                        reasons_json, latitude, longitude, geohash_val, location_label,
                        prop_json, alias_json, tags_json, 1,
                        now, now,
                    ),
                )
                # Index blocking keys
                keys = generate_blocking_keys(ftm_schema, canon_val)
                for ptype, bkey in keys:
                    conn.execute(
                        "INSERT OR IGNORE INTO entity_blocking_keys (entity_id, workspace_id, pass_type, blocking_key) VALUES (?, ?, ?, ?);",
                        (ent_id, workspace_id, ptype, bkey),
                    )
                # Index in FTS5
                conn.execute(
                    "INSERT INTO search_index_fts (record_id, workspace_id, record_kind, title, identifiers, body_text) VALUES (?, ?, 'ENTITY', ?, ?, ?);",
                    (ent_id, workspace_id, final_label, f"{canon_val} {ftm_schema}", prop_json),
                )

        return self.get_entity(ent_id)

    def get_entity(self, entity_id: str) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            cur = conn.execute("SELECT * FROM entities WHERE id = ?;", (entity_id,))
            row = cur.fetchone()
            if not row:
                return None
            res = dict(row)
            res["properties"] = json.loads(res.pop("properties_json"))
            res["aliases"] = json.loads(res.pop("aliases_json"))
            res["tags"] = json.loads(res.pop("tags_json"))
            res["risk_reasons"] = json.loads(res.pop("risk_reasons_json"))
            return res

    def list_entities(
        self,
        workspace_id: str,
        ftm_schema: Optional[str] = None,
        include_staged: bool = False,
        min_belief: Optional[float] = None,
        search_query: Optional[str] = None,
        limit: int = 500,
    ) -> List[Dict[str, Any]]:
        query = "SELECT id FROM entities WHERE workspace_id = ?"
        params: List[Any] = [workspace_id]

        if not include_staged:
            query += " AND is_staged = 0"
        if ftm_schema:
            query += " AND ftm_schema = ?"
            params.append(ftm_schema)
        if min_belief is not None:
            query += " AND sl_belief >= ?"
            params.append(min_belief)
        if search_query:
            query += " AND (canonical_value LIKE ? OR display_label LIKE ?)"
            params.extend([f"%{search_query}%", f"%{search_query}%"])

        query += " ORDER BY last_seen_at DESC LIMIT ?"
        params.append(limit)

        with self.get_connection() as conn:
            cur = conn.execute(query, params)
            ids = [r["id"] for r in cur.fetchall()]
        return [self.get_entity(eid) for eid in ids if eid]

    def promote_staged_entities(
        self, workspace_id: str, entity_ids: Optional[List[str]] = None, min_risk: Optional[int] = None
    ) -> int:
        with self.get_connection() as conn:
            if entity_ids:
                placeholders = ",".join("?" for _ in entity_ids)
                params: List[Any] = [workspace_id] + entity_ids
                cur = conn.execute(
                    f"UPDATE entities SET is_staged = 0 WHERE workspace_id = ? AND id IN ({placeholders}) AND is_staged = 1;",
                    params,
                )
                count = cur.rowcount
            elif min_risk is not None:
                cur = conn.execute(
                    "UPDATE entities SET is_staged = 0 WHERE workspace_id = ? AND risk_score >= ? AND is_staged = 1;",
                    (workspace_id, min_risk),
                )
                count = cur.rowcount
            else:
                cur = conn.execute(
                    "UPDATE entities SET is_staged = 0 WHERE workspace_id = ? AND is_staged = 1;",
                    (workspace_id,),
                )
                count = cur.rowcount
        return count

    # -------------------------------------------------------------------------
    # Claims (Bitemporal Edges)
    # -------------------------------------------------------------------------

    def add_claim(
        self,
        workspace_id: str,
        subject_entity_id: str,
        predicate: str,
        object_entity_id: Optional[str] = None,
        object_literal: str = "",
        epistemic_status: str = "OBSERVED_FACT",
        sl_opinion: Optional[Tuple[float, float, float, float]] = None,
        ief_edge_weight: float = 1.0,
        attributes: Optional[Dict[str, Any]] = None,
        valid_from: Optional[str] = None,
        valid_until: Optional[str] = None,
        evidence_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        import uuid
        claim_id = f"clm_{uuid.uuid4().hex[:12]}"
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        b, d, u, a = sl_opinion or (0.75, 0.00, 0.25, 0.50)
        proj_prob = b + (a * u)
        attr_json = json.dumps(attributes or {})

        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO claims (
                    id, workspace_id, subject_entity_id, predicate,
                    object_entity_id, object_literal, epistemic_status,
                    sl_belief, sl_disbelief, sl_uncertainty, sl_base_rate,
                    projected_probability, ief_edge_weight, attributes_json,
                    valid_from, valid_until, first_observed_at, last_observed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    claim_id, workspace_id, subject_entity_id, predicate,
                    object_entity_id, object_literal, epistemic_status,
                    b, d, u, a, proj_prob, ief_edge_weight, attr_json,
                    valid_from, valid_until, now, now,
                ),
            )
            # Link evidence
            if evidence_ids:
                for evid in evidence_ids:
                    conn.execute(
                        "INSERT OR IGNORE INTO claim_evidence (claim_id, evidence_id, stance) VALUES (?, ?, 'SUPPORTS');",
                        (claim_id, evid),
                    )

        return self.get_claim(claim_id)

    def get_claim(self, claim_id: str) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            cur = conn.execute("SELECT * FROM claims WHERE id = ?;", (claim_id,))
            row = cur.fetchone()
            if not row:
                return None
            res = dict(row)
            res["attributes"] = json.loads(res.pop("attributes_json"))
            # Fetch attached evidence IDs
            ev_cur = conn.execute("SELECT evidence_id FROM claim_evidence WHERE claim_id = ?;", (claim_id,))
            res["evidence_ids"] = [r["evidence_id"] for r in ev_cur.fetchall()]
            return res

    def list_claims(
        self,
        workspace_id: str,
        epistemic_status: Optional[str] = None,
        as_of_time: Optional[str] = None,
        subject_id: Optional[str] = None,
        object_id: Optional[str] = None,
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        query = "SELECT id FROM claims WHERE workspace_id = ?"
        params: List[Any] = [workspace_id]

        if epistemic_status:
            query += " AND epistemic_status = ?"
            params.append(epistemic_status)

        if subject_id:
            query += " AND subject_entity_id = ?"
            params.append(subject_id)

        if object_id:
            query += " AND object_entity_id = ?"
            params.append(object_id)

        # Bitemporal time-travel filtering: valid_from <= as_of_time and (valid_until is null or valid_until >= as_of_time)
        if as_of_time:
            query += " AND (valid_from IS NULL OR valid_from <= ?) AND (valid_until IS NULL OR valid_until >= ?)"
            params.extend([as_of_time, as_of_time])

        query += " ORDER BY last_observed_at DESC LIMIT ?"
        params.append(limit)

        with self.get_connection() as conn:
            cur = conn.execute(query, params)
            ids = [r["id"] for r in cur.fetchall()]
        return [self.get_claim(cid) for cid in ids if cid]

    # -------------------------------------------------------------------------
    # Evidence Artifacts
    # -------------------------------------------------------------------------

    def add_evidence(
        self,
        workspace_id: str,
        connector_id: str,
        upstream_lineage_family: str,
        source_name: str,
        source_url: str,
        title: str,
        summary_text: str,
        raw_payload: Dict[str, Any],
        parent_evidence_id: Optional[str] = None,
        admiralty_reliability: str = "B",
        admiralty_credibility: int = 2,
        http_status: int = 200,
        response_headers: Optional[Dict[str, str]] = None,
        simhash_64: str = "0000000000000000",
    ) -> Dict[str, Any]:
        import hashlib
        import uuid
        ev_id = f"ev_{uuid.uuid4().hex[:12]}"
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        payload_str = json.dumps(raw_payload, sort_keys=True)
        sha256_hash = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()
        headers_str = json.dumps(response_headers or {})

        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO evidence_artifacts (
                    id, workspace_id, connector_id, upstream_lineage_family,
                    source_name, source_url, parent_evidence_id,
                    admiralty_reliability, admiralty_credibility, http_status,
                    response_headers_json, title, summary_text, raw_payload_json,
                    payload_sha256, simhash_64, observed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    ev_id, workspace_id, connector_id, upstream_lineage_family,
                    source_name, source_url, parent_evidence_id,
                    admiralty_reliability, admiralty_credibility, http_status,
                    headers_str, title, summary_text, payload_str,
                    sha256_hash, simhash_64, now,
                ),
            )
            # Index in FTS5
            conn.execute(
                "INSERT INTO search_index_fts (record_id, workspace_id, record_kind, title, identifiers, body_text) VALUES (?, ?, 'EVIDENCE', ?, ?, ?);",
                (ev_id, workspace_id, title, f"{source_name} {connector_id} {upstream_lineage_family}", summary_text),
            )

        return self.get_evidence(ev_id)

    def get_evidence(self, evidence_id: str) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            cur = conn.execute("SELECT * FROM evidence_artifacts WHERE id = ?;", (evidence_id,))
            row = cur.fetchone()
            if not row:
                return None
            res = dict(row)
            res["raw_payload"] = json.loads(res.pop("raw_payload_json"))
            res["response_headers"] = json.loads(res.pop("response_headers_json"))
            return res

    def list_evidence(self, workspace_id: str, limit: int = 500) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cur = conn.execute(
                "SELECT id FROM evidence_artifacts WHERE workspace_id = ? ORDER BY observed_at DESC LIMIT ?;",
                (workspace_id, limit),
            )
            ids = [r["id"] for r in cur.fetchall()]
        return [self.get_evidence(eid) for eid in ids if eid]

    # -------------------------------------------------------------------------
    # Full-Text Search (FTS5 BM25)
    # -------------------------------------------------------------------------

    def search_fts(self, workspace_id: str, query_str: str, limit: int = 50) -> List[Dict[str, Any]]:
        clean_q = "".join(c for c in query_str if c.isalnum() or c in " -_.:/@").strip()
        if not clean_q:
            return []

        fts_query = f'"{clean_q}"*'
        with self.get_connection() as conn:
            cur = conn.execute(
                """
                SELECT record_id, workspace_id, record_kind, title, identifiers, bm25(search_index_fts) AS rank
                FROM search_index_fts
                WHERE search_index_fts MATCH ? AND workspace_id = ?
                ORDER BY rank ASC
                LIMIT ?;
                """,
                (fts_query, workspace_id, limit),
            )
            return [dict(r) for r in cur.fetchall()]

    # -------------------------------------------------------------------------
    # Audit Logs (Cryptographically Hash-Chained)
    # -------------------------------------------------------------------------

    def append_audit_log(
        self, action: str, details: str, workspace_id: str = "", actor: str = "local_analyst"
    ) -> Dict[str, Any]:
        import uuid
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        entry_id = f"aud_{uuid.uuid4().hex[:12]}"

        with self.get_connection() as conn:
            cur = conn.execute("SELECT seq_no, entry_hash FROM audit_logs ORDER BY seq_no DESC LIMIT 1;")
            last_entry = cur.fetchone()
            if last_entry:
                seq_no = last_entry["seq_no"] + 1
                prev_hash = last_entry["entry_hash"]
            else:
                seq_no = 1
                prev_hash = HashChainedAuditLogger.GENESIS_HASH

            entry_hash = HashChainedAuditLogger.compute_entry_hash(
                prev_hash, seq_no, now, action, details
            )

            conn.execute(
                """
                INSERT INTO audit_logs (id, seq_no, timestamp, action, workspace_id, actor, details, prev_hash, entry_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (entry_id, seq_no, now, action, workspace_id, actor, details, prev_hash, entry_hash),
            )

        return {
            "id": entry_id,
            "seq_no": seq_no,
            "timestamp": now,
            "action": action,
            "workspace_id": workspace_id,
            "details": details,
            "prev_hash": prev_hash,
            "entry_hash": entry_hash,
        }

    def get_audit_logs(self, limit: int = 100) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cur = conn.execute("SELECT * FROM audit_logs ORDER BY seq_no ASC LIMIT ?;", (limit,))
            return [dict(r) for r in cur.fetchall()]

    def verify_audit_log(self) -> Tuple[bool, int]:
        """Cryptographically verifies the SHA-256 audit log hash chain."""
        entries = self.get_audit_logs(limit=1000)
        valid, count, _ = HashChainedAuditLogger.verify_chain(entries)
        return valid, count

    # -------------------------------------------------------------------------
    # Connector Configs & Vault
    # -------------------------------------------------------------------------

    def get_connectors(self) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cur = conn.execute("SELECT * FROM connector_configs ORDER BY category, display_name ASC;")
            rows = [dict(r) for r in cur.fetchall()]
            for r in rows:
                enc_key = r.pop("encrypted_api_key", "")
                r["has_api_key"] = bool(enc_key)
                if enc_key:
                    plain = vault.decrypt(enc_key)
                    r["masked_api_key"] = vault.mask_key(plain)
                else:
                    r["masked_api_key"] = ""
            return rows

    def update_connector(
        self,
        connector_id: str,
        enabled: Optional[bool] = None,
        plaintext_api_key: Optional[str] = None,
        rate_limit_rpm: Optional[int] = None,
    ) -> bool:
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with self.get_connection() as conn:
            updates: List[str] = ["updated_at = ?"]
            params: List[Any] = [now]

            if enabled is not None:
                updates.append("enabled = ?")
                params.append(1 if enabled else 0)

            if plaintext_api_key is not None:
                updates.append("encrypted_api_key = ?")
                enc = vault.encrypt(plaintext_api_key) if plaintext_api_key else ""
                params.append(enc)

            if rate_limit_rpm is not None:
                updates.append("rate_limit_rpm = ?")
                params.append(max(1, rate_limit_rpm))

            params.append(connector_id)
            cur = conn.execute(
                f"UPDATE connector_configs SET {', '.join(updates)} WHERE connector_id = ?;",
                params,
            )
            return cur.rowcount > 0

    # -------------------------------------------------------------------------
    # Settings
    # -------------------------------------------------------------------------

    def get_settings(self) -> Dict[str, str]:
        with self.get_connection() as conn:
            cur = conn.execute("SELECT setting_key, setting_value FROM app_settings;")
            return {r["setting_key"]: r["setting_value"] for r in cur.fetchall()}

    def set_setting(self, key: str, value: str) -> None:
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO app_settings (setting_key, setting_value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(setting_key) DO UPDATE SET setting_value = excluded.setting_value, updated_at = excluded.updated_at;
                """,
                (key, str(value), now),
            )

    # -------------------------------------------------------------------------
    # Tasks & Reports
    # -------------------------------------------------------------------------

    def create_task(
        self, workspace_id: str, connector_id: str, target_query: str, target_type: str = "AUTO", pivot_depth: int = 0
    ) -> Dict[str, Any]:
        import uuid
        task_id = f"task_{uuid.uuid4().hex[:12]}"
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO tasks (
                    id, workspace_id, connector_id, target_query, target_type,
                    pivot_depth, status, progress, entities_found, claims_found,
                    staged_count, started_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'RUNNING', 0, 0, 0, 0, ?);
                """,
                (task_id, workspace_id, connector_id, target_query, target_type, pivot_depth, now),
            )
        return self.get_task(task_id)

    def update_task(
        self,
        task_id: str,
        status: str,
        progress: int = 100,
        entities_found: int = 0,
        claims_found: int = 0,
        staged_count: int = 0,
        error_message: str = "",
        result_summary: Optional[Dict[str, Any]] = None,
    ) -> None:
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        res_json = json.dumps(result_summary or {})
        with self.get_connection() as conn:
            conn.execute(
                """
                UPDATE tasks SET
                    status = ?,
                    progress = ?,
                    entities_found = ?,
                    claims_found = ?,
                    staged_count = ?,
                    error_message = ?,
                    result_summary_json = ?,
                    completed_at = ?
                WHERE id = ?;
                """,
                (status, progress, entities_found, claims_found, staged_count, error_message, res_json, now, task_id),
            )

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            cur = conn.execute("SELECT * FROM tasks WHERE id = ?;", (task_id,))
            row = cur.fetchone()
            if not row:
                return None
            res = dict(row)
            res["result_summary"] = json.loads(res.pop("result_summary_json"))
            return res

    def list_tasks(self, workspace_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            if workspace_id:
                cur = conn.execute("SELECT * FROM tasks WHERE workspace_id = ? ORDER BY started_at DESC LIMIT ?;", (workspace_id, limit))
            else:
                cur = conn.execute("SELECT * FROM tasks ORDER BY started_at DESC LIMIT ?;", (limit,))
            rows = [dict(r) for r in cur.fetchall()]
            for r in rows:
                r["result_summary"] = json.loads(r.pop("result_summary_json"))
            return rows

    def create_report(
        self,
        workspace_id: str,
        title: str,
        content_markdown: str,
        report_type: str = "COMPREHENSIVE",
        tlp_marking: str = "TLP:CLEAR",
        citation_audit: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        import uuid
        rep_id = f"rep_{uuid.uuid4().hex[:12]}"
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        cite_json = json.dumps(citation_audit or {})
        meta_json = json.dumps(metadata or {})

        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO reports (
                    id, workspace_id, title, report_type, tlp_marking,
                    content_markdown, citation_audit_json, metadata_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (rep_id, workspace_id, title, report_type, tlp_marking, content_markdown, cite_json, meta_json, now),
            )
        return {
            "id": rep_id,
            "workspace_id": workspace_id,
            "title": title,
            "report_type": report_type,
            "tlp_marking": tlp_marking,
            "content_markdown": content_markdown,
            "citation_audit": citation_audit or {},
            "metadata": metadata or {},
            "created_at": now,
        }

    def list_reports(self, workspace_id: str) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cur = conn.execute("SELECT * FROM reports WHERE workspace_id = ? ORDER BY created_at DESC;", (workspace_id,))
            rows = [dict(r) for r in cur.fetchall()]
            for r in rows:
                r["citation_audit"] = json.loads(r.pop("citation_audit_json"))
                r["metadata"] = json.loads(r.pop("metadata_json"))
            return rows

    # -------------------------------------------------------------------------
    # Entity Merge Ledger (Reversible Audit Trail)
    # -------------------------------------------------------------------------

    def list_merge_ledger_records(self, workspace_id: str) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cur = conn.execute(
                "SELECT * FROM entity_merge_ledger WHERE workspace_id = ? ORDER BY merged_at DESC;",
                (workspace_id,),
            )
            records = []
            for r in cur.fetchall():
                row_dict = dict(r)
                records.append({
                    "id": row_dict["id"],
                    "workspace_id": row_dict["workspace_id"],
                    "winner_entity_id": row_dict["winner_entity_id"],
                    "absorbed_entity_id": row_dict["absorbed_entity_id"],
                    "absorbed_entity_snapshot": json.loads(row_dict.get("absorbed_entity_snapshot_json") or "{}"),
                    "repointed_claims": json.loads(row_dict.get("repointed_claims_json") or "[]"),
                    "fellegi_sunter_log2_weight": float(row_dict["fellegi_sunter_log2_weight"]),
                    "match_probability": float(row_dict["match_probability"]),
                    "waterfall_explanation": json.loads(row_dict.get("waterfall_explanation_json") or "[]"),
                    "is_reverted": bool(row_dict["is_reverted"]),
                    "merged_at": row_dict["merged_at"],
                    "reverted_at": row_dict["reverted_at"],
                })
            return records

    def get_merge_ledger_record(self, merge_id: str, workspace_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        query = "SELECT * FROM entity_merge_ledger WHERE id = ?"
        params: List[Any] = [merge_id]
        if workspace_id:
            query += " AND workspace_id = ?"
            params.append(workspace_id)
        with self.get_connection() as conn:
            cur = conn.execute(query, params)
            row = cur.fetchone()
            if not row:
                return None
            row_dict = dict(row)
            return {
                "id": row_dict["id"],
                "workspace_id": row_dict["workspace_id"],
                "winner_entity_id": row_dict["winner_entity_id"],
                "absorbed_entity_id": row_dict["absorbed_entity_id"],
                "absorbed_entity_snapshot": json.loads(row_dict.get("absorbed_entity_snapshot_json") or "{}"),
                "repointed_claims": json.loads(row_dict.get("repointed_claims_json") or "[]"),
                "fellegi_sunter_log2_weight": float(row_dict["fellegi_sunter_log2_weight"]),
                "match_probability": float(row_dict["match_probability"]),
                "waterfall_explanation": json.loads(row_dict.get("waterfall_explanation_json") or "[]"),
                "is_reverted": bool(row_dict["is_reverted"]),
                "merged_at": row_dict["merged_at"],
                "reverted_at": row_dict["reverted_at"],
            }

    def insert_merge_ledger_record(
        self,
        merge_id: str,
        workspace_id: str,
        winner_entity_id: str,
        absorbed_entity_id: str,
        absorbed_entity_snapshot: Dict[str, Any],
        repointed_claims: List[Dict[str, Any]],
        fellegi_sunter_log2_weight: float,
        match_probability: float,
        waterfall_explanation: List[Dict[str, Any]],
        merged_at: str,
    ) -> Dict[str, Any]:
        with self.get_connection() as conn:
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
                    merge_id,
                    workspace_id,
                    winner_entity_id,
                    absorbed_entity_id,
                    json.dumps(absorbed_entity_snapshot),
                    json.dumps(repointed_claims),
                    fellegi_sunter_log2_weight,
                    match_probability,
                    json.dumps(waterfall_explanation),
                    merged_at,
                ),
            )
        return self.get_merge_ledger_record(merge_id, workspace_id) or {}

    def revert_merge_ledger_record(self, merge_id: str, workspace_id: Optional[str] = None) -> bool:
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        query = "UPDATE entity_merge_ledger SET is_reverted = 1, reverted_at = ? WHERE id = ?"
        params: List[Any] = [now, merge_id]
        if workspace_id:
            query += " AND workspace_id = ?"
            params.append(workspace_id)
        with self.get_connection() as conn:
            cur = conn.execute(query, params)
            return cur.rowcount > 0

    # =========================================================================
    # V3.0 GEOSPATIAL & 4D TRAJECTORY METHODS
    # =========================================================================
    def insert_geo_tracks_batch(self, tracks: List[Dict[str, Any]]) -> int:
        if not tracks:
            return 0
        rows = []
        for t in tracks:
            rows.append((
                t.get("track_id") or f"trk_{uuid.uuid4().hex[:12]}",
                t.get("entity_id"),
                t.get("layer_type", "UNKNOWN"),
                float(t.get("lat", 0.0)),
                float(t.get("lon", 0.0)),
                float(t.get("altitude_m", 0.0)),
                float(t.get("velocity_mps", 0.0)),
                float(t.get("heading_deg", 0.0)),
                t.get("telemetry_status", "LIVE"),
                1 if t.get("is_sanctioned") else 0,
                1 if t.get("is_military") else 0,
                t.get("squawk"),
                json.dumps(t.get("metadata_json") or (t.get("metadata") or {})),
                t.get("observed_at") or datetime.datetime.now(datetime.timezone.utc).isoformat(),
            ))
        with self.get_connection() as conn:
            conn.executemany(
                """
                INSERT OR REPLACE INTO geo_tracks (
                    track_id, entity_id, layer_type, lat, lon, altitude_m, velocity_mps,
                    heading_deg, telemetry_status, is_sanctioned, is_military, squawk,
                    metadata_json, observed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                rows,
            )
        return len(rows)

    def query_geo_tracks(
        self,
        layer_types: Optional[List[str]] = None,
        since_iso: Optional[str] = None,
        until_iso: Optional[str] = None,
        bbox: Optional[Tuple[float, float, float, float]] = None,
        limit: int = 2000,
    ) -> List[Dict[str, Any]]:
        query = "SELECT * FROM geo_tracks WHERE 1=1"
        params: List[Any] = []

        if layer_types:
            placeholders = ",".join("?" for _ in layer_types)
            query += f" AND layer_type IN ({placeholders})"
            params.extend(layer_types)

        if since_iso:
            query += " AND observed_at >= ?"
            params.append(since_iso)

        if until_iso:
            query += " AND observed_at <= ?"
            params.append(until_iso)

        if bbox:
            min_lon, min_lat, max_lon, max_lat = bbox
            query += " AND lat >= ? AND lat <= ? AND lon >= ? AND lon <= ?"
            params.extend([min_lat, max_lat, min_lon, max_lon])

        query += " ORDER BY observed_at DESC LIMIT ?"
        params.append(limit)

        results = []
        with self.get_connection() as conn:
            cur = conn.execute(query, params)
            for row in cur.fetchall():
                d = dict(row)
                d["metadata"] = json.loads(d.get("metadata_json") or "{}")
                d["is_sanctioned"] = bool(d["is_sanctioned"])
                d["is_military"] = bool(d["is_military"])
                results.append(d)
        return results

    # =========================================================================
    # V3.0 SANCTIONS INDEX METHODS
    # =========================================================================
    def upsert_sanctions_batch(self, records: List[Dict[str, Any]]) -> int:
        if not records:
            return 0
        rows = []
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        for r in records:
            rows.append((
                r.get("sanction_id") or f"sdn_{uuid.uuid4().hex[:12]}",
                r.get("sdn_name", "UNKNOWN"),
                r.get("sdn_type", "ENTITY"),
                r.get("program", "OFAC-SDN"),
                r.get("mmsi"),
                r.get("imo"),
                r.get("icao24", "").lower() if r.get("icao24") else None,
                r.get("tail_number"),
                r.get("flag_country"),
                r.get("remarks"),
                r.get("updated_at") or now,
            ))
        with self.get_connection() as conn:
            conn.executemany(
                """
                INSERT OR REPLACE INTO sanctions_index (
                    sanction_id, sdn_name, sdn_type, program, mmsi, imo, icao24,
                    tail_number, flag_country, remarks, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                rows,
            )
        return len(rows)

    def match_sanction(
        self,
        mmsi: Optional[str] = None,
        imo: Optional[str] = None,
        icao24: Optional[str] = None,
        tail_number: Optional[str] = None,
        name: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            if mmsi:
                cur = conn.execute("SELECT * FROM sanctions_index WHERE mmsi = ? LIMIT 1;", (str(mmsi).strip(),))
                row = cur.fetchone()
                if row:
                    return dict(row)

            if imo:
                cur = conn.execute("SELECT * FROM sanctions_index WHERE imo = ? LIMIT 1;", (str(imo).strip(),))
                row = cur.fetchone()
                if row:
                    return dict(row)

            if icao24:
                cur = conn.execute("SELECT * FROM sanctions_index WHERE icao24 = ? LIMIT 1;", (str(icao24).strip().lower(),))
                row = cur.fetchone()
                if row:
                    return dict(row)

            if tail_number:
                cur = conn.execute("SELECT * FROM sanctions_index WHERE tail_number = ? LIMIT 1;", (str(tail_number).strip().upper(),))
                row = cur.fetchone()
                if row:
                    return dict(row)

            if name:
                cur = conn.execute(
                    "SELECT * FROM sanctions_index WHERE sdn_name = ? COLLATE NOCASE LIMIT 1;",
                    (str(name).strip(),)
                )
                row = cur.fetchone()
                if row:
                    return dict(row)
        return None

    # =========================================================================
    # V3.0 CRUCIX SWEEP RUNS & DELTAS METHODS
    # =========================================================================
    def create_sweep_run(self, investigation_id: str = "default") -> str:
        sweep_id = f"swp_{datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:6]}"
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO sweep_runs (
                    sweep_id, investigation_id, started_at, status
                ) VALUES (?, ?, ?, 'RUNNING');
                """,
                (sweep_id, investigation_id, now),
            )
        return sweep_id

    def complete_sweep_run(
        self, sweep_id: str, stats: Dict[str, Any], deltas: List[Dict[str, Any]]
    ) -> None:
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with self.get_connection() as conn:
            conn.execute(
                """
                UPDATE sweep_runs SET
                    completed_at = ?,
                    status = ?,
                    sources_polled = ?,
                    sources_succeeded = ?,
                    new_entities_count = ?,
                    escalated_count = ?,
                    sanction_matches_count = ?,
                    geofence_alerts_count = ?,
                    escalation_score = ?,
                    summary_briefing_md = ?
                WHERE sweep_id = ?;
                """,
                (
                    now,
                    stats.get("status", "COMPLETED"),
                    stats.get("sources_polled", 0),
                    stats.get("sources_succeeded", 0),
                    stats.get("new_entities_count", 0),
                    stats.get("escalated_count", 0),
                    stats.get("sanction_matches_count", 0),
                    stats.get("geofence_alerts_count", 0),
                    float(stats.get("escalation_score", 0.0)),
                    stats.get("summary_briefing_md", ""),
                    sweep_id,
                ),
            )
            if deltas:
                delta_rows = []
                for d in deltas:
                    delta_rows.append((
                        d.get("delta_id") or f"dlt_{uuid.uuid4().hex[:12]}",
                        sweep_id,
                        d.get("entity_id"),
                        d.get("delta_type", "NEW_ENTITY"),
                        d.get("severity", "INFO"),
                        d.get("title", ""),
                        d.get("description", ""),
                        json.dumps(d.get("prev_value_json") or {}),
                        json.dumps(d.get("curr_value_json") or {}),
                        d.get("lat"),
                        d.get("lon"),
                        d.get("created_at") or now,
                    ))
                conn.executemany(
                    """
                    INSERT INTO sweep_deltas (
                        delta_id, sweep_id, entity_id, delta_type, severity, title,
                        description, prev_value_json, curr_value_json, lat, lon, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    delta_rows,
                )

    def get_latest_sweep_run(self) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            cur = conn.execute("SELECT * FROM sweep_runs ORDER BY started_at DESC LIMIT 1;")
            row = cur.fetchone()
            return dict(row) if row else None

    def get_sweep_run(self, sweep_id: str) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            cur = conn.execute("SELECT * FROM sweep_runs WHERE sweep_id = ?;", (sweep_id,))
            row = cur.fetchone()
            return dict(row) if row else None

    def get_sweep_deltas(self, sweep_id: str, severity: Optional[str] = None) -> List[Dict[str, Any]]:
        query = "SELECT * FROM sweep_deltas WHERE sweep_id = ?"
        params: List[Any] = [sweep_id]
        if severity:
            query += " AND severity = ?"
            params.append(severity)
        query += " ORDER BY created_at DESC;"
        with self.get_connection() as conn:
            cur = conn.execute(query, params)
            deltas = []
            for row in cur.fetchall():
                d = dict(row)
                d["prev_value"] = json.loads(d.get("prev_value_json") or "{}")
                d["curr_value"] = json.loads(d.get("curr_value_json") or "{}")
                deltas.append(d)
            return deltas

    # =========================================================================
    # V3.0 GEOFENCE ZONES METHODS
    # =========================================================================
    def create_geofence(
        self,
        name: str,
        polygon_geojson: str,
        monitored_layers: Optional[List[str]] = None,
        min_severity: str = "MEDIUM",
        notify_channels: Optional[List[str]] = None,
    ) -> str:
        geofence_id = f"geo_{uuid.uuid4().hex[:10]}"
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        layers = monitored_layers or ["AIRCRAFT", "VESSEL", "EARTHQUAKE", "CONFLICT"]
        channels = notify_channels or ["SSE"]
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO geofence_zones (
                    geofence_id, name, polygon_geojson, monitored_layers_json,
                    min_severity, notify_channels_json, is_active, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, 1, ?);
                """,
                (
                    geofence_id,
                    name,
                    polygon_geojson,
                    json.dumps(layers),
                    min_severity,
                    json.dumps(channels),
                    now,
                ),
            )
        return geofence_id

    def list_geofences(self, active_only: bool = True) -> List[Dict[str, Any]]:
        query = "SELECT * FROM geofence_zones"
        params: List[Any] = []
        if active_only:
            query += " WHERE is_active = 1"
        query += " ORDER BY created_at DESC;"
        with self.get_connection() as conn:
            cur = conn.execute(query, params)
            zones = []
            for row in cur.fetchall():
                z = dict(row)
                z["monitored_layers"] = json.loads(z.get("monitored_layers_json") or "[]")
                z["notify_channels"] = json.loads(z.get("notify_channels_json") or "[]")
                z["is_active"] = bool(z["is_active"])
                zones.append(z)
            return zones

    def delete_geofence(self, geofence_id: str) -> bool:
        with self.get_connection() as conn:
            cur = conn.execute("DELETE FROM geofence_zones WHERE geofence_id = ?;", (geofence_id,))
            return cur.rowcount > 0

    # =========================================================================
    # V3.0 VISUAL ASSETS & CONSENTED GALLERY METHODS
    # =========================================================================
    def save_visual_asset(self, asset: Dict[str, Any]) -> str:
        asset_id = asset.get("asset_id") or f"vis_{uuid.uuid4().hex[:12]}"
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO visual_assets (
                    asset_id, investigation_id, entity_id, filename, sha256_hash,
                    phash_64, dhash_64, ahash_64, width, height, laplacian_sharpness,
                    quality_grade, faces_detected, bystanders_blurred, exif_json,
                    c2pa_json, lat, lon, redacted_image_b64, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    asset_id,
                    asset.get("investigation_id", "default"),
                    asset.get("entity_id"),
                    asset.get("filename", "unknown.jpg"),
                    asset.get("sha256_hash", ""),
                    asset.get("phash_64", "0" * 16),
                    asset.get("dhash_64", "0" * 16),
                    asset.get("ahash_64", "0" * 16),
                    int(asset.get("width", 0)),
                    int(asset.get("height", 0)),
                    float(asset.get("laplacian_sharpness", 0.0)),
                    asset.get("quality_grade", "MODERATE"),
                    int(asset.get("faces_detected", 0)),
                    1 if asset.get("bystanders_blurred", True) else 0,
                    json.dumps(asset.get("exif_json") or {}),
                    json.dumps(asset.get("c2pa_json") or {}),
                    asset.get("lat"),
                    asset.get("lon"),
                    asset.get("redacted_image_b64"),
                    asset.get("created_at") or now,
                ),
            )
        return asset_id

    def get_visual_asset(self, asset_id: str) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            cur = conn.execute("SELECT * FROM visual_assets WHERE asset_id = ?;", (asset_id,))
            row = cur.fetchone()
            if not row:
                return None
            d = dict(row)
            d["exif"] = json.loads(d.get("exif_json") or "{}")
            d["c2pa"] = json.loads(d.get("c2pa_json") or "{}")
            d["bystanders_blurred"] = bool(d["bystanders_blurred"])
            return d

    def list_visual_assets(self, limit: int = 100) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cur = conn.execute("SELECT * FROM visual_assets ORDER BY created_at DESC LIMIT ?;", (limit,))
            assets = []
            for row in cur.fetchall():
                d = dict(row)
                d["exif"] = json.loads(d.get("exif_json") or "{}")
                d["c2pa"] = json.loads(d.get("c2pa_json") or "{}")
                d["bystanders_blurred"] = bool(d["bystanders_blurred"])
                assets.append(d)
            return assets

    def find_similar_visual_assets(self, phash_hex: str, max_hamming: int = 10) -> List[Dict[str, Any]]:
        try:
            target_int = int(phash_hex, 16)
        except ValueError:
            return []

        candidates = self.list_visual_assets(limit=500)
        similar = []
        for c in candidates:
            c_hash = c.get("phash_64", "")
            if not c_hash:
                continue
            try:
                cand_int = int(c_hash, 16)
                diff = bin(target_int ^ cand_int).count("1")
                if diff <= max_hamming:
                    c_copy = dict(c)
                    c_copy["hamming_distance"] = diff
                    c_copy["similarity_score"] = round(1.0 - (diff / 64.0), 4)
                    similar.append(c_copy)
            except ValueError:
                continue
        similar.sort(key=lambda x: x["hamming_distance"])
        return similar

    def enroll_consented_face(
        self,
        subject_name: str,
        consent_purpose: str,
        consent_attestation: bool,
        embedding_blob: bytes,
        image_sha256: str,
        laplacian_sharpness: float,
        expires_at: str,
    ) -> str:
        if not consent_attestation:
            raise ValueError("Explicit consent attestation is legally mandatory for face enrollment.")
        gallery_id = f"gal_{uuid.uuid4().hex[:12]}"
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO consented_face_gallery (
                    gallery_id, subject_name, consent_purpose, consent_attestation,
                    embedding_blob, image_sha256, laplacian_sharpness, enrolled_at, expires_at
                ) VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?);
                """,
                (
                    gallery_id,
                    subject_name,
                    consent_purpose,
                    embedding_blob,
                    image_sha256,
                    float(laplacian_sharpness),
                    now,
                    expires_at,
                ),
            )
        return gallery_id

    def list_consented_faces(self, non_expired_only: bool = True) -> List[Dict[str, Any]]:
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        query = "SELECT * FROM consented_face_gallery"
        params: List[Any] = []
        if non_expired_only:
            query += " WHERE expires_at > ?"
            params.append(now)
        query += " ORDER BY enrolled_at DESC;"
        with self.get_connection() as conn:
            cur = conn.execute(query, params)
            return [dict(row) for row in cur.fetchall()]


# Singleton
db = DatabaseManager()
