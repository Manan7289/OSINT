# GEMINI_3_8_FLASH_EXECUTION_GUIDE.md — Context-Window & Milestone Execution Protocol

## 1. Purpose of This Guide
This execution protocol is specifically engineered for **Gemini 3.8 Flash** operating inside **Google Antigravity**. Because the complete OSINT platform spans 10 core backend/frontend modules, 24 data-source connectors, and a full automated test suite, attempting to generate everything in a single monolithic turn risks context truncation or subtle interface mismatches.

Follow the **15 Golden Rules of Incremental Execution** below to guarantee a clean, deterministic, zero-defect build.

---

## 2. The 15 Golden Rules for Gemini 3.8 Flash

1. **Read `START_HERE.md` first**, followed by `ANTIGRAVITY_HANDOVER.md` and `IMPLEMENTATION_MASTER_PLAN.md`.
2. **Never Load All Documents Into Context Simultaneously:** Load only the specification file (`03_MODULE_SPECIFICATIONS/Mxx_*.md`) and schema/API contract (`02_ARCHITECTURE/DATABASE_DESIGN.md` or `API_SPECIFICATION.md`) required for the *current* phase you are implementing.
3. **Inspect `https://github.com/Manan7289/OSINT.git` Before Changing Anything:** Run `git status`, `git branch -a`, and list existing files so you never overwrite existing repository assets without documenting why.
4. **Treat `FINAL_TECHNICAL_DECISIONS.md` as Immutable Law:** Do not invent a competing database schema, do not substitute Elasticsearch or Neo4j for SQLite WAL, do not replace Leiden with Louvain, and do not replace Sorted Neighborhood + Fellegi-Sunter EM with an $O(N^2)$ loop.
5. **Implement Exactly One Phase at a Time (Phases 1 $ightarrow$ 13):** Complete all files for Phase $k$, run the Phase $k$ test command, fix any failures, mark Phase $k$ `[x]` in `09_PROJECT_MANAGEMENT/IMPLEMENTATION_TRACKER.md`, create a Git checkpoint commit, and only then begin Phase $k+1$.
6. **Maintain Strict Naming & Schema Consistency:** Use the exact table names (`workspaces`, `evidence_artifacts`, `entities`, `entity_blocking_keys`, `claims`, `claim_evidence`, `entity_merge_ledger`, `search_index_fts`, `spatial_rtree`, `connector_configs`, `http_cache`, `tasks`, `reports`, `audit_logs`), column names, and FastAPI route paths specified in `02_ARCHITECTURE/`.
7. **Write Tests Alongside Code—Never Defer Testing to the End:** Every backend module (`M01`–`M09`) has a corresponding `tests/test_mXX_*.py` file. Execute `pytest tests/test_mXX_*.py -v` immediately after writing the module.
8. **Zero Placeholders or Stubs:** Never write `pass`, `return {}`, `TODO: implement later`, or hardcoded fake search results in production modules. If an optional API key is missing, return a structured `SKIPPED` task state with a clear user message and `docs_url`.
9. **Graceful Optional Dependency Fallbacks:** Core features must work with standard pure-Python + SQLite + NumPy/SciPy packages even if optional heavy wheels (`onnxruntime` model weights or local Ollama server) are offline or not yet downloaded.
10. **Enforce Commit-Time Epistemic Stratification:** Every claim inserted into `claims` must have a validated `epistemic_status` (`OBSERVED_FACT`, `CORROBORATED_FACT`, `DERIVED_INFERENCE`, `ANALYST_HYPOTHESIS`, `UNVERIFIED_CLAIM`) and Subjective Logic tuple `(sl_belief, sl_disbelief, sl_uncertainty, sl_base_rate)` where $b + d + u = 1.0$.
11. **Enforce Source Independence Before Confidence Boosting:** Never increment `sl_belief` via Cumulative Fusion ($\oplus$) if two evidence artifacts share the same `upstream_lineage_family` or `parent_evidence_id`; use Averaging Fusion ($	ilde{\oplus}$) instead.
12. **Protect the Visual Graph Canvas with the Staging Buffer:** Any collector invocation emitting $>50$ child entities must set `is_staged = 1` on the overflow entities so the analyst's visual graph never freezes.
13. **Keep Documentation Synchronized:** If any minor implementation adjustment is required due to OS/library version differences on the target machine, log it immediately in `09_PROJECT_MANAGEMENT/CHANGELOG.md` and `OPEN_QUESTIONS_AND_RISKS.md`.
14. **Never Embed Secrets:** Keep `.venv/`, `data/*.db`, `data/.vault_key`, and `.env` in `.gitignore`.
15. **Verify End-to-End Startup Before Declaring Completion:** In Phase 13, start the FastAPI server (`python run.py`), verify `GET /api/health` returns `HTTP 200`, verify the UI loads at `http://127.0.0.1:8000`, and verify all test suites pass.
