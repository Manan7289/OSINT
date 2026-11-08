# 13 — SECURITY AND PRIVACY ARCHITECTURE (`M01` & `M11`)

**Target Repository:** [`https://github.com/Manan7289/OSINT.git`](https://github.com/Manan7289/OSINT.git)  
**Target Files:** `backend/core/security.py`, `backend/visual/consent_guard.py`, `backend/visual/vision_engine.py`

---

## 1. Local-First Zero-Telemetry Privacy Guarantee

1. **100% Local Persistence:** All entities, edges, spatiotemporal trajectories (`geo_tracks`), sweep deltas (`sweep_deltas`), visual assets (`visual_assets`), and audit logs (`audit_log`) are stored exclusively on the user's local disk inside `data/osint_command.db`.
2. **Zero Cloud AI Leakage:** All entity resolution, graph analytics, perceptual hashing (`pHash`), face detection (`OpenCV YuNet`), face verification (`OpenCV SFace`), and AI briefings (`Ollama` / deterministic synthesis) execute locally on the user's CPU/GPU. Uploaded photographs and case files are **never** transmitted to any external cloud API.
3. **Loopback-Only Binding:** FastAPI binds strictly to `127.0.0.1:8420` by default (`backend/main.py`), preventing unauthorized LAN/WAN exposure.

---

## 2. Biometric & Visual Privacy Safeguards (`M11`)

To ensure the Visual Intelligence Studio (`backend/visual/`) is strictly ethical, lawful, and privacy-preserving:

1. **Mandatory Default Bystander Face Blurring (`blur_bystanders=True`):**
   - Every image analyzed via `POST /api/v1/visual/analyze` automatically runs face detection and applies irreversible Gaussian + mosaic pixelation to all detected face regions before storing `redacted_image_b64` in SQLite.
2. **Prohibition of Mass Surveillance & Third-Party Biometric Scraping:**
   - The platform contains **zero** scrapers or connectors for social media facial indexing, Clearview AI, PimEyes, or live CCTV facial tracking.
   - Public traffic/weather camera feeds (`M03`) are strictly separated from biometric gallery matching.
3. **Consent-Gated Reference Gallery (`consented_face_gallery` + `ConsentGuard`):**
   - Enrolling a reference subject (`POST /api/v1/visual/gallery/enroll`) requires `consent_attestation: true`, a documented `consent_purpose`, and an automatic expiration timestamp (`expires_at`, maximum 90 days).
   - Executing a 1:N similarity check (`POST /api/v1/visual/verify`) requires an active `consent_reason`, rejects expired gallery records, enforces the Laplacian/resolution quality gate ($\sigma_L^2 \ge 40.0$, face crop $\ge 48 	imes 48	ext{ px}$) to prevent false-positive misidentification on degraded images, and writes an immutable entry to the SHA-256 `audit_log` hash chain.

---

## 3. Network, Credential & Audit Security (`M01`)

1. **RFC 9110 SSRF Guard (`SSRFGuard.validate_url`):**
   - Resolves DNS prior to outbound collector requests and blocks loopback (`127.0.0.0/8`, `::1`), private RFC 1918 ranges (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`), link-local (`169.254.0.0/16` cloud metadata), and CGNAT (`100.64.0.0/10`) addresses.
2. **Thread-Safe Circuit Breaker (`CircuitBreaker`):**
   - Protects every external OSINT API adapter with a `threading.Lock()`-synchronized state machine (`CLOSED` $ightarrow$ `OPEN` after 3 consecutive failures $ightarrow$ `HALF_OPEN` after cooldown), automatically falling back to cached or `OFFLINE_BOOTSTRAP` data when an upstream service is unreachable.
3. **Windows DPAPI / Fernet Encrypted Credential Vault (`CredentialVault`):**
   - Optional API keys (`AISSTREAM_API_KEY`, `NASA_FIRMS_KEY`, `CESIUM_ION_TOKEN`, `TELEGRAM_BOT_TOKEN`, `DISCORD_WEBHOOK_URL`) are encrypted at rest using Windows Data Protection API (`CryptProtectData` via `ctypes` on Windows 11) with PBKDF2-HMAC-SHA256 + Fernet fallback on POSIX.
4. **Tamper-Evident SHA-256 Audit Chain (`audit_log`):**
   - Every collection sweep, entity merge, geofence alert, and consent-gated visual verification appends a cryptographically chained record:
     $$H_n = 	ext{SHA256}\left(H_{n-1} \parallel 	ext{timestamp}_n \parallel 	ext{actor}_n \parallel 	ext{action}_n \parallel 	ext{target\_id}_n \parallel 	ext{details\_json}_night)$$
   - `GET /api/v1/audit/verify` recomputes the entire chain from Genesis (`"0" * 64`) and alerts immediately if any historical record was altered in SQLite.
