# IMPLEMENTATION_ROADMAP.md — Dependency-Aware, Module-by-Module Engineering Specification

## 1. Overview & Dependency-Aware Execution Sequence
This roadmap translates our research and architecture reassessment into an **implementation-ready engineering blueprint** broken into 10 modular subsystems across 4 dependency-ordered phases.

### Dependency DAG & Parallelization Strategy
```text
PHASE 1 (Foundation — Sequential Core)
  [M1: Core Config, Vault, RateLimiter & CircuitBreaker]
                         |
                         v
  [M2: Bitemporal SQLite WAL/FTS5/R*Tree + FollowTheMoney Schema]
           /                             \
          v                               v
PHASE 2 (Core Engines — Parallelizable)
  [M3: AsyncEventBus & 24 OSINT Connectors]   [M4: Hybrid IE (Defang/Regex + ONNX GLiNER)]
          \                               /
           v                             v
PHASE 3 (Analytical Intelligence — Parallelizable after M2)
  [M5: Blocking + Fellegi-Sunter EM + Reversible Merge]
  [M6: W3C PROV Lineage, Dong Copying & Subjective Logic Engine]
  [M7: rustworkx Graph Engine (Leiden, IEF-PPR, Adamic-Adar, Anomaly)]
  [M8: Hybrid RRF Search (FTS5 BM25 + INT8 Vectors) & GraphRAG Assistant]
                         |
                         v
PHASE 4 (Interfaces, Visualization & Verification)
  [M9: FastAPI REST/WebSocket API & Export Engine (STIX 2.1, FtM, PROV)]
                         |
                         v
  [M10: Dual-Engine WebGL/Canvas Workstation UI + E2E Verification Suite]
```

---

## 2. Detailed Module-by-Module Engineering Specifications

### Module M1: Security Vault, Rate Limiter, Circuit Breaker & OPSEC Guard
- **Exact Objective:** Provide thread/async-safe credential encryption, per-source token-bucket rate limiting, 3-state circuit breaking (`CLOSED`, `OPEN`, `HALF_OPEN`), and `PASSIVE_ONLY` OPSEC enforcement.
- **Features:** Fernet AES-128-CBC + HMAC-SHA256 vault (`data/.vault_key`), per-connector RPM buckets, exponential backoff with jitter, hash-chained tamper-evident audit logger.
- **Algorithms:** Token Bucket algorithm; SHA-256 Merkle/hash chain ($H_i = \text{SHA256}(H_{i-1} \parallel t_i \parallel \text{payload}_i)$).
- **Recommended Libraries:** `cryptography`, `hashlib`, `asyncio`, `httpx`.
- **Database Requirements:** `connector_configs`, `http_cache`, `audit_logs`.
- **Backend / Frontend Components:** `backend/core/security.py`, `backend/core/network.py` / Settings & OPSEC Bar in UI.
- **Testing Requirements:** Unit tests for encryption round-trip, token exhaustion wait calculation, circuit-breaker trip on 3 consecutive `HTTP 502/429` responses, and hash-chain tamper detection.
- **Resource Consumption:** $< 5\text{ MB}$ RAM, $< 0.1\text{ ms}$ overhead per call.
- **Acceptance Criteria & Priority:** **P0 (Develop First — Zero external module dependencies).**

---

### Module M2: Bitemporal FollowTheMoney SQLite WAL + FTS5 + R*Tree Storage Engine
- **Exact Objective:** Manage workspaces, canonical entities, reified bitemporal claims, evidence provenance artifacts, blocking keys, and spatial/full-text indices.
- **Features:** FollowTheMoney entity validation, automatic canonicalization (IDNA punycode, E.164, CIDR, legal suffix normalization), staging buffer (`is_staged`), RIOT-Lite shared infrastructure flag (`is_shared_infra`).
- **Algorithms:** Unicode NFKD normalization, Soundex/Metaphone phonetic key generation, Geohash-8 encoding.
- **Recommended Libraries:** `sqlite3` (WAL + FTS5 + R*Tree), `pydantic`, `idna`.
- **Database Requirements:** Full schema defined in `DATA_FLOW_AND_SCHEMA_DESIGN.md`.
- **Backend / Frontend Components:** `backend/core/database.py`, `backend/core/ontology.py` / Workspace Manager & Entity Explorer.
- **Testing Requirements:** ACID persistence across restarts, bitemporal time-slice queries (`valid_from <= T <= valid_until`), FTS5 technical token search (`185.220.101.34`, `CVE-2024-3400`).
- **Resource Consumption:** ~15–35 MB RAM (32 MB SQLite page cache cap).
- **Integration Dependencies:** Depends on `M1`. **Priority: P0.**

---

