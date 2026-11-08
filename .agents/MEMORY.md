# Workspace Memory: LocalOSINT v3.0 (Global Intelligence Command Centre)

## Project Overview
- **Repository**: https://github.com/Manan7289/OSINT.git (branch: main)
- **Objective**: Upgrade from v2.0 to LocalOSINT v3.0 Global Intelligence Command Centre.
- **Reference Architectures Unified**:
  1. Argos Atlas: Live commercial/military flights, maritime AIS, automated OFAC SDN sanctions cross-referencing, GPS interference, public traffic/weather cameras, event-asset spatial proximity correlation.
  2. Crucix: Local-first intelligence terminal, automated 15-minute scheduled parallel sweeps, Sweep-Delta analysis (NEW_ENTITY, SANCTION_MATCH_DETECTED, ESCALATED_RISK, ENTERED_GEOFENCE, AIS_DARK_GAP, RESOLVED_EVENT), Global Escalation Score E_sweep in [0, 100], SSE push, Telegram/Discord webhooks, grounded AI SitRep briefings.
  3. God's Eye View: Keyless 2D/3D globe (MapLibre GL JS + Globe.gl/CesiumJS), real-time SGP4 satellite propagation (CelesTrak), 4D historical playback, honest telemetry badges (LIVE, DELAYED, ORBITAL_PROPAGATED, HISTORICAL, OFFLINE_BOOTSTRAP).
  4. Privacy-Preserving Visual Intelligence Studio (M11): OpenCV YuNet face detection (Haar fallback), mandatory bystander blurring (blur_bystanders=True), Laplacian quality gate (var >= 40.0, crop >= 48x48 px), 64-bit pHash/dHash/aHash (Hamming <= 10), EXIF/GPS/C2PA metadata, consent-gated SFace 128-D cosine verification.

## 7-Milestone Roadmap Status
- [x] Milestone 1: Fix v2.0 Core Defects & Expand SQLite Schema to 20 Tables (M01, M02, M05, M08) - COMPLETED
  - CircuitBreaker thread-safety synchronized with `threading.Lock()` & `allow_request()`
  - FellegiSunterResolver with Bayesian Beta smoothing & `cross_reference_sanctions()`
  - Citation validator `validate_citations()` enforcing `valid_ratio == 1.0` and `stripped_sentences == 0`
  - Ontology & SQLite schema expanded to 20 tables with CRUD methods
- [x] Milestone 2: Build Live Geospatial, Aviation, Maritime, Orbital, Hazard & Camera Collectors (M03, M09) - COMPLETED
  - OFAC SDN Sanctions Loader (`sanctions_loader.py`) with memory index & bootstrap
  - Live & Military Aviation Adapter (`aviation_adapter.py`) with emergency squawk & GPS interference detection
  - Maritime AIS Adapter (`maritime_adapter.py`) with OFAC check & dark-ship gap detection
  - Satellite SGP4 Orbital Propagator (`satellite_adapter.py` & `spatiotemporal.py`)
  - Natural Events & Disaster Adapter (`natural_events_adapter.py`) with USGS, NASA EONET, NOAA
  - Public Traffic/Weather Cameras Adapter (`camera_adapter.py`)
  - Parallel ThreadPoolExecutor(8) in `orchestrator.py`
- [x] Milestone 3: Implement Crucix-Style Sweep-Delta Engine (M04) - COMPLETED
  - `SweepDeltaEngine` in `sweep_delta.py` with delta taxonomy and Global Escalation Score $E_{\text{sweep}} \in [0, 100]$
  - REST endpoints `POST /api/v1/sweeps/run`, `GET /api/v1/sweeps/latest`, `GET /api/v1/sweeps/{sweep_id}/deltas`, `GET /api/v1/sweeps/latest/briefing`
- [x] Milestone 4: Implement Privacy-Preserving Visual Intelligence Studio (M11) - COMPLETED
  - Media forensics (`media_forensics.py`) with EXIF/GPS/C2PA extraction, 64-bit perceptual hashes (`pHash`, `dHash`, `aHash`), Hamming search ($d_H \le 10$)
  - Vision engine (`vision_engine.py`) with YuNet ONNX detection, Laplacian sharpness $\sigma_L^2$ quality gate, mandatory bystander blurring
  - ConsentGuard (`consent_guard.py`) enforcing legal consent attestation, 90-day gallery expiration, SHA-256 audit log, and SFace 128-D cosine verification
  - REST endpoints `POST /api/v1/visual/analyze`, `POST /api/v1/visual/gallery/enroll`, `POST /api/v1/visual/verify`, `GET /api/v1/visual/assets`
- [x] Milestone 5: Implement Geofence Watch Zones, SSE Real-Time Push & Alerting (M12) - COMPLETED
  - Alert engine (`alert_engine.py`) with ray-casting point-in-polygon evaluation, SSE event broadcasting (`GET /api/v1/stream`), Telegram/Discord webhook dispatchers
  - REST endpoints `POST /api/v1/geofences`, `GET /api/v1/geofences`, `DELETE /api/v1/geofences/{geofence_id}`
- [x] Milestone 6: Build the 5-Zone 2D/3D Global Command Centre UI (M10) - COMPLETED
  - Full-viewport 5-zone tactical layout (`index.html`, `styles.css`)
  - Dual 2D Map (Leaflet) & 3D Globe (`Globe.gl`) synchronized canvas (`globe_map.js`)
  - Layer Manager & Crucix Sweep-Delta ticker (`sweep_delta_hud.js`)
  - 4D Spatiotemporal Time Scrubber (`timeline_4d.js`) with 1x/10x/60x playback
  - Privacy-Preserving Visual Studio modal (`visual_studio.js`)
  - Main state coordinator (`app.js`) with SSE stream listener, Cytoscape.js ego-graph, Subjective Logic inspector
- [x] Milestone 7: Run Full Verification Suite, Update Windows Scripts & Push to GitHub - COMPLETED
  - Requirements, installation batch scripts (`install.bat`, `start.bat`), `.env.example`, `README.md` updated
  - Full automated test suite passes 80/80 tests (100%) across all 12 modules
  - Ready for Git push to `main`

## Critical Guardrails Maintained
- No licensing violations: Clean-room implementation, no copying AGPL-3.0 JS or restricted media.
- No dishonest telemetry: Accurate badges (LIVE, DELAYED, SGP4, HISTORICAL, OFFLINE_BOOTSTRAP).
- No unconsented biometric surveillance: ConsentGuard, default bystander face blurring, Laplacian/resolution quality gate.
- No fake UI controls: Every button/scrubber wired to real backend or client-side WebGL/SGP4 action.
