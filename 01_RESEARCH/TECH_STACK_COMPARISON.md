# TECH_STACK_COMPARISON.md — Rigorous Evaluation of Candidate Technologies for a Local-First Windows 11 OSINT Platform

## 1. Evaluation Criteria
Every technology layer is evaluated against seven strict criteria tailored to a single-machine **Windows 11 workstation (~16 GB RAM, CPU-only operation)**:
1. **Idle & Peak RAM Footprint** (must leave $\ge 10\text{ GB}$ free for the OS and browser).
2. **Startup Latency** (target $< 2\text{ seconds}$ cold start).
3. **Windows 11 Native Compatibility** (prebuilt `win_amd64` wheels; zero requirement for Visual C++ Build Tools, WSL2, or Docker Desktop).
4. **Algorithmic Throughput on CPU** (GIL behavior, SIMD vectorization, async I/O).
5. **Long-Term Maintenance & Repository Health** (eliminating archived or abandoned projects).
6. **Zero-Config Single-Folder Portability** (easy backup/export of workspaces).
7. **License Permissiveness** (MIT / Apache-2.0 / BSD preferred).

---

## 2. Layer-by-Layer Comparative Analysis

### 2.1 Backend Language & Web Framework

| Candidate | Concurrency & Speed | OSINT/ML Ecosystem | Windows 11 Packaging | Trade-offs | Verdict |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Python 3.11/3.12 + FastAPI + Uvicorn (`asyncio`)** | High async I/O throughput (`httpx`, `aiosqlite`); CPU-bound work offloaded to Rust/C++ extensions (`rustworkx`, `onnxruntime`, `numpy`). | **Unmatched:** Native access to `dnspython`, `pypdf`, `lxml`, `onnxruntime`, `scipy`, `cryptography`, `duckdb`. | Official Python installer or embedded redistributable; 100% prebuilt wheels. | Python GIL requires offloading heavy graph/ML loops to C/Rust extensions or `ProcessPoolExecutor`. | **SELECTED (Primary Backend)** |
| **Go (Golang) + Gin/Fiber** | Single static binary; fast goroutines. | Weak local NLP/ML (no native GLiNER, SciPy, or Splink without cgo/sidecars). | Easy single `.exe`, but requires dual-language sidecar for Python ML/forensics. | Splits codebase into two languages. | **Rejected** |
| **Rust + Axum (or Tauri)** | Maximum CPU speed and memory safety. | High friction for rapid OSINT connector authoring and document parsing compared to Python. | Requires Rust toolchain during development; better used *via* Python bindings (`rustworkx`, `pydantic-core`, `orjson`). | Slower connector iteration velocity. | **Used via Python C/Rust Extensions (`rustworkx`, `onnxruntime`)** |

---

### 2.2 Transactional, Analytical & Graph Database Storage

