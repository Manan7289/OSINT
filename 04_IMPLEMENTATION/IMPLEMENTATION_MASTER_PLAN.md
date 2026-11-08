# IMPLEMENTATION_MASTER_PLAN.md — 13-Phase Execution Blueprint for Antigravity (Gemini 3.8 Flash)

## 1. Executive Summary
This document is the central operational blueprint for building **LocalOSINT v2.0** inside `https://github.com/Manan7289/OSINT.git`. It organizes the entire engineering effort into **13 sequential, dependency-ordered phases**. Each phase specifies its exact objective, required files, modules involved, technical tasks, verification tests, and gate criteria before advancing.

---

## 2. Dependency-Ordered 13-Phase Implementation Plan

### Phase 1: Repository Inspection & Project Skeleton Setup
- **Objective:** Clone/open `https://github.com/Manan7289/OSINT.git`, inspect existing branches/files, preserve useful existing assets, and create the clean directory tree and configuration templates.
- **Files Created/Updated:** `.gitignore`, `requirements.txt`, `.env.example`, `README.md`, directory tree (`backend/core/`, `backend/collectors/plugins/`, `backend/nlp/`, `backend/ai/`, `frontend/assets/`, `tests/`, `scripts/`, `docs/`, `data/`).
- **Technical Tasks:**
  1. Run `git status`, `git branch -a`, and `git log -n 5`.
  2. Configure `.gitignore` to exclude `.venv/`, `data/*.db*`, `data/.vault_key`, `__pycache__/`, and `.env`.
  3. Create `requirements.txt` with pinned/verified Windows 11 compatible packages.
- **Verification & Gate Criteria:** Directory structure matches `FILE_STRUCTURE_AND_IMPLEMENTATION_MAP.md`; `git status` is clean.

---

### Phase 2: Foundational Security Vault, Rate Limiter, Circuit Breaker & OPSEC Guard (`M01`)
- **Objective:** Implement `CryptoVault`, `TokenBucketRateLimiter`, `CircuitBreaker`, `OPSECGuard`, and hash-chained audit logging.
- **Files Created:** `backend/core/__init__.py`, `backend/core/config.py`, `backend/core/security.py`, `tests/test_m01_security.py`.
- **Modules Involved:** `M01` (Spec: `03_MODULE_SPECIFICATIONS/M01_SECURITY_VAULT_AND_NETWORK_GUARD.md`).
- **Verification & Gate Criteria:** `pytest tests/test_m01_security.py -v` passes 100% (Fernet round-trip, key masking, token exhaustion, circuit-breaker trip/reset, SHA-256 hash-chain tamper detection).

---

### Phase 3: Bitemporal SQLite WAL/FTS5/R*Tree Storage & FollowTheMoney Ontology (`M02`)
- **Objective:** Implement the 14-table SQLite WAL + FTS5 + R*Tree database schema, FollowTheMoney entity canonicalizers, RIOT-Lite shared infrastructure detector, and 3-pass blocking key generator.
- **Files Created:** `backend/core/ontology.py`, `backend/core/database.py`, `tests/test_m02_database.py`.
- **Modules Involved:** `M02` (Spec: `03_MODULE_SPECIFICATIONS/M02_BITEMPORAL_SQLITE_FTM_STORAGE.md` & `02_ARCHITECTURE/DATABASE_DESIGN.md`).
- **Verification & Gate Criteria:** `pytest tests/test_m02_database.py -v` passes (WAL mode enabled, bitemporal claim time-slicing works, FTS5 technical token queries succeed, blocking keys populate automatically).

---

