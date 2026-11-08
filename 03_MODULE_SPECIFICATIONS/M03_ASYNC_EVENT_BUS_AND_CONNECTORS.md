# M03 — AsyncEventBus, Staging Triage Buffer & 24 Modular OSINT Connectors

## 1. Module Name & Identifier
- **Module Title:** M03 — AsyncEventBus, Staging Triage Buffer & 24 Modular OSINT Connectors
- **Target File Path(s):** `backend/collectors/orchestrator.py, backend/collectors/plugins/`

## 2. Purpose
Orchestrates concurrent, rate-limited, cached OSINT collection across 24 public and BYO-key data sources with depth-bounded recursive pivoting (`max_pivot_depth`) and a Staging Triage Buffer (`is_staged = 1`).

## 3. User-Facing Functionality
Powers View 2 (OSINT Playbook Launcher & Staging Triage Buffer) and View 10 (Task & Circuit Breaker Monitor).

## 4. Internal Responsibilities
Runs an asynchronous event queue (`AsyncEventBus`), checks SQLite `http_cache` before making network calls, records raw responses in `evidence_artifacts`, delegates text/HTML parsing to `M04`, delegates belief scoring to `M06`, and diverts batches $>50$ entities into `is_staged = 1`.

## 5. Inputs
`workspace_id: str`, `target_query: str`, `target_type: str`, `connectors: List[str]`, `pivot_depth: int`.

## 6. Outputs
`PlaybookExecutionResult` containing task statuses, entity/claim counts, staged counts, and provenance hashes.

## 7. Required Algorithms & Mathematical Formulations
1. **BFS Depth-Bounded Event Propagation** with bloom/hash loop prevention (`seen_queries`).
2. **SimHash 64-Bit Document Fingerprinting** for near-duplicate web/news detection.
3. **CISA KEV + FIRST EPSS + NVD CVSS Composite Vulnerability Risk Formula:** $\text{Risk} = \min(100, \mathbb{I}_{\text{KEV}} \cdot 95 + (1 - \mathbb{I}_{\text{KEV}}) \cdot (0.6 \cdot \text{CVSS} \cdot 10 + 0.4 \cdot \text{EPSS} \cdot 100))$.

## 8. Dependencies
`httpx`, `dnspython`, `beautifulsoup4`, `lxml`, `M01`, `M02`, `M04`, `M06`.

## 9. Backend Integration
Invoked by `POST /api/collect/workflow` and `POST /api/collect/playbook`.

## 10. Frontend Integration
Streams task updates to View 2 & View 10; populates Staging Triage Buffer.

## 11. Data Storage Requirements
Writes to `evidence_artifacts`, `entities`, `claims`, `claim_evidence`, `timeline_events`, `http_cache`, and `tasks`.

## 12. Error-Handling Requirements
Network timeouts, DNS NXDOMAIN, or HTTP 4xx/5xx errors mark the individual connector task as `FAILED` or `SKIPPED` (or use deterministic offline simulation when `offline_mode=true` is explicitly enabled) without aborting sibling connectors.

## 13. Security, OPSEC & Privacy Requirements
Respects `opsec_mode == 'PASSIVE_ONLY'` by skipping direct target web fetches; enforces custom `User-Agent` required by SEC EDGAR and Nominatim.

## 14. Testing Requirements
`tests/test_m03_collectors.py`: Test target auto-detection, HTTP cache hit/miss, staging buffer overflow (`>50` entities), keyed connector graceful skip, and provenance hash generation.

## 15. Dependencies on Other Modules
Depends on `M01`, `M02`, `M04`, `M06`.

## 16. Completion & Acceptance Criteria
All 24 connectors registered in `DEFAULT_CONNECTORS` and verified via `test_m03_collectors.py`.
