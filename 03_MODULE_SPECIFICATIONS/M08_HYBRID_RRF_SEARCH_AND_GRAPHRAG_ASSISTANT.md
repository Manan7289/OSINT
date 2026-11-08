# M08 — Hybrid RRF Search (FTS5 BM25 + INT8 Vectors) & GraphRAG Citation Validator

## 1. Module Name & Identifier
- **Module Title:** M08 — Hybrid RRF Search (FTS5 BM25 + INT8 Vectors) & GraphRAG Citation Validator
- **Target File Path(s):** `backend/ai/search_rrf.py, backend/ai/assistant.py`

## 2. Purpose
Delivers sub-15ms hybrid retrieval combining SQLite FTS5 `bm25()` with INT8 quantized 384-d semantic vectors via Reciprocal Rank Fusion ($k=60$), and synthesizes epistemically stratified intelligence answers and reports with deterministic `[ev_id]` citation verification.

## 3. User-Facing Functionality
Powers global hybrid search, View 9 (AI Intelligence Assistant & Report Builder), and contradiction alerts.

## 4. Internal Responsibilities
Indexes entities and evidence into `search_index_fts` and `vector_embeddings` (using ONNX 384-d embeddings when loaded, or deterministic char/token feature hashing embeddings in pure-CPU core mode so vector math always executes), fuses rankings via RRF ($k=60$), compiles 2-hop Leiden subgraphs for queries, optionally queries local Ollama, and validates every `[ev_xxxx]` citation tag.

## 5. Inputs
`workspace_id: str`, `query: str`, `mode: str`.

## 6. Outputs
Ranked hybrid search results, `GraphRAGResponse` with verified citations, and saved Markdown `Report` objects.

## 7. Required Algorithms & Mathematical Formulations
1. **BM25 + INT8 SIMD Cosine Similarity.**
2. **Reciprocal Rank Fusion ([Cormack et al., SIGIR 2009](https://arxiv.org/html/2508.01405v2)):** $\text{RRF}(d) = \frac{1}{60 + r_{\text{BM25}}(d)} + \frac{1}{60 + r_{\text{vec}}(d)}$.
3. **GraphRAG Subgraph Compilation ([arXiv:2608.13050](https://arxiv.org/abs/2608.13050)) & Post-Generation Regex Citation Entailment Validator.**

## 8. Dependencies
`numpy`, `httpx`, `onnxruntime` (optional), `M02`, `M06`, `M07`.

## 9. Backend Integration
Backs `GET /api/workspaces/{id}/search`, `POST /api/ai/query`, and `POST /api/reports/generate`.

## 10. Frontend Integration
Powers View 3 search bar and View 9 AI Assistant & Report preview.

## 11. Data Storage Requirements
Reads/writes `search_index_fts`, `vector_embeddings`, and `reports`.

## 12. Error-Handling Requirements
If local Ollama (`127.0.0.1:11434`) is unreachable, transparently falls back to the deterministic GraphRAG Subgraph Compiler in `<25ms`.

## 13. Security, OPSEC & Privacy Requirements
Flags any unverified LLM statement lacking a valid workspace `[ev_xxxx]` ID.

## 14. Testing Requirements
`tests/test_m08_search_and_ai.py`: Test INT8 quantization/dequantization, RRF ranking fusion, GraphRAG fact/inference separation, and citation validator.

## 15. Dependencies on Other Modules
Depends on `M02`, `M06`, `M07`.

## 16. Completion & Acceptance Criteria
All tests in `test_m08_search_and_ai.py` pass.
