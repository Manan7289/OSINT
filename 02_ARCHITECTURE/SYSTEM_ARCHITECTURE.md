# SYSTEM_ARCHITECTURE.md — Ideal Local-First OSINT Platform Architecture (v2.0 Blueprint)

## 1. Architectural Vision
The redesigned **LocalOSINT v2.0** architecture transforms the platform from a synchronous request-response dashboard into an **event-driven, provenance-stratified, bitemporal intelligence workstation**. It is engineered to run as a single cohesive local process tree on Windows 11 (~16 GB RAM, CPU-only) while supporting recursive collection playbooks, 50,000-node WebGL graphs, unsupervised Fellegi-Sunter EM entity resolution, and Subjective Logic belief fusion.

---

## 2. End-to-End 11-Stage Intelligence Pipeline Architecture

```text
+---------------------------------------------------------------------------------------------------+
|STAGE 1: SOURCES         Public Registries (RDAP, crt.sh, RIPEstat, GLEIF, SEC, CISA KEV, EPSS)    |
|                         Unstructured Feeds (GDELT, RSS, URLScan, Local PDFs/DOCX/EXIF/PCAP/Logs)  |
+-------------------------------------------------+-------------------------------------------------+
                                                  |
                                                  v
+---------------------------------------------------------------------------------------------------+
|STAGE 2: COLLECTION      AsyncEventBus + TokenBucketRateLimiter + CircuitBreaker + HTTP/2 Pool     |
|                         Writes Immutable Raw Capture (SHA-256 + Headers + UTC) to Evidence Vault  |
+-------------------------------------------------+-------------------------------------------------+
                                                  |
                                                  v
+---------------------------------------------------------------------------------------------------+
|STAGE 3: VALIDATION      Pydantic v2 Schema Validator + Defang Normalizer (hxxp -> http, [.] -> .) |
|                         Scope Distance Guard (max_hops) + RIOT-Lite Benign CDN/Resolver Tagging   |
+-------------------------------------------------+-------------------------------------------------+
                                                  |
                                                  v
+---------------------------------------------------------------------------------------------------+
|STAGE 4: NORMALIZATION   FollowTheMoney (FtM)-Aligned Canonicalizers:                              |
|                         IDNA Punycode, E.164 Phone, ISO-3166 Country, Legal Suffix, CIDR/ASN      |
+-------------------------------------------------+-------------------------------------------------+
                                                  |
                                                  v
+---------------------------------------------------------------------------------------------------+
|STAGE 5: EXTRACTION      Tier 1: Deterministic Regex + Aho-Corasick Gazetteers (0ms overhead)      |
|                         Tier 2: ONNX INT8 GLiNER Zero-Shot Span Extractor + Co-Occurrence Triples |
+-------------------------------------------------+-------------------------------------------------+
                                                  |
                                                  v
+---------------------------------------------------------------------------------------------------+
|STAGE 6: ENTITY          Stage 6a: Multi-Pass Blocking (Sorted Neighborhood w=15 + 3-gram MinHash) |
|         RESOLUTION      Stage 6b: Fellegi-Sunter EM + Inverse Entity Frequency (IEF) Match Weight |
|                         Stage 6c: Non-Destructive Canonical Merge Cluster + Conflict Audit Trail  |
+-------------------------------------------------+-------------------------------------------------+
                                                  |
                                                  v
+---------------------------------------------------------------------------------------------------+
|STAGE 7: CORRELATION &   W3C PROV Lineage DAG + Dong Copying Detection (Independence Weight I_e)   |
|         BELIEF FUSION   Jøsang Subjective Logic Opinion ω = (b, d, u, a) + Kleinberg Burst Score  |
+-------------------------------------------------+-------------------------------------------------+
                                                  |
                                                  v
+---------------------------------------------------------------------------------------------------+
|STAGE 8: STORAGE         SQLite 3 WAL (OLTP Entities/Claims/PROV) + FTS5 (BM25) + R*Tree (Geo)     |
|                         + sqlite-vec / USearch (INT8 Vectors) + DuckDB (Analytical ER/OLAP)       |
+-------------------------------------------------+-------------------------------------------------+
                                                  |
                                                  v
+---------------------------------------------------------------------------------------------------+
|STAGE 9: ANALYSIS        rustworkx Graph Engine: Leiden Communities, IEF-Personalized PageRank,    |
|                         Adamic-Adar Link Prediction, Haversine HDBSCAN, Isolation Forest Anomaly  |
+-------------------------------------------------+-------------------------------------------------+
                                                  |
                                                  v
+---------------------------------------------------------------------------------------------------+
|STAGE 10: VISUALIZATION  Sigma.js (WebGL 60FPS Macro Graph) + Cytoscape.js (Ego/PROV DAG)          |
|                         + MapLibre/Leaflet (HDBSCAN Geo Clusters) + Simile/Vis Timeline + ER UI   |
+-------------------------------------------------+-------------------------------------------------+
                                                  |
                                                  v
+---------------------------------------------------------------------------------------------------+
|STAGE 11: REPORTING      Epistemically Stratified Reports (Observed Fact vs Corroborated Fact vs   |
|                         Inference vs Hypothesis) + STIX 2.1 / FollowTheMoney / CSV / PDF Export   |
+---------------------------------------------------------------------------------------------------+
```

