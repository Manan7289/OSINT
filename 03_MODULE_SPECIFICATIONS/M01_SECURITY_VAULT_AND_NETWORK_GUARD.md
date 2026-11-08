# M01 — Security Vault, Rate Limiter, Circuit Breaker & OPSEC Guard

## 1. Module Name & Identifier
- **Module Title:** M01 — Security Vault, Rate Limiter, Circuit Breaker & OPSEC Guard
- **Target File Path(s):** `backend/core/config.py, backend/core/security.py`

## 2. Purpose
Provides symmetric encryption at rest for API keys, per-source token-bucket rate limiting, 3-state circuit breaking for flaky upstream APIs, OPSEC Passive-Only network enforcement, and tamper-evident SHA-256 hash-chained audit logging.

## 3. User-Facing Functionality
Powers View 11 (API Key Vault & OPSEC Settings), masked API key indicators (`shod****3210`), connector health badges (`READY`, `CIRCUIT_OPEN`, `API_KEY_REQUIRED`), and the hash-chain verification indicator.

## 4. Internal Responsibilities
Manages `data/.vault_key` generation/loading (`0600` permissions), encrypts/decrypts connector credentials via `Fernet`, throttles outbound HTTP calls per `connector_id`, trips circuit breakers on consecutive HTTP 429/5xx errors, blocks direct target connections when `opsec_mode == 'PASSIVE_ONLY'`, and computes `entry_hash = SHA256(prev_hash || seq_no || timestamp || action || details)` for `audit_logs`.

## 5. Inputs
`plaintext_api_key: str`, `connector_id: str`, `requests_per_minute: int`, `target_url: str`, `opsec_mode: str`.

## 6. Outputs
`encrypted_token: str`, `masked_key: str`, `(allowed: bool, wait_seconds: float)`, `circuit_state: Literal['CLOSED','OPEN','HALF_OPEN']`, `AuditLogVerifyResult`.

## 7. Required Algorithms & Mathematical Formulations
1. **Fernet (`AES-128-CBC` + `HMAC-SHA256`)** symmetric authenticated encryption.
2. **Token Bucket Algorithm:** $T_{\text{new}} = \min(C, T_{\text{old}} + \Delta t \cdot (RPM / 60))$.
3. **3-State Circuit Breaker:** Trips `CLOSED -> OPEN` after 3 consecutive failures; transitions `OPEN -> HALF_OPEN` after cooldown $\tau = 60\text{s}$; resets `HALF_OPEN -> CLOSED` on probe success.
4. **Hash-Chained Ledger:** $H_k = \text{SHA256}(H_{k-1} \parallel k \parallel t_k \parallel a_k \parallel d_k)$ with genesis $H_0 = 0^{64}$.

## 8. Dependencies
Python stdlib (`os`, `time`, `hashlib`, `hmac`, `base64`, `threading`, `logging`, `pathlib`) + `cryptography>=38.0.0`.

## 9. Backend Integration
Imported by `M02` (`DatabaseManager`) and `M03` (`CollectorOrchestrator`) as singletons `vault`, `rate_limiter`, and `circuit_breaker`.

## 10. Frontend Integration
Exposed via `GET /api/connectors`, `PUT /api/connectors/{id}`, and `GET /api/settings`.

## 11. Data Storage Requirements
Reads/writes `data/.vault_key` on filesystem; persists state in `connector_configs` and `audit_logs` tables.

## 12. Error-Handling Requirements
Corrupt ciphertext in `decrypt()` logs a warning and returns `""` without crashing; tripped circuit breaker raises `CircuitOpenError` handled gracefully by `M03`.

## 13. Security, OPSEC & Privacy Requirements
Never logs or returns plaintext API keys in REST responses; enforces `PASSIVE_ONLY` check before any non-registry HTTP request.

## 14. Testing Requirements
`tests/test_m01_security.py`: Test Fernet round-trip, key masking, token bucket exhaustion/refill, circuit breaker state transitions, and audit log tamper detection.

## 15. Dependencies on Other Modules
None (Foundational Layer 0 module).

## 16. Completion & Acceptance Criteria
All 5 unit tests in `test_m01_security.py` pass with 0 warnings.
