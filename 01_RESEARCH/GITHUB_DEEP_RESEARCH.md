# GITHUB_DEEP_RESEARCH.md — Deep Code & Architecture Analysis of Open-Source Intelligence & Core Technology Repositories

## 1. Executive Summary
In this expanded review, we go far beyond traditional CLI OSINT scripts. We examined **22 open-source repositories** across five foundational layers:
1. Next-Generation Event-Driven OSINT Frameworks
2. Investigative Data Models, Entity Resolution & Sanctions Screening
3. High-Performance Embedded Graph & Vector Engines
4. Zero-Shot NLP & Document Forensics
5. WebGL Graph Visualization Libraries

For each repository, we document its URL, primary implementation language, key source modules, underlying algorithms, license compatibility, and our exact integration decision (**Direct Library Dependency**, **Methodological/Schema Adaptation**, or **Architectural Inspiration Only**).

---

## 2. Deep Repository Analysis & Integration Decisions

### Layer 1: Event-Driven OSINT & Attack-Surface Frameworks

| Repository & URL | Language & License | Key Modules & Architecture | Strengths | Limitations | Integration Decision for LocalOSINT |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **[BBOT (`blacklanternsecurity/bbot`)](https://github.com/blacklanternsecurity/bbot)** | Python 3 (`asyncio`), **GPL-3.0** | `bbot/core/engine.py`, `bbot/scanner/`, `bbot/modules/`. Event-driven recursive pub-sub pipeline where each module consumes typed events (`DNS_NAME`, `IP_ADDRESS`, `URL_UNVERIFIED`) and emits new events with loop/scope filtering. | Best modern Python async event-bus design in open-source OSINT; automatic wildcard DNS detection and scope distance bounding (`scan.scope_distance`). | GPL-3.0 viral license; heavy CLI/Linux tool assumptions. | **Architectural Inspiration Only:** Reimplement a clean, MIT-licensed `AsyncEventBus` with `scope_distance` and deduplication filters in `backend/core/pipeline.py`. |
| **[OWASP Amass (`owasp-amass/amass`)](https://github.com/owasp-amass/amass)** | Go, **Apache-2.0** | `netmap` graph store, [Open Asset Model (OAM)](https://github.com/owasp-amass/amass), token-bucket rate limiters per data source. | Formalizes infrastructure assets via the Open Asset Model; strong DNS/ASN graph traversal. | Go binary; recent v4 rewrite split into multiple repos with complex setup ([Issue #1104](https://github.com/owasp-amass/amass/issues/1104)). | **Schema Inspiration:** Adopt OAM's strict distinction between `FQDN`, `Netblock`, `AutonomousSystem`, and `TLS_Certificate`. |
| **[SpiderFoot (`smicallef/spiderfoot`)](https://github.com/smicallef/spiderfoot)** | Python 3, **MIT** | `sf.py`, `sflib.py`, `sfdb.py`, `correlations/` (37 YAML correlation rules), 200+ `modules/sfp_*.py`. | Declarative YAML correlation engine (`correlations/*.yaml`) that evaluates multi-event rules after collection. | Legacy CherryPy server; synchronous threading bottlenecks. | **Adapt YAML Correlation Concept:** Implement a declarative YAML/JSON rule engine for infrastructure & threat anomaly detection. |
| **[Recon-ng (`lanmaster53/recon-ng`)](https://github.com/lanmaster53/recon-ng)** | Python 3, **GPL-3.0** | `recon/core/framework.py`, workspace-scoped SQLite databases, centralized key store. | Clean per-investigation workspace isolation. | CLI-only; no graph or ER engine. | **Architectural Inspiration:** Retain workspace isolation and API key management. |
| **[theHarvester (`laramies/theharvester`)](https://github.com/laramies/theharvester)** | Python 3 (`asyncio`, `httpx`), **GPL-2.0** | `theHarvester/discovery/` (`crtsh.py`, `certspottersearch.py`, `otxsearch.py`). | Concise async HTTP collectors. | Stateless one-shot CLI output. | **Inspiration Only:** Use native async `httpx` collectors writing to our provenance graph. |
| **[IntelOwl (`intelowlproject/IntelOwl`)](https://github.com/intelowlproject/IntelOwl)** | Python (Django + Celery), **AGPL-3.0** | `api_app/analyzers_manager/`, `observable_analyzers/`, `file_analyzers/`. | Clear separation of Observable Analyzers vs. File Analyzers; Playbook orchestration. | Requires Docker + Celery + Redis + Postgres; AGPL-3.0 license. | **Concept Adaptation:** Support multi-connector "Investigation Playbooks" for observables and files without Docker/Celery overhead. |

---

### Layer 2: Investigative Data Models, Entity Resolution & Sanctions

| Repository & URL | Language & License | Key Modules & Algorithms | Strengths | Limitations | Integration Decision for LocalOSINT |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **[FollowTheMoney (`alephdata/followthemoney`)](https://github.com/alephdata/followthemoney)** | Python 3, **MIT** | `followthemoney/schema/`, `followthemoney/types/` (names, countries, IBANs, domains, companies, vessels, legal entities), `followthemoney-compare` ([GitHub](https://github.com/alephdata/followthemoney-compare)). | Battle-tested by OCCRP investigative journalists globally; models both entities (`Company`, `Person`, `LegalEntity`) and reified link intervals (`Ownership`, `Directorship`, `Payment`, `Sanction`). | Full [Aleph](https://github.com/alephdata/aleph) stack requires Elasticsearch + Kubernetes and is transitioning to commercial Aleph Pro. | **Direct Schema & Normalization Adoption (MIT):** Adopt FollowTheMoney's entity/interval schema design and property normalizers inside our SQLite/DuckDB engine without Aleph's heavy server stack. |
| **[OpenSanctions `yente` (`opensanctions/yente`)](https://pypi.org/project/yente/3.2.0/)** | Python 3 (FastAPI), **MIT** | Entity matching scoring engine (`nomenklatura` / `yente`) over FollowTheMoney entities ([API Docs](https://www.opensanctions.org/docs/api/)). | Excellent name/alias transliteration, phonetic normalization, and sanctions/PEP matching logic. | On-prem `yente` requires Elasticsearch. | **API Connector + Algorithm Adaptation:** Query the public [OpenSanctions API](https://api.opensanctions.org/) or ingest local OpenSanctions JSONL exports directly into SQLite FTS5. |
| **[Splink (`moj-analytical-services/splink`)](https://github.com/moj-analytical-services/splink)** | Python 3 + SQL (DuckDB / SQLite), **MIT** | `splink/internals/em_training_session.py`, `comparison_library.py`, `blocking.py`. | Gold-standard open-source implementation of Fellegi-Sunter + Expectation-Maximization + term-frequency adjustments + waterfall match explanation charts. | External pip package if not bundled. | **Direct Dependency (Enhanced) + Core Native Implementation:** Implement Splink's exact SQL/math formulation (EM + TF adjustments + waterfall weight breakdown) natively so it runs with zero external build issues. |
| **[Dedupe (`dedupeio/dedupe`)](https://github.com/dedupeio/dedupe)** | Python + Cython, **MIT** | Active learning logistic regression over affine gap / predicate blocking ([GitHub](https://github.com/dedupeio/dedupe)). | Pioneer in active-learning record linkage. | Requires manual human labeling of 20–50 pairs before it can score a new workspace. | **Rejected as Primary ER Engine:** Cold-start investigations need immediate unsupervised scoring (Fellegi-Sunter + EM), with optional analyst feedback overrides. |

---

### Layer 3: Embedded Graph, Columnar & Vector Engines

| Repository & URL | Language & License | Key Modules & Algorithms | Strengths | Limitations | Integration Decision for LocalOSINT |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **[rustworkx (`Qiskit/rustworkx`)](https://github.com/Qiskit/rustworkx)** | Rust + Python bindings (`PyO3`), **Apache-2.0** | `PyDiGraph`, `PyGraph`, Dijkstra, Yen's $k$-shortest paths, PageRank, betweenness centrality, connected components. | 10×–100× faster than pure-Python NetworkX; releases the Python GIL during heavy graph traversals; prebuilt Windows 11 wheels (`pip install rustworkx`). | Does not include database persistence (in-memory compute engine). | **Recommended Graph Compute Engine** (with automatic fallback to pure-Python/NumPy/SciPy algorithms so startup never breaks if optional wheel is absent). |
| **[sqlite-vec (`asg017/sqlite-vec`)](https://github.com/asg017/sqlite-vec)** | C (Zero-dependency SQLite extension), **MIT / Apache-2.0** | `vec0` virtual table supporting float32, int8, and bit-quantized SIMD vector search directly inside SQLite queries. | Runs everywhere SQLite runs; single-file database; supports metadata filtering + KNN. | Brute-force / IVF scan up to ~100k vectors (sub-15ms for 20k vectors). | **Recommended Embedded Vector Store** alongside NumPy INT8 memory-mapped fallback. |
| **[USearch (`unum-cloud/usearch`)](https://github.com/unum-cloud/usearch)** | C++17 + Python bindings, **Apache-2.0** | Single-header SIMD HNSW index supporting `f32`, `f16`, `i8`, and `b1` (binary) quantization. | Extremely fast HNSW approximate nearest neighbor search for $>100,000$ vectors on CPU. | Separate index file from SQLite. | **Optional High-Scale Vector Index** when workspace exceeds 50,000 documents. |
| **[DuckDB (`duckdb/duckdb`)](https://github.com/duckdb/duckdb)** | C++ + Python, **MIT** | Vectorized columnar OLAP SQL engine; reads SQLite files directly (`sqlite_scanner`), Parquet, JSONL. | Sub-second analytical aggregations over millions of log/timeline/blocking rows. | Single-writer concurrency model if used for OLTP writes. | **Recommended Analytical Co-Processor** (keep SQLite WAL as transactional OLTP store; use DuckDB or vectorized NumPy/Pandas for bulk analytical aggregations). |
| **[KuzuDB (`kuzudb/kuzu`)](https://github.com/kuzudb/kuzu)** | C++ Embedded Cypher Graph DB, **MIT** | Factorized worst-case optimal joins, Cypher queries. | High-speed embedded Cypher property graph. | **CRITICAL FINDING:** As verified in our live search ([github.com/kuzudb/kuzu](https://github.com/kuzudb/kuzu)), the KuzuDB repository was **archived in October 2025**. | **REJECTED:** Building a new platform on an archived database engine introduces severe long-term maintenance risk. SQLite WAL + `rustworkx` is far safer and actively maintained. |

---

### Layer 4: Zero-Shot NLP & Document Forensics

| Repository & URL | Language & License | Key Modules & Algorithms | Integration Decision for LocalOSINT |
| :--- | :--- | :--- | :--- |
| **[GLiNER (`urchade/GLiNER`)](https://aclanthology.org/2024.naacl-long.300/)** | Python / ONNX, **Apache-2.0** | Bidirectional transformer span-level NER supporting arbitrary entity prompts (`gliner_small-v2.1` ONNX INT8). | **Selected as Enhanced Local NER Engine** running on CPU via `onnxruntime`. |
| **[FOCA (`ElevenPaths/FOCA`)](https://github.com/elevenpaths/foca)** | C# .NET, **GPL-3.0** | Document metadata & hidden path/author/software extraction. | **Methodological Inspiration:** Implemented natively in Python via `pypdf`, `python-docx`, `openpyxl`, and `Pillow` EXIF without .NET/SQL Server dependencies. |

---

### Layer 5: Interactive Graph Visualization

| Repository & URL | Rendering Engine & License | Performance & Capabilities | Integration Decision for LocalOSINT |
| :--- | :--- | :--- | :--- |
| **[Sigma.js (`jacomyal/sigma.js`)](https://github.com/jacomyal/sigma.js/)** + **Graphology** | **WebGL**, **MIT** | Renders **10,000–50,000+ nodes and edges at 60 FPS** using GPU WebGL shaders; pairs with `graphology-layout-forceatlas2` running in a background WebWorker. | **Selected for Large-Scale Macro Graph View** (>500 nodes). |
| **[Cytoscape.js (`cytoscape/cytoscape.js`)](https://github.com/cytoscape/cytoscape.js/)** | **HTML5 Canvas**, **MIT** | Rich compound nodes, hierarchical DAG layouts (`dagre`, `cola`, `fcose`), edge-bends, and badge overlays up to ~2,500 elements. | **Selected for Tactical Ego-Graph & Provenance DAG View** (<2,500 elements). |
