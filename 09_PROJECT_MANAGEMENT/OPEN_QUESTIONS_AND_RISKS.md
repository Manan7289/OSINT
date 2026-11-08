# OPEN_QUESTIONS_AND_RISKS.md — Technical Risk Register & Mitigation Controls

| Risk ID | Risk Description | Likelihood | Impact | Engineered Mitigation in Handover Blueprint |
| :---: | :--- | :---: | :---: | :--- |
| `R01` | **Pydantic v1 vs. v2 Compatibility on Target Machine:** Target environment may have Pydantic v1.10 or Pydantic v2.x installed. | Medium | High | Write Pydantic models using standard `BaseModel` and `Field` idioms compatible with both v1 and v2 (avoid v2-only `@field_validator` or provide a compatibility shim). |
| `R02` | **Public API Rate Limiting / Outages (`crt.sh`, `nvd.nist.gov`):** Upstream free endpoints occasionally return HTTP 429 or 502/503 under load. | High | Medium | `M01` 3-state `CircuitBreaker` + `TokenBucketRateLimiter` + SQLite `http_cache` + deterministic fallback mode prevent pipeline hangs. |
| `R03` | **Graph Visual Overload on Large Domains:** A single domain may have $>2,000$ historical subdomains in Certificate Transparency logs. | High | High | `M03` Staging Triage Buffer (`is_staged = 1` above `staging_threshold = 50`) + `M07` RIOT-Lite super-node dampening keep the visual graph fast and readable. |
| `R04` | **Circular Reporting / Echo Chambers:** Multiple OSINT feeds repeating the same unverified claim. | High | High | `M06` groups evidence by `upstream_lineage_family` and SimHash-64 similarity, applying Averaging Fusion ($\tilde{\oplus}$) instead of Cumulative Fusion ($\oplus$). |
| `R05` | **Optional Binary Wheels Missing in Air-Gapped Setup:** User runs on a machine without `onnxruntime` model weights or `rustworkx`. | Medium | Low | Every module (`M04`, `M07`, `M08`) includes a 100% functional pure-Python/NumPy/SciPy fallback so the platform never fails to start or test. |