---

## 3. Detailed Subsystem Responsibilities & Interfaces

### 3.1 Plugin-Based Connector Architecture (Open-Closed Principle)
New OSINT connectors are added by dropping a single Python module into `backend/collectors/plugins/` implementing the `BaseOSINTConnector` abstract base class—**without modifying any core orchestrator, database, or UI code**:
- **Declarative Manifest:** Each plugin declares `connector_id`, `display_name`, `category`, `upstream_lineage_family`, `default_admiralty_reliability` (`A`–`F`), `input_entity_types` (e.g., `["Domain", "IPv4Address"]`), `output_entity_types`, `rate_limit_rpm`, `cache_ttl_seconds`, and `requires_api_key`.
- **Recursive Event Subscription ([BBOT Pattern](https://github.com/blacklanternsecurity/bbot)):** When a playbook runs with `max_depth = 2`, a `Domain` emitted by `crtsh_ct` automatically triggers `dns_doh`, which emits an `IPv4Address` that automatically triggers `ripestat_data` and `shodan_internetdb`, bounded by loop-detection hashes and `scope_distance`.

### 3.2 Staging & Triage Buffer (Solving Graph Clutter)
A classic failure mode in [SpiderFoot](https://github.com/smicallef/spiderfoot) and [Maltego](https://www.maltego.com/transform-hub/) is "graph explosion": querying `crt.sh` on a large enterprise domain returns 3,000 expired staging subdomains that render the visual graph unreadable.
- **Architectural Solution:** All newly collected entities with low centrality or unverified status enter a database-backed **Workspace Staging Buffer (`is_staged = 1`)** when a connector batch exceeds a configurable threshold (e.g., $>50$ child nodes).
- Analysts can filter, search, and bulk-promote staged entities into the primary visual canvas, while all staged records remain immediately searchable via FTS5 and DuckDB analytics.

### 3.3 Dual-Tier Concurrency Model for Windows 11
- **I/O Bound Pool (`asyncio` Event Loop + `httpx.AsyncClient`):** Handles up to 64 concurrent HTTP/2 and DoH requests governed by per-source `TokenBucketRateLimiter` and an adaptive **3-State Circuit Breaker** (`CLOSED`, `OPEN`, `HALF_OPEN`) so a slow or rate-limited external API (such as `crt.sh` returning HTTP 502/429) fails fast and schedules a backoff retry without stalling other connectors.
- **CPU Bound Pool (`ProcessPoolExecutor`, 2–4 worker processes):** Executes ONNX Runtime inference (GLiNER NER + 384-d embeddings), Fellegi-Sunter EM iterations, and `rustworkx` Leiden/PageRank computations outside the main FastAPI event loop so the UI never stutters.