### Module M3: Asynchronous Event-Driven Collector Pipeline & 24 OSINT Plugins
- **Exact Objective:** Execute single-connector transforms and multi-hop recursive playbooks across 24 public and BYO-key OSINT sources with automatic staging and loop prevention.
- **Features:** `AsyncEventBus` with `max_pivot_depth` and bloom/set deduplication; 18 keyless public connectors (DoH, RDAP, crt.sh, RIPEstat, URLScan, Shodan InternetDB, NVD CVE v2, CISA KEV, FIRST EPSS, ThreatFox, URLhaus, MalwareBazaar, GLEIF LEI, SEC EDGAR, OpenSanctions, Wikidata SPARQL, OpenAlex, Wayback CDX, GDELT 2.0, GitHub REST, Nominatim OSM, Local Document/EXIF Parser) + 6 optional keyed connectors.
- **Algorithms:** BFS depth-bounded event propagation; SimHash 64-bit document fingerprinting.
- **Recommended Libraries:** `httpx`, `dnspython`, `beautifulsoup4`, `lxml`, `pypdf`, `python-docx`, `Pillow`.
- **Database Requirements:** Writes to `evidence_artifacts`, `entities`, `claims`, `tasks`.
- **Backend / Frontend Components:** `backend/collectors/pipeline.py`, `backend/collectors/plugins/*.py` / Collection Playbook Launcher & Task Monitor.
- **Testing Requirements:** Mocked + live HTTP contract tests for every connector, graceful `SKIPPED` state when optional API key is absent, staging buffer activation when child count $> 50$.
- **Resource Consumption:** ~25 MB RAM during 32-way concurrent async HTTP collection.
- **Integration Dependencies:** Depends on `M1`, `M2`. **Priority: P0 (Core 14 connectors) / P1 (Remaining 10 connectors).**

---

### Module M4: Two-Tier Hybrid Information Extraction (Defang/Regex + ONNX INT8 GLiNER)
- **Exact Objective:** Extract structured technical indicators and unstructured named entities/relations from web pages, pasted advisories, and uploaded PDF/DOCX files.
- **Features:** Automatic defanging normalization (`hxxps://`, `[.]`, `[@]`), Shannon entropy DGA scoring, Tier 1 Regex/Aho-Corasick extractor, Tier 2 optional `onnxruntime` INT8 `gliner_small-v2.1` zero-shot span extractor.
- **Algorithms:** Aho-Corasick automaton, Shannon entropy $H(s)$, bidirectional transformer span scoring via ONNX Runtime.
- **Recommended Libraries:** `re`, `onnxruntime`, `numpy`, `pypdf`, `Pillow`.
- **Backend / Frontend Components:** `backend/nlp/extractor.py` / Document & Text Forensics Analyzer View.
- **Testing Requirements:** 100% recall on defanged IOC test corpus; verified fallback to Tier 1 if ONNX model weights are not downloaded.
- **Resource Consumption:** ~5 MB (Tier 1) / ~185 MB (Tier 2 with INT8 ONNX loaded).
- **Integration Dependencies:** Depends on `M2`. Can be developed in parallel with `M3`. **Priority: P0 (Tier 1) / P1 (Tier 2 ONNX).**

---

