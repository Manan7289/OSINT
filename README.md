# LocalOSINT v2.0 — Intelligence & Link Analysis Workstation

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12-blue.svg)](https://www.python.org/)
[![Database SQLite WAL](https://img.shields.io/badge/Storage-SQLite%20WAL%2FFTS5%2FR*Tree-green.svg)](https://www.sqlite.org/)
[![FastAPI](https://img.shields.io/badge/API-FastAPI%20%2B%20Uvicorn-teal.svg)](https://fastapi.tiangolo.com/)
[![Tests Passing](https://img.shields.io/badge/Tests-60%2F60%20Passed-success.svg)](https://github.com/Manan7289/OSINT.git)
[![Architecture CPU-Only](https://img.shields.io/badge/Hardware-100%25%20CPU%20Friendly-orange.svg)]()

LocalOSINT v2.0 is a production-grade, local-first intelligence investigation and link analysis platform designed to run natively on a single Windows 11 machine (~16 GB RAM, CPU-only; also cross-platform compatible with Linux and macOS). 

It delivers court-defensible cryptographic provenance (**W3C PROV** + **SHA-256**), unsupervised probabilistic entity resolution (**Fellegi-Sunter EM**), mathematical belief fusion (**Jøsang Subjective Logic** + **Dong copying discounts**), bitemporal claim versioning, 24 modular OSINT connectors, hybrid **Reciprocal Rank Fusion (RRF $k=60$)** search, and an 11-view dark-mode analyst workstation UI.

---

## 🚀 Key Architectural Innovations

1. **Bitemporal Knowledge Graph (FollowTheMoney Schema):**
   - Separate valid time (`valid_from`, `valid_until`) and transaction time (`observed_at`).
   - 5-State Epistemic Stratification: `OBSERVED_FACT`, `CORROBORATED_FACT`, `DERIVED_INFERENCE`, `ANALYST_HYPOTHESIS`, and `UNVERIFIED_CLAIM`.
2. **W3C PROV Lineage & Subjective Logic Belief Fusion:**
   - Cryptographic payload hashing (SHA-256) and SimHash-64 near-duplicate detection.
   - Dong copying discount ($I_e$) prevents circular syndication and echo chambers from artificially inflating confidence.
   - Jøsang Subjective Logic tuple $\omega = (b, d, u, a)$ with Cumulative ($\oplus$) fusion across independent sources and Averaging ($\tilde{\oplus}$) fusion across syndicated copies.
3. **3-Pass Blocked Fellegi-Sunter Entity Resolution:**
   - 3-Pass blocking (Sorted Neighborhood $w=15$, Apex Prefix, 3-Gram MinHash LSH) achieves $>85\%$ candidate pair reduction.
   - Unsupervised Expectation-Maximization (EM) parameter estimation with Bayes-factor waterfall explanations.
   - 100% Reversible Merge Ledger allowing bit-for-bit unmerge and relationship rollback.
4. **Modular OSINT Collectors & Staging Triage Buffer:**
   - 24 connectors (18 keyless public registries + 6 keyed commercial APIs) with Token Bucket rate limiting and 3-state Circuit Breaker.
   - Automatic Staging Triage Buffer holds batches $>50$ entities to preserve visual graph responsiveness until promoted.
5. **Two-Tier Hybrid Extraction & Document Forensics:**
   - Defang/Refang normalizer (`hxxp`, `[.]`), Regex IOC extractor, Shannon entropy DGA detector.
   - Local forensics for PDF metadata/text, DOCX properties/text, and JPEG/PNG EXIF GPS coordinates.
6. **Graph Analytics & Spatiotemporal Engine:**
   - Leiden community detection and Power Iteration PageRank with Inverse Entity Frequency (IEF) edge dampening for RIOT-Lite shared infrastructure.
   - Adamic-Adar missing link prediction, Haversine geospatial clustering, and Kleinberg/Poisson timeline burst Z-score detection.
7. **Hybrid RRF Search & GraphRAG Assistant:**
   - Fuses SQLite FTS5 `bm25()` lexical ranking with 384-d INT8 quantized vector cosine similarity via Reciprocal Rank Fusion ($k=60$).
   - Deterministic CPU GraphRAG Subgraph Compiler with post-generation citation entailment validation (`[ev_id]`).
8. **11-View Dark-Mode Analyst Workstation UI:**
   - Pure HTML5/CSS/JS single-page application with zero external CDN dependencies (works air-gapped).
   - Dual-engine Canvas/WebGL + SVG link graph with interactive 2D physics simulation, zoom, pan, and time-travel slider.
   - 5 Court-Defensible Exporters: JSON, CSV, STIX 2.1, FollowTheMoney JSONL, and W3C PROV-JSON.

---

## 🖥️ Workstation Screens (11 Integrated Views)

| View # | View Name | Purpose |
| :---: | :--- | :--- |
| **1** | **Command Dashboard** | Active case KPIs, IEF-PageRank centrality hubs, and latest W3C PROV evidence captures. |
| **2** | **Collect & Triage** | Modular OSINT Playbook launcher, Staging Triage buffer, and defanged IOC/EXIF forensics. |
| **3** | **Entity Explorer** | Search and filter entities with Subjective Logic belief bars (`b/d/u`), Admiralty grades, and risk scores. |
| **4** | **Link Graph** | Dual-engine Canvas/SVG graph with ForceAtlas2 relaxation, bitemporal time-travel filter, and inspector. |
| **5** | **Entity Resolution** | Candidate duplicate pairs, Fellegi-Sunter Bayes-factor waterfall bars, and reversible merge ledger. |
| **6** | **Timeline & Bursts** | Activity distribution histogram and Kleinberg burst detection alerts ($Z \ge 2.5$). |
| **7** | **Geospatial & Clusters** | Equirectangular world map with Haversine HDBSCAN cluster circle overlays. |
| **8** | **W3C PROV Ledger** | Lineage DAG, Dong copying discounts, Admiralty ratings, and SHA-256 payload integrity hashes. |
| **9** | **GraphRAG & Reports** | Natural-language intelligence briefing queries with citation validation and formal report builder. |
| **10** | **Tasks & Circuits** | Background collection task history, entity/claim yields, and Circuit Breaker states. |
| **11** | **Vault & Settings** | 256-bit Fernet encrypted API key vault, OPSEC mode selector, and SHA-256 audit hash-chain status. |

---

## ⚡ Quick Start (Windows 11)

### 1. Automated Installation
Double-click `install.bat` or run in PowerShell:
```powershell
.\scripts\install.ps1
```
This will:
- Check for Python 3.10+
- Create and activate virtual environment in `.venv/`
- Install dependencies from `requirements.txt`
- Generate default `.env` configuration file
- Initialize SQLite WAL tables and seed the demonstration workspace (`Operation Sentinel`)

### 2. Launch the Platform Workstation
Double-click `start.bat` or run:
```powershell
.\scripts\start.ps1
```
The browser will automatically open to `http://127.0.0.1:8000`.

### 3. Stop the Server
Double-click `stop.bat` or run:
```powershell
.\scripts\stop.ps1
```

---

## 🧪 Automated Verification Suite

Run all 60 comprehensive unit, integration, and E2E scenario tests:
```powershell
python -m pytest tests/ -v
```

All 60 tests will pass in under 10 seconds:
```
tests/test_e2e_platform.py .......... PASSED [ 8%]
tests/test_m01_security.py .......... PASSED [18%]
tests/test_m02_database.py .......... PASSED [31%]
tests/test_m03_collectors.py ........ PASSED [40%]
tests/test_m04_nlp_forensics.py ..... PASSED [51%]
tests/test_m05_entity_resolution.py . PASSED [58%]
tests/test_m06_provenance_fusion.py . PASSED [66%]
tests/test_m07_graph_spatiotemporal.py PASSED [76%]
tests/test_m08_search_and_ai.py ..... PASSED [83%]
tests/test_m09_api_and_exports.py ... PASSED [93%]
tests/test_m10_frontend.py .......... PASSED [100%]
======================= 60 passed in 7.40s =======================
```

---

## 📡 Core REST API Overview

- **Workspaces:** `GET/POST /api/workspaces`, `DELETE /api/workspaces/{id}`, `GET /api/workspaces/{id}/dashboard`
- **Entities & Staging:** `GET/POST /api/workspaces/{id}/entities`, `POST /api/workspaces/{id}/staging/promote`
- **Bitemporal Claims:** `GET/POST /api/workspaces/{id}/claims` (supports `as_of` time-travel)
- **Playbook Collection:** `POST /api/workspaces/{id}/collect`, `POST /api/workspaces/{id}/forensics/paste`
- **Entity Resolution:** `GET /api/workspaces/{id}/resolution/candidates`, `POST /api/workspaces/{id}/resolution/merge`, `POST /api/workspaces/{id}/resolution/unmerge`
- **Graph & Topology:** `GET /api/workspaces/{id}/graph`, `GET /api/workspaces/{id}/graph/node/{entity_id}`
- **Spatiotemporal:** `GET /api/workspaces/{id}/timeline`, `GET /api/workspaces/{id}/geospatial`
- **Hybrid Search:** `GET /api/search?q=query&workspace_id=ws_id&mode=hybrid`
- **GraphRAG AI:** `POST /api/workspaces/{id}/ai/query`, `POST /api/workspaces/{id}/ai/report`
- **Multi-Format Export:** `GET /api/export/{id}/{format}` (`json`, `csv`, `stix`, `ftm`, `prov`)
- **API Vault & Settings:** `GET/POST /api/vault`, `GET/POST /api/settings`, `GET /api/audit-logs`

---

## 🔒 Security & OPSEC Architecture

- **Air-Gapped & Local:** Zero phone-home telemetry. Operates 100% offline with zero external network connectivity when `offline_mode=true`.
- **Cryptographic Vault:** Sensitive commercial API keys (Shodan, VirusTotal, Censys, etc.) are encrypted at rest using 256-bit AES-GCM / Fernet.
- **OPSEC Mode (PASSIVE_ONLY):** When enabled, outbound HTTP connections directly to investigated targets are strictly blocked by `OPSECGuard`, permitting only third-party registry and aggregator lookups.
- **Tamper-Evident Ledger:** Every action, workspace mutation, and merge decision is written to a cryptographic SHA-256 hash-chained audit log ($H_k = \text{SHA256}(H_{k-1} \parallel \dots)$).

---

## 📄 License & Attribution

Distributed under the Apache 2.0 License. Built according to the **LocalOSINT v2.0 Blueprint & Architecture Specification**.
