# SECURITY_PRIVACY_AND_RELIABILITY.md — Comprehensive Security, OPSEC, Provenance & Reliability Specification

## 1. Lawful & Ethical OSINT Boundaries
**LocalOSINT v2.0** is strictly designed for lawful public-source intelligence, corporate due diligence, journalistic verification, and authorized defensive security research.
- **Excluded by Design:** Credential stuffing, brute-force attacks, active vulnerability exploitation, unauthorized active SYN/UDP scanning, session-cookie hijacking, CAPTCHA bypass, and hosting stolen plaintext credential dumps.

---

## 2. Cryptographic API Key Vault & Local Storage Security
1. **Symmetric Encryption at Rest (`CryptoVault`):**
   - Uses 256-bit **Fernet (`AES-128-CBC` + `HMAC-SHA256`)** from Python's `cryptography` library.
   - Master key resolution priority:
     1. `LOCALOSINT_SECRET_KEY` environment variable (derived via SHA-256 + URL-safe Base64).
     2. Restricted local keyfile `data/.vault_key` (`chmod 0600` on POSIX; user-scoped ACL on Windows 11).
2. **Zero Key Leakage:**
   - REST endpoints (`GET /api/connectors`) return only `has_api_key: bool` and `masked_api_key: str` (`shod********3210`).
   - Workspace exports (`JSON`, `CSV`, `STIX`, `FtM`, `PROV`) never include `connector_configs` or `encrypted_api_key`.

---

## 3. Input Validation, Output Sanitization & Safe File Forensics
1. **SQL Injection Prevention:** 100% of SQLite queries in `DatabaseManager` use parameterized `?` bindings. Dynamic table/column names are never interpolated from user input.
2. **XSS Prevention in UI:** Every string rendered in `frontend/assets/app.js` passes through `escapeHtml()` before DOM insertion so malicious payloads embedded in WHOIS records, HTTP headers, or DNS TXT records cannot execute JavaScript in the analyst's browser.
3. **Safe Document Parsing (`M04`):**
   - Uploaded PDF, DOCX, and Image files are parsed strictly in memory (`io.BytesIO`) with a 25 MB upload limit.
   - XML/HTML parsing disables external entity resolution (`resolve_entities=False`) to prevent XXE attacks.

---

## 4. OPSEC `PASSIVE_ONLY` Mode
When a workspace is configured with `opsec_mode = "PASSIVE_ONLY"`, `OPSECGuard` intercepts every outbound HTTP request:
- **Permitted:** Third-party public registries and archives (`cloudflare-dns.com`, `rdap.org`, `crt.sh`, `stat.ripe.net`, `internetdb.shodan.io`, `services.nvd.nist.gov`, `www.cisa.gov`, `api.first.org`, `api.gleif.org`, `www.sec.gov`, `api.opensanctions.org`, `web.archive.org`, `api.gdeltproject.org`, `api.github.com`, `nominatim.openstreetmap.org`).
- **Blocked:** Direct connections to the target organization's own domain or IP address (`web_document_osint` direct crawl), ensuring the analyst's IP address never appears in the target's web server logs.

---

## 5. Evidence Integrity, Epistemic Stratification & Hash-Chained Audit Ledger
1. **Evidence Integrity:** Every `evidence_artifacts` row stores `payload_sha256 = SHA256(source_url || title || canonical_json)` and `simhash_64`.
2. **Epistemic Stratification:** Claims are classified at commit time into `OBSERVED_FACT`, `CORROBORATED_FACT`, `DERIVED_INFERENCE`, `ANALYST_HYPOTHESIS`, or `UNVERIFIED_CLAIM`.
3. **Tamper-Evident Audit Log (`audit_logs`):**
   - Each log entry $k$ computes `entry_hash = SHA256(prev_hash || seq_no || timestamp || action || workspace_id || details)`.
   - `DatabaseManager.verify_audit_chain()` recomputes the entire chain from `seq_no = 1` (`prev_hash = "0" * 64`) and alerts the user if any row was modified or deleted outside the application.

---

## 6. Rate Limiting, Circuit Breaking & Backup/Recovery
- **Token-Bucket Rate Limiting:** Enforces per-connector RPM limits (`crtsh_ct = 15 RPM`, `virustotal_v3 = 4 RPM`, `gleif_lei = 60 RPM`).
- **3-State Circuit Breaker:** Trips to `OPEN` for 60 seconds after 3 consecutive upstream `HTTP 429/502/503/504` or timeout errors, preventing cascading stalls.
- **Hot Backup & Recovery:** Because SQLite runs in `WAL` mode, analysts can back up an entire workspace via `GET /api/workspaces/{id}/export?format=json` or use SQLite's online backup API (`sqlite3.Connection.backup()`) without stopping the server.
