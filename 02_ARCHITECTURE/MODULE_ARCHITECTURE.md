# MODULE_ARCHITECTURE.md — Inter-Module Communication & Dependency Architecture

## 1. Ten-Module Decomposition
The **LocalOSINT v2.0** codebase is partitioned into 10 strictly decoupled modules (`M01` through `M10`) following the **Dependency Inversion** and **Open-Closed** principles:

| Module ID | Module Name | Package Path | Direct Upstream Dependencies |
| :--- | :--- | :--- | :--- |
| **`M01`** | Security Vault, Rate Limiter, Circuit Breaker & OPSEC Guard | `backend/core/config.py`, `backend/core/security.py` | Python Stdlib + `cryptography` |
| **`M02`** | Bitemporal SQLite WAL/FTS5/R*Tree & FollowTheMoney Storage | `backend/core/database.py`, `backend/core/ontology.py` | `M01` |
| **`M03`** | AsyncEventBus & 24 Modular OSINT Collectors + Staging Buffer | `backend/collectors/orchestrator.py`, `backend/collectors/plugins/` | `M01`, `M02`, `M04`, `M06` |
| **`M04`** | Two-Tier Hybrid NLP Extractor (Defang/Regex + ONNX GLiNER) & File Forensics | `backend/nlp/extractor.py`, `backend/nlp/forensics.py` | `M02` |
| **`M05`** | 3-Pass Blocking, Fellegi-Sunter EM Entity Resolution & Reversible Merge | `backend/core/entity_resolution.py` | `M02`, `M06` |
| **`M06`** | W3C PROV Lineage DAG, Dong Copying Discount & Subjective Logic Fusion | `backend/core/provenance_fusion.py` | `M02` |
| **`M07`** | `rustworkx` Graph Engine (Leiden, IEF-PageRank, Adamic-Adar) & Spatiotemporal/Burst | `backend/core/graph_analytics.py`, `backend/core/spatiotemporal.py` | `M02`, `M06` |
| **`M08`** | Hybrid RRF Search (FTS5 BM25 + INT8 Vectors) & GraphRAG Citation Validator | `backend/ai/search_rrf.py`, `backend/ai/assistant.py` | `M02`, `M06`, `M07` |
| **`M09`** | FastAPI REST/WebSocket API & Multi-Format Export Engine (STIX 2.1, FtM, PROV) | `backend/main.py`, `backend/exporters.py` | `M01`–`M08` |
| **`M10`** | 11-View Dual-Engine WebGL/Canvas Analyst Workstation Frontend | `frontend/index.html`, `frontend/assets/app.js`, `frontend/assets/styles.css` | `M09` (via REST/WS) |

---

## 2. Strict Inter-Module Communication Rules
1. **No Direct SQL Outside `M02` (`DatabaseManager`) and `M08` (`search_rrf`):** All collectors (`M03`), extractors (`M04`), and analytics engines (`M05`, `M06`, `M07`) read and write state exclusively through typed methods on `DatabaseManager`.
2. **All Confidence Updates Pass Through `M06` (`SubjectiveLogicEngine`):** No collector may manually overwrite `sl_belief` on an existing entity or claim. Collectors submit an `EvidenceArtifact` + `ClaimAttestation`, and `M06` recomputes $\omega = (b, d, u, a)$ and `epistemic_status`.
3. **Zero Circular Imports:** `M01` and `M02` never import from `M03`–`M09`.
