# AI_AND_ML_STRATEGY.md — Pragmatic, Provenance-Grounded Local AI & Machine Learning Architecture

## 1. Core Philosophy: Deterministic First, Compact Specialized ONNX Second, Optional LLM Third
A major pitfall in contemporary OSINT tools is forcing a 7B–70B parameter Large Language Model onto tasks (like IP/domain extraction, record linkage, or community detection) where deterministic parsers or specialized statistical models are **100× faster, require 10× less RAM, and never hallucinate**.

Our AI/ML strategy strictly partitions workloads into three tiers so the platform operates with **full analytical integrity even when all neural models are disabled**.

---

## 2. Three-Tier Local AI/ML Capability Matrix

| Analytical Task | Tier 1: Core Deterministic / Statistical (Always On, 0 MB ML RAM) | Tier 2: Compact Specialized ONNX Models (CPU-Native, ~240 MB RAM Total) | Tier 3: Optional Local Generative LLM via Ollama (~4.5 GB RAM for 7B/8B Q4) |
| :--- | :--- | :--- | :--- |
| **Structured Observable Extraction** | RFC-compliant Regex + Defang Normalizer (`hxxp`, `[.]`) + Aho-Corasick gazetteers | Not needed (Regex has higher precision on IPs, CVEs, hashes, domains) | Never used (too slow and error-prone for raw IOC scanning) |
| **Unstructured Entity & Relation Extraction** | Capitalized phrase chunking + corporate legal suffix rules (`Inc`, `GmbH`, `Ltd`) | **[GLiNER (`gliner_small-v2.1` INT8 ONNX)](https://aclanthology.org/2024.naacl-long.300/)** zero-shot span extractor (~180 MB RAM, ~65 ms/doc on CPU) | Optional complex event/narrative extraction from long unstructured reports |
| **Semantic Search & Cross-Lingual Retrieval** | SQLite FTS5 `bm25()` with custom technical tokenizers | **`bge-small-en-v1.5` or `paraphrase-multilingual-MiniLM-L12-v2` (INT8 ONNX, 384-d)** (~60 MB RAM) fused with BM25 via **Reciprocal Rank Fusion (RRF)** | Optional query expansion / natural-language filter translation |
| **Entity Resolution (Record Linkage)** | Multi-pass Sorted Neighborhood blocking + **Fellegi-Sunter EM + Jaro-Winkler + Jaccard** | Cosine similarity between 384-d entity embeddings injected as comparison feature $\gamma_{\text{sem}}$ into Fellegi-Sunter | Optional human-readable adjudication summary for borderline ($P \in [0.50, 0.80]$) candidate pairs |
| **Contradiction & Entailment Detection** | Structured predicate conflict rules (e.g., conflicting `HAS_STATUS` or `REGISTERED_COUNTRY` claims; Subjective Logic $d > 0.25$) | **DeBERTa-v3-xsmall NLI Cross-Encoder (INT8 ONNX)** classifying pairs of text claims on the same entity as `ENTAILMENT`, `NEUTRAL`, or `CONTRADICTION` | Synthesizes multi-paragraph explanation of competing hypotheses |
| **Investigation Q&A & Report Generation** | Template-based **GraphRAG Subgraph Compiler** outputting structured Markdown tables of Facts, Inferences, Contradictions, and Provenance | Reranks top-20 evidence passages via ONNX Cross-Encoder before assembly | **[GraphRAG](https://arxiv.org/abs/2608.13050)-grounded synthesis** with mandatory inline `[ev_id]` citation verification |

---

## 3. Anti-Hallucination & Citation Entailment Architecture (GraphRAG Guardrails)
When Tier 3 (Ollama / OpenAI-compatible local LLM) is enabled by the analyst, the system enforces a **4-step Citation Verification Harness** inspired by [Provenance-Based CTI KGRAG](https://www.researchgate.net/publication/398266120_Provenance-Based_CTI_Analysis_with_Knowledge_Graph_and_RAG_KGRAG) and [Operationalizing CTI with GraphRAG (arXiv:2608.13050)](https://arxiv.org/abs/2608.13050):
1. **Subgraph & Provenance Context Serialization:** The LLM is never asked open-ended questions from parametric memory. Instead, the backend extracts the target's 2-hop Leiden community subgraph, Subjective Logic opinion tuples $\omega = (b, d, u, a)$, and verbatim evidence summaries with their `evidence_id` and `admiralty_rating`.
2. **Epistemically Stratified System Prompt:** The model must output structured sections matching our schema:
   - `### 1. Observed & Corroborated Facts` (every sentence must end with `[ev_xxxx]`)
   - `### 2. Graph-Derived Inferences` (every sentence must cite `[claim_xxxx]` or centrality/ER metrics)
   - `### 3. Contradictions & Intelligence Gaps` (citing high-disbelief $d$ or high-uncertainty $u$ nodes)
3. **Post-Generation Citation Validator:** A deterministic post-processor parses all `[ev_xxxx]` and `[ent_xxxx]` tags in the LLM's output against the workspace SQLite database. Any sentence asserting a factual claim without a valid workspace ID is automatically highlighted with an `[UNGROUNDED_LLM_STATEMENT — VERIFY]` warning badge in the UI.
4. **Zero-GPU Fallback Guarantee:** If Ollama is not installed or stopped, the exact same `GraphRAG Subgraph Compiler` renders a deterministic, publication-grade Markdown intelligence briefing in `< 25\text{ ms}` on CPU.