### Phase 4: W3C PROV Lineage DAG, Dong Copying Discount & Subjective Logic Fusion (`M06`)
- **Objective:** Implement the mathematical belief fusion engine that prevents circular reporting from inflating confidence and assigns 5-state `epistemic_status`.
- **Files Created:** `backend/core/provenance_fusion.py`, `tests/test_m06_provenance_fusion.py`.
- **Modules Involved:** `M06` (Spec: `03_MODULE_SPECIFICATIONS/M06_W3C_PROV_AND_SUBJECTIVE_LOGIC_FUSION.md`).
- **Verification & Gate Criteria:** `pytest tests/test_m06_provenance_fusion.py -v` proves that 5 syndicated copies from the same `upstream_lineage_family` (Averaging Fusion $\tilde{\oplus}$) yield lower corroborated belief $b$ than 2 independent authoritative `A1` sources (Cumulative Fusion $\oplus$), and conflicting claims ($d \ge 0.25$) transition to `UNVERIFIED_CLAIM`.

---

### Phase 5: Two-Tier Hybrid NLP Extractor & Document/EXIF Forensics (`M04`)
- **Objective:** Implement Tier-1 defanging (`hxxps://`, `[.]`) + Regex + Aho-Corasick + DGA Shannon entropy + SimHash-64, Tier-2 optional CPU INT8 ONNX `gliner_small-v2.1` span extractor, and PDF/DOCX/Image EXIF metadata forensics.
- **Files Created:** `backend/nlp/__init__.py`, `backend/nlp/extractor.py`, `backend/nlp/forensics.py`, `tests/test_m04_nlp_forensics.py`.
- **Modules Involved:** `M04` (Spec: `03_MODULE_SPECIFICATIONS/M04_HYBRID_NLP_AND_DOCUMENT_FORENSICS.md`).
- **Verification & Gate Criteria:** `pytest tests/test_m04_nlp_forensics.py -v` passes 100% on defanged IOC strings, DGA hostname entropy, SimHash near-duplicate detection, and PDF/EXIF binary parsing.

---

### Phase 6: AsyncEventBus, Staging Triage Buffer & 24 OSINT Connectors (`M03`)
- **Objective:** Implement the asynchronous pub-sub collection pipeline (`AsyncEventBus`), Staging Triage Buffer (`is_staged = 1` when batch $>50$), and all 24 modular OSINT connectors (18 keyless public + 6 optional BYO-key).
- **Files Created:** `backend/collectors/__init__.py`, `backend/collectors/orchestrator.py`, `backend/collectors/plugins/*.py`, `tests/test_m03_collectors.py`.
- **Modules Involved:** `M03` (Spec: `03_MODULE_SPECIFICATIONS/M03_ASYNC_EVENT_BUS_AND_CONNECTORS.md` & `01_RESEARCH/DATA_SOURCE_RESEARCH.md`).
- **Verification & Gate Criteria:** `pytest tests/test_m03_collectors.py -v` verifies all 24 connectors, HTTP cache hits, CISA KEV + FIRST EPSS + NVD composite vulnerability scoring, GLEIF Level-2 ownership parsing, and graceful `SKIPPED` status when optional keys are absent.

---

### Phase 7: 3-Pass Blocked Fellegi-Sunter EM Entity Resolution & Reversible Merge (`M05`)
- **Objective:** Implement Sorted Neighborhood ($w=15$) + Identifier Prefix + 3-gram MinHash LSH blocking, unsupervised Expectation-Maximization (EM) Fellegi-Sunter parameter estimation with Inverse Entity Frequency (IEF) scaling, Bayes-factor waterfall explanations, and reversible `merge` / `unmerge`.
- **Files Created:** `backend/core/entity_resolution.py`, `tests/test_m05_entity_resolution.py`.
- **Modules Involved:** `M05` (Spec: `03_MODULE_SPECIFICATIONS/M05_BLOCKED_FELLEGI_SUNTER_ENTITY_RESOLUTION.md`).
- **Verification & Gate Criteria:** `pytest tests/test_m05_entity_resolution.py -v` verifies $>50\times$ pair reduction on 1,000+ entities, EM weight convergence, waterfall factor output, and exact state restoration after `unmerge`.

---

