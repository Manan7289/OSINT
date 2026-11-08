# ANTIGRAVITY_HANDOVER.md — Principal Engineering Handover for Google Antigravity

## 1. Project Overview & Core Objective
**LocalOSINT v2.0** is a local-first, single-machine Open-Source Intelligence (OSINT), probabilistic entity resolution, bitemporal knowledge graph, geospatial, and defensive cyber investigation workstation.

Unlike basic OSINT scripts that dump unverified JSON or enterprise platforms ([OpenCTI](https://github.com/opencti-platform/opencti), [MISP](https://github.com/misp/misp), [IntelOwl](https://github.com/intelowlproject/IntelOwl)) that require 16+ GB RAM across multi-container Elasticsearch/RabbitMQ/PostgreSQL clusters, **LocalOSINT** runs natively on **Windows 11 (~16 GB RAM, CPU-only)** using a single Python 3.11+ FastAPI process backed by **SQLite 3 (`WAL` + `FTS5` + `R*Tree`)**, **[DuckDB](https://duckdb.org/)**, **[rustworkx](https://github.com/Qiskit/rustworkx)**, and **INT8 quantized ONNX Runtime (`onnxruntime`)** models.

---

## 2. Official Target GitHub Repository & Audit Findings

- **Official Repository URL:** `https://github.com/Manan7289/OSINT.git`

### Honest Audit Findings from Packaging Environment
1. **Repository Inspection Status:** During packaging inside an air-gapped sandbox VM (`execute_bash` has outbound internet disabled by policy), we queried `https://github.com/Manan7289/OSINT` via web search and browse tools. Public search indices returned zero indexed pages for `github.com/Manan7289/OSINT`, and the unauthenticated web browse tool returned an access restriction notice (`"not able to access the website(s) you've provided"`), which occurs when a GitHub repository is newly initialized/empty, unindexed, or set to private requiring local Git credentials.
2. **Audit of Prior Local Project Materials:** We audited all 13 Turn-1 prototype documents (`LocalOSINT/`) and all 15 Turn-2 reassessment documents. Every conflict between the Turn-1 prototype (which used $O(N^2)$ blocking, static Fellegi-Sunter weights, linear confidence boosts, and DOM SVG rendering) and the Turn-2 reassessment has been **permanently resolved in favor of the v2.0 Blueprint** documented in `FINAL_TECHNICAL_DECISIONS.md`.

### Mandatory Repository Initialization & Inspection Protocol for Antigravity
When Antigravity starts execution on the user's Windows 11 machine, its very first step (**Phase 1 of `IMPLEMENTATION_MASTER_PLAN.md`**) must be:
```powershell
# 1. If not already inside the cloned repository, clone it using the user's configured Git credentials:
git clone https://github.com/Manan7289/OSINT.git
cd OSINT

# 2. Inspect current status, branches, remotes, and any existing files:
git status
git branch -a
git log -n 5 --oneline
dir /a
```
- **If the repository is empty (or contains only an initial `README.md` / `LICENSE` / `.gitignore`):** Initialize the `main` branch, preserve any existing `LICENSE` or README notes, and scaffold the exact folder structure defined in `04_IMPLEMENTATION/FILE_STRUCTURE_AND_IMPLEMENTATION_MAP.md`.
- **If the repository already contains existing code or commits:** Create a feature branch (`git checkout -b feat/localosint-v2-core`) or commit cleanly in incremental checkpoints on the active branch without running destructive commands (`git push --force` or `git reset --hard` are strictly forbidden).
- **Zero Embedded Credentials:** Never hardcode GitHub Personal Access Tokens (PATs), passwords, or API keys in source files or commit history. Rely on Windows Git Credential Manager (`git config --global credential.helper manager`).

---

## 3. Summary of the Approved Final Architecture
1. **Data Model (`02_ARCHITECTURE/DATABASE_DESIGN.md`):** [FollowTheMoney (FtM)](https://github.com/alephdata/followthemoney)-aligned entities + **Bitemporal Reified Claims** (`valid_from`/`valid_until` vs. `observed_at`) + **5-State Epistemic Stratification** (`OBSERVED_FACT`, `CORROBORATED_FACT`, `DERIVED_INFERENCE`, `ANALYST_HYPOTHESIS`, `UNVERIFIED_CLAIM`).
2. **Storage Layer:** SQLite 3 (`WAL` + `FTS5` with custom technical tokenizer + `R*Tree` spatial index) + [DuckDB](https://duckdb.org/) analytical co-processor + [sqlite-vec](https://github.com/asg017/sqlite-vec) / NumPy INT8 384-d vector index.
3. **Collection Engine (`M03`):** Asynchronous event-driven pub-sub bus (`AsyncEventBus` inspired by [BBOT](https://github.com/blacklanternsecurity/bbot)) with per-source `TokenBucketRateLimiter`, 3-state `CircuitBreaker`, `PASSIVE_ONLY` OPSEC guard, **Staging Triage Buffer (`is_staged = 1`)**, and 24 modular OSINT connectors (18 keyless public + 6 optional BYO-key encrypted in a 256-bit Fernet vault).
4. **Entity Resolution (`M05`):** 3-pass blocking (Sorted Neighborhood $w=15$ + Identifier Prefix + 3-gram MinHash LSH) $ightarrow$ Unsupervised Fellegi-Sunter Expectation-Maximization (EM) with Inverse Entity Frequency (IEF) weight scaling $ightarrow$ Bayes-factor waterfall charts and a **100% Reversible Merge Ledger**.
5. **Provenance & Belief Fusion (`M06`):** W3C PROV lineage DAG + [Dong et al. (VLDB 2009)](http://www.vldb.org/pvldb/vol2/vldb09-335.pdf) copying discount + [Jøsang Subjective Logic ($\omega = (b, d, u, a)$)](https://www.mn.uio.no/ifi/english/people/aca/josang/publications/jwz2017-fusion.pdf) applying Cumulative Fusion ($\oplus$) across independent lineage families and Averaging Fusion ($	ilde{\oplus}$) within the same family.
6. **Graph & Spatiotemporal Analytics (`M07`):** [rustworkx](https://github.com/Qiskit/rustworkx) + [Leiden Community Detection](https://arxiv.org/abs/1810.08473) + RIOT-Lite Super-Node Dampening + IEF-Weighted Personalized PageRank + Adamic-Adar link prediction + Haversine HDBSCAN spatial clustering + Kleinberg temporal burst detection.
7. **Hybrid Search & AI Assistant (`M08`):** SQLite FTS5 `bm25()` + 384-d INT8 embeddings fused via [Reciprocal Rank Fusion ($k=60$)](https://arxiv.org/html/2508.01405v2) + deterministic [GraphRAG Subgraph Compiler](https://arxiv.org/abs/2608.13050) + optional local Ollama LLM guarded by a post-generation `[ev_id]` citation entailment validator.
8. **Workstation Frontend (`M10`):** Dual-engine graph workbench ([Sigma.js WebGL](https://github.com/jacomyal/sigma.js/) for 50,000-node macro views + [Cytoscape.js Canvas](https://github.com/cytoscape/cytoscape.js/) for tactical ego-graphs and W3C PROV trees), bitemporal time-travel slider, waterfall ER adjudicator, and `STIX 2.1` / `FollowTheMoney` / `CSV` / `Markdown` export.

---

## 4. Implementation Priorities & Phased Delivery
- **Priority P0 (Foundational MVP — Phases 1 to 7):** Repository setup, M01 Security Vault/RateLimiter/CircuitBreaker, M02 Bitemporal SQLite WAL/FTS5/R*Tree schema, M03 AsyncEventBus + 14 core keyless connectors, M04 Tier-1 Defang/Regex/File Metadata extractor, M05 Blocked Fellegi-Sunter EM + Reversible Merge, M06 W3C PROV + Subjective Logic Fusion, M07 Leiden/IEF-PageRank graph engine.
- **Priority P1 (Enhanced Workstation — Phases 8 to 11):** M04 Tier-2 ONNX INT8 GLiNER NER, remaining 10 connectors (GLEIF LEI, OpenSanctions, CISA KEV, FIRST EPSS, URLScan, Wikidata, plus optional keyed APIs), M08 Hybrid RRF Search + GraphRAG Assistant, M09 FastAPI REST/WebSocket server, M10 11-View Workstation UI with WebGL/Canvas graphs and Staging Triage Buffer.
- **Priority P2 (Advanced Polish & Release — Phases 12 to 13):** Spatiotemporal HDBSCAN + Kleinberg burst anomalies, full E2E & regression test suite (`pytest`), OPSEC/privacy audit, and Windows 11 `install.bat` / `start.bat` packaging.

---

## 5. Final Delivery Requirements for Antigravity
Antigravity's mission is complete **only** when:
1. All 10 modules (`M01`–`M10`) are implemented with real, working code inside `https://github.com/Manan7289/OSINT.git`.
2. Zero placeholder functions (`pass`, `TODO`, hardcoded mock arrays) exist in any production path.
3. All unit, database, entity-resolution, belief-fusion, collector, and FastAPI integration tests pass (`pytest -v`).
4. The application starts cleanly on Windows 11 (`start.bat` or `python run.py`) and serves the full interactive workstation UI on `http://127.0.0.1:8000`.