| Candidate | Architecture | Idle RAM | Windows 11 Setup | Maintenance Status | Technical Trade-offs | Verdict |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **SQLite 3 (WAL Mode + FTS5 + R*Tree)** | Embedded ACID relational + full-text + spatial index in a single file. | **~5–15 MB** | Built into Python (`sqlite3`). Zero external server. | Rock-solid (supported through 2050). | Single-writer lock (mitigated by WAL + serialized async write queue); recursive CTEs slower than in-memory Rust graphs above 5 hops. | **SELECTED (Transactional Core & FTS5/R*Tree Index)** |
| **[DuckDB (`duckdb/duckdb`)](https://duckdb.org/)** | Embedded vectorized columnar OLAP engine ([GitHub](https://github.com/duckdb/duckdb)). | ~50–150 MB | Single `pip install duckdb` (`win_amd64` wheel). | Actively maintained (v1.5/v2.0 in 2026, MIT). | Ideal for bulk analytical SQL, Parquet export, and [Splink](https://github.com/moj-analytical-services/splink) EM record linkage; less suited than SQLite WAL for high-frequency tiny OLTP updates. | **SELECTED (Analytical & Splink ER Co-Processor)** |
| **[KuzuDB (`kuzudb/kuzu`)](https://github.com/kuzudb/kuzu)** | Embedded Cypher property graph database. | ~100 MB | Prebuilt wheels up to v0.11. | **ARCHIVED in Oct 2025** ([Verified on GitHub](https://github.com/kuzudb/kuzu)). | Relying on an archived database engine is an unacceptable architectural risk. | **REJECTED (Archived Project)** |
| **Neo4j Community / Memgraph / PostgreSQL** | External client-server DBMS. | 1.5–4.0 GB (JVM / Docker) | Requires Java JVM, Windows Service, or Docker Desktop. | Active. | Heavy idle RAM; breaks single-command portable Windows 11 installation. | **Rejected for Default Local Mode** (Optional export only) |

---

### 2.3 In-Memory Graph Compute Engine

| Candidate | Implementation | Speed (10k nodes, PageRank / Shortest Path) | Capabilities | Verdict |
| :--- | :--- | :--- | :--- | :--- |
| **[rustworkx (`Qiskit/rustworkx`)](https://github.com/Qiskit/rustworkx)** + **`igraph` / `scipy.sparse`** | Rust (`petgraph` + `PyO3`) / C core | **~2–8 ms** (10–50× faster than NetworkX) | Dijkstra, Yen's $k$-shortest paths, PageRank, centrality, Leiden (via `leidenalg`/`igraph` or sparse matrix solver). | **SELECTED (Primary Graph Compute Layer)** with pure-Python/SciPy fallback. |
| **NetworkX** | Pure Python dicts | ~150–800 ms | Rich API, easy debugging. | **Retained only as fallback / adapter** due to pure-Python loop overhead on large graphs. |

---

### 2.4 Search & Dense Vector Retrieval Engine

| Candidate | Architecture | Memory (50k chunks, 384-d) | Windows 11 Wheel | Verdict |
| :--- | :--- | :--- | :--- | :--- |
| **SQLite FTS5 (`bm25()`) + [sqlite-vec](https://github.com/asg017/sqlite-vec) / [USearch](https://github.com/unum-cloud/usearch) (INT8)** | Hybrid Sparse BM25 + SIMD INT8 HNSW/Flat vectors fused via **Reciprocal Rank Fusion (RRF)** | **~20 MB RAM** (INT8 quantized) | Prebuilt `win_amd64` wheels; zero external server. | **SELECTED** (Sub-15ms hybrid search, 4× lower RAM via INT8 quantization). |
| **[LanceDB (`lancedb/lancedb`)](https://github.com/lancedb/lancedb)** | Embedded disk-backed Lance columnar vector store. | ~80 MB RAM | Prebuilt wheels. | **Viable Alternative** if multi-million vector disk indexing is needed; slightly heavier dependency tree (Arrow/PyArrow) than `sqlite-vec`/`usearch`. |
| **Elasticsearch / OpenSearch / Qdrant Server** | External search daemon. | 1.0–4.0 GB RAM | Requires Docker or service installer. | **Rejected** (violates lightweight local-first mandate). |

---

### 2.5 Frontend Workstation & Graph Visualization Stack

| Candidate | Graph Rendering Capacity | UI Responsiveness & Ecosystem | Verdict |
| :--- | :--- | :--- | :--- |
| **React 18 + TypeScript + Vite + Tailwind + [Sigma.js (WebGL)](https://github.com/jacomyal/sigma.js/) + [Cytoscape.js (Canvas)](https://github.com/cytoscape/cytoscape.js/) + MapLibre GL / Leaflet** | **Dual-Engine Graph:** Sigma.js WebGL renders **10,000–50,000+ nodes at 60 FPS**; Cytoscape.js renders detailed compound ego-graphs and W3C PROV lineage trees (<2,000 nodes). | Pre-compiled static bundle (`frontend/dist`) served directly by FastAPI—**Node.js is NOT required on the end-user's Windows 11 machine** to run the prebuilt app, while full TypeScript source is included for developers. | **SELECTED** (Best of both worlds: zero runtime Node requirement for users + WebGL 60 FPS scalability). |
| **DOM SVG Graph (Phase 1 approach)** | Degrades above ~500 nodes due to browser DOM layout reflows. | Zero dependencies, but insufficient for 5,000+ node investigations. | **Replaced** by WebGL (Sigma.js) + Canvas (Cytoscape.js). |

---

### 2.6 Local AI & NLP Inference Runtime

| Candidate | Footprint & Speed on CPU | Role in Platform | Verdict |
| :--- | :--- | :--- | :--- |
| **ONNX Runtime (`onnxruntime` CPUExecutionProvider, INT8 Quantized)** | **~180–250 MB RAM** total for `gliner_small-v2.1` (zero-shot NER) + `bge-small-en-v1.5` (384-d embeddings). Runs on AVX2/AVX-512 CPU in **15–65 ms/doc** without PyTorch's 2.5 GB install bloat. | **Enhanced Local NLP Tier** (NER, Embeddings, Cross-Encoder Reranking). | **SELECTED (Primary Embedded ML Runtime)** |
| **Ollama / `llama.cpp` (Optional External Local Process)** | 4.5 GB RAM for 7B/8B Q4_K_M GGUF model (or 1.6 GB for 3B Q4_K_M). | **Optional Generative AI Tier** (GraphRAG natural-language synthesis, contradiction explanation, narrative drafting). | **SELECTED (Optional Local LLM Integration)** |
| **Full PyTorch + HuggingFace `transformers` (FP32/FP16)** | 2.5+ GB disk install, 1.5–3.0 GB RAM for encoders. | Unnecessary bloat when ONNX Runtime executes the exact same quantized models 3× faster on CPU. | **Rejected in favor of ONNX Runtime** |

---

## 3. Summary of the Recommended Complete Tech Stack
- **Backend Core:** Python 3.11+ / FastAPI / Uvicorn / `httpx` (`asyncio` HTTP/2 connection pooling)
- **Task & Workflow Engine:** Persistent SQLite-backed `AsyncEventBus` + `ProcessPoolExecutor` for CPU-bound ER/graph/ONNX tasks
- **Storage Engine:** SQLite 3 (`WAL` + `FTS5` + `R*Tree`) + [DuckDB](https://duckdb.org/) analytical co-processor + [sqlite-vec](https://github.com/asg017/sqlite-vec) / [USearch](https://github.com/unum-cloud/usearch) INT8 vector index
- **Graph Compute:** [rustworkx](https://github.com/Qiskit/rustworkx) + Leiden community detection + SciPy sparse matrices
- **Local AI / NLP:** `onnxruntime` (INT8 quantized [GLiNER](https://aclanthology.org/2024.naacl-long.300/) + 384-d Bi-Encoder + Cross-Encoder) + optional local [Ollama](https://github.com/ollama/ollama)
- **Frontend UI:** Pre-bundled React + TypeScript + Tailwind + [Sigma.js](https://github.com/jacomyal/sigma.js/) (WebGL) + [Cytoscape.js](https://github.com/cytoscape/cytoscape.js/) (Canvas) + Leaflet/MapLibre GL