### Phase 8: High-Performance Graph Engine (Leiden, IEF-PageRank, Adamic-Adar) & Spatiotemporal/Burst Analytics (`M07`)
- **Objective:** Implement Leiden community detection, RIOT-Lite super-node dampening, IEF-Personalized PageRank, Adamic-Adar link prediction, Haversine HDBSCAN spatial clustering, Kleinberg/Poisson timeline burst detection, and Isolation Forest node anomaly scoring.
- **Files Created:** `backend/core/graph_analytics.py`, `backend/core/spatiotemporal.py`, `tests/test_m07_graph_spatiotemporal.py`.
- **Modules Involved:** `M07` (Spec: `03_MODULE_SPECIFICATIONS/M07_RUSTWORKX_LEIDEN_AND_SPATIOTEMPORAL_ENGINE.md`).
- **Verification & Gate Criteria:** `pytest tests/test_m07_graph_spatiotemporal.py -v` passes (0 disconnected Leiden communities, super-nodes dampened, Haversine clusters and burst Z-scores computed).

---

### Phase 9: Hybrid RRF Search (FTS5 BM25 + INT8 Vectors) & GraphRAG Citation Validator (`M08`)
- **Objective:** Implement INT8 384-d vector quantization, Reciprocal Rank Fusion ($k=60$) combining FTS5 `bm25()` and cosine similarity, the deterministic GraphRAG Subgraph Compiler, optional local Ollama client, and post-generation `[ev_id]` citation verification.
- **Files Created:** `backend/ai/__init__.py`, `backend/ai/search_rrf.py`, `backend/ai/assistant.py`, `tests/test_m08_search_and_ai.py`.
- **Modules Involved:** `M08` (Spec: `03_MODULE_SPECIFICATIONS/M08_HYBRID_RRF_SEARCH_AND_GRAPHRAG_ASSISTANT.md`).
- **Verification & Gate Criteria:** `pytest tests/test_m08_search_and_ai.py -v` passes.

---

### Phase 10: FastAPI REST/WebSocket Server & Multi-Format Export Engine (`M09`)
- **Objective:** Implement all REST/WebSocket endpoints specified in `02_ARCHITECTURE/API_SPECIFICATION.md` and the 5-format exporter (`JSON`, `CSV`, `STIX 2.1`, `FollowTheMoney JSONL`, `W3C PROV-JSON`).
- **Files Created:** `backend/exporters.py`, `backend/main.py`, `run.py`, `tests/test_m09_api_and_exports.py`.
- **Modules Involved:** `M09`.
- **Verification & Gate Criteria:** `pytest tests/test_m09_api_and_exports.py -v` passes 100%.

---

### Phase 11: 11-View Dual-Engine WebGL/Canvas Analyst Workstation Frontend (`M10`)
- **Objective:** Implement the complete dark-mode intelligence workstation UI (`frontend/index.html`, `frontend/assets/styles.css`, `frontend/assets/app.js`) following `06_UI_UX/UI_UX_SPECIFICATION.md` and `SCREEN_BY_SCREEN_REQUIREMENTS.md`.
- **Modules Involved:** `M10`.
- **Verification & Gate Criteria:** UI loads at `GET /` with all 11 views, interactive Canvas/WebGL + SVG graph, Bitemporal Time-Travel bar, Staging Triage promoter, Waterfall ER modal, and API Vault.

---

### Phase 12: End-to-End Integration, OPSEC, Privacy & Performance Validation
- **Objective:** Run the full multi-module test suite, verify `PASSIVE_ONLY` OPSEC mode blocks direct target traffic, verify audit hash-chain integrity, and benchmark memory/latency on 10,000 records.
- **Files Created:** `tests/test_e2e_platform.py`.
- **Verification & Gate Criteria:** Full `pytest -v` suite passes in `<15 seconds` with zero failures.

---

### Phase 13: Windows 11 Packaging, Scripts & Final Release Verification
- **Objective:** Create `install.bat`, `start.bat`, `stop.bat`, `scripts/install.ps1`, `scripts/start.ps1`, update user/developer documentation, and verify clean startup from a fresh checkout.