### Module M5: Scalable Blocking, Fellegi-Sunter EM Entity Resolution & Reversible Merge Engine
- **Exact Objective:** Identify duplicate/alias entities across sources in $O(N \log N)$ time, provide explainable Bayes-factor waterfall charts, and execute reversible entity merges.
- **Features:** 3-pass blocking (Sorted Neighborhood $w=15$ on phonetic name, exact identifier prefix, and 3-gram MinHash LSH), unsupervised Expectation-Maximization weight calibration with Inverse Entity Frequency (IEF) adjustment, one-click Merge and Unmerge.
- **Algorithms:** Sorted Neighborhood ([arXiv:1501.01696](https://arxiv.org/pdf/1501.01696)), MinHash LSH, Fellegi-Sunter EM ([arXiv:2008.04443v3](https://arxiv.org/html/2008.04443v3)), Jaro-Winkler, Token Jaccard.
- **Recommended Libraries:** `numpy`, `scipy`, `duckdb` (optional [Splink](https://github.com/moj-analytical-services/splink) backend).
- **Database Requirements:** `entity_blocking_keys`, `entity_merge_ledger`, `entities`, `claims`.
- **Backend / Frontend Components:** `backend/core/entity_resolution.py` / Entity Resolution Workbench with Waterfall Chart Inspector.
- **Testing Requirements:** Verify $>60\times$ pair reduction vs. $O(N^2)$ on 2,000 entities; verify exact state restoration after Merge $\rightarrow$ Unmerge cycle.
- **Resource Consumption:** $< 20\text{ MB}$ RAM for 10,000 entities.
- **Integration Dependencies:** Depends on `M2`. **Priority: P0.**

---

### Module M6: W3C PROV Lineage, Source Independence & Subjective Logic Belief Fusion Engine
- **Exact Objective:** Prevent circular reporting from inflating confidence, compute Subjective Logic opinions $\omega = (b, d, u, a)$, and transition claims across epistemic statuses.
- **Features:** Upstream lineage grouping, Dong et al. copying discount $I(e_i)$, Cumulative ($\oplus$) vs. Averaging ($\tilde{\oplus}$) belief fusion, automated Contradiction Alert when $d \ge 0.25$, temporal freshness decay.
- **Algorithms:** Dong copying detection ([VLDB 2009](http://www.vldb.org/pvldb/vol2/vldb09-335.pdf)); Jøsang Subjective Logic multi-source fusion ([UiO 2017](https://www.mn.uio.no/ifi/english/people/aca/josang/publications/jwz2017-fusion.pdf)).
- **Database Requirements:** `evidence_artifacts`, `claims`, `claim_evidence`.
- **Backend / Frontend Components:** `backend/core/provenance_fusion.py` / Provenance Ledger & Contradiction Matrix UI.
- **Testing Requirements:** Prove that 5 syndicated copies from the same `upstream_lineage_family` yield lower corroborated belief $b$ than 2 independent authoritative registries (`A1`).
- **Resource Consumption:** $< 5\text{ MB}$ RAM.
- **Integration Dependencies:** Depends on `M2`. **Priority: P0.**

---

### Module M7: High-Performance Graph Analytics, Spatiotemporal & Anomaly Engine
- **Exact Objective:** Execute community detection, hub-dampened centrality, link prediction, spatial clustering, and temporal burst detection.
- **Features:** Leiden community detection, IEF-weighted Personalized PageRank, Adamic-Adar missing link prediction, Dijkstra max-reliability pathfinder, Haversine HDBSCAN spatial clustering, Kleinberg/Poisson Z-score timeline burst detector, Isolation Forest node anomaly scorer.
- **Algorithms:** Leiden ([arXiv:1810.08473](https://arxiv.org/abs/1810.08473)), Personalized PageRank, Adamic-Adar, HDBSCAN, Isolation Forest.
- **Recommended Libraries:** [rustworkx](https://github.com/Qiskit/rustworkx) (with SciPy/pure-Python fallback), `scipy`, `numpy`, `scikit-learn`.
- **Backend / Frontend Components:** `backend/core/graph_analytics.py`, `backend/core/spatiotemporal.py` / Graph Analytics & Geo/Timeline Views.
- **Testing Requirements:** Verify super-node (`AS13335`) dampening in PageRank; verify Leiden produces 0 disconnected communities; verify Haversine HDBSCAN groups nearby coordinates.
- **Resource Consumption:** ~30–60 MB RAM for 25,000 nodes/edges.
- **Integration Dependencies:** Depends on `M2`, `M6`. **Priority: P0 (Graph Centrality/Leiden) / P1 (HDBSCAN/Burst/Isolation Forest).**

---

### Module M8: Hybrid RRF Search (BM25 + INT8 Vectors) & GraphRAG AI Assistant
- **Exact Objective:** Provide sub-15ms hybrid keyword + semantic search and a halluncination-guarded GraphRAG assistant that strictly separates facts, inferences, and contradictions.
- **Features:** SQLite FTS5 `bm25()` + INT8 384-d vector index fused via Reciprocal Rank Fusion ($k=60$); deterministic GraphRAG Subgraph Compiler; optional local Ollama LLM connector with post-generation `[ev_xxxx]` citation validator.
- **Algorithms:** BM25, INT8 SIMD Cosine Similarity, Reciprocal Rank Fusion ([arXiv:2508.01405v2](https://arxiv.org/html/2508.01405v2)), GraphRAG subgraph extraction ([arXiv:2608.13050](https://arxiv.org/abs/2608.13050)).
- **Recommended Libraries:** `sqlite3`, `numpy`, `onnxruntime`, `httpx` (for local Ollama API).
- **Backend / Frontend Components:** `backend/ai/search_rrf.py`, `backend/ai/graphrag_assistant.py` / Search & AI Intelligence Assistant View.
- **Testing Requirements:** Verify RRF ranks exact CVE/IP matches and semantic queries accurately; verify ungrounded LLM sentences are flagged by the citation validator.
- **Resource Consumption:** ~15 MB (BM25 + INT8 vectors) / +60 MB if ONNX embedding model loaded.
- **Integration Dependencies:** Depends on `M2`, `M6`, `M7`. **Priority: P1.**

---

### Module M9 & Module M10: FastAPI REST/WebSocket Server & Dual-Engine Workstation UI
- **Exact Objective:** Expose all analytical engines via typed FastAPI endpoints and render the 11-view workstation UI with WebGL/Canvas graphs, bitemporal timeline slider, HDBSCAN map, waterfall ER workbench, and STIX 2.1 / FollowTheMoney / W3C PROV exports.
- **Acceptance Criteria & Priority:** **P0 (Core Workstation & Exports) / P1 (WebGL Macro Canvas & Time-Travel Slider).**
