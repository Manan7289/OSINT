# FILE_STRUCTURE_AND_IMPLEMENTATION_MAP.md — Complete Repository File Ownership & Dependency Map

## 1. Intended Target Repository Structure (`https://github.com/Manan7289/OSINT.git`)

```text
OSINT/
├── README.md                                   # Project overview & Windows 11 quick-start
├── run.py                                      # Cross-platform Uvicorn launcher (127.0.0.1:8000)
├── requirements.txt                            # Pinned Python dependencies
├── .env.example                                # Optional environment variable template
├── .gitignore                                  # Excludes .venv, data/*.db, data/.vault_key, .env
├── install.bat                                 # Windows 11 CMD automated installer
├── start.bat                                   # Windows 11 CMD server + browser launcher
├── stop.bat                                    # Windows 11 CMD clean shutdown script
├── scripts/
│   ├── install.ps1                             # Windows 11 PowerShell installer
│   └── start.ps1                               # Windows 11 PowerShell launcher
├── backend/
│   ├── __init__.py
│   ├── main.py                                 # [M09] FastAPI application, routers & static mount
│   ├── exporters.py                            # [M09] JSON, CSV, STIX 2.1, FtM JSONL, W3C PROV exporters
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py                           # [M01] Paths, settings, CryptoVault, TokenBucketRateLimiter
│   │   ├── security.py                         # [M01] CircuitBreaker, OPSECGuard, HashChainedAuditLogger
│   │   ├── ontology.py                         # [M02] FollowTheMoney schemas, canonicalizers, RIOT-Lite list
│   │   ├── database.py                         # [M02] SQLite WAL + FTS5 + R*Tree 14-table DatabaseManager
│   │   ├── provenance_fusion.py                # [M06] W3C PROV DAG, Dong copying discount, Subjective Logic
│   │   ├── entity_resolution.py                # [M05] 3-Pass Blocking, Fellegi-Sunter EM, Reversible Merge
│   │   ├── graph_analytics.py                  # [M07] rustworkx/SciPy Leiden, IEF-PageRank, Adamic-Adar, Anomaly
│   │   └── spatiotemporal.py                   # [M07] Haversine HDBSCAN clustering & Kleinberg burst Z-score
│   ├── nlp/
│   │   ├── __init__.py
│   │   ├── extractor.py                        # [M04] Defang normalizer, Regex, Aho-Corasick, ONNX GLiNER, DGA
│   │   └── forensics.py                        # [M04] PDF (pypdf), DOCX, Image EXIF (Pillow), SimHash-64
│   ├── collectors/
│   │   ├── __init__.py
│   │   └── orchestrator.py                     # [M03] AsyncEventBus, Staging Buffer & 24 OSINT Connectors
│   └── ai/
│       ├── __init__.py
│       ├── search_rrf.py                       # [M08] SQLite FTS5 BM25 + INT8 Vectors + Reciprocal Rank Fusion
│       └── assistant.py                        # [M08] GraphRAG Subgraph Compiler, Ollama client, Citation Validator
├── frontend/
│   ├── index.html                              # [M10] 11-View Dark-Mode Analyst Workstation SPA
│   └── assets/
│       ├── styles.css                          # [M10] Precision dark-mode CSS design system
│       └── app.js                              # [M10] Dual Canvas/SVG Graph, Time-Travel, Waterfall ER, Map UI
└── tests/
    ├── test_m01_security.py                    # Unit tests for Vault, RateLimiter, CircuitBreaker, Audit Chain
    ├── test_m02_database.py                    # Unit tests for SQLite WAL, FtM canonicalization, Bitemporal Claims
    ├── test_m03_collectors.py                  # Tests for AsyncEventBus, Staging Buffer, and 24 Connectors
    ├── test_m04_nlp_forensics.py               # Tests for Defang parser, DGA entropy, SimHash, PDF/EXIF
    ├── test_m05_entity_resolution.py           # Tests for 3-pass blocking, Fellegi-Sunter EM, Merge/Unmerge
    ├── test_m06_provenance_fusion.py           # Tests for Dong copying discount & Subjective Logic fusion
    ├── test_m07_graph_spatiotemporal.py        # Tests for Leiden, IEF-PageRank, HDBSCAN, Kleinberg burst
    ├── test_m08_search_and_ai.py               # Tests for INT8 vectors, RRF search, and GraphRAG validator
    ├── test_m09_api_and_exports.py             # FastAPI TestClient & STIX 2.1 / FtM / PROV export tests
    └── test_e2e_platform.py                    # Full end-to-end investigation workflow & persistence test
```

---

## 2. File-by-File Ownership & Dependency Matrix

| File Path | Owning Module | Essential vs. Optional | Depends On | Depended On By |
| :--- | :---: | :---: | :--- | :--- |
| `backend/core/config.py` | `M01` | **Essential** | `cryptography`, stdlib | All backend files |
| `backend/core/security.py` | `M01` | **Essential** | `backend/core/config.py` | `database.py`, `orchestrator.py` |
| `backend/core/ontology.py` | `M02` | **Essential** | `idna`, stdlib | `database.py`, `entity_resolution.py`, `graph_analytics.py` |
| `backend/core/database.py` | `M02` | **Essential** | `config.py`, `security.py`, `ontology.py` | `M03`–`M09` |
| `backend/core/provenance_fusion.py` | `M06` | **Essential** | `database.py` | `orchestrator.py`, `entity_resolution.py`, `assistant.py` |
| `backend/nlp/extractor.py` | `M04` | **Essential** | `ontology.py`, `onnxruntime` (opt) | `forensics.py`, `orchestrator.py` |
| `backend/nlp/forensics.py` | `M04` | **Essential** | `extractor.py`, `pypdf`, `Pillow` | `orchestrator.py`, `main.py` |
| `backend/collectors/orchestrator.py` | `M03` | **Essential** | `M01`, `M02`, `M04`, `M06`, `httpx`, `dnspython` | `main.py` |
| `backend/core/entity_resolution.py` | `M05` | **Essential** | `database.py`, `provenance_fusion.py`, `numpy` | `main.py`, `assistant.py` |
| `backend/core/graph_analytics.py` | `M07` | **Essential** | `database.py`, `ontology.py`, `numpy`, `scipy`, `rustworkx` (opt) | `main.py`, `assistant.py` |
| `backend/core/spatiotemporal.py` | `M07` | **Essential** | `database.py`, `numpy`, `scipy` | `main.py` |
| `backend/ai/search_rrf.py` | `M08` | **Essential** | `database.py`, `numpy` | `main.py`, `assistant.py` |
| `backend/ai/assistant.py` | `M08` | **Essential** | `database.py`, `graph_analytics.py`, `search_rrf.py` | `main.py` |
| `backend/exporters.py` | `M09` | **Essential** | `database.py` | `main.py` |
| `backend/main.py` | `M09` | **Essential** | All backend modules (`M01`–`M09`) | `run.py`, `frontend/` |
| `frontend/index.html`, `styles.css`, `app.js` | `M10` | **Essential** | REST API (`backend/main.py`) | End-user browser |
