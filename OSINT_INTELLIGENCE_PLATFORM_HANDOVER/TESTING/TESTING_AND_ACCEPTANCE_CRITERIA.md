# 12 — TESTING AND ACCEPTANCE CRITERIA (`LocalOSINT v3.0`)

**Target Repository:** [`https://github.com/Manan7289/OSINT.git`](https://github.com/Manan7289/OSINT.git)  
**Test Framework:** `pytest` + `fastapi.testclient.TestClient`  
**Requirement:** Zero mock-only endpoints, 100% automated test pass rate, and verifiable end-to-end execution across all 12 modules (`M01`–`M12`).

---

## 1. Automated Test Suite Architecture (`tests/`)

Antigravity must maintain and execute three comprehensive test modules under `tests/`:
1. `tests/test_api_smoke.py` — Validates all core v2.0 + v3.0 REST endpoints, SQLite 20-table schema integrity, Blocked Fellegi-Sunter EM with `Beta(1,1)` smoothing, W3C PROV + Subjective Logic fusion, Leiden + IEF-PageRank, Hybrid RRF search, Grounded GraphRAG citation enforcement, and SHA-256 audit chain integrity.
2. `tests/test_geospatial_and_sweeps.py` — Validates `SGP4` satellite orbital propagation (`CelesTrak`), Aviation (`OpenSky`/`ADSB.lol`) and Maritime (`Digitraffic AIS`) normalization, OFAC SDN sanctions cross-referencing (`sanctions_index`), AIS Dark-Ship gap detection, 4D historical trajectory replay (`/api/v1/geospatial/replay`), Point-in-Polygon geofence breach detection, and Crucix-style Sweep-Delta generation (`/api/v1/sweeps/run`).
3. `tests/test_visual_privacy.py` — Validates `M11` Privacy-Preserving Visual Intelligence: EXIF/GPS extraction, 64-bit `pHash`/`dHash`/`aHash` computation and Hamming distance search ($d_H \le 10$), Laplacian sharpness quality gate ($\sigma_L^2 < 40.0$ rejection), mandatory automatic bystander face blurring, and `ConsentGuard` rejection of unconsented face verification requests.

---

## 2. Module-by-Module Acceptance Criteria Matrix

| Module | Acceptance Criterion | Verification Test / Command | Pass Threshold |
| :--- | :--- | :--- | :--- |
| **M01 Security & Config** | Thread-safe `CircuitBreaker`, RFC 9110 SSRF block on RFC1918/loopback IPs, and unbroken SHA-256 `audit_log` chain. | `test_ssrf_and_circuit_breaker()` + `GET /api/v1/audit/verify` | `chain_valid == True` & `127.0.0.1` SSRF blocked |
| **M02 20-Table SQLite DB** | All 20 tables (`entities`, `edges`, `geo_tracks`, `sweep_runs`, `sweep_deltas`, `sanctions_index`, `geofence_zones`, `visual_assets`, `consented_face_gallery`, etc.) created in WAL mode. | `test_database_20_tables_initialized()` | 20/20 tables present, `journal_mode == "wal"` |
| **M03 Geospatial & OSINT Collectors** | Parallel `ThreadPoolExecutor(8)` orchestrator ingests Aviation, Maritime, Satellite, Earthquake, Wildfire, Weather, Camera, Cyber, and Sanctions feeds with honest `telemetry_status` badges. | `POST /api/v1/sweeps/run` + `GET /api/v1/geospatial/layers` | Speedup $\ge 2.5	imes$ over sequential; all layers return valid GeoJSON |
| **M04 Sweep-Delta Engine** | Consecutive sweeps compute accurate deltas (`NEW_ENTITY`, `SANCTION_MATCH_DETECTED`, `ESCALATED_RISK`, `ENTERED_GEOFENCE`) and Global Escalation Score $E_{	ext{sweep}} \in [0,100]$. | `test_crucix_sweep_delta_engine()` | Deltas persisted in `sweep_deltas` & linked to `sweep_id` |
| **M05 Fellegi-Sunter + Sanctions** | `Beta(1,1)` smoothed EM converges without `0.0`/`1.0` collapse; aircraft `icao24`/tail and vessel `mmsi`/`imo` match against `sanctions_index`. | `test_fellegi_sunter_and_ofac_matching()` | Known OFAC vessel/aircraft flagged `is_sanctioned == True` |
| **M06 Provenance & Fusion** | Josang Subjective Logic cumulative ($\oplus$) and averaging ($	ilde{\oplus}$) fusion satisfy $b + d + u = 1.0 \pm 10^{-6}$. | `test_subjective_logic_fusion()` | Exact simplex conservation $b+d+u=1.0$ |
| **M07 Graph Analytics** | Leiden community detection and IEF-weighted PageRank execute on the combined Cyber + Geospatial + Sanctions graph. | `GET /api/v1/graph/{inv_id}/communities` | Non-empty communities & hub suppression verified |
| **M08 Hybrid RRF & SitRep AI** | RRF ($k=60$) fuses BM25 + Vector search; `validate_citations()` enforces `valid_ratio == 1.0`; `/api/v1/sweeps/latest/briefing` generates cited Markdown SitRep. | `test_citation_validator_and_briefing()` | Uncited sentences stripped; `valid_ratio == 1.0` |
| **M09 4D Spatiotemporal & SGP4** | `sgp4` propagates TLEs to exact WGS84 `(lat, lon, alt_km)` + footprint radius; 4D replay returns historical tracks for any timestamp window. | `test_sgp4_propagation_and_4d_replay()` | ISS / active satellite lat $\in [-90, 90]$, alt $> 150	ext{ km}$ |
| **M10 2D/3D Command Centre UI** | Full-viewport 5-Zone HUD loads MapLibre 2D + Globe 3D, toggles layers, scrubs 4D timeline, displays Sweep-Deltas, and opens Visual Studio. | Browser verification at `http://127.0.0.1:8420` | Zero console errors, zero dead buttons |
| **M11 Visual Intelligence Studio** | Extracts EXIF/GPS, computes 64-bit `pHash`, auto-blurs detected faces by default, flags blurry/low-res faces ($\sigma_L^2 < 40$), and blocks unconsented verification. | `pytest tests/test_visual_privacy.py` | Unconsented verify returns HTTP 403; blurred image differs from raw ROI |
| **M12 Geofence & Alerting** | Ray-casting point-in-polygon triggers `ENTERED_GEOFENCE` delta and broadcasts on `/api/v1/stream` SSE when an asset enters an active zone. | `test_geofence_point_in_polygon_alert()` | Inside point triggers alert; outside point does not |
