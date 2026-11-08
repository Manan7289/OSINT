# RELEASE_CHECKLIST.md — Pre-Release Verification Gate for Antigravity

Before declaring the implementation complete in `https://github.com/Manan7289/OSINT.git`, verify every item below:

- [ ] **1. Repository Cleanliness:** `git status` shows no untracked temporary `.db`, `.vault_key`, `.env`, or `__pycache__` files.
- [ ] **2. Automated Test Suite:** All unit, module, and E2E tests pass (`pytest -v` or `unittest discover`).
- [ ] **3. Database Schema Integrity:** All 14 tables and virtual tables (`search_index_fts`, `spatial_rtree`) initialize automatically on first run in SQLite `WAL` mode.
- [ ] **4. 24 Connectors Registered:** `GET /api/connectors` returns all 18 keyless public connectors (`READY`) and 6 optional BYO-key connectors (`API_KEY_REQUIRED` until configured).
- [ ] **5. Epistemic & Subjective Logic Invariants:** Every entity and claim maintains $b + d + u = 1.0$ and valid `epistemic_status`.
- [ ] **6. Audit Hash-Chain Verification:** `GET /api/settings` confirms `audit_chain_valid: true`.
- [ ] **7. Multi-Format Export Verification:** `json`, `csv`, `stix`, `ftm`, and `prov` exports all return valid downloadable payloads.
- [ ] **8. Windows 11 Scripts:** `install.bat`, `start.bat`, `stop.bat`, `scripts/install.ps1`, and `scripts/start.ps1` are present and executable.
