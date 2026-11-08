# REFERENCE_PLATFORM_RESEARCH.md — Deep Technical & Architectural Teardown of Argos Atlas, Crucix, God's Eye View & Existing Repository

## 1. Executive Summary
To engineer a genuinely next-generation intelligence platform rather than a conventional lookup dashboard, we conducted a deep technical and architectural analysis of the three reference platforms—**Argos Atlas**, **Crucix**, and **God's Eye View**—alongside a complete audit of our existing repository ([`https://github.com/Manan7289/OSINT.git`](https://github.com/Manan7289/OSINT)).

---

## 2. Reference Platform 1: ARGOS ATLAS (`argosatlas.com` / `argos.foundation`)

### 2.1 Product & Technical Architecture Analysis
- **Official References:** [Argos Foundation](https://www.argos.foundation/) and [Argos Atlas Platform Analysis](https://climairshop.it/community/nachrichten/exploration-astronomy-vabako/).
- **Core Capabilities Studied:**
  1. **Unified Multi-Domain Crisis & Asset Map:** Overlays **16 active conflict fronts**, **1,600+ geolocated events** (verified by matching photo/video evidence to satellite/street imagery), and **80 GPS-jamming zones** on the same canvas as live moving assets.
  2. **Sanctions-Cross-Referenced Aviation & Maritime Tracking:** Simultaneously renders ~14,000 live aircraft (including military transponders) and ~20,000 maritime vessels, **automatically cross-referencing and flagging 1,559 vessels and 342 aircraft on the US OFAC sanctions list**.
  3. **Public Camera Aggregation:** Integrates 200,000+ public traffic and municipal webcams directly onto the map so an analyst inspecting a port, border crossing, or highway can open nearby live camera feeds in one click.
  4. **Strategic Country & Infrastructure Depth (`Argos Radar`):** Tracks 25+ infrastructure layers (power grids, military installations, embassies, hospitals, trade flows, resource dependencies) plus geofence alerting (`ARGOS PRO`) when a tracked ship or aircraft enters a watched polygon.
- **Strengths:** Best-in-class operational fusion of *static infrastructure + dynamic moving assets (ships/planes) + sanctions screening + geolocated media/cameras*.
- **Limitations & Gaps:**
  - Proprietary closed-source web SaaS (no local-first data ownership; advanced history, geofence alerts, and AI analyst are locked behind `ARGOS PRO` paid tiers).
  - Lacks deep document forensics (PDF/EXIF), probabilistic entity resolution (Fellegi-Sunter EM), and W3C PROV / Subjective Logic mathematical source-independence scoring.
- **Licensing & Legal Rule:** Proprietary commercial platform. We **must not** copy Argos Atlas branding, proprietary assets, or closed source code; instead, we engineer our own clean-room **Sanctions-Cross-Referenced ADS-B/AIS + Geofence + Public Camera Correlation Engine** using open data ([OpenSanctions](https://www.opensanctions.org/docs/api/), [OpenSky](https://github.com/debjit450/skywatch-live), [AISStream](https://grokipedia.com/page/AISStreamio), DOT open camera feeds).

---

## 3. Reference Platform 2: CRUCIX (`crucix.live` / `github.com/calesthio/Crucix`)

### 3.1 Source Code & Architecture Inspection
- **Official Repository:** [`https://github.com/calesthio/Crucix`](https://github.com/calesthio/Crucix) ([README](https://github.com/calesthio/Crucix/blob/master/README.md), [`.env.example`](https://github.com/calesthio/Crucix/blob/master/.env.example), [Live Demo](https://crucix.live/)).
- **Implementation Stack Inspected:**
  - **Runtime:** Node.js 22+ single-process server (`node server.mjs` on port `3117`) with a diagnostic health checker (`node diag.mjs`).
  - **Collection Engine:** Polls **25–27 open-source intelligence feeds in parallel every 15 minutes** (covering NASA FIRMS satellite fire detection, flight tracking, radiation monitoring, satellite constellations, economic/market indicators, conflict events, OFAC sanctions, GDELT, and RSS/Telegram).
  - **The "Sweep Delta" Innovation:** After each 15-minute collection sweep, Crucix compares the current snapshot $S_t$ against the previous snapshot $S_{t-1}$ to compute a structured **Sweep Delta** (what newly appeared, what escalated in severity/count, and what de-escalated), pushing the delta to all connected browsers via **Server-Sent Events (SSE)**.
  - **Two-Way Messaging & Alerting Pipeline:** Connects to **Telegram** and **Discord** bots to push multi-tier alerts when sweep deltas cross thresholds and responds to interactive analyst commands (`/brief`, `/sweep`).
- **Strengths:** Exceptional "personal intelligence agent that watches the world while you sleep" workflow; the **Sweep Delta** panel immediately tells the analyst *what changed* rather than forcing them to re-read static dashboards.
- **Limitations & Technical Problems Identified in Repo:**
  - **Ephemeral In-Memory / Flat State:** Lacks a bitemporal relational/property-graph database (SQLite WAL/R*Tree) for long-term multi-hop link analysis and entity resolution.
  - **Large Feed Timeout Bug:** As documented in Crucix's own commit history ([`fix(ofac): stop downloading 267 MB per sweep; source always timed out`](https://github.com/calesthio/Crucix/actions)), naive full-feed downloads without HTTP `ETag`/`If-Modified-Since` conditional caching and circuit breakers cause sweep timeouts.
- **Licensing Compliance (`AGPL-3.0`):** Crucix is licensed under **GNU AGPL-3.0** ([Star History / License](https://www.star-history.com/calesthio/crucix/)). To maintain clean licensing in our Python/FastAPI repository (`https://github.com/Manan7289/OSINT.git`), we **do not copy any JavaScript source code from `calesthio/Crucix`**. Instead, we design an original Python/SQLite **Bitemporal Sweep-Delta & Alerting Engine** with `ETag`/`Last-Modified` delta caching and WebSocket/SSE push.

---

## 4. Reference Platform 3: GOD'S EYE VIEW (`godseyeview.ai` / `github.com/bilawalsidhu/gods-eye-view`)

### 4.1 Source Code & Architecture Inspection
- **Official Repository:** [`https://github.com/bilawalsidhu/gods-eye-view`](https://github.com/bilawalsidhu/gods-eye-view) ([`package.json`](https://github.com/bilawalsidhu/gods-eye-view/blob/main/package.json), [`docs/CURRENT-STATE.md`](https://github.com/bilawalsidhu/gods-eye-view/blob/main/docs/CURRENT-STATE.md), [`DATA_SOURCES.md`](https://github.com/bilawalsidhu/gods-eye-view/blob/main/DATA_SOURCES.md), [`LICENSE`](https://github.com/bilawalsidhu/gods-eye-view/blob/main/LICENSE)).
- **Implementation Stack Inspected:**
  - **3D Rendering Engine:** Built on **CesiumJS** (`cesium` WebGL globe) with **keyless Esri World Imagery + keyless terrain** out of the box, automatic fallback to **OpenStreetMap** when offline/unreachable, and optional in-app upgrade ("POWER UP panel") for **Cesium ion** or **Google Photorealistic 3D Tiles**.
  - **Orbital & Spatial Layers:** Uses `satellite.js` (`SGP4` / `SDP4` propagator) to compute real-time sub-satellite points, altitudes, and orbital tracks from live **CelesTrak GP/TLE** feeds; overlays **OpenSky Network** & **ADSB.lol** (`api.adsb.lol/v2/mil` military flights), **USGS Earthquake GeoJSON**, **TxDOT / municipal traffic cameras**, **OpenStreetMap ALPR camera tags**, and **GPSJam** (`gpsjam.org` H3 hexagonal interference cells).
  - **Performance & Honest Telemetry Design:** Skips Cesium's per-model environment map for faster aircraft rendering ([Releases](https://github.com/bilawalsidhu/gods-eye-view/releases)), and explicitly labels which layers are live (`OpenSky`, `USGS`, `CelesTrak`) vs. coarse estimates/simulations (road traffic flow, camera poses).
- **Strengths:** Instant zero-key out-of-the-box 3D globe experience with seamless optional photorealistic 3D tile upgrades and exemplary transparency regarding data quality.
- **Limitations & Gaps:**
  - Purely a browser-based spatial visualizer—lacks a persistent local investigative database, cross-source entity resolution, document/visual forensics, W3C PROV evidence custody, and automated sweep-delta alerting.
- **Licensing Compliance (`MIT` with Media Carve-out):** The code in [`bilawalsidhu/gods-eye-view/blob/main/LICENSE`](https://github.com/bilawalsidhu/gods-eye-view/blob/main/LICENSE) is **MIT-licensed**, with a specific carve-out in [`docs/media/README.md`](https://github.com/bilawalsidhu/gods-eye-view/blob/main/docs/media/README.md) prohibiting reuse of Bilawal Sidhu's personal promotional PNGs/media. We strictly exclude all media/branding from `gods-eye-view` and build our own clean 2D/3D geospatial engine.

---

## 5. Audit of Our Existing Repository (`https://github.com/Manan7289/OSINT.git`)

We inspected all 14 commits (`ad99151` through `8ba4a70`) on the `main` branch of [`https://github.com/Manan7289/OSINT`](https://github.com/Manan7289/OSINT) (~5,600+ LOC). Below is our engineering decision matrix on what to **Retain**, **Fix & Upgrade**, or **Replace**:

| Existing File in `Manan7289/OSINT` | Current Status (LOC) | Redesign Decision | Technical Justification |
| :--- | :--- | :---: | :--- |
| `backend/core/config.py` & `security.py` | Working (`M01`) | **RETAIN & EXTEND** | Keep 256-bit Fernet `CryptoVault`, `TokenBucketRateLimiter`, `CircuitBreaker`, `OPSECGuard`, and `HashChainedAuditLogger`. Add SSRF private-IP validator and Telegram/Discord webhook secrets to Vault. |
| `backend/core/database.py` & `ontology.py` | Working (1,101 LOC, `M02`) | **RETAIN & EXTEND** | Keep all 14 tables (`WAL` + `FTS5` + `R*Tree`). Add 4 new tables for the v3.0 vision: `spatiotemporal_tracks` (moving aircraft/ships/satellites), `sweep_snapshots` & `sweep_deltas` (Crucix delta engine), `visual_evidence_assets` & `consented_face_gallery` (Visual Intel), and `alert_rules` & `alert_notifications`. |
| `backend/collectors/orchestrator.py` | Partial (693 LOC, `M03`) | **UPGRADE** | Fix the Windows sequential `urllib.request` bottleneck (`L100–260`) using `ThreadPoolExecutor(max_workers=12)` + HTTP `ETag`/`If-Modified-Since` caching, and add the **12 Live Geospatial/Orbital/Aviation/Maritime/Camera Connectors** + **Scheduled Sweep-Delta Runner**. |
| `backend/core/entity_resolution.py` | Partial (511 LOC, `M05`) | **RETAIN & FIX** | Keep 3-pass blocking (`PHONETIC_SORT`, `APEX_PREFIX`, `MINHASH_LSH`) + Fellegi-Sunter EM + Reversible Merge. Add Bayesian Beta smoothing ($lpha_m=8,eta_m=1; lpha_u=1,eta_u=9$) and non-person vessel/aircraft identifier matching (`IMO`, `MMSI`, `ICAO24`, `Callsign`, `NORAD_CAT_ID`). |
| `backend/core/provenance_fusion.py` | Working (`M06`) | **RETAIN** | Keep W3C PROV DAG, Dong copying discount, and Jøsang Subjective Logic ($\oplus$ vs. $	ilde{\oplus}$). |
| `backend/core/graph_analytics.py` & `spatiotemporal.py` | Working (289+ LOC, `M07`) | **RETAIN & EXTEND** | Keep Leiden communities, IEF-PageRank, Adamic-Adar, Haversine HDBSCAN, and Kleinberg burst detection. Add **Geofence Polygon Point-in-Polygon (Ray-Casting)** and **Spatiotemporal Proximity Correlator** (linking events within $\Delta d \le R	ext{ km}$ and $\Delta t \le W	ext{ hours}$). |
| `backend/ai/search_rrf.py` & `assistant.py` | Working (408 LOC, `M08`) | **RETAIN & EXTEND** | Keep Hybrid RRF ($k=60$) and GraphRAG `[ev_id]` citation validator. Add **Regional Intelligence Briefing Generator** (summarizing everything inside a user-drawn bounding box/polygon) and **Sweep-Delta Briefing Generator**. |
| `frontend/index.html`, `styles.css`, `app.js` | Basic Dashboard (2,140+ LOC, `M10`) | **MAJOR REDESIGN** | Transform the traditional sidebar-table layout into a **Full-Viewport Global Intelligence Command Centre** featuring an interactive **2D/3D Globe & Tactical Map (`CesiumJS` / `Globe.gl` + `MapLibre GL`)**, Collapsible Layer Manager, 4D Historical Playback Timeline Scrubber, Live Sweep-Delta Ticker, Visual Intelligence Studio, and Link-Analysis Graph Dock. |
