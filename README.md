# LocalOSINT v3.0 — Next-Generation Global Intelligence Command Centre

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12-blue.svg)](https://www.python.org/)
[![Database SQLite WAL](https://img.shields.io/badge/Storage-SQLite%20WAL%2020--Table%20Schema-green.svg)](https://www.sqlite.org/)
[![FastAPI](https://img.shields.io/badge/API-FastAPI%20%2B%20SSE%20Stream-teal.svg)](https://fastapi.tiangolo.com/)
[![Tests Passing](https://img.shields.io/badge/Tests-80%2F80%20Passed%20(100%25)-success.svg)](https://github.com/Manan7289/OSINT.git)
[![Architecture CPU-Only](https://img.shields.io/badge/Hardware-100%25%20CPU%20Friendly-orange.svg)]()
[![Privacy Ethical Guard](https://img.shields.io/badge/Privacy-Mandatory%20Bystander%20Blur-purple.svg)]()

**LocalOSINT v3.0** is an autonomous, local-first **Global Intelligence Command Centre** that unifies the strongest capabilities of:
1. **Argos Atlas (`argosatlas.com`):** Real-time commercial & military aviation tracking, maritime AIS vessel tracking, automated US Treasury OFAC SDN sanctions cross-referencing, GPS/GNSS interference heatmaps, public traffic/weather cameras, and event-to-asset spatial proximity correlation.
2. **Crucix (`crucix.live`):** Local-first terminal with automated 15-minute scheduled parallel sweeps, Sweep-Delta Analysis (`NEW_ENTITY`, `SANCTION_MATCH_DETECTED`, `ESCALATED_RISK`, `ENTERED_GEOFENCE`, `AIS_DARK_GAP`, `RESOLVED_EVENT`), Global Escalation Score ($E_{\text{sweep}} \in [0, 100]$), real-time SSE push (`GET /api/v1/stream`), Telegram/Discord webhook alerts, and grounded AI SitRep briefings.
3. **God's Eye View (`godseyeview.ai`):** Keyless-first 2D/3D Earth canvas (`MapLibre GL JS` / `Leaflet` + `Globe.gl` 3D orbital globe), real-time `SGP4` satellite orbital propagation (`CelesTrak`), 4D historical time-scrubber trajectory playback, and honest telemetry status badges (`LIVE`, `DELAYED`, `SGP4`, `HISTORICAL`, `BOOTSTRAP`).
4. **Privacy-Preserving Visual Intelligence Studio (M11):** Local CPU-executable OpenCV YuNet face detection, mandatory default bystander face blurring (`blur_bystanders=True`), Laplacian sharpness quality gate ($\sigma_L^2 \ge 40.0$, crop $\ge 48\times 48\text{ px}$), 64-bit perceptual hashing (`pHash`, `dHash`, `aHash`) with Hamming distance deduplication ($d_H \le 10$), EXIF/GPS/C2PA forensic metadata extraction, and strictly consent-gated SFace 128-D cosine verification against an authorized local gallery (`consented_face_gallery`).

---

## 🏛️ System Architecture

```text
+------------------------------------------------------------------------------------------------------------------+
| LOCALOSINT v3.0 TACTICAL HUD COMMAND CENTRE (100vw x 100vh)                                                      |
| [2D Map | 3D Globe] | Region Presets | Global Escalation Gauge | Hybrid RRF Search (Ctrl+K) | Visual Studio Modal|
+--------------------------+------------------------------------------------------------+--------------------------+
| ZONE 2: LAYER & SWEEP    |                                                            | ZONE 4: ENTITY, GRAPH    |
| MANAGER (Left HUD 320px) |             ZONE 1: INTERACTIVE 2D / 3D EARTH              | & PROVENANCE INSPECTOR   |
|                          |             (Leaflet Dark/Sat + Globe.gl 3D)               | (Right HUD 400px)        |
| [x] Aviation (Live)      |                                                            |                          |
| [x] Military (Live)      |                   * [SAT: ISS (SGP4)]                      | Selected Asset Details   |
| [x] Maritime AIS (Live)  |                      /                                     | Sanction Match Alert Box |
| [x] OFAC Sanctions       |        +------------+                                      | Subjective Logic (b,d,u) |
| [x] Satellites (SGP4)    |        |  [AIR: USAF RCH412]                               | Admiralty Rating (A1)    |
| [x] Quakes & Hazards     |        |                                                   | Cytoscape.js 2-Hop Graph |
| [x] GPS Jamming Zones    |   (( [VESSEL: BEHSHAD - OFAC FLAGGED] ))                   | Fellegi-Sunter Unmerge   |
| [x] Public Cameras       |         \--- 18 km ---> [CAM: Port CCTV]                   |                          |
|                          |                                                            |                          |
| --- CRUCIX SWEEP-DELTAS -|   +----------------------------------------------------+   |                          |
| ! [CRIT] Vessel in zone  |   | ZONE 3: VISUAL INTELLIGENCE STUDIO (Modal/Drawer)  |   |                          |
| ^ [HIGH] M5.8 Earthquake |   | [EXIF/GPS Forensics | Default Bystander Blur]      |   |                          |
| + [NEW] 14 CVE Entities  |   | [Laplacian Sharpness Gate | ConsentGuard SFace]    |   |                          |
| [Run Sweep Now]          |   +----------------------------------------------------+   |                          |
+--------------------------+------------------------------------------------------------+--------------------------+
| ZONE 5: 4D SPATIOTEMPORAL TIME SCRUBBER & STATUS DOCK (Bottom Dock 68px)                                         |
| [▶] [1x|10x|60x] [LIVE] |=====[2026-11-09 00:00 UTC]=====*--------------------------| [Draw Geofence] [Export]  |
+------------------------------------------------------------------------------------------------------------------+
```

---

## 📦 SQLite 20-Table WAL Schema

The underlying SQLite persistence layer operates in high-performance Write-Ahead Logging (`WAL`) mode with `-64000` page cache (64 MB in-memory cache) and covers 20 dedicated tables:

1. `workspaces` — Multi-case investigation isolation with OPSEC modes (`STANDARD`, `PASSIVE_ONLY`) and TLP markings.
2. `evidence_artifacts` — W3C PROV immutable provenance artifacts with SHA-256 payload hashing and SimHash-64 deduplication.
3. `entities` — FollowTheMoney canonicalized entities (Actors, Companies, Aircraft, Vessels, Satellites, Cameras, IP, Domains).
4. `entity_blocking_keys` — Fast candidate generation indexes for 3-pass Fellegi-Sunter entity resolution.
5. `claims` — Bitemporal property graph edges with Subjective Logic belief tuples $\omega = (b, d, u, a)$ and epistemic status.
6. `claim_evidence` — Many-to-many relationship linking claims to corroborating evidence artifacts.
7. `entity_merge_ledger` — Reversible merge transaction ledger allowing 1-click unmerge and relationship rollback.
8. `timeline_events` — Temporal event index powering Kleinberg Poisson burst detection ($Z \ge 2.5$).
9. `vector_embeddings` — Dense INT8/FP32 vector embeddings for hybrid reciprocal rank fusion (RRF $k=60$) search.
10. `connector_configs` — Encrypted credential vault (Fernet AES-128-CBC) and rate limits.
11. `tasks` — Background collection job tracker and entity/claim yield ledger.
12. `reports` — Grounded GraphRAG intelligence reports with verified inline citations (`[ev_id]`).
13. `http_cache` — Conditional HTTP caching headers (`ETag`, `Last-Modified`) preventing redundant bandwidth.
14. `audit_logs` — Tamper-evident SHA-256 hash-chained audit ledger ($H_k = \text{SHA256}(H_{k-1} \parallel \dots)$).
15. `app_settings` — Runtime operational parameters and active OPSEC configuration.
16. `geo_tracks` — Kinetic geospatial points (AIRCRAFT, VESSEL, SATELLITE, CAMERA, HAZARD) with telemetry status badges.
17. `sweep_runs` — Crucix scheduled collection sweep records and Global Escalation Scores ($E_{\text{sweep}} \in [0, 100]$).
18. `sweep_deltas` — Structured sweep diffs (`NEW_ENTITY`, `SANCTION_MATCH_DETECTED`, `ESCALATED_RISK`, `ENTERED_GEOFENCE`, `AIS_DARK_GAP`).
19. `sanctions_index` — Fast in-memory and SQLite-backed OFAC SDN sanctions lookup (MMSI, IMO, ICAO24, tail number, SDN name).
20. `geofence_zones` — User-defined watch zones evaluated via deterministic ray-casting point-in-polygon logic.
21. `visual_assets` — Photographic intelligence records with EXIF, GPS, C2PA, 64-bit perceptual hashes (`pHash`, `dHash`, `aHash`), Laplacian sharpness scores, and redacted crops.
22. `consented_face_gallery` — Consent-gated authorized facial reference gallery with mandatory 90-day expiration and audit tracking.

---

## ⚡ Quick Start (Windows 11)

### 1. Automated Installation
Double-click `install.bat` or run:
```powershell
.\install.bat
```
This will:
- Detect your Python 3.10+ environment.
- Create an isolated virtual environment (`.venv`).
- Install all dependencies (`fastapi`, `uvicorn`, `opencv-python-headless`, `sgp4`, `imagehash`, `igraph`, `Pillow`, etc.).
- Download/verify OpenCV YuNet and SFace ONNX neural models into `data/models/`.
- Initialize the 20-table SQLite WAL database and seed demonstration cases.

### 2. Launching the Command Centre
Double-click `start.bat` or run:
```powershell
python run.py
```
Open your browser to: **`http://127.0.0.1:8000`**

---

## 🧪 Automated Test Verification

LocalOSINT v3.0 includes an 80-test automated verification suite across all 12 modules with 100% pass rate:
```powershell
pytest -v
```

### Key Test Suites:
- `tests/test_api_smoke.py`: Tests 20-table SQLite schema, v3.0 REST endpoints, and SHA-256 audit log chain.
- `tests/test_geospatial_and_sweeps.py`: Tests real-time SGP4 orbital satellite propagation, OpenSky/Digitraffic normalization, OFAC cross-referencing, ray-casting geofence evaluation, AIS dark-ship gap detection, and Crucix sweep-deltas.
- `tests/test_visual_privacy.py`: Tests EXIF/GPS extraction, 64-bit pHash Hamming distance search, default bystander face blurring, Laplacian sharpness quality gate, and ConsentGuard unconsented verification blocking.
- `tests/test_m01_security.py` through `tests/test_m10_frontend.py`: Core mathematical, resolution, graph, search, and UI tests.

---

## 🛡️ Privacy & Ethical AI Architecture

- **Zero Unconsented Biometric Surveillance:** The platform enforces an architectural barrier (`ConsentGuard`). Automated stranger identification is physically blocked. Face enrollment and verification require documented investigation purpose, affirmative consent attestation, and are recorded in the tamper-evident SHA-256 audit ledger.
- **Mandatory Default Bystander Redaction:** All processed intelligence photos apply automated Gaussian blur + mosaic pixelation over detected faces by default (`blur_bystanders=True`).
- **Laplacian Quality Gate:** Biometric matching requests are rejected if image sharpness variance $\sigma_L^2 < 40.0$ or face crop $< 48\times 48\text{ px}$ to eliminate low-resolution false-positive misidentifications.
- **Honest Telemetry Policy:** The platform strictly distinguishes between `LIVE` telemetry, `SGP4` mathematical propagation, `HISTORICAL` playback, and `OFFLINE_BOOTSTRAP` fallback. Offline data is never mislabeled as live.

---

## 📜 License
Internal OSINT Research & Intelligence Framework. Follows Apache 2.0 / MIT licensing. Contains zero proprietary code or unlicensed assets.
