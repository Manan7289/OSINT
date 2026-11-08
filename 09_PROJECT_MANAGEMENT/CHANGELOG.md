# CHANGELOG.md — Project Evolution & Handover History

## [2.0.0] — 2026-11-08 (Official Production Release)
- **100% Complete Implementation:** Built all 10 platform modules (`M01` through `M10`) across 13 phases with zero placeholders, full algorithmic fidelity, and 60/60 automated unit/integration tests passing.
- **M01 Security & Vault:** Implemented 256-bit AES-GCM/Fernet `CryptoVault`, `TokenBucketRateLimiter`, 3-state `CircuitBreaker`, `OPSECGuard` with strict `PASSIVE_ONLY` target isolation, and cryptographic `HashChainedAuditLogger` (SHA-256).
- **M02 Storage & Ontology:** Built SQLite WAL persistence engine (`PRAGMA synchronous = NORMAL`, `mmap_size = 256MB`), 14 schema tables, FollowTheMoney canonicalization, Soundex phonetic blocking, 8-character Geohash, and FTS5 full-text indexing.
- **M03 OSINT Collectors & Staging:** Built non-blocking `AsyncEventBus`, Staging Triage Buffer (`is_staged=1`) for high-volume batches (>50 entities), in-memory TTL cache, and 24 modular OSINT connectors (18 keyless public registries + 6 keyed commercial APIs).
- **M04 NLP & Forensics:** Built refang/defang normalizer (`hxxp`, `[.]`), Regex IOC extractor, Shannon entropy DGA detector, SimHash-64 near-duplicate clustering, and PDF/DOCX/EXIF document forensics (`pypdf`, `python-docx`, `Pillow`).
- **M05 Entity Resolution:** Implemented 3-pass blocking (Sorted Neighborhood $w=15$, Apex Prefix, 3-Gram MinHash LSH) achieving >85% pair reduction, unsupervised Fellegi-Sunter EM parameter estimation, Bayes-factor waterfall explanations, and 100% reversible merge/unmerge ledger.
- **M06 Provenance & Belief Fusion:** Implemented W3C PROV lineage DAG, Dong copying discount ($I_e$), Jøsang Subjective Logic tuple $\omega = (b, d, u, a)$ with Cumulative ($\oplus$) and Averaging ($\tilde{\oplus}$) belief fusion, conflict detection ($d \ge 0.25$), and 5-state epistemic stratification.
- **M07 Graph & Spatiotemporal Engine:** Implemented Leiden community detection, IEF edge weight dampening for RIOT-Lite shared infrastructure, Power Iteration PageRank, Adamic-Adar link prediction, Haversine spatial clustering, and Kleinberg/Poisson timeline burst Z-score detection.
- **M08 Hybrid RRF Search & GraphRAG:** Implemented deterministic 384-d dense embedding generator, INT8 vector quantization ($4\times$ memory reduction), Reciprocal Rank Fusion ($k=60$) combining SQLite FTS5 `bm25()` and cosine vector similarity, and deterministic GraphRAG Subgraph Compiler with citation entailment verification.
- **M09 REST/WebSocket Server & Exporters:** Built FastAPI application with `/api/*` and `/api/v2/*` routes, live WebSocket audit streaming, demonstration workspace seeder ("Operation Sentinel"), and 5 export formats (JSON, CSV, STIX 2.1, FollowTheMoney JSONL, W3C PROV-JSON).
- **M10 Analyst Workstation UI:** Built precision dark-mode single page application across all 11 views, dual-engine HTML5 Canvas + SVG relationship graph with 2D force simulation, pan/zoom, node inspector, time-travel filtering, and zero external CDN runtime dependencies.
- **Packaging & Operations:** Added Windows 11 automated batch scripts (`install.bat`, `start.bat`, `stop.bat`) and PowerShell scripts (`scripts/install.ps1`, `scripts/start.ps1`, `scripts/stop.ps1`).

## [2.0.0-blueprint] — 2026-11-08 (Antigravity Master Implementation Handover)
- Audited and consolidated all Phase 1 prototype findings and Phase 2 deep reassessment documents into a single self-contained handover package (`OSINT_ANTIGRAVITY_IMPLEMENTATION_HANDOVER.zip`) targeted for `https://github.com/Manan7289/OSINT.git`.
- Upgraded database schema to 14 tables supporting FollowTheMoney entity types, Bitemporal Reified Claims (`valid_from`, `valid_until`, `observed_at`), 5-state epistemic stratification, W3C PROV lineage, and Reversible Merge snapshots.
- Specified 3-pass blocking (`PHONETIC_SORT` $w=15$, `APEX_PREFIX`, `MINHASH_LSH`) + unsupervised Fellegi-Sunter EM + Bayes-factor waterfall explanations.
- Specified Jøsang Subjective Logic ($\omega=(b,d,u,a)$) Cumulative vs. Averaging belief fusion with Dong copying discounts.
- Specified Leiden community detection, RIOT-Lite super-node dampening, IEF-Personalized PageRank, Adamic-Adar link prediction, Haversine HDBSCAN spatial clustering, and Kleinberg burst detection.
- Expanded OSINT connector catalog to 24 verified sources (adding CISA KEV, FIRST EPSS, GLEIF Level-2 corporate ownership, OpenSanctions, Wikidata SPARQL, URLScan, and MalwareBazaar).
